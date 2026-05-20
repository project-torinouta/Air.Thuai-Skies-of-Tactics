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

"""Compute tactical indicators from parsed replay data.

Four core metrics replace the previous indicator system:

1. **Compactness Index** — centroid-based MAD of team formation
2. **Focus Fire Index (FFI)** — window-based coordination metric
3. **Kiting Efficiency Index (KEI)** — hit-and-run effectiveness
"""

from collections import Counter
from typing import Dict, List, Tuple

from analysis.models import ParsedReplay


def compute_indicators(replay: ParsedReplay) -> dict:
    """Compute all indicators for a single replay.

    :param replay: Parsed replay data.
    :type replay: ParsedReplay
    :returns: Dictionary of indicator values.
    :rtype: dict
    """
    pc = replay.user_camp
    oc = "Blue" if pc == "Red" else "Red"

    return {
        "player_build": _camp_build(replay, pc),
        "opponent_build": _camp_build(replay, oc),

        "player_compactness": _compactness_index(replay, pc),
        "opponent_compactness": _compactness_index(replay, oc),

        "player_ffi": _focus_fire_index(replay, pc),
        "opponent_ffi": _focus_fire_index(replay, oc),

        "player_kei": _kiting_efficiency(replay, pc),
        "opponent_kei": _kiting_efficiency(replay, oc),

        "player_kiting_sequence": _kiting_per_round(replay, pc),
        "opponent_kiting_sequence": _kiting_per_round(replay, oc),

        "player_avg_damage": _camp_avg_damage(replay, pc),
        "player_spell_count": _camp_spell_count(replay, pc),

        # Outcomes
        "total_rounds": replay.rounds[-1].round_number if replay.rounds else 0,
        "player_won": replay.winner == pc,
        "first_blood_round": _first_blood_round(replay),
        "first_blood_camp": _first_blood_camp(replay),
        "death_sequence": _death_sequence(replay),
    }


def _camp_build(replay: ParsedReplay, camp: str) -> Dict:
    """Read the actual attribute values from the replay.

    :param replay: Parsed replay data
    :type replay: ParsedReplay
    :param camp: The camp of user
    :type camp: str
    :returns: The initial properties of soldiers of user
    :rtype: Dict
    """

    soldiers = [s for s in replay.soldiers if s.camp == camp]
    if not soldiers:
        return {"str": [], "dex": [], "int": [], "weapon": [], "hp": []}
    return {
        "str": [s.strength for s in soldiers],
        "dex": [s.dexterity for s in soldiers],
        "int": [s.intelligence for s in soldiers],
        "weapon": [s.weapon_name for s in soldiers],
        "hp": [s.health for s in soldiers],
    }


def _compactness_index(replay: ParsedReplay, camp: str) -> List[float]:
    """Average Manhattan distance from team centroid (initial positions).

    Lower values = tighter deathball formation; higher = lane splitting.

    Uses starting positions from ``soldiersData``. Computes the geometric
    centroid (mean x, mean z), then returns the mean absolute Manhattan
    deviation from it.

    :param replay: Parsed replay data
    :type replay: ParsedReplay
    :param camp: Camps of analysed user
    :type camp: str
    :returns: The sequence consists of MAD of three pieces owned by ``camp``
    :rtype: List[float]
    """
    sequence = []

    for rnd in replay.rounds:
        pieces = []
        for idx, soldier_id in enumerate(list(rnd.positions.keys())):
            if rnd.camps[soldier_id] == camp:
                pos = rnd.positions[soldier_id]
                pieces.append((pos[0], pos[1]))

        if len(pieces) < 2:
            # When there are no piece / soldier then the average MAD is 0
            sequence.append(0)
            continue

        cx = sum(p[0] for p in pieces) / len(pieces)
        cz = sum(p[1] for p in pieces) / len(pieces)

        mad = sum(abs(p[0] - cx) + abs(p[1] - cz) for p in pieces) / len(pieces)
        sequence.append(round(mad, 2))
    return sequence


def _focus_fire_index(replay: ParsedReplay, camp: str) -> List[float]:
    """Per-round rolling 3-round Focus Fire Index.

    For each round r, FFI(r) = max_target_attacks / total_attacks
    over the 3-round window [r-2, r]. Rounds with no attacks get 0.5
    (neutral).

    :param replay: Parsed replay data
    :type replay: ParsedReplay
    :param camp: Camp to compute FFI for.
    :type camp: str
    :returns: One FFI value per round.
    :rtype: List[float]
    """
    soldier_camp = {s.id: s.camp for s in replay.soldiers}

    # Collect all attacks by the camp, grouped by round
    round_attacks: Dict[int, List[int]] = {}
    for act in replay.actions:
        if act.action_type != "Attack" or act.target_id < 0:
            continue
        if soldier_camp.get(act.soldier_id) != camp:
            continue
        round_attacks.setdefault(act.round_number, []).append(act.target_id)

    if not replay.rounds:
        return []
    max_rn = replay.rounds[-1].round_number
    sequence = []
    for rn in range(1, max_rn + 1):
        targets: List[int] = []
        for w in range(rn - 2, rn + 1):
            targets.extend(round_attacks.get(w, []))
        if len(targets) <= 1:
            sequence.append(0.5)
        else:
            target_counts = Counter(targets)
            sequence.append(max(target_counts.values()) / len(targets))
    return sequence


