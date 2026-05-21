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

"""Sniper variants — STR 29 / DEX 1 / INT 0, different tactical approaches.

All variants use the same optimal build as the base sniper (bow + heavy armour).
Only the action strategy differs, isolating purely tactical decisions.
"""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


def get_sniper_init_strategy() -> Callable[..., List[PieceArg]]:
    """Standard sniper init — STR 29 / DEX 1 / INT 0, bow + heavy armour.

    :returns: An init strategy callable.
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


# Deathball — minimise ally spacing, fight as a concentrated clump

def get_deathball_action_strategy() -> Callable[..., ActionSet]:
    """Deathball tactics: stay tightly clustered for mutual protection.

    All pieces minimise distance to their team's centroid, advancing as a
    single unit.  This trades flanking angles for concentrated firepower and
    makes it harder for the enemy to isolate a single piece.
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

        # Target closest enemy
        target = min(
            enemies,
            key=lambda e: calculate_distance(current.position, e.position),
        )
        dist = calculate_distance(current.position, target.position)

        if dist <= current.attack_range:
            action.move = False
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
            action.spell = False
            return action

        legal_moves = get_legal_moves(env)
        if not legal_moves:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        # Team centroid (including own current position)
        if allies:
            cx = (
                current.position.x
                + sum(a.position.x for a in allies)
            ) / (len(allies) + 1)
            cy = (
                current.position.y
                + sum(a.position.y for a in allies)
            ) / (len(allies) + 1)
        else:
            cx = float(current.position.x)
            cy = float(current.position.y)

        def move_score(pos: Point) -> float:
            d_to_centroid = abs(pos.x - cx) + abs(pos.y - cy)
            d_to_enemy = calculate_distance(pos, target.position)
            return -d_to_centroid * 1.5 - d_to_enemy

        best_move = max(legal_moves, key=move_score)
        action.move = True
        action.move_target = best_move

        new_dist = calculate_distance(best_move, target.position)
        if new_dist <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
        else:
            action.attack = False

        action.spell = False
        return action

    return strategy


# High Ground — prioritise height advantage

def get_high_ground_action_strategy() -> Callable[..., ActionSet]:
    """High-ground tactics: seek and hold elevated positions.

    Height advantage grants +1 attack range and +1 damage.  This strategy
    weights moves toward the highest adjacent cells and will not leave high
    ground once secured if enemies are in range.
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

        target = min(
            enemies,
            key=lambda e: calculate_distance(current.position, e.position),
        )
        dist = calculate_distance(current.position, target.position)
        current_height = env.board.height_map[current.position.x][current.position.y]

        # On high ground with enemy in range — hold and shoot
        if dist <= current.attack_range and current_height >= 1:
            action.move = False
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
            action.spell = False
            return action

        legal_moves = get_legal_moves(env)
        if not legal_moves:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        def move_score(pos: Point) -> float:
            h = env.board.height_map[pos.x][pos.y]
            d_to_enemy = calculate_distance(pos, target.position)
            return float(h) * 5.0 - d_to_enemy

        best_move = max(legal_moves, key=move_score)
        action.move = True
        action.move_target = best_move

        new_dist = calculate_distance(best_move, target.position)
        if new_dist <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
        else:
            action.attack = False

        action.spell = False
        return action

    return strategy


# Zoner — maintain mid-range control, retreat when overextended

def get_zoner_action_strategy() -> Callable[..., ActionSet]:
    """Zoner tactics: maintain optimal bow range (3-4 tiles).

    Retreats when enemies get too close (≤ 2 tiles) and advances only enough
    to keep targets in bow range.  Avoids melee engagement.
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

        target = min(
            enemies,
            key=lambda e: calculate_distance(current.position, e.position),
        )
        dist = calculate_distance(current.position, target.position)

        # In range — attack (always take the shot)
        if dist <= current.attack_range:
            action.move = False
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
            action.spell = False
            return action

        legal_moves = get_legal_moves(env)
        if not legal_moves:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        # Prefer to stay close to own half (retreat option)
        pid = current.team
        board_height = env.board.height

        def move_score(pos: Point) -> float:
            d_to_enemy = calculate_distance(pos, target.position)
            # Reward being close to bow range
            range_penalty = abs(d_to_enemy - 4.0)
            # Reward staying near own side
            if pid == 1:
                retreat_bonus = float(board_height - 1 - pos.y)
            else:
                retreat_bonus = float(pos.y)
            return -range_penalty + retreat_bonus * 0.5

        best_move = max(legal_moves, key=move_score)
        action.move = True
        action.move_target = best_move

        new_dist = calculate_distance(best_move, target.position)
        if new_dist <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
        else:
            action.attack = False

        action.spell = False
        return action

    return strategy
