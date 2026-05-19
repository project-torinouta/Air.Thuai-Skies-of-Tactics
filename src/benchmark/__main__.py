"""CLI entry point for the benchmark suite."""

import argparse
import itertools
import os
import random
import sys
from typing import Dict, List, Optional, Tuple

from benchmark import (
    ACTION_NAMES,
    INIT_NAMES,
    STRATEGY_NAMES,
    get_action_strategy,
    get_init_strategy,
    get_strategy_pair,
    StrategyPair,
)
from benchmark.board import resolve_boards
from benchmark.cache import load_results_cache, save_results_cache
from benchmark.chart import (
    aggregate_strategy_series,
    plot_first_blood_histogram,
    plot_game_length_histogram,
    plot_head_to_head,
    plot_survivor_count,
    plot_win_rate_curve,
    try_init_matplotlib,
)
from benchmark.report import print_results_table, print_win_rate_summary
from benchmark.runner import run_matchup_series
from benchmark.sweep import run_sweep


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
            "      --board-rows 16 --board-cols 16 "
            "--obstacle-density 0.15\n"
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
        help="Path to a board file or directory. Default: ./BoardCase/case1.txt",
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
        help="Player 1 strategy (omit for round-robin).",
    )
    parser.add_argument(
        "--p2",
        type=str,
        choices=STRATEGY_NAMES,
        help="Player 2 strategy (omit for round-robin).",
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
        "--chart",
        type=str,
        default=None,
        help="Save win-rate line chart to this file (e.g. benchmark.png)",
    )
    parser.add_argument(
        "--chart-only",
        type=str,
        default=None,
        help="Re-plot cached results to this file without re-running games",
    )
    parser.add_argument(
        "--matrix",
        type=str,
        default=None,
        help="Save head-to-head win-rate matrix (round-robin only, e.g. matrix.png)",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="*",
        default=None,
        help="Skip these strategies in round-robin (e.g. --exclude mcts alpha_beta)",
    )
    parser.add_argument(
        "--hist",
        type=str,
        default=None,
        help="Save game-length histogram (round-robin only, e.g. hist.png)",
    )
    parser.add_argument(
        "--first-blood",
        type=str,
        default=None,
        help="Save first-blood timing chart (round-robin only, e.g. first_blood.png)",
    )
    parser.add_argument(
        "--survivors",
        type=str,
        default=None,
        help="Save survivor-count chart (round-robin only, e.g. survivors.png)",
    )
    parser.add_argument(
        "--all-charts",
        type=str,
        default=None,
        help="Output directory for all chart types (e.g. benchmark/h2h)",
    )
    parser.add_argument(
        "--svg",
        action="store_true",
        default=False,
        help="Output SVG instead of PNG for --all-charts",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show game output during benchmark",
    )
    parser.add_argument(
        "--sweep",
        type=str,
        default=None,
        help="Output file for attribute-sweep heatmap (e.g. sweep.png)",
    )
    parser.add_argument(
        "--sweep-games",
        type=int,
        default=8,
        help="Games per (STR, INT) cell in sweep (default: 8)",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the benchmark."""
    args = parse_args()

    # --chart-only: re-plot from cache without running games
    if args.chart_only is not None:
        cached = load_results_cache()
        if cached is None:
            print("No cached results found. Run a benchmark first.")
            return
        if not try_init_matplotlib():
            print("matplotlib not installed. Install with: pip install matplotlib")
            return
        plot_win_rate_curve(cached, args.chart_only, "cached")
        return

    # Filter strategies when --exclude is given
    active_names = STRATEGY_NAMES
    if args.exclude:
        excluded = set(args.exclude)
        active_names = [n for n in STRATEGY_NAMES if n not in excluded]
        print(f"Excluded strategies: {', '.join(sorted(excluded))}")
        print(f"Active strategies ({len(active_names)}): {', '.join(active_names)}")
        print()

    if args.sweep is not None:
        if not try_init_matplotlib():
            print("matplotlib not installed. Install with: pip install matplotlib")
            return
        run_sweep(
            output=args.sweep,
            games_per_cell=args.sweep_games,
            max_rounds=args.max_game_rounds,
            board_files=resolve_boards(args),
        )
        return

    if args.seed is not None:
        random.seed(args.seed)

    board_files = resolve_boards(args)

    strategies: Dict[str, StrategyPair] = {
        name: get_strategy_pair(
            name,
            mcts_simulations=args.mcts_simulations,
            alpha_beta_depth=args.alpha_beta_depth,
        )
        for name in active_names
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
        board_desc = (
            f"{len(board_files)} boards from "
            f"{os.path.dirname(board_files[0])}"
        )

    print("THUAI9 Strategy Benchmark")
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
        _run_single_matchup(
            p1_init_name, p1_action_name,
            p2_init_name, p2_action_name,
            board_files, board_desc, args, strategies,
        )
    else:
        _run_round_robin(
            strategies, active_names, board_files, board_desc, args,
        )


def _run_single_matchup(
    p1_init_name: str,
    p1_action_name: str,
    p2_init_name: str,
    p2_action_name: str,
    board_files: List[str],
    board_desc: str,
    args: argparse.Namespace,
    strategies: Dict[str, StrategyPair],
) -> None:
    """Run a single P1 vs P2 matchup."""
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
    series = run_matchup_series(
        board_files, p1_pair, p2_pair,
        args.rounds, args.max_game_rounds,
    )
    p1_wins = sum(1 for r in series.results if r == 1)
    p2_wins = sum(1 for r in series.results if r == 2)
    draws = sum(1 for r in series.results if r == 0)
    print()
    results = {(p1_label, p2_label): (p1_wins, p2_wins, draws)}
    print_results_table(results)

    p1_series = [1 if r == 1 else 0 for r in series.results]
    p2_series = [1 if r == 2 else 0 for r in series.results]
    series: Dict[str, List[int]] = {
        f"{p1_label} (P1)": p1_series,
        f"{p2_label} (P2)": p2_series,
    }
    save_results_cache(series)

    if args.chart is not None:
        if try_init_matplotlib():
            plot_win_rate_curve(
                series, args.chart,
                f"{p1_label} vs {p2_label}  ({args.rounds} games)",
            )
        else:
            print("matplotlib not installed. Install with: pip install matplotlib")


def _run_round_robin(
    strategies: Dict[str, StrategyPair],
    strategy_names: List[str],
    board_files: List[str],
    board_desc: str,
    args: argparse.Namespace,
) -> None:
    """Run a full round-robin across all strategy pairs."""
    print("Running round-robin benchmark...")
    all_results: Dict[Tuple[str, str], Tuple[int, int, int]] = {}
    all_series: Dict[Tuple[str, str], List[int]] = {}
    all_lengths: Dict[Tuple[str, str], List[int]] = {}
    all_first_bloods: Dict[Tuple[str, str], List[int]] = {}
    all_survivors: Dict[Tuple[str, str], List[Tuple[int, int]]] = {}

    for p1_name, p2_name in itertools.permutations(strategy_names, 2):
        sys.stdout.write(f"  {p1_name:>12s} vs {p2_name:<12s} ")
        sys.stdout.flush()
        ms = run_matchup_series(
            board_files,
            strategies[p1_name],
            strategies[p2_name],
            args.rounds,
            args.max_game_rounds,
        )
        p1_wins = sum(1 for r in ms.results if r == 1)
        p2_wins = sum(1 for r in ms.results if r == 2)
        draws = sum(1 for r in ms.results if r == 0)
        all_results[(p1_name, p2_name)] = (p1_wins, p2_wins, draws)
        all_series[(p1_name, p2_name)] = ms.results
        all_lengths[(p1_name, p2_name)] = ms.lengths
        all_first_bloods[(p1_name, p2_name)] = ms.first_bloods
        all_survivors[(p1_name, p2_name)] = ms.survivors
        print(f" {p1_wins}-{p2_wins}-{draws}")

    print_results_table(all_results)
    print_win_rate_summary(all_results, strategy_names)

    if args.chart is not None:
        if try_init_matplotlib():
            strategy_curves = aggregate_strategy_series(
                all_series, strategy_names,
            )
            plot_win_rate_curve(strategy_curves, args.chart, board_desc)
        else:
            print("matplotlib not installed. Install with: pip install matplotlib")

    if args.matrix is not None:
        if try_init_matplotlib():
            plot_head_to_head(all_results, strategy_names, args.matrix, board_desc)
        else:
            print("matplotlib not installed. Install with: pip install matplotlib")

    if args.hist is not None:
        if try_init_matplotlib():
            plot_game_length_histogram(
                all_lengths, strategy_names, args.hist,
            )
        else:
            print("matplotlib not installed. Install with: pip install matplotlib")

    if args.first_blood is not None:
        if try_init_matplotlib():
            plot_first_blood_histogram(
                all_first_bloods, strategy_names, args.first_blood,
            )
        else:
            print("matplotlib not installed. Install with: pip install matplotlib")

    if args.survivors is not None:
        if try_init_matplotlib():
            plot_survivor_count(
                all_survivors, strategy_names, args.survivors,
            )
        else:
            print("matplotlib not installed. Install with: pip install matplotlib")

    if args.all_charts is not None:
        _export_all_charts(
            output_dir=args.all_charts,
            all_results=all_results,
            all_series=all_series,
            all_lengths=all_lengths,
            all_first_bloods=all_first_bloods,
            all_survivors=all_survivors,
            strategy_names=strategy_names,
            board_desc=board_desc,
            svg=args.svg,
        )


def _export_all_charts(
    output_dir: str,
    all_results: Dict[Tuple[str, str], Tuple[int, int, int]],
    all_series: Dict[Tuple[str, str], List[int]],
    all_lengths: Dict[Tuple[str, str], List[int]],
    all_first_bloods: Dict[Tuple[str, str], List[int]],
    all_survivors: Dict[Tuple[str, str], List[Tuple[int, int]]],
    strategy_names: List[str],
    board_desc: str,
    svg: bool = False,
) -> None:
    """Generate all chart types to a directory.

    :param svg: If True, output SVG files instead of PNG.
    :type svg: bool
    """
    import os as _os

    _os.makedirs(output_dir, exist_ok=True)

    if not try_init_matplotlib():
        print("matplotlib not installed. Install with: pip install matplotlib")
        return

    ext = ".svg" if svg else ".png"

    strategy_curves = aggregate_strategy_series(all_series, strategy_names)
    plot_win_rate_curve(
        strategy_curves, _os.path.join(output_dir, f"curve{ext}"), board_desc,
    )
    plot_head_to_head(
        all_results, strategy_names, _os.path.join(output_dir, f"matrix{ext}"), board_desc,
    )
    plot_game_length_histogram(
        all_lengths, strategy_names, _os.path.join(output_dir, f"hist{ext}"),
    )
    plot_first_blood_histogram(
        all_first_bloods, strategy_names, _os.path.join(output_dir, f"first_blood{ext}"),
    )
    plot_survivor_count(
        all_survivors, strategy_names, _os.path.join(output_dir, f"survivors{ext}"),
    )
    print(f"All charts exported to {output_dir}/")


if __name__ == "__main__":
    main()
