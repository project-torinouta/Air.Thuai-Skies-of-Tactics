<div align="center">
  <img src="assets/banner.png" />
  <h1>THUAI-9: Skies of Tactics</h1>

[![build](https://img.shields.io/github/actions/workflow/status/project-torinouta/Air.Thuai-Skies-of-Tactics/nightly.yml?label=nightly)](https://github.com/AshGreyG/Obsino/actions/workflows/nightly.yml)
[![Typst](https://img.shields.io/badge/Typst-239DAD?logo=typst&logoColor=fff)](https://typst.app/)
[![Nix](https://img.shields.io/badge/Nix-5277C3?logo=nixos&logoColor=fff)](https://nixos.org/)
[![MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

A turn-based grid strategy game where AI-controlled pieces compete in tactical
combat. Contestants write Python strategies (initialization + per-turn actions)
to compete on the Saiblo platform.

## Rules

- [Game Rules (English)](docs/rules/game.en.md)
- [Game Rules (中文)](docs/rules/game.zh.md)
- [API Reference (English)](docs/rules/api.en.md)
- [API Reference (中文)](docs/rules/api.zh.md)
- [Ranking Rules (English)](docs/rules/rank.en.md)
- [Ranking Rules (中文)](docs/rules/rank.zh.md)

## Quick Start

```bash
cd src
uv run local_client.py --mode function --strategy aggressive
```

### Options

| Flag                 | Description                                           |
| -------------------- | ----------------------------------------------------- |
| `--mode`             | `local` (console two-player) or `function` (AI vs AI) |
| `--strategy`         | `aggressive`, `defensive`, or `mcts`                  |
| `--board`            | Path to board file (default: `./BoardCase/case1.txt`) |
| `--mcts-simulations` | MCTS simulation count (default: 25)                   |

### Writing Your Own Strategy

Create a new module in `src/strategies/` following the existing pattern:

```python
from strategies.aggressive import get_aggressive_action_strategy
```

See [`docs/rules/api.en.md`](docs/rules/api.en.md) for the full API reference.

## Project Structure

```
src/
├── utils.py            # Core data types
├── env.py              # Game engine
├── saiblo_client.py    # Saiblo protocol
├── json_converter.py   # State serialisation
├── strategy_utils.py   # Public AI helpers
├── local_input.py      # Input dispatch
├── local_client.py     # Local entry point
├── main.py             # Saiblo entry point
├── board_visual.py     # Terminal rendering
├── pyproject.toml      # Config (ruff, mypy)
└── strategies/         # Built-in strategies
    ├── aggressive.py
    ├── defensive.py
    ├── mcts.py
    ├── alpha_beta.py
    └── random.py
```

## Commit Convention

This project uses **gitmoji + conventional commits**:

```
:emoji: type(scope): short description
```

| Emoji                | Type            | Use case                      |
| -------------------- | --------------- | ----------------------------- |
| `:tada:`             | `feat`          | Initial project / major start |
| `:package:`          | `feat`          | New feature or dependency     |
| `:snowflake:`        | `fix`           | Bug fix                       |
| `:recycle:`          | `refactor`      | Code restructuring            |
| `:art:`              | `style`/`chore` | Formatting, lint              |
| `:page_facing_up:`   | `chore`         | License headers               |
| `:see_no_evil:`      | `chore`         | gitignore                     |
| `:memo:`             | `docs`          | Documentation                 |
| `:white_check_mark:` | `test`          | Tests                         |

See `.claude/skills/commit-message/SKILL.md` for the full list.
