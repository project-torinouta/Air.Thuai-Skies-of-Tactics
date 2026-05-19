"""Compute tactical indicators from parsed replay data.

Indicators cover three categories:

**Initial strategy (build):**
- STR/DEX/INT allocation per piece
- Starting position spread (formation tightness)
- Weapon type

**Action strategy (tactics):**
- Target preference: lowest-HP vs closest enemy
- Focus-fire coordination (multiple teammates hitting same target)
- Formation spread over time
- Advance/retreat tendency
- Spell usage
- Damage efficiency (damage per attack)

**Match outcome:**
- First blood (who, when)
- Death sequence
- Win/loss
"""

from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from analysis.models import ParsedReplay


# ---------------------------------------------------------------------------
# Per-match indicators
# ---------------------------------------------------------------------------


def compute_indicators(replay: ParsedReplay) -> dict:
    """Compute all indicators for a single replay.

    :param replay: Parsed replay data.
    :type replay: ParsedReplay
    :returns: Dictionary of indicator values.
    :rtype: dict
    """
    return {
        # Build
        "str_values": _build_str_values(replay),
        "dex_values": _build_dex_values(replay),
        "int_values": _build_int_values(replay),
        "formation_spread_init": _formation_spread(replay, round_idx=0),
        "weapon_types": _weapon_types(replay),

        # Tactics
        "target_lowest_hp_ratio": _target_lowest_hp_ratio(replay),
        "focus_fire_events": _focus_fire_count(replay),
        "focus_fire_rounds": _focus_fire_rounds(replay),
        "avg_formation_spread": _avg_formation_spread(replay),
        "spell_count": _spell_count(replay),
        "avg_damage": _avg_damage(replay),
        "total_attacks": _total_attacks(replay),
        "advance_ratio": _advance_vs_retreat_ratio(replay),
        "retreat_count": _retreat_count(replay),

        # Outcomes
        "first_blood_round": _first_blood_round(replay),
        "first_blood_camp": _first_blood_camp(replay),
        "total_rounds": replay.rounds[-1].round_number if replay.rounds else 0,
        "player_won": replay.winner == replay.ashgrey_camp,
        "death_sequence": _death_sequence(replay),
        "hp_curves": _hp_curves(replay),
    }


def _build_str_values(replay: ParsedReplay) -> List[int]:
    return [s.strength for s in replay.soldiers]


def _build_dex_values(replay: ParsedReplay) -> List[int]:
    return [s.dexterity for s in replay.soldiers]


def _build_int_values(replay: ParsedReplay) -> List[int]:
    return [s.intelligence for s in replay.soldiers]


def _weapon_types(replay: ParsedReplay) -> List[str]:
    return [s.weapon_name for s in replay.soldiers]


def _formation_spread(replay: ParsedReplay, round_idx: int = 0) -> float:
    """Average pairwise Manhattan distance between teammates at a snapshot."""
    if round_idx >= len(replay.rounds):
        return 0.0
    snapshot = replay.rounds[round_idx]
    return _pairwise_dist(snapshot.positions)


def _avg_formation_spread(replay: ParsedReplay) -> float:
    """Average formation spread across all rounds."""
    spreads = []
    for snap in replay.rounds:
        sp = _pairwise_dist(snap.positions)
        if sp > 0:
            spreads.append(sp)
    return sum(spreads) / len(spreads) if spreads else 0.0


def _pairwise_dist(positions: Dict[int, Tuple[int, int]]) -> float:
    """Average pairwise Manhattan distance among pieces."""
    coords = list(positions.values())
    if len(coords) < 2:
        return 0.0
    total = 0.0
    count = 0
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            total += abs(coords[i][0] - coords[j][0]) + abs(coords[i][1] - coords[j][1])
            count += 1
    return total / count if count else 0.0


