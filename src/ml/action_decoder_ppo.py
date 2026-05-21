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

"""Action decoder — converts PPO discrete actions to game ActionSet.

Action space (4 discrete heads):
  move_idx (0-2):   0=advance toward enemy, 1=stay, 2=retreat from enemy
  target_idx (0-2): which enemy to target (sorted by proximity)
  attack_idx (0-1): whether to attack
  spell_idx (0-1):  whether to cast spell (always 0 for now)
"""

from typing import List, Tuple

import numpy as np

from env import Environment
from strategies._utils import calculate_distance
from utils import ActionSet, AttackContext


def decode_ppo_action(
    action: np.ndarray,
    env: Environment,
) -> ActionSet:
    """Convert a 4-element PPO action to a valid ActionSet.

    :param action: [move_idx, target_idx, attack_idx, spell_idx]
    :param env: Current game environment.
    :returns: Executable ActionSet.
    """
    result = ActionSet()
    current = env.current_piece

    if current is None or not current.is_alive:
        result.move = False
        result.attack = False
        result.spell = False
        return result

    from strategy_utils import get_legal_moves

    move_idx = int(action[0])
    target_idx = int(action[1])
    do_attack = bool(action[2])

    # --- Target selection: sort enemies by proximity, pick target_idx ---
    enemies = [
        p for p in env.action_queue
        if p.team != current.team and p.is_alive
    ]
    if not enemies:
        result.move = False
        result.attack = False
        result.spell = False
        return result

    enemies.sort(key=lambda e: calculate_distance(current.position, e.position))
    target = enemies[min(target_idx, len(enemies) - 1)]
    in_range = calculate_distance(current.position, target.position) <= current.attack_range
    legal = get_legal_moves(env)

    # --- Movement: 0=advance, 1=stay, 2=retreat ---
    if move_idx == 0 and legal:  # advance toward target
        best = min(legal, key=lambda m: calculate_distance(m, target.position))
        result.move = True
        result.move_target = best
    elif move_idx == 2 and legal:  # retreat from nearest enemy
        nearest = min(enemies, key=lambda e: calculate_distance(current.position, e.position))
        best = max(legal, key=lambda m: calculate_distance(m, nearest.position))
        result.move = True
        result.move_target = best
    else:  # stay
        result.move = False

    # --- Attack ---
    if in_range and do_attack:
        result.attack = True
        ctx = AttackContext()
        ctx.attacker = current
        ctx.target = target
        result.attack_context = ctx
    elif result.move and do_attack:
        new_dist = calculate_distance(result.move_target, target.position)
        if new_dist <= current.attack_range:
            result.attack = True
            ctx = AttackContext()
            ctx.attacker = current
            ctx.target = target
            result.attack_context = ctx
        else:
            result.attack = False
    else:
        result.attack = False

    result.spell = False
    return result
