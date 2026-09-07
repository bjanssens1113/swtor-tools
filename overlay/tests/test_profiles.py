import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from rules import Profile  # noqa: E402

VALID_TYPES = {"self", "target", "stacks", "proc", "cooldown"}


def test_every_profile_loads_and_is_well_formed():
    profiles = Profile.load_all()
    assert len(profiles) >= 4
    for p in profiles:
        assert p.cls and p.discipline and p.rules, p.name
        for r in p.rules:
            assert r.type in VALID_TYPES, (p.name, r)
            if r.type == "cooldown":
                assert r.ability and r.seconds > 0, (p.name, r)
            else:
                assert r.effect, (p.name, r)


def test_hand_written_profile_wins_over_auto():
    profiles = Profile.load_all()
    first = {}
    for p in profiles:
        first.setdefault((p.cls, p.discipline), p)
    assert first[("Operative", "Lethality")].name == "Lethality Operative"
    assert first[("Mercenary", "Innovative Ordnance")].name == "Innovative Ordnance Mercenary"


def test_no_duplicate_discipline_within_a_tier():
    hand = [p for p in Profile.load_all() if "(auto)" not in p.name and "(mirrored)" not in p.name]
    keys = [(p.cls, p.discipline) for p in hand]
    assert len(keys) == len(set(keys))
