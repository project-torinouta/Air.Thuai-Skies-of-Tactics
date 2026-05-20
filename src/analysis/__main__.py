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

"""CLI entry point for the analysis toolkit.

Usage:
    python -m analysis --username player1 --token $SAIBLO_TOKEN --output-dir analysis
    python -m analysis --replay-dir replay --output-dir analysis
    python -m analysis --replay-dir replay --copy-mode
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

from analysis.chart import plot_average_timelines, plot_strategy_fingerprint
from analysis.fetcher import download_replay, fetch_all_matches
from analysis.indicators import aggregate_indicators, compute_indicators
from analysis.models import ParsedReplay
from analysis.parser import parse_replay
from analysis.timeline import average_timeline_sequences


# Argument parsing


def parse_args() -> argparse.Namespace:
    """Return parsed command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Analyze THUAI9 Saiblo replays and generate strategy charts",
    )
    parser.add_argument(
        "--username",
        type=str,
        default=None,
        help="Saiblo username to fetch replays for",
    )
    parser.add_argument(
        "--replay-dir",
        type=str,
        default=None,
        help="Directory of local replay JSONs",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Saiblo API token (env: SAIBLO_TOKEN)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max replays to fetch (default: 200)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="analysis",
        help="Output directory for charts",
    )
    parser.add_argument(
        "--replay-cache",
        type=str,
        default=None,
        help="Directory to cache downloaded replays",
    )
    parser.add_argument(
        "--copy-mode",
        action="store_true",
        help="Print dense text block, skip chart generation",
    )
    parser.add_argument(
        "--fingerprint",
        action="store_true",
        help="Also generate the 6-panel fingerprint chart",
    )
    parser.add_argument(
        "--min-games",
        type=int,
        default=20,
        help="Minimum games per group for analysis (default: 20)",
    )
    return parser.parse_args()


def main() -> None:
    """Run the full analysis pipeline."""
    args = parse_args()

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # raw_replays stores: (my_entity, my_version, my_camp, opponent,
    #                      opp_entity, opp_version, match_id, data)

    raw_replays: List[Tuple[str, int, str, str, str, int, int, dict]] = []
    existing: List[Tuple[str, int]] = []

    # Determine where to look for replay files
    replay_dir = args.replay_dir
    if replay_dir is None:
        default_replay = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".replay",
        )
        if os.path.isdir(default_replay):
            replay_dir = default_replay

    if args.username is not None:
        token = args.token or os.environ.get("SAIBLO_TOKEN")
        if not token:
            print("Error: no token. Use --token argument or set SAIBLO_TOKEN.")
            sys.exit(1)

        cache_dir = args.replay_cache or replay_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

        matches = fetch_all_matches(
            args.username, token,
            max_games=args.limit,
        )

        for m in matches:
            dpath = os.path.join(
                cache_dir or replay_dir,
                args.username,
            )
            result = download_replay(
                m, token,
                dpath,
                player_name=args.username,
            )
            if result is not None:
                my_ent, my_ver, my_camp, opp, opp_ent, opp_ver, mid = result
                print(
                    f"→ Match {my_ent} v{my_ver} vs {opp_ent} v{opp_ver}"
                    f" saved to {dpath}"
                )

                if (opp, mid) not in existing:
                    fpath = os.path.join(
                        cache_dir or output_dir,
                        args.username,
                        f"{opp}-{mid}.json",
                    )
                    with open(fpath) as f:
                        data = json.load(f)
                    raw_replays.append(
                        (my_ent, my_ver, my_camp, opp, opp_ent, opp_ver, mid, data)
                    )
                    existing.append((opp, mid))

    if not raw_replays:
        print("No replays found.")
        sys.exit(0)

    all_groups: Dict[str, list] = defaultdict(list)
    for my_ent, my_ver, my_camp, opp, opp_ent, opp_ver, mid, data in raw_replays:
        key = f"{my_ent} v{my_ver}"
        all_groups[key].append(
            (my_ent, my_ver, my_camp, opp, opp_ent, opp_ver, mid, data)
        )

    print(f"\nAll groups ({len(all_groups)}):")
    for k, v in sorted(all_groups.items(), key=lambda x: -len(x[1])):
        print(f"  {k}: {len(v)} games")
    print()

    groups = {
        k: v for k, v in all_groups.items()
        if len(v) >= args.min_games
    }
    if not groups:
        print(f"No group has {args.min_games}+ games. Analysis failed.")
        sys.exit(0)

    print(
        f"Analyzing {len(groups)} group(s)"
        f" with {args.min_games}+ games:\n"
    )

    for group_name, group_replays in sorted(groups.items()):
        safe_name = group_name.replace(" ", "_").replace("/", "_")
        group_dir = os.path.join(output_dir, safe_name)
        os.makedirs(group_dir, exist_ok=True)
        _analyze_group(
            group_replays, group_dir, args,
            user=args.username,
            group_label=group_name,
        )


