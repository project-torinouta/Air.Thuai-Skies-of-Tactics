// Warrior & Ranger Strategies — High-Strength Burst

#set document(title: "Warrior & Ranger Strategies", author: "THUAI9 Team")
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
      [Warrior & Ranger Strategies #h(1fr) Page #page]
    }
  },
)

= Warrior & Ranger Strategies

== Overview

The *warrior* and *ranger* strategies are high-strength builds derived from
analysis of six game replays (`assets/8367*.json`). Across all replays, the
dominant winning composition was type-3 warriors with high strength (STR 23-24),
enabling 3 action points per turn for a move-attack-spell burst combo.

Both variants share the core principle of maximising strength for action-point
advantage, but differ in weapon choice and engagement range.

== Warrior (Melee Burst)

=== Characteristics

#figure(
  table(
    columns: (auto, auto),
    [*Aspect*], [*Value*],
    [Strength], [24],
    [Dexterity], [6],
    [Intelligence], [0],
    [Weapon], [Shortsword (type 2)],
    [Armour], [Light (type 1)],
    [Role], [Melee burst],
    [AP per turn], [3],
    [Spell usage], [Arrow Hit],
  ),
  caption: [Warrior configuration],
)

=== Stat Rationale

- *Strength 24*: Exceeds the 21-point threshold for 3 action points per turn.
  Health = 30 + 48 = 78. Attack damage = 10 + 24 = 34 (before resist).
- *Dexterity 6*: Movement = 6 + 12 + 10 = 28 (+3 from light armour = 31).
- *Intelligence 0*: Still grants 1 spell slot (INT ≤ 3), enough for Arrow Hit.

=== Burst Combo

With 3 AP, the warrior can execute all three actions in one turn:

1. *Move* toward the target (1 AP).
2. *Attack* with shortsword: 34 base damage (before physical resist).
3. *Arrow Hit* spell: 30 fixed damage at range 1.

Total burst: up to 64 damage per turn — enough to kill or severely wound
most pieces.

=== Behaviour

#figure(
  table(
    columns: (auto, auto),
    [*Priority*], [*Action*],
    [1. Arrow Hit], [On the lowest-health adjacent enemy (range 1, 30 dmg)],
    [2. Attack], [On the lowest-health enemy in weapon range (range 3)],
    [3. Move], [Toward the nearest enemy],
  ),
  caption: [Warrior decision matrix],
)

== Ranger (Ranged Counter)

=== Characteristics

#figure(
  table(
    columns: (auto, auto),
    [*Aspect*], [*Value*],
    [Strength], [22],
    [Dexterity], [8],
    [Intelligence], [0],
    [Weapon], [Bow (type 3)],
    [Armour], [Light (type 1)],
    [Role], [Ranged damage dealer],
    [AP per turn], [3],
    [Spell usage], [Arrow Hit],
  ),
  caption: [Ranger configuration],
)

=== Stat Rationale

- *Strength 22*: Just over the 21-point threshold for 3 AP. Attack damage = 16 +
  22 = 38 (before resist). Health = 30 + 44 = 74.
- *Dexterity 8*: Movement = 8 + 11 + 10 = 29 (+3 from light armour = 32).
- *Intelligence 0*: 1 spell slot for Arrow Hit.

The ranger trades 4 HP and 4 base attack damage versus the warrior for +3
movement and +6 attack range, which is critical for countering the tactical
mage.

=== Behaviour

Identical decision matrix to the warrior. The key difference is engagement
range: the bow's range 9 allows the ranger to attack from safety while the
warrior must close to range 3.

=== Why the Ranger Beats the Tactical Mage

The tactical mage relies on staff range 12 + kiting. The ranger counters
this because:

- Bow range (9) is close enough to staff range (12) that the 3-tile gap is
  closed in one turn of movement.
- Bow damage (38/hit) is 9.5 times the staff's fixed 4 true damage.
- The ranger's 74 HP can absorb many staff hits; the mage's 58 HP dies in
  2 bow shots.

== Replay Analysis Summary

All six replays were analysed to identify the winning formula:

#figure(
  table(
    columns: (auto, auto, auto, auto),
    [*Replay*], [*Winner*], [*Composition*], [*Rounds*],
    [8369951], [Blue], [3x Mage vs 3x Warrior], [4],
    [8367856], [Red], [3x Warrior vs 3x Type-1], [10],
    [8369953], [Red], [3x Warrior (STR 24) vs 3x Warrior (STR 23)], [16],
    [8369954], [Blue], [3x Warrior (STR 23) vs 3x Warrior (STR 24)], [5],
    [8371271], [Red], [3x Warrior (HP 98) vs 3x Mage (HP 86)], [15],
    [8371272], [Blue], [3x Warrior (HP 98) vs 3x Mage (HP 86)], [15],
  ),
  caption: [Game replay analysis],
)

Key findings:
- High strength (STR > 21) for 3 AP is the single most important attribute.
- Focus fire on one target at a time dramatically reduces time-to-kill.
- The burst combo (attack + ability) deals 60-70 damage per turn.
- In even stat matchups, the side that focuses first wins.

== Benchmark Performance

Results from the standard 31-board benchmark (30 games per matchup, max 60
rounds, seed 42).

#figure(
  table(
    columns: (auto, auto, auto),
    [*Matchup*], [*Win rate*], [*Note*],
    [Warrior vs aggressive], [0%], [Loses the 1v1 trade],
    [Warrior vs defensive], [100%], [Easily closes gap on kiter],
    [Warrior vs tactical], [90%], [Overwhelms the mage before kiting],
    [Ranger vs aggressive], [13%], [Range helps but armour gap is fatal],
    [Ranger vs defensive], [100%], [Superior reach and damage],
    [Ranger vs tactical], [100%], [Bow damage overwhelms staff],
  ),
  caption: [Benchmark results],
)

== When to Use

Use the *warrior* on dense boards with many obstacles where the short
attack range is less of a liability. For general-purpose play, consider the
*sniper* strategy instead — it achieves a 100% win rate across all matchups.
