import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import quick_add  # noqa: E402
from rules import append_rule_to_file, item_stem  # noqa: E402


def test_item_stem():
    assert item_stem("tgt:Corrosive Dart:12345") == "tgt:Corrosive Dart"
    assert item_stem("cd:Shiv:ready") == "cd:Shiv"
    assert item_stem("cd:Shiv") == "cd:Shiv"
    assert item_stem("cl:Poisoned (Physical):Whoopiecat") == "cl:Poisoned (Physical)"
    assert item_stem("cast:99:Terminate") == "cast:Terminate"
    assert item_stem("preview:cd:Shiv") == "cd:Shiv"
    assert item_stem("preview:tgt:Corrosive Dart") == "tgt:Corrosive Dart"
    assert item_stem("stk:Tactical Advantage") == "stk:Tactical Advantage"


def test_append_rule_hand_and_auto(tmp_path):
    hand = tmp_path / "x.json"
    hand.write_text(json.dumps({"name": "X", "match": {"class": "Operative", "discipline": "Lethality"}, "rules": []}))
    out = append_rule_to_file(hand, {"type": "cooldown", "ability": "Shiv", "seconds": 6}, tmp_path)
    assert out == hand and json.loads(hand.read_text())["rules"][0]["ability"] == "Shiv"
    auto = tmp_path / "auto_x.json"
    auto.write_text(json.dumps({"name": "Y (auto)", "_auto": True,
                                "match": {"class": "Sorcerer", "discipline": "Lightning"}, "rules": [{"type": "self", "effect": "A"}]}))
    out = append_rule_to_file(auto, {"type": "self", "effect": "B"}, tmp_path)
    assert out == tmp_path / "sorcerer_lightning.json"
    doc = json.loads(out.read_text())
    assert doc["name"] == "Y" and "_auto" not in doc and [r["effect"] for r in doc["rules"]] == ["A", "B"]
    out2 = append_rule_to_file(auto, {"type": "self", "effect": "C"}, tmp_path)   # second add goes to the hand copy
    assert [r["effect"] for r in json.loads(out2.read_text())["rules"]] == ["A", "B", "C"]


def test_candidates_cover_log_data_and_parsely_both_factions():
    c = quick_add.candidates("Operative", "Medicine")
    names = {x["name"] for x in c}
    assert "Kolto Probe" in names and "Surgical Probe" in names
    kinds = {x["kind"] for x in c}
    assert {"ability", "buff", "stacks"} <= kinds
    rep = quick_add.candidates("Scoundrel", "Sawbones")
    rep_names = {x["name"] for x in rep}
    assert "Slow-release Medpac" in rep_names and "Kolto Probe" not in rep_names
