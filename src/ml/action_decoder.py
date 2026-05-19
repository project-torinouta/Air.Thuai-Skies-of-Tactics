"""Action decoder — converts policy network output to a valid ActionSet.

Network output adjusts the proven sniper behavior:
0. target_bias: 0 = lowest-HP target, 1 = highest-HP target
1. positional_deviation: 0 = stay near allies, 1 = flank independently
2. aggression: 0 = hold when out of range, 1 = always advance
3. retreat_hp: 0 = never retreat, 1 = retreat at 50% HP threshold
4. focus_fire: 0 = spread damage, 1 = always focus lowest HP
5. spare (unused)

With all outputs = 0.5, behaviour is identical to the hand-coded sniper.
The ES then nudges these parameters to find improvements.
"""

from typing import List

import numpy as np

from env import Environment
from strategies._utils import calculate_distance
from utils import ActionSet, AttackContext, Point


def _sniper_default(env: Environment, enemies: List) -> Point:
    """Compute where the hand-coded sniper would move.

    :param env: Game environment.
    :param enemies: List of alive enemy pieces.
    :returns: Target movement position.
    """
    from strategy_utils import get_legal_moves
    current = env.current_piece
    primary = min(enemies, key=lambda e: e.health)

    if calculate_distance(current.position, primary.position) <= current.attack_range:
        return current.position  # don't move, attack instead

    moves = get_legal_moves(env)
    if not moves:
        return current.position
    return min(moves, key=lambda m: calculate_distance(m, primary.position))


def _find_flank_position(env: Environment, enemies: List) -> Point:
    """Find a flanking position that attacks from a different angle.

    :param env: Game environment.
    :param enemies: List of alive enemy pieces.
    :returns: A flanking position.
    """
    from strategy_utils import get_legal_moves
    current = env.current_piece
    moves = get_legal_moves(env)
    if not moves:
        return current.position

    # Find the average enemy position
    avg_x = sum(e.position.x for e in enemies) / len(enemies)
    avg_y = sum(e.position.y for e in enemies) / len(enemies)

    # Flank: pick a move that is perpendicular to the direct approach
    direct = min(moves, key=lambda m: calculate_distance(m, Point(int(avg_x), int(avg_y))))
    return direct


def decode_action(logits: np.ndarray, env: Environment) -> ActionSet:
    """Convert policy network logits to a valid ActionSet.

    :param logits: 6-dim array. Each in roughly [-2, 2] range (tanh-activated).
    :param env: The current game environment.
    :returns: A valid ActionSet.
    """
    action = ActionSet()
    current = env.current_piece

    if current is None or not current.is_alive:
        return action

    enemies = [p for p in env.action_queue if p.team != current.team and p.is_alive]
    if not enemies:
        return action

    # Clip outputs to [-2, 2] then normalise to [0, 1]
    params = np.clip(logits, -2.0, 2.0) / 4.0 + 0.5  # → [0, 1]

    target_bias = float(params[0])    # 0 = lowest HP, 1 = highest HP
    deviation = float(params[1])      # 0 = stay with allies, 1 = flank
    aggression = float(params[2])     # 0 = hold, 1 = advance
    retreat_hp = float(params[3])     # retreat threshold
    focus_fire = float(params[4])     # 0 = spread damage, 1 = focus-fire finish

    # --- Target selection ---
    # Score each enemy: lower = more preferred
    # focus_fire controls how much to weight finishing low-HP enemies
    # vs spreading damage or targeting high-threat enemies
    enemy_scores = []
    for e in enemies:
        hp_score = e.health / max(float(e.max_health), 1.0)
        dist_score = calculate_distance(current.position, e.position) / 20.0
        # When focus_fire is high: strongly prefer lower HP
        # When focus_fire is low: consider distance and HP together
        score = (1.0 - focus_fire * 0.6) * hp_score + (1.0 - target_bias * 0.5) * dist_score
        enemy_scores.append(score)

    best_idx = int(np.argmin(enemy_scores))
    primary = enemies[best_idx]

    in_range = calculate_distance(current.position, primary.position) <= current.attack_range
    health_ratio = current.health / max(float(current.max_health), 1.0)
    should_retreat = retreat_hp > 0.4 and health_ratio < (retreat_hp * 0.5)

    # Retreat: move away from nearest enemy
    if should_retreat:
        closest = min(enemies, key=lambda e: calculate_distance(current.position, e.position))
        dx = current.position.x - closest.position.x
        dy = current.position.y - closest.position.y
        dist = max(abs(dx), abs(dy), 1)
        target = Point(
            int(np.clip(current.position.x + dx // dist, 0, int(env.board.width) - 1)),
            int(np.clip(current.position.y + dy // dist, 0, int(env.board.height) - 1)),
        )
        from strategy_utils import get_legal_moves
        moves = get_legal_moves(env)
        if moves:
            best = max(moves, key=lambda m: calculate_distance(m, closest.position))
            action.move = True
            action.move_target = best
            action.attack = False
            action.spell = False
            return action

    # Positioning: blend between sniper default and flanking
    if deviation > 0.6:
        dest = _find_flank_position(env, enemies)
    else:
        dest = _sniper_default(env, enemies)

    at_dest = (dest.x == current.position.x and dest.y == current.position.y)

    # Attack decision
    if in_range:
        action.move = False
        action.attack = True
        ctx = AttackContext()
        ctx.attacker = current
        ctx.target = primary
        action.attack_context = ctx
    elif not at_dest:
        action.move = True
        action.move_target = dest
        new_dist = calculate_distance(dest, primary.position)
        if new_dist <= current.attack_range and aggression > 0.3:
            action.attack = True
            ctx = AttackContext()
            ctx.attacker = current
            ctx.target = primary
            action.attack_context = ctx
        else:
            action.attack = False
    elif aggression >= 0.4:
        from strategy_utils import get_legal_moves
        moves = get_legal_moves(env)
        if moves:
            best = min(moves, key=lambda m: calculate_distance(m, primary.position))
            action.move = True
            action.move_target = best
            new_dist = calculate_distance(best, primary.position)
            if new_dist <= current.attack_range:
                action.attack = True
                ctx = AttackContext()
                ctx.attacker = current
                ctx.target = primary
                action.attack_context = ctx
            else:
                action.attack = False
        else:
            action.move = action.attack = False
    else:
        action.move = action.attack = False

    action.spell = False
    return action
