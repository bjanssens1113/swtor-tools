# swtor-tools

Two **separate** helper tools for Star Wars: The Old Republic. See `docs/SWTOR_TOOLS_HANDOFF.md` for the full design and ToS guardrails.

| Tool | Folder | What it does | Direction | ToS |
|---|---|---|---|---|
| A — Mouseover macro | `macro/` | One keypress: click the unit under the cursor, then press one ability key. AutoHotkey v2. | Sends input **into** the game | Grey zone (input remap) |
| B — Alert overlay | `overlay/` | Tails the combat log file, parses events, shows timers / stacks / proc alerts in a transparent always-on-top window. Python + PyQt6. | Reads data **out of** the game | Green zone (log parsing) |

They never share a process. The overlay contains no input-injection code.

## Guardrails (non-negotiable)
1. Never read game memory, hook the process, or inject into the client.
2. Macro: strictly **1 keypress = 1 click + 1 ability**. No rotations, chaining, conditionals, or auto-fire.
3. Overlay: reads the combat log **file only**.

## Quick start

### Tool A — mouseover macro
AutoHotkey v2 is installed at `%LOCALAPPDATA%\Programs\AutoHotkey\v2`. Double-click `macro\mouseover.ahk`
(a green **H** appears in the tray). Edit the bindings block at the bottom of the file: left side is the key you
press, right side is the SWTOR keybind of the ability. Tune `CLICK_TO_CAST_DELAY_MS` (start at 60).

### Tool B — overlay
Python 3.13 + PyQt6 live in `.venv` (created with `uv`). From the repo root:

```
.venv\Scripts\python.exe overlay\main.py
```

- Auto-detects your discipline from the log and loads the matching profile in `overlay\profiles\`.
- Tray icon (blue square) → **Unlock** to drag the window, **Lock** to make it click-through, **Quit**.
- Position and lock state are saved in `overlay\settings.json` (git-ignored).

Test without the game by replaying a saved log:

```
.venv\Scripts\python.exe overlay\main.py --replay overlay\samples\combat_2025-02-08_09_22_00_862785.txt --skip-to 09:23:40 --speed 4
.venv\Scripts\python.exe overlay\main.py --headless --replay <log> --skip-to HH:MM:SS --speed 6   # text mode
```

Tests: `.venv\Scripts\python.exe -m pytest overlay\tests`

Regenerate the "what do I actually use" catalog from every log on this PC:
`.venv\Scripts\python.exe overlay\catalog.py` → `docs\CATALOG.md` + `overlay\catalog.json`.

## Profiles (what the overlay shows)
| Profile | Source of timings |
|---|---|
| Lethality Operative | Parsely #1 parse, `docs/PARSELY_LETHALITY.md` |
| Innovative Ordnance Mercenary | Parsely #1 parse, `docs/PARSELY_IO.md` |
| Medicine Operative | Brad's own logs (`docs/CATALOG.md`); cooldowns approximate |
| Bodyguard Mercenary | Brad's own logs; cooldowns approximate |

Rule types: `self` (buff on you → countdown bar), `target` (your effect on an enemy/ally → bar per target),
`stacks` (ModifyCharges → number, red when low), `proc` (big flash text), `cooldown` (bar after AbilityActivate,
then a READY flash). Built-in fight timer from EnterCombat / ExitCombat. Effect names must match the log exactly;
`docs/CATALOG.md` lists every name that has appeared in your logs.

## Layout
```
swtor-tools/
├── README.md
├── docs/
│   ├── SWTOR_TOOLS_HANDOFF.md   # original design/handoff doc
│   ├── LOG_FORMAT.md            # combat log format, reverse-engineered from real logs
│   ├── CATALOG.md               # generated: every ability/effect per character+discipline, with counts
│   ├── PARSELY_LETHALITY.md     # top-parse timings scraped from Parsely
│   ├── PARSELY_IO.md
│   └── PARSELY_ABILITIES.md     # Operative + Mercenary ability lists from Parsely's database
├── macro/
│   └── mouseover.ahk            # Tool A
└── overlay/                     # Tool B
    ├── samples/                 # real combat logs for parser tests / replay
    ├── profiles/*.json          # per-discipline rule sets
    ├── parser.py                # log line -> Event (cp1252 text, regex)
    ├── tailer.py                # LogTailer (follow newest file) + ReplaySource
    ├── rules.py                 # Engine: events -> Items, profile auto-select
    ├── overlay.py               # transparent PyQt6 window + tray menu
    ├── catalog.py               # mines all logs into docs/CATALOG.md
    ├── main.py                  # entry point (live / replay / headless)
    └── tests/
```

## Where the logs are on this PC
Documents is redirected to OneDrive, so the log folder is:

`C:\Users\bjans\OneDrive\Documents\Star Wars - The Old Republic\CombatLogs\`

Files are named `combat_YYYY-MM-DD_HH_MM_SS_ffffff.txt` and are cp1252-encoded (see `docs/LOG_FORMAT.md`).
