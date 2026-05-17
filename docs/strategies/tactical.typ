// Tactical Strategy — Spell-Focused Mage

#set document(title: "Tactical Strategy", author: "THUAI9 Team")
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
      [Tactical Strategy #h(1fr) Page #page]
    }
  },
)

= Tactical Strategy

== Overview

The *tactical strategy* is a spell-focused mage build inspired by the winning
team in game replay `assets/8369951.json`. It uses a staff (range 12, fixed
4 true damage) for safe ranged harassment and Fireball (30 AoE damage) as a
close-range finishing tool.

== Characteristics

#figure(
  table(
    columns: (auto, auto),
    [*Aspect*], [*Value*],
    [Strength], [14],
    [Dexterity], [8],
    [Intelligence], [8],
    [Weapon], [Staff (type 4)],
    [Armour], [Light (type 1)],
    [Role], [Ranged mage],
    [Spell usage], [Fireball, Arrow Hit],
  ),
  caption: [Piece configuration],
)

== Stat Rationale

- *Strength 14*: Grants 2 action points per turn (move + spell or attack +
  spell) and a health pool of 58.
- *Dexterity 8*: Combined with light armour (+3), movement = 8 + 7 + 10 = 28
  tiles per turn, enough to kite effectively on a 20 by 20 board.
- *Intelligence 8*: Provides 3 spell slots, enough for several Fireball casts
  per game.

== Behaviour

The action strategy follows a three-tier priority:

#figure(
  table(
    columns: (auto, auto),
    [*Priority*], [*Action*],
    [1. Spell], [Fireball at the enemy with the most neighbours in
      blast radius (range 2, area radius 5); fall back to Arrow Hit on
      adjacent low-health enemies],
    [2. Attack], [Staff attack (4 true damage) on the lowest-health enemy
      in range 12],
    [3. Move], [Move to maintain 80% of attack range (~9 tiles) from the
      primary target; penalise positions within 3 tiles],
  ),
  caption: [Decision matrix],
)

=== Fireball Targeting

The spell decision evaluates every enemy within Fireball range (2 tiles) and
selects the one with the most additional enemies inside the blast radius
(5 tiles). This maximises area damage.

If no enemy is within Fireball range, the strategy checks for Arrow Hit
(range 1, 30 damage) on adjacent enemies before falling through to attack
and move.

== Strengths and Weaknesses

*Strengths:*
- Longest attack range in the game (staff range 12).
- Fireball deals 30 AoE damage to clustered enemies.
- No damage falloff from distance or resistances (staff deals true damage).
- Kiting behaviour makes it hard for melee opponents to engage.

*Weaknesses:*
- Low strength (58 HP) makes pieces fragile under sustained fire.
- Only 2 action points per turn limits tactical flexibility.
- Fireball has very short range (2), requiring the mage to close distance
  to use it.
- No healing or defensive spells.

== When to Use

Use the tactical strategy on open boards where the staff's range can be
fully utilised. Effective against melee-focused opponents but vulnerable to
other ranged builds with higher damage output (see ranger strategy).

== Benchmark Performance

#figure(
  table(
    columns: (auto, auto, auto),
    [*Opponent*], [*Win rate*], [*Note*],
    [Aggressive], [80%], [Outranges and kites effectively],
    [Defensive], [100%], [Superior range and damage],
    [Ranger], [20%], [Bow out-trades staff],
  ),
  caption: [Benchmark results (10 games per matchup)],
)
