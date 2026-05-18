// Sniper Strategy — Bow + Heavy Armour, Focus-Fire

#set document(title: "Sniper Strategy", author: "THUAI9 Team")
#set text(size: 11pt, lang: "en")
#set par(justify: true)
#set heading(numbering: "1.1")

#show heading.where(level: 1): it => {
  align(center, text(16pt, strong(it.body)))
  v(0.5em)
}

#show heading.where(level: 2): set text(size: 13pt)
#show raw: set text(size: 9pt)

#set page(paper: "a4", margin: 2cm, numbering: "1")
#set page(
  header: context {
    let page = counter(page).get().first()
    if page > 1 {
      [Sniper Strategy #h(1fr) Page #page]
    }
  },
)

= Sniper Strategy

== Overview

The *sniper* strategy is a bow-wielding heavy-armour build designed to out-trade
every existing strategy. It achieves a 100% win rate across all matchups in the
standard 31-board benchmark by exploiting a simple insight: at STR 29 / DEX 1, the
bow deals 45 base damage — enough to punch through heavy armour for 22 damage
per hit, while the same heavy armour reduces incoming attacks to single digits.

== Characteristics

#figure(
  table(
    columns: (auto, auto),
    [*Aspect*], [*Value*],
    [Strength], [29],
    [Dexterity], [1],
    [Intelligence], [0],
    [Weapon], [Bow (type 3)],
    [Armour], [Heavy (type 3)],
    [Role], [Ranged tank],
    [AP per turn], [3],
    [Spell usage], [None],
  ),
  caption: [Piece configuration],
)

== Stat Rationale

- *Strength 29*: Near-maximised damage. Bow damage = 16 + 29 = 45, yielding
  45 - 23 = 22 damage against heavy-armour opponents (the common defensive
  configuration). Health = 50 + 58 = 108.
- *Dexterity 1*: A single point trades 2 HP and 1 damage for +1 initiative
  (d10+DEX turn order) and +1 movement. This gives a small but meaningful
  edge in mirror matchups — acting first decides who gets the opening shot.
- *Intelligence 0*: No spell slots. The sniper relies on raw attack damage
  rather than situational spells.

== Behaviour

The action strategy follows a simple two-branch decision tree:

#figure(
  table(
    columns: (auto, auto),
    [*Condition*], [*Action*],
    [Enemy in bow range (≤ 9)],
    [Attack the lowest-health enemy. Do not move — every AP is spent on
      damage.],

    [No enemy in bow range],
    [Advance toward the lowest-health enemy to close to range 9.],
  ),
  caption: [Sniper decision matrix],
)

The strategy has no special cases for retreat, kiting, or positioning. This
simplicity is deliberate: the sniper wins the damage trade 3:1, so the optimal
move is always to maximise damage output.

=== Focus-Fire

All three pieces independently target the globally lowest-health enemy. This
concentrates ~66 damage per round (3 × 22) onto a single target, producing:

- Enemy kill in ~5 hits (90 HP / 22 damage) ≈ 2-3 round cycles
- Fight snowballs from 3v3 to 3v2, then 3v1
- Enemy damage output collapses as pieces die

=== Why No Retreat

The sniper's heavy armour (resist 23) reduces incoming physical attacks to:

- Aggressive shortsword: 30 - 23 = 7 damage
- Warrior shortsword: 34 - 23 = 11 damage

While its bow deals 22 damage per hit to any heavy-armour target. The 3:1 trade
ratio means retreating is strictly suboptimal — every turn spent moving instead
of attacking is a turn the enemy survives longer.

== Comparison to Aggressive

#figure(
  table(
    columns: (auto, auto, auto),
    [*Metric*], [*Sniper*], [*Aggressive*],
    [Strength], [29], [20],
    [Weapon], [Bow (range 9)], [Shortsword (range 3)],
    [Armour], [Heavy (23 resist)], [Heavy (23 resist)],
    [Damage vs heavy], [22], [7],
    [HP], [108], [90],
    [AP per turn], [3], [2],
    [Win rate vs each other], [100%], [0%],
  ),
  caption: [Sniper vs aggressive head-to-head],
)

The sniper's range advantage (9 vs 3) gives it a free shot before the aggressive
can close to melee. By the time the aggressive reaches shortsword range, the
sniper has already dealt 22 damage and has a decisive HP advantage (108 vs 67).

== Strengths and Weaknesses

*Strengths:*
- Highest per-hit damage in the game (bow 45 base, 22 after heavy armour).
- Longest effective range of any non-mage (bow range 9).
- 108 HP makes every piece a tank — no single target can be burst down.
- No reliance on spells or limited resources — consistent output every turn.
- Simple AI with no positioning bugs (no retreat/kite logic to get wrong).

*Weaknesses:*
- Low dexterity (1) means poor initiative — often acts late in the queue.
- Movement (22.5) is slower than light-armour builds (25-32).
- No area damage — must kill enemies one at a time.
- Predictable: always attacks the lowest-health enemy, never repositions.

== When to Use

Use the sniper as the default strategy for competition. It has no losing matchup
and its simple logic is unlikely to produce unexpected behaviour. Avoid only on
boards so small (< 12 tiles wide) that range advantage disappears entirely.

== Benchmark Performance

All results from the standard 31-board benchmark (30 games per matchup, max 60
rounds, seed 42).

#figure(
  table(
    columns: (auto, auto, auto),
    [*Opponent*], [*Win rate*], [*Note*],
    [Aggressive], [100%], [3:1 damage ratio wins every trade],
    [Warrior], [100%], [Bow outranges shortsword 3:1],
    [Ranger], [100%], [Heavy armour vs light armour: 23 vs 8 resist],
    [Tactical], [100%], [Staff 4 true damage vs 106 HP is too slow],
    [Defensive], [100%], [Never lets the kiter create distance],
    [Random], [100%], [Expected],
  ),
  caption: [Benchmark results],
)
