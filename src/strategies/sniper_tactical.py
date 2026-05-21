# Copyright 2026 AshGrey <ashgrey.huaier@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in the
# Software without restriction, including without limitation the rights to use, copy,
# modify, merge, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to the following
# conditions:
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

"""Tactical sniper — STR 29, bow + heavy armour, low-HP assassination focus.

Same optimal build as the base sniper, tuned for elimination speed:

- Prioritise the LOWEST-health enemy with every piece every turn. Never split
  damage across multiple targets — snowball the 3v2 advantage.
- Maintain moderate formation spread (3-5 tiles) to create flanking angles
  around the enemy deathball, forcing them to split focus.
- No retreat: every damage trade is favourable at STR 29.
"""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point

_FORMATION_SPACING = 4


def get_sniper_tactical_init_strategy() -> Callable[..., List[PieceArg]]:
    """Return the tactical sniper initialisation strategy.

    STR 29, DEX 1, bow + heavy armour. Starting positions are spread to
    create flanking options.

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


def get_sniper_tactical_action_strategy() -> Callable[..., ActionSet]:
    """Return the tactical sniper action strategy.

    1. Always attack the lowest-health enemy in range. Never split damage.
    2. If out of range, advance while maintaining ~4 tile spacing from
       teammates to create flanking angles.
    3. Advance-and-attack when movement brings the target into bow range.
    4. Never retreat — every trade is favourable.

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

        from strategy_utils import get_legal_moves

        enemies = [
            p for p in env.action_queue
            if p.team != current.team and p.is_alive
        ]
        if not enemies:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        # Always target the lowest-health enemy for quick elimination
        enemies.sort(key=lambda p: p.health)
        primary = enemies[0]

        allies = [
            p for p in env.action_queue
            if p.team == current.team and p.id != current.id and p.is_alive
        ]

        dist_to_primary = calculate_distance(current.position, primary.position)

        #
        # 1. In bow range — attack, never waste AP on movement
        #
        if dist_to_primary <= current.attack_range:
            action.move = False
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = primary
            action.spell = False
            return action

        #
        # 2. Out of range — advance with formation spacing
        #
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        def move_score(pos) -> float:
            d_to_enemy = calculate_distance(pos, primary.position)
            # Penalise clustering too close to allies
            spacing = 0.0
            for ally in allies:
                d = calculate_distance(pos, ally.position)
                if d < _FORMATION_SPACING:
                    spacing += (_FORMATION_SPACING - d) * 2
            return -d_to_enemy - spacing

        best_move = max(legal_moves, key=move_score)
        action.move = True
        action.move_target = best_move

        # Advance-and-attack
        new_dist = calculate_distance(best_move, primary.position)
        if new_dist <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = primary
        else:
            action.attack = False

        action.spell = False
        return action

    return strategy
