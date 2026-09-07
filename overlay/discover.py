"""Discover what every discipline does, from every player that ever appeared in the logs.

Group members' abilities, buffs, debuffs and stacks are all logged, so 557 logs of ops/flashpoints cover far
more disciplines than Brad has played himself. For each class/discipline this measures:
  - abilities activated (count, median re-use interval, MIN interval = cooldown lower bound)
  - self buffs (count, median duration)
  - effects applied to other units (count, median duration)
  - stack effects (ModifyCharges)
and writes overlay/data/disciplines.json + docs/DISCIPLINES.md, then drafts a profile per discipline into
overlay/profiles/auto/ (hand-written profiles in overlay/profiles/ always win).

Usage: python overlay/discover.py [LOG_DIR]
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parser import parse_file  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = (
    Path(os.environ.get("USERPROFILE", "~")).expanduser()
    / "OneDrive" / "Documents" / "Star Wars - The Old Republic" / "CombatLogs"
)
SKIP_EFFECTS = {"Damage", "Heal", "Sprint", "Stealth", "Safe Login Immunity", "In Conversation", "Major Experience Boost",
                "Speed Boosted", "Grant Vehicle", "Looting", "Using", "Guard", "MSM J-37 Jetpack", "Rocket Boost",
                "Recuperate", "Carbonite Chamber", "Unshakable", "Mounted", "Agitated", "Unnatural Might",
                "Coordination", "Hunter's Boon", "Mark of Power", "Protected", "Invigorated", "Power Surge",
                "Mastery Surge", "Critical Surge", "Endurance Surge", "Accuracy Surge", "Alacrity Surge"}
SKIP_ABILITY_RE = re.compile(r"\.\.\.$|^(Using|Looting|Collecting|Slicing|Scanning|Accessing|Open Box|Grant Vehicle|"
                             r"Unlock|Redirecting|Activating|Give Gift|Emergency Fleet Pass|Quick Travel|Repair|"
                             r"Speed Boost|Rocket Boost|MSM J-37 Jetpack|Recuperate|Stealth|Sprint|Escape|Seethe|"
                             r"Channel Hatred|Recharge and Reload|Recharge Cells|Recuperation)")
GENERIC_DEBUFFS = re.compile(r"^(Slowed|Stunned|Assailable|Susceptible|Marked|Knockdown|Immobilized|Armor Reduced|"
                             r"Burning \(Physical\)|Bleeding \(Physical\)|Poisoned \(Physical\)|Thrown|Head Trauma|"
                             r"Trauma|Vulnerable|Weakened|Unsteady|Shocked|Rooted|Snared|Taunted|Ravaged|"
                             r"Overwhelmed|Exposed)")


def pct(vals, q):
    vals = sorted(vals)
    if not vals:
        return 0.0
    return vals[min(len(vals) - 1, int(q * len(vals)))]


def discover(log_dir: Path):
    D = defaultdict(lambda: {"abilities": Counter(), "ability_gaps": defaultdict(list),
                             "self": Counter(), "self_dur": defaultdict(list),
                             "target": Counter(), "target_dur": defaultdict(list),
                             "stacks": Counter(), "stack_max": Counter(), "players": set(), "logs": 0})
    for path in sorted(log_dir.glob("combat_*.txt")):
        disc_of: dict[str, str] = {}
        seen_disc_in_file = set()
        active: dict = {}
        last_use: dict = {}
        for ev in parse_file(path):
            src, tgt = ev.source, ev.target
            if ev.type == "DisciplineChanged" and src and src.kind == "player":
                d = f"{ev.extra['class'].name}/{ev.extra['discipline'].name}"
                disc_of[src.name] = d
                if (src.name, d) not in seen_disc_in_file:
                    seen_disc_in_file.add((src.name, d))
                    D[d]["players"].add(src.name)
                    D[d]["logs"] += 1
                continue
            if not (src and src.kind == "player" and src.name in disc_of):
                continue
            d = disc_of[src.name]
            rec = D[d]
            eff = ev.effect.name if ev.effect else ""
            abil = ev.ability.name if ev.ability else ""
            if ev.type == "Event" and eff == "AbilityActivate" and abil and not SKIP_ABILITY_RE.search(abil):
                rec["abilities"][abil] += 1
                k = (src.name, abil)
                if k in last_use:
                    gap = ev.seconds - last_use[k]
                    if 0.5 < gap < 600:
                        rec["ability_gaps"][abil].append(gap)
                last_use[k] = ev.seconds
            elif ev.type == "ApplyEffect" and eff and eff not in SKIP_EFFECTS and tgt is not None:
                key = (src.name, eff, tgt.kind, tgt.name, tgt.instance)
                active[key] = ev.seconds
                if tgt.kind == "player" and tgt.name == src.name:
                    rec["self"][eff] += 1
                elif not GENERIC_DEBUFFS.match(eff):
                    rec["target"][eff] += 1
            elif ev.type == "RemoveEffect" and eff and tgt is not None:
                key = (src.name, eff, tgt.kind, tgt.name, tgt.instance)
                if key in active:
                    dur = ev.seconds - active.pop(key)
                    if 0.3 < dur < 600:
                        if tgt.kind == "player" and tgt.name == src.name:
                            rec["self_dur"][eff].append(dur)
                        else:
                            rec["target_dur"][eff].append(dur)
            elif ev.type == "ModifyCharges" and eff and ev.value is not None:
                rec["stacks"][eff] += 1
                rec["stack_max"][eff] = max(rec["stack_max"][eff], ev.value.amount)
    return D


def summarize(D):
    out = {}
    for d, rec in D.items():
        if rec["logs"] < 2:
            continue
        cls, disc = d.split("/")
        abilities = []
        for name, n in rec["abilities"].most_common():
            gaps = rec["ability_gaps"][name]
            abilities.append({"name": name, "uses": n,
                              "min_gap": round(min(gaps), 1) if gaps else None,
                              "p10_gap": round(pct(gaps, 0.10), 1) if gaps else None,
                              "median_gap": round(statistics.median(gaps), 1) if gaps else None})
        selfb = [{"name": k, "count": n, "median_s": round(statistics.median(rec["self_dur"][k]), 1) if rec["self_dur"][k] else None,
                  "p75_s": round(pct(rec["self_dur"][k], 0.75), 1) if rec["self_dur"][k] else None}
                 for k, n in rec["self"].most_common()]
        target = [{"name": k, "count": n, "median_s": round(statistics.median(rec["target_dur"][k]), 1) if rec["target_dur"][k] else None,
                   "p75_s": round(pct(rec["target_dur"][k], 0.75), 1) if rec["target_dur"][k] else None}
                  for k, n in rec["target"].most_common()]
        stacks = [{"name": k, "count": n, "max_seen": rec["stack_max"][k]} for k, n in rec["stacks"].most_common()]
        out[d] = {"class": cls, "discipline": disc, "logs": rec["logs"], "players": len(rec["players"]),
                  "abilities": abilities, "self_buffs": selfb, "target_effects": target, "stacks": stacks}
    return dict(sorted(out.items()))


JUNK_RE = re.compile(r"\(Physical\)|Droid|Manta|Scyk|Watchman|Planting|Bomb|Device|Mount|Speeder|Vehicle|Walker|"
                     r"Rejuvenating Kolto|Enduring Bastion|Throwing|Explosion|Rescue|Emersion|Krall|Kyrprax|Medpac|"
                     r"Seethe|Channel|Adrenal|Stim$|Boost$")


def load_parsely_names() -> dict:
    """{class: set(all ability/passive/mod names)} from the Parsely scrape, if present. Used as an allowlist."""
    p = ROOT / "overlay" / "data" / "parsely_abilities.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for cls, sections in data.items():
        names = set()
        for rows in sections.values():
            for row in rows:
                names.update(n for n in row[1:] if n)
        out[cls] = names
    return out


def draft_profile(d: dict, allow: dict, min_count: int = 8) -> dict:
    """Heuristic rules. Everything here is a starting point to prune/tune in game."""
    rules = []
    known = allow.get(d["class"], set())
    mirror = {"Operative": "Scoundrel", "Scoundrel": "Operative", "Mercenary": "Commando", "Commando": "Mercenary",
              "Sorcerer": "Sage", "Sage": "Sorcerer", "Assassin": "Shadow", "Shadow": "Assassin",
              "Juggernaut": "Guardian", "Guardian": "Juggernaut", "Marauder": "Sentinel", "Sentinel": "Marauder",
              "Powertech": "Vanguard", "Vanguard": "Powertech", "Sniper": "Gunslinger", "Gunslinger": "Sniper"}
    known = known | allow.get(mirror.get(d["class"], ""), set())

    def ok(name: str, count: int, strong: int = 150) -> bool:
        if JUNK_RE.search(name):
            return False
        base = re.sub(r"\s*\(.*\)$", "", name)
        if known and (name in known or base in known):
            return True
        return not known or count >= strong

    for s in d["stacks"]:
        if s["count"] >= min_count and ok(s["name"], s["count"], 40):
            rules.append({"type": "stacks", "effect": s["name"], "max_stacks": s["max_seen"]})
    for t in d["target_effects"]:
        if t["count"] >= min_count and t["p75_s"] and 3 <= t["p75_s"] <= 60 and ok(t["name"], t["count"], 60):
            rules.append({"type": "target", "effect": t["name"], "duration": t["p75_s"], "warn_at": 2})
    stack_names = {s["name"] for s in d["stacks"]}
    for s in d["self_buffs"]:
        if s["name"] in stack_names or s["count"] < min_count or not s["median_s"] or not ok(s["name"], s["count"]):
            continue
        if 1.0 <= s["median_s"] <= 3.5 and s["count"] >= 3 * min_count:
            rules.append({"type": "proc", "effect": s["name"], "duration": s["median_s"]})
        elif 3.5 < s["median_s"] <= 60:
            rules.append({"type": "self", "effect": s["name"], "duration": s["median_s"]})
    for a in d["abilities"]:
        if not (a["uses"] >= min_count and a["p10_gap"] and 6 <= a["p10_gap"] <= 300):
            continue
        if known and a["name"] not in known:
            continue
        if JUNK_RE.search(a["name"]):
            continue
        rules.append({"type": "cooldown", "ability": a["name"], "seconds": a["p10_gap"]})
    return {"name": f"{d['discipline']} {d['class']} (auto)",
            "match": {"class": d["class"], "discipline": d["discipline"]},
            "_auto": True,
            "_source": f"drafted by overlay/discover.py from {d['logs']} log sessions / {d['players']} players; "
                       "durations = 75th percentile of Apply->Remove, cooldowns = 10th percentile re-use gap. TUNE IN GAME.",
            "rules": rules}


def write_md(summary: dict, out: Path):
    L = ["# Every discipline seen in the logs — abilities, buffs, debuffs, stacks", "",
         "Generated by `overlay/discover.py` from all combat logs on this PC, using every player in every group. "
         "Names are exact log strings. `gap` = seconds between re-uses by the same player (10th percentile ≈ cooldown). "
         "Durations are seconds from ApplyEffect to RemoveEffect (median / 75th percentile).", ""]
    for d, s in summary.items():
        L += [f"## {d}  ({s['logs']} sessions, {s['players']} players)", ""]
        L += ["**Abilities** (uses · p10 gap · median gap)", ""]
        L.append(", ".join(f"{a['name']} ({a['uses']}·{a['p10_gap']}·{a['median_gap']})" for a in s["abilities"][:30]))
        L.append("")
        if s["stacks"]:
            L += ["**Stacks:** " + ", ".join(f"{x['name']} (max {x['max_seen']})" for x in s["stacks"][:12]), ""]
        if s["self_buffs"]:
            L += ["**Self buffs** (count · median s · p75 s)", "",
                  ", ".join(f"{x['name']} ({x['count']}·{x['median_s']}·{x['p75_s']})" for x in s["self_buffs"][:30]), ""]
        if s["target_effects"]:
            L += ["**On targets** (count · median s · p75 s)", "",
                  ", ".join(f"{x['name']} ({x['count']}·{x['median_s']}·{x['p75_s']})" for x in s["target_effects"][:30]), ""]
    out.write_text("\n".join(L), encoding="utf-8")


def main():
    log_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    summary = summarize(discover(log_dir))
    data_dir = ROOT / "overlay" / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "disciplines.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    write_md(summary, ROOT / "docs" / "DISCIPLINES.md")
    auto = ROOT / "overlay" / "profiles" / "auto"
    auto.mkdir(exist_ok=True)
    for old in auto.glob("*.json"):
        old.unlink()
    allow = load_parsely_names()
    for d, s in summary.items():
        prof = draft_profile(s, allow)
        if not prof["rules"]:
            continue  # too little data to say anything useful
        slug = d.lower().replace("/", "_").replace(" ", "_")
        (auto / f"{slug}.json").write_text(json.dumps(prof, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(summary)} disciplines -> docs/DISCIPLINES.md, overlay/data/disciplines.json, {len(summary)} auto profiles")


if __name__ == "__main__":
    main()
