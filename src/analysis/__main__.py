"""CLI entry point for the analysis toolkit.

Usage:
    python -m analysis --username player1 --token $SAIBLO_TOKEN --output-dir analysis_out
    python -m analysis --replay-dir replay --output-dir analysis_out
"""

import argparse
import os
import sys
from typing import Dict, List, Tuple

from analysis.chart import (
    plot_build_distribution,
    plot_death_sequence,
    plot_first_blood_summary,
    plot_focus_fire,
    plot_target_preference,
)
from analysis.fetcher import download_replay, fetch_match_list, load_local_replays
from analysis.indicators import aggregate_indicators, compute_indicators
from analysis.parser import parse_replay


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    :returns: Parsed arguments.
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="Analyze THUAI9 Saiblo replays and generate strategy charts",
    )
    parser.add_argument(
        "--username", type=str, default=None,
        help="Saiblo username to fetch replays for",
    )
    parser.add_argument(
        "--replay-dir", type=str, default=None,
        help="Directory of local replay JSONs",
    )
    parser.add_argument(
        "--token", type=str, default=None,
        help="Saiblo API token (env: SAIBLO_TOKEN)",
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Max replays to fetch (default: 50)",
    )
    parser.add_argument(
        "--output-dir", type=str, default="analysis_out",
        help="Output directory for charts (default: analysis_out)",
    )
    parser.add_argument(
        "--replay-cache", type=str, default=None,
        help="Directory to cache downloaded replays",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # --- Step 1: Collect replays ---
    import json as _json

    raw_replays = []

    # Load local cache if replay-dir is given (or default ../replay/)
    replay_dir = args.replay_dir
    if replay_dir is None:
        default_replay = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "replay",
        )
        if os.path.isdir(default_replay):
            replay_dir = default_replay

    if replay_dir is not None:
        print(f"Loading local replays from {replay_dir} ...")
        raw_replays = load_local_replays(replay_dir)
        print(f"  Found {len(raw_replays)} replay(s).")

    # Fetch from API if username is given
    if args.username is not None:
        token = args.token or os.environ.get("SAIBLO_TOKEN")
        if not token:
            print("Error: no token. Use --token or set SAIBLO_TOKEN.")
            sys.exit(1)

        cache_dir = args.replay_cache or replay_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

        print(f"Fetching match list for {args.username} ...")
        matches = fetch_match_list(args.username, token, limit=args.limit)
        print(f"  Found {len(matches)} matches.")

        existing_ids = {mid for _, mid, _ in raw_replays}
        new_count = 0
        for m in matches:
            result = download_replay(m, token, cache_dir or output_dir)
            if result is not None:
                opp, mid = result
                if mid not in existing_ids:
                    fpath = os.path.join(
                        cache_dir or output_dir, f"{opp}-{mid}.json",
                    )
                    with open(fpath) as f:
                        data = _json.load(f)
                    raw_replays.append((opp, mid, data))
                    existing_ids.add(mid)
                    new_count += 1
                    print(f"  Downloaded {opp} match #{mid}")

        if new_count == 0:
            print("  No new matches.")

    if not raw_replays:
        print("Error: no replays found. Specify --username or --replay-dir.")
        sys.exit(1)

    if not raw_replays:
        print("No replays found.")
        sys.exit(0)

    print(f"Loaded {len(raw_replays)} replay(s).")

    # --- Step 2: Parse and compute indicators ---
    parsed = []
    all_indicators = []
    labels: List[str] = []

    for opponent, match_id, data in raw_replays:
        replay = parse_replay(data, match_id, opponent)
        parsed.append(replay)
        ind = compute_indicators(replay)
        all_indicators.append(ind)
        labels.append(f"{opponent} #{match_id}")

    # --- Step 3: Print summary table ---
    _print_indicator_table(all_indicators, labels)

    # --- Step 4: Generate charts ---
    agg = aggregate_indicators(all_indicators)

    builds: List[Tuple[int, int, int]] = agg.get("builds", [])
    if builds:
        plot_build_distribution(
            builds, os.path.join(output_dir, "build_distribution.png"),
        )

    target_ratios = [ind["target_lowest_hp_ratio"] for ind in all_indicators]
    plot_target_preference(
        target_ratios, labels, os.path.join(output_dir, "target_preference.png"),
    )

    plot_focus_fire(
        all_indicators, labels, os.path.join(output_dir, "focus_fire.png"),
    )

    plot_first_blood_summary(
        all_indicators, labels, os.path.join(output_dir, "first_blood.png"),
    )

    plot_death_sequence(
        all_indicators, labels, os.path.join(output_dir, "death_sequence.png"),
    )

    # --- Step 5: Print aggregate stats ---
    print()
    print("=" * 60)
    print("Aggregate Statistics")
    print("=" * 60)
    print(f"  Matches: {agg['n_matches']}")
    print(f"  Wins: {agg['n_wins']} / {agg['n_matches']} "
          f"({agg['n_wins'] / agg['n_matches'] * 100:.1f}%)")
    print(f"  Avg formation spread: {agg['avg_formation_spread']:.1f}")
    print(f"  Avg focus-fire rounds: {agg['avg_focus_fire_rounds']:.1f}")
    print(f"  Avg target-lowest-HP ratio: {agg['avg_target_lowest_hp_ratio']:.2f}")
    print(f"  Avg first-blood round: {agg['avg_first_blood_round']:.1f}")
    print(f"  Avg damage per attack: {agg['avg_damage']:.1f}")
    print(f"  Avg spells per match: {agg['avg_spell_count']:.1f}")
    print(f"  First-blood win rate: {agg['first_blood_wins']:.0%}")

    print()
    print(f"Charts saved to {output_dir}/")


def _print_indicator_table(
    all_indicators: List[dict],
    labels: List[str],
) -> None:
    """Print a text table of per-match indicators."""
    print()
    header = (
        f"{'Match':<22} {'Result':>6} {'Rounds':>7} "
        f"{'FB R':>5} {'FF':>4} {'LHP%':>6} {'Adv%':>6} {'Dmg':>5}"
    )
    print(header)
    print("-" * len(header))
    for label, ind in zip(labels, all_indicators):
        result = "W" if ind["player_won"] else "L"
        print(
            f"{label:<22} {result:>6} {ind['total_rounds']:>7d} "
            f"{ind['first_blood_round']:>5d} {ind['focus_fire_events']:>4d} "
            f"{ind['target_lowest_hp_ratio']:>5.0%} "
            f"{ind['advance_ratio']:>5.0%} "
            f"{ind['avg_damage']:>5.1f}"
        )
    print()


if __name__ == "__main__":
    main()
