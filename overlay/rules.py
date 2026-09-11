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
import re
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
    icon: str = ""              # ability/passive name whose icon to show (default: the effect/ability itself)
    # ---- conditions ----
    regex: bool = False         # treat `effect` as a regular expression (e.g. "Kyrprax .* Stim$")
    in_combat: Optional[bool] = None   # True: only in combat; False: only out of combat; None: always
    stacks_below: int = -1      # stacks rule: show only while count < N
    stacks_at_least: int = -1   # stacks rule: show only while count >= N
    boss_only: Optional[bool] = None  # target: only bosses (default no); cast: only bosses (default yes)
    charges: int = 1            # cooldown rule: abilities with multiple charges (shows n/max, recharges one at a time)
    # ---- cleanse rules ----
    types: list = field(default_factory=list)   # debuff categories you can cleanse: Physical, Tech, Mental, Force
    ignore: list = field(default_factory=list)  # debuff names never worth a cleanse alert (e.g. "Slowed (Tech)")

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @property
    def group_name(self) -> str:
        return self.group or DEFAULT_GROUP[self.type]

    def matches(self, name: str, attr: str = "effect") -> bool:
        pat = getattr(self, attr)
        if not pat:
            return False
        if self.regex:
            try:
                return re.search(pat, name) is not None
            except re.error:
                return False
        return pat == name

    @property
    def cond(self) -> dict:
        return {"in_combat": self.in_combat, "stacks_below": self.stacks_below,
                "stacks_at_least": self.stacks_at_least}


DEFAULT_GROUP = {"self": "buffs", "target": "target", "stacks": "stacks", "proc": "alerts", "cooldown": "cooldowns",
                 "missing": "alerts", "cleanse": "alerts", "cast": "alerts"}
DEFAULT_GROUPS = ["timer", "stacks", "alerts", "buffs", "target", "cooldowns", "party"]
RULE_TYPES = ["self", "target", "stacks", "proc", "cooldown", "missing", "cleanse", "cast"]
PREVIEW_SECONDS = 5.0


def item_stem(key: str) -> str:
    """Stable identity of an item across targets/instances, used for free-layout positions:
    'tgt:Corrosive Dart:12345' -> 'tgt:Corrosive Dart', 'cd:Shiv:ready' -> 'cd:Shiv'."""
    if key.endswith(":ready"):
        key = key[:-6]
    parts = key.split(":")
    if parts[0] in ("tgt", "cl", "preview") and len(parts) >= 3:
        return ":".join(parts[:2]) if parts[0] != "preview" else ":".join(parts[1:3])
    if parts[0] == "cast" and len(parts) >= 3:
        return "cast:" + parts[-1]
    return key


