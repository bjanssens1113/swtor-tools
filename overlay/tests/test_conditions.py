import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from parser import parse_line  # noqa: E402
from rules import Engine, Profile, Rule  # noqa: E402

ME = "[@Jitzl#690022047680969|(0,0,0,0)|(400000/400000)]"
TRASH = "[Trash Mob {1}:11|(1,1,1,0)|(50000/50000)]"
BOSS = "[Big Boss {2}:22|(1,1,1,0)|(9000000/9000000)]"
T = 10 * 3600


def line(t, src, tgt, ability, event, value=None):
    return f"[{t}] {src} {tgt} [{ability}] [{event}]" + (f" ({value})" if value else "")


def engine(rules=None, global_rules=None):
    if rules is None:
        e = Engine(Profile.load_all(), global_rules=global_rules if global_rules is not None else Profile.load_global())
    else:
        p = Profile("Test", "Operative", "Lethality", rules)
        e = Engine([p], global_rules=global_rules or [])
    e.feed(parse_line(line("10:00:00.000", ME, "[]", "", "AreaEntered {1}: Dummy {2}", "he3000")))
    e.feed(parse_line(line("10:00:00.000", ME, "[]", "", "DisciplineChanged {1}: Operative {2}/Lethality {3}")))
    return e


def enter_combat(e, t="10:00:05.000"):
    e.feed(parse_line(line(t, ME, "[=]", "", "Event {1}: EnterCombat {2}")))


def test_missing_stim_global_rule_in_combat_only():
    e = engine()
    assert not [i for i in e.snapshot(T + 1) if i.kind == "missing"]          # out of combat: quiet
    enter_combat(e)
    labels = {i.label for i in e.snapshot(T + 6) if i.kind == "missing"}
    assert labels == {"NO STIM"}                                              # class buffs are permanent: not tracked
    e.feed(parse_line(line("10:00:07.000", ME, "[=]", "Advanced Kyrprax Versatile Stim {9}",
                           "ApplyEffect {1}: Advanced Kyrprax Versatile Stim {9}")))
    assert not [i for i in e.snapshot(T + 8) if i.kind == "missing"]
    e.feed(parse_line(line("10:00:09.000", ME, "[=]", "Advanced Kyrprax Versatile Stim {9}",
                           "RemoveEffect {1}: Advanced Kyrprax Versatile Stim {9}")))
    assert "NO STIM" in {i.label for i in e.snapshot(T + 10) if i.kind == "missing"}


def test_area_entered_resets_active_buffs():
    e = engine()
    e.feed(parse_line(line("10:00:01.000", ME, "[=]", "Prototype Kyrprax Attack Stim {9}",
                           "ApplyEffect {1}: Prototype Kyrprax Attack Stim {9}")))
    e.feed(parse_line(line("10:00:02.000", ME, "[]", "", "AreaEntered {1}: Elsewhere {2}", "he3000")))
    enter_combat(e)
    assert "NO STIM" in {i.label for i in e.snapshot(T + 6) if i.kind == "missing"}


def test_in_combat_condition_on_self_buff():
    rules = [Rule(type="self", effect="Stim Boost", duration=15, in_combat=True)]
    e = engine(rules)
    e.feed(parse_line(line("10:00:01.000", ME, "[=]", "Stim Boost {5}", "ApplyEffect {1}: Stim Boost {5}")))
    assert not [i for i in e.snapshot(T + 2) if i.kind == "bar"]
    enter_combat(e)
    assert [i for i in e.snapshot(T + 6) if i.kind == "bar"]


def test_stacks_below_condition():
    rules = [Rule(type="stacks", effect="Tactical Advantage", stacks_below=2)]
    e = engine(rules)
    e.feed(parse_line(line("10:00:01.000", ME, "[=]", "Tactical Advantage {7}",
                           "ModifyCharges {1}: Tactical Advantage {7}", "3 charges {9}")))
    assert not [i for i in e.snapshot(T + 2) if i.kind == "stacks"]
    e.feed(parse_line(line("10:00:03.000", ME, "[=]", "Tactical Advantage {7}",
                           "ModifyCharges {1}: Tactical Advantage {7}", "1 charges {9}")))
    assert [i for i in e.snapshot(T + 4) if i.kind == "stacks"][0].stacks == 1


def test_boss_only_target_rule():
    rules = [Rule(type="target", effect="Corrosive Dart", duration=22, boss_only=True)]
    e = engine(rules)
    e.feed(parse_line(line("10:00:01.000", ME, TRASH, "Corrosive Dart {5}", "ApplyEffect {1}: Corrosive Dart {5}")))
    assert not [i for i in e.snapshot(T + 2) if i.kind == "bar"]
    e.feed(parse_line(line("10:00:01.000", ME, BOSS, "Corrosive Dart {5}", "ApplyEffect {1}: Corrosive Dart {5}")))
    assert [i for i in e.snapshot(T + 2) if i.kind == "bar"]


def test_regex_rule_matches_any_tier():
    rules = [Rule(type="self", effect=r"Kyrprax .* Adrenal$", regex=True, duration=15, label="Adrenal")]
    e = engine(rules)
    e.feed(parse_line(line("10:00:01.000", ME, "[=]", "Advanced Kyrprax Critical Adrenal {9}",
                           "ApplyEffect {1}: Advanced Kyrprax Critical Adrenal {9}")))
    assert [i for i in e.snapshot(T + 2) if i.kind == "bar" and i.label == "Adrenal"]


def test_missing_rule_regex_alternation_covers_both_factions():
    rules = [Rule(type="missing", effect="^(Coordination|Lucky Shots)$", regex=True, label="X")]
    e = engine(rules)
    enter_combat(e)
    assert [i for i in e.snapshot(T + 6) if i.kind == "missing"]
    e.feed(parse_line(line("10:00:07.000", ME, "[=]", "Lucky Shots {9}", "ApplyEffect {1}: Lucky Shots {9}")))
    assert not [i for i in e.snapshot(T + 8) if i.kind == "missing"]


def test_missing_rule_always_variant():
    rules = [Rule(type="missing", effect="Stealth", in_combat=False, label="NOT STEALTHED")]
    e = engine(rules)
    assert [i for i in e.snapshot(T + 1) if i.kind == "missing"]
    enter_combat(e)
    assert not [i for i in e.snapshot(T + 6) if i.kind == "missing"]
