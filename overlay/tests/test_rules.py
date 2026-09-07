import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from parser import parse_line  # noqa: E402
from rules import Engine, Profile  # noqa: E402

ME = "[@Jitzl#690022047680969|(0,0,0,0)|(400000/400000)]"
MOB = "[Training Dummy {123}:999|(1,1,1,0)|(1000000/1000000)]"


def line(t, src, tgt, ability, event, value=None):
    s = f"[{t}] {src} {tgt} [{ability}] [{event}]"
    return s + (f" ({value})" if value else "")


def engine():
    e = Engine(Profile.load_all())
    e.feed(parse_line(line("10:00:00.000", ME, "[]", "", "AreaEntered {1}: Dummy {2}", "he3000")))
    e.feed(parse_line(line("10:00:00.000", ME, "[]", "",
                           "DisciplineChanged {1}: Operative {2}/Lethality {3}")))
    return e


def test_profile_autoselect():
    e = engine()
    assert e.me == "Jitzl" and e.profile.name == "Lethality Operative"


def test_target_debuff_bar_and_removal():
    e = engine()
    e.feed(parse_line(line("10:00:01.000", ME, MOB, "Corrosive Dart {5}", "ApplyEffect {1}: Corrosive Dart {5}")))
    items = e.snapshot(10 * 3600 + 5)
    bar = next(i for i in items if i.kind == "bar")
    assert bar.label.startswith("Corrosive Dart") and "Training Dummy" in bar.label
    assert abs(bar.remaining(10 * 3600 + 5) - 18.0) < 0.01 and not bar.warn(10 * 3600 + 5)
    assert bar.warn(10 * 3600 + 21)          # 2 s left, warn_at 3
    e.feed(parse_line(line("10:00:20.000", ME, MOB, "Corrosive Dart {5}", "RemoveEffect {1}: Corrosive Dart {5}")))
    assert not [i for i in e.snapshot(10 * 3600 + 20) if i.kind == "bar"]


def test_target_death_clears_its_bars():
    e = engine()
    e.feed(parse_line(line("10:00:01.000", ME, MOB, "Corrosive Dart {5}", "ApplyEffect {1}: Corrosive Dart {5}")))
    e.feed(parse_line(line("10:00:02.000", ME, MOB, "", "Event {1}: Death {2}")))
    assert not [i for i in e.snapshot(10 * 3600 + 2) if i.kind == "bar"]


def test_stacks_from_modify_charges_and_warn():
    e = engine()
    e.feed(parse_line(line("10:00:01.000", ME, "[=]", "Tactical Advantage {7}",
                           "ModifyCharges {1}: Tactical Advantage {7}", "2 charges {9}")))
    st = next(i for i in e.snapshot(10 * 3600 + 1) if i.kind == "stacks")
    assert st.stacks == 2 and not st.warn(0)
    e.feed(parse_line(line("10:00:02.000", ME, "[=]", "Tactical Advantage {7}",
                           "RemoveEffect {1}: Tactical Advantage {7}")))
    st = next(i for i in e.snapshot(10 * 3600 + 2) if i.kind == "stacks")
    assert st.stacks == 0 and st.warn(0)


def test_proc_flash_expires():
    e = engine()
    e.feed(parse_line(line("10:00:01.000", ME, "[=]", "Fatality {8}", "ApplyEffect {1}: Fatality {8}")))
    assert [i for i in e.snapshot(10 * 3600 + 3) if i.kind == "flash" and i.label == "FATALITY"]
    assert not [i for i in e.snapshot(10 * 3600 + 7) if i.kind == "flash"]


def test_cooldown_then_ready_flash():
    e = engine()
    e.feed(parse_line(line("10:00:00.000", ME, MOB, "Lethal Strike {6}", "Event {1}: AbilityActivate {2}")))
    t = 10 * 3600
    cd = next(i for i in e.snapshot(t + 5) if i.kind == "cooldown")
    assert abs(cd.remaining(t + 5) - 5.5) < 0.01
    ready = [i for i in e.snapshot(t + 11) if i.kind == "flash"]
    assert ready and "READY" in ready[0].label
    assert not [i for i in e.snapshot(t + 14) if i.kind in ("flash", "cooldown")]


def test_fight_timer():
    e = engine()
    e.feed(parse_line(line("10:00:00.000", ME, "[=]", "", "Event {1}: EnterCombat {2}")))
    assert [i for i in e.snapshot(10 * 3600 + 3) if i.kind == "fight"]
    e.feed(parse_line(line("10:00:30.000", ME, "[=]", "", "Event {1}: ExitCombat {2}")))
    assert not [i for i in e.snapshot(10 * 3600 + 31) if i.kind == "fight"]


def test_respec_switches_profile():
    e = engine()
    e.feed(parse_line(line("10:05:00.000", ME, "[]", "", "DisciplineChanged {1}: Operative {2}/Medicine {3}")))
    assert e.profile.name == "Medicine Operative"