def _kiting_efficiency(replay: ParsedReplay, camp: str) -> dict:
    """Measure of hit-and-run (kiting) effectiveness.

    Looks for rounds where a piece **moves and then attacks** (or vice versa).
    A kite is counted when the move *increases* distance to the nearest enemy:
      ΔD = end_dist - start_dist > 0  (moving away from threat).

    Returns:
    - ``ratio``: fraction of move+attack actions that are successful kites
    - ``avg_gain``: average tiles of distance gained per kite
    - ``total_attempts``: total move+attack actions detected
    """
    soldier_camp = {s.id: s.camp for s in replay.soldiers}
    other_camp = "Blue" if camp == "Red" else "Red"

    # Group actions by round and soldier
    from collections import defaultdict
    actions_by_unit: Dict[int, Dict[int, list]] = defaultdict(lambda: defaultdict(list))
    for act in replay.actions:
        actions_by_unit[act.round_number][act.soldier_id].append(act)

    # Build position lookup
    pos_lookup: Dict[Tuple[int, int], Tuple[int, int]] = {}
    for snap in replay.rounds:
        for sid, pos in snap.positions.items():
            pos_lookup[(snap.round_number, sid)] = pos

    kites = 0
    total_gain = 0.0
    attempts = 0

    for rn, unit_actions in actions_by_unit.items():
        for sid, acts in unit_actions.items():
            if soldier_camp.get(sid) != camp:
                continue

            has_move = any(a.action_type == "Movement" and len(a.path) >= 2 for a in acts)
            has_attack = any(a.action_type == "Attack" for a in acts)
            if not (has_move and has_attack):
                continue

            # Find the move action with longest path
            move_act = max(
                (a for a in acts if a.action_type == "Movement" and len(a.path) >= 2),
                key=lambda a: len(a.path), default=None,
            )
            if move_act is None:
                continue

            start_pos = move_act.path[0]
            end_pos = move_act.path[-1]

            # Find nearest enemy at this round
            enemy_positions = [
                pos_lookup.get((rn, e_id))
                for e_id in soldier_camp
                if soldier_camp[e_id] == other_camp
                and pos_lookup.get((rn, e_id)) is not None
            ]
            if not enemy_positions:
                continue

            start_dist = min(
                abs(start_pos[0] - e[0]) + abs(start_pos[1] - e[1])
                for e in enemy_positions
            )
            end_dist = min(
                abs(end_pos[0] - e[0]) + abs(end_pos[1] - e[1])
                for e in enemy_positions
            )

            attempts += 1
            gain = end_dist - start_dist
            if gain > 0:
                kites += 1
                total_gain += gain

    return {
        "ratio": kites / attempts if attempts else 0.0,
        "avg_gain": total_gain / kites if kites else 0.0,
        "total_attempts": attempts,
    }


def _kiting_per_round(replay: ParsedReplay, camp: str) -> List[float]:
    """Per-round kite success (1.0 if a unit kited this round, else 0.0).

    A kite is counted when a unit both moves and attacks in the same round,
    and the move *increases* distance to the nearest enemy.

    :param replay: Parsed replay data.
    :type replay: ParsedReplay
    :param camp: Camp to evaluate.
    :type camp: str
    :returns: One value per round.
    :rtype: List[float]
    """
    soldier_camp = {s.id: s.camp for s in replay.soldiers}
    other_camp = "Blue" if camp == "Red" else "Red"

    # Build position lookup per round
    pos_lookup: Dict[Tuple[int, int], Tuple[int, int]] = {}
    for snap in replay.rounds:
        for sid, pos in snap.positions.items():
            pos_lookup[(snap.round_number, sid)] = pos

    # Group actions by round and soldier
    from collections import defaultdict
    actions_by_unit: Dict[int, Dict[int, list]] = defaultdict(lambda: defaultdict(list))
    for act in replay.actions:
        actions_by_unit[act.round_number][act.soldier_id].append(act)

    max_rn = replay.rounds[-1].round_number if replay.rounds else 0
    sequence = [0.0] * max_rn

    for rn in range(1, max_rn + 1):
        for sid, acts in actions_by_unit.get(rn, {}).items():
            if soldier_camp.get(sid) != camp:
                continue

            has_move = any(a.action_type == "Movement" and len(a.path) >= 2 for a in acts)
            has_attack = any(a.action_type == "Attack" for a in acts)
            if not (has_move and has_attack):
                continue

            move_act = max(
                (a for a in acts if a.action_type == "Movement" and len(a.path) >= 2),
                key=lambda a: len(a.path), default=None,
            )
            if move_act is None:
                continue

            start_pos = move_act.path[0]
            end_pos = move_act.path[-1]

            enemy_positions = [
                pos_lookup.get((rn, e_id))
                for e_id in soldier_camp
                if soldier_camp[e_id] == other_camp
                and pos_lookup.get((rn, e_id)) is not None
            ]
            if not enemy_positions:
                continue

            start_dist = min(
                abs(start_pos[0] - e[0]) + abs(start_pos[1] - e[1])
                for e in enemy_positions
            )
            end_dist = min(
                abs(end_pos[0] - e[0]) + abs(end_pos[1] - e[1])
                for e in enemy_positions
            )

            if end_dist - start_dist > 0:
                sequence[rn - 1] = 1.0

    return sequence


