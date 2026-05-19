"""Heuristic board evaluator — replaces random MCTS rollouts with fast scoring.

Returns a value in [-1, 1] indicating how favourable the board state is
for the current team. Positive = winning, negative = losing.

Components scored:
- HP advantage (team HP ratio difference)
- Numerical advantage (3v2, 3v1 bonuses)
- Focus-fire progress (how close to killing an enemy)
- Height advantage (controlling high ground)
- Action-point advantage (AP in bank)
"""

from env import Environment


def heuristic_evaluate(env: Environment) -> float:
    """Score a board state from the current team's perspective.

    :param env: The game environment (or a forked copy).
    :type env: Environment
    :returns: Score in [-1, 1]. Positive favours the current team.
    :rtype: float
    """
    current = env.current_piece
    if current is None:
        return 0.0
    team = current.team

    # --- Terminal states ---
    if env.is_game_over:
        p1_alive = any(p.is_alive for p in env.player1.pieces)
        p2_alive = any(p.is_alive for p in env.player2.pieces)
        if p1_alive and not p2_alive:
            return 1.0 if team == 1 else -1.0
        if p2_alive and not p1_alive:
            return 1.0 if team == 2 else -1.0
        return 0.0

    our_pieces = [p for p in env.action_queue if p.is_alive and p.team == team]
    enemy_pieces = [p for p in env.action_queue if p.is_alive and p.team != team]

    if not our_pieces and not enemy_pieces:
        return 0.0
    if not our_pieces:
        return -0.9
    if not enemy_pieces:
        return 0.9

    score = 0.0

    # --- 1. HP advantage (weight: 40%) ---
    our_hp = sum(p.health for p in our_pieces)
    our_max_hp = sum(p.max_health for p in our_pieces)
    enemy_hp = sum(p.health for p in enemy_pieces)
    enemy_max_hp = sum(p.max_health for p in enemy_pieces)

    our_hp_ratio = our_hp / max(our_max_hp, 1)
    enemy_hp_ratio = enemy_hp / max(enemy_max_hp, 1)
    hp_diff = our_hp_ratio - enemy_hp_ratio
    score += 0.4 * hp_diff

    # --- 2. Numerical advantage (weight: 30%) ---
    num_diff = len(our_pieces) - len(enemy_pieces)
    # Scale: +1 piece ≈ +0.15 score
    score += 0.3 * (num_diff / 3.0)

    # --- 3. Focus-fire progress (weight: 15%) ---
    if enemy_pieces:
        min_enemy_hp_ratio = min(e.health / max(e.max_health, 1) for e in enemy_pieces)
        # Closer to 0 = closer to killing one → bonus
        fire_progress = 1.0 - min_enemy_hp_ratio
        score += 0.15 * (fire_progress - 0.5)

    # --- 4. Height advantage (weight: 10%) ---
    if our_pieces and enemy_pieces:
        our_height = sum(p.height for p in our_pieces) / len(our_pieces)
        enemy_height = sum(p.height for p in enemy_pieces) / len(enemy_pieces)
        height_diff = (our_height - enemy_height) / 5.0
        score += 0.1 * height_diff

    # --- 5. AP advantage (weight: 5%) ---
    our_ap = sum(p.action_points for p in our_pieces)
    enemy_ap = sum(p.action_points for p in enemy_pieces)
    max_possible = max(len(our_pieces), len(enemy_pieces), 1) * 3.0
    ap_diff = (our_ap - enemy_ap) / max_possible
    score += 0.05 * ap_diff

    return max(-1.0, min(1.0, score))
