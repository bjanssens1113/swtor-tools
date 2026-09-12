"""Is the game running? Uses the Windows process list only (Toolhelp snapshot). Never touches the game process."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import os
import subprocess
import sys
from pathlib import Path

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)), ("th32ModuleID", w.DWORD),
        ("cntThreads", w.DWORD), ("th32ParentProcessID", w.DWORD), ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", w.DWORD), ("szExeFile", ctypes.c_wchar * 260),
    ]


def running_exes() -> set[str]:
    if sys.platform != "win32":
        return set()
    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        return set()
    out = set()
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = k32.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            out.add(pe.szExeFile.lower())
            ok = k32.Process32NextW(snap, ctypes.byref(pe))
    finally:
        k32.CloseHandle(snap)
    return out


def is_running(exe: str = "swtor.exe") -> bool:
    return exe.lower() in running_exes()


# ---- "start with Windows" via a shortcut in the user's Startup folder -------------------------------
STARTUP_DIR = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
SHORTCUT = STARTUP_DIR / "SWTOR Overlay.lnk"


def startup_enabled() -> bool:
    return SHORTCUT.exists()


def _make_shortcut(path: Path, target: Path, args: str, workdir: Path, description: str, icon: str = "") -> None:
    ps = (
        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{path}');"
        f"$s.TargetPath='{target}';$s.Arguments='{args}';$s.WorkingDirectory='{workdir}';"
        f"$s.Description='{description}';" + (f"$s.IconLocation='{icon}';" if icon else "") + "$s.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], check=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def set_startup(enabled: bool) -> None:
    if not enabled:
        if SHORTCUT.exists():
            SHORTCUT.unlink()
        return
    root = Path(__file__).resolve().parents[1]
    _make_shortcut(SHORTCUT, root / ".venv" / "Scripts" / "pythonw.exe", f'"{root / "overlay" / "main.py"}"',
                   root, "SWTOR combat-log overlay")


def make_desktop_shortcuts() -> list[Path]:
    """Desktop shortcuts for the overlay and the macro. Returns the paths written."""
    root = Path(__file__).resolve().parents[1]
    desktop = Path(os.environ.get("USERPROFILE", "~")).expanduser() / "Desktop"
    if not desktop.exists():
        desktop = Path(os.environ.get("USERPROFILE", "~")).expanduser() / "OneDrive" / "Desktop"
    out = []
    ov = desktop / "SWTOR Overlay.lnk"
    _make_shortcut(ov, root / ".venv" / "Scripts" / "pythonw.exe", f'"{root / "overlay" / "main.py"}"', root,
                   "SWTOR combat-log overlay (tray app)", "%SystemRoot%\\System32\\shell32.dll,165")
    out.append(ov)
    ahk = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "AutoHotkey" / "v2" / "AutoHotkey64.exe"
    if ahk.exists():
        mac = desktop / "SWTOR Mouseover Macro.lnk"
        _make_shortcut(mac, ahk, f'"{root / "macro" / "mouseover.ahk"}"', root, "SWTOR mouseover macro (AutoHotkey)")
        out.append(mac)
    return out
