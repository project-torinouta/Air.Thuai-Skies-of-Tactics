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

---

## 🤖 Strategies

The project includes **7 built-in strategies** ranging from simple to optimised:

| Strategy          | File             | Build                    | Role                     | Win Rate\* |
| ----------------- | ---------------- | ------------------------ | ------------------------ | :--------: |
| **Sniper** 🏆     | `sniper.py`      | STR 29, DEX 1, bow+heavy | Refined initiative tank  |  **100%**  |
| **Sniper v1.0.3** | `sniper_v103.py` | STR 30, bow+heavy        | Original STR 30 baseline |     —      |
| **Sniper v1.0.2** | `sniper_v102.py` | STR 28, bow+heavy        | Previous optimum         |     —      |
| **Warrior**       | `warrior.py`     | STR 24, shortsword+light | Melee burst              |   0–90%    |
| **Ranger**        | `warrior.py`     | STR 22, bow+light        | Ranged damage            |  13–100%   |
| **Tactical**      | `tactical.py`    | STR 14, staff+light      | Mage kiting              |   0–17%    |
| **Aggressive**    | `aggressive.py`  | STR 20, shortsword+heavy | Rush damage              |   0–100%   |
| **Defensive**     | `defensive.py`   | DEX-heavy kiting         | Avoidance                |   0–100%   |

_\*Win rates vs other strategies on the standard 31-board benchmark._

### The Optimal Build

After analysing 40+ Saiblo replays and running 31-board benchmarks, the
game is **stat-solved** — the optimal build is:

```python
arg.strength = 29       # 108 HP, 22 damage/hit
arg.dexterity = 1        # +1 initiative for turn-order advantage
arg.intelligence = 0     # No spells — pure damage
arg.equip = Point(3, 3)  # Bow (range 9) + Heavy armour (23 resist)
```

Key insight: bow physical damage scales with STR, heavy armour caps incoming
damage, and no spell or mechanic in the game bypasses this trade. The 29 STR
/ 1 DEX split trades 2 HP and 1 damage for +1 initiative (d10+DEX turn
order) and +1 movement — a net positive in mirror matchups.

---

## 📁 Project Structure

```
.
├── src/                    # Python source
│   ├── env.py              # Game engine (board, combat, spells)
│   ├── utils.py            # Core types (Point, ActionSet, Spell, ...)
│   ├── strategy_utils.py   # Public AI helpers
│   ├── benchmark.py        # Head-to-head benchmark runner
│   ├── local_client.py     # Local CLI entry point
│   ├── main.py             # Saiblo competition entry point
│   ├── saiblo_client.py    # Saiblo protocol handler
│   ├── json_converter.py   # State serialisation
│   ├── pyproject.toml      # Ruff, mypy config
│   ├── BoardCase/          # Board definition files
│   └── strategies/         # Built-in AI strategies
│       ├── sniper.py       # ★ Optimal: STR 29/DEX 1, bow+heavy
│       ├── aggressive.py   # Rush damage
│       ├── defensive.py    # Kiting
│       ├── tactical.py     # Mage
│       ├── warrior.py      # Warrior + Ranger
│       ├── mcts.py         # Monte Carlo Tree Search
│       ├── alpha_beta.py   # Alpha-Beta pruning
│       └── random.py       # Random
├── docs/
│   ├── rules/              # Game rules (zh + en)
│   └── strategies/         # Strategy documentation (.typ)
├── script/                 # Utility scripts
│   ├── run_benchmark.sh    # Automated benchmark runner
│   └── get_replays.py      # Download Saiblo replays
├── benchmark/              # Benchmark result markdown files
├── replay/                 # Downloaded Saiblo replay JSONs
├── claude/                 # AI skills (release, create-pr, ...)
├── flake.nix               # Nix build configuration
├── CLAUDE.md               # AI assistant context
└── README.md               # This file
```

---

## 🛠 Development

### Nix Build System

```bash
nix run .#clean            # Remove build directory
nix run .#build            # Build zip of src/
nix run .#documents        # Compile all .typ to PDFs
```

### Run All Tests

```bash
cd src && uv run python -m unittest discover -s ../tests -p 'test_*.py'
```

**254 tests** across game logic, strategy utils, search algorithms, and strategy-specific suites.

### Create a Release

```bash
/release                    # Uses the project's release skill
```

The `release` skill tags the current commit, builds artifacts via Nix, and
creates a GitHub release with the zip + all strategy PDFs.

### Download Replays

```bash
export SAIBLO_TOKEN="your_token"
uv run script/get_replays.py
```

---

## 📊 Benchmark Results

All results from the standard 31-board benchmark (30 games per matchup, max 60 rounds, seed 42).

### Sniper vs All Opponents

| Opponent   | Sniper Wins | Losses | Draws | Win Rate |
| ---------- | :---------: | :----: | :---: | :------: |
| Aggressive |     30      |   0    |   0   | **100%** |
| Defensive  |     30      |   0    |   0   | **100%** |
| Warrior    |     30      |   0    |   0   | **100%** |
| Ranger     |     30      |   0    |   0   | **100%** |
| Tactical   |     30      |   0    |   0   | **100%** |

### Sniper v2 vs v1.0.2

| Matchup    | v2 Wins | v102 Wins | Draws | v2 Win%  |
| ---------- | :-----: | :-------: | :---: | :------: |
| v2 vs v102 |   30    |     0     |   0   | **100%** |
| v102 vs v2 |   30    |     0     |   0   | **100%** |

> The sniper upgrade (STR 28 → 30, + advance-and-attack) achieves a decisive
> **100% win rate** against the previous version.

---

## 💬 Commit Convention

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
