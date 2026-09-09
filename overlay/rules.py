"""Trigger engine: combat-log Events -> displayable Items, driven by per-discipline JSON profiles.

Rule types (see overlay/profiles/*.json):
  self      buff on you:            ApplyEffect X on me            -> countdown bar (duration), RemoveEffect ends it
  target    effect you put on others: ApplyEffect X by me on other -> one bar per target instance
  stacks    stack counter:          ModifyCharges / Apply / Remove -> number, warn when below `warn_below`
  proc      short proc on you:      ApplyEffect X on me            -> big flash text
  cooldown  ability cooldown:       AbilityActivate X by me        -> bar for `seconds`, then a READY flash
Built in: fight timer from EnterCombat / ExitCombat.
The engine only ever consumes parsed log lines. It never touches the game.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from parser import Event

PROFILE_DIR = Path(__file__).resolve().parent / "profiles"
READY_FLASH_SECONDS = 2.0


@dataclass
class Rule:
    type: str
    effect: str = ""
    ability: str = ""
    duration: float = 0.0
    seconds: float = 0.0        # cooldown length
    warn_at: float = 0.0        # bar turns red with this many seconds left
    warn_below: int = -1        # stacks: warn when count <= this
    max_stacks: int = 0
    text: str = ""              # proc flash text (defaults to effect name)
    label: str = ""
    color: str = ""
    enabled: bool = True
    group: str = ""             # layout group; empty = default for the rule type (see DEFAULT_GROUP)
    sound: str = ""             # "" | "beep" | path to a .wav; plays when the item appears (cooldown: when READY)

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @property
    def group_name(self) -> str:
        return self.group or DEFAULT_GROUP[self.type]


DEFAULT_GROUP = {"self": "buffs", "target": "target", "stacks": "stacks", "proc": "alerts", "cooldown": "cooldowns"}
DEFAULT_GROUPS = ["timer", "stacks", "alerts", "buffs", "target", "cooldowns"]


@dataclass
class Profile:
    name: str
    cls: str
    discipline: str
    rules: list[Rule]
    path: Optional[Path] = None
    auto: bool = False

    @classmethod
    def load(cls, path) -> "Profile":
        path = Path(path)
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(d["name"], d["match"]["class"], d["match"]["discipline"],
                   [Rule.from_dict(r) for r in d["rules"]], path, bool(d.get("_auto")))

    @staticmethod
    def load_all(directory=PROFILE_DIR) -> list["Profile"]:
        """Hand-written profiles first, then generated ones in profiles/auto/. First match wins,
        so a hand-written profile always beats an auto/mirrored one for the same discipline."""
        d = Path(directory)
        paths = sorted(d.glob("*.json")) + sorted((d / "auto").glob("*.json"))
        return [Profile.load(p) for p in paths]


@dataclass
class Item:
    key: str
    kind: str                  # 'fight' | 'stacks' | 'flash' | 'bar' | 'cooldown'
    label: str
    start: float
    end: Optional[float] = None
    stacks: int = 0
    warn_at: float = 0.0
    warn_below: int = -1
    max_stacks: int = 0
    color: str = ""
    target: Optional[str] = None
    order: int = 0
    group: str = ""
    sound: str = ""
    meta: dict = field(default_factory=dict)

    def remaining(self, now: float) -> Optional[float]:
        return None if self.end is None else max(0.0, self.end - now)

    def total(self) -> Optional[float]:
        return None if self.end is None else self.end - self.start

    def warn(self, now: float) -> bool:
        if self.kind == "stacks":
            return self.warn_below >= 0 and self.stacks <= self.warn_below
        r = self.remaining(now)
        return r is not None and self.warn_at > 0 and r <= self.warn_at


class Engine:
    def __init__(self, profiles: list[Profile], forced_profile: Optional[str] = None):
        self.profiles = profiles
        self.forced = forced_profile
        self.profile: Optional[Profile] = None
        self.me: Optional[str] = None
        self.discipline: Optional[str] = None
        self.items: dict[str, Item] = {}
        self.fight_start: Optional[float] = None
        self.last_seconds: float = 0.0
        if forced_profile:
            self.profile = next((p for p in profiles if p.name.lower() == forced_profile.lower()), None)
            if self.profile is None:
                raise SystemExit(f"no profile named {forced_profile!r}; have: {[p.name for p in profiles]}")

    @property
    def profile_names(self) -> list[str]:
        return [p.name for p in self.profiles]

    @property
    def in_combat(self) -> bool:
        return self.fight_start is not None

    def group_names(self) -> list[str]:
        """Default groups plus every group any loaded profile references."""
        names = list(DEFAULT_GROUPS)
        for p in self.profiles:
            for r in p.rules:
                g = r.group_name
                if g not in names:
                    names.append(g)
        return names

    # ---- helpers -------------------------------------------------------------------------------
    def _is_me(self, ent) -> bool:
        return ent is not None and ent.kind == "player" and ent.name == self.me

    def _select_profile(self, cls: str, disc: str):
        self.discipline = f"{cls}/{disc}"
        if self.forced:
            return
        self.profile = next((p for p in self.profiles if p.cls == cls and p.discipline == disc), None)
        self.items.clear()

    def _rules(self, type_: str, name: str, attr: str = "effect"):
        if not self.profile:
            return []
        return [r for r in self.profile.rules if r.enabled and r.type == type_ and getattr(r, attr) == name]

    def reload(self, profiles: list[Profile], forced_profile: Optional[str] = None):
        """Swap in freshly loaded profiles (hot reload) without losing who/where we are."""
        self.profiles = profiles
        self.forced = forced_profile or None
        if self.forced:
            self.profile = next((p for p in profiles if p.name.lower() == self.forced.lower()), None)
        elif self.discipline:
            cls, disc = self.discipline.split("/", 1)
            self.profile = next((p for p in profiles if p.cls == cls and p.discipline == disc), None)
        else:
            self.profile = None
        self.items.clear()

    # ---- event intake --------------------------------------------------------------------------
    def feed(self, ev: Event):
        self.last_seconds = ev.seconds
        src, tgt = ev.source, ev.target
        if self.me is None and ev.type in ("AreaEntered", "DisciplineChanged") and src and src.kind == "player":
            self.me = src.name
        if ev.type == "DisciplineChanged" and self._is_me(src):
            self._select_profile(ev.extra["class"].name, ev.extra["discipline"].name)
            return
        if ev.type == "Event" and ev.effect:
            sub = ev.effect.name
            if sub == "EnterCombat" and self._is_me(src):
                self.fight_start = ev.seconds
            elif sub == "ExitCombat" and self._is_me(src):
                self.fight_start = None
                self.items = {k: v for k, v in self.items.items() if v.kind != "bar" or v.target is None}
            elif sub == "Death" and tgt is not None:
                inst = tgt.instance or tgt.name
                self.items = {k: v for k, v in self.items.items() if v.target != inst}
            elif sub == "AbilityActivate" and self._is_me(src) and ev.ability:
                for r in self._rules("cooldown", ev.ability.name, "ability"):
                    self.items[f"cd:{r.ability}"] = Item(
                        f"cd:{r.ability}", "cooldown", r.label or r.ability, ev.seconds, ev.seconds + r.seconds,
                        color=r.color, order=50, group=r.group_name, sound=r.sound)
            return
        if not ev.effect or not self.profile:
            return
        name = ev.effect.name
        src_me, tgt_me = self._is_me(src), self._is_me(tgt)

        if ev.type == "ApplyEffect":
            if tgt_me:
                for r in self._rules("self", name):
                    end = ev.seconds + r.duration if r.duration else None
                    self.items[f"self:{name}"] = Item(f"self:{name}", "bar", r.label or name, ev.seconds, end,
                                                      warn_at=r.warn_at, color=r.color, order=30,
                                                      group=r.group_name, sound=r.sound)
                for r in self._rules("proc", name):
                    end = ev.seconds + (r.duration or 3.0)
                    self.items[f"proc:{name}"] = Item(f"proc:{name}", "flash", r.text or r.label or name,
                                                      ev.seconds, end, color=r.color, order=20,
                                                      group=r.group_name, sound=r.sound)
                for r in self._rules("stacks", name):
                    it = self.items.get(f"stk:{name}")
                    stacks = max(1, it.stacks) if it else 1
                    self.items[f"stk:{name}"] = Item(f"stk:{name}", "stacks", r.label or name, ev.seconds,
                                                     stacks=stacks, warn_below=r.warn_below,
                                                     max_stacks=r.max_stacks, color=r.color, order=10,
                                                     group=r.group_name, sound=r.sound)
            if src_me and tgt is not None and not tgt_me:
                for r in self._rules("target", name):
                    inst = tgt.instance or tgt.name
                    key = f"tgt:{name}:{inst}"
                    end = ev.seconds + r.duration if r.duration else None
                    self.items[key] = Item(key, "bar", f"{r.label or name} · {tgt.name}", ev.seconds, end,
                                           warn_at=r.warn_at, color=r.color, target=inst, order=40,
                                           stacks=self.items[key].stacks if key in self.items else 0,
                                           group=r.group_name, sound=r.sound)
        elif ev.type == "RemoveEffect":
            if tgt_me:
                self.items.pop(f"self:{name}", None)
                self.items.pop(f"proc:{name}", None)
                it = self.items.get(f"stk:{name}")
                if it:
                    it.stacks = 0
            if tgt is not None and not tgt_me:
                self.items.pop(f"tgt:{name}:{tgt.instance or tgt.name}", None)
        elif ev.type == "ModifyCharges" and ev.value is not None:
            if tgt_me:
                for r in self._rules("stacks", name):
                    it = self.items.get(f"stk:{name}")
                    if it is None:
                        it = Item(f"stk:{name}", "stacks", r.label or name, ev.seconds, warn_below=r.warn_below,
                                  max_stacks=r.max_stacks, color=r.color, order=10, group=r.group_name,
                                  sound=r.sound)
                        self.items[it.key] = it
                    it.stacks = ev.value.amount
            elif tgt is not None:
                it = self.items.get(f"tgt:{name}:{tgt.instance or tgt.name}")
                if it:
                    it.stacks = ev.value.amount

    # ---- output ------------------------------------------------------------------------------
    def snapshot(self, now: float) -> list[Item]:
        out: list[Item] = []
        if self.fight_start is not None:
            out.append(Item("fight", "fight", "Fight", self.fight_start, None, order=0, group="timer"))
        expired = []
        for it in self.items.values():
            if it.kind == "cooldown" and it.end is not None and now >= it.end:
                if now < it.end + READY_FLASH_SECONDS:
                    out.append(Item(it.key + ":ready", "flash", f"{it.label} READY", it.end,
                                    it.end + READY_FLASH_SECONDS, color=it.color, order=20, group="alerts",
                                    sound=it.sound))
                expired.append(it.key)
                continue
            if it.end is not None and now >= it.end and it.kind != "stacks":
                expired.append(it.key)
                continue
            out.append(it)
        for k in expired:
            self.items.pop(k, None)
        out.sort(key=lambda i: (i.order, i.label))
        return out
