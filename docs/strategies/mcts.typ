// MCTS Strategy — Monte Carlo Tree Search

#set document(title: "MCTS Strategy", author: "THUAI9 Team")
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
#show list: set text(size: 10pt)

#set page(paper: "a4", margin: 2cm, numbering: "1")
#set page(
  header: context {
    let page = counter(page).get().first()
    if page > 1 {
      [MCTS Strategy #h(1fr) Page #page]
    }
  },
)

= MCTS Strategy

== Overview

The *MCTS (Monte Carlo Tree Search) strategy* uses statistical search to select
actions. It builds a partial game tree by simulating random playouts and uses
the results to guide action selection via the UCB1 (Upper Confidence Bound)
formula.

== Algorithm

The MCTS implementation follows four phases per iteration:

#set list(marker: [--])
- *Selection*: Starting from the root, traverse the tree by choosing the child
  with the highest UCB1 score until a leaf or unexpanded node is reached.
- *Expansion*: If the node has been visited before, generate all legal child
  actions (move, attack, and spell combinations) and add them as children.
- *Simulation*: From the selected child, run a random playout: move with 70%
  probability, attack with 80% probability, no spells, until game over or 50
  steps.
- *Backpropagation*: Propagate the result back up the tree, negating the value
  at each level for adversarial search.

=== UCB1 Formula

$ "UCB1"_j = (v_j)/(n_j) + sqrt((2 ln N) / (n_j)) $

Where $v_j$ is the cumulative value of child $j$, $n_j$ is its visit count, and
$N$ is the parent's visit count. Unvisited children receive a UCB1 score of
$infinity$, ensuring exploration.

== Simulation Scoring

Each playout returns a score between $-1.0$ and $1.0$:

#figure(
  table(
    columns: (auto, auto),
    [*Outcome*], [*Score*],
    [Current team wins], [+1.0],
    [Current team loses], [-1.0],
    [Draw (all dead)], [0.0],
    [No action taken], [-0.5],
    [Timeout, higher health], [Team with more HP wins],
    [Timeout, equal health], [0.0],
  ),
  caption: [Simulation scoring],
)

== Behaviour

The action strategy follows these steps per turn:

1. Build a root node from the current environment.
2. Run `simulation_count` MCTS iterations (default: 10).
3. After all iterations, select the child action with the highest visit count.
4. If no child was generated (no legal actions), return an empty action set.

== Strengths and Weaknesses

*Strengths:*
- Does not require a hand-crafted evaluation function for terminal states.
- Asymmetric search handles varying branch depths naturally.
- Can discover non-obvious sequences of actions.

*Weaknesses:*
- High computational cost — each iteration forks the environment and simulates.
- Random playouts can be noisy, requiring many simulations for reliable results.
- No spell usage in the simulation phase limits tactical depth.

== Configuration

The strategy accepts a parameter:

#raw(
  "get_mcts_action_strategy(simulation_count: int = 10)",
  lang: "python"
)

Higher simulation counts improve decision quality at the cost of computation
time.

== When to Use

Use MCTS when you have sufficient computation budget and want a general-purpose
searcher that works across diverse board states.
