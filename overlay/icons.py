"""Ability / effect icon lookup.

overlay/data/parsely_icons.json maps ability and passive names (Empire and Republic) to Parsely icon slugs.
The PNGs themselves live in overlay/data/icons/<slug>.png (git-ignored, game assets; fetched with
overlay/tools/parsely_icons_zip.js + unpack_icons.py). Missing icon -> None, and tiles fall back to colour.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

DATA = Path(__file__).resolve().parent / "data"
ICON_DIR = DATA / "icons"
_MAP: Optional[dict] = None
_CACHE: dict = {}


def _map() -> dict:
    global _MAP
    if _MAP is None:
        try:
            _MAP = json.loads((DATA / "parsely_icons.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _MAP = {}
    return _MAP


def slug_for(name: str) -> Optional[str]:
    """'Burning (Incendiary Missile)' -> slug of Incendiary Missile; 'Kolto Probe' -> its slug."""
    if not name:
        return None
    m = _map()
    if name in m:
        return m[name]
    inner = re.match(r"^.*?\((.+)\)$", name)
    if inner and inner.group(1) in m:
        return m[inner.group(1)]
    base = re.sub(r"\s*\(.*\)$", "", name)
    return m.get(base)


def icon_path(name: str) -> Optional[Path]:
    slug = slug_for(name)
    if not slug:
        return None
    p = ICON_DIR / f"{slug}.png"
    return p if p.exists() else None


def pixmap(name: str):
    """QPixmap for the name, cached; None when no icon file exists. Imported lazily so tests stay Qt-free."""
    if name in _CACHE:
        return _CACHE[name]
    from PyQt6.QtGui import QPixmap
    p = icon_path(name)
    pm = QPixmap(str(p)) if p else None
    if pm is not None and pm.isNull():
        pm = None
    _CACHE[name] = pm
    return pm


def available() -> int:
    return len(list(ICON_DIR.glob("*.png"))) if ICON_DIR.exists() else 0
