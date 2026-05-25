"""Round-by-round debug tracer — prints piece positions and HP.

Usage via benchmark::

    uv run python benchmark.py --p1 child6 --p2 sniper --rounds 1 \\
        --board ./BoardCase/case1.txt --debug

Or programmatically::

    from debug_trace import make_debug_callback
    from benchmark.runner import run_single_game

    cb = make_debug_callback()
    result = run_single_game(
        board_file, p1_pair, p2_pair,
        round_callback=cb,
    )
"""

from typing import Any, Callable, List


def make_debug_callback() -> Callable:
    """Return a ``round_callback`` that prints all piece states.

    The callback prints a table with one row per piece per round:
    round, team, piece ID, position (x, y), HP / max HP, alive.
    """
    def callback(env: Any, round_number: int) -> None:
        pieces: List[Any] = []
        for team_id in (1, 2):
            for piece in getattr(env, f"player{team_id}").pieces:
                pieces.append({
                    "team": team_id,
                    "id": piece.id,
                    "x": piece.position.x,
                    "y": piece.position.y,
                    "hp": piece.health,
                    "max_hp": piece.max_health,
                    "alive": piece.is_alive,
                })

        header = f"=== Round {round_number} ==="
        print(header)
        print(
            f"  {'Team':<5} {'ID':<3} {'Pos':<10} {'HP':<8} {'Alive'}"
        )
        print(f"  {'-'*5} {'-'*3} {'-'*10} {'-'*8} {'-'*5}")
        for p in pieces:
            pos = f"({p['x']},{p['y']})"
            hp = f"{p['hp']}/{p['max_hp']}"
            alive = "✓" if p["alive"] else "✗"
            print(
                f"  {p['team']:<5} {p['id']:<3} {pos:<10} {hp:<8} {alive}"
            )
        print()

    return callback


def debug_main() -> None:
    """Entry point for standalone use: ``uv run python debug_trace.py``."""
    import random
    import sys

    from env import Environment

    from benchmark import get_strategy_pair
    from benchmark.runner import run_single_game

    # Parse strategy names from CLI args or use defaults
    p1_name = sys.argv[1] if len(sys.argv) > 1 else "child6"
    p2_name = sys.argv[2] if len(sys.argv) > 2 else "sniper"

    print(f"Debug trace: {p1_name} (P1) vs {p2_name} (P2)")
    print()

    p1_pair = get_strategy_pair(p1_name)
    p2_pair = get_strategy_pair(p2_name)

    cb = make_debug_callback()
    result = run_single_game(
        "./BoardCase/case1.txt",
        p1_pair, p2_pair,
        max_rounds=100,
        verbose=False,
        round_callback=cb,
    )

    print(f"Game result: {result.result}")
    print(f"Rounds: {result.rounds}")


if __name__ == "__main__":
    debug_main()
