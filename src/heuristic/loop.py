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

"""Heuristic Learning loop — CLI entry point.

Calls benchmark functions directly instead of subprocessing.  All runs use
``--fixed-build 29 1 0`` to isolate tactical differences.

Usage::

    uv run python -m heuristic.loop baseline --rounds 50
    uv run python -m heuristic.loop test <variant> --rounds 30
    uv run python -m heuristic.loop analyse <variant> --games 5
    uv run python -m heuristic.loop promote <variant>
    uv run python -m heuristic.loop status
"""

import argparse
import contextlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Make src/ importable
_SRC_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_SRC_DIR))

from benchmark import (
    INIT_NAMES,
    get_action_strategy,
    get_init_strategy,
    StrategyPair,
)
from benchmark.runner import run_matchup_series, run_single_game
from benchmark.board import resolve_boards
from benchmark.chart import (
    plot_head_to_head,
    plot_win_rate_curve,
    try_init_matplotlib,
)
from benchmark.__main__ import _make_fixed_build_init

from heuristic.analyser import (
    analyse_snapshots,
    format_analysis,
    make_round_callback,
)

_PACKAGE_DIR = Path(__file__).parent
_STATE_FILE = _PACKAGE_DIR / "state.json"
_ITERATIONS_DIR = _PACKAGE_DIR / "iterations"


def _load_state() -> Dict[str, Any]:
    with open(_STATE_FILE) as f:
        return json.load(f)


def _save_state(state: Dict[str, Any]) -> None:
    with open(_STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)
        f.write("\n")


def _build_pairs(
    names: List[str],
    fixed: Tuple[int, int, int],
) -> Dict[str, StrategyPair]:
    """Build (init, action) pairs for the given strategy names,
    wrapping inits with ``_make_fixed_build_init``."""
    pairs: Dict[str, StrategyPair] = {}
    for name in names:
        if name in INIT_NAMES:
            raw_init = get_init_strategy(name)
        else:
            from strategies.defensive import get_defensive_init_strategy
            raw_init = get_defensive_init_strategy()
        wrapped_init = _make_fixed_build_init(
            raw_init, fixed[0], fixed[1], fixed[2],
        )
        pairs[name] = (wrapped_init, get_action_strategy(name))
    return pairs


