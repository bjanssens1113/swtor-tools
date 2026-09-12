import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import gamewatch  # noqa: E402
import settings as settings_mod  # noqa: E402
from parser import parse_line  # noqa: E402
from rules import Engine, Profile, Rule  # noqa: E402

ME = "[@Jitzl#690022047680969|(0,0,0,0)|(400000/400000)]"


def test_settings_defaults_merge(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_mod, "SETTINGS_PATH", tmp_path / "s.json")
    d = settings_mod.load()
    assert d["show_only_in_game"] is True and d["scale"] == 1.0
    d["scale"] = 1.5
    settings_mod.save(d)
    assert json.loads((tmp_path / "s.json").read_text())["scale"] == 1.5
    assert settings_mod.load()["configure"] is False
    # old files with the pre-configure 'locked' flag migrate: unlocked used to mean editing
    (tmp_path / "s.json").write_text(json.dumps({"locked": False}))
    assert settings_mod.load()["configure"] is True and "locked" not in settings_mod.load()


def test_running_exes_lists_this_python():
    exes = gamewatch.running_exes()
    assert any(e.startswith("python") for e in exes)
    assert not gamewatch.is_running("definitely-not-a-process.exe")


def test_disabled_rule_is_ignored_and_reload_keeps_discipline():
    profiles = Profile.load_all()
    e = Engine(profiles)
    e.feed(parse_line(f"[10:00:00.000] {ME} [] [] [DisciplineChanged {{1}}: Operative {{2}}/Lethality {{3}}]"))
    assert e.profile.name == "Lethality Operative"
    # disable the Fatality proc rule in a modified copy of the profile and hot-reload
    mod = Profile(e.profile.name, e.profile.cls, e.profile.discipline,
                  [Rule(**{**r.__dict__, "enabled": r.effect != "Fatality"}) for r in e.profile.rules])
    e.reload([mod] + [p for p in profiles if p is not e.profile])
    assert e.profile is mod and e.discipline == "Operative/Lethality"
    e.feed(parse_line(f"[10:00:01.000] {ME} [=] [Fatality {{8}}] [ApplyEffect {{1}}: Fatality {{8}}]"))
    assert not [i for i in e.snapshot(10 * 3600 + 2) if i.kind == "flash"]
    e.feed(parse_line(f"[10:00:01.000] {ME} [=] [Augmented Toxins {{9}}] [ApplyEffect {{1}}: Augmented Toxins {{9}}]"))
    assert [i for i in e.snapshot(10 * 3600 + 2) if i.kind == "bar"]


def test_reload_with_forced_profile():
    e = Engine(Profile.load_all())
    e.reload(Profile.load_all(), "Medicine Operative")
    assert e.profile.name == "Medicine Operative"
