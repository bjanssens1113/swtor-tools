"""Line sources for the overlay.

LogTailer   - follows the newest combat_*.txt in the SWTOR log folder (read-only, file only).
ReplaySource - replays a saved log at N x speed so the overlay can be tested without the game.

Both expose:  poll() -> list[str] of new raw lines (non-blocking)   and   now() -> seconds since midnight.
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from parser import LOG_ENCODING, time_to_seconds


def _line_seconds(line: str) -> Optional[float]:
    if len(line) > 13 and line[0] == "[" and line[13] == "]":
        try:
            return time_to_seconds(line[1:13])
        except ValueError:
            return None
    return None


class LogTailer:
    """Follow the newest log file. On first open, only the header lines (AreaEntered / DisciplineChanged)
    are emitted before skipping to the end, unless from_start=True. A newer file appearing later is
    picked up automatically and read from its beginning."""

    def __init__(self, log_dir, from_start: bool = False, rescan_every: float = 2.0):
        self.log_dir = Path(log_dir)
        self.from_start = from_start
        self.rescan_every = rescan_every
        self._fh = None
        self._path: Optional[Path] = None
        self._buf = ""
        self._last_scan = 0.0
        self._opened = 0

    @property
    def path(self) -> Optional[Path]:
        return self._path

    def newest(self) -> Optional[Path]:
        files = sorted(self.log_dir.glob("combat_*.txt"))
        return files[-1] if files else None

    def _open(self, path: Path) -> list[str]:
        if self._fh:
            self._fh.close()
        self._fh = open(path, "r", encoding=LOG_ENCODING, errors="replace", newline="")
        self._path = path
        self._buf = ""
        self._opened += 1
        head: list[str] = []
        if self._opened == 1 and not self.from_start:
            for _ in range(40):
                line = self._fh.readline()
                if not line:
                    break
                head.append(line)
                if "DisciplineChanged" in line:
                    break
            self._fh.seek(0, os.SEEK_END)
        return head

    @staticmethod
    def now() -> float:
        t = datetime.now()
        return t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6

    def poll(self) -> list[str]:
        out: list[str] = []
        t = time.monotonic()
        if self._fh is None or t - self._last_scan > self.rescan_every:
            self._last_scan = t
            newest = self.newest()
            if newest is not None and newest != self._path:
                out.extend(self._open(newest))
        if self._fh is None:
            return out
        chunk = self._fh.read()
        if chunk:
            self._buf += chunk
            *lines, self._buf = self._buf.split("\n")
            out.extend(ln for ln in lines if ln.strip())
        return out

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None


class ReplaySource:
    """Replay a saved log. Lines before skip_to (HH:MM:SS) are emitted immediately as history;
    later lines are released as simulated time passes at `speed` x real time."""

    def __init__(self, path, speed: float = 1.0, skip_to: Optional[str] = None):
        with open(path, encoding=LOG_ENCODING, errors="replace") as fh:
            self.lines = [ln.rstrip("\r\n") for ln in fh if ln.strip()]
        self.speed = speed
        self.i = 0
        first = next((s for s in (_line_seconds(ln) for ln in self.lines) if s is not None), 0.0)
        self.t0 = time_to_seconds(skip_to) if skip_to else first
        self._wall0 = time.monotonic()

    def now(self) -> float:
        return self.t0 + (time.monotonic() - self._wall0) * self.speed

    @property
    def done(self) -> bool:
        return self.i >= len(self.lines)

    def poll(self) -> list[str]:
        out: list[str] = []
        limit = self.now()
        while self.i < len(self.lines):
            s = _line_seconds(self.lines[self.i])
            if s is not None and s > limit:
                break
            out.append(self.lines[self.i])
            self.i += 1
        return out
