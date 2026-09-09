"""GroupWindow: one transparent always-on-top window per layout group (WeakAuras-style group).

Each group has its own position, grow direction (down / up), scale and display style:
  bars  - stack boxes, flash text and progress bars (the classic look)
  icons - square tiles with a big countdown / stack number and a small label, wrapping at `columns`
  text  - one big text line per item (for alert groups)
Draws only; never sends input. app.py feeds it items every tick.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

import icons
from rules import Item

COLORS = {
    "bar": QColor(70, 160, 255), "target": QColor(120, 220, 90), "cooldown": QColor(110, 110, 110),
    "warn": QColor(255, 70, 60), "flash": QColor(255, 210, 40), "stacks": QColor(255, 255, 255),
    "fight": QColor(220, 220, 220), "ready": QColor(120, 255, 120),
}


def _base_color(it: Item) -> QColor:
    if it.color:
        return QColor(it.color)
    if it.kind == "cooldown":
        return COLORS["cooldown"]
    if it.kind == "flash":
        return COLORS["ready"] if it.label.endswith("READY") else COLORS["flash"]
    if it.target:
        return COLORS["target"]
    return COLORS["bar"]


class GroupWindow(QWidget):
    def __init__(self, name: str, cfg: dict, settings: dict, save_cb):
        super().__init__()
        self.name, self.cfg, self.settings, self.save = name, cfg, settings, save_cb
        self.items: list[Item] = []
        self.now = 0.0
        self.wanted = False          # app-level: game running, enabled, combat rule...
        self._drag = None
        self.setWindowTitle(f"SWTOR overlay — {name}")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(*self.cfg["geometry"])
        self._apply_flags()

    # ---- window plumbing ----------------------------------------------------------------------
    @property
    def locked(self) -> bool:
        return bool(self.settings.get("locked"))

    def _apply_flags(self):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        if self.locked:
            flags |= Qt.WindowType.WindowTransparentForInput
        was = self.isVisible()
        self.setWindowFlags(flags)
        if was:
            self.show()

    def apply_settings(self):
        """Re-read cfg (style/scale/geometry) and lock state."""
        g = self.cfg["geometry"]
        if [self.x(), self.y(), self.width(), self.height()] != g:
            self.setGeometry(*g)
        self._apply_flags()
        self.update()

    def set_wanted(self, wanted: bool):
        self.wanted = wanted
        if wanted != self.isVisible():
            self.setVisible(wanted)

    def reset_position(self, geometry: list):
        self.cfg["geometry"] = list(geometry)
        self.setGeometry(*geometry)
        self.save()

    def _save_geometry(self):
        g = self.geometry()
        self.cfg["geometry"] = [g.x(), g.y(), g.width(), g.height()]
        self.save()

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

    def set_items(self, items: list[Item], now: float):
        self.items, self.now = items, now
        if self.isVisible():
            self.update()

    # ---- layout ---------------------------------------------------------------------------------
    def _cell_size(self, it: Item, W: float) -> tuple[float, float]:
        style = self.cfg.get("style", "bars")
        if style == "icons":
            s = float(self.cfg.get("icon_size", 48))
            return s, s
        if style == "text":
            return W, 30.0
        if it.kind == "fight":
            return W, 24.0
        if it.kind == "stacks":
            return 64.0, 44.0
        if it.kind == "flash":
            return W, 30.0
        return W, 18.0

    def _layout(self, W: float, H: float, gap: float = 3.0):
        """Flow cells left-to-right, wrapping; rows grow down or up."""
        cells = [(it, self._cell_size(it, W)) for it in self.items]
        rows, row, x, rowh = [], [], 0.0, 0.0
        for it, (cw, ch) in cells:
            if row and x + cw > W + 0.01:
                rows.append((row, rowh))
                row, x, rowh = [], 0.0, 0.0
            row.append((it, x, cw, ch))
            x += cw + gap
            rowh = max(rowh, ch)
        if row:
            rows.append((row, rowh))
        out = []
        if self.cfg.get("orientation") == "up":
            y = H
            for row, rowh in rows:
                y -= rowh
                out += [(it, QRectF(x, y, cw, ch)) for it, x, cw, ch in row]
                y -= gap
        else:
            y = 0.0
            for row, rowh in rows:
                out += [(it, QRectF(x, y, cw, ch)) for it, x, cw, ch in row]
                y += rowh + gap
        return out

    # ---- drawing ------------------------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = float(self.cfg.get("scale") or 1.0)
        p.scale(s, s)
        W, H = self.width() / s, self.height() / s
        pad = 4.0
        if not self.locked:
            p.setPen(QPen(COLORS["flash"], 1.5, Qt.PenStyle.DashLine))
            p.setBrush(QColor(0, 0, 0, 80))
            p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 6, 6)
            p.setPen(COLORS["flash"])
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(QRectF(pad, H - 16, W - 2 * pad, 14), Qt.AlignmentFlag.AlignRight, self.name)
        style = self.cfg.get("style", "bars")
        p.translate(pad, pad)
        for it, r in self._layout(W - 2 * pad, H - 2 * pad - (16 if not self.locked else 0)):
            if style == "icons":
                self._draw_tile(p, it, r)
            elif style == "text":
                self._draw_text(p, it, r)
            else:
                self._draw_bar_cell(p, it, r)
        p.end()

    def _fmt_rem(self, it: Item) -> str:
        rem = it.remaining(self.now)
        if rem is None:
            return ""
        return f"{rem:.1f}" if rem < 10 else f"{int(rem)}"

    def _draw_bar_cell(self, p: QPainter, it: Item, r: QRectF):
        warn = it.warn(self.now)
        if it.kind == "fight":
            t = self.now - it.start
            p.setPen(COLORS["fight"])
            p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            p.drawText(r, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       f"{int(t // 60):02d}:{t % 60:04.1f}")
            return
        if it.kind == "stacks":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 60, 50, 160) if warn else QColor(0, 0, 0, 130))
            p.drawRoundedRect(r, 6, 6)
            p.setPen(COLORS["stacks"])
            p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            p.drawText(QRectF(r.x(), r.y(), r.width(), 28), Qt.AlignmentFlag.AlignCenter, str(it.stacks))
            p.setFont(QFont("Segoe UI", 7))
            p.drawText(QRectF(r.x(), r.y() + 27, r.width(), 14), Qt.AlignmentFlag.AlignCenter, it.label[:14])
            return
        if it.kind == "flash":
            self._draw_text(p, it, r)
            return
        rem, tot = it.remaining(self.now), it.total()
        col = COLORS["warn"] if warn else _base_color(it)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 130))
        p.drawRoundedRect(r, 4, 4)
        frac = 1.0 if rem is None or not tot else rem / tot
        if it.kind == "cooldown":
            frac = 1.0 - frac
        p.setBrush(QColor(col.red(), col.green(), col.blue(), 190))
        p.drawRoundedRect(QRectF(r.x(), r.y(), r.width() * max(0.0, min(1.0, frac)), r.height()), 4, 4)
        p.setPen(Qt.GlobalColor.white)
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        label = it.label + (f"  x{it.stacks}" if it.stacks else "")
        p.drawText(r.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
        if rem is not None:
            p.drawText(r.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       f"{rem:.1f}")

    def _draw_text(self, p: QPainter, it: Item, r: QRectF):
        if it.kind == "fight":
            return self._draw_bar_cell(p, it, r)
        col = COLORS["warn"] if it.warn(self.now) else _base_color(it)
        p.setPen(col)
        p.setFont(QFont("Segoe UI", 18, QFont.Weight.Black))
        txt = it.label
        if it.kind == "stacks":
            txt = f"{it.label} x{it.stacks}"
        elif it.kind in ("bar", "cooldown"):
            txt = f"{it.label} {self._fmt_rem(it)}"
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, txt)

    def _outlined(self, p: QPainter, rect: QRectF, flags, text: str, color=Qt.GlobalColor.white):
        """Text with a dark outline so it reads on top of any icon."""
        p.setPen(QColor(0, 0, 0, 220))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            p.drawText(rect.translated(dx, dy), flags, text)
        p.setPen(color)
        p.drawText(rect, flags, text)

    def _draw_tile(self, p: QPainter, it: Item, r: QRectF):
        warn = it.warn(self.now)
        col = _base_color(it)
        pm = icons.pixmap(it.icon) if it.icon else None
        rem, tot = it.remaining(self.now), it.total()
        p.setPen(Qt.PenStyle.NoPen)
        if pm is not None:
            path = QPainterPath()
            path.addRoundedRect(r, 6, 6)
            p.save()
            p.setClipPath(path)
            p.drawPixmap(r.toRect(), pm)
            if it.kind == "cooldown":
                # dark cover shrinks from the top as the cooldown runs down
                frac = 0.0 if rem is None or not tot else rem / tot
                p.fillRect(QRectF(r.x(), r.y() + r.height() * (1 - frac), r.width(), r.height() * frac),
                           QColor(0, 0, 0, 165))
            elif it.kind == "bar" and it.end is not None:
                frac = 0.0 if not tot else 1.0 - rem / tot
                p.fillRect(QRectF(r.x(), r.y(), r.width(), r.height() * frac), QColor(0, 0, 0, 120))
            p.restore()
            if it.kind == "flash":
                p.setPen(QPen(col, 3))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(r.adjusted(1.5, 1.5, -1.5, -1.5), 6, 6)
        elif it.kind == "cooldown":
            p.setBrush(QColor(0, 0, 0, 170))
            p.drawRoundedRect(r, 6, 6)
            frac = 0.0 if rem is None or not tot else rem / tot
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 90))
            p.drawRoundedRect(QRectF(r.x(), r.y() + r.height() * (1 - frac), r.width(), r.height() * frac), 6, 6)
        elif it.kind == "fight":
            p.setBrush(QColor(0, 0, 0, 150))
            p.drawRoundedRect(r, 6, 6)
        else:
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 200 if not warn else 120))
            p.drawRoundedRect(r, 6, 6)
            if it.kind == "bar" and it.end is not None:
                frac = 0.0 if not tot else 1.0 - rem / tot
                p.setBrush(QColor(0, 0, 0, 120))
                p.drawRoundedRect(QRectF(r.x(), r.y(), r.width(), r.height() * frac), 6, 6)
        if warn:
            p.setPen(QPen(COLORS["warn"], 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(1.5, 1.5, -1.5, -1.5), 6, 6)
        big = str(it.stacks) if it.kind == "stacks" else (
            f"{int(self.now - it.start)}" if it.kind == "fight" else self._fmt_rem(it))
        p.setFont(QFont("Segoe UI", int(r.height() * 0.36), QFont.Weight.Bold))
        self._outlined(p, QRectF(r.x(), r.y(), r.width(), r.height() * (0.7 if pm is None else 1.0)),
                       Qt.AlignmentFlag.AlignCenter, big)
        if pm is None:
            p.setFont(QFont("Segoe UI", max(6, int(r.height() * 0.15))))
            self._outlined(p, QRectF(r.x() + 2, r.y() + r.height() * 0.66, r.width() - 4, r.height() * 0.32),
                           Qt.AlignmentFlag.AlignCenter, it.label.split(" · ")[0][:12])
        if it.kind == "bar" and it.stacks:
            p.setFont(QFont("Segoe UI", max(6, int(r.height() * 0.22)), QFont.Weight.Bold))
            self._outlined(p, r.adjusted(0, 1, -3, 0), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
                           str(it.stacks))
