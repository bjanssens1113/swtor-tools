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
from rules import Item, item_stem

COLORS = {
    "bar": QColor(70, 160, 255), "target": QColor(120, 220, 90), "cooldown": QColor(110, 110, 110),
    "warn": QColor(255, 70, 60), "flash": QColor(255, 210, 40), "stacks": QColor(255, 255, 255),
    "fight": QColor(220, 220, 220), "ready": QColor(120, 255, 120),
}


def _base_color(it: Item) -> QColor:
    if it.color:
        return QColor(it.color)
    if it.kind in ("missing", "cleanse"):
        return COLORS["warn"]
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
        self._drag = None            # dragging the whole window
        self._drag_item = None       # free layout: (stem, offset) while dragging one element
        self._resize = None          # (start global pos, start size) while dragging the corner grip
        self._rects: list = []       # last laid-out (item, rect) pairs, logical units
        self.on_edit = None          # callback(name) when the window's edit button is clicked
        self.on_done = None          # callback() when the Done button is clicked
        self.setWindowTitle(f"SWTOR overlay — {name}")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(*self.cfg["geometry"])
        self._apply_flags()

    # ---- window plumbing ----------------------------------------------------------------------
    @property
    def locked(self) -> bool:
        """Locked = normal play mode: click-through, no frames. Unlocked = configure mode."""
        return not bool(self.settings.get("configure"))

    # configure-mode chrome (logical units)
    BTN = 16.0
    GRIP = 14.0

    def _chrome(self, W: float, H: float) -> dict:
        b = self.BTN
        return {
            "edit": QRectF(W - 2 * b - 8, 2, b, b),
            "done": QRectF(W - b - 4, 2, b, b),
            "grip": QRectF(W - self.GRIP, H - self.GRIP, self.GRIP, self.GRIP),
        }

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

    def _logical(self, e, pad: float = 4.0):
        s = float(self.cfg.get("scale") or 1.0)
        pos = e.position()
        top = pad + (16.0 if (pad and not self.locked) else 0.0)
        return (pos.x() / s - pad, pos.y() / s - top)

    def mousePressEvent(self, e):
        if self.locked or e.button() != Qt.MouseButton.LeftButton:
            return
        s = float(self.cfg.get("scale") or 1.0)
        W, H = self.width() / s, self.height() / s
        rx, ry = self._logical(e, 0.0)
        ch = self._chrome(W, H)
        if ch["done"].contains(rx, ry):
            if self.on_done:
                self.on_done()
            return
        if ch["edit"].contains(rx, ry):
            if self.on_edit:
                self.on_edit(self.name)
            return
        if ch["grip"].contains(rx, ry):
            self._resize = (e.globalPosition().toPoint(), (self.width(), self.height()))
            return
        if self.cfg.get("layout") == "free":
            lx, ly = self._logical(e)
            for it, r in reversed(self._rects):
                if r.contains(lx, ly):
                    self._drag_item = (item_stem(it.key), (lx - r.x(), ly - r.y()))
                    return
        self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._resize is not None:
            start, (w0, h0) = self._resize
            d = e.globalPosition().toPoint() - start
            self.resize(max(60, w0 + d.x()), max(30, h0 + d.y()))
        elif self._drag_item is not None:
            stem, (ox, oy) = self._drag_item
            lx, ly = self._logical(e)
            self.cfg.setdefault("positions", {})[stem] = [round(lx - ox), round(ly - oy)]
            self.update()
        elif self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)
        elif not self.locked:
            s = float(self.cfg.get("scale") or 1.0)
            rx, ry = self._logical(e, 0.0)
            ch = self._chrome(self.width() / s, self.height() / s)
            if ch["grip"].contains(rx, ry):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif ch["edit"].contains(rx, ry) or ch["done"].contains(rx, ry):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mouseReleaseEvent(self, e):
        if self._resize is not None:
            self._resize = None
            self._save_geometry()
        elif self._drag_item is not None:
            self._drag_item = None
            self.save()
        elif self._drag is not None:
            self._drag = None
            self._save_geometry()

    def mouseDoubleClickEvent(self, e):
        if not self.locked and self.on_edit:
            self.on_edit(self.name)

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
        if it.kind == "party":
            return W, 20.0
        if it.kind == "fight":
            return W, 24.0
        if it.kind == "stacks":
            return 64.0, 44.0
        if it.kind in ("flash", "missing", "cleanse"):
            return W, 30.0
        return W, 18.0

    def _layout(self, W: float, H: float, gap: float = 3.0):
        """Flow cells left-to-right, wrapping; rows grow down or up. 'right'/'left' = one row, no wrap,
        growing from the left or the right edge (icon-style groups). Free layout: elements with a saved
        position sit there; the rest flow from the top-left until dragged."""
        orient = self.cfg.get("orientation", "down")
        if self.cfg.get("layout") == "free":
            positions = self.cfg.get("positions", {})
            placed, rest = [], []
            for it in self.items:
                pos = positions.get(item_stem(it.key))
                if pos:
                    cw, ch = self._cell_size(it, W)
                    placed.append((it, QRectF(pos[0], pos[1], cw, ch)))
                else:
                    rest.append(it)
            saved, self.items = self.items, rest
            try:
                flowed = self._layout_flow(W, H, gap, orient)
            finally:
                self.items = saved
            return placed + flowed
        return self._layout_flow(W, H, gap, orient)

    def _layout_flow(self, W: float, H: float, gap: float, orient: str):
        cells = [(it, self._cell_size(it, W)) for it in self.items]
        rows, row, x, rowh = [], [], 0.0, 0.0
        wrap = orient in ("down", "up")
        for it, (cw, ch) in cells:
            if wrap and row and x + cw > W + 0.01:
                rows.append((row, rowh))
                row, x, rowh = [], 0.0, 0.0
            row.append((it, x, cw, ch))
            x += cw + gap
            rowh = max(rowh, ch)
        if row:
            rows.append((row, rowh))
        out = []
        if orient == "up":
            y = H
            for row, rowh in rows:
                y -= rowh
                out += [(it, QRectF(x, y, cw, ch)) for it, x, cw, ch in row]
                y -= gap
        elif orient == "left":
            for row, rowh in rows:
                out += [(it, QRectF(W - x - cw, 0.0, cw, ch)) for it, x, cw, ch in row]
        else:
            y = 0.0
            for row, rowh in rows:
                out += [(it, QRectF(x, y, cw, ch)) for it, x, cw, ch in row]
                y += rowh + gap
        return out

    def _label(self, it: Item) -> str:
        """Substitute the dynamic tokens: %r remaining seconds, %s stacks."""
        lbl = it.label
        if "%" in lbl:
            lbl = lbl.replace("%r", self._fmt_rem(it)).replace("%s", str(it.stacks))
        return lbl

    # ---- drawing ------------------------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = float(self.cfg.get("scale") or 1.0)
        p.scale(s, s)
        W, H = self.width() / s, self.height() / s
        pad = 4.0
        if not self.locked:
            self._draw_chrome(p, W, H)
        style = self.cfg.get("style", "bars")
        p.translate(pad, pad)
        if not self.locked:
            p.translate(0, 16)   # leave the title row free
        self._rects = self._layout(W - 2 * pad, H - 2 * pad - (32 if not self.locked else 0))
        if not self.locked and self.cfg.get("layout") == "free":
            p.setPen(QPen(QColor(255, 210, 40, 120), 1, Qt.PenStyle.DotLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for _, r in self._rects:
                p.drawRect(r)
        for it, r in self._rects:
            if it.kind == "party":
                self._draw_party_row(p, it, r)
            elif style == "icons":
                self._draw_tile(p, it, r)
            elif style == "text":
                self._draw_text(p, it, r)
            else:
                self._draw_bar_cell(p, it, r)
        p.end()

    def _draw_party_row(self, p: QPainter, it: Item, r: QRectF):
        m = it.meta
        pct = max(0.0, min(1.0, m.get("pct", 1.0)))
        low = pct * 100 < float(self.cfg.get("low_hp", 35))
        dead = m.get("dead")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 140))
        p.drawRoundedRect(r, 4, 4)
        if dead:
            col = QColor(90, 90, 90)
        elif low:
            col = COLORS["warn"] if int(self.now * 3) % 2 == 0 else QColor(200, 40, 40)   # blink
        elif pct < 0.7:
            col = QColor(230, 180, 40)
        else:
            col = QColor(60, 190, 80)
        p.setBrush(QColor(col.red(), col.green(), col.blue(), 200))
        p.drawRoundedRect(QRectF(r.x(), r.y(), r.width() * pct, r.height()), 4, 4)
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if m.get("me") else QFont.Weight.Normal))
        name = it.label if m.get("kind") != "companion" else f"{it.label} (comp)"
        self._outlined(p, r.adjusted(5, 0, -5, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       name[:18])
        right = "DEAD" if dead else f"{int(pct * 100)}%"
        self._outlined(p, r.adjusted(5, 0, -5, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, right)
        # my HoTs / shields on this member: small icons (or dots) left of the percent
        x = r.right() - 44
        for label, stacks, rem, icon in m.get("effects", [])[:4]:
            pm = icons.pixmap(icon) if icon else None
            box = QRectF(x - 16, r.y() + 2, 16, 16)
            if pm is not None:
                p.drawPixmap(box.toRect(), pm)
            else:
                p.setBrush(COLORS["target"])
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(box.adjusted(3, 3, -3, -3))
            if stacks:
                p.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                self._outlined(p, box, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, str(stacks))
            x -= 18

    def _draw_chrome(self, p: QPainter, W: float, H: float):
        """Configure-mode frame: dashed border, name, [edit] and [done] buttons, corner resize grip."""
        p.setPen(QPen(COLORS["flash"], 1.5, Qt.PenStyle.DashLine))
        p.setBrush(QColor(0, 0, 0, 80))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 6, 6)
        p.setPen(COLORS["flash"])
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.drawText(QRectF(6, 2, W - 50, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.name)
        ch = self._chrome(W, H)
        for key, glyph, col in (("edit", "✎", QColor(255, 210, 40)), ("done", "✓", QColor(120, 255, 120))):
            r = ch[key]
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 200))
            p.drawRoundedRect(r, 3, 3)
            p.setPen(col)
            p.setFont(QFont("Segoe UI Symbol", 9, QFont.Weight.Bold))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, glyph)
        g = ch["grip"]
        p.setPen(QPen(COLORS["flash"], 1.5))
        for i in (3, 7, 11):
            p.drawLine(int(g.right() - i), int(g.bottom() - 1), int(g.right() - 1), int(g.bottom() - i))
        p.setPen(QColor(255, 210, 40, 160))
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(QRectF(6, H - 15, W - 24, 12), Qt.AlignmentFlag.AlignLeft, "drag to move · ✎ edit · ✓ done")

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
        if it.kind in ("flash", "missing", "cleanse"):
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
        label = self._label(it)
        if it.stacks and "%s" not in it.label:
            label += f"  {it.stacks}/{it.meta['max']}" if it.meta.get("max", 1) > 1 else f"  x{it.stacks}"
        p.drawText(r.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
        if rem is not None:
            p.drawText(r.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       f"{rem:.1f}")

    def _draw_text(self, p: QPainter, it: Item, r: QRectF):
        if it.kind == "fight":
            return self._draw_bar_cell(p, it, r)
        col = COLORS["warn"] if it.warn(self.now) else _base_color(it)
        if it.kind in ("missing", "cleanse"):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(120, 0, 0, 150))
            p.drawRoundedRect(r, 6, 6)
        p.setPen(col)
        p.setFont(QFont("Segoe UI", 18 if it.kind != "cleanse" else 13, QFont.Weight.Black))
        txt = self._label(it)
        if "%" not in it.label:
            if it.kind == "stacks":
                txt = f"{txt} x{it.stacks}"
            elif it.kind in ("bar", "cooldown"):
                txt = f"{txt} {self._fmt_rem(it)}"
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
            if it.kind in ("missing", "cleanse"):
                p.fillRect(r, QColor(160, 0, 0, 130))
            if it.kind in ("flash", "missing", "cleanse"):
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
            f"{int(self.now - it.start)}" if it.kind == "fight" else (
                "✕" if it.kind == "missing" else ("!" if it.kind == "cleanse" else self._fmt_rem(it))))
        p.setFont(QFont("Segoe UI", int(r.height() * 0.36), QFont.Weight.Bold))
        self._outlined(p, QRectF(r.x(), r.y(), r.width(), r.height() * (0.7 if pm is None else 1.0)),
                       Qt.AlignmentFlag.AlignCenter, big)
        if pm is None or it.kind in ("missing", "cleanse"):
            p.setFont(QFont("Segoe UI", max(6, int(r.height() * 0.15))))
            self._outlined(p, QRectF(r.x() + 2, r.y() + r.height() * 0.66, r.width() - 4, r.height() * 0.32),
                           Qt.AlignmentFlag.AlignCenter, self._label(it).split(" · ")[0][:12])
        if it.kind in ("bar", "cooldown") and (it.stacks or it.meta.get("max", 1) > 1):
            p.setFont(QFont("Segoe UI", max(6, int(r.height() * 0.22)), QFont.Weight.Bold))
            txt = f"{it.stacks}/{it.meta['max']}" if it.meta.get("max", 1) > 1 else str(it.stacks)
            self._outlined(p, r.adjusted(0, 1, -3, 0), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, txt)
