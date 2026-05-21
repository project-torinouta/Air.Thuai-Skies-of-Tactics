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

"""Per-round game analyser for the heuristic learning loop.

Captures round-by-round snapshots during benchmark games and produces
analysis text: HP curves, kill timing, positioning, and first blood.
"""

from typing import Any, Callable, Dict, List, Tuple

from env import Environment


def _capture_snapshot(env: Environment) -> Dict[str, Any]:
    """Capture the current round's state for all pieces."""
    pieces = []
    for team_id, player in [(1, env.player1), (2, env.player2)]:
        for piece in player.pieces:
            pieces.append(
                {
                    "id": piece.id,
                    "team": team_id,
                    "x": piece.position.x,
                    "y": piece.position.y,
                    "height": piece.height,
                    "hp": piece.health,
                    "max_hp": piece.max_health,
                    "alive": piece.is_alive,
                    "death_round": getattr(piece, "death_round", -1),
                }
            )
    return {
        "round": env.round_number,
        "pieces": pieces,
    }


def make_round_callback(snapshots: List[Dict[str, Any]]) -> Callable:
    """Return a ``round_callback`` that appends snapshots to *snapshots*.

    Usage::

        snapshots: List[Dict] = []
        gr = run_single_game(..., round_callback=make_round_callback(snapshots))
    """
    def callback(env: Environment, _: int) -> None:
        snapshots.append(_capture_snapshot(env))
    return callback


def analyse_snapshots(
    snapshots: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Analyse a sequence of round snapshots into human-readable metrics.

    :returns: A dict with hp_curves, kill_order, first_blood_round, etc.
    :rtype: Dict
    """
    if not snapshots:
        return {"error": "no snapshots"}

    # HP per piece per round
    piece_ids = {p["id"] for p in snapshots[0]["pieces"]}

    hp_curves: Dict[int, List[Tuple[int, float]]] = {pid: [] for pid in piece_ids}
    death_rounds: Dict[int, int] = {}
    positions: Dict[int, List[Tuple[int, int, int]]] = {pid: [] for pid in piece_ids}

    for snap in snapshots:
        rnd = snap["round"]
        for p in snap["pieces"]:
            pid = p["id"]
            hp_curves[pid].append((rnd, p["hp"]))
            positions[pid].append((rnd, p["x"], p["y"]))
            if p["death_round"] > 0:
                death_rounds[pid] = p["death_round"]

    # First blood
    first_blood_round = min(death_rounds.values()) if death_rounds else -1
    first_blood_piece = None
    if first_blood_round > 0:
        for pid, dr in death_rounds.items():
            if dr == first_blood_round:
                # Find team
                for snap in snapshots:
                    for p in snap["pieces"]:
                        if p["id"] == pid:
                            first_blood_piece = {
                                "id": pid,
                                "team": p["team"],
                                "round": dr,
                            }
                            break
                    if first_blood_piece:
                        break

    # Kill order
    kill_order = sorted(death_rounds.items(), key=lambda x: x[1])

    # Total HP remaining per team at end
    last_snap = snapshots[-1]
    team_hp = {1: 0.0, 2: 0.0}
    for p in last_snap["pieces"]:
        if p["alive"]:
            team_hp[p["team"]] += p["hp"]

    # Round-by-round team total HP
    team_hp_curves = {1: [], 2: []}
    for snap in snapshots:
        hp1 = sum(
            p["hp"] for p in snap["pieces"]
            if p["team"] == 1 and p["alive"]
        )
        hp2 = sum(
            p["hp"] for p in snap["pieces"]
            if p["team"] == 2 and p["alive"]
        )
        team_hp_curves[1].append((snap["round"], hp1))
        team_hp_curves[2].append((snap["round"], hp2))

    return {
        "total_rounds": len(snapshots),
        "first_blood_round": first_blood_round,
        "first_blood_piece": first_blood_piece,
        "kill_order": [
            {"piece_id": pid, "round": dr}
            for pid, dr in kill_order
        ],
        "hp_curves": {str(pid): pts for pid, pts in hp_curves.items()},
        "team_hp_curves": {
            str(team): pts for team, pts in team_hp_curves.items()
        },
        "team_hp_remaining": team_hp,
        "positions": {str(pid): pts for pid, pts in positions.items()},
    }


def format_analysis(analysis: Dict[str, Any]) -> str:
    """Format analysis dict into a human-readable report."""
    lines = []
    lines.append(f"Game duration: {analysis['total_rounds']} rounds")
    if analysis["first_blood_round"] > 0:
        fb = analysis["first_blood_piece"]
        lines.append(
            f"First blood: piece {fb['id']} (team {fb['team']}) "
            f"at round {fb['round']}"
        )
    else:
        lines.append("No deaths")

    if analysis["kill_order"]:
        lines.append("Kill order:")
        for k in analysis["kill_order"]:
            lines.append(f"  piece {k['piece_id']} — round {k['round']}")

    lines.append(f"Team HP remaining: P1={analysis['team_hp_remaining'][1]:.0f}"
                 f" P2={analysis['team_hp_remaining'][2]:.0f}")

    lines.append("\nTeam HP per round:")
    for team, pts in analysis["team_hp_curves"].items():
        hp_str = " ".join(f"{r}:{hp:.0f}" for r, hp in pts)
        lines.append(f"  Team {team}: {hp_str}")

    return "\n".join(lines)
