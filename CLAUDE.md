# THUAI9 Skies of Tactics — Project Context

## Overview

THUAI9 苍穹棋域 (Skies of Tactics) is a turn-based AI competition game where two
players control 3 pieces each on a grid board. Contestants write Python
strategies (initialization + per-turn actions) to compete.

The game has been stat-solved: **STR 29 / DEX 1, bow + heavy armour, advance-and-attack**
is the Pareto-optimal physical build confirmed by benchmarks and 40+ Saiblo
replays. See `src/strategies/sniper.py`.

## Project Structure

```
docs/
├── rules/              # Game rules, API docs, ranking rules (zh/en bilingual)
│   ├── api.zh.md / api.en.md
│   ├── game.zh.md / game.en.md
│   └── rank.zh.md / rank.en.md
├── reference/          # Additional reference materials (TBD)
└── strategies/         # Strategy documentation (.typ)
    ├── aggressive.typ
    ├── defensive.typ
    ├── mcts.typ
    ├── alpha_beta.typ
    ├── tactical.typ
    ├── warrior.typ
    └── sniper.typ

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
├── benchmark.py        # Head-to-head strategy benchmark
├── pyproject.toml      # Project config with ruff/mypy
├── BoardCase/          # Board definition files
└── strategies/         # Built-in strategies (one file per variant)
    ├── aggressive.py   # Close-range rush strategy
    ├── defensive.py    # Ranged kiting strategy
    ├── mcts.py         # Monte Carlo Tree Search (benchmark only)
    ├── alpha_beta.py   # Alpha-Beta pruning search (benchmark only)
    ├── random.py       # Random delegation
    ├── tactical.py     # Mage kiting strategy
    ├── warrior.py      # Warrior + Ranger melee/ranged burst
    ├── sniper.py       # STR 29 / DEX 1 bow + heavy, advance-and-attack (optimal)
├── sniper_v103.py  # Original STR 30 baseline (comparison)
    ├── sniper_v102.py  # STR 28 baseline (for comparison benchmarking)
    └── _utils.py       # Shared helpers (positioning, distance)

script/
├── run_benchmark.sh    # Benchmark runner (nix-based)
├── get_replays.py      # Download replays from Saiblo API
└── get_ai_tokens.py    # Scrape AI tokens from rank list

cli/                    # Nix build outputs (gitignored)
benchmark/              # Benchmark result markdown files
replay/                 # Downloaded Saiblo replay JSONs
changelog/              # Version marker files
```

## Build System

Uses Nix flakes for reproducible builds:

```bash
nix run .#clean          # Remove build/
nix run .#build          # Zip src/ → build/nightly-latest.zip
nix run .#documents      # Compile all .typ → PDFs in build/
```

## Release Workflow

The `release` skill (`/.claude/skills/release/`) automates the full release:

1. `nix run .#clean && nix run .#build && nix run .#documents`
2. Rename `build/nightly-latest.zip` → `build/v<VERSION>.zip`
3. `git tag v<VERSION>` and `gh release create` with zip + all PDFs

See `.claude/skills/release/SKILL.md`.

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
  `from strategies.sniper import get_sniper_action_strategy`.
- **StrategyFactory is removed**. Use `src/strategies/` functions instead.