# Group-level analysis


def _analyze_group(
    raw_replays: List[Tuple[str, int, str, str, str, int, int, dict]],
    output_dir: str,
    args: argparse.Namespace,
    user: str,
    group_label: str = "",
) -> None:
    """Parse, compute indicators, and output analysis for one AI group."""

    parsed: List[ParsedReplay] = []
    all_indicators = []
    labels: List[str] = []
    skipped = 0

    for my_ent, my_ver, my_camp, opponent, opp_ent, opp_ver, match_id, data in raw_replays:
        replay = parse_replay(
            data, match_id, opponent,
            user, my_camp
        )

        if replay.rounds and replay.rounds[-1].round_number == 0:
            skipped += 1
            continue

        parsed.append(replay)
        ind = compute_indicators(replay)

        pc = my_camp
        oc = "Blue" if pc == "Red" else "Red"

        ind["player_name"] = user
        ind["player_ai"] = f"{my_ent} v{my_ver}" if my_ent else ""
        ind["opponent_name"] = opponent
        ind["opponent_ai"] = f"{opp_ent} v{opp_ver}" if opp_ent else ""
        ind["player_camp"] = pc
        ind["opponent_camp"] = oc

        all_indicators.append(ind)

        label = f"{opponent} #{match_id}"
        if opp_ent:
            label += f" [{opp_ent} v{opp_ver}]"
        labels.append(label)

    n_loaded = len(all_indicators)
    header = f"  ({group_label}) " if group_label else ""
    print(
        f"{header}Loaded {len(raw_replays)} replay(s),"
        f" {n_loaded} with data ({skipped} empty)."
    )
    if not all_indicators:
        print("  No valid replays.")
        return

    agg = aggregate_indicators(all_indicators)

    if args.copy_mode:
        _print_copy_block(all_indicators, labels, agg)
    else:
        _print_indicator_table(all_indicators, labels)

        # Average timeline charts
        print("  Generating average timeline charts ...")
        avg = average_timeline_sequences(all_indicators)
        if avg:
            ind0 = all_indicators[0]
            pc = ind0.get("player_camp", "Red")
            pn = ind0.get("player_name", "?")
            camp_labels = {
                pc: f"{pc} ({pn})",
                "Red" if pc == "Blue" else "Blue": "Opponent",
            }
            plot_average_timelines(
                avg, output_dir,
                n_matches=n_loaded,
                camp_labels=camp_labels,
                player_camp=pc,
            )

        if args.fingerprint:
            plot_strategy_fingerprint(
                all_indicators, agg,
                os.path.join(output_dir, "strategy_fingerprint.png"),
            )

        _print_aggregate_profile(agg, all_indicators)
        print(f"\n  Charts saved to {output_dir}/")


# Copy-mode output: dense text block for easy copy-paste


def _print_copy_block(
    all_indicators: List[dict],
    labels: List[str],
    agg: dict,
) -> None:
    """Print a compact strategy summary ready for copy-paste."""
    build = agg.get("player_build", {})
    s_mode = ", ".join(str(v) for v in build.get("str", ["?"]))
    d_mode = ", ".join(str(v) for v in build.get("dex", ["?"]))
    i_mode = ", ".join(str(v) for v in build.get("int", ["?"]))

    p_info = ""
    if all_indicators:
        p_name = all_indicators[0].get("player_name", "?")
        p_camp = all_indicators[0].get("player_camp", "?")
        ai = all_indicators[0].get("player_ai", "")
        p_info = f"Player: {p_name} as {p_camp}"
        if ai:
            p_info += f"  AI: {ai}"

    lines = [
        f"=== Strategy: {agg['n_matches']} matches,"
        f" {agg['n_wins']}W / {agg['n_matches'] - agg['n_wins']}L"
        f" ({agg['win_rate']:.0f}%) ===",
        p_info,
        f"Build: STR {s_mode} / DEX {d_mode} / INT {i_mode}",
        (
            f"Damage: {agg['avg_damage']:.1f}/att"
            f"  Spells: {agg['avg_spell_count']:.1f}/match"
        ),
        (
            f"First blood: R{agg['avg_first_blood_round']:.0f}"
            f"  (win {agg['first_blood_win_rate']:.0%})"
        ),
        "",
        (
            f"Compactness: {agg['compactness']:.1f}"
            f" (opp: {agg['opponent_compactness']:.1f})"
        ),
        (
            f"FFI: {agg['ffi']:.0%}"
            f"  KEI: {agg['kei_ratio']:.0%}"
            f"  ({agg['kei_total_attempts']} attempts)"
        ),
        "",
        (
            f"{'Match':<30} {'AI':<20} {'Camp':>4}"
            f" {'W/L':>1} {'Rnd':>3} {'FB':>3}"
            f" {'Cmpct':>5} {'FFI':>4} {'KEI':>4} {'Dmg':>5}"
        ),
        (
            f"{'-----':<30} {'---':<20} {'----':>4}"
            f" {'---':>1} {'---':>3} {'---':>3}"
            f" {'-----':>5} {'----':>4} {'----':>4} {'---':>5}"
        ),
    ]

    for label, ind in zip(labels, all_indicators):
        result = "W" if ind["player_won"] else "L"
        fb = ind["first_blood_round"]
        camp = ind.get("player_camp", "?")
        ai = ind.get("opponent_ai", "")

        if len(ind["player_compactness"]) == 0 or len(ind["player_ffi"]) == 0:
            continue
        else:
            lines.append(
                f"{label:<30} {ai:<20} {camp:>4} {result:>1}"
                f" {ind['total_rounds']:>3d}"
                f" {fb if fb > 0 else '-':>3}"
                f" {ind['player_compactness'][0]:>5.1f} → {ind['player_compactness'][-1]:>5.1f}"
                f" {ind['player_ffi'][0]:>4.0%} → {ind['player_ffi'][-1]:>4.0%}"
                f" {ind['player_kei']['ratio']:>4.0%}"
                f" {ind['player_avg_damage']:>5.1f}"
            )

    print()
    print("\n".join(lines))
    print()


