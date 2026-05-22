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

"""Baiter — sacrificial DEX piece + two STR 29 damage dealers.

Mixed stats across the team:
- **Baiter** (piece 0): STR 0 / DEX 29 / INT 1, bow + heavy.
  Goes first every round (d10+29).  Rushes ahead to bait the enemy's
  closest-target AI.  All 3 enemies focus the baiter.
- **Support** (pieces 1,2): STR 29 / DEX 1 / INT 0, bow + heavy.
  Standard optimal build.  Hang back and shoot while the baiter tanks.
"""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


def get_baiter_init_strategy() -> Callable[..., List[PieceArg]]:
    """Mixed-stats init: 1 baiter + 2 standard snipers."""
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
        stats = [
            (15, 14, 1),  # baiter: STR 15, DEX 14, HP 80, movement 28.5
            (29, 1, 0),   # support: standard sniper
            (29, 1, 0),   # support: standard sniper
        ]
        piece_args: List[PieceArg] = []
        for i, pos in enumerate(positions):
            s, d, inte = stats[i]
            arg = PieceArg()
            arg.strength = s
            arg.dexterity = d
            arg.intelligence = inte
            arg.equip = Point(3, 3)
            arg.pos = pos
            piece_args.append(arg)
        return piece_args
    return strategy


def get_baiter_action_strategy() -> Callable[..., ActionSet]:
    """Baiter pushes ahead; supports hang back and focus-fire.

    - If the acting piece is the baiter (DEX == 29): advance directly
      toward the closest enemy to stay ahead of supports.
    - If the acting piece is a support (DEX == 1): target the globally
      lowest-HP enemy, stay 4-5 tiles behind the baiter.
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

        is_baiter = (current.dexterity == 29)
        target = min(enemies, key=lambda p: p.health)

        # In range — attack
        dist = calculate_distance(current.position, target.position)
        if dist <= current.attack_range:
            action.move = False
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
            action.spell = False
            return action

        # Out of range — move
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        closest = min(
            enemies,
            key=lambda e: calculate_distance(current.position, e.position),
        )

        if is_baiter:
            # Baiter: rush toward the closest enemy, stay ahead
            action.move = True
            action.move_target = min(
                legal_moves,
                key=lambda m: calculate_distance(m, closest.position),
            )
            # Advance-and-attack if in range after moving
            new_d = calculate_distance(
                action.move_target, target.position,
            )
            if new_d <= current.attack_range:
                action.attack = True
                action.attack_context = AttackContext()
                action.attack_context.attacker = current
                action.attack_context.target = target
            else:
                action.attack = False
        else:
            # Support: advance but maintain gap from baiter
            allies = [
                p for p in env.action_queue
                if p.team == current.team and p.id != current.id and p.is_alive
            ]
            baiter_pieces = [a for a in allies if a.dexterity == 29]

            def support_score(pos: Point) -> float:
                d = calculate_distance(pos, closest.position)
                gap = 0.0
                if baiter_pieces:
                    gap = min(
                        calculate_distance(pos, b.position) for b in baiter_pieces
                    )
                # Prefer being 4-5 tiles behind the baiter
                gap_penalty = abs(gap - 4.5) * 1.5
                return -d - gap_penalty

            best = max(legal_moves, key=support_score)
            action.move = True
            action.move_target = best

            new_d = calculate_distance(best, target.position)
            if new_d <= current.attack_range:
                action.attack = True
                action.attack_context = AttackContext()
                action.attack_context.attacker = current
                action.attack_context.target = target
            else:
                action.attack = False

        action.spell = False
        return action

    return strategy
