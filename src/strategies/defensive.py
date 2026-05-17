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

"""Defensive strategy — ranged kiting with bow + light armour."""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


def get_defensive_init_strategy() -> Callable[..., List[PieceArg]]:
    """Return a defensive initialisation strategy.

    Prioritises dexterity and intelligence with rearline positioning.
    Each piece is configured with strength=5, dexterity=15,
    intelligence=10, bow + light armour.

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
                for y in range(3, board.boarder)
                for x in range(3, board.width - 3)
            ]
        else:
            order = [
                (x, y)
                for y in range(board.height - 1, board.boarder, -1)
                for x in range(board.width - 4, 3, -1)
            ]
        positions = allocate_init_positions(board, pid, init_message.piece_cnt, order)
        piece_args: List[PieceArg] = []
        for pos in positions:
            arg = PieceArg()
            arg.strength = 5
            arg.dexterity = 15
            arg.intelligence = 10
            arg.equip = Point(3, 1)
            arg.pos = pos
            piece_args.append(arg)
        return piece_args

    return strategy


def get_defensive_action_strategy() -> Callable[..., ActionSet]:
    """Return a defensive action strategy.

    The piece maintains distance from enemies (targeting ~70% of
    attack range) and uses ranged attacks. No spells are used.

    :returns: A callable action strategy.
    :rtype: Callable
    """
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current_piece = env.current_piece

        target_enemy = None
        nearest_distance = float("inf")

        for piece in env.action_queue:
            if piece.team != current_piece.team and piece.is_alive:
                distance = calculate_distance(
                    Point(current_piece.position.x, current_piece.position.y),
                    Point(piece.position.x, piece.position.y),
                )
                if distance < nearest_distance:
                    nearest_distance = distance
                    target_enemy = piece

        if target_enemy is None:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        from strategy_utils import get_legal_moves

        legal_moves = get_legal_moves(env)
        if legal_moves:
            ideal_distance = current_piece.attack_range * 0.7
            best_move = None
            min_distance_diff = float("inf")

            for move in legal_moves:
                distance_to_enemy = calculate_distance(move, target_enemy.position)
                distance_diff = abs(distance_to_enemy - ideal_distance)

                if nearest_distance < ideal_distance - 2:
                    if distance_to_enemy > nearest_distance:
                        min_distance_diff = distance_diff
                        best_move = move
                elif nearest_distance > ideal_distance + 2:
                    if distance_to_enemy < nearest_distance:
                        min_distance_diff = distance_diff
                        best_move = move
                else:
                    min_distance_diff = distance_diff
                    best_move = move

            if best_move:
                action.move = True
                action.move_target = best_move
            else:
                action.move = False
        else:
            action.move = False

        if nearest_distance <= current_piece.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current_piece
            action.attack_context.target = target_enemy
        else:
            action.attack = False

        action.spell = False
        return action

    return strategy
