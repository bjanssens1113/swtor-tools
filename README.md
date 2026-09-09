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

- Runs as a **tray app** (blue square). The overlay appears while `swtor.exe` is running and hides when the game
  exits. Tray menu: enable, lock (click-through), **Settings…**, reload profiles, open profiles folder, quit.
  Double-click the tray icon for Settings.
- **Settings → General**: start with Windows (Startup-folder shortcut), show only in game, lock, follow
  discipline changes or pin a profile, overlay scale.
- **Settings → Rules**: pick any profile, enable/disable rules, edit durations / cooldowns / warn thresholds /
  labels / colors, add rules from a picker fed by your own logs, save. Saving a generated profile writes a
  hand-written copy into `overlay\profiles\` which then takes priority.
- Profiles **hot-reload**: edit any JSON in `overlay\profiles\` and the overlay picks it up within a second.
- Auto-detects your discipline from the log and loads the matching profile.
- Position, lock state and options live in `overlay\settings.json` (git-ignored).
- The game must be in **Fullscreen (Windowed)** mode. Exclusive fullscreen hides every overlay.

Test without the game by replaying a saved log:

```
.venv\Scripts\python.exe overlay\main.py --replay overlay\samples\combat_2025-02-08_09_22_00_862785.txt --skip-to 09:23:40 --speed 4
.venv\Scripts\python.exe overlay\main.py --headless --replay <log> --skip-to HH:MM:SS --speed 6   # text mode
```

Tests: `.venv\Scripts\python.exe -m pytest overlay\tests`

Regenerate the "what do I actually use" catalog from every log on this PC:
`.venv\Scripts\python.exe overlay\catalog.py` → `docs\CATALOG.md` + `overlay\catalog.json`.

## Profiles (what the overlay shows)
Every one of the 48 disciplines has a profile. Three tiers, best wins:

| Tier | Where | How it was made |
|---|---|---|
| Hand-written | `overlay/profiles/*.json` | Lethality + IO from Parsely #1 parses (`docs/PARSELY_*.md`); Medicine + Bodyguard from Brad's logs |
| Auto (mined) | `overlay/profiles/auto/*_(auto)` | `overlay/discover.py` mined every player in all 557 logs: 38 disciplines, real effect names, 75th-pct durations, 10th-pct re-use gaps as cooldowns, filtered through Parsely's ability list |
| Mirrored | `overlay/profiles/auto/*_(mirrored)` | `overlay/mirror.py` translated a profile to its Empire/Republic twin using Parsely name pairs (Tactical Advantage → Upper Hand …) |

Auto and mirrored profiles are **drafts**: prune rules you don't want and fix cooldowns in game. Copy one to
`overlay/profiles/` (drop the `_auto` flag, give it a name) once you've tuned it, and it becomes hand-written.

Reference material for tuning:
- `docs/DISCIPLINES.md` — per discipline: abilities with re-use gaps, self buffs and target effects with measured durations, stack effects. All from real logs.
- `docs/ABILITIES_ALL.md` — Parsely's full ability/passive/mod list for all 16 classes, Empire and Republic names (2 155 rows).
- `docs/CATALOG.md` — what *Brad's own* characters have used, with counts.

Regenerate after new logs: `python overlay/discover.py` then `python overlay/mirror.py`.

Rule types: `self` (buff on you → countdown bar), `target` (your effect on an enemy/ally → bar per target),
`stacks` (ModifyCharges → number, red when low), `proc` (big flash text), `cooldown` (bar after AbilityActivate,
then a READY flash), `missing` (alert while a buff is **not** on you — in combat by default). Built-in fight
timer from EnterCombat / ExitCombat. Effect names must match the log exactly; `docs/CATALOG.md` and
`docs/DISCIPLINES.md` list every name that has appeared in the logs.

**Conditions** (per rule, editable in the Conditions column): `combat` / `nocombat`, `stacks<N`, `stacks>=N`,
`boss` (target max HP ≥ 500 000), `regex` (effect is a regular expression, e.g. `Kyrprax .* Stim$`).

**Global rules** (`overlay/profiles/_global.json`) are added to every discipline, both factions. Ships with one
rule: missing stim (regex covers every tier). Class buffs are permanent once unlocked in Legacy, so they are not
tracked. Edit global rules in Settings → Rules (first entry in the profile list).

**Healer tools**: the `party` group lists everyone in your group with live HP bars (every log line carries the
actor's HP), blinking red below the group's Low HP %, DEAD greyed, and your own HoTs/shields on each member drawn
as small icons with stack counts. Companions show when solo (toggle per group). `cleanse` rules alert when an NPC
puts a debuff of a category you can cleanse on an ally — the log tags debuffs `(Physical)`, `(Tech)`,
`(Mental)`, `(Force)` — with an ignore list for slows/stuns. Medicine/Sawbones and Bodyguard/Combat Medic ship
with Physical+Tech, Corruption/Seer with Mental+Force.

**Layout groups**: every rule has a Group; each group is its own movable window with a style (`bars`, `icons`
with real ability art, `text`), grow direction, scale, combat-only and hidden flags. Make your own groups on the
Groups tab. Icons come from Parsely: run `overlay/tools/parsely_icons_zip.js` in a logged-in browser tab, then
`python overlay/tools/unpack_icons.py`. Per-rule `sound` (`beep` or a .wav) plays when the alert appears.

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
