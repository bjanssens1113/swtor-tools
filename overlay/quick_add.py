"""Quick add: put one ability or effect on screen in three clicks.

Search everything known for the current discipline (log-mined abilities / buffs / target effects / stacks, plus
Parsely's ability list for the class), choose what to track, choose a group, Add. The rule is appended to the
active profile (a generated profile becomes a hand-written copy) and previewed immediately.
"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout)

import icons
from rules import append_rule_to_file

ROOT = Path(__file__).resolve().parents[1]
DISC_DATA = ROOT / "overlay" / "data" / "disciplines.json"
PARSELY = ROOT / "overlay" / "data" / "parsely_abilities.json"
REPUBLIC = {"Scoundrel", "Commando", "Sage", "Shadow", "Guardian", "Sentinel", "Vanguard", "Gunslinger"}
TRACK = [
    ("cooldown", "Cooldown after I use it"),
    ("self", "Buff on me (countdown)"),
    ("stacks", "Stack counter on me"),
    ("target", "My effect on a target (bar per target)"),
    ("proc", "Proc flash when it appears on me"),
    ("missing", "Alert while it is NOT on me (in combat)"),
]


def candidates(cls: str, disc: str) -> list[dict]:
    """[{name, kind, hint, seconds}] for the discipline: 'ability' | 'buff' | 'target' | 'stacks'."""
    out, seen = [], set()
    try:
        d = json.loads(DISC_DATA.read_text(encoding="utf-8")).get(f"{cls}/{disc}", {})
    except (OSError, ValueError):
        d = {}
    for a in d.get("abilities", []):
        out.append({"name": a["name"], "kind": "ability", "seconds": a.get("p10_gap") or 0,
                    "hint": f"ability · {a['uses']} uses · re-use gap {a.get('p10_gap')} s"})
        seen.add(a["name"])
    for x in d.get("stacks", []):
        out.append({"name": x["name"], "kind": "stacks", "seconds": 0, "hint": f"stacks · max {x.get('max_seen')}"})
        seen.add(x["name"])
    for x in d.get("self_buffs", []):
        if x["name"] not in seen:
            out.append({"name": x["name"], "kind": "buff", "seconds": x.get("median_s") or 0,
                        "hint": f"buff on you · lasts ~{x.get('median_s')} s"})
            seen.add(x["name"])
    for x in d.get("target_effects", []):
        if x["name"] not in seen:
            out.append({"name": x["name"], "kind": "target", "seconds": x.get("p75_s") or 0,
                        "hint": f"on targets · lasts ~{x.get('p75_s')} s"})
            seen.add(x["name"])
    try:
        pd = json.loads(PARSELY.read_text(encoding="utf-8")).get(cls, {})
    except (OSError, ValueError):
        pd = {}
    col = 2 if cls in REPUBLIC else 1
    for sec, rows in pd.items():
        if disc and " / " in sec and disc not in sec:
            continue  # other disciplines' skills
        for row in rows:
            n = row[col]
            if n and n not in seen:
                out.append({"name": n, "kind": "ability", "seconds": 0, "hint": f"{sec} (from Parsely; no log data yet)"})
                seen.add(n)
    return out


class QuickAddDialog(QDialog):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("Quick add — put an ability on screen")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.resize(560, 620)
        prof = app.engine.profile
        self.cls, self.disc = (prof.cls, prof.discipline) if prof else ("", "")
        self.cands = candidates(self.cls, self.disc)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(f"Profile: <b>{prof.name if prof else 'none (log not read yet)'}</b>"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("type an ability or effect name…")
        self.search.textChanged.connect(self._fill)
        v.addWidget(self.search)
        self.list = QListWidget()
        self.list.setIconSize(QSize(28, 28))
        self.list.currentItemChanged.connect(self._picked)
        v.addWidget(self.list, 1)
        form = QFormLayout()
        self.track = QComboBox()
        for key, text in TRACK:
            self.track.addItem(text, key)
        self.seconds = QDoubleSpinBox()
        self.seconds.setRange(0, 900)
        self.seconds.setDecimals(1)
        self.group = QComboBox()
        self.group.setEditable(True)
        self.group.addItems(app.group_names())
        self.sound = QComboBox()
        self.sound.setEditable(True)
        self.sound.addItems(["", "beep", "say:ready"])
        form.addRow("Track", self.track)
        form.addRow("Seconds (cooldown / duration)", self.seconds)
        form.addRow("Group (type a new name to create one)", self.group)
        form.addRow("Sound", self.sound)
        v.addLayout(form)
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        v.addWidget(self.hint)
        row = QHBoxLayout()
        b_add = QPushButton("Add to profile and preview")
        b_add.clicked.connect(self._add)
        b_close = QPushButton("Close")
        b_close.clicked.connect(self.close)
        row.addStretch(1)
        row.addWidget(b_close)
        row.addWidget(b_add)
        v.addLayout(row)
        self._fill()

    def _fill(self):
        q = self.search.text().lower()
        self.list.clear()
        for c in self.cands:
            if q in c["name"].lower():
                it = QListWidgetItem(c["name"])
                p = icons.icon_path(c["name"])
                if p:
                    it.setIcon(QIcon(str(p)))
                it.setData(Qt.ItemDataRole.UserRole, c)
                self.list.addItem(it)
            if self.list.count() >= 400:
                break

    def _picked(self, cur, _prev=None):
        if not cur:
            return
        c = cur.data(Qt.ItemDataRole.UserRole)
        default = {"ability": "cooldown", "buff": "self", "stacks": "stacks", "target": "target"}[c["kind"]]
        self.track.setCurrentIndex(self.track.findData(default))
        self.seconds.setValue(float(c["seconds"] or 0))
        self.hint.setText(c["hint"])

    def _add(self):
        cur = self.list.currentItem()
        prof = self.app.engine.profile
        if not cur or not prof:
            QMessageBox.information(self, "Quick add", "Pick an entry first (and make sure a profile is active).")
            return
        name = cur.text()
        t = self.track.currentData()
        secs = self.seconds.value()
        r: dict = {"type": t}
        if t == "cooldown":
            r["ability"] = name
            r["seconds"] = secs or 10
        else:
            r["effect"] = name
            if t in ("self", "target", "proc") and secs:
                r["duration"] = secs
            if t == "target":
                r["warn_at"] = 2
            if t == "missing":
                r["label"] = f"MISSING {name}"
                r["in_combat"] = True
        g = self.group.currentText().strip()
        if g:
            r["group"] = g
            self.app.add_group(g)
        if self.sound.currentText().strip():
            r["sound"] = self.sound.currentText().strip()
        try:
            written = append_rule_to_file(prof.path, r)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Quick add", f"Could not save: {e}")
            return
        self.app.reload_profiles()
        self.app.preview_rule(r)
        self.hint.setText(f"Added '{name}' as {t} to {written.name} in group '{g or 'default'}'. "
                          "Press CONFIGURE LAYOUT to drag it (free layout lets you place it on its own).")
