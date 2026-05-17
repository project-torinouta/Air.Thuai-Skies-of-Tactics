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
and reports win/loss/draw statistics.

Usage:
    python benchmark.py                              # Full round-robin, 10 rounds each
    python benchmark.py --rounds 50                  # 50 games per matchup
    python benchmark.py --p1 aggressive --p2 defensive  # Single matchup
    python benchmark.py --p1 mcts --p2 alpha_beta --mcts-simulations 25 --alpha-beta-depth 4
"""

import argparse
import contextlib
import itertools
import os
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
from utils import ActionSet, PieceArg

StrategyPair = Tuple[Callable[..., List[PieceArg]], Callable[..., ActionSet]]

STRATEGY_NAMES: List[str] = [
    "aggressive",
    "defensive",
    "mcts",
    "alpha_beta",
    "random",
]


def get_strategy_pair(
    name: str,
    mcts_simulations: int = 10,
    alpha_beta_depth: int = 3,
) -> StrategyPair:
    """Resolve a strategy name to an (init_fn, action_fn) pair.

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
    if name == "aggressive":
        return (get_aggressive_init_strategy(), get_aggressive_action_strategy())
    if name == "defensive":
        return (get_defensive_init_strategy(), get_defensive_action_strategy())
    if name == "mcts":
        return (
            get_defensive_init_strategy(),
            get_mcts_action_strategy(mcts_simulations),
        )
    if name == "alpha_beta":
        return (
            get_defensive_init_strategy(),
            get_alpha_beta_action_strategy(alpha_beta_depth),
        )
    if name == "random":
        return (get_random_init_strategy(), get_random_action_strategy())
    raise ValueError(f"Unknown strategy: {name}")


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
    board_file: str,
    p1_name: str,
    p2_name: str,
    strategies: Dict[str, StrategyPair],
    rounds: int,
    max_rounds: int,
) -> Tuple[int, int, int]:
    """Run multiple games between two named strategies.

    Prints a progress dot per game.

    :param board_file: Path to the board definition file.
    :type board_file: str
    :param p1_name: Name of the player 1 strategy.
    :type p1_name: str
    :param p2_name: Name of the player 2 strategy.
    :type p2_name: str
    :param strategies: Mapping of names to strategy pairs.
    :type strategies: Dict[str, StrategyPair]
    :param rounds: Number of games to play.
    :type rounds: int
    :param max_rounds: Max game rounds before timeout.
    :type max_rounds: int
    :returns: (p1_wins, p2_wins, draws) counts.
    :rtype: Tuple[int, int, int]
    """
    p1_pair = strategies[p1_name]
    p2_pair = strategies[p2_name]

    p1_wins = 0
    p2_wins = 0
    draws = 0

    for _ in range(rounds):
        result = run_single_game(board_file, p1_pair, p2_pair, max_rounds)
        if result == 1:
            p1_wins += 1
        elif result == 2:
            p2_wins += 1
        elif result == 0:
            draws += 1

        sys.stdout.write(".")
        sys.stdout.flush()

    return p1_wins, p2_wins, draws


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
            "  python benchmark.py                        # Round-robin, 10 games each\n"
            "  python benchmark.py --rounds 50            # 50 games per matchup\n"
            "  python benchmark.py --p1 aggressive --p2 defensive\n"
            "  python benchmark.py --p1 mcts --p2 alpha_beta \\\n"
            "      --mcts-simulations 25 --alpha-beta-depth 4"
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
        help="Path to the board file (default: ./BoardCase/case1.txt)",
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
        help="Player 1 strategy (omit for full round-robin)",
    )
    parser.add_argument(
        "--p2",
        type=str,
        choices=STRATEGY_NAMES,
        help="Player 2 strategy (omit for full round-robin)",
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
        "--verbose",
        action="store_true",
        help="Show game output during benchmark",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the benchmark."""
    args = parse_args()

    board_file = args.board if args.board is not None else "./BoardCase/case1.txt"

    strategies: Dict[str, StrategyPair] = {
        name: get_strategy_pair(
            name,
            mcts_simulations=args.mcts_simulations,
            alpha_beta_depth=args.alpha_beta_depth,
        )
        for name in STRATEGY_NAMES
    }

    print(f"THUAI9 Strategy Benchmark")
    print(f"Board: {board_file}")
    print(f"Games per matchup: {args.rounds}")
    print(f"Max in-game rounds: {args.max_game_rounds}")
    print()

    if args.p1 and args.p2:
        print(f"Matchup: {args.p1} (P1) vs {args.p2} (P2)")
        print("Progress: ", end="", flush=True)
        p1_wins, p2_wins, draws = run_matchup(
            board_file,
            args.p1,
            args.p2,
            strategies,
            args.rounds,
            args.max_game_rounds,
        )
        results = {(args.p1, args.p2): (p1_wins, p2_wins, draws)}
        print_results_table(results)
    else:
        print("Running round-robin benchmark...")
        all_results: Dict[Tuple[str, str], Tuple[int, int, int]] = {}

        for p1_name, p2_name in itertools.permutations(STRATEGY_NAMES, 2):
            sys.stdout.write(f"  {p1_name:>12s} vs {p2_name:<12s} ")
            sys.stdout.flush()
            p1_wins, p2_wins, draws = run_matchup(
                board_file,
                p1_name,
                p2_name,
                strategies,
                args.rounds,
                args.max_game_rounds,
            )
            all_results[(p1_name, p2_name)] = (p1_wins, p2_wins, draws)
            print(f" {p1_wins}-{p2_wins}-{draws}")

        print_results_table(all_results)
        print_win_rate_summary(all_results, STRATEGY_NAMES)


if __name__ == "__main__":
    main()
