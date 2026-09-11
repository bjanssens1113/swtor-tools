import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from parser import parse_line  # noqa: E402
from rules import PREVIEW_SECONDS, Engine, Profile, Rule  # noqa: E402

ME = "[@Jitzl#690022047680969|(0,0,0,0)|(400000/400000)]"
BOSS = "[Big Boss {2}:22|(1,1,1,0)|(9000000/9000000)]"
TRASH = "[Trash Mob {1}:11|(1,1,1,0)|(50000/50000)]"
T = 10 * 3600


def line(t, src, tgt, ability, event, value=None):
    return f"[{t}] {src} {tgt} [{ability}] [{event}]" + (f" ({value})" if value else "")


def engine(rules, global_rules=None):
    p = Profile("Test", "Operative", "Lethality", rules)
    e = Engine([p], global_rules=global_rules or [])
    e.feed(parse_line(line("10:00:00.000", ME, "[]", "", "AreaEntered {1}: Dummy {2}", "he3000")))
    e.feed(parse_line(line("10:00:00.000", ME, "[]", "", "DisciplineChanged {1}: Operative {2}/Lethality {3}")))
    return e


def test_cast_rule_boss_only_by_default_and_regex():
    e = engine([Rule(type="cast", ability=".*", regex=True, label="%n: %e", duration=3)])
    e.feed(parse_line(line("10:00:01.000", TRASH, "[=]", "Slash {5}", "Event {1}: AbilityActivate {2}")))
    assert not [i for i in e.snapshot(T + 2) if i.kind == "flash"]
    e.feed(parse_line(line("10:00:02.000", BOSS, "[=]", "Terminate {5}", "Event {1}: AbilityActivate {2}")))
    fl = [i for i in e.snapshot(T + 3) if i.kind == "flash"]
    assert fl and fl[0].label == "Big Boss: Terminate" and fl[0].icon == "Terminate"
    assert not [i for i in e.snapshot(T + 6) if i.kind == "flash"]


def test_cast_rule_anymob():
    e = engine([Rule(type="cast", ability="Slash", boss_only=False)])
    e.feed(parse_line(line("10:00:01.000", TRASH, "[=]", "Slash {5}", "Event {1}: AbilityActivate {2}")))
    assert [i for i in e.snapshot(T + 2) if i.kind == "flash" and i.label == "Trash Mob: Slash"]


def test_cooldown_charges_recharge_one_at_a_time():
    e = engine([Rule(type="cooldown", ability="Exfiltrate", seconds=10, charges=2)])
    e.feed(parse_line(line("10:00:00.000", ME, "[=]", "Exfiltrate {6}", "Event {1}: AbilityActivate {2}")))
    cd = [i for i in e.snapshot(T + 1) if i.kind == "cooldown"][0]
    assert cd.stacks == 1 and abs(cd.remaining(T + 1) - 9) < 0.01
    e.feed(parse_line(line("10:00:02.000", ME, "[=]", "Exfiltrate {6}", "Event {1}: AbilityActivate {2}")))
    cd = [i for i in e.snapshot(T + 3) if i.kind == "cooldown"][0]
    assert cd.stacks == 0 and abs(cd.remaining(T + 3) - 7) < 0.01     # timer not reset by the second use
    cd = [i for i in e.snapshot(T + 11) if i.kind == "cooldown"][0]
    assert cd.stacks == 1 and abs(cd.remaining(T + 11) - 9) < 0.01    # one charge back, next one recharging
    assert [i for i in e.snapshot(T + 20.5) if i.kind == "flash" and "READY" in i.label]
    assert not [i for i in e.snapshot(T + 23) if i.kind in ("cooldown", "flash")]


def test_dynamic_labels():
    e = engine([Rule(type="target", effect="Corrosive Dart", duration=22, label="Dart on %n"),
                Rule(type="self", effect="Stim Boost", duration=15, label="%e %r")])
    e.feed(parse_line(line("10:00:01.000", ME, BOSS, "Corrosive Dart {5}", "ApplyEffect {1}: Corrosive Dart {5}")))
    e.feed(parse_line(line("10:00:01.000", ME, "[=]", "Stim Boost {5}", "ApplyEffect {1}: Stim Boost {5}")))
    labels = {i.label for i in e.snapshot(T + 2) if i.kind == "bar"}
    assert "Dart on Big Boss" in labels and "Stim Boost %r" in labels    # %r is resolved at draw time


def test_preview_items_expire():
    e = engine([])
    e.preview(Rule(type="stacks", effect="Tactical Advantage", max_stacks=3), T)
    e.preview(Rule(type="cooldown", ability="Shiv", seconds=6, charges=2), T)
    e.preview(Rule(type="cast", ability="Terminate"), T)
    kinds = sorted(i.kind for i in e.snapshot(T + 1))
    assert kinds == ["cooldown", "flash", "party", "stacks"]
    assert not [i for i in e.snapshot(T + PREVIEW_SECONDS + 0.1) if i.kind != "party"]


def test_global_cast_rule_is_off_by_default():
    e = Engine(Profile.load_all(), global_rules=Profile.load_global())
    assert any(r.type == "cast" and not r.enabled for r in e.global_rules)
