---
name: benchmark
description: >
  Run the THUAI9 strategy benchmark (benchmark.py) to compare strategies
  head-to-head or in round-robin, and save results as markdown files in the
  benchmark/ directory. Use when the user asks to "benchmark", "compare
  strategies", "run benchmark", or "evaluate strategies".
---

# Benchmark Skill

## Tool

`src/benchmark.py` — a CLI script that runs AI strategy matchups and
reports win/loss/draw statistics. Supports single matchups and full
round-robin, with static or randomly generated boards.

## Output Format

Always save results to `benchmark/<p1>-<p2>.md` for single matchups or
`benchmark/round-robin.md` for round-robin. The file must contain a single
fenced code block with language `plaintext` containing the full benchmark
stdout output.

```markdown
\`\`\`plaintext
<full benchmark output>
\`\`\`
```

## Usage

Change into the `src/` directory, then run via `uv run`:

```bash
cd src
```

### Single Matchup

```bash
uv run python benchmark.py --p1 <strategy> --p2 <strategy> --rounds <N> [options]
```

Example:

```bash
uv run python benchmark.py --p1 aggressive --p2 defensive --rounds 50
```

### Round-robin (all vs all)

```bash
uv run python benchmark.py --rounds <N> [options]
```

### With Random Boards

```bash
uv run python benchmark.py --p1 aggressive --p2 defensive --rounds 50 \
    --generate-boards 10 --board-rows 16 --board-cols 16 --obstacle-density 0.12
```

## Strategies

| Name         | Behaviour                                      |
| ------------ | ---------------------------------------------- |
| `aggressive` | Close-range rush, high strength, shortsword    |
| `defensive`  | Ranged kiting, high dex, bow + light armour    |
| `mcts`       | Monte Carlo Tree Search (configurable sims)    |
| `alpha_beta` | Alpha-beta pruning search (configurable depth) |
| `random`     | Randomly delegates to aggressive or defensive  |

## Key Options

| Flag                   | Default | Description                        |
| ---------------------- | ------- | ---------------------------------- |
| `--rounds N`           | 10      | Games per matchup                  |
| `--board PATH`         | case1   | Board file or directory            |
| `--board-dir DIR`      | —       | Directory of .txt board files      |
| `--generate-boards N`  | 0       | Generate N random boards           |
| `--board-rows N`       | 20      | Rows for generated boards          |
| `--board-cols N`       | 20      | Columns for generated boards       |
| `--obstacle-density F` | 0.1     | Obstacle density 0.0–1.0           |
| `--max-game-rounds N`  | 100     | Max rounds per game before timeout |
| `--mcts-simulations N` | 10      | MCTS iterations per decision       |
| `--alpha-beta-depth N` | 3       | Alpha-beta search depth            |
| `--seed N`             | —       | Random seed for reproducibility    |