def _target_lowest_hp_ratio(replay: ParsedReplay) -> float:
    """Ratio of attacks targeting the lowest-HP alive enemy."""
    # Build HP timeline from snapshots
    hp_before_round: Dict[int, Dict[int, int]] = {}
    prev_hp: Dict[int, int] = {}
    for snap in replay.rounds:
        for sid, hp in snap.hp.items():
            prev_hp[sid] = hp
        hp_before_round[snap.round_number] = dict(prev_hp)

    soldier_camp = {s.id: s.camp for s in replay.soldiers}

    # For each attack, check if the target was the lowest-HP enemy at that time
    correct = 0
    total = 0
    for act in replay.actions:
        if act.action_type != "Attack":
            continue
        total += 1
        rn = act.round_number
        attacker_camp = soldier_camp.get(act.soldier_id, "")
        hp_state = hp_before_round.get(rn, {})

        # Find alive enemies at this round
        enemy_hp = {
            sid: h for sid, h in hp_state.items()
            if soldier_camp.get(sid, "") != attacker_camp and h > 0
        }
        if not enemy_hp:
            continue
        lowest_enemy = min(enemy_hp, key=lambda e: enemy_hp[e])
        if act.target_id == lowest_enemy:
            correct += 1

    return correct / total if total else 0.0


def _focus_fire_count(replay: ParsedReplay) -> int:
    """Number of rounds where 2+ teammates attacked the same target."""
    soldier_camp = {s.id: s.camp for s in replay.soldiers}
    round_attacks: Dict[int, Dict[int, List[int]]] = defaultdict(
        lambda: defaultdict(list),
    )

    for act in replay.actions:
        if act.action_type != "Attack" or act.target_id < 0:
            continue
        round_attacks[act.round_number][act.target_id].append(act.soldier_id)

    focus = 0
    for targets in round_attacks.values():
        for target, attackers in targets.items():
            camps = {soldier_camp.get(a, "") for a in attackers}
            if len(attackers) >= 2 and len(camps) == 1:
                focus += 1
                break  # one focus event per round
    return focus


def _focus_fire_rounds(replay: ParsedReplay) -> List[int]:
    """List of round numbers where focus-fire occurred."""
    soldier_camp = {s.id: s.camp for s in replay.soldiers}
    round_attacks: Dict[int, Dict[int, List[int]]] = defaultdict(
        lambda: defaultdict(list),
    )
    for act in replay.actions:
        if act.action_type != "Attack" or act.target_id < 0:
            continue
        round_attacks[act.round_number][act.target_id].append(act.soldier_id)

    rounds = []
    for rn, targets in sorted(round_attacks.items()):
        for target, attackers in targets.items():
            camps = {soldier_camp.get(a, "") for a in attackers}
            if len(attackers) >= 2 and len(camps) == 1:
                rounds.append(rn)
                break
    return rounds


def _spell_count(replay: ParsedReplay) -> int:
    return sum(1 for a in replay.actions if a.action_type == "Spell")


def _avg_damage(replay: ParsedReplay) -> float:
    damages = [a.damage for a in replay.actions if a.action_type == "Attack" and a.damage > 0]
    return sum(damages) / len(damages) if damages else 0.0


def _total_attacks(replay: ParsedReplay) -> int:
    return sum(1 for a in replay.actions if a.action_type == "Attack")


def _advance_vs_retreat_ratio(replay: ParsedReplay) -> float:
    """Ratio of moves that advance toward the enemy vs all moves.

    An advance is a move that reduces distance to the nearest enemy camp.
    """
    soldier_camp = {s.id: s.camp for s in replay.soldiers}
    moves_toward = 0
    total_moves = 0

    for act in replay.actions:
        if act.action_type != "Movement" or len(act.path) < 2:
            continue
        total_moves += 1
        sid = act.soldier_id
        start = act.path[0]

        # Find centre of the other camp's positions at this round
        other_camp = "Blue" if soldier_camp.get(sid) == "Red" else "Red"
        snap = _snapshot_at(replay, act.round_number)

        other_z = [s.z for s in replay.soldiers if s.camp == other_camp]
        if not other_z:
            continue
        enemy_centre_z = sum(other_z) / len(other_z)

        start_dist = abs(start[1] - enemy_centre_z)
        end_dist = abs(act.path[-1][1] - enemy_centre_z)
        if end_dist < start_dist:
            moves_toward += 1

    return moves_toward / total_moves if total_moves else 0.0


def _retreat_count(replay: ParsedReplay) -> int:
    """Count of retreat actions (moving away from enemy)."""
    soldier_camp = {s.id: s.camp for s in replay.soldiers}
    retreats = 0
    for act in replay.actions:
        if act.action_type != "Movement" or len(act.path) < 2:
            continue
        sid = act.soldier_id
        start = act.path[0]
        other_camp = "Blue" if soldier_camp.get(sid) == "Red" else "Red"
        other_z = [s.z for s in replay.soldiers if s.camp == other_camp]
        if not other_z:
            continue
        enemy_centre_z = sum(other_z) / len(other_z)

        start_dist = abs(start[1] - enemy_centre_z)
        end_dist = abs(act.path[-1][1] - enemy_centre_z)
        if end_dist > start_dist:
            retreats += 1
    return retreats


