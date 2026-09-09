"""Extract parsely_icons.zip (from the Downloads folder by default) into overlay/data/icons/."""
from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "overlay" / "data" / "icons"


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get("USERPROFILE", "~")).expanduser() / "Downloads" / "parsely_icons.zip"
    if not src.exists():
        raise SystemExit(f"not found: {src}")
    DEST.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(src) as z:
        for info in z.infolist():
            if info.filename.lower().endswith(".png") and "/" not in info.filename:
                (DEST / info.filename).write_bytes(z.read(info))
                n += 1
    print(f"{n} icons -> {DEST}")


if __name__ == "__main__":
    main()
