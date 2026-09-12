"""Tray application: owns the engine, the log source and one GroupWindow per layout group.

- Shows the overlay only while swtor.exe is running (configurable).
- Hot-reloads profiles when any profiles/*.json changes.
- Plays a rule's sound when its item first appears.
- Tray menu: enable, lock, settings, reload, open profiles folder, quit.
Reads the log file and the Windows process list. Never touches the game.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

import gamewatch
import settings as settings_mod
from overlay import GroupWindow
from parser import parse_line
from rules import PROFILE_DIR, Engine, Profile, Rule

# item kind -> fallback group when a rule's group no longer exists
DEFAULT_GROUP = {"bar": "buffs", "flash": "alerts", "stacks": "stacks", "cooldown": "cooldowns", "fight": "timer",
                 "missing": "alerts", "cleanse": "alerts", "party": "party"}


def _icon(color=QColor(70, 160, 255)) -> QIcon:
    pm = QPixmap(32, 32)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setBrush(QBrush(color))
    p.setPen(QColor(0, 0, 0, 0))
    p.drawRoundedRect(2, 2, 28, 28, 6, 6)
    p.end()
    return QIcon(pm)


def _speak(text: str):
    """Windows SAPI text-to-speech on a worker thread (pywin32)."""
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        voice.Rate = 2
        voice.Speak(text)
    except Exception:
        pass


def play_sound(spec: str):
    """'beep', 'say:<text>' (spoken), or a .wav path. Silent on any failure."""
    try:
        import winsound
        if spec == "beep":
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
        elif spec.lower().startswith("say:"):
            threading.Thread(target=_speak, args=(spec[4:].strip(),), daemon=True).start()
        elif spec and Path(spec).exists():
            winsound.PlaySound(spec, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass


SIGNAL_FILE = Path(__file__).resolve().parent / ".open_settings"   # written by a second launch


def already_running() -> bool:
    """Single-instance guard: a named Windows mutex that lives as long as this process."""
    try:
        import ctypes
        global _MUTEX
        _MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\SWTOR_Overlay_Tray")
        return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return False


class TrayApp(QObject):
    def __init__(self, qapp: QApplication, source, replay: bool = False, open_settings: bool = False):
        super().__init__()
        self.qapp = qapp
        self.replay = replay
        self.settings = settings_mod.load()
        self.profiles = Profile.load_all()
        self.engine = Engine(self.profiles, global_rules=Profile.load_global())
        self.engine.reload(self.profiles, self._forced())
        self.source = source
        self.enabled = True
        self.windows: dict[str, GroupWindow] = {}
        self._seen_keys: set[str] = set()
        self._profiles_stamp = self._profiles_mtime()
        self.config = None
        self._ensure_windows()
        self._settings_stamp = self._settings_mtime()

        self.tray = QSystemTrayIcon(_icon(), self)
        menu = QMenu()
        self.a_enabled = QAction("Overlay enabled", menu, checkable=True, checked=True)
        self.a_enabled.triggered.connect(self._toggle_enabled)
        self.a_locked = QAction("Lock overlay (click-through)", menu, checkable=True,
                                checked=bool(self.settings.get("locked")))
        self.a_locked.triggered.connect(self._toggle_locked)
        a_settings = QAction("Settings…", menu)
        a_settings.triggered.connect(self.open_settings)
        a_quick = QAction("Quick add ability…", menu)
        a_quick.triggered.connect(self.open_quick_add)
        a_reload = QAction("Reload profiles", menu)
        a_reload.triggered.connect(self.reload_profiles)
        a_folder = QAction("Open profiles folder", menu)
        a_folder.triggered.connect(lambda: os.startfile(PROFILE_DIR))
        a_reset = QAction("Reset group positions", menu)
        a_reset.triggered.connect(self.reset_positions)
        a_quit = QAction("Quit", menu)
        a_quit.triggered.connect(qapp.quit)
        for a in (self.a_enabled, self.a_locked, a_quick, a_settings, a_reload, a_folder, a_reset):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(a_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        self.t_tick = QTimer(self)
        self.t_tick.timeout.connect(self.tick)
        self.t_tick.start(50)
        self.t_game = QTimer(self)
        self.t_game.timeout.connect(self.check_game)
        self.t_game.start(3000)
        self.t_reload = QTimer(self)
        self.t_reload.timeout.connect(self.check_reload)
        self.t_reload.start(1000)
        self.game_running = False
        self.check_game()
        if open_settings:
            QTimer.singleShot(300, self.open_settings)

    # ---- helpers ------------------------------------------------------------------------------
    def _forced(self):
        return None if self.settings.get("auto_switch", True) else (self.settings.get("forced_profile") or None)

    def _profiles_mtime(self) -> float:
        files = list(PROFILE_DIR.glob("*.json")) + list((PROFILE_DIR / "auto").glob("*.json"))
        return max((f.stat().st_mtime for f in files), default=0.0) + len(files)

    def _status(self):
        prof = self.engine.profile.name if self.engine.profile else "no profile"
        state = "locked" if self.settings.get("locked") else "UNLOCKED"
        self.tray.setToolTip(f"SWTOR overlay — {prof} — {state}")

    def group_names(self) -> list[str]:
        return self.engine.group_names(list(self.settings.get("groups", {}).keys()))

    def _ensure_windows(self):
        for name in self.group_names():
            if name not in self.windows:
                cfg = settings_mod.group_cfg(self.settings, name)
                self.windows[name] = GroupWindow(name, cfg, self.settings, self.save_settings)
        self.save_settings()

    def add_group(self, name: str) -> bool:
        name = name.strip()
        if not name or name in self.windows:
            return False
        settings_mod.group_cfg(self.settings, name)
        self._ensure_windows()
        return True

    def remove_group(self, name: str) -> bool:
        """Delete a user group. Rules pointing at it fall back to their type's default group."""
        if name in settings_mod.DEFAULT_GROUP_LAYOUT or name not in self.windows:
            return False
        self.windows.pop(name).close()
        self.settings.get("groups", {}).pop(name, None)
        self.save_settings()
        return True

    def save_settings(self):
        settings_mod.save(self.settings)
        self._settings_stamp = self._settings_mtime()

    @staticmethod
    def _settings_mtime() -> float:
        try:
            return settings_mod.SETTINGS_PATH.stat().st_mtime
        except OSError:
            return 0.0

    def _reload_settings_from_disk(self):
        """settings.json was edited by hand while running: adopt it instead of clobbering it on next save."""
        fresh = settings_mod.load()
        self.settings.clear()
        self.settings.update(fresh)
        for name, w in self.windows.items():
            w.cfg = settings_mod.group_cfg(self.settings, name)
            w.apply_settings()
        self.a_locked.setChecked(bool(self.settings.get("locked")))
        self.engine.reload(self.profiles, self._forced())
        self._settings_stamp = self._settings_mtime()

    # ---- main loop ----------------------------------------------------------------------------
    def tick(self):
        for line in self.source.poll():
            ev = parse_line(line)
            if ev:
                self.engine.feed(ev)
        now = self.source.now()
        items = self.engine.snapshot(now)
        keys = {it.key for it in items}
        for it in items:
            if it.sound and it.key not in self._seen_keys:
                play_sound(it.sound)
        self._seen_keys = keys
        by_group: dict[str, list] = {name: [] for name in self.windows}
        for it in items:
            g = it.group if it.group in self.windows else DEFAULT_GROUP.get(it.kind, "buffs")
            by_group.setdefault(g, []).append(it)
        base = self.enabled and (self.replay or not self.settings.get("show_only_in_game", True) or self.game_running)
        for name, win in self.windows.items():
            cfg = win.cfg
            want = base and not cfg.get("hidden") and (not cfg.get("combat_only") or self.engine.in_combat)
            win.set_wanted(want)
            items_for = by_group.get(name, [])
            if not cfg.get("show_companions", True):
                items_for = [i for i in items_for if not (i.kind == "party" and i.meta.get("kind") == "companion")]
            win.set_items(items_for, now)

    # ---- actions ------------------------------------------------------------------------------
    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_settings()

    def _toggle_enabled(self, checked):
        self.enabled = bool(checked)

    def _toggle_locked(self, checked):
        self.settings["locked"] = bool(checked)
        self.save_settings()
        for w in self.windows.values():
            w.apply_settings()
        self._status()

    def check_game(self):
        self.game_running = gamewatch.is_running(self.settings.get("game_exe", "swtor.exe"))
        self._status()

    def check_reload(self):
        if SIGNAL_FILE.exists():
            try:
                SIGNAL_FILE.unlink()
            except OSError:
                pass
            state = "showing over the game" if self.game_running else "waiting in the tray for SWTOR to start"
            self.tray.showMessage("SWTOR overlay", f"Already running — {state}.", QSystemTrayIcon.MessageIcon.Information)
            self.open_settings()
        stamp = self._profiles_mtime()
        if stamp != self._profiles_stamp:
            self._profiles_stamp = stamp
            self.reload_profiles()
        if self._settings_mtime() != self._settings_stamp:
            self._reload_settings_from_disk()

    def reload_profiles(self):
        try:
            self.profiles = Profile.load_all()
            global_rules = Profile.load_global()
        except Exception as e:  # a half-saved JSON must not kill the overlay
            self.tray.showMessage("SWTOR overlay", f"Profile reload failed: {e}", QSystemTrayIcon.MessageIcon.Warning)
            return
        self.engine.reload(self.profiles, self._forced(), global_rules)
        self._profiles_stamp = self._profiles_mtime()
        self._ensure_windows()
        self._status()

    def apply_settings(self):
        """Settings dict was edited by the config window."""
        self.save_settings()
        self.a_locked.setChecked(bool(self.settings.get("locked")))
        for w in self.windows.values():
            w.apply_settings()
        try:
            gamewatch.set_startup(bool(self.settings.get("start_with_windows")))
        except Exception as e:
            self.tray.showMessage("SWTOR overlay", f"Could not update Startup shortcut: {e}",
                                  QSystemTrayIcon.MessageIcon.Warning)
        self.engine.reload(self.profiles, self._forced())
        self.check_game()

    def preview_rule(self, rule: dict):
        """Show a fake item for this rule for a few seconds (config window 'Test' button)."""
        try:
            r = Rule.from_dict(rule)
        except TypeError as e:
            self.tray.showMessage("SWTOR overlay", f"Can't preview: {e}", QSystemTrayIcon.MessageIcon.Warning)
            return
        if r.group_name not in self.windows:
            self.add_group(r.group_name)
        self.engine.preview(r, self.source.now())
        if r.sound:
            play_sound(r.sound)

    def reset_positions(self):
        for name, w in self.windows.items():
            w.reset_position(settings_mod.DEFAULT_GROUP_LAYOUT.get(name, [400, 200, 300, 140]))

    def open_quick_add(self):
        from quick_add import QuickAddDialog
        self.quick = QuickAddDialog(self)   # fresh each time so the candidate list matches the current profile
        self.quick.show()
        self.quick.raise_()
        self.quick.activateWindow()

    def open_settings(self):
        from config_window import ConfigWindow
        if self.config is None:
            self.config = ConfigWindow(self)
        self.config.refresh()
        self.config.show()
        self.config.raise_()
        self.config.activateWindow()
