# SWTOR Tools — Handoff Doc

Carry this into a fresh Claude Code session on your Windows PC. It captures everything decided so far so the new session can start building immediately.

---

## 1. What we're building

Two **separate** helper tools for Star Wars: The Old Republic.

### Tool A — Mouseover macro
- **What:** Hover a unit, press one key → it clicks-to-target that unit and fires an ability. Behaves like a WoW mouseover cast (mainly for healing).
- **How:** SWTOR has **no macro system and no add-on API**, so this is an **input remapper**, not an add-on. It exploits one game behavior: left-clicking a unit targets it. The macro is `left-click at cursor → small delay → press ability key`.
- **Tech:** **AutoHotkey v2** (or the gaming-peripheral software — Logitech G Hub / Razer Synapse / Corsair iCUE — if that's preferred).
- **Effort:** An afternoon. The only real work is tuning the click→cast delay so it feels instant without misfiring.

### Tool B — "WeakAuras-lite" alert overlay
- **What:** A transparent, always-on-top window over the game that shows alerts/timers: procs, buff/debuff gained/lost, cooldown-usage tracking, fight timers.
- **How:** Tails SWTOR's **combat log file** on disk in near-real-time, parses events, runs them through alert rules, renders alerts. This is the *only* ToS-safe live data source in SWTOR — it's exactly how StarParse works.
- **Hard limit:** It can only react to what the combat log contains (ability activations, damage/heals, buff/debuff events for you and your group). It **cannot** see resource bars, true cooldown timers, or most enemy internal state. It's WeakAuras bounded by the log.
- **Tech (recommended):** **Python 3 + PyQt6** — frameless transparent always-on-top windows are well supported and iteration is fast. Alternative if you want a native feel: C# / WPF.
- **Effort:** Basic version a few days; polished trigger system a few weeks.

### Why two tools, not one
They are opposite kinds of software with opposite risk profiles:

| | Tool A (macro) | Tool B (overlay) |
|---|---|---|
| Direction | Sends input **into** the game | Reads data **out of** the game |
| ToS status | **Grey zone** (input automation) | **Green zone** (BioWare has said they don't ban for log parsing) |
| Runtime | Fires on keypress | Runs continuously |

Keep the input injector in its **own process** so the safe overlay is never bundled with automation code. An optional single launcher/control panel that starts both is fine — but the injection stays separate.

---

## 2. ToS guardrails — non-negotiable

The new session must respect these. They're the line between "tolerated tool" and "bannable":

1. **Never** read game memory, hook the process, or inject into the client.
2. **Macro:** strictly **1 keypress = 1 click + 1 ability**. No rotations, no chaining multiple abilities, no conditional logic, no auto-firing. Anything more crosses into botting.
3. **Overlay:** reads the combat log **file only**. No other game interaction.

---

## 3. Check StarParse first (before building Tool B from scratch)

**StarParse** (ixparse.com) already has a timers/alerts/trigger system built on the combat log. Before writing the overlay, evaluate whether configuring or extending StarParse covers 80% of what's wanted. Building custom only makes sense for alerts StarParse can't express. The parser work is useful either way.

---

## 4. Setup steps for the new session

1. **Create a new repo** — e.g. `swtor-tools` — as a local folder and on GitHub. Do **not** put this in `iron-log` (that's a fitness app; wrong project).
2. **Open it in Claude Code** on the PC.
3. **Enable combat logging in SWTOR** if not already on: `Preferences → Combat Logging → Enable Combat Logging to file`.
4. **Locate the logs.** Default location:
   `%USERPROFILE%\Documents\Star Wars - The Old Republic\CombatLogs\`
   Files are named `CombatLog_<date>_<time>.txt`.
5. **Generate a sample log** — play a fight with the content you care about (healing, procs, buffs/debuffs; an op or flashpoint is ideal) so there's real data to reverse-engineer the format from. **This is the single most valuable input** — the entire overlay hinges on the exact log format, and it should be built from real data, not a spec.
6. Copy a sample log into the repo (e.g. `overlay/samples/`).

---

## 5. Facts to give the new session (answer in chat)

- **OS:** Windows (confirm)
- **Mouse/keyboard brand** (Logitech / Razer / Corsair / none) → decides AHK vs. peripheral profile for the macro
- **Class/spec and content** (healer in ops? PvP?) → decides which alerts the overlay needs
- **Already running StarParse?** → decides what's left to build vs. just configure

---

## 6. Proposed repo structure

```
swtor-tools/
├── README.md
├── macro/
│   └── mouseover.ahk          # Tool A — AutoHotkey v2 mouseover macro
└── overlay/                   # Tool B — log-tailing alert overlay
    ├── samples/               # real CombatLog_*.txt files for testing
    ├── tailer.py              # follows the newest log file, yields new lines
    ├── parser.py              # combat log line → structured event
    ├── rules.py               # alert/trigger rules (the "aura" definitions)
    ├── overlay.py             # transparent always-on-top PyQt6 window
    └── main.py
```

---

## 7. Build order

| Phase | Deliverable | Notes |
|---|---|---|
| 0 | Repo + sample combat log | Blocks everything in Tool B |
| 1 | `mouseover.ahk` | Quick win; test click→cast delay live in game |
| 2 | `parser.py` + tests | Reverse-engineer log format from the sample. Confirm what buff/debuff/proc events actually appear. |
| 3 | `rules.py` | Trigger engine: "when effect X gained/lost → alert"; timers |
| 4 | `overlay.py` | Transparent click-through always-on-top window; positionable |
| 5 | (optional) Launcher | One control panel that starts both — injection still in its own process |

---

## 8. Ready-to-paste opening prompt for the new session

> I'm building two separate SWTOR helper tools in this repo, per the handoff doc `SWTOR_TOOLS_HANDOFF.md` — read it first. Tool A is an AutoHotkey v2 mouseover macro (strictly 1 keypress = 1 click + 1 ability, no automation beyond that). Tool B is a combat-log-tailing alert overlay in Python + PyQt6. Respect the ToS guardrails in section 2 exactly. Start with Phase 0: confirm the repo structure, then help me locate and copy a sample combat log into `overlay/samples/`. My setup: [OS / mouse brand / class+spec+content / StarParse yes-no].

---

## 9. Context on where this came from

This plan was worked out in a **remote cloud** Claude Code session that only had access to the `iron-log` fitness-app repo — so it could design but not run or test anything against the game. That's why the work moves to the PC: the new local session can read the real combat logs, run the AHK script, and render the overlay with SWTOR running.
