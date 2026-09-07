# Ability names by discipline (from Parsely's class-abilities database)

Scraped 2026-09-07 from `parsely.io/parser/abilities/<class>` (Empire name / Republic mirror). The Empire
name is what appears in Brad's logs. Useful as the reference list when writing `rules.py`; the log itself
only tells us what was *used*, this tells us what *exists*.

## Operative

**Base skills:** Overload Shot, Recuperate, Rifle Shot, Shiv, Fragmentation Grenade, Corrosive Dart,
Diagnostic Scan, Backstab, Stealth, Adrenaline Probe, Noxious Knives, Distraction, Kolto Infusion, Evasion,
Kolto Probe, Cloaking Screen, Sleep Dart, Toxic Haze, Shield Probe, Toxin Scan, Exfiltrate, Tactical Superiority

**Base passives that show up as effects:** Coordination, Tactical Advantage (stack buff), Skirmisher, Preparedness

**Base mods (effects you may see):** Advanced Cloaking, Evasive Screen, Med Shield, Holotraverse, Infiltrate,
Flash Bang, Debilitate, Jarring Strike, Endorphin Rush

### Lethality
- Skills: Corrosive Assault, Stim Boost, Corrosive Grenade, Toxic Blast, Lethal Strike
- Passives that become log effects: Toxic Regulators, Fatality, Quickening, Augmented Toxins, Lethal Purpose,
  Combat Stims (Revitalizers heal), Devouring Microbes, Corrosive Microbes, Acidic Compounds
- Mods: Tactical Overdrive, Tactical Stims, Critical Grenade, Corrosive Defense/Refund/Impair/Return

### Medicine
- Skills: Kolto Injection, Stim Boost, Recuperative Nanotech, Surgical Probe, Kolto Waves, Resuscitation Probe, Toxic Haze
- Passives: Durable Meds, Enduring Kolto, Incisive Action, Medical Therapy, Prognosis: Critical, Tox Screen,
  Surgical Steadiness, Surprise Surgery, Medical Engineering, Patient Studies, Surgical Precision,
  Accomplished Doctor, Medical Consult, Tactical Medicine, Curative Jolt
- Mods: Kolto Burst, Kolto Stim, Reactive Substance, Critical Nanotech, Nano Mark, Nanotech Stim, Stim Burst,
  Tactical Effectiveness, Tactical Overdrive

### Concealment
- Skills: Laceration, Stim Boost, Crippling Slice, Volatile Substance, Veiled Strike
- Passives: Acid Blade, Collateral Strike, Tactical Opportunity, Culling, Prey on the Weak, Revealing Weakness,
  Calculated Frenzy, Critical Stimulants
- Mods: Tactical Overdrive, Tactical Critical, Advanced Stealth, Roll Knife, Relentless Blades, Crippling Throw/Wounds

## Mercenary

**Base skills:** Missile Blast, Rapid Shots, Recharge and Reload, Power Shot, Kolto Shot, Death from Above,
Determination, Vent Heat, Energy Shield, Rail Shot, Disabling Shot, Rapid Scan, Sweeping Blasters,
Fusion Missile, Jet Boost, Unload, Emergency Scan, Concussion Missile, Cure, Hydraulic Overrides,
Kolto Overload, Power Surge, Electro Net

**Base passives / effects:** Combustible Gas Cylinder, Hunter's Boon, Supercharge (stack buff), Advanced Targeting,
Fuel Reserves

**Base mods:** Power Barrier, Chaff Flare, Power Overrides, Supercharged Celerity, Energy Rebounder,
Kolto Surge, Power Shield, Electro Dart, Responsive Safeguards, Rocket Out, Trauma Regulators,
Gyroscopic Alignment Jets

### Innovative Ordnance
- Skills: Incendiary Missile, Supercharged Gas, Thermal Detonator, Serrated Shot, Mag Shot
- Passives that become effects: Volatile Warhead, Superheated Shot, Sweltering Heat,
  Innovative Particle Accelerator (proc), Relentless Ordnance, Speed to Burn, Surging Shots (stack buff)
- Mods: Eruptive Flames, Incendiary Ignition, Volatile Cinders, Heavy Shrapnel, Impact Explosives, Slow Burn

### Arsenal
- Skills: High Velocity Supercharged Gas, Tracer Missile, Heatseeker Missiles, Priming Shot, Blazing Bolts
- Passives: Tracer Lock (stacks), Blazing Barrels, Terminal Velocity, Pinning Fire, Target Tracking, Barrage, Blowback, Riddle
- Mods: Signature Shot, Triple Trace, Customized Warhead, Thermonuclear Fusion, Tracing Residue

### Bodyguard
- Skills: Healing Scan, Supercharged Kolto Gas, Kolto Shell, Kolto Missile, Onboard AED, Progressive Scan
- Passives: Kolto Pods, Powered Insulators, Surgical Precision System, Med Tech, Warden, Critical Efficiency,
  Emergency Response, Kolto Residue, Kolto Boosters, Proactive Medicine
- Mods: Critical Scanning, Integrated Scanning, Residual Globules, Efficient Shells, Shell Shield, Splashing Shells

## Other classes
Same URL pattern: `/parser/abilities/sorcerer`, `/powertech`, `/commando`, etc. Scrape on demand.
