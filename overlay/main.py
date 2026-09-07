"""SWTOR alert overlay — Tool B. Reads the combat log file; nothing else.

  python overlay/main.py                              # tail the newest live log
  python overlay/main.py --replay overlay/samples/X.txt --speed 4 --skip-to 09:23:40
  python overlay/main.py --headless --replay ...      # text mode, no window (for testing)
  python overlay/main.py --profile "Lethality Operative"   # force a profile
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parser import parse_line  # noqa: E402
from rules import Engine, Profile  # noqa: E402
from tailer import LogTailer, ReplaySource  # noqa: E402

DEFAULT_LOG_DIR = (
    Path(os.environ.get("USERPROFILE", "~")).expanduser()
    / "OneDrive" / "Documents" / "Star Wars - The Old Republic" / "CombatLogs"
)


def build_source(a):
    if a.replay:
        return ReplaySource(a.replay, speed=a.speed, skip_to=a.skip_to)
    return LogTailer(a.log_dir, from_start=a.from_start)


def run_headless(engine: Engine, source, seconds: float):
    """Print a snapshot once per second. Used for tests and for checking rules without the game."""
    t_end = time.monotonic() + seconds
    last_print = 0.0
    while time.monotonic() < t_end:
        for line in source.poll():
            ev = parse_line(line)
            if ev:
                engine.feed(ev)
        if time.monotonic() - last_print >= 1.0:
            last_print = time.monotonic()
            now = source.now()
            items = engine.snapshot(now)
            hh, mm, ss = int(now // 3600), int(now % 3600 // 60), now % 60
            head = f"[{hh:02d}:{mm:02d}:{ss:04.1f}] {engine.profile.name if engine.profile else engine.discipline}"
            print(head)
            for it in items:
                rem = it.remaining(now)
                extra = f" {rem:5.1f}s" if rem is not None else ""
                stk = f" x{it.stacks}" if it.kind == "stacks" or it.stacks else ""
                warn = " !!" if it.warn(now) else ""
                print(f"    {it.kind:8s} {it.label}{stk}{extra}{warn}")
        if getattr(source, "done", False):
            break
        time.sleep(0.05)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    ap.add_argument("--from-start", action="store_true", help="read the current log from its beginning")
    ap.add_argument("--profile", help="force a profile by name instead of auto-detecting from DisciplineChanged")
    ap.add_argument("--replay", help="replay a saved log file instead of tailing the live one")
    ap.add_argument("--speed", type=float, default=1.0, help="replay speed multiplier")
    ap.add_argument("--skip-to", help="replay: start the clock at HH:MM:SS (earlier lines are applied instantly)")
    ap.add_argument("--headless", action="store_true", help="print snapshots to stdout instead of drawing a window")
    ap.add_argument("--duration", type=float, default=30.0, help="headless: seconds to run")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # names can carry odd bytes; never crash on print

    engine = Engine(Profile.load_all(), forced_profile=a.profile)
    source = build_source(a)
    if a.headless:
        run_headless(engine, source, a.duration)
        return
    from PyQt6.QtWidgets import QApplication  # imported late so headless mode needs no Qt
    from overlay import OverlayWindow
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    win = OverlayWindow(engine, source)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