def append_rule_to_file(path: Path, rule: dict, profile_dir: Path = PROFILE_DIR) -> Path:
    """Append a rule to a profile file. A generated (auto/mirrored) profile is first copied to a hand-written
    file in profile_dir, which then takes priority. Returns the path that was written."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    target = Path(path)
    if doc.get("_auto"):
        m = doc["match"]
        doc["name"] = re.sub(r"\s*\((auto|mirrored)\)$", "", doc["name"])
        doc.pop("_auto", None)
        doc.pop("_kind", None)
        doc["_source"] = f"hand-edited copy of generated profile. {doc.get('_source', '')}"
        target = profile_dir / (f"{m['class']}_{m['discipline']}".lower().replace(" ", "_") + ".json")
        if target.exists():
            doc = json.loads(target.read_text(encoding="utf-8"))
    doc.setdefault("rules", []).append(rule)
    target.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return target


def fmt_label(template: str, effect: str = "", target: str = "") -> str:
    """Static label tokens: %e = effect/ability name, %n = target name. (%r remaining and %s stacks are
    substituted at draw time by the window.)"""
    return template.replace("%e", effect).replace("%n", target)
CLEANSE_TTL = 20.0          # a cleanse alert expires on its own after this many seconds
ROSTER_TTL = 120.0          # a group member drops off the party panel after this long without a log line
DEBUFF_TYPE_RE = re.compile(r"\((Physical|Tech|Mental|Force)\)$")


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
        so a hand-written profile always beats an auto/mirrored one for the same discipline.
        Files starting with '_' are global rule sets (see load_global) and are skipped here."""
        d = Path(directory)
        paths = [p for p in sorted(d.glob("*.json")) if not p.name.startswith("_")] + sorted((d / "auto").glob("*.json"))
        return [Profile.load(p) for p in paths]

    @staticmethod
    def load_global(directory=PROFILE_DIR) -> list[Rule]:
        """Rules from profiles/_*.json apply to every discipline (stim / class-buff reminders etc.)."""
        rules: list[Rule] = []
        for p in sorted(Path(directory).glob("_*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            rules += [Rule.from_dict(r) for r in d.get("rules", [])]
        return rules


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
    icon: str = ""             # effect / ability name used to look up an icon image
    cond: dict = field(default_factory=dict)   # display conditions from the rule (see Rule.cond)
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
    boss_hp = 500_000  # NPC max HP at/above which a target counts as a boss for boss_only rules

    def __init__(self, profiles: list[Profile], forced_profile: Optional[str] = None,
                 global_rules: Optional[list[Rule]] = None):
        self.profiles = profiles
        self.forced = forced_profile
        self.global_rules: list[Rule] = list(global_rules or [])
        self.profile: Optional[Profile] = None
        self.me: Optional[str] = None
        self.discipline: Optional[str] = None
        self.items: dict[str, Item] = {}
        self.active_self: set[str] = set()   # every effect currently on me (for 'missing' rules)
        # party roster: name -> {hp, max_hp, seen, friendly, kind ('player'|'companion'), dead}
        self.roster: dict[str, dict] = {}
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

    def group_names(self, extra: Optional[list[str]] = None) -> list[str]:
        """Default groups, user-created groups (`extra`, from settings), and every group a profile references."""
        names = list(DEFAULT_GROUPS)
        for g in extra or []:
            if g not in names:
                names.append(g)
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
        self.items = {k: v for k, v in self.items.items() if k.startswith("preview:")}

    def _all_rules(self):
        return (self.profile.rules if self.profile else []) + self.global_rules

    def _rules(self, type_: str, name: str, attr: str = "effect"):
        return [r for r in self._all_rules() if r.enabled and r.type == type_ and r.matches(name, attr)]

    def reload(self, profiles: list[Profile], forced_profile: Optional[str] = None,
               global_rules: Optional[list[Rule]] = None):
        """Swap in freshly loaded profiles (hot reload) without losing who/where we are."""
        self.profiles = profiles
        if global_rules is not None:
            self.global_rules = list(global_rules)
        self.forced = forced_profile or None
        if self.forced:
            self.profile = next((p for p in profiles if p.name.lower() == self.forced.lower()), None)
        elif self.discipline:
            cls, disc = self.discipline.split("/", 1)
            self.profile = next((p for p in profiles if p.cls == cls and p.discipline == disc), None)
        else:
            self.profile = None
        self.items = {k: v for k, v in self.items.items() if k.startswith("preview:")}

    # ---- roster -------------------------------------------------------------------------------
    def _track(self, ent, seconds: float, as_source: bool, healed_by_me: bool = False):
        """Record HP for players and my companions. 'friendly' = appeared as a source (only group members'
        actions are logged) or was healed by me; enemy players only ever appear as my targets."""
        if ent is None:
            return
        if ent.kind == "companion":
            if ent.owner != self.me:
                return
            kind = "companion"
        elif ent.kind == "player":
            kind = "player"
        else:
            return
        r = self.roster.get(ent.name)
        if r is None:
            r = self.roster[ent.name] = {"hp": 0, "max_hp": 0, "seen": 0.0, "friendly": False, "kind": kind, "dead": False}
        if ent.max_hp:
            r["hp"], r["max_hp"] = ent.hp, ent.max_hp
            if ent.hp > 0:
                r["dead"] = False
        r["seen"] = seconds
        if as_source or healed_by_me or ent.name == self.me or kind == "companion":
            r["friendly"] = True

    # ---- event intake --------------------------------------------------------------------------
    def feed(self, ev: Event):
        self.last_seconds = ev.seconds
        src, tgt = ev.source, ev.target
        healed = ev.type == "ApplyEffect" and ev.effect is not None and ev.effect.name == "Heal" and self._is_me(src)
        self._track(src, ev.seconds, as_source=True)
        self._track(tgt, ev.seconds, as_source=False, healed_by_me=healed)
        if self.me is None and ev.type in ("AreaEntered", "DisciplineChanged") and src and src.kind == "player":
            self.me = src.name
        if ev.type == "AreaEntered" and self._is_me(src):
            self.active_self.clear()   # the game re-logs every active buff right after AreaEntered
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
                if tgt.name in self.roster:
                    self.roster[tgt.name]["dead"] = True
                    self.roster[tgt.name]["hp"] = 0
            elif sub == "Revived" and tgt is not None and tgt.name in self.roster:
                self.roster[tgt.name]["dead"] = False
            elif sub == "AbilityActivate" and self._is_me(src) and ev.ability:
                for r in self._rules("cooldown", ev.ability.name, "ability"):
                    key = f"cd:{r.ability}"
                    label = fmt_label(r.label, ev.ability.name) if r.label else r.ability
                    if r.charges > 1:
                        it = self.items.get(key)
                        if it is None:
                            it = Item(key, "cooldown", label, ev.seconds, ev.seconds + r.seconds, color=r.color,
                                      order=50, group=r.group_name, sound=r.sound, icon=r.icon or r.ability,
                                      cond=r.cond, meta={"charges": r.charges, "max": r.charges, "seconds": r.seconds})
                            self.items[key] = it
                        if it.meta["charges"] > 0:
                            if it.meta["charges"] == it.meta["max"]:
                                it.start, it.end = ev.seconds, ev.seconds + r.seconds
                            it.meta["charges"] -= 1
                        it.stacks = it.meta["charges"]
                        continue
                    self.items[key] = Item(key, "cooldown", label, ev.seconds, ev.seconds + r.seconds,
                                           color=r.color, order=50, group=r.group_name, sound=r.sound,
                                           icon=r.icon or r.ability, cond=r.cond)
            elif sub == "AbilityActivate" and src is not None and src.kind == "npc" and ev.ability:
                for r in self._all_rules():
                    if not (r.enabled and r.type == "cast" and r.matches(ev.ability.name, "ability")):
                        continue
                    if (r.boss_only is None or r.boss_only) and src.max_hp < self.boss_hp:
                        continue
                    key = f"cast:{src.instance or src.name}:{ev.ability.name}"
                    label = fmt_label(r.label, ev.ability.name, src.name) if r.label else f"{src.name}: {ev.ability.name}"
                    self.items[key] = Item(key, "flash", label, ev.seconds, ev.seconds + (r.duration or 3.0),
                                           color=r.color, order=4, group=r.group_name, sound=r.sound,
                                           icon=r.icon or ev.ability.name, cond=r.cond, target=src.instance or src.name)
            return
        if not ev.effect:
            return
        name = ev.effect.name
        src_me, tgt_me = self._is_me(src), self._is_me(tgt)
        if tgt_me and name not in ("Damage", "Heal"):
            if ev.type == "ApplyEffect":
                self.active_self.add(name)
            elif ev.type == "RemoveEffect":
                self.active_self.discard(name)
        if not self.profile and not self.global_rules:
            return

        if ev.type == "ApplyEffect":
            if tgt_me:
                for r in self._rules("self", name):
                    end = ev.seconds + r.duration if r.duration else None
                    self.items[f"self:{name}"] = Item(f"self:{name}", "bar", fmt_label(r.label or "%e", name),
                                                      ev.seconds, end, warn_at=r.warn_at, color=r.color, order=30,
                                                      group=r.group_name, sound=r.sound, icon=r.icon or name,
                                                      cond=r.cond)
                for r in self._rules("proc", name):
                    end = ev.seconds + (r.duration or 3.0)
                    self.items[f"proc:{name}"] = Item(f"proc:{name}", "flash",
                                                      fmt_label(r.text or r.label or "%e", name),
                                                      ev.seconds, end, color=r.color, order=20,
                                                      group=r.group_name, sound=r.sound, icon=r.icon or name,
                                                      cond=r.cond)
                for r in self._rules("stacks", name):
                    it = self.items.get(f"stk:{name}")
                    stacks = max(1, it.stacks) if it else 1
                    self.items[f"stk:{name}"] = Item(f"stk:{name}", "stacks", fmt_label(r.label or "%e", name),
                                                     ev.seconds, stacks=stacks, warn_below=r.warn_below,
                                                     max_stacks=r.max_stacks, color=r.color, order=10,
                                                     group=r.group_name, sound=r.sound, icon=r.icon or name,
                                                     cond=r.cond)
            # cleanse: an NPC put a typed debuff on a friendly player / my companion
            if tgt is not None and src is not None and src.kind == "npc" and tgt.name in self.roster \
                    and self.roster[tgt.name]["friendly"]:
                m = DEBUFF_TYPE_RE.search(name)
                if m:
                    for r in self._all_rules():
                        if not (r.enabled and r.type == "cleanse") or m.group(1) not in r.types or name in r.ignore:
                            continue
                        key = f"cl:{name}:{tgt.name}"
                        base = name[: m.start()].strip()
                        self.items[key] = Item(key, "cleanse", f"CLEANSE {tgt.name}: {base}", ev.seconds,
                                               ev.seconds + CLEANSE_TTL, color=r.color, target=tgt.name, order=6,
                                               group=r.group_name, sound=r.sound, icon=r.icon, cond=r.cond,
                                               meta={"type": m.group(1)})
            if src_me and tgt is not None and not tgt_me:
                for r in self._rules("target", name):
                    if r.boss_only and tgt.max_hp < self.boss_hp:
                        continue
                    inst = tgt.instance or tgt.name
                    key = f"tgt:{name}:{inst}"
                    end = ev.seconds + r.duration if r.duration else None
                    label = fmt_label(r.label, name, tgt.name) if "%" in r.label else f"{r.label or name} · {tgt.name}"
                    self.items[key] = Item(key, "bar", label, ev.seconds, end,
                                           warn_at=r.warn_at, color=r.color, target=inst, order=40,
                                           stacks=self.items[key].stacks if key in self.items else 0,
                                           group=r.group_name, sound=r.sound, icon=r.icon or name, cond=r.cond)
        elif ev.type == "RemoveEffect":
            if tgt_me:
                self.items.pop(f"self:{name}", None)
                self.items.pop(f"proc:{name}", None)
                it = self.items.get(f"stk:{name}")
                if it:
                    it.stacks = 0
            if tgt is not None and not tgt_me:
                self.items.pop(f"tgt:{name}:{tgt.instance or tgt.name}", None)
            if tgt is not None:
                self.items.pop(f"cl:{name}:{tgt.name}", None)
        elif ev.type == "ModifyCharges" and ev.value is not None:
            if tgt_me:
                for r in self._rules("stacks", name):
                    it = self.items.get(f"stk:{name}")
                    if it is None:
                        it = Item(f"stk:{name}", "stacks", fmt_label(r.label or "%e", name), ev.seconds,
                                  warn_below=r.warn_below, max_stacks=r.max_stacks, color=r.color, order=10,
                                  group=r.group_name, sound=r.sound, icon=r.icon or name, cond=r.cond)
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
            if it.key.startswith("preview:") and it.end is not None and now >= it.end:
                expired.append(it.key)
                continue
            if it.kind == "cooldown" and it.meta.get("max", 1) > 1 and it.end is not None:
                while now >= it.end and it.meta["charges"] < it.meta["max"]:
                    it.meta["charges"] += 1
                    it.stacks = it.meta["charges"]
                    it.start, it.end = it.end, it.end + it.meta["seconds"]
                if it.meta["charges"] >= it.meta["max"]:
                    expired.append(it.key)
                    if now < it.start + READY_FLASH_SECONDS:
                        out.append(Item(it.key + ":ready", "flash", f"{it.label} READY", it.start,
                                        it.start + READY_FLASH_SECONDS, color=it.color, order=20, group="alerts",
                                        sound=it.sound, icon=it.icon))
                    continue
                out.append(it)
                continue
            if it.kind == "cooldown" and it.end is not None and now >= it.end:
                if now < it.end + READY_FLASH_SECONDS:
                    out.append(Item(it.key + ":ready", "flash", f"{it.label} READY", it.end,
                                    it.end + READY_FLASH_SECONDS, color=it.color, order=20, group="alerts",
                                    sound=it.sound, icon=it.icon))
                expired.append(it.key)
                continue
            if it.end is not None and now >= it.end and it.kind != "stacks":
                expired.append(it.key)
                continue
            out.append(it)
        for k in expired:
            self.items.pop(k, None)
        out = [it for it in out if self._cond_ok(it)]
        # 'missing' rules: alert when a buff is not on me
        if self.me is not None:
            for r in self._all_rules():
                if not (r.enabled and r.type == "missing"):
                    continue
                in_combat = True if r.in_combat is None else r.in_combat   # default: only nag in combat
                if in_combat and not self.in_combat or (r.in_combat is False and self.in_combat):
                    continue
                if any(r.matches(n) for n in self.active_self):
                    continue
                out.append(Item(f"miss:{r.effect}", "missing", r.label or f"MISSING {r.effect}", now, None,
                                color=r.color, order=5, group=r.group_name, sound=r.sound,
                                icon=r.icon or ("" if r.regex else r.effect)))
        out += self._party_items(now)
        out.sort(key=lambda i: (i.order, i.label))
        return out

    def preview(self, r: Rule, now: float):
        """Insert a fake item for this rule so the user can see where/how it renders (expires after 5 s)."""
        end = now + PREVIEW_SECONDS
        name = r.effect or r.ability or "Preview"
        prefix = {"self": "self", "target": "tgt", "stacks": "stk", "cooldown": "cd", "missing": "miss",
                  "cleanse": "cl", "cast": "cast", "proc": "proc"}.get(r.type, r.type)
        key = f"preview:{prefix}:{name}"   # same stem as the real item, so free-layout positions carry over
        common = dict(color=r.color, group=r.group_name, sound=r.sound, icon=r.icon or name, cond={})
        if r.type == "self":
            it = Item(key, "bar", fmt_label(r.label or "%e", name), now, end, warn_at=r.warn_at, order=30, **common)
        elif r.type == "target":
            lbl = fmt_label(r.label, name, "Target") if "%" in r.label else f"{r.label or name} · Target"
            it = Item(key, "bar", lbl, now, end, warn_at=r.warn_at, order=40, target="preview", **common)
        elif r.type == "stacks":
            it = Item(key, "stacks", fmt_label(r.label or "%e", name), now, end, stacks=max(1, r.max_stacks or 2),
                      warn_below=r.warn_below, max_stacks=r.max_stacks, order=10, **common)
        elif r.type == "cooldown":
            it = Item(key, "cooldown", fmt_label(r.label, name) if r.label else name, now, end, order=50, **common)
            if r.charges > 1:
                it.meta = {"charges": r.charges - 1, "max": r.charges, "seconds": PREVIEW_SECONDS}
                it.stacks = r.charges - 1
        elif r.type == "missing":
            it = Item(key, "missing", r.label or f"MISSING {name}", now, end, order=5, **common)
        elif r.type == "cleanse":
            it = Item(key, "cleanse", "CLEANSE Target: Poisoned", now, end, order=6, target="preview", **common)
        elif r.type == "cast":
            it = Item(key, "flash", fmt_label(r.label, name, "Boss") if r.label else f"Boss: {name}", now, end,
                      order=4, **common)
        else:
            it = Item(key, "flash", fmt_label(r.text or r.label or "%e", name), now, end, order=20, **common)
        self.items[key] = it

    def _party_items(self, now: float) -> list[Item]:
        """One 'party' item per friendly roster member, with my HoTs/shields on them attached in meta."""
        out = []
        mine = {}
        for it in self.items.values():
            if it.kind == "bar" and it.target:
                mine.setdefault(it.target, []).append(it)
        for name, r in list(self.roster.items()):
            if not r["friendly"]:
                continue
            if name != self.me and now - r["seen"] > ROSTER_TTL:
                del self.roster[name]
                continue
            pct = (r["hp"] / r["max_hp"]) if r["max_hp"] else 1.0
            order = 100 + (0 if name == self.me else (1 if r["kind"] == "player" else 2))
            out.append(Item(f"party:{name}", "party", name, r["seen"], None, order=order, group="party",
                            meta={"hp": r["hp"], "max_hp": r["max_hp"], "pct": pct, "dead": r["dead"],
                                  "kind": r["kind"], "me": name == self.me,
                                  "effects": [(x.label.split(" · ")[0], x.stacks, x.remaining(now), x.icon)
                                              for x in mine.get(name, [])]}))
        return out

    def _cond_ok(self, it: Item) -> bool:
        c = it.cond
        if not c:
            return True
        ic = c.get("in_combat")
        if ic is True and not self.in_combat or ic is False and self.in_combat:
            return False
        if it.kind == "stacks":
            if c.get("stacks_below", -1) >= 0 and it.stacks >= c["stacks_below"]:
                return False
            if c.get("stacks_at_least", -1) >= 0 and it.stacks < c["stacks_at_least"]:
                return False
        return True
