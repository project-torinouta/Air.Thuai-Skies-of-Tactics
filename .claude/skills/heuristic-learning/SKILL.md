---
name: heuristic-learning
description: 'Apply Heuristic Learning (HL) — iteratively improve programmatic policies
  through testing, benchmarking, and structured feedback. Use when: (1) User says
  "/heuristic-learning", "hl", "apply HL", "iterate strategy"; (2) User wants to
  improve a game strategy without neural network training; (3) User wants to explore
  tactical variants through benchmark-driven iteration'
---

# Heuristic Learning

Based on Jiayi Weng's _Learning Beyond Gradients_ — the insight that coding agents
can iteratively improve programmatic policies through tests, feedback, and structured
memory, without gradient-based neural network training.

In this project, Heuristic Learning means: **you (the user) + Claude iterate on
game strategies using benchmark results as the objective signal, replays as
episodic memory, and explicit test suites as long-term memory.**

## Core Loop

Each iteration follows the **Observe → Hypothesise → Modify → Verify** cycle:

### 1. Observe

Run a benchmark to establish the current baseline:

```bash
python -m benchmark --rounds 30 --fixed-build 29 1 0 \
  --include sniper sniper_tactical <your-strategy> \
  --matrix /tmp/hl_matrix.png --chart /tmp/hl_curve.png
```

Analyse the results:

- Which matchups are strong/weak?
- Are losses due to positioning, target selection, or AP management?
- What patterns appear in the loss replays (if available)?

### 2. Hypothesise

Form a concrete hypothesis about what change would improve performance:

- _"We lose when the enemy gets high ground first because we always advance
  through the centre. We should route around the edges."_
- _"We spread damage across all three enemies instead of focusing one down.
  Target selection should concentrate fire."_
- _"We waste AP repositioning when already in range. Only move when the target
  is outside bow range."_

Each hypothesis should be **falsifiable** — the benchmark result will tell you
whether it was correct.

### 3. Modify

Edit the strategy code to test the hypothesis. Keep changes minimal and focused
— one hypothesis per iteration. If the hypothesis is about target selection,
only change target selection logic.

### 4. Verify

Run the same benchmark again:

```bash
python -m benchmark --rounds 30 --fixed-build 29 1 0 \
  --include sniper sniper_tactical <your-strategy> \
  --matrix /tmp/hl_matrix.png --chart /tmp/hl_curve.png
```

Compare against the previous baseline:

| Iteration | vs Sniper | vs Sniper Tactical | Overall |
| --------- | --------- | ------------------ | ------- |
| Before    | 45%       | 30%                | 37.5%   |
| After     | 55%       | 35%                | 45.0%   |

**Decision rules:**

| Win-rate change | Decision                                       |
| --------------- | ---------------------------------------------- |
| ≥ +5%           | ✅ Keep the change, iterate further            |
| -5% to +5%      | ➖ Ambiguous — revert or run more games (100+) |
| ≤ -5%           | ❌ Revert the change                           |

## Preventing Catastrophic Forgetting

When a new change improves matchup A but regresses matchup B:

1. **Don't revert blindly.** Try to understand _why_ it hurts B.
2. **Add a test case.** Save a replay of the B loss and reference it.
3. **Combine both approaches.** Can you add a condition that activates the new
   behaviour only in situations where A arises, while keeping the old behaviour
   everywhere else?

The key insight from the article: in HL, forgetting is a software engineering
problem, not an optimisation problem. Old capabilities are preserved via **tests,
replays, version diffs, and conditional branches** — not compressed into a
fixed-size weight matrix.

## Memory & Replay

Use these memory mechanisms to accumulate knowledge across iterations:

- **Code comments** — annotate non-obvious heuristics with why they exist and
  what failure case they address
- **Benchmark charts** — save to `benchmark/hl/` with iteration numbers
- **Replay files** — when a match reveals a failure mode, save the replay
  from Saiblo or local test output
- **Project memory** — save key decisions to the memory system so future
  sessions inherit the context

## Parameter Sweep Heuristics

When exploring a new idea, start coarse then refine:

1. **Coarse sweep** — benchmark at 10-15 games per matchup across 4-5 variants
2. **Filter** — discard variants below 30% win rate
3. **Fine sweep** — benchmark survivors at 50+ games
4. **Champion vs champ** — best new variant vs current best, 100 games

## Limitations

HL works well when:

- The policy can be expressed in ~200 lines of conditional logic
- The objective is measurable (win rate, score, survival time)
- Each game runs in under a minute (quick feedback)
- The action space is small enough to reason about

HL struggles when:

- The optimal policy requires sub-symbolic pattern recognition (e.g. pixels)
- The state space is too large for human reasoning (e.g. Go, StarCraft)
- The evaluation is noisy and requires hundreds of games per data point

For those cases, consider the ML pipeline (`src/ml/`) instead.
