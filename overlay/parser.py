"""SWTOR combat log line -> structured Event.

Format (7.x, <v7.0.0b>), see docs/LOG_FORMAT.md:
  [HH:MM:SS.mmm] [SOURCE] [TARGET] [ABILITY {id}] [EVENT {id}: SUBTYPE {id}] (VALUE) <THREAT>
This module reads text only. It has no knowledge of the game process.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# SWTOR writes the log in the Windows ANSI code page, not UTF-8 (accented character names break utf-8).
LOG_ENCODING = "cp1252"

_LINE_RE = re.compile(
    r"^\[(?P<time>[^\]]*)\] \[(?P<src>[^\]]*)\] \[(?P<tgt>[^\]]*)\] "
    r"\[(?P<ability>[^\]]*)\] \[(?P<event>[^\]]*)\]"
    r"(?: \((?P<value>.*)\))?(?: <(?P<threat>[^>]*)>)?\s*$"
)
_ENTITY_RE = re.compile(r"^(?P<name>.*?)\|\((?P<pos>[^)]*)\)\|\((?P<hp>-?\d+)/(?P<maxhp>-?\d+)\)$")
_NAMED_ID_RE = re.compile(r"^(?P<name>.*?)\s*\{(?P<id>\d+)\}$")
_INST_RE = re.compile(r"^(?P<name>.*?)\s*\{(?P<id>\d+)\}:(?P<inst>\d+)$")
_VALUE_RE = re.compile(
    r"^(?P<amount>-?\d+)(?P<crit>\*)?"
    r"(?:\s+(?P<kind>[^{~(]+?)\s*\{(?P<kind_id>\d+)\})?"
    r"(?:\s*~(?P<effective>-?\d+))?"
    r"(?P<rest>.*)$"
)


@dataclass(frozen=True)
class Entity:
    name: str                      # player name without '@' / companion name / NPC name
    kind: str                      # 'player' | 'companion' | 'npc'
    id: str                        # player id / npc type id
    instance: Optional[str] = None # NPC/companion spawn instance id
    owner: Optional[str] = None    # companion owner's player name
    hp: int = 0
    max_hp: int = 0
    pos: tuple = ()


@dataclass(frozen=True)
class NamedId:
    name: str
    id: str


@dataclass(frozen=True)
class Value:
    amount: int
    crit: bool = False
    kind: Optional[str] = None      # damage type ('kinetic', 'energy', ...) or None for heals
    kind_id: Optional[str] = None
    effective: Optional[int] = None # heal: effective amount after overheal
    raw: str = ""


@dataclass
class Event:
    time: str                    # 'HH:MM:SS.mmm'
    seconds: float               # seconds since midnight
    source: Optional[Entity]
    target: Optional[Entity]     # resolved: '=' becomes source
    ability: Optional[NamedId]
    type: str                    # 'ApplyEffect' | 'RemoveEffect' | 'Event' | 'ModifyCharges' | 'Spend' | 'Restore' | ...
    type_id: str
    effect: Optional[NamedId]    # subtype: 'Damage' | 'Heal' | buff name | 'AbilityActivate' | ...
    value: Optional[Value]
    threat: Optional[float]
    raw: str = field(repr=False, default="")
    extra: dict = field(default_factory=dict)  # DisciplineChanged -> class/discipline; AreaEntered -> area/server/tag

    @property
    def is_self_target(self) -> bool:
        return self.source is not None and self.target is not None and self.source == self.target


def parse_named_id(text: str) -> Optional[NamedId]:
    text = text.strip()
    if not text:
        return None
    m = _NAMED_ID_RE.match(text)
    if not m:
        return NamedId(text, "")
    return NamedId(m.group("name").strip(), m.group("id"))


def parse_entity(text: str) -> Optional[Entity]:
    """Empty -> None. The '=' (same as source) marker must be resolved by the caller."""
    text = text.strip()
    if not text or text == "=":
        return None
    m = _ENTITY_RE.match(text)
    if not m:
        return Entity(name=text, kind="npc", id="")
    name_part = m.group("name")
    hp, max_hp = int(m.group("hp")), int(m.group("maxhp"))
    pos = tuple(float(x) for x in m.group("pos").split(",")) if m.group("pos") else ()
    if name_part.startswith("@"):
        owner_part, sep, comp_part = name_part[1:].partition("/")
        pname, _, pid = owner_part.partition("#")
        if sep:  # companion
            cm = _INST_RE.match(comp_part)
            if cm:
                return Entity(cm.group("name"), "companion", cm.group("id"), cm.group("inst"), pname, hp, max_hp, pos)
            return Entity(comp_part, "companion", "", None, pname, hp, max_hp, pos)
        return Entity(pname, "player", pid, None, None, hp, max_hp, pos)
    nm = _INST_RE.match(name_part)
    if nm:
        return Entity(nm.group("name"), "npc", nm.group("id"), nm.group("inst"), None, hp, max_hp, pos)
    return Entity(name_part, "npc", "", None, None, hp, max_hp, pos)


def parse_value(text: Optional[str]) -> Optional[Value]:
    if text is None:
        return None
    m = _VALUE_RE.match(text.strip())
    if not m:
        return Value(0, raw=text)
    return Value(
        amount=int(m.group("amount")),
        crit=bool(m.group("crit")),
        kind=(m.group("kind") or "").strip() or None,
        kind_id=m.group("kind_id"),
        effective=int(m.group("effective")) if m.group("effective") is not None else None,
        raw=text,
    )


def time_to_seconds(t: str) -> float:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_line(line: str) -> Optional[Event]:
    m = _LINE_RE.match(line.rstrip("\r\n"))
    if not m:
        return None
    src = parse_entity(m.group("src"))
    tgt_raw = m.group("tgt").strip()
    tgt = src if tgt_raw == "=" else parse_entity(tgt_raw)

    ev_text = m.group("event")
    left, _, right = ev_text.partition(": ")
    ev = parse_named_id(left)
    extra: dict = {}
    effect: Optional[NamedId]
    if ev and ev.name == "DisciplineChanged":
        cls, _, disc = right.partition("/")
        extra = {"class": parse_named_id(cls), "discipline": parse_named_id(disc)}
        effect = NamedId("DisciplineChanged", "")
    elif ev and ev.name == "AreaEntered":
        extra = {"area": parse_named_id(right)}
        effect = NamedId("AreaEntered", "")
    else:
        effect = parse_named_id(right) if right else None

    threat = None
    if m.group("threat") is not None:
        try:
            threat = float(m.group("threat"))
        except ValueError:
            extra["tag"] = m.group("threat")  # e.g. 'v7.0.0b' on AreaEntered

    value = None
    if m.group("value") is not None:
        v = m.group("value")
        if v.startswith("he") and v[2:].isdigit():
            extra["server"] = v  # AreaEntered '(he3000)'
        else:
            value = parse_value(v)

    t = m.group("time")
    return Event(
        time=t,
        seconds=time_to_seconds(t),
        source=src,
        target=tgt,
        ability=parse_named_id(m.group("ability")),
        type=ev.name if ev else left,
        type_id=ev.id if ev else "",
        effect=effect,
        value=value,
        threat=threat,
        raw=line,
        extra=extra,
    )


def parse_file(path, encoding=LOG_ENCODING):
    """Yield Events from a whole log file (tests/catalog). The live tailer uses parse_line."""
    with open(path, encoding=encoding, errors="replace") as fh:
        for line in fh:
            ev = parse_line(line)
            if ev:
                yield ev