class _LogWriter:
    """Writes to both the real terminal and a log file."""

    def __init__(self, path: Path, terminal) -> None:
        self._terminal = terminal
        self._file = open(path, "w")

    def write(self, text: str) -> None:
        self._terminal.write(text)
        self._file.write(text)

    def flush(self) -> None:
        self._terminal.flush()
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def _run_direct_benchmark(
    include: List[str],
    rounds: int = 30,
    label: str = "hl",
    fixed: Tuple[int, int, int] = (29, 1, 0),
) -> str:
    """Run a round-robin benchmark directly and save results to an iteration dir.

    :returns: Path to the iteration directory.
    :rtype: str
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = _ITERATIONS_DIR / f"{label}_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    _old_stdout = sys.stdout
    _log = _LogWriter(out_dir / "results.log", _old_stdout)
    sys.stdout = _log  # type: ignore[assignment]

    try:
        board_files = resolve_boards(
            argparse.Namespace(
                board=str(_SRC_DIR / "BoardCase" / "case1.txt"),
                board_dir=None,
                generate_boards=0,
            )
        )

        pairs = _build_pairs(include, fixed)

        print(f"Strategies: {', '.join(include)}")
        print(f"Build: STR {fixed[0]} / DEX {fixed[1]} / INT {fixed[2]}")
        print(f"Games per matchup: {rounds}")
        print()

        all_results: Dict[Tuple[str, str], Tuple[int, int, int]] = {}
        all_series: Dict[Tuple[str, str], List[int]] = {}

        for p1_name in include:
            for p2_name in include:
                if p1_name == p2_name:
                    continue
                sys.stdout.write(f"  {p1_name} vs {p2_name}  ")
                sys.stdout.flush()
                ms = run_matchup_series(
                    board_files, pairs[p1_name], pairs[p2_name],
                    rounds, max_rounds=100,
                )
                p1_wins = sum(1 for r in ms.results if r == 1)
                p2_wins = sum(1 for r in ms.results if r == 2)
                draws = sum(1 for r in ms.results if r == 0)
                all_results[(p1_name, p2_name)] = (p1_wins, p2_wins, draws)
                all_series[(p1_name, p2_name)] = ms.results
                print(f" {p1_wins}-{p2_wins}-{draws}")

        print()
        from benchmark.report import (
            print_results_table,
            print_win_rate_summary,
        )
        print_results_table(all_results)
        print_win_rate_summary(all_results, include)
        print()
    finally:
        sys.stdout = _old_stdout
        _log.close()

    if try_init_matplotlib():
        strategy_curves: Dict[str, List[int]] = {}
        for name in include:
            curve: List[int] = []
            for (p1, p2), series in all_series.items():
                if p1 == name:
                    curve.extend(1 if r == 1 else 0 for r in series)
                elif p2 == name:
                    curve.extend(1 if r == 2 else 0 for r in series)
            strategy_curves[name] = curve
        plot_win_rate_curve(
            strategy_curves, str(out_dir / "curve.png"),
            f"baseline ({rounds} games each)",
        )
        plot_head_to_head(
            all_results, include, str(out_dir / "matrix.png"),
            f"baseline ({rounds} games each)",
        )

    return str(out_dir)


# Argument parsers

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="heuristic.loop",
        description="Heuristic Learning loop (Observe → Hypothesise → Modify → Verify).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run python -m heuristic.loop baseline --rounds 50\n"
            "  uv run python -m heuristic.loop test zoner --rounds 30\n"
            "  uv run python -m heuristic.loop analyse zoner --games 5\n"
            "  uv run python -m heuristic.loop promote zoner\n"
            "  uv run python -m heuristic.loop status\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # baseline
    p_baseline = sub.add_parser(
        "baseline", help="Benchmark champion vs configured opponents.",
    )
    p_baseline.add_argument(
        "--rounds", type=int, default=30,
        help="Games per matchup (default: 30).",
    )

    # test
    p_test = sub.add_parser(
        "test", help="Test a variant vs the current champion.",
    )
    p_test.add_argument("variant", type=str)
    p_test.add_argument(
        "--rounds", type=int, default=30,
        help="Games per matchup (default: 30).",
    )

    # analyse
    p_analyse = sub.add_parser(
        "analyse", help="Per-round snapshots (HP curves, kill order).",
    )
    p_analyse.add_argument("variant", type=str)
    p_analyse.add_argument(
        "--games", type=int, default=5,
        help="Number of games to analyse (default: 5).",
    )

    # promote
    sub.add_parser("promote", help="Promote a variant to champion.").add_argument(
        "variant", type=str,
    )

    # status
    sub.add_parser("status", help="Show current HL loop state.")

    return parser


# Command implementations

def cmd_baseline(args: argparse.Namespace) -> None:
    state = _load_state()
    include = [state["champion"]] + [
        o for o in state["opponents"] if o != state["champion"]
    ]
    out_dir = _run_direct_benchmark(
        include, rounds=args.rounds, label="baseline",
    )
    print(f"Baseline saved to {out_dir}/")


def cmd_test(args: argparse.Namespace) -> None:
    state = _load_state()
    include = [state["champion"], args.variant]
    out_dir = _run_direct_benchmark(
        include, rounds=args.rounds, label=f"test_{args.variant}",
    )
    print(f"Test results saved to {out_dir}/")


def cmd_analyse(args: argparse.Namespace) -> None:
    state = _load_state()
    board_file = str(_SRC_DIR / "BoardCase" / "case1.txt")

    build = tuple(state["fixed_build"])
    pairs = _build_pairs([state["champion"], args.variant], build)

    p1_pair = pairs[state["champion"]]
    p2_pair = pairs[args.variant]

    print(f"Analysing {state['champion']} (champion) vs {args.variant}")
    print(f"  Games: {args.games}")
    print()

    for g in range(args.games):
        snapshots: List[Dict[str, Any]] = []
        cb = make_round_callback(snapshots)

        with open(os.devnull, "w") as _devnull, contextlib.redirect_stdout(_devnull):
            gr = run_single_game(
                board_file, p1_pair, p2_pair,
                round_callback=cb,
            )

        print(f"  Game {g + 1}: ", end="")
        if gr.result == 1:
            print(f"champion wins (round {gr.rounds})")
        elif gr.result == 2:
            print(f"{args.variant} wins (round {gr.rounds})")
        else:
            print(f"draw (round {gr.rounds})")

        analysis = analyse_snapshots(snapshots)
        report = format_analysis(analysis)
        for line in report.split("\n"):
            print(f"    {line}")
        print()


def cmd_promote(args: argparse.Namespace) -> None:
    state = _load_state()
    state["iteration"] += 1
    state["champion"] = args.variant
    state["iterations"].append(
        {
            "iteration": state["iteration"],
            "champion": args.variant,
            "timestamp": datetime.now().isoformat(),
        }
    )
    _save_state(state)
    print(f"Promoted {args.variant} to champion (iteration {state['iteration']}).")
    print(f"Update src/heuristic/champion.py to point to {args.variant}.")


def cmd_status(_args: argparse.Namespace) -> None:
    state = _load_state()
    print(f"Iteration:  {state['iteration']}")
    print(f"Champion:   {state['champion']}")
    print(f"Build:      STR {state['fixed_build'][0]}"
          f" / DEX {state['fixed_build'][1]}"
          f" / INT {state['fixed_build'][2]}")
    print(f"Opponents:  {', '.join(state['opponents'])}")
    print()

    iters = sorted(_ITERATIONS_DIR.iterdir()) if _ITERATIONS_DIR.exists() else []
    if iters:
        print("Iteration directories:")
        for d in iters:
            log_file = d / "results.log"
            champ = "?"
            if log_file.exists():
                for line in log_file.read_text().split("\n"):
                    if line.startswith(state["champion"]):
                        champ = line
            print(f"  {d.name}  ({champ})")
    else:
        print("No iterations yet. Run `baseline` to start.")


_COMMANDS = {
    "baseline": cmd_baseline,
    "test": cmd_test,
    "analyse": cmd_analyse,
    "promote": cmd_promote,
    "status": cmd_status,
}


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    _COMMANDS[args.command](args)


if __name__ == "__main__":
    main()
