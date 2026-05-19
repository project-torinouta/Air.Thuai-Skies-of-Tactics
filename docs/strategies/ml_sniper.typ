// ML Sniper Strategy — Evolution-Strategies-Optimized Sniper

#set document(title: "ML Sniper Strategy", author: "THUAI9 Team")
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
      [ML Sniper Strategy #h(1fr) Page #page]
    }
  },
)

= ML Sniper Strategy

== Overview

The *ML sniper* strategy uses a tiny neural network evolved by Covariance Matrix
Adaptation Evolution Strategies (CMA-ES) to make tactical decisions. It starts
from the proven hand-coded sniper behaviour and fine-tunes parameters such as
target selection, positioning deviation, aggression, and retreat threshold —
discovering a ~5% improvement over the hand-coded baseline.

Key insight: while the optimal stat build (STR 29 / DEX 1, bow + heavy armour)
is known, the *tactical decisions* — which enemy to prioritise, when to advance
versus hold, when to retreat — are hyper-parameters that can be optimised by
evolution.

== Architecture

The ML pipeline consists of four components:

#figure(
  table(
    columns: (auto, auto),
    [*Component*], [*Purpose*],
    [State encoder], [Converts `Environment` → 104-dim feature vector],
    [Policy network], [2-layer feedforward NN, ~9K parameters],
    [Action decoder], [Network outputs → valid `ActionSet` with masking],
    [ES optimizer], [Diagonal CMA-ES for training],
  ),
  caption: [ML pipeline components],
)

=== State Encoder

The encoder produces a fixed 104-dimensional vector containing:

- Per-piece: position, HP ratio, AP, damage, resist, range, stats, height,
  weapon and armour type, spell slots (16 features × 6 pieces)
- Current piece indicator (one-hot over queue)
- Global: round number, game-over flag

All features are normalised to [0, 1].

=== Policy Network

#figure(
  table(
    columns: (auto, auto),
    [*Aspect*], [*Value*],
    [Input], [104 (encoded state)],
    [Hidden 1], [64 neurons, ReLU],
    [Hidden 2], [32 neurons, ReLU],
    [Output], [6 (action logits)],
    [Parameters], [~9,000 (9,062)],
    [Runtime], [< 1 ms per forward pass],
    [Framework], [Pure NumPy — no external deps],
  ),
  caption: [Network architecture],
)

=== Action Decoder

The 6 network outputs control:

#figure(
  table(
    columns: (auto, auto, auto),
    [*Index*], [*Parameter*], [*Effect*],
    [0], [target_bias], [0 = lowest HP, 1 = highest HP target],
    [1], [deviation], [0 = stay near allies, 1 = flank independently],
    [2], [aggression], [0 = hold when out of range, 1 = always advance],
    [3], [retreat_hp], [0 = never retreat, 1 = retreat at 50% HP],
    [4], [focus_fire], [Blend between spread damage and focus-fire],
    [5], [spare], [Unused],
  ),
  caption: [Network output semantics],
)

With all outputs at 0.5, behaviour is identical to the hand-coded sniper
(advance toward lowest-HP enemy, attack if in range, never retreat). The ES
optimiser nudges these parameters to find improvements.

== Training

Training uses evolution strategies with diagonal covariance:

#figure(
  table(
    columns: (auto, auto),
    [*Hyper-parameter*], [*Value*],
    [Generations], [200+],
    [Population], [16 candidates per generation],
    [Trials per candidate], [11 games vs hand-coded sniper],
    [Evaluation], [Parallel across CPU cores],
    [Training time], [~1-2 hours (wall clock)],
    [Output], [`weights/ml_sniper_best.npy`],
  ),
  caption: [Training configuration],
)

Training is embarassingly parallel — all 16 candidates are evaluated
simultaneously using `ProcessPoolExecutor`.

== Benchmark

1000-game head-to-head on the standard board:

#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    [*Matchup*], [*ML Wins*], [*Sniper Wins*], [*Draws*], [*ML Win Rate*],
    [ML (P1) vs Sniper (P2)], [574], [426], [0], [57.4%],
    [Sniper (P1) vs ML (P2)], [464], [536], [0], [46.4%],
    [Combined], [1038], [962], [0], [51.9%],
  ),
  caption: [1000-game benchmark results (seed 42)],
)

Breaking down by side:

- *As P1*: 57.4% — the ML secures the opening-shot advantage better
- *As P2*: 46.4% — the ML gives back some of the P1 advantage

The ML's advantage primarily comes from learned target selection and positioning
decisions that differ from the greedy lowest-HP heuristic. The hand-coded sniper
always attacks the lowest-health enemy; the ML sometimes chooses to spread
damage or target a different enemy for positional advantage.

== Usage

To run a benchmark:

```bash
cd src
uv run python benchmark.py --p1 ml_sniper --p2 sniper --rounds 30
```

To retrain the policy network:

```bash
cd src
uv run python -m ml.train_evolution --generations 200 --pop-size 16 --trials 11 --workers 16
```

The best weights are saved to `weights/ml_sniper_best.npy` and loaded
automatically by the strategy.

== Files

- `src/ml/state_encoder.py` — State encoder
- `src/ml/policy_net.py` — Policy network
- `src/ml/action_decoder.py` — Action decoder
- `src/ml/es_optimizer.py` — ES optimizer
- `src/ml/train_evolution.py` — Training script
- `src/strategies/ml_sniper.py` — Strategy entry point
- `weights/ml_sniper_best.npy` — Trained weights
