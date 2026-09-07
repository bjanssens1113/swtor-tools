"""Transparent always-on-top PyQt6 overlay that draws Engine items.

Tray icon menu: Lock (click-through) / Unlock (drag to move) / Reset position / Quit.
Window geometry and lock state persist in overlay/settings.json. Draws only; never sends input.
"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QAction, QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from parser import parse_line
from rules import Engine, Item

SETTINGS = Path(__file__).resolve().parent / "settings.json"
DEFAULT_GEOMETRY = (60, 200, 340, 420)  # x, y, w, h
COLORS = {
    "bar": QColor(70, 160, 255), "target": QColor(120, 220, 90), "cooldown": QColor(160, 160, 160),
    "warn": QColor(255, 70, 60), "flash": QColor(255, 210, 40), "stacks": QColor(255, 255, 255),
    "fight": QColor(220, 220, 220),
}


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_settings(d: dict):
    SETTINGS.write_text(json.dumps(d, indent=1), encoding="utf-8")


class OverlayWindow(QWidget):
    def __init__(self, engine: Engine, source, tick_ms: int = 50):
        super().__init__()
        self.engine, self.source = engine, source
        self.items: list[Item] = []
        self.settings = _load_settings()
        self.locked = bool(self.settings.get("locked", False))
        self._drag = None
        self.setWindowTitle("SWTOR overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        x, y, w, h = self.settings.get("geometry", DEFAULT_GEOMETRY)
        self.setGeometry(x, y, w, h)
        self._apply_flags()
        self._build_tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(tick_ms)

    # ---- window plumbing ----------------------------------------------------------------------
    def _apply_flags(self):
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        if self.locked:
            flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.show()

    def _build_tray(self):
        pm = QPixmap(32, 32)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setBrush(QBrush(COLORS["bar"]))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(2, 2, 28, 28, 6, 6)
        p.end()
        self.tray = QSystemTrayIcon(QIcon(pm), self)
        menu = QMenu()
        self.lock_action = QAction("", menu)
        self.lock_action.triggered.connect(self.toggle_lock)
        menu.addAction(self.lock_action)
        reset = QAction("Reset position", menu)
        reset.triggered.connect(self.reset_position)
        menu.addAction(reset)
        quit_ = QAction("Quit", menu)
        quit_.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_)
        self.tray.setContextMenu(menu)
        self._refresh_tray_text()
        self.tray.show()

    def _refresh_tray_text(self):
        self.lock_action.setText("Unlock (move overlay)" if self.locked else "Lock (click-through)")
        self.tray.setToolTip(f"SWTOR overlay — {'locked' if self.locked else 'UNLOCKED: drag to move'}")

    def toggle_lock(self):
        self.locked = not self.locked
        self.settings["locked"] = self.locked
        _save_settings(self.settings)
        self._refresh_tray_text()
        self._apply_flags()
        self.update()

    def reset_position(self):
        self.setGeometry(*DEFAULT_GEOMETRY)
        self._save_geometry()

    def _save_geometry(self):
        g = self.geometry()
        self.settings["geometry"] = [g.x(), g.y(), g.width(), g.height()]
        _save_settings(self.settings)

    def mousePressEvent(self, e):
        if not self.locked and e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        if self._drag is not None:
            self._drag = None
            self._save_geometry()

    # ---- data ---------------------------------------------------------------------------------
    def tick(self):
        for line in self.source.poll():
            ev = parse_line(line)
            if ev:
                self.engine.feed(ev)
        self.items = self.engine.snapshot(self.source.now())
        self.update()

    # ---- drawing ------------------------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        now = self.source.now()
        if not self.locked:
            p.setPen(QPen(COLORS["flash"], 2, Qt.PenStyle.DashLine))
            p.setBrush(QColor(0, 0, 0, 90))
            p.drawRoundedRect(1, 1, w - 2, self.height() - 2, 8, 8)
            p.setPen(COLORS["flash"])
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRectF(0, self.height() - 22, w, 20), Qt.AlignmentFlag.AlignCenter,
                       "UNLOCKED — drag to move, tray icon to lock")
        y = 6
        header = self.engine.profile.name if self.engine.profile else (self.engine.discipline or "waiting for log…")
        p.setPen(QColor(200, 200, 200, 200))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(6, y, w - 12, 14), Qt.AlignmentFlag.AlignLeft, header)
        y += 16
        flashes = [i for i in self.items if i.kind == "flash"]
        stacks = [i for i in self.items if i.kind == "stacks"]
        bars = [i for i in self.items if i.kind in ("bar", "cooldown")]
        fight = next((i for i in self.items if i.kind == "fight"), None)
        if fight:
            t = now - fight.start
            p.setPen(COLORS["fight"])
            p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            p.drawText(QRectF(6, y, w - 12, 22), Qt.AlignmentFlag.AlignLeft, f"{int(t // 60):02d}:{t % 60:04.1f}")
            y += 26
        if stacks:
            x = 6
            for it in stacks:
                warn = it.warn(now)
                box = QRectF(x, y, 64, 44)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 60, 50, 160) if warn else QColor(0, 0, 0, 130))
                p.drawRoundedRect(box, 6, 6)
                p.setPen(COLORS["stacks"])
                p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
                p.drawText(QRectF(x, y, 64, 28), Qt.AlignmentFlag.AlignCenter, str(it.stacks))
                p.setFont(QFont("Segoe UI", 7))
                p.drawText(QRectF(x, y + 27, 64, 14), Qt.AlignmentFlag.AlignCenter, it.label[:14])
                x += 70
            y += 50
        for it in flashes:
            p.setPen(QColor(it.color) if it.color else COLORS["flash"])
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Black))
            p.drawText(QRectF(6, y, w - 12, 30), Qt.AlignmentFlag.AlignCenter, it.label)
            y += 32
        for it in bars:
            rem, tot = it.remaining(now), it.total()
            warn = it.warn(now)
            base = COLORS["cooldown"] if it.kind == "cooldown" else (COLORS["target"] if it.target else COLORS["bar"])
            if it.color:
                base = QColor(it.color)
            col = COLORS["warn"] if warn else base
            rect = QRectF(6, y, w - 12, 18)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 130))
            p.drawRoundedRect(rect, 4, 4)
            frac = 1.0 if rem is None or not tot else rem / tot
            if it.kind == "cooldown":
                frac = 1.0 - frac
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 190))
            p.drawRoundedRect(QRectF(6, y, (w - 12) * max(0.0, min(1.0, frac)), 18), 4, 4)
            p.setPen(Qt.GlobalColor.white)
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            label = it.label + (f"  x{it.stacks}" if it.stacks else "")
            p.drawText(rect.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
            if rem is not None:
                p.drawText(rect.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                           f"{rem:.1f}")
            y += 21
        p.end()
