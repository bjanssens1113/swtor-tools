import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import settings as settings_mod  # noqa: E402
from parser import parse_line  # noqa: E402
from rules import DEFAULT_GROUPS, Engine, Profile, Rule  # noqa: E402

ME = "[@Jitzl#690022047680969|(0,0,0,0)|(400000/400000)]"
MOB = "[Training Dummy {123}:999|(1,1,1,0)|(1000000/1000000)]"


def _engine():
    e = Engine(Profile.load_all())
    e.feed(parse_line(f"[10:00:00.000] {ME} [] [] [DisciplineChanged {{1}}: Operative {{2}}/Lethality {{3}}]"))
    return e


def test_items_carry_default_groups():
    e = _engine()
    e.feed(parse_line(f"[10:00:01.000] {ME} {MOB} [Corrosive Dart {{5}}] [ApplyEffect {{1}}: Corrosive Dart {{5}}]"))
    e.feed(parse_line(f"[10:00:01.000] {ME} [=] [Fatality {{8}}] [ApplyEffect {{1}}: Fatality {{8}}]"))
    e.feed(parse_line(f"[10:00:01.000] {ME} [=] [Tactical Advantage {{7}}] "
                      f"[ModifyCharges {{1}}: Tactical Advantage {{7}}] (2 charges {{9}})"))
    e.feed(parse_line(f"[10:00:01.000] {ME} {MOB} [Lethal Strike {{6}}] [Event {{1}}: AbilityActivate {{2}}]"))
    e.feed(parse_line(f"[10:00:01.000] {ME} [=] [] [Event {{1}}: EnterCombat {{2}}]"))
    groups = {i.kind: i.group for i in e.snapshot(10 * 3600 + 2)}
    assert groups == {"bar": "target", "flash": "alerts", "stacks": "stacks", "cooldown": "cooldowns", "fight": "timer"}


def test_custom_group_and_sound_flow_through():
    e = _engine()
    p = e.profile
    custom = Profile(p.name, p.cls, p.discipline,
                     [Rule(**{**r.__dict__, "group": "mine", "sound": "beep"}) for r in p.rules])
    e.reload([custom])
    e.feed(parse_line(f"[10:00:01.000] {ME} [=] [Fatality {{8}}] [ApplyEffect {{1}}: Fatality {{8}}]"))
    it = [i for i in e.snapshot(10 * 3600 + 2) if i.kind == "flash"][0]
    assert it.group == "mine" and it.sound == "beep"
    assert "mine" in e.group_names() and e.group_names()[: len(DEFAULT_GROUPS)] == DEFAULT_GROUPS


def test_group_cfg_defaults_and_layout(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_mod, "SETTINGS_PATH", tmp_path / "s.json")
    s = settings_mod.load()
    cd = settings_mod.group_cfg(s, "cooldowns")
    assert cd["style"] == "bars" and cd["geometry"] == settings_mod.DEFAULT_GROUP_LAYOUT["cooldowns"]
    extra = settings_mod.group_cfg(s, "mine")
    assert extra["geometry"][2] == 300 and "mine" in s["groups"]
    settings_mod.save(s)
    assert settings_mod.load()["groups"]["cooldowns"]["style"] == "bars"
