# swtor-tools

Two **separate** helper tools for Star Wars: The Old Republic. See `docs/SWTOR_TOOLS_HANDOFF.md` for the full design and ToS guardrails.

| Tool | Folder | What it does | Direction | ToS |
|---|---|---|---|---|
| A — Mouseover macro | `macro/` | One keypress: click the unit under the cursor, then press one ability key. AutoHotkey v2. | Sends input **into** the game | Grey zone (input remap) |
| B — Alert overlay | `overlay/` | Tails the combat log file, parses events, shows alerts/timers in a transparent always-on-top window. Python + PyQt6. | Reads data **out of** the game | Green zone (log parsing) |

They never share a process. The overlay contains no input-injection code.

## Guardrails (non-negotiable)
1. Never read game memory, hook the process, or inject into the client.
2. Macro: strictly **1 keypress = 1 click + 1 ability**. No rotations, chaining, conditionals, or auto-fire.
3. Overlay: reads the combat log **file only**.

## Layout
```
swtor-tools/
├── README.md
├── docs/
│   ├── SWTOR_TOOLS_HANDOFF.md   # original design/handoff doc
│   └── LOG_FORMAT.md            # combat log format, reverse-engineered from real logs
├── macro/
│   └── mouseover.ahk            # Tool A
└── overlay/                     # Tool B
    ├── samples/                 # real combat logs for parser tests
    ├── tailer.py                # (phase 4) follows newest log file
    ├── parser.py                # (phase 2) log line -> event
    ├── rules.py                 # (phase 3) trigger/alert rules
    ├── overlay.py               # (phase 4) transparent PyQt6 window
    └── main.py
```

## Where the logs are on this PC
Documents is redirected to OneDrive, so the log folder is:

`C:\Users\bjans\OneDrive\Documents\Star Wars - The Old Republic\CombatLogs\`

Files are named `combat_YYYY-MM-DD_HH_MM_SS_ffffff.txt` (not `CombatLog_*` as the handoff guessed).

## Prerequisites
- **AutoHotkey v2** for Tool A: https://www.autohotkey.com/ (installer, pick v2)
- **Python 3.12+** for Tool B: https://www.python.org/downloads/ (tick "Add to PATH"), then `pip install PyQt6`
