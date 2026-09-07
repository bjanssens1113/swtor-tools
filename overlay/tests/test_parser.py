import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from parser import parse_file, parse_line  # noqa: E402

SAMPLES = pathlib.Path(__file__).resolve().parents[1] / "samples"


def test_damage_crit_with_threat():
    ev = parse_line(
        "[09:23:43.497] [@Jitzel#686771103607246|(747.44,25.94,-10.06,29.98)|(139319/139319)] "
        "[Mutated Geonosian Trooper {4207251178913792}:15838664386303|(747.84,18.77,-9.71,95.09)|(22912/33925)] "
        "[Death from Above {814201245270016}] [ApplyEffect {836045448945477}: Damage {836045448945501}] "
        "(3148* kinetic {836045448940873}) <3148.0>"
    )
    assert ev.source.kind == "player" and ev.source.name == "Jitzel" and ev.source.id == "686771103607246"
    assert ev.target.kind == "npc" and ev.target.name == "Mutated Geonosian Trooper"
    assert ev.target.instance == "15838664386303"
    assert ev.target.hp == 22912 and ev.target.max_hp == 33925
    assert ev.ability.name == "Death from Above" and ev.ability.id == "814201245270016"
    assert ev.type == "ApplyEffect" and ev.effect.name == "Damage"
    assert ev.value.amount == 3148 and ev.value.crit and ev.value.kind == "kinetic"
    assert ev.threat == 3148.0


def test_heal_effective_and_companion_source():
    ev = parse_line(
        "[09:24:13.012] [@Jitzel#686771103607246/Aric Jorgan {3604169051078656}:15838674915557|(705.23,68.70,-13.10,131.39)|(121134/121134)] "
        "[@Jitzel#686771103607246|(698.90,73.91,-15.34,133.07)|(136465/139319)] [Kolto Shell {4238449821351936}] "
        "[ApplyEffect {836045448945477}: Heal {836045448945500}] (5548 ~5549) <1109.0>"
    )
    assert ev.source.kind == "companion" and ev.source.name == "Aric Jorgan" and ev.source.owner == "Jitzel"
    assert ev.target.kind == "player" and ev.target.name == "Jitzel"
    assert ev.effect.name == "Heal" and ev.value.amount == 5548 and ev.value.effective == 5549
    assert not ev.value.crit


def test_self_target_buff():
    ev = parse_line(
        "[13:00:36.313] [@Jitzl#690022047680969|(0.26,-30.53,15.54,-1.81)|(422744/422744)] [=] "
        "[Advanced Kyrprax Critical Adrenal {4258842326073344}] "
        "[ApplyEffect {836045448945477}: Advanced Kyrprax Critical Adrenal {4258842326073344}]"
    )
    assert ev.is_self_target and ev.target.name == "Jitzl"
    assert ev.type == "ApplyEffect" and ev.effect.name == "Advanced Kyrprax Critical Adrenal"
    assert ev.value is None and ev.threat is None
    assert ev.seconds == 13 * 3600 + 36.313


def test_area_entered_and_discipline():
    a = parse_line(
        "[12:59:09.121] [@Jitzl#690022047680969|(-0.18,24.89,4.01,179.59)|(422744/422744)] [] [] "
        "[AreaEntered {836045448953664}: D5-Mantis {137438988857}] (he3000) <v7.0.0b>"
    )
    assert a.type == "AreaEntered" and a.extra["area"].name == "D5-Mantis"
    assert a.extra["server"] == "he3000" and a.extra["tag"] == "v7.0.0b"
    assert a.target is None and a.ability is None
    d = parse_line(
        "[12:59:09.121] [@Jitzl#690022047680969|(-0.18,24.89,4.01,179.59)|(422744/422744)] [] [] "
        "[DisciplineChanged {836045448953665}: Operative {16140905232405801950}/Lethality {2031339142381593}]"
    )
    assert d.extra["class"].name == "Operative" and d.extra["discipline"].name == "Lethality"


def test_empty_ability_name():
    ev = parse_line(
        "[09:22:45.679] [@Jitzel#686771103607246/Aric Jorgan {3604169051078656}:15838674743017|(1125.60,171.90,-27.92,0.00)|(121134/121134)] "
        "[=] [ {4196681264398336}] [RemoveEffect {836045448945478}: Coordination {4196681264398637}]"
    )
    assert ev.ability.name == "" and ev.ability.id == "4196681264398336"
    assert ev.type == "RemoveEffect" and ev.effect.name == "Coordination"


def test_whole_samples_parse_every_line():
    files = sorted(SAMPLES.glob("*.txt"))
    assert files, "no sample logs"
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            n_lines = sum(1 for line in fh if line.strip())
        n_events = sum(1 for _ in parse_file(f))
        assert n_events == n_lines, f"{f.name}: parsed {n_events} of {n_lines} lines"
