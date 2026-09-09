"""Every module must at least compile and import (GUI modules included) so a typo can't hide until the tray runs."""
import importlib
import pathlib
import py_compile
import sys

OVERLAY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OVERLAY))


def test_all_modules_compile():
    for f in OVERLAY.glob("*.py"):
        py_compile.compile(str(f), doraise=True)


def test_gui_modules_import():
    for name in ("settings", "gamewatch", "rules", "tailer", "parser", "overlay", "app", "config_window"):
        importlib.import_module(name)
