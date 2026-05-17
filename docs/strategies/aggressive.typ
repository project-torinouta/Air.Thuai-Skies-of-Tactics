// Aggressive Strategy — Close-range Rush

#set document(title: "Aggressive Strategy", author: "THUAI9 Team")
#set text(size: 11pt, lang: "en")
#set par(justify: true)
#set heading(numbering: "1.1")

#show heading.where(level: 1): it => {
  pagebreak(weak: true)
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
      [Aggressive Strategy #h(1fr) Page #page]
    }
  },
)

= Aggressive Strategy

== Overview

The *aggressive strategy* is a close-range rush tactic designed to overwhelm
opponents through high physical damage and frontline pressure. It prioritises
*strength* over all other attributes, equipping pieces with shortswords and
heavy armour for maximum durability and melee output.

== Characteristics

#figure(
  table(
    columns: (auto, auto),
    [*Aspect*], [*Value*],
    [Strength], [20],
    [Dexterity], [8],
    [Intelligence], [2],
    [Weapon], [Shortsword (type 2)],
    [Armour], [Heavy (type 3)],
    [Role], [Frontline brawler],
    [Spell usage], [None],
  ),
  caption: [Piece configuration],
)

== Positioning

Player 1 pieces are placed as far forward as possible (near the border), while
player 2 pieces occupy the front of their half. This minimises the distance to
the enemy team, allowing early engagement.

== Behaviour

The action strategy follows a simple priority:

1. Find the nearest living enemy piece.
2. Move toward that enemy, selecting the legal move that minimises the remaining
  distance.
3. If the enemy is within attack range, attack.
4. Never cast spells.

#figure(
  table(
    columns: (auto, auto),
    [*Action*], [*Condition*],
    [Move], [Always toward nearest enemy],
    [Attack], [Enemy in attack range],
    [Spell], [Never],
  ),
  caption: [Decision matrix],
)

== Strengths and Weaknesses

*Strengths:*
- High survivability from heavy armour (23 physical resist).
- Decent damage output (10 base + 20 strength = 30 before reduction).
- Simple, fast decision-making.

*Weaknesses:*
- No ranged capability (attack range 3).
- Zero magic damage; defenceless against magic-based opponents.
- Very low intelligence limits spell slots and tactical flexibility.
- Predictable movement pattern easily exploited by kiting.

== When to Use

Use the aggressive strategy as a baseline for melee-oriented tactics or when the
board layout favours close-quarters combat (narrow corridors, few obstacles).
