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

"""Sniper v1.0.3 baseline — STR 30, DEX 0, bow + heavy armour.

Preserves the original STR 30 build for comparison benchmarking against
the refined STR 29 / DEX 1 variant in sniper.py.

- STR 30: bow deals 46-23=23 damage per hit, 110 HP
- DEX 0: initiative sacrificed for max STR
- Heavy armour caps incoming attacks
- Advance-and-attack, focus-fire lowest-health enemy
"""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


def get_sniper_init_strategy_v103() -> Callable[..., List[PieceArg]]:
    """Return the sniper v1.0.3 initialisation strategy (STR 30 baseline).

    Each piece: STR 30 (max), DEX 0, bow + heavy armour.

    :returns: A callable that takes an ``InitGameMessage`` and returns
        a list of ``PieceArg``.
    :rtype: Callable
    """
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
        positions = allocate_init_positions(board, pid, init_message.piece_cnt, order)
        piece_args: List[PieceArg] = []
        for pos in positions:
            arg = PieceArg()
            arg.strength = 30
            arg.dexterity = 0
            arg.intelligence = 0
            arg.equip = Point(3, 3)
            arg.pos = pos
            piece_args.append(arg)
        return piece_args

    return strategy


def get_sniper_action_strategy_v103() -> Callable[..., ActionSet]:
    """Return the sniper v1.0.3 action strategy (same logic, original).

    1. Focus-fire the lowest-health enemy within bow range
    2. If no enemy is in range, advance toward the lowest-health enemy.
       If the move brings the target into bow range, attack in the
       same turn (advance-and-attack) instead of waiting.
    3. Never retreat — the sniper wins every damage trade decisively.

    :returns: A callable action strategy.
    :rtype: Callable
    """
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current = env.current_piece

        if current is None or not current.is_alive:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        enemies = [
            p for p in env.action_queue
            if p.team != current.team and p.is_alive
        ]
        if not enemies:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        # Focus-fire: sort by health ascending
        enemies.sort(key=lambda p: p.health)
        primary = enemies[0]
        dist = calculate_distance(current.position, primary.position)

        if dist <= current.attack_range:
            # In bow range — attack, don't waste AP on movement
            action.move = False
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = primary
        else:
            # Out of range — advance toward primary
            from strategy_utils import get_legal_moves

            legal_moves = get_legal_moves(env)
            if legal_moves:
                best_move = min(
                    legal_moves,
                    key=lambda m: calculate_distance(m, primary.position),
                )
                action.move = True
                action.move_target = best_move

                # Advance-and-attack: if moving brings the target into
                # bow range, attack in the same turn
                new_dist = calculate_distance(best_move, primary.position)
                if new_dist <= current.attack_range:
                    action.attack = True
                    action.attack_context = AttackContext()
                    action.attack_context.attacker = current
                    action.attack_context.target = primary
                else:
                    action.attack = False
            else:
                action.move = False
                action.attack = False

        action.spell = False
        return action

    return strategy
