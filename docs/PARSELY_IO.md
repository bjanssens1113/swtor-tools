# Innovative Ordnance Mercenary — what a top parse looks like (from Parsely)

Source: Parsely DPS leaderboard, Mercenary / Innovative Ordnance, Live, 10M dummy, #1 entry on 2026-09-07
(Tammy Bundleballs, 35 344 DPS, 4m 43s, parse `parsely.io/parser/view/1136061/0`). Effect names are the
exact log strings.

## Debuffs to keep on the target
| Effect (log name) | Duration | Uptime | Source ability | Overlay alert |
|---|---|---|---|---|
| Burning (Incendiary Missile) | ~13.9 s | 98.8 % | Incendiary Missile | timer bar, warn at 2 s |
| Bleeding | ~13.9 s | 97.3 % | Serrated Shot | timer bar, warn at 2 s |
| Burning (Thermal Detonator) | ~11.1 s | 77.0 % | Thermal Detonator (after 2.4 s fuse) | timer bar |
| Thermal Detonator | ~2.4 s | fuse | Thermal Detonator | small fuse indicator |
| Supercharged Burn | ~8.0 s | 52.4 % | Supercharged Gas window | timer bar |
| Electro Net | ~9.6 s | 13.5 % | Electro Net (~90 s cd) | timer bar |
| Burning | ~12-14 s | 95.7 % | generic burn from Mag Shot/IPA | informational |

## Self buffs / procs
| Effect (log name) | Type | Duration | Notes |
|---|---|---|---|
| Surging Shots | stack buff (ModifyCharges) | rolling, 96 % uptime | show stacks |
| Supercharge | stack buff (ModifyCharges) | builds to 10 | show stacks; Supercharged Gas when full |
| Supercharged Gas | buff | ~16-30 s | active window bar |
| Innovative Particle Accelerator | proc | 5.7 s (or 1.3 s when consumed fast) | "MAG SHOT" flash, 40 procs / 4.7 min |
| Volatile Warhead | proc | 1.5-11 s | free Missile Blast / Thermal Detonator |
| Relentless Ordnance | buff | ~20 s | maintained by rotation |
| Concentrated Fire | buff | short | Unload/Power Shot window |
| Speed to Burn | buff | 1.4 s | ignore |
| Prototype Kyrprax Attack Adrenal | adrenal | 15 s | ~180 s cd |
| Vent Heat | cooldown | 2.8 s | used at 47 s and 174 s |
| Advanced Targeting / Power Barrier | passives | permanent | ignore |

## Overlay rules derived
1. Target timers: Burning (Incendiary Missile) 14 s, Bleeding 14 s, Burning (Thermal Detonator) 11 s,
   Supercharged Burn 8 s, Electro Net 9.5 s.
2. Stack counters: Surging Shots, Supercharge.
3. Proc flash: Innovative Particle Accelerator (6 s), Volatile Warhead.
4. Cooldowns from AbilityActivate: Thermal Detonator 15 s, Serrated Shot 15 s, Incendiary Missile 15 s,
   Electro Net 90 s, Vent Heat 120 s, adrenal 180 s.

Cross-check: all of these names appear in Brad's own Merc IO logs (`docs/CATALOG.md`, Jitzl / Jitzel IO).
