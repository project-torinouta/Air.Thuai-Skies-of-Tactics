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

"""Camper — advance to bow-range edge, then hold.

Replicates the Blue camp's tactic from the Saiblo replay:
1. Advance toward the enemy until the closest target is at exactly bow
   range (9 tiles).
2. Stop and never move again — attack every turn.
3. Focus fire the lowest-HP enemy.

This is subtly different from the base sniper which keeps advancing
indefinitely, wasting AP that could be used for attacks.
"""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


def get_camper_init_strategy() -> Callable[..., List[PieceArg]]:
    """Standard sniper init — back row, STR 29 / DEX 1 / INT 0."""
    def strategy(init_message: InitGameMessage) -> List[PieceArg]:
        board = init_message.board
        pid = init_message.id
        if pid == 1:
            order = [
                (x, y)
                for y in range(5, 0, -1)
                for x in range(2, board.width - 2)
            ]
        else:
            order = [
                (x, y)
                for y in range(board.height - 6, board.height)
                for x in range(board.width - 3, 2, -1)
            ]
        positions = allocate_init_positions(
            board, pid, init_message.piece_cnt, order,
        )
        piece_args: List[PieceArg] = []
        for pos in positions:
            arg = PieceArg()
            arg.strength = 29
            arg.dexterity = 1
            arg.intelligence = 0
            arg.equip = Point(3, 3)
            arg.pos = pos
            piece_args.append(arg)
        return piece_args
    return strategy


def get_camper_action_strategy() -> Callable[..., ActionSet]:
    """Advance to bow-range edge, then hold position.

    1. If any enemy is in range — attack the lowest-HP one, never move.
    2. If no enemy is in range — advance until the closest enemy would be
       at range 9.  Then stop permanently.
    """
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current = env.current_piece

        if current is None or not current.is_alive:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        from strategy_utils import get_legal_moves

        enemies = [
            p for p in env.action_queue
            if p.team != current.team and p.is_alive
        ]
        allies = [
            p for p in env.action_queue
            if p.team == current.team and p.id != current.id and p.is_alive
        ]
        if not enemies:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        closest = min(
            enemies,
            key=lambda e: calculate_distance(current.position, e.position),
        )
        dist = calculate_distance(current.position, closest.position)

        # ---- IN RANGE — attack, never move ----
        in_range = [
            e for e in enemies
            if calculate_distance(current.position, e.position)
            <= current.attack_range
        ]
        if in_range:
            target = min(in_range, key=lambda p: p.health)
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
            action.move = False
            action.spell = False
            return action

        # ---- OUT OF RANGE — advance to edge of bow range ----
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        def move_score(pos: Point) -> float:
            d = calculate_distance(pos, closest.position)
            # Ideally we want to be at EXACTLY bow range (d=9).
            # Prefer being at the edge over being too close.
            if d <= current.attack_range:
                # In range from this position — prefer range-edge (9 > 8 > 7 ...)
                return -abs(d - float(current.attack_range))
            # Not in range — get as close as possible
            return -d

        best = max(legal_moves, key=move_score)
        action.move = True
        action.move_target = best

        # Advance-and-attack
        new_dist = calculate_distance(best, closest.position)
        if new_dist <= current.attack_range:
            in_range_after = [
                e for e in enemies
                if calculate_distance(best, e.position)
                <= current.attack_range
            ]
            if in_range_after:
                target = min(in_range_after, key=lambda p: p.health)
                action.attack = True
                action.attack_context = AttackContext()
                action.attack_context.attacker = current
                action.attack_context.target = target
            else:
                action.attack = False
        else:
            action.attack = False

        action.spell = False
        return action

    return strategy
