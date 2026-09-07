# SWTOR combat log format (7.x, `<v7.0.0b>`)

Reverse-engineered from real logs in `overlay/samples/`. Update this as new event shapes show up.

## Encoding
The file is **Windows ANSI (cp1252)**, not UTF-8. Names like `Critic\xe1l M\xe1ss` (Criticál Máss) are single
bytes. 53 of the 557 logs on this PC fail UTF-8 decoding. `parser.LOG_ENCODING` is the one place this is set.

## Line shape
```
[HH:MM:SS.mmm] [SOURCE] [TARGET] [ABILITY {id}] [EVENT {id}: SUBTYPE {id}] (VALUE) <THREAT>
```
Every field is bracketed. `(VALUE)` and `<THREAT>` are optional. Time is local wall-clock with no date; the date comes from the filename.

## Entity fields (SOURCE / TARGET)
| Form | Meaning | Example |
|---|---|---|
| `@Name#id\|(x,y,z,facing)\|(hp/maxhp)` | Player | `@Jitzl#690022047680969\|(-0.18,24.89,4.01,179.59)\|(422744/422744)` |
| `@Owner#id/Name {npcId}:instId\|(pos)\|(hp)` | Companion (owned by player) | `@Jitzel#686771103607246/Aric Jorgan {3604169051078656}:15838674743017\|...` |
| `Name {npcId}:instId\|(pos)\|(hp)` | NPC | `Mutated Geonosian Reaver {4207255473881088}:15838664386389\|...` |
| `=` | Same as SOURCE (self-target) | `[=]` |
| empty | No target | `[]` |

`instId` distinguishes individual NPC spawns sharing an `npcId`.

## Ability field
`Name {id}`. Name can be empty (`[ {4196681264398336}]`) for hidden/internal effects.

## Events seen so far
| EVENT | SUBTYPE | Notes |
|---|---|---|
| `Event` | `AreaEntered` | First line of a file. Tail `(he3000) <v7.0.0b>` = server / log version |
| `Event` | `DisciplineChanged` | `Class {id}/Discipline {id}` |
| `Event` | `AbilityActivate` / `AbilityDeactivate` | Cast start / end. Ability in ABILITY field |
| `Event` | `EnterCombat` / `ExitCombat` | Fight boundaries — use for fight timers |
| `Event` | `TargetSet` / `TargetCleared` | Target changes |
| `Event` | `Death` | |
| `ApplyEffect` | `Damage` | `(1958 kinetic {id})`; `*` after the number = crit (`3148*`); may have `<threat>` |
| `ApplyEffect` | `Heal` | `(4845 ~0)` — number after `~` is *effective* heal (0 = full overheal) |
| `ApplyEffect` | `<buff/debuff name>` | Buff/debuff/proc **gained**. This is the WeakAuras trigger source |
| `RemoveEffect` | `<buff/debuff name>` | Buff/debuff/proc **lost** |
| `ModifyCharges` | `<effect name>` | Stack count changed; value is `(2 charges {id})` = new total (e.g. `Tactical Advantage`, `Supercharge`, `Kolto Shell`) |
| `ApplyEffect` | `Damage` (shielded) | `(100 energy {id} -shield {id} (54 absorbed {id}))` — nested parens when a shield absorbed part of the hit |
| `Spend` / `Restore` | `energy` (etc.) | Resource events — only for the logging player |

## Event counts, one Ossus session (Mercenary IO, 9 136 lines)
```
3216 ApplyEffect -> Damage        670 ApplyEffect -> Heal
 711 Event -> AbilityActivate     417 Event -> TargetSet
 357 Spend -> energy              280 ModifyCharges -> Surging Shots
  84 Event -> Death                42 Event -> EnterCombat / ExitCombat
  59 ApplyEffect/RemoveEffect -> Innovative Particle Accelerator   (a proc)
```

## Implications for the overlay
- Procs and buffs/debuffs **are** logged (`ApplyEffect`/`RemoveEffect` with the effect name) — the core "aura" trigger works.
- Stack counts are logged via `ModifyCharges`.
- Resource is logged for the player (`Spend`/`Restore energy`), so a resource readout *is* possible — better than the handoff assumed.
- Fight timers: anchor on `EnterCombat`, clear on `ExitCombat`.
- Cooldowns must be inferred from `AbilityActivate` + a known cooldown table; the log does not carry them.
