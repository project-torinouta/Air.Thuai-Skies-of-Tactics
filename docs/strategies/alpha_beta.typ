// Alpha-Beta Strategy — Adversarial Search

#set document(title: "Alpha-Beta Strategy", author: "THUAI9 Team")
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
      [Alpha-Beta Strategy #h(1fr) Page #page]
    }
  },
)

= Alpha-Beta Strategy

== Overview

The *Alpha-Beta strategy* uses adversarial search with alpha-beta pruning to
find optimal actions. It explores the game tree up to a configurable depth,
evaluating leaf nodes with a state-scoring heuristic.

== Algorithm

The implementation alternates between two phases:

=== Maximising Phase (current player)

Generate all legal action combinations (move $times$ attack $times$ spell) and
evaluate each by recursing into the minimising phase. Track the best score and
prune branches where $beta <= alpha$.

=== Minimising Phase (opponent)

Generate legal actions for the opponent using a simplified set of four generic
spells (Damage, Heal, Buff, Debuff) combined with move and attack options. Prune
branches where $beta <= alpha$.

#figure(
  table(
    columns: (auto, auto),
    [*Parameter*], [*Value*],
    [Default depth], [3],
    [Search space], [All move × attack × spell combinations],
    [Opponent model], [Generic spells + move/attack],
  ),
  caption: [Search configuration],
)

== Evaluation Function

Leaf nodes are scored using #raw("get_state_score"), which computes:

$
  S = sum_("piece") [10 dot "HP"/"max HP" + 0.5 dot "height" + 2 dot "AP" + 1.5
    dot "slots" + 0.3 dot "damage" + 0.2 dot "resist"]
$

Scores are summed for allied pieces and subtracted for enemy pieces.

== Behaviour

1. At each turn, enumerate all legal moves, attackable targets, and available
  spells for the current piece.
2. For the maximising phase, use the piece's actual available spells.
3. For the minimising phase, use a simplified generic spell set (since opponent
  spells are unknown).
4. Evaluate to the configured depth, pruning with alpha-beta.
5. Return the action that led to the highest evaluation.

== Strengths and Weaknesses

*Strengths:*
- Guaranteed optimal play within the search depth (with perfect evaluation).
- Alpha-beta pruning significantly reduces the branching factor compared to
  naive minimax.
- Customisable search depth trades quality for speed.

*Weaknesses:*
- State evaluation function (#raw("get_state_score")) is heuristic and may
  misjudge complex positions.
- Depth-limited search suffers from the horizon effect.
- The minimising phase uses generic opponent spells that may not match the real
  opponent's capabilities.
- Exponential blowup: each additional depth level multiplies computation
  dramatically.

== Configuration

The strategy accepts a parameter:

#raw("get_alpha_beta_action_strategy(max_depth: int = 3)")

A depth of 2 is faster but shallow; depth 4+ may be too slow for real-time play
depending on board complexity.

== When to Use

Use alpha-beta when you have a reliable evaluation function and want
deterministic, optimal play within a bounded search horizon.
