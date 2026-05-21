# Heuristic Learning Loop — src/heuristic/

This package implements the **Observe → Hypothesise → Modify → Verify** cycle
from the `/heuristic-learning` skill.

## Quick Start

```bash
# 0. Status — show current champion and iteration
uv run python -m heuristic.loop status

# 1. Baseline — benchmark current champion vs main opponents
uv run python -m heuristic.loop baseline --rounds 50

# 2. Analyse — per-round snapshots (HP curves, kill order, first blood)
uv run python -m heuristic.loop analyse <variant>

# 3. Test — win-rate benchmark vs champion
uv run python -m heuristic.loop test <variant> --rounds 30

# 4. Promote — make a variant the new champion
uv run python -m heuristic.loop promote <variant>
```

## Directory Structure

```
src/heuristic/
├── __init__.py        # Package marker
├── loop.py            # CLI entry point
├── champion.py        # Current best strategy code
├── state.json         # Persistent state (iteration, champion name, results)
└── iterations/        # Iteration log files
    ├── 000-baseline/  # Initial baseline benchmark
    ├── 001-*/         # Each cycle gets a numbered folder
    └── ...
```

## Iteration Process

1. **Observe** — Run `loop.py baseline` or `loop.py test <variant>` to get
   objective numbers
2. **Hypothesise** — Analyse the results and form a falsifiable hypothesis
3. **Modify** — Edit `champion.py` (or create a new variant in
   `src/strategies/`) to test the hypothesis
4. **Verify** — Run `loop.py test <variant>` and compare results
5. **Promote** — If the variant wins, run `loop.py promote <variant>` to make
   it the new champion

## Decision Rules

| Win-rate change vs champion | Action                |
| --------------------------- | --------------------- |
| ≥ +5%                       | Promote to champion   |
| -5% to +5%                  | Run more games (100+) |
| ≤ -5%                       | Reject                |