def _first_blood_round(replay: ParsedReplay) -> int:
    """Round of the first death, or -1 if none."""
    for act in replay.actions:
        if act.action_type == "Death":
            return act.round_number
    return -1


def _first_blood_camp(replay: ParsedReplay) -> str:
    """Camp that got the first kill."""
    soldier_camp = {s.id: s.camp for s in replay.soldiers}
    for act in replay.actions:
        if act.action_type == "Death":
            victim_camp = soldier_camp.get(act.soldier_id, "")
            killer_camp = "Blue" if victim_camp == "Red" else "Red"
            return killer_camp
    return ""


def _death_sequence(replay: ParsedReplay) -> List[Tuple[int, int, str]]:
    """List of ``(round, soldier_id, camp)`` for each death in order."""
    soldier_camp = {s.id: s.camp for s in replay.soldiers}
    deaths = []
    for act in replay.actions:
        if act.action_type == "Death":
            camp = soldier_camp.get(act.soldier_id, "")
            deaths.append((act.round_number, act.soldier_id, camp))
    return deaths


def _hp_curves(replay: ParsedReplay) -> Dict[int, List[Tuple[int, int]]]:
    """HP over time per soldier: ``{sid: [(round, hp), ...]}``."""
    curves: Dict[int, List[Tuple[int, int]]] = {}
    for snap in replay.rounds:
        for sid, hp in snap.hp.items():
            curves.setdefault(sid, []).append((snap.round_number, hp))
    return curves


def _snapshot_at(replay: ParsedReplay, round_number: int):
    """Find the snapshot closest to (but not after) a given round."""
    best = None
    for snap in replay.rounds:
        if snap.round_number <= round_number:
            best = snap
    return best


# ---------------------------------------------------------------------------
# Cross-match aggregation
# ---------------------------------------------------------------------------


def aggregate_indicators(all_indicators: List[dict]) -> dict:
    """Aggregate indicators across multiple matches.

    :param all_indicators: List of per-match indicator dicts.
    :type all_indicators: List[dict]
    :returns: Aggregated statistics.
    :rtype: dict
    """
    n = len(all_indicators)
    if n == 0:
        return {}

    builds = []
    for ind in all_indicators:
        for s, d, i in zip(ind["str_values"], ind["dex_values"], ind["int_values"]):
            builds.append((s, d, i))

    return {
        "n_matches": n,
        "n_wins": sum(1 for ind in all_indicators if ind["player_won"]),
        "builds": builds,
        "weapon_counts": Counter(
            w for ind in all_indicators for w in ind["weapon_types"]
        ),
        "avg_formation_spread": sum(
            ind["avg_formation_spread"] for ind in all_indicators
        ) / n,
        "avg_focus_fire_rounds": sum(
            ind["focus_fire_events"] for ind in all_indicators
        ) / n,
        "avg_target_lowest_hp_ratio": sum(
            ind["target_lowest_hp_ratio"] for ind in all_indicators
        ) / n,
        "avg_first_blood_round": sum(
            ind["first_blood_round"] for ind in all_indicators
            if ind["first_blood_round"] > 0
        ) / max(sum(1 for ind in all_indicators if ind["first_blood_round"] > 0), 1),
        "avg_damage": sum(
            ind["avg_damage"] for ind in all_indicators
        ) / n,
        "avg_spell_count": sum(
            ind["spell_count"] for ind in all_indicators
        ) / n,
        "first_blood_wins": _first_blood_win_rate(all_indicators),
        "advance_ratio": sum(
            ind["advance_ratio"] for ind in all_indicators
        ) / n,
        "total_rounds": [ind["total_rounds"] for ind in all_indicators],
        "player_won_list": [ind["player_won"] for ind in all_indicators],
    }


def _first_blood_win_rate(all_indicators: List[dict]) -> float:
    """Win rate when getting / conceding first blood."""
    matches_with_fb = [ind for ind in all_indicators if ind["first_blood_round"] > 0]
    if not matches_with_fb:
        return 0.0
    return sum(1 for ind in matches_with_fb if ind["player_won"]) / len(matches_with_fb)
