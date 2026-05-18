"""Action decoder — converts policy network output to a valid ActionSet.

Network output (6 logits):
0–2: target priority for enemies 0, 1, 2 (softmax → target choice)
3.   move_bias: 0 = hold position, 1 = advance toward target
4.   retreat_bias: 0 = never retreat, 1 = retreat when low HP
5.   spare (unused, reserved)

The decoder masks invalid actions (out-of-range attacks, unreachable moves)
and produces a legal ActionSet.
"""

from typing import List

import numpy as np

from env import Environment
from strategies._utils import calculate_distance
from utils import ActionSet, AttackContext, Point


def decode_action(
    logits: np.ndarray,
    env: Environment,
) -> ActionSet:
    """Convert policy network logits to a valid ActionSet.

    :param logits: 6-dim array from policy_net.forward().
    :type logits: np.ndarray
    :param env: The current game environment.
    :type env: Environment
    :returns: A valid ActionSet.
    :rtype: ActionSet
    """
    action = ActionSet()
    current = env.current_piece

    if current is None or not current.is_alive:
        return action

    # Identify enemies
    enemies = [
        p for p in env.action_queue
        if p.team != current.team and p.is_alive
    ]
    if not enemies:
        return action

    # --- Target selection (softmax over target priorities) ---
    target_logits = np.array(logits[0:3], dtype=np.float64)
    # Mask out enemies that don't exist or are dead
    for i in range(3):
        if i >= len(enemies):
            target_logits[i] = -1e9
    exp = np.exp(target_logits - np.max(target_logits))
    target_probs = exp / (np.sum(exp) + 1e-10)
    primary_idx = int(np.argmax(target_probs))
    primary = enemies[primary_idx]

    # --- Move decision ---
    move_bias = float(np.clip(logits[3], 0.0, 1.0))
    retreat_bias = float(np.clip(logits[4], 0.0, 1.0))
    retreat_hp = 0.3  # retreat when below 30% HP
    in_range = calculate_distance(current.position, primary.position) <= current.attack_range
    health_ratio = current.health / max(current.max_health, 1)

    should_retreat = (
        retreat_bias > 0.5
        and health_ratio < retreat_hp
        and enemies
    )

    if should_retreat:
        # Move away from the closest enemy
        closest = min(enemies, key=lambda e: calculate_distance(current.position, e.position))
        from strategy_utils import get_legal_moves
        moves = get_legal_moves(env)
        if moves:
            best = max(moves, key=lambda m: calculate_distance(m, closest.position))
            action.move = True
            action.move_target = best
        else:
            action.move = False
    elif move_bias > 0.5 and not in_range:
        # Advance toward primary target
        from strategy_utils import get_legal_moves
        moves = get_legal_moves(env)
        if moves:
            best = min(moves, key=lambda m: calculate_distance(m, primary.position))
            action.move = True
            action.move_target = best
        else:
            action.move = False
    elif in_range:
        # Already in range — don't waste AP moving
        action.move = False
    else:
        action.move = False

    # --- Attack decision ---
    if in_range:
        action.attack = True
        ctx = AttackContext()
        ctx.attacker = current
        ctx.target = primary
        action.attack_context = ctx
    else:
        action.attack = False

    # Check if moving into range enables an attack (advance-and-attack)
    if action.move and not action.attack:
        new_dist = calculate_distance(action.move_target, primary.position)
        if new_dist <= current.attack_range:
            action.attack = True
            ctx = AttackContext()
            ctx.attacker = current
            ctx.target = primary
            action.attack_context = ctx

    action.spell = False
    return action
