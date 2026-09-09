"""Tray application: owns the engine, the log source and the overlay window.

- Shows the overlay only while swtor.exe is running (configurable).
- Hot-reloads profiles when any profiles/*.json changes.
- Tray menu: enable, lock, settings, reload, open profiles folder, quit.
Reads the log file and the Windows process list. Never touches the game.
"""
from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

import gamewatch
import settings as settings_mod
from overlay import OverlayWindow
from rules import PROFILE_DIR, Engine, Profile


def _icon(color=QColor(70, 160, 255)) -> QIcon:
    pm = QPixmap(32, 32)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setBrush(QBrush(color))
    p.setPen(QColor(0, 0, 0, 0))
    p.drawRoundedRect(2, 2, 28, 28, 6, 6)
    p.end()
    return QIcon(pm)


class TrayApp(QObject):
    def __init__(self, qapp: QApplication, source, replay: bool = False, open_settings: bool = False):
        super().__init__()
        self.qapp = qapp
        self.replay = replay
        self.settings = settings_mod.load()
        self.profiles = Profile.load_all()
        self.engine = Engine(self.profiles)
        self.engine.reload(self.profiles, self._forced())
        self.source = source
        self.win = OverlayWindow(self.engine, self.source, self.settings)
        self.enabled = True
        self._profiles_stamp = self._profiles_mtime()
        self.config = None

        self.tray = QSystemTrayIcon(_icon(), self)
        menu = QMenu()
        self.a_enabled = QAction("Overlay enabled", menu, checkable=True, checked=True)
        self.a_enabled.triggered.connect(self._toggle_enabled)
        self.a_locked = QAction("Lock overlay (click-through)", menu, checkable=True, checked=self.win.locked)
        self.a_locked.triggered.connect(self._toggle_locked)
        a_settings = QAction("Settings…", menu)
        a_settings.triggered.connect(self.open_settings)
        a_reload = QAction("Reload profiles", menu)
        a_reload.triggered.connect(self.reload_profiles)
        a_folder = QAction("Open profiles folder", menu)
        a_folder.triggered.connect(lambda: os.startfile(PROFILE_DIR))
        a_reset = QAction("Reset overlay position", menu)
        a_reset.triggered.connect(self.win.reset_position)
        a_quit = QAction("Quit", menu)
        a_quit.triggered.connect(qapp.quit)
        for a in (self.a_enabled, self.a_locked, a_settings, a_reload, a_folder, a_reset):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(a_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        self.t_game = QTimer(self)
        self.t_game.timeout.connect(self.check_game)
        self.t_game.start(3000)
        self.t_reload = QTimer(self)
        self.t_reload.timeout.connect(self.check_reload)
        self.t_reload.start(1000)
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
        state = "locked" if self.win.locked else "UNLOCKED"
        self.tray.setToolTip(f"SWTOR overlay — {prof} — {state}")

    # ---- actions ------------------------------------------------------------------------------
    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_settings()

    def _toggle_enabled(self, checked):
        self.enabled = bool(checked)
        self.check_game()

    def _toggle_locked(self, checked):
        self.win.set_locked(bool(checked))
        self._status()

    def check_game(self):
        want = self.enabled and (self.replay or not self.settings.get("show_only_in_game", True)
                                 or gamewatch.is_running(self.settings.get("game_exe", "swtor.exe")))
        if want != self.win.isVisible():
            self.win.setVisible(want)
        self._status()

    def check_reload(self):
        stamp = self._profiles_mtime()
        if stamp != self._profiles_stamp:
            self._profiles_stamp = stamp
            self.reload_profiles()

    def reload_profiles(self):
        try:
            self.profiles = Profile.load_all()
        except Exception as e:  # a half-saved JSON must not kill the overlay
            self.tray.showMessage("SWTOR overlay", f"Profile reload failed: {e}", QSystemTrayIcon.MessageIcon.Warning)
            return
        self.engine.reload(self.profiles, self._forced())
        self._profiles_stamp = self._profiles_mtime()
        self._status()
        self.win.update()

    def apply_settings(self):
        """Settings dict was edited by the config window and saved."""
        settings_mod.save(self.settings)
        self.win.apply_settings()
        self.a_locked.setChecked(self.win.locked)
        try:
            gamewatch.set_startup(bool(self.settings.get("start_with_windows")))
        except Exception as e:
            self.tray.showMessage("SWTOR overlay", f"Could not update Startup shortcut: {e}",
                                  QSystemTrayIcon.MessageIcon.Warning)
        self.engine.reload(self.profiles, self._forced())
        self.check_game()

    def open_settings(self):
        from config_window import ConfigWindow
        if self.config is None:
            self.config = ConfigWindow(self)
        self.config.refresh()
        self.config.show()
        self.config.raise_()
        self.config.activateWindow()
