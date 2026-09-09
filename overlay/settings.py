"""User settings for the overlay app (overlay/settings.json, git-ignored)."""
from __future__ import annotations

import json
from pathlib import Path

SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"
DEFAULTS = {
    "geometry": [60, 200, 340, 420],
    "locked": False,
    "show_only_in_game": True,     # hide the overlay while swtor.exe is not running
    "start_with_windows": False,
    "scale": 1.0,
    "auto_switch": True,           # follow DisciplineChanged in the log
    "forced_profile": "",          # profile name to pin when auto_switch is off
    "game_exe": "swtor.exe",
}


def load() -> dict:
    d = dict(DEFAULTS)
    try:
        d.update(json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return d


def save(d: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps(d, indent=1), encoding="utf-8")
