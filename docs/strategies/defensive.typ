// Defensive Strategy — Ranged Kiting

#set document(title: "Defensive Strategy", author: "THUAI9 Team")
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
      [Defensive Strategy #h(1fr) Page #page]
    }
  },
)

= Defensive Strategy

== Overview

The *defensive strategy* is a ranged kiting approach that emphasises mobility
and distance control. Pieces are built for high dexterity and intelligence,
equipped with bows and light armour, and positioned in the rear half of the
board.

== Characteristics

#figure(
  table(
    columns: (auto, auto),
    [*Aspect*], [*Value*],
    [Strength], [5],
    [Dexterity], [15],
    [Intelligence], [10],
    [Weapon], [Bow (type 3)],
    [Armour], [Light (type 1)],
    [Role], [Ranged skirmisher],
    [Spell usage], [None],
  ),
  caption: [Piece configuration],
)

== Positioning

Pieces are placed in the rear of the player's half, as far from the border as
possible. This gives maximum reaction time and forces the enemy to close the gap
under fire.

== Behaviour

The kiting logic maintains a preferred distance of 70% of the piece's attack
range from the nearest enemy:

#figure(
  table(
    columns: (auto, auto),
    [*Situation*], [*Response*],
    [Enemy too close], [Move away from enemy],
    [Enemy at ideal distance], [Hold position or adjust slightly],
    [Enemy too far], [Move toward enemy],
    [Enemy in attack range], [Attack],
  ),
  caption: [Decision matrix],
)

The distance maintenance uses three thresholds:

- *Too close*: enemy is closer than 70% of attack range minus 2. The piece moves
  away if possible.
- *Ideal*: enemy is near 70% of attack range. The piece moves to the closest
  legal position to this ideal.
- *Too far*: enemy is beyond 70% of attack range plus 2. The piece moves closer
  if needed.

== Strengths and Weaknesses

*Strengths:*
- Long attack range (9) allows safe engagement from distance.
- High dexterity grants good movement speed and turn priority.
- Light armour provides +3 movement, reinforcing the kiting playstyle.
- Moderate intelligence keeps spell options open for customisation.

*Weaknesses:*
- Low strength means poor damage output in melee.
- Light armour offers minimal protection (8 physical resist).
- No spell usage in the default implementation.

== When to Use

Use the defensive strategy on open boards where ranged pieces can maintain line
of sight, or as a counter to slow melee opponents who struggle to close the gap.
