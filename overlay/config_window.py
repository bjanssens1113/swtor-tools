"""Configuration window: edit profile rules and launch settings. Opened from the tray icon.

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
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
                             QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from rules import PROFILE_DIR

ROOT = Path(__file__).resolve().parents[1]
DISC_DATA = ROOT / "overlay" / "data" / "disciplines.json"
RULE_TYPES = ["self", "target", "stacks", "proc", "cooldown"]
COLS = ["On", "Type", "Effect / ability", "Duration s", "Cooldown s", "Warn at", "Label", "Color"]


def _load_disc_data() -> dict:
    try:
        return json.loads(DISC_DATA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class AddRuleDialog(QDialog):
    def __init__(self, parent, cls: str, disc: str):
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
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        form = QFormLayout(self)
        form.addRow("Type", self.type)
        form.addRow("Name", self.name)
        form.addRow("Duration / cooldown (s)", self.seconds)
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
        else:
            r["effect"] = name
            if t != "stacks" and self.seconds.value() > 0:
                r["duration"] = self.seconds.value()
            if t == "target":
                r["warn_at"] = 2
        return r


class ConfigWindow(QDialog):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("SWTOR overlay — settings")
        self.resize(820, 560)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        tabs = QTabWidget()
        tabs.addTab(self._rules_tab(), "Rules")
        tabs.addTab(self._general_tab(), "General")
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        self.doc: dict = {}
        self.doc_path: Path | None = None

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
        self.table.setColumnWidth(2, 220)
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
        self.note = QLabel("")
        self.note.setWordWrap(True)
        v.addWidget(self.note)
        return w

    def refresh(self):
        self._refresh_general()
        cur = self.profile_box.currentData()
        self.profile_box.blockSignals(True)
        self.profile_box.clear()
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
        self.table.setItem(row, 0, on)
        t = QTableWidgetItem(r.get("type", ""))
        t.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.table.setItem(row, 1, t)
        self.table.setItem(row, 2, QTableWidgetItem(r.get("effect") or r.get("ability") or ""))
        self.table.setItem(row, 3, QTableWidgetItem(str(r.get("duration", "") or "")))
        self.table.setItem(row, 4, QTableWidgetItem(str(r.get("seconds", "") or "")))
        self.table.setItem(row, 5, QTableWidgetItem(str(r.get("warn_at", "") or "")))
        self.table.setItem(row, 6, QTableWidgetItem(r.get("label", "")))
        self.table.setItem(row, 7, QTableWidgetItem(r.get("color", "")))
        self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, dict(r))

    def _add_rule(self):
        m = self.doc.get("match", {})
        dlg = AddRuleDialog(self, m.get("class", ""), m.get("discipline", ""))
        if dlg.exec():
            self._append_row(dlg.rule())

    def _remove_rule(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)

    def _rows_to_rules(self) -> list[dict]:
        def num(row, col):
            txt = (self.table.item(row, col).text() if self.table.item(row, col) else "").strip()
            try:
                return float(txt) if txt else None
            except ValueError:
                return None
        out = []
        for row in range(self.table.rowCount()):
            r = dict(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) or {})
            r["type"] = self.table.item(row, 1).text()
            name = self.table.item(row, 2).text().strip()
            if r["type"] == "cooldown":
                r["ability"] = name
                r.pop("effect", None)
            else:
                r["effect"] = name
                r.pop("ability", None)
            for key, col in (("duration", 3), ("seconds", 4), ("warn_at", 5)):
                v = num(row, col)
                if v:
                    r[key] = v
                else:
                    r.pop(key, None)
            for key, col in (("label", 6), ("color", 7)):
                v = self.table.item(row, col).text().strip()
                if v:
                    r[key] = v
                else:
                    r.pop(key, None)
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked:
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

    # ---- general tab ----------------------------------------------------------------------------
    def _general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        s = self.app.settings
        self.c_game = QCheckBox("Show the overlay only while the game is running")
        self.c_start = QCheckBox("Start with Windows (shortcut in the Startup folder)")
        self.c_lock = QCheckBox("Locked (click-through)")
        self.c_auto = QCheckBox("Follow discipline changes in the log")
        self.forced = QComboBox()
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.5, 3.0)
        self.scale.setSingleStep(0.1)
        self.exe = QLineEdit()
        form.addRow(self.c_game)
        form.addRow(self.c_start)
        form.addRow(self.c_lock)
        form.addRow(self.c_auto)
        form.addRow("Pinned profile (when not following)", self.forced)
        form.addRow("Overlay scale", self.scale)
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
        self.scale.setValue(float(s.get("scale", 1.0)))
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
        s["scale"] = round(self.scale.value(), 2)
        s["game_exe"] = self.exe.text().strip() or "swtor.exe"
        self.app.apply_settings()
        self.note.setText("Settings applied.")
