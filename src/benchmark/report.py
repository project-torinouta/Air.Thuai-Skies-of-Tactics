"""Formatted text output for benchmark results."""

from typing import Dict, List, Tuple


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
