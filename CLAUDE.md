# THUAI9 Skies of Tactics — Project Context

## Overview

THUAI9 苍穹棋域 (Skies of Tactics) is a turn-based AI competition game where two
players control 3 pieces each on a grid board. Contestants write Python
strategies (initialization + per-turn actions) to compete.

## Project Structure

```
docs/
├── rules/              # Game rules, API docs, ranking rules (zh/en bilingual)
│   ├── api.zh.md / api.en.md
│   ├── game.zh.md / game.en.md
│   └── rank.zh.md / rank.en.md
└── reference/          # Additional reference materials (TBD)

src/
├── utils.py            # Core types: Point, ActionSet, PieceArg, Spell, enums
├── env.py              # Game engine: Cell, Piece, Board, Environment, combat
├── saiblo_client.py    # Saiblo stdin/stdout protocol
├── json_converter.py   # JSON state serialisation
├── strategy_utils.py   # AI helpers (public API for contestants)
├── local_input.py      # Input methods (console, function, remote)
├── local_client.py     # Local test entry point
├── main.py             # Saiblo competition entry point
├── board_visual.py     # Colourised terminal output
├── test_local.py       # Smoke test
├── pyproject.toml      # Project config with ruff/mypy
├── BoardCase/          # Board definition files
└── strategies/         # Built-in strategies (one file per variant)
    ├── aggressive.py   # Close-range rush strategy
    ├── defensive.py    # Ranged kiting strategy
    ├── mcts.py         # Monte Carlo Tree Search
    ├── alpha_beta.py   # Alpha-Beta pruning search
    └── random.py       # Random delegation
```

## Key Conventions

- **Documentation**: All docs have both Chinese (`*.zh.md`) and English
  (`*.en.md`) versions. Update both when modifying.
- **Commit style**: Follow conventional commits with emoji prefix, e.g.,
  `:art: chore(format): ...`.
- **Language**: Code and comments in English; docs bilingual.
- **Docstrings**: Sphinx `:param:` / `:type:` / `:returns:` / `:rtype:` style.
- **Type annotations**: Use the `typing` package (`List[X]`, `Optional[X]`,
  `Tuple[X, Y]`, `Dict[K, V]`) — not built-in generics or `| None` union syntax.
- **Formatter**: Ruff configured in `pyproject.toml` (line-length 100,
  double quotes, space indent).
- **Strategies**: Each strategy variant lives in its own file under
  `src/strategies/`. Import factory functions directly:
  `from strategies.aggressive import get_aggressive_action_strategy`.
- **StrategyFactory is removed**. Use `src/strategies/` functions instead.
