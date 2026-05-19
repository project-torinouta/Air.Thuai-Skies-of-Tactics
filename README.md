<div align="center">
  <img src="assets/banner.png" alt="THUAI9 Skies of Tactics" />

  <h1>⚔️ Skies of Tactics</h1>
  <p><em>Turn-based AI competition game — write Python strategies, compete on Saiblo</em></p>

  <!-- Badges -->
  <p>
    <a href="https://github.com/project-torinouta/Air.Thuai-Skies-of-Tactics/actions/workflows/nightly.yml">
      <img src="https://img.shields.io/github/actions/workflow/status/project-torinouta/Air.Thuai-Skies-of-Tactics/nightly.yml?label=nightly&style=flat-square&logo=github" alt="build" />
    </a>
    <a href="https://github.com/project-torinouta/Air.Thuai-Skies-of-Tactics/releases">
      <img src="https://img.shields.io/github/v/release/project-torinouta/Air.Thuai-Skies-of-Tactics?style=flat-square&logo=semver" alt="release" />
    </a>
    <a href="https://nixos.org/">
      <img src="https://img.shields.io/badge/Nix-5277C3?style=flat-square&logo=nixos&logoColor=fff" alt="Nix" />
    </a>
    <a href="https://www.python.org/">
      <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=fff" alt="python" />
    </a>
    <a href="LICENSE">
      <img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square" alt="MIT" />
    </a>
  </p>
</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Game Rules](#-game-rules)
- [Quick Start](#-quick-start)
- [Strategies](#-strategies)
- [Project Structure](#-project-structure)
- [Development](#-development)
- [Benchmark Results](#-benchmark-results)
- [Commit Convention](#-commit-convention)
- [License](#-license)

---

## 🎯 Overview

**Skies of Tactics** is a turn-based grid strategy game for the [THUAI9](https://saiblo.net) competition. Two players each control 3 pieces on a 20×20 board, making tactical decisions every turn — move, attack, or cast spells.

Contestants write **Python strategies** that compete on the Saiblo platform. The project provides:

- ✅ A full game engine with pathfinding, combat, and spell systems
- ✅ Multiple built-in AI strategies for study and comparison
- ✅ Local testing tools for rapid iteration
- ✅ Nix-based reproducible builds and PDF documentation
- ✅ **40+ game replays** from Saiblo for strategy analysis

---

## 📖 Game Rules

<div align="center">

| English                                | 中文                              |
| -------------------------------------- | --------------------------------- |
| [Game Rules](docs/rules/game.en.md)    | [游戏规则](docs/rules/game.zh.md) |
| [API Reference](docs/rules/api.en.md)  | [API 参考](docs/rules/api.zh.md)  |
| [Ranking Rules](docs/rules/rank.en.md) | [排名规则](docs/rules/rank.zh.md) |

</div>

### Key Mechanics

- **3 pieces per player**, each with 30 attribute points (STR / DEX / INT)
- **Equipment**: weapon (1–4) + armour (1–3) define damage, range, and resist
- **Action Points**: STR thresholds determine AP per turn (≤13→1, ≤21→2, >21→3)
- **Spell slots**: INT thresholds (≤12→1, ≤16→2, ≤21→3, >21→5)
- **Movement**: Manhattan-based, with A\* pathfinding
- **Win condition**: eliminate all 3 enemy pieces

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Nix](https://nixos.org/) (optional, for builds)

### Run a Local AI Battle

```bash
cd src
uv run local_client.py --mode function --strategy sniper
```

### Run the Benchmark

```bash
cd src
uv run benchmark.py --p1 sniper --p2 aggressive --rounds 30 --board-dir BoardCase/ --seed 42
```

### Build Artifacts (with Nix)

```bash
nix run .#clean
nix run .#build      # → build/nightly-latest.zip
nix run .#documents   # → build/*.pdf (7 strategy docs)
```

### Command-Line Options

| Flag            | Description                                                          |
| --------------- | -------------------------------------------------------------------- |
| `--mode`        | `local` (two-player console) or `function` (AI vs AI)                |
| `--strategy`    | `aggressive`, `defensive`, `tactical`, `warrior`, `ranger`, `sniper` |
| `--board`       | Path to board file (default: `./BoardCase/case1.txt`)                |
| `--p1` / `--p2` | Strategies for head-to-head benchmark                                |

### Writing Your Own Strategy

Create a new module in `src/strategies/` implementing two factory functions:

```python
from env import Environment, InitGameMessage
from utils import ActionSet, PieceArg

def get_my_init_strategy():
    def strategy(msg: InitGameMessage) -> list[PieceArg]:
        # Return 3 PieceArgs with your stat allocation
        ...

    return strategy

def get_my_action_strategy():
    def strategy(env: Environment) -> ActionSet:
        # Return one ActionSet per turn
        ...

    return strategy
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
| **ML Sniper**     | `ml_sniper.py`   | STR 29, DEX 1, bow+heavy | ES-optimised tactics     |  **55%**   |
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
│   ├── ml/                   # ML pipeline (ES-optimised policy)
│   │   ├── state_encoder.py  #   Environment → feature vector
│   │   ├── policy_net.py     #   2-layer NN in pure NumPy
│   │   ├── action_decoder.py #   Network output → ActionSet
│   │   ├── es_optimizer.py   #   Diagonal CMA-ES
│   │   └── train_evolution.py#   Training script
│   └── strategies/         # Built-in AI strategies
│       ├── ml_sniper.py    # ★ ES-optimised: ~55% win rate vs optimal
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

| Emoji         | Type       | Use Case                |
| ------------- | ---------- | ----------------------- |
| `:unicorn:`   | `feat`     | New feature or strategy |
| `:bug:`       | `fix`      | Bug fix                 |
| `:memo:`      | `docs`     | Documentation           |
| `:test_tube:` | `test`     | Tests                   |
| `:fire:`      | `chore`    | Benchmark / cleanup     |
| `:recycle:`   | `refactor` | Code restructuring      |
| `:art:`       | `style`    | Formatting              |
| `:bookmark:`  | `release`  | Version bump            |

See `.claude/skills/commit-message/SKILL.md` for the full list.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  <sub>Built with ❤️ for the THUAI9 competition · Saiblo platform</sub>
  <br />
  <sub>
    <a href="https://github.com/project-torinouta/Air.Thuai-Skies-of-Tactics">GitHub</a> ·
    <a href="https://github.com/project-torinouta/Air.Thuai-Skies-of-Tactics/releases">Releases</a> ·
    <a href="https://github.com/project-torinouta/Air.Thuai-Skies-of-Tactics/issues">Issues</a>
  </sub>
</div>
