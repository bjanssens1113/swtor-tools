import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import icons  # noqa: E402


def test_slug_lookup_direct_and_parenthesised():
    assert icons.slug_for("Rifle Shot") == "rifleshot"
    assert icons.slug_for("Kolto Probe") == icons.slug_for("Slow-release Medpac")  # mirror pair share an icon
    assert icons.slug_for("Burning (Incendiary Missile)") == icons.slug_for("Incendiary Missile")
    assert icons.slug_for("Not A Real Thing") is None
    assert icons.slug_for("") is None


def test_icon_path_absent_is_none(tmp_path, monkeypatch):
    monkeypatch.setattr(icons, "ICON_DIR", tmp_path)
    assert icons.icon_path("Rifle Shot") is None
    (tmp_path / "rifleshot.png").write_bytes(b"x")
    assert icons.icon_path("Rifle Shot") == tmp_path / "rifleshot.png"
