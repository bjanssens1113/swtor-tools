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
    "groups": {},                  # per layout group: geometry, locked, style, orientation, scale, combat_only, hidden
}

GROUP_DEFAULTS = {
    "style": "bars",          # bars | icons | text
    "orientation": "down",    # down | up | right (grow direction)
    "scale": 1.0,
    "combat_only": False,
    "hidden": False,
    "locked": False,
    "icon_size": 48,
    "columns": 6,             # icons: tiles per row before wrapping
}
# starting positions for the default groups, stacked down the left edge
DEFAULT_GROUP_LAYOUT = {
    "timer":     [60, 120, 160, 40],
    "stacks":    [60, 170, 300, 60],
    "alerts":    [500, 300, 420, 80],
    "buffs":     [60, 240, 300, 140],
    "target":    [60, 390, 300, 140],
    "cooldowns": [60, 540, 300, 200],
}


def group_cfg(d: dict, name: str) -> dict:
    """Merged config for one group; creates the entry with defaults if missing (does not save)."""
    groups = d.setdefault("groups", {})
    g = groups.setdefault(name, {})
    for k, v in GROUP_DEFAULTS.items():
        g.setdefault(k, v)
    if "geometry" not in g:
        n = len(groups)
        g["geometry"] = list(DEFAULT_GROUP_LAYOUT.get(name, [400 + 40 * n, 200 + 40 * n, 300, 140]))
    return g


def load() -> dict:
    d = dict(DEFAULTS)
    try:
        d.update(json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return d


def save(d: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps(d, indent=1), encoding="utf-8")
