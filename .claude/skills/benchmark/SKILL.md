---
name: benchmark
description: >
  Run the THUAI9 strategy benchmark (benchmark.py) to compare strategies
  head-to-head or in round-robin, and save results as markdown files in the
  benchmark/ directory. Use when the user asks to "benchmark", "compare
  strategies", "run benchmark", or "evaluate strategies".
---

# Benchmark Skill

## Tools

- **`src/benchmark.py`** — CLI script for single matchups with full control
  over init/action strategies, boards, and parameters.
- **`script/run_benchmark.sh`** — Batch runner that iterates through a
  predefined list of matchups using shared random boards.  Run it and let
  it finish; it saves all results to `benchmark/` automatically.

  ```bash
  cd script
  bash run_benchmark.sh              # 30 fast + 10 slow rounds each
  bash run_benchmark.sh 50 15        # custom round counts
  ```

## Output Format

Save results to `benchmark/` as markdown files with a single `plaintext`
code block containing the full stdout. File naming convention:

| Scenario           | Pattern                                 | Example                                |
| ------------------ | --------------------------------------- | -------------------------------------- |
| Standard matchup   | `<p1>-vs-<p2>.md`                       | `aggressive-vs-defensive.md`           |
| Mixed init+action  | `<init>+<action>-vs-<init>+<action>.md` | `aggressive+mcts-vs-defensive.md`      |
| Round-robin        | `round-robin.md`                        | `round-robin.md`                       |
| Non-default params | append `-<param>.md`                    | `aggressive-vs-alpha_beta-depth-10.md` |

```markdown
\`\`\`plaintext
<full benchmark stdout>
\`\`\`
```

## Usage

Change into the `src/` directory first, then run via `uv run`:

```bash
cd src
```

### Single Matchup

```bash
uv run benchmark.py --p1 <strategy> --p2 <strategy> --rounds <N> [options]
```

Example:

```bash
uv run benchmark.py --p1 aggressive --p2 defensive --rounds 50
```

### Mixed Init/Action

```bash
uv run benchmark.py --p1-init aggressive --p1-action mcts --p2 defensive --rounds 50
```

### Round-robin (all vs all)

```bash
uv run benchmark.py --rounds <N> [options]
```

### With Random Boards

```bash
uv run benchmark.py --p1 aggressive --p2 defensive --rounds 50 \
    --generate-boards 10 --board-rows 16 --board-cols 16 --obstacle-density 0.12
```

## Strategies

| Name         | Behaviour                                   | Can init? | Can action? |
| ------------ | ------------------------------------------- | --------- | ----------- |
| `aggressive` | Close-range rush, high strength, shortsword | yes       | yes         |
| `defensive`  | Ranged kiting, high dex, bow + light armour | yes       | yes         |
| `mcts`       | Monte Carlo Tree Search                     | —         | yes         |
| `alpha_beta` | Alpha-beta pruning search                   | —         | yes         |
| `random`     | Randomly delegates                          | yes       | yes         |

## Key Options

| Flag                   | Default | Description                        |
| ---------------------- | ------- | ---------------------------------- |
| `--rounds N`           | 10      | Games per matchup                  |
| `--board PATH`         | case1   | Board file or directory            |
| `--board-dir DIR`      | —       | Directory of `.txt` board files    |
| `--generate-boards N`  | 0       | Generate N random boards           |
| `--board-rows N`       | 20      | Rows for generated boards          |
| `--board-cols N`       | 20      | Columns for generated boards       |
| `--obstacle-density F` | 0.1     | Obstacle density 0.0–1.0           |
| `--max-game-rounds N`  | 100     | Max rounds per game before timeout |
| `--p1-init S`          | —       | Init strategy for P1               |
| `--p1-action S`        | —       | Action strategy for P1             |
| `--p2-init S`          | —       | Init strategy for P2               |
| `--p2-action S`        | —       | Action strategy for P2             |
| `--mcts-simulations N` | 10      | MCTS iterations per decision       |
| `--alpha-beta-depth N` | 3       | Alpha-beta search depth            |
| `--seed N`             | —       | Random seed for reproducibility    |
