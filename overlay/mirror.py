"""Translate profiles to their faction-mirror discipline using Parsely's Empire/Republic name pairs.

SWTOR disciplines come in mirrored pairs with identical mechanics and different names
(Lethality Operative == Ruffian Scoundrel, Tactical Advantage == Upper Hand ...). Any profile we have for one side
can be converted to the other by renaming. Priority for a discipline, highest first:
  1. hand-written profile in overlay/profiles/
  2. mirror of a hand-written profile          -> overlay/profiles/auto/<slug>.json  (_source: mirrored-hand)
  3. auto profile mined from logs (discover.py) -> overlay/profiles/auto/<slug>.json
  4. mirror of an auto profile                  -> overlay/profiles/auto/<slug>.json  (_source: mirrored-auto)
Run after discover.py:  python overlay/mirror.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "overlay" / "profiles"
AUTO = PROFILES / "auto"
CLASS_MIRROR = {"Operative": "Scoundrel", "Mercenary": "Commando", "Sorcerer": "Sage", "Assassin": "Shadow",
                "Juggernaut": "Guardian", "Marauder": "Sentinel", "Powertech": "Vanguard", "Sniper": "Gunslinger"}
CLASS_MIRROR.update({v: k for k, v in CLASS_MIRROR.items()})


def build_maps():
    """Returns (name_map[class] -> {name: mirror_name}, disc_map[(class, disc)] -> (mirror_class, mirror_disc))."""
    data = json.loads((ROOT / "overlay" / "data" / "parsely_abilities.json").read_text(encoding="utf-8"))
    name_map: dict[str, dict[str, str]] = {}
    disc_map: dict[tuple[str, str], tuple[str, str]] = {}
    # parsely_abilities.json is normalized to Empire-first: rows are [level, empire, republic] and section
    # headers read "EmpireDisc / RepublicDisc Skills" on both factions' pages.
    for cls, sections in data.items():
        emp_cls = cls if cls in ("Operative", "Mercenary", "Sorcerer", "Assassin", "Juggernaut", "Marauder",
                                 "Powertech", "Sniper") else CLASS_MIRROR[cls]
        rep_cls = CLASS_MIRROR[emp_cls]
        fwd = name_map.setdefault(emp_cls, {})
        back = name_map.setdefault(rep_cls, {})
        for sec, rows in sections.items():
            m = re.match(r"^(.*?) / (.*?) (Skills|Passives|Mods)$", sec)
            if m:
                disc_map[(emp_cls, m.group(1))] = (rep_cls, m.group(2))
                disc_map[(rep_cls, m.group(2))] = (emp_cls, m.group(1))
            for _, emp, rep in rows:
                if emp and rep:
                    fwd.setdefault(emp, rep)
                    back.setdefault(rep, emp)
    return name_map, disc_map


def translate(profile: dict, name_map: dict, disc_map: dict) -> dict | None:
    cls, disc = profile["match"]["class"], profile["match"]["discipline"]
    if (cls, disc) not in disc_map:
        return None
    mcls, mdisc = disc_map[(cls, disc)]
    nm = name_map.get(cls, {})
    unmapped = []

    def tr(name: str) -> str:
        if name in nm:
            return nm[name]
        # "Burning (Incendiary Missile)" -> translate the inner ability name
        m = re.match(r"^(.*?) \((.*)\)$", name)
        if m and m.group(2) in nm:
            return f"{m.group(1)} ({nm[m.group(2)]})"
        unmapped.append(name)
        return name

    rules = []
    for r in profile["rules"]:
        r2 = dict(r)
        if r2.get("effect"):
            r2["effect"] = tr(r2["effect"])
        if r2.get("ability"):
            r2["ability"] = tr(r2["ability"])
        rules.append(r2)
    kind = "mirrored-auto" if profile.get("_auto") else "mirrored-hand"
    return {"name": f"{mdisc} {mcls} (mirrored)", "match": {"class": mcls, "discipline": mdisc}, "_auto": True,
            "_mirrored_from": profile["name"], "_kind": kind,
            "_source": f"{kind}: translated from '{profile['name']}' via Parsely Empire/Republic name pairs. "
                       + (f"Unmapped names kept as-is: {sorted(set(unmapped))}. " if unmapped else "")
                       + "Verify effect names against docs/DISCIPLINES.md or a fresh log.",
            "rules": rules}


def slug(cls: str, disc: str) -> str:
    return f"{cls}_{disc}".lower().replace(" ", "_")


def main():
    name_map, disc_map = build_maps()
    hand = {(p["match"]["class"], p["match"]["discipline"]): p
            for p in (json.loads(f.read_text(encoding="utf-8")) for f in PROFILES.glob("*.json"))}
    auto = {}
    for f in AUTO.glob("*.json"):
        p = json.loads(f.read_text(encoding="utf-8"))
        if not p.get("_mirrored_from"):
            auto[(p["match"]["class"], p["match"]["discipline"])] = p
    for f in AUTO.glob("*.json"):  # drop previous mirrored outputs
        if json.loads(f.read_text(encoding="utf-8")).get("_mirrored_from"):
            f.unlink()
    written = []
    done = set()
    for key, src in list(hand.items()) + list(auto.items()):   # hand first, so mirrored-hand claims a slot first
        if not src.get("rules"):
            continue
        out = translate(src, name_map, disc_map)
        if out is None:
            continue
        tkey = (out["match"]["class"], out["match"]["discipline"])
        if tkey in hand or tkey in done:
            continue                                   # hand-written wins; first mirror wins
        if tkey in auto and out["_kind"] == "mirrored-auto":
            continue                                   # mined-from-logs beats mirrored-auto
        done.add(tkey)
        path = AUTO / f"{slug(*tkey)}.json"
        path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        written.append((tkey, out["_kind"], src["name"]))
    for tkey, kind, src in sorted(written):
        print(f"{tkey[0]}/{tkey[1]:22s} <- {kind:14s} {src}")
    covered = set(hand) | set(auto) | {w[0] for w in written}
    all_disc = set(disc_map)
    print(f"\n{len(covered)} / {len(all_disc)} disciplines have a profile; missing: {sorted(all_disc - covered)}")


if __name__ == "__main__":
    main()
