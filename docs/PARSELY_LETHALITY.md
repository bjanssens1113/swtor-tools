# Lethality Operative — what a top parse looks like (from Parsely)

Source: Parsely DPS leaderboard, Operative / Lethality, Live, 10M dummy, #1 entry on 2026-09-07
(Eleemosynary, 36 733 DPS, 4m 32s, parse `parsely.io/parser/view/1101769/0`). Timings are milliseconds
from the Effects tab. All effect names below are the exact strings that appear in the combat log, so they
can be pasted straight into `rules.py`.

## Debuffs to keep on the target (the core of Lethality)
| Effect (log name) | Duration seen | Uptime in top parse | Reapply cadence | Overlay alert |
|---|---|---|---|---|
| Corrosive Grenade | ~22.3 s | 97.8 % | every ~22 s | timer bar; warn at 3 s left / when dropped |
| Corrosive Dart | ~22.4 s | 95.8 % | every ~22 s | timer bar; warn at 3 s left / when dropped |
| Toxic Blast | ~10.0 s | 67.8 % | every ~15 s (cooldown-gated) | timer bar |

## Self buffs / procs to watch
| Effect (log name) | Type | Duration | Notes / alert idea |
|---|---|---|---|
| Tactical Advantage | stack buff (ModifyCharges) | rolling, 96.5 % uptime | show stack count; warn when 0 (Corrosive Assault / Lethal Strike need it) |
| Augmented Toxins | proc buff | ~6.1 s | 25 procs / 4.5 min; fired ~every 10-11 s; show remaining time |
| Fatality | proc buff | 1.3-5.6 s | 24 procs; short window, big alert "FATALITY" |
| Toxic Regulators | buff | ~6.0 s | appears right after Shield Probe ends |
| Stim Boost / Revitalizers | cooldown buff | 15.0 s | used every ~89 s; show cooldown-ready |
| Shield Probe | defensive | 10.1 s | used every ~30 s in the parse |
| Advanced Kyrprax Critical Adrenal | adrenal | 15.1 s | used at 4.5 s and 200 s (~195 s cooldown) |
| Advanced Kyrprax Medpac | medpac heal-over-time | 15.1 s | ~90 s cooldown |
| Evasion | defensive | 8.1 s | ~62 s cadence |
| Power Surge / Mastery Surge | relic procs | 6.0 s | 13 procs each, ~20 s ICD; nice-to-know only |
| Critical Tactics | passive | permanent | ignore |
| Agitated | debuff on self | permanent in combat | ignore |
| Tactical Overdrive / Tactical Superiority | opener cooldowns | 14.7 s / 10.1 s | cooldown-ready alerts |

## Ability cadence (Ability Usage tab, avg interval)
| Ability | Uses | Avg interval | Implied cooldown |
|---|---|---|---|
| Corrosive Assault | 82 | 5.2 s | filler, TA-gated |
| Shiv | 30 | 8.8 s | ~6 s cd (TA builder) |
| Lethal Strike | 25 | 11.0 s | ~10.5 s cd |
| Toxic Blast | 19 | 14.7 s | ~13-15 s cd |
| Toxic Haze | 18 | 14.8 s | ~13-15 s cd |
| Corrosive Grenade | 13 | 21.9 s | reapply at expiry |
| Corrosive Dart | 12 | 22.2 s | reapply at expiry |
| Distraction | 14 | 19.6 s | interrupt, off-GCD (used as a filler here) |
| Shield Probe | 9 | 32.0 s | 30 s cd |
| Stim Boost | 4 | 73.3 s | 90 s cd (used late) |
| Holotraverse | 6 | 38.3 s | movement |
| Cloaking Screen / Stealth | 3-4 | | reset tool |

## What this means for the overlay (Tool B)
1. **Three DoT timers** (Corrosive Grenade, Corrosive Dart, Toxic Blast) keyed on `ApplyEffect`/`RemoveEffect`
   with the target's instance id, so multi-target fights show one bar per enemy.
2. **Tactical Advantage stack counter** from `ModifyCharges`.
3. **Proc flashes**: Augmented Toxins (6 s bar), Fatality (big flash, short).
4. **Cooldown-ready reminders** inferred from `AbilityActivate` + known cooldown: Lethal Strike 10.5 s,
   Toxic Blast 15 s, Toxic Haze 15 s, Shield Probe 30 s, Stim Boost 90 s, adrenal 180 s.
5. **Fight timer** from `EnterCombat`/`ExitCombat`.

## Cross-check against Brad's own logs (`docs/CATALOG.md`, Jitzl / Jitzil Lethality)
Same effect names appear locally: Tactical Advantage, Augmented Toxins, Fatality, Corrosive Dart/Grenade,
Toxic Blast, Stim Boost, Revitalizers, Toxic Regulators, Shield Probe, Critical Tactics. So the rules built
from this table will fire on Brad's own logs without renaming anything.