# Normal-mode helpers

def _print_indicator_table(
    all_indicators: List[dict],
    labels: List[str],
) -> None:
    """Print per-match indicator table."""
    print()
    header = (
        f"{'Match':<28} {'Camp':>5} {'W/L':>4} {'R':>4} {'FB':>4}"
        f" {'Cmpct':>6} {'FFI':>5} {'KEI':>5} {'Dmg':>5}"
    )
    print(header)
    print("-" * len(header))
    for label, ind in zip(labels, all_indicators):
        result = "W" if ind["player_won"] else "L"
        fb = ind["first_blood_round"]
        camp = ind["player_camp"]

        if len(ind["player_compactness"]) == 0 or len(ind["player_ffi"]) == 0:
            continue
        else:
            print(
                f"{label:<28} {camp:>5} {result:>4} {ind['total_rounds']:>4d}"
                f" {fb if fb > 0 else '-':>4}"
                f" {ind['player_compactness'][0]:>5.1f} → {ind['player_compactness'][-1]:>5.1f}"
                f" {ind['player_ffi'][0]:>4.0%} → {ind['player_ffi'][-1]:>4.0%}"
                f" {ind['player_kei']['ratio']:>4.0%}"
                f" {ind['player_avg_damage']:>5.1f}"
            )
    print()


def _print_aggregate_profile(
    agg: dict,
    all_indicators: list = None,
) -> None:
    """Print aggregate strategy profile."""
    build = agg.get("player_build", {})
    s_mode = ", ".join(str(v) for v in build.get("str", ["?"]))
    d_mode = ", ".join(str(v) for v in build.get("dex", ["?"]))
    i_mode = ", ".join(str(v) for v in build.get("int", ["?"]))

    print()
    print("=" * 65)
    print("  Strategy Profile")
    print("=" * 65)
    print(
        f"  Matches:              {agg['n_matches']}"
        f"  ({agg['n_wins']}W / {agg['n_matches'] - agg['n_wins']}L)"
    )
    print(f"  Win rate:             {agg['win_rate']:.0f}%")
    if all_indicators:
        pc = all_indicators[0].get("player_camp", "?")
        pn = all_indicators[0].get("player_name", "?")
        ai = all_indicators[0].get("player_ai", "")
        ai_str = f"  AI: {ai}" if ai else ""
        print(f"  Player camp:          {pn} as {pc}{ai_str}")
    print(
        f"  Build:                STR {s_mode}"
        f" / DEX {d_mode} / INT {i_mode}"
    )
    print(
        f"  Compactness:          {agg['compactness']:.1f} tiles from centroid"
        f"  (opp: {agg['opponent_compactness']:.1f})"
    )
    print(f"  Focus Fire Index:     {agg['ffi']:.0%}")
    print(
        f"  Kiting Efficiency:    {agg['kei_ratio']:.0%}"
        f"  ({agg['kei_total_attempts']} move+attack actions)"
    )
    print(f"  Damage:               {agg['avg_damage']:.1f} per attack")
    print(f"  Spells:               {agg['avg_spell_count']:.1f} per match")
    print(
        f"  First blood:          R{agg['avg_first_blood_round']:.0f}"
        f"  (win {agg['first_blood_win_rate']:.0%})"
    )


if __name__ == "__main__":
    main()
