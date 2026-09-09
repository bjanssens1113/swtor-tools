import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from parser import parse_line  # noqa: E402
from rules import CLEANSE_TTL, ROSTER_TTL, Engine, Profile, Rule  # noqa: E402

ME = "[@Jitzl#690022047680969|(0,0,0,0)|(400000/400000)]"
ALLY = "[@Whoopiecat#12345|(0,0,0,0)|(300000/400000)]"
ALLY_LOW = "[@Whoopiecat#12345|(0,0,0,0)|(50000/400000)]"
ENEMY_PLAYER = "[@Badguy#999|(0,0,0,0)|(350000/400000)]"
COMP = "[@Jitzl#690022047680969/Lana Beniko {77}:5|(0,0,0,0)|(100000/120000)]"
MOB = "[Sith Marauder Elite {1}:11|(1,1,1,0)|(50000/50000)]"
T = 10 * 3600


def line(t, src, tgt, ability, event, value=None):
    return f"[{t}] {src} {tgt} [{ability}] [{event}]" + (f" ({value})" if value else "")


def engine(cls="Operative", disc="Medicine"):
    e = Engine(Profile.load_all(), global_rules=Profile.load_global())
    e.feed(parse_line(line("10:00:00.000", ME, "[]", "", "AreaEntered {1}: Dummy {2}", "he3000")))
    e.feed(parse_line(line("10:00:00.000", ME, "[]", "", f"DisciplineChanged {{1}}: {cls} {{2}}/{disc} {{3}}")))
    return e


def party(e, now):
    return {i.label: i.meta for i in e.snapshot(now) if i.kind == "party"}


def test_party_roster_from_hp_in_log_lines():
    e = engine()
    assert list(party(e, T + 1)) == ["Jitzl"]
    e.feed(parse_line(line("10:00:01.000", ALLY, MOB, "Shiv {5}", "ApplyEffect {1}: Damage {2}", "1000 kinetic {3}")))
    p = party(e, T + 2)
    assert p["Whoopiecat"]["pct"] == 0.75 and p["Whoopiecat"]["kind"] == "player"
    e.feed(parse_line(line("10:00:03.000", MOB, ALLY_LOW, "Slash {5}", "ApplyEffect {1}: Damage {2}", "1000 kinetic {3}")))
    assert party(e, T + 4)["Whoopiecat"]["pct"] == 0.125


def test_enemy_players_are_not_friendly():
    e = engine()
    e.feed(parse_line(line("10:00:01.000", ME, ENEMY_PLAYER, "Shiv {5}", "ApplyEffect {1}: Damage {2}", "1000 kinetic {3}")))
    assert "Badguy" not in party(e, T + 2)
    # but someone I heal is
    e.feed(parse_line(line("10:00:02.000", ME, ALLY, "Kolto Probe {5}", "ApplyEffect {1}: Heal {2}", "500 ~500")))
    assert "Whoopiecat" in party(e, T + 3)


def test_companion_death_and_roster_expiry():
    e = engine()
    e.feed(parse_line(line("10:00:01.000", COMP, MOB, "Slash {5}", "ApplyEffect {1}: Damage {2}", "10 kinetic {3}")))
    assert party(e, T + 2)["Lana Beniko"]["kind"] == "companion"
    e.feed(parse_line(line("10:00:03.000", MOB, COMP, "", "Event {1}: Death {2}")))
    assert party(e, T + 4)["Lana Beniko"]["dead"] is True
    assert "Lana Beniko" not in party(e, T + 4 + ROSTER_TTL + 1)
    assert "Jitzl" in party(e, T + 4 + ROSTER_TTL + 1)          # I never expire


def test_my_hots_are_attached_to_party_rows():
    e = engine()
    e.feed(parse_line(line("10:00:00.500", ALLY, MOB, "Shiv {5}", "ApplyEffect {1}: Damage {2}", "1 kinetic {3}")))
    e.feed(parse_line(line("10:00:01.000", ME, ALLY, "Kolto Probe {5}", "ApplyEffect {1}: Kolto Probe {5}")))
    e.feed(parse_line(line("10:00:01.000", ME, ALLY, "Kolto Probe {5}", "ModifyCharges {1}: Kolto Probe {5}", "2 charges {9}")))
    eff = party(e, T + 2)["Whoopiecat"]["effects"]
    assert eff and eff[0][0] == "Kolto Probe" and eff[0][1] == 2


def test_cleanse_alert_for_tech_healer_and_ignore_list():
    e = engine()
    e.feed(parse_line(line("10:00:01.000", ALLY, MOB, "Shiv {5}", "ApplyEffect {1}: Damage {2}", "1 kinetic {3}")))
    e.feed(parse_line(line("10:00:02.000", MOB, ALLY, "Toxic Spit {5}", "ApplyEffect {1}: Poisoned (Physical) {6}")))
    cl = [i for i in e.snapshot(T + 3) if i.kind == "cleanse"]
    assert cl and cl[0].label == "CLEANSE Whoopiecat: Poisoned" and cl[0].sound == "beep"
    e.feed(parse_line(line("10:00:02.500", MOB, ALLY, "Bolt {5}", "ApplyEffect {1}: Slowed (Tech) {6}")))
    assert len([i for i in e.snapshot(T + 3) if i.kind == "cleanse"]) == 1       # ignored
    e.feed(parse_line(line("10:00:02.600", MOB, ALLY, "Mind Blast {5}", "ApplyEffect {1}: Crushed (Mental) {6}")))
    assert len([i for i in e.snapshot(T + 3) if i.kind == "cleanse"]) == 1       # wrong category for Toxin Scan
    e.feed(parse_line(line("10:00:04.000", MOB, ALLY, "Toxic Spit {5}", "RemoveEffect {1}: Poisoned (Physical) {6}")))
    assert not [i for i in e.snapshot(T + 5) if i.kind == "cleanse"]


def test_cleanse_expires_and_force_healer_types():
    e = engine("Sorcerer", "Corruption")
    assert e.profile.name == "Corruption Sorcerer"
    e.feed(parse_line(line("10:00:01.000", ALLY, MOB, "Shock {5}", "ApplyEffect {1}: Damage {2}", "1 energy {3}")))
    e.feed(parse_line(line("10:00:02.000", MOB, ALLY, "Mind Blast {5}", "ApplyEffect {1}: Crushed (Mental) {6}")))
    assert [i for i in e.snapshot(T + 3) if i.kind == "cleanse"]
    assert not [i for i in e.snapshot(T + 3 + CLEANSE_TTL) if i.kind == "cleanse"]
    e.feed(parse_line(line("10:00:05.000", MOB, ALLY, "Toxic Spit {5}", "ApplyEffect {1}: Poisoned (Physical) {6}")))
    assert not [i for i in e.snapshot(T + 6) if i.kind == "cleanse"]           # sorcs can't cleanse physical


def test_cleanse_ignores_debuffs_from_players():
    e = engine()
    e.feed(parse_line(line("10:00:01.000", ALLY, MOB, "Shiv {5}", "ApplyEffect {1}: Damage {2}", "1 kinetic {3}")))
    e.feed(parse_line(line("10:00:02.000", ENEMY_PLAYER, ALLY, "Dart {5}", "ApplyEffect {1}: Poisoned (Physical) {6}")))
    assert not [i for i in e.snapshot(T + 3) if i.kind == "cleanse"]
