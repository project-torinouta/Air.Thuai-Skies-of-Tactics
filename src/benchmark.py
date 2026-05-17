# Copyright 2026 AshGrey <ashgrey.huaier@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in the
# Software without restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the
# following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Benchmark script for comparing AI strategies head-to-head.

Runs multiple games between strategy pairings (single or round-robin)
and reports win/loss/draw statistics. Supports multiple board files
and random board generation.

Usage:
    python benchmark.py                                 # Full round-robin, 10 rounds each
    python benchmark.py --rounds 50                     # 50 games per matchup
    python benchmark.py --p1 aggressive --p2 defensive  # Single matchup
    python benchmark.py --board-dir BoardCase/          # Use all boards in directory
    python benchmark.py --generate-boards 20            # Generate 20 random boards
    python benchmark.py --generate-boards 10 --board-rows 16 --board-cols 16
"""

import argparse
import contextlib
import glob
import itertools
import os
import random
import sys
from typing import Callable, Dict, List, Optional, Tuple

from env import Environment
from strategies.aggressive import (
    get_aggressive_action_strategy,
    get_aggressive_init_strategy,
)
from strategies.alpha_beta import get_alpha_beta_action_strategy
from strategies.defensive import (
    get_defensive_action_strategy,
    get_defensive_init_strategy,
)
from strategies.mcts import get_mcts_action_strategy
from strategies.random import (
    get_random_action_strategy,
    get_random_init_strategy,
)
from strategies.tactical import (
    get_tactical_action_strategy,
    get_tactical_init_strategy,
)
from strategies.warrior import (
    get_warrior_action_strategy,
    get_warrior_init_strategy,
    get_ranger_action_strategy,
    get_ranger_init_strategy,
)
from utils import ActionSet, PieceArg

StrategyPair = Tuple[Callable[..., List[PieceArg]], Callable[..., ActionSet]]

STRATEGY_NAMES: List[str] = [
    "aggressive",
    "defensive",
    "mcts",
    "alpha_beta",
    "tactical",
    "warrior",
    "ranger",
    "random",
]

INIT_NAMES: List[str] = [
    "aggressive",
    "defensive",
    "tactical",
    "warrior",
    "ranger",
    "random",
]

ACTION_NAMES: List[str] = [
    "aggressive",
    "defensive",
    "mcts",
    "alpha_beta",
    "tactical",
    "warrior",
    "ranger",
    "random",
]

_GENERATED_BOARD_DIR: str = "BoardCase"


def get_init_strategy(name: str) -> Callable[..., List[PieceArg]]:
    """Resolve a strategy name to an init strategy callable.

    :param name: Strategy name from INIT_NAMES.
    :type name: str
    :returns: An initialisation strategy callable.
    :rtype: Callable
    :raises ValueError: If the name is unknown.
    """
    if name == "aggressive":
        return get_aggressive_init_strategy()
    if name == "defensive":
        return get_defensive_init_strategy()
    if name == "tactical":
        return get_tactical_init_strategy()
    if name == "warrior":
        return get_warrior_init_strategy()
    if name == "ranger":
        return get_ranger_init_strategy()
    if name == "random":
        return get_random_init_strategy()
    raise ValueError(f"Unknown init strategy: {name}")


def get_action_strategy(
    name: str,
    mcts_simulations: int = 10,
    alpha_beta_depth: int = 3,
) -> Callable[..., ActionSet]:
    """Resolve a strategy name to an action strategy callable.

    :param name: Strategy name from ACTION_NAMES.
    :type name: str
    :param mcts_simulations: MCTS simulation count (only for mcts). Defaults to 10.
    :type mcts_simulations: int
    :param alpha_beta_depth: Alpha-beta search depth (only for alpha_beta).
        Defaults to 3.
    :type alpha_beta_depth: int
    :returns: An action strategy callable.
    :rtype: Callable
    :raises ValueError: If the name is unknown.
    """
    if name == "aggressive":
        return get_aggressive_action_strategy()
    if name == "defensive":
        return get_defensive_action_strategy()
    if name == "mcts":
        return get_mcts_action_strategy(mcts_simulations)
    if name == "alpha_beta":
        return get_alpha_beta_action_strategy(alpha_beta_depth)
    if name == "tactical":
        return get_tactical_action_strategy()
    if name == "warrior":
        return get_warrior_action_strategy()
    if name == "ranger":
        return get_ranger_action_strategy()
    if name == "random":
        return get_random_action_strategy()
    raise ValueError(f"Unknown action strategy: {name}")


def get_strategy_pair(
    name: str,
    mcts_simulations: int = 10,
    alpha_beta_depth: int = 3,
) -> StrategyPair:
    """Resolve a strategy name to an (init_fn, action_fn) pair.

    Uses the strategy's own init when available, otherwise falls back
    to defensive init.  This is kept for round-robin mode.

    :param name: Strategy name from STRATEGY_NAMES.
    :type name: str
    :param mcts_simulations: MCTS simulation count (only for mcts). Defaults to 10.
    :type mcts_simulations: int
    :param alpha_beta_depth: Alpha-beta search depth (only for alpha_beta).
        Defaults to 3.
    :type alpha_beta_depth: int
    :returns: A tuple of (init_strategy, action_strategy) callables.
    :rtype: StrategyPair
    :raises ValueError: If the strategy name is unknown.
    """
    if name in INIT_NAMES:
        init_fn = get_init_strategy(name)
    else:
        init_fn = get_defensive_init_strategy()
    return (init_fn, get_action_strategy(name, mcts_simulations, alpha_beta_depth))


# ---------------------------------------------------------------------------
# Board discovery and generation
# ---------------------------------------------------------------------------


def _make_grid(
    rows: int,
    cols: int,
    obstacle_density: float,
    border: int,
) -> List[List[int]]:
    """Generate a random grid of cell states for a board.

    Produces a ``rows x cols`` grid where most cells are walkable (1) and
    some are blocked (-1).  Guarantees at least 15 walkable cells on each
    side of the border so that pieces can be placed.

    :param rows: Number of rows in the grid.
    :type rows: int
    :param cols: Number of columns in the grid.
    :type cols: int
    :param obstacle_density: Probability that a cell is blocked.
    :type obstacle_density: float
    :param border: The y-coordinate of the border (split between players).
    :type border: int
    :returns: A 2D list of cell states (1 = walkable, -1 = blocked).
    :rtype: List[List[int]]
    """
    grid: List[List[int]] = [
        [1 for _ in range(rows)] for _ in range(cols)
    ]

    for x in range(cols):
        for y in range(rows):
            if random.random() < obstacle_density:
                grid[x][y] = -1

    for half_border in (border, rows):
        half_start = 0 if half_border == border else border + 1
        blocked = [
            (x, y)
            for x in range(cols)
            for y in range(half_start, half_border)
            if grid[x][y] == -1
        ]
        open_cnt = cols * (half_border - half_start) - len(blocked)
        needed = max(0, 15 - open_cnt)
        for x, y in blocked[:needed]:
            grid[x][y] = 1

    return grid


def _make_height_map(rows: int, cols: int) -> List[List[int]]:
    """Generate a random height map using a simple smoothing approach.

    Heights range from 0 to 3.

    :param rows: Number of rows.
    :type rows: int
    :param cols: Number of columns.
    :type cols: int
    :returns: A 2D list of height values.
    :rtype: List[List[int]]
    """
    heights: List[List[int]] = [
        [random.randint(0, 3) for _ in range(rows)] for _ in range(cols)
    ]

    for _ in range(2):
        smoothed: List[List[int]] = [
            [0 for _ in range(rows)] for _ in range(cols)
        ]
        for x in range(cols):
            for y in range(rows):
                neighbors = [heights[x][y]]
                if x > 0:
                    neighbors.append(heights[x - 1][y])
                if x < cols - 1:
                    neighbors.append(heights[x + 1][y])
                if y > 0:
                    neighbors.append(heights[x][y - 1])
                if y < rows - 1:
                    neighbors.append(heights[x][y + 1])
                smoothed[x][y] = round(sum(neighbors) / len(neighbors))
        heights = smoothed

    return heights


def generate_random_board(
    file_path: str,
    rows: int = 20,
    cols: int = 20,
    obstacle_density: float = 0.1,
) -> None:
    """Generate a random board file at the given path.

    The board is created with walkable cells and randomly placed obstacles.
    The border is placed at ``rows // 2``.

    :param file_path: Output path for the board file.
    :type file_path: str
    :param rows: Number of rows. Defaults to 20.
    :type rows: int
    :param cols: Number of columns. Defaults to 20.
    :type cols: int
    :param obstacle_density: Probability a cell is blocked (0.0-1.0).
        Defaults to 0.1.
    :type obstacle_density: float
    """
    border = rows // 2
    grid = _make_grid(rows, cols, obstacle_density, border)
    heights = _make_height_map(rows, cols)

    with open(file_path, "w") as f:
        f.write(f"{cols} {rows}\n\n")
        for y in range(rows):
            f.write(", ".join(str(grid[x][y]) for x in range(cols)) + "\n")
        f.write("\n")
        for y in range(rows):
            f.write(", ".join(str(heights[x][y]) for x in range(cols)) + "\n")


def resolve_boards(args: argparse.Namespace) -> List[str]:
    """Build the list of board file paths based on CLI arguments.

    Order of precedence:
    1. ``--board`` pointing to a single file.
    2. ``--board`` pointing to a directory (scans for ``*.txt``).
    3. ``--board-dir`` (scans for ``*.txt`` in that directory).
    4. ``--generate-boards N`` (creates N random boards).
    5. Default: ``./BoardCase/case1.txt``.

    :param args: Parsed command-line arguments.
    :type args: argparse.Namespace
    :returns: A list of board file paths.
    :rtype: List[str]
    """
    boards: List[str] = []

    if args.board is not None:
        if os.path.isdir(args.board):
            boards = sorted(glob.glob(os.path.join(args.board, "*.txt")))
            if not boards:
                print(
                    f"Warning: no .txt files found in {args.board}, "
                    f"using default board"
                )
        else:
            boards = [args.board]
    elif args.board_dir is not None:
        boards = sorted(glob.glob(os.path.join(args.board_dir, "*.txt")))
        if not boards:
            print(
                f"Warning: no .txt files found in {args.board_dir}, "
                f"using default board"
            )
    elif args.generate_boards > 0:
        os.makedirs(_GENERATED_BOARD_DIR, exist_ok=True)
        for i in range(args.generate_boards):
            path = os.path.join(_GENERATED_BOARD_DIR, f"generated_{i}.txt")
            generate_random_board(
                path,
                rows=args.board_rows,
                cols=args.board_cols,
                obstacle_density=args.obstacle_density,
            )
            boards.append(path)
        print(f"Generated {args.generate_boards} random board files ({args.board_cols}x{args.board_rows})")
        print(f"  Density: {args.obstacle_density}")
    else:
        default = "./BoardCase/case1.txt"
        if os.path.exists(default):
            boards = [default]

    if not boards:
        print("Warning: no board files found, using default ./BoardCase/case1.txt")
        boards = ["./BoardCase/case1.txt"]

    return boards


# ---------------------------------------------------------------------------
# Game execution
# ---------------------------------------------------------------------------


def run_single_game(
    board_file: str,
    p1_strategy: StrategyPair,
    p2_strategy: StrategyPair,
    max_rounds: int = 100,
    verbose: bool = False,
) -> int:
    """Run a single game between two strategy pairs and return the result.

    :param board_file: Path to the board definition file.
    :type board_file: str
    :param p1_strategy: (init, action) pair for player 1.
    :type p1_strategy: StrategyPair
    :param p2_strategy: (init, action) pair for player 2.
    :type p2_strategy: StrategyPair
    :param max_rounds: Maximum rounds before the game is stopped.
        Defaults to 100.
    :type max_rounds: int
    :param verbose: Whether to show game output (stdout). Defaults to False.
    :type verbose: bool
    :returns: 0 = draw, 1 = player 1 wins, 2 = player 2 wins, -1 = error.
    :rtype: int
    """
    env = Environment(local_mode=True, if_log=0)
    env.max_rounds = max_rounds

    p1_init, p1_action = p1_strategy
    p2_init, p2_action = p2_strategy

    env.input_manager.set_function_input_method(1, p1_init, p1_action)
    env.input_manager.set_function_input_method(2, p2_init, p2_action)

    try:
        if verbose:
            env.run(board_file)
        else:
            with open(os.devnull, "w") as devnull:
                with contextlib.redirect_stdout(devnull):
                    env.run(board_file)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return -1

    p1_alive = any(p.is_alive for p in env.player1.pieces)
    p2_alive = any(p.is_alive for p in env.player2.pieces)

    if p1_alive and not p2_alive:
        return 1
    if p2_alive and not p1_alive:
        return 2
    return 0


def run_matchup(
    board_files: List[str],
    p1_pair: StrategyPair,
    p2_pair: StrategyPair,
    rounds: int,
    max_rounds: int,
) -> Tuple[int, int, int]:
    """Run multiple games between two strategy pairs.

    A random board is selected from ``board_files`` for each game.
    Prints a progress dot per game.

    :param board_files: List of available board file paths.
    :type board_files: List[str]
    :param p1_pair: (init, action) for player 1.
    :type p1_pair: StrategyPair
    :param p2_pair: (init, action) for player 2.
    :type p2_pair: StrategyPair
    :param rounds: Number of games to play.
    :type rounds: int
    :param max_rounds: Max game rounds before timeout.
    :type max_rounds: int
    :returns: (p1_wins, p2_wins, draws) counts.
    :rtype: Tuple[int, int, int]
    """
    p1_wins = 0
    p2_wins = 0
    draws = 0

    for _ in range(rounds):
        board = random.choice(board_files)
        result = run_single_game(board, p1_pair, p2_pair, max_rounds)
        if result == 1:
            p1_wins += 1
        elif result == 2:
            p2_wins += 1
        elif result == 0:
            draws += 1

        sys.stdout.write(".")
        sys.stdout.flush()

    return p1_wins, p2_wins, draws


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def print_results_table(
    results: Dict[Tuple[str, str], Tuple[int, int, int]],
) -> None:
    """Print a formatted matchup results table.

    :param results: Mapping of (p1, p2) to (p1_wins, p2_wins, draws).
    :type results: Dict[Tuple[str, str], Tuple[int, int, int]]
    """
    max_name_len = max(
        len(f"{p1} vs {p2}") for p1, p2 in results
    )
    col_width = max(max_name_len + 2, 30)

    divider = "=" * 78
    print()
    print(divider)
    header = (
        f"{'Matchup':<{col_width}} {'P1 Wins':>8} {'P2 Wins':>8} "
        f"{'Draws':>6} {'P1 Win%':>8}"
    )
    print(header)
    print("-" * 78)

    for (p1_name, p2_name), (p1_wins, p2_wins, draws) in sorted(results.items()):
        total = p1_wins + p2_wins + draws
        pct = (p1_wins / total * 100) if total > 0 else 0.0
        label = f"{p1_name} vs {p2_name}"
        print(
            f"{label:<{col_width}} {p1_wins:>8d} {p2_wins:>8d} "
            f"{draws:>6d} {pct:>7.1f}%"
        )

    print(divider)


def print_win_rate_summary(
    all_results: Dict[Tuple[str, str], Tuple[int, int, int]],
    strategy_names: List[str],
) -> None:
    """Print overall win rate summary per strategy.

    Computes combined win rate across all matchups.
    Draws are treated as splits so that win % + loss % = 100%.

    :param all_results: Mapping of (p1, p2) to (p1_wins, p2_wins, draws).
    :type all_results: Dict[Tuple[str, str], Tuple[int, int, int]]
    :param strategy_names: Ordered list of strategy names.
    :type strategy_names: List[str]
    """
    total_wins: Dict[str, int] = {}
    total_losses: Dict[str, int] = {}
    total_draws: Dict[str, int] = {}

    for name in strategy_names:
        total_wins[name] = 0
        total_losses[name] = 0
        total_draws[name] = 0

    for (p1, p2), (w1, w2, d) in all_results.items():
        total_wins[p1] += w1
        total_losses[p1] += w2
        total_draws[p1] += d
        total_wins[p2] += w2
        total_losses[p2] += w1
        total_draws[p2] += d

    print()
    print("Overall Win Rate (all games combined):")
    print("-" * 50)
    print(f"{'Strategy':<15} {'Wins':>6} {'Losses':>8} {'Draws':>6} {'Win%':>8}")
    print("-" * 50)

    for name in strategy_names:
        w = total_wins[name]
        l = total_losses[name]
        d = total_draws[name]
        total = w + l + d
        pct = (w / total * 100) if total > 0 else 0.0
        print(f"{name:<15s} {w:>6d} {l:>8d} {d:>6d} {pct:>7.1f}%")

    print("-" * 50)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    :returns: Parsed arguments.
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="THUAI9 Strategy Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python benchmark.py                                   # Round-robin\n"
            "  python benchmark.py --rounds 50                       # 50 games each\n"
            "  python benchmark.py --p1 aggressive --p2 defensive    # Single matchup\n"
            "  python benchmark.py --board-dir BoardCase/            # Use dir boards\n"
            "  python benchmark.py --generate-boards 20              # Random boards\n"
            "  python benchmark.py --generate-boards 10 \\\n"
            "      --board-rows 16 --board-cols 16 --obstacle-density 0.15\n"
        ),
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=10,
        help="Number of games per matchup (default: 10)",
    )
    parser.add_argument(
        "--board",
        type=str,
        default=None,
        help=(
            "Path to a board file or a directory of board files. "
            "Default: ./BoardCase/case1.txt"
        ),
    )
    parser.add_argument(
        "--board-dir",
        type=str,
        default=None,
        help="Directory containing .txt board files (scanned at startup)",
    )
    parser.add_argument(
        "--generate-boards",
        type=int,
        default=0,
        help="Number of random boards to generate for the benchmark",
    )
    parser.add_argument(
        "--board-rows",
        type=int,
        default=20,
        help="Row count for generated boards (default: 20)",
    )
    parser.add_argument(
        "--board-cols",
        type=int,
        default=20,
        help="Column count for generated boards (default: 20)",
    )
    parser.add_argument(
        "--obstacle-density",
        type=float,
        default=0.1,
        help="Obstacle density for generated boards 0.0-1.0 (default: 0.1)",
    )
    parser.add_argument(
        "--max-game-rounds",
        type=int,
        default=100,
        help="Maximum in-game rounds before timeout (default: 100)",
    )
    parser.add_argument(
        "--p1",
        type=str,
        choices=STRATEGY_NAMES,
        help="Player 1 strategy (omit for full round-robin).  Sets both "
             "init and action; use --p1-init/--p1-action to override individually.",
    )
    parser.add_argument(
        "--p2",
        type=str,
        choices=STRATEGY_NAMES,
        help="Player 2 strategy (omit for full round-robin).  Sets both "
             "init and action; use --p2-init/--p2-action to override individually.",
    )
    parser.add_argument(
        "--p1-init",
        type=str,
        choices=INIT_NAMES,
        default=None,
        help="Player 1 init strategy (overrides --p1 for init)",
    )
    parser.add_argument(
        "--p1-action",
        type=str,
        choices=ACTION_NAMES,
        default=None,
        help="Player 1 action strategy (overrides --p1 for action)",
    )
    parser.add_argument(
        "--p2-init",
        type=str,
        choices=INIT_NAMES,
        default=None,
        help="Player 2 init strategy (overrides --p2 for init)",
    )
    parser.add_argument(
        "--p2-action",
        type=str,
        choices=ACTION_NAMES,
        default=None,
        help="Player 2 action strategy (overrides --p2 for action)",
    )
    parser.add_argument(
        "--mcts-simulations",
        type=int,
        default=10,
        help="MCTS iterations per decision (default: 10)",
    )
    parser.add_argument(
        "--alpha-beta-depth",
        type=int,
        default=3,
        help="Alpha-beta search depth (default: 3)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible benchmarks",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show game output during benchmark",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the benchmark."""
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    board_files = resolve_boards(args)

    strategies: Dict[str, StrategyPair] = {
        name: get_strategy_pair(
            name,
            mcts_simulations=args.mcts_simulations,
            alpha_beta_depth=args.alpha_beta_depth,
        )
        for name in STRATEGY_NAMES
    }

    board_desc: str
    if args.generate_boards > 0:
        board_desc = (
            f"{args.generate_boards} generated boards "
            f"({args.board_cols}x{args.board_rows}, "
            f"density={args.obstacle_density})"
        )
    elif len(board_files) == 1:
        board_desc = board_files[0]
    else:
        board_desc = f"{len(board_files)} boards from {os.path.dirname(board_files[0])}"

    print(f"THUAI9 Strategy Benchmark")
    print(f"Board: {board_desc}")
    print(f"Games per matchup: {args.rounds}")
    print(f"Max in-game rounds: {args.max_game_rounds}")
    if args.seed is not None:
        print(f"Random seed: {args.seed}")
    print()

    p1_init_name: Optional[str] = args.p1_init or args.p1
    p1_action_name: Optional[str] = args.p1_action or args.p1
    p2_init_name: Optional[str] = args.p2_init or args.p2
    p2_action_name: Optional[str] = args.p2_action or args.p2

    if p1_init_name and p1_action_name and p2_init_name and p2_action_name:
        p1_pair = (
            get_init_strategy(p1_init_name),
            get_action_strategy(
                p1_action_name,
                mcts_simulations=args.mcts_simulations,
                alpha_beta_depth=args.alpha_beta_depth,
            ),
        )
        p2_pair = (
            get_init_strategy(p2_init_name),
            get_action_strategy(
                p2_action_name,
                mcts_simulations=args.mcts_simulations,
                alpha_beta_depth=args.alpha_beta_depth,
            ),
        )

        p1_label = (
            f"{p1_init_name}+{p1_action_name}"
            if p1_init_name != p1_action_name
            else p1_init_name
        )
        p2_label = (
            f"{p2_init_name}+{p2_action_name}"
            if p2_init_name != p2_action_name
            else p2_init_name
        )

        print(f"Matchup: {p1_label} (P1) vs {p2_label} (P2)")
        print(f"  Init: P1={p1_init_name}, P2={p2_init_name}")
        print(f"  Action: P1={p1_action_name}, P2={p2_action_name}")
        print("Progress: ", end="", flush=True)
        p1_wins, p2_wins, draws = run_matchup(
            board_files,
            p1_pair,
            p2_pair,
            args.rounds,
            args.max_game_rounds,
        )
        results = {(p1_label, p2_label): (p1_wins, p2_wins, draws)}
        print_results_table(results)
    else:
        print("Running round-robin benchmark...")
        all_results: Dict[Tuple[str, str], Tuple[int, int, int]] = {}

        for p1_name, p2_name in itertools.permutations(STRATEGY_NAMES, 2):
            sys.stdout.write(f"  {p1_name:>12s} vs {p2_name:<12s} ")
            sys.stdout.flush()
            p1_wins, p2_wins, draws = run_matchup(
                board_files,
                strategies[p1_name],
                strategies[p2_name],
                args.rounds,
                args.max_game_rounds,
            )
            all_results[(p1_name, p2_name)] = (p1_wins, p2_wins, draws)
            print(f" {p1_wins}-{p2_wins}-{draws}")

        print_results_table(all_results)
        print_win_rate_summary(all_results, STRATEGY_NAMES)


if __name__ == "__main__":
    main()
