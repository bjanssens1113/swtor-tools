"""Configuration window: profile rules, layout groups and launch settings. Opened from the tray icon.

Rules tab edits the raw JSON of a profile file. Saving an auto/mirrored profile writes a hand-written copy into
overlay/profiles/ (which then takes priority). The Add-rule picker is fed by overlay/data/disciplines.json so
effect and ability names are the exact strings the log uses.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                             QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton,
                             QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

import settings as settings_mod
from rules import PROFILE_DIR, RULE_TYPES

ROOT = Path(__file__).resolve().parents[1]
DISC_DATA = ROOT / "overlay" / "data" / "disciplines.json"
COLS = ["On", "Type", "Effect / ability", "Duration s", "Cooldown s", "Warn at", "Conditions", "Label", "Group",
        "Sound", "Icon", "Color"]
C_ON, C_TYPE, C_NAME, C_DUR, C_CD, C_WARN, C_COND, C_LABEL, C_GROUP, C_SOUND, C_ICON, C_COLOR = range(12)
COND_HELP = ("Conditions: combat | nocombat | stacks<N | stacks>=N | boss | regex  (space separated). "
             "Type 'missing' = alert when the buff is NOT on you (in combat by default; 'nocombat' flips it).")


def format_cond(r: dict) -> str:
    parts = []
    if r.get("in_combat") is True:
        parts.append("combat")
    elif r.get("in_combat") is False:
        parts.append("nocombat")
    if r.get("stacks_below", -1) >= 0:
        parts.append(f"stacks<{r['stacks_below']}")
    if r.get("stacks_at_least", -1) >= 0:
        parts.append(f"stacks>={r['stacks_at_least']}")
    if r.get("boss_only"):
        parts.append("boss")
    if r.get("regex"):
        parts.append("regex")
    return " ".join(parts)


def parse_cond(text: str, r: dict) -> None:
    """Apply a conditions string to a rule dict (clears any it doesn't mention)."""
    for k in ("in_combat", "stacks_below", "stacks_at_least", "boss_only", "regex"):
        r.pop(k, None)
    for tok in text.replace(",", " ").split():
        t = tok.lower()
        if t == "combat":
            r["in_combat"] = True
        elif t in ("nocombat", "ooc"):
            r["in_combat"] = False
        elif t == "boss":
            r["boss_only"] = True
        elif t == "regex":
            r["regex"] = True
        elif t.startswith("stacks<"):
            r["stacks_below"] = int(t[7:])
        elif t.startswith("stacks>="):
            r["stacks_at_least"] = int(t[8:])
STYLES = ["bars", "icons", "text"]
ORIENTATIONS = ["down", "up"]
SOUNDS = ["", "beep"]


def _load_disc_data() -> dict:
    try:
        return json.loads(DISC_DATA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class AddRuleDialog(QDialog):
    def __init__(self, parent, cls: str, disc: str, groups: list[str]):
        super().__init__(parent)
        self.setWindowTitle("Add rule")
        self.data = _load_disc_data().get(f"{cls}/{disc}", {})
        self.type = QComboBox()
        self.type.addItems(RULE_TYPES)
        self.name = QComboBox()
        self.name.setEditable(True)
        self.seconds = QDoubleSpinBox()
        self.seconds.setRange(0, 900)
        self.seconds.setDecimals(1)
        self.group = QComboBox()
        self.group.addItems([""] + groups)
        self.sound = QComboBox()
        self.sound.setEditable(True)
        self.sound.addItems(SOUNDS)
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        form = QFormLayout(self)
        form.addRow("Type", self.type)
        form.addRow("Name", self.name)
        form.addRow("Duration / cooldown (s)", self.seconds)
        form.addRow("Group (blank = default for type)", self.group)
        form.addRow("Sound (blank, beep, or .wav path)", self.sound)
        form.addRow(self.hint)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)
        self.type.currentTextChanged.connect(self._fill)
        self.name.currentIndexChanged.connect(self._suggest)
        self._fill()

    def _candidates(self):
        t = self.type.currentText()
        if t == "cooldown":
            return [(a["name"], a.get("p10_gap"), f"{a['uses']} uses, re-use gap p10 {a.get('p10_gap')} s")
                    for a in self.data.get("abilities", [])]
        if t == "target":
            return [(x["name"], x.get("p75_s"), f"{x['count']} seen, lasts ~{x.get('p75_s')} s")
                    for x in self.data.get("target_effects", [])]
        if t == "stacks":
            return [(x["name"], None, f"{x['count']} seen, max {x.get('max_seen')} stacks")
                    for x in self.data.get("stacks", [])]
        if t == "missing":
            return [(x["name"], None, f"{x['count']} seen; alert shows in combat while this is NOT on you")
                    for x in self.data.get("self_buffs", [])]
        if t == "cleanse":
            return [("Physical Tech", None, "tech healers (Operative/Scoundrel, Mercenary/Commando): Toxin Scan / Cure"),
                    ("Mental Force", None, "force healers (Sorcerer/Sage): Expunge / Restoration"),
                    ("Physical Tech Mental Force", None, "everything with a category tag")]
        return [(x["name"], x.get("median_s"), f"{x['count']} seen, lasts ~{x.get('median_s')} s")
                for x in self.data.get("self_buffs", [])]

    def _fill(self):
        self.name.clear()
        self._cands = self._candidates()
        for n, _, _ in self._cands:
            self.name.addItem(n)
        self.hint.setText("Names come from your logs for this discipline. Type any exact log name if it is missing."
                          if self._cands else "No log data for this discipline yet; type the exact effect or ability name.")
        self._suggest()

    def _suggest(self):
        i = self.name.currentIndex()
        if 0 <= i < len(self._cands):
            _, val, note = self._cands[i]
            self.seconds.setValue(float(val or 0))
            self.hint.setText(note)

    def rule(self) -> dict:
        t = self.type.currentText()
        name = self.name.currentText().strip()
        r: dict = {"type": t}
        if t == "cooldown":
            r["ability"] = name
            r["seconds"] = self.seconds.value()
        elif t == "cleanse":
            r["types"] = name.split()
            r["effect"] = "cleanse"
            r["label"] = "CLEANSE"
        else:
            r["effect"] = name
            if t not in ("stacks", "missing") and self.seconds.value() > 0:
                r["duration"] = self.seconds.value()
            if t == "target":
                r["warn_at"] = 2
            if t == "missing":
                r["label"] = f"MISSING {name}"
                r["in_combat"] = True
        if self.group.currentText():
            r["group"] = self.group.currentText()
        if self.sound.currentText().strip():
            r["sound"] = self.sound.currentText().strip()
        return r


class ConfigWindow(QDialog):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("SWTOR overlay — settings")
        self.resize(900, 600)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.doc: dict = {}
        self.doc_path: Path | None = None
        tabs = QTabWidget()
        tabs.addTab(self._rules_tab(), "Rules")
        tabs.addTab(self._groups_tab(), "Groups")
        tabs.addTab(self._general_tab(), "General")
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        g = self.app.settings.get("config_geometry")
        if g and len(g) == 4:
            self.setGeometry(*g)

    def _remember_geometry(self):
        r = self.geometry()
        self.app.settings["config_geometry"] = [r.x(), r.y(), r.width(), r.height()]
        self.app.save_settings()

    def closeEvent(self, e):
        self._remember_geometry()
        super().closeEvent(e)

    def hideEvent(self, e):
        self._remember_geometry()
        super().hideEvent(e)

    # ---- rules tab ------------------------------------------------------------------------------
    def _rules_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Profile"))
        self.profile_box = QComboBox()
        self.profile_box.currentIndexChanged.connect(self._load_profile)
        top.addWidget(self.profile_box, 1)
        v.addLayout(top)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(C_NAME, 190)
        self.table.setColumnWidth(C_COND, 130)
        for c in (C_DUR, C_CD, C_WARN):
            self.table.setColumnWidth(c, 64)
        v.addWidget(self.table, 1)
        btns = QHBoxLayout()
        b_add, b_del, b_save = QPushButton("Add rule…"), QPushButton("Remove selected"), QPushButton("Save profile")
        b_add.clicked.connect(self._add_rule)
        b_del.clicked.connect(self._remove_rule)
        b_save.clicked.connect(self._save_profile)
        for b in (b_add, b_del):
            btns.addWidget(b)
        btns.addStretch(1)
        btns.addWidget(b_save)
        v.addLayout(btns)
        self.note = QLabel(COND_HELP + "  Group blank = default for the type. Sound: blank, 'beep', or a .wav path.")
        self.note.setWordWrap(True)
        v.addWidget(self.note)
        return w

    def refresh(self):
        self._refresh_general()
        self._refresh_groups()
        cur = self.profile_box.currentData()
        self.profile_box.blockSignals(True)
        self.profile_box.clear()
        for g in sorted(PROFILE_DIR.glob("_*.json")):
            self.profile_box.addItem(f"GLOBAL rules — every discipline   [{g.relative_to(ROOT)}]", str(g))
        for p in self.app.profiles:
            tag = "auto" if p.auto else "hand"
            self.profile_box.addItem(f"{p.name}   [{tag}: {p.path.relative_to(ROOT)}]", str(p.path))
        self.profile_box.blockSignals(False)
        active = self.app.engine.profile
        idx = self.profile_box.findData(str(active.path)) if active else -1
        if cur and self.profile_box.findData(cur) >= 0:
            idx = self.profile_box.findData(cur)
        self.profile_box.setCurrentIndex(max(idx, 0))
        self._load_profile()

    def _load_profile(self):
        path = self.profile_box.currentData()
        if not path:
            return
        self.doc_path = Path(path)
        self.doc = json.loads(self.doc_path.read_text(encoding="utf-8"))
        self.table.setRowCount(0)
        for r in self.doc.get("rules", []):
            self._append_row(r)
        prefix = ("This is a generated profile. Saving writes a hand-written copy into overlay/profiles/ "
                  "that takes priority.  ") if self.doc.get("_auto") else ""
        self.note.setText(prefix + str(self.doc.get("_source", ""))[:300])

    def _append_row(self, r: dict):
        row = self.table.rowCount()
        self.table.insertRow(row)
        on = QTableWidgetItem()
        on.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        on.setCheckState(Qt.CheckState.Checked if r.get("enabled", True) else Qt.CheckState.Unchecked)
        on.setData(Qt.ItemDataRole.UserRole, dict(r))
        self.table.setItem(row, 0, on)
        t = QTableWidgetItem(r.get("type", ""))
        t.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.table.setItem(row, 1, t)
        shown_name = " ".join(r.get("types", [])) if r.get("type") == "cleanse" else (r.get("effect") or r.get("ability") or "")
        vals = [shown_name, str(r.get("duration", "") or ""),
                str(r.get("seconds", "") or ""), str(r.get("warn_at", "") or ""), format_cond(r),
                r.get("label", ""), r.get("group", ""), r.get("sound", ""), r.get("icon", ""), r.get("color", "")]
        for i, v in enumerate(vals, start=C_NAME):
            self.table.setItem(row, i, QTableWidgetItem(v))
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems([""] + self.app.group_names())
        combo.setCurrentText(r.get("group", ""))
        self.table.setCellWidget(row, C_GROUP, combo)

    def _refresh_group_combos(self):
        names = [""] + self.app.group_names()
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, C_GROUP)
            if isinstance(combo, QComboBox):
                cur = combo.currentText()
                combo.clear()
                combo.addItems(names)
                combo.setCurrentText(cur)

    def _add_rule(self):
        m = self.doc.get("match", {})
        dlg = AddRuleDialog(self, m.get("class", ""), m.get("discipline", ""), self.app.group_names())
        if dlg.exec():
            self._append_row(dlg.rule())

    def _remove_rule(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)

    def _cell(self, row, col) -> str:
        widget = self.table.cellWidget(row, col)
        if isinstance(widget, QComboBox):
            return widget.currentText().strip()
        it = self.table.item(row, col)
        return it.text().strip() if it else ""

    def _rows_to_rules(self) -> list[dict]:
        def num(row, col):
            txt = self._cell(row, col)
            try:
                return float(txt) if txt else None
            except ValueError:
                return None
        out = []
        for row in range(self.table.rowCount()):
            r = dict(self.table.item(row, C_ON).data(Qt.ItemDataRole.UserRole) or {})
            r["type"] = self.table.item(row, C_TYPE).text()
            name = self._cell(row, C_NAME)
            if r["type"] == "cooldown":
                r["ability"] = name
                r.pop("effect", None)
            elif r["type"] == "cleanse":
                r["types"] = name.split()
                r["effect"] = "cleanse"
            else:
                r["effect"] = name
                r.pop("ability", None)
            for key, col in (("duration", C_DUR), ("seconds", C_CD), ("warn_at", C_WARN)):
                v = num(row, col)
                if v:
                    r[key] = v
                else:
                    r.pop(key, None)
            parse_cond(self._cell(row, C_COND), r)
            for key, col in (("label", C_LABEL), ("group", C_GROUP), ("sound", C_SOUND), ("icon", C_ICON),
                             ("color", C_COLOR)):
                v = self._cell(row, col)
                if v:
                    r[key] = v
                else:
                    r.pop(key, None)
            if self.table.item(row, C_ON).checkState() == Qt.CheckState.Checked:
                r.pop("enabled", None)
            else:
                r["enabled"] = False
            out.append(r)
        return out

    def _save_profile(self):
        if not self.doc_path:
            return
        doc = dict(self.doc)
        doc["rules"] = self._rows_to_rules()
        target = self.doc_path
        if doc.get("_auto"):
            m = doc["match"]
            doc["name"] = re.sub(r"\s*\((auto|mirrored)\)$", "", doc["name"])
            doc.pop("_auto", None)
            doc.pop("_kind", None)
            doc["_source"] = f"hand-edited copy of generated profile. {doc.get('_source', '')}"
            slug = f"{m['class']}_{m['discipline']}".lower().replace(" ", "_")
            target = PROFILE_DIR / f"{slug}.json"
            if target.exists():
                if QMessageBox.question(self, "Overwrite?", f"{target.name} already exists. Overwrite it?") \
                        != QMessageBox.StandardButton.Yes:
                    return
        try:
            target.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self.app.reload_profiles()
        self.refresh()
        idx = self.profile_box.findData(str(target))
        if idx >= 0:
            self.profile_box.setCurrentIndex(idx)
        self.note.setText(f"Saved {target.relative_to(ROOT)} and reloaded.")

    # ---- groups tab -----------------------------------------------------------------------------
    GCOLS = ["Group", "Style", "Grow", "Scale", "Icon px", "Columns", "Combat only", "Hidden", "Low HP %", "Companions"]

    def _groups_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel("Each group is its own movable window. Unlock (General tab or tray) to drag them. "
                           "Style: bars = classic, icons = square tiles with countdown, text = big alert lines. "
                           "Make your own group (e.g. 'defensives'), then put rules in it via the Group column on the Rules tab."))
        self.gtable = QTableWidget(0, len(self.GCOLS))
        self.gtable.setHorizontalHeaderLabels(self.GCOLS)
        self.gtable.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self.gtable, 1)
        row = QHBoxLayout()
        b_new = QPushButton("New group…")
        b_new.clicked.connect(self._new_group)
        b_del = QPushButton("Delete selected group")
        b_del.clicked.connect(self._delete_group)
        b_apply = QPushButton("Apply groups")
        b_apply.clicked.connect(self._apply_groups)
        b_reset = QPushButton("Reset positions")
        b_reset.clicked.connect(self.app.reset_positions)
        for b in (b_new, b_del, b_reset):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(b_apply)
        v.addLayout(row)
        return w

    def _new_group(self):
        name, ok = QInputDialog.getText(self, "New group", "Group name (letters, digits, - and _):")
        name = re.sub(r"[^A-Za-z0-9_\- ]", "", name or "").strip()
        if not ok or not name:
            return
        if not self.app.add_group(name):
            QMessageBox.information(self, "New group", f"A group called '{name}' already exists.")
            return
        self._refresh_groups()
        self._refresh_group_combos()
        self.note.setText(f"Group '{name}' created. Unlock to position it; assign rules to it on the Rules tab.")

    def _delete_group(self):
        rows = {i.row() for i in self.gtable.selectedIndexes()}
        if not rows:
            return
        name = self.gtable.item(min(rows), 0).text()
        if name in settings_mod.DEFAULT_GROUP_LAYOUT:
            QMessageBox.information(self, "Delete group", "Built-in groups can't be deleted. Tick Hidden instead.")
            return
        if QMessageBox.question(self, "Delete group", f"Delete group '{name}'? Rules in it fall back to their "
                                "default group.") != QMessageBox.StandardButton.Yes:
            return
        self.app.remove_group(name)
        self._refresh_groups()
        self._refresh_group_combos()

    def _refresh_groups(self):
        names = self.app.group_names()
        self.gtable.setRowCount(0)
        for name in names:
            cfg = settings_mod.group_cfg(self.app.settings, name)
            r = self.gtable.rowCount()
            self.gtable.insertRow(r)
            it = QTableWidgetItem(name)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.gtable.setItem(r, 0, it)
            style = QComboBox()
            style.addItems(STYLES)
            style.setCurrentText(cfg.get("style", "bars"))
            self.gtable.setCellWidget(r, 1, style)
            grow = QComboBox()
            grow.addItems(ORIENTATIONS)
            grow.setCurrentText(cfg.get("orientation", "down"))
            self.gtable.setCellWidget(r, 2, grow)
            self.gtable.setItem(r, 3, QTableWidgetItem(str(cfg.get("scale", 1.0))))
            self.gtable.setItem(r, 4, QTableWidgetItem(str(cfg.get("icon_size", 48))))
            self.gtable.setItem(r, 5, QTableWidgetItem(str(cfg.get("columns", 6))))
            for col, key in ((6, "combat_only"), (7, "hidden"), (9, "show_companions")):
                c = QTableWidgetItem()
                c.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                c.setCheckState(Qt.CheckState.Checked if cfg.get(key) else Qt.CheckState.Unchecked)
                self.gtable.setItem(r, col, c)
            self.gtable.setItem(r, 8, QTableWidgetItem(str(cfg.get("low_hp", 35))))

    def _apply_groups(self):
        for r in range(self.gtable.rowCount()):
            name = self.gtable.item(r, 0).text()
            cfg = settings_mod.group_cfg(self.app.settings, name)
            cfg["style"] = self.gtable.cellWidget(r, 1).currentText()
            cfg["orientation"] = self.gtable.cellWidget(r, 2).currentText()
            for col, key, cast, default in ((3, "scale", float, 1.0), (4, "icon_size", int, 48), (5, "columns", int, 6)):
                try:
                    cfg[key] = cast(self.gtable.item(r, col).text())
                except (ValueError, AttributeError):
                    cfg[key] = default
            cfg["combat_only"] = self.gtable.item(r, 6).checkState() == Qt.CheckState.Checked
            cfg["hidden"] = self.gtable.item(r, 7).checkState() == Qt.CheckState.Checked
            try:
                cfg["low_hp"] = float(self.gtable.item(r, 8).text())
            except (ValueError, AttributeError):
                cfg["low_hp"] = 35
            cfg["show_companions"] = self.gtable.item(r, 9).checkState() == Qt.CheckState.Checked
        self.app.apply_settings()
        self.note.setText("Groups applied.")

    # ---- general tab ----------------------------------------------------------------------------
    def _general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.c_game = QCheckBox("Show the overlay only while the game is running")
        self.c_start = QCheckBox("Start with Windows (shortcut in the Startup folder)")
        self.c_lock = QCheckBox("Locked (click-through). Unlock to drag groups around.")
        self.c_auto = QCheckBox("Follow discipline changes in the log")
        self.forced = QComboBox()
        self.exe = QLineEdit()
        form.addRow(self.c_game)
        form.addRow(self.c_start)
        form.addRow(self.c_lock)
        form.addRow(self.c_auto)
        form.addRow("Pinned profile (when not following)", self.forced)
        form.addRow("Game process name", self.exe)
        form.addRow(QLabel(f"Log folder: {getattr(self.app.source, 'log_dir', '(replay)')}"))
        b = QPushButton("Apply")
        b.clicked.connect(self._apply_general)
        form.addRow(b)
        return w

    def _refresh_general(self):
        s = self.app.settings
        self.c_game.setChecked(bool(s.get("show_only_in_game", True)))
        self.c_start.setChecked(bool(s.get("start_with_windows", False)))
        self.c_lock.setChecked(bool(s.get("locked", False)))
        self.c_auto.setChecked(bool(s.get("auto_switch", True)))
        self.exe.setText(s.get("game_exe", "swtor.exe"))
        self.forced.clear()
        self.forced.addItems(self.app.engine.profile_names)
        i = self.forced.findText(s.get("forced_profile", ""))
        self.forced.setCurrentIndex(max(i, 0))

    def _apply_general(self):
        s = self.app.settings
        s["show_only_in_game"] = self.c_game.isChecked()
        s["start_with_windows"] = self.c_start.isChecked()
        s["locked"] = self.c_lock.isChecked()
        s["auto_switch"] = self.c_auto.isChecked()
        s["forced_profile"] = self.forced.currentText()
        s["game_exe"] = self.exe.text().strip() or "swtor.exe"
        self.app.apply_settings()
        self.note.setText("Settings applied.")
