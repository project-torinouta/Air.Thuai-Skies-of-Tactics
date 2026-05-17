# Copyright 2026 saiblo platform <https://saiblo.net>
#
# This SDK copy is distributed from https://api.saiblo.net/api/games/56/download/,
# All rights reserved by saiblo platform. All I modified is translating the
# comment and document string from Chinese to English

"""Local Environment client (no gRPC / Saiblo).

Supports two modes:
- ``local``: both players use console input.
- ``function``: both players use AI strategy functions.
"""

import argparse

from env import Environment
from strategies.aggressive import (
    get_aggressive_init_strategy,
    get_aggressive_action_strategy,
)
from strategies.defensive import (
    get_defensive_init_strategy,
    get_defensive_action_strategy,
)
from strategies.alpha_beta import get_alpha_beta_action_strategy
from strategies.mcts import get_mcts_action_strategy
from strategies.sniper import (
    get_sniper_action_strategy,
    get_sniper_init_strategy,
)
from strategies.tactical import (
    get_tactical_action_strategy,
    get_tactical_init_strategy,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    :returns: Parsed arguments.
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="THUAI9 Local Environment Client"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["local", "function"],
        default="local",
        help="local=console input, function=AI strategy input",
    )
    parser.add_argument(
        "--board",
        type=str,
        default=None,
        help="Path to the board file (default: ./BoardCase/case1.txt)",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        choices=["aggressive", "defensive", "mcts", "alpha_beta", "tactical", "sniper"],
        default="aggressive",
        help="AI strategy to use in function mode",
    )
    parser.add_argument(
        "--mcts-simulations",
        type=int,
        default=25,
        help="MCTS simulation count when strategy=mcts",
    )
    parser.add_argument(
        "--alpha-beta-depth",
        type=int,
        default=3,
        help="Alpha-beta search depth when strategy=alpha_beta",
    )
    return parser.parse_args()


def _strategies_for(args: argparse.Namespace):
    """Return (init_strategy, action_strategy) for the given CLI args.

    :param args: Parsed command-line arguments.
    :type args: argparse.Namespace
    :returns: A tuple of (init_strategy, action_strategy) callables.
    :rtype: tuple
    """
    if args.strategy == "aggressive":
        return (
            get_aggressive_init_strategy(),
            get_aggressive_action_strategy(),
        )
    if args.strategy == "defensive":
        return (
            get_defensive_init_strategy(),
            get_defensive_action_strategy(),
        )
    if args.strategy == "alpha_beta":
        return (
            get_defensive_init_strategy(),
            get_alpha_beta_action_strategy(args.alpha_beta_depth),
        )
    if args.strategy == "tactical":
        return (
            get_tactical_init_strategy(),
            get_tactical_action_strategy(),
        )
    if args.strategy == "sniper":
        return (
            get_sniper_init_strategy(),
            get_sniper_action_strategy(),
        )
    init_s = get_defensive_init_strategy()
    action_s = get_mcts_action_strategy(args.mcts_simulations)
    return init_s, action_s


def main() -> None:
    """Main entry point for local client."""
    args = parse_args()
    env = Environment(local_mode=True)
    board_file = (
        args.board if args.board is not None else "./BoardCase/case1.txt"
    )

    if args.mode == "function":
        init_strategy, action_strategy = _strategies_for(args)
        env.input_manager.set_function_input_method(
            1, init_strategy, action_strategy
        )
        env.input_manager.set_function_input_method(
            2, init_strategy, action_strategy
        )
        print("=== Function-mode dual AI ===")
        print(f"Strategy: {args.strategy}, Board: {board_file}")
    else:
        print("=== Local console two-player mode ===")
        print(f"Board: {board_file}")

    try:
        env.run(board_file)
    except KeyboardInterrupt:
        print("\nGame interrupted by user.")
    except Exception as e:
        raise e


if __name__ == "__main__":
    main()