def aggregate_indicators(all_indicators: List[dict]) -> dict:
    """Aggregate indicators across matches.

    :param all_indicators: All indicator that we're interested
    :type all_indicators: List[dict]
    """

    n = len(all_indicators)
    if n == 0:
        return {}

    n_wins = sum(1 for ind in all_indicators if ind["player_won"])

    # Build: most common values
    all_str = [v for ind in all_indicators for v in ind["player_build"]["str"]]
    all_dex = [v for ind in all_indicators for v in ind["player_build"]["dex"]]
    all_int = [v for ind in all_indicators for v in ind["player_build"]["int"]]

    # Sequences: flatten all per-round values into one pool, take mean
    all_comp = [
        v for ind in all_indicators
        for v in ind["player_compactness"]
    ]
    avg_compactness = _mean(all_comp)

    all_ffi = [
        v for ind in all_indicators
        for v in ind["player_ffi"]
    ]
    avg_ffi = _mean(all_ffi)

    kei_ratios = [
        ind["player_kei"]["ratio"]
        for ind in all_indicators
        if ind["player_kei"]["total_attempts"] > 0
    ]
    avg_kei = _mean(kei_ratios)
    kei_attempts = sum(ind["player_kei"]["total_attempts"] for ind in all_indicators)

    # Opponent compactness (for comparison)
    opp_comp = [
        v for ind in all_indicators
        for v in ind["opponent_compactness"]
    ]
    opp_compactness = _mean(opp_comp)

    fb_rounds = [ind["first_blood_round"] for ind in all_indicators if ind["first_blood_round"] > 0]

    return {
        "n_matches": n,
        "n_wins": n_wins,
        "win_rate": n_wins / n * 100 if n else 0,
        "player_build": {
            "str": _mode(all_str),
            "dex": _mode(all_dex),
            "int": _mode(all_int),
        },
        "compactness": avg_compactness,
        "opponent_compactness": opp_compactness,
        "ffi": avg_ffi,
        "kei_ratio": avg_kei,
        "kei_total_attempts": kei_attempts,
        "avg_spell_count": _mean(ind["player_spell_count"] for ind in all_indicators),
        "avg_damage": _mean(ind["player_avg_damage"] for ind in all_indicators),
        "avg_first_blood_round": (
            sum(fb_rounds) / len(fb_rounds) if fb_rounds else 0
        ),
        "first_blood_win_rate": _first_blood_win_rate(all_indicators),
    }


# Helpers

def _mean(iterable):
    vals = list(iterable)
    return sum(vals) / len(vals) if vals else 0.0


def _mode(vals: list) -> list:
    if not vals:
        return []
    c = Counter(vals)
    max_count = max(c.values())
    return sorted(k for k, v in c.items() if v == max_count)


def _camp_spell_count(replay: ParsedReplay, camp: str) -> int:
    soldier_camp = {s.id: s.camp for s in replay.soldiers}
    return sum(
        1 for a in replay.actions
        if a.action_type == "Spell" and soldier_camp.get(a.soldier_id) == camp
    )


def _camp_avg_damage(replay: ParsedReplay, camp: str) -> float:
    soldier_camp = {s.id: s.camp for s in replay.soldiers}
    damages = [
        a.damage for a in replay.actions
        if a.action_type == "Attack" and a.damage > 0
        and soldier_camp.get(a.soldier_id) == camp
    ]
    return sum(damages) / len(damages) if damages else 0.0


def _first_blood_round(replay: ParsedReplay) -> int:
    for act in replay.actions:
        if act.action_type == "Death":
            return act.round_number
    return -1


def _first_blood_camp(replay: ParsedReplay) -> str:
    soldier_camp = {s.id: s.camp for s in replay.soldiers}
    for act in replay.actions:
        if act.action_type == "Death":
            victim_camp = soldier_camp.get(act.soldier_id, "")
            return "Blue" if victim_camp == "Red" else "Red"
    return ""


def _death_sequence(replay: ParsedReplay) -> List[Tuple[int, int, str]]:
    soldier_camp = {s.id: s.camp for s in replay.soldiers}
    return [
        (act.round_number, act.soldier_id, soldier_camp.get(act.soldier_id, ""))
        for act in replay.actions if act.action_type == "Death"
    ]


def _first_blood_win_rate(all_indicators: List[dict]) -> float:
    matches = [ind for ind in all_indicators if ind["first_blood_round"] > 0]
    if not matches:
        return 0.0
    return sum(1 for ind in matches if ind["player_won"]) / len(matches)
