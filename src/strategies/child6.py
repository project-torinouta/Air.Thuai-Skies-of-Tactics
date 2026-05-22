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

"""Child6 — tight group advance from replay ashgrey-8497768.

Replicates the strategy observed in the child6 tournament replay where
child6 (Red) beats ashgrey (Blue):

- Standard STR 29 / DEX 1 / INT 0, bow + heavy armour.
- **Maintain tight formation**: each piece moves to stay near its
  teammates, advancing as a group rather than independently.
- **Attack the globally lowest-HP enemy** (focus fire).
- Once a piece is in bow range, it stops moving and attacks every turn.
- The formation arrives at the fight together, enabling 3v2 / 3v1
  focus-fire against isolated targets.
"""

from typing import Callable, List, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


def get_child6_init_strategy() -> Callable[..., List[PieceArg]]:
    """Tight-cluster placement: pieces adjacent, near the centre."""
    def strategy(init_message: InitGameMessage) -> List[PieceArg]:
        board = init_message.board
        pid = init_message.id

        # Try to place pieces in a tight cluster near the centre of the
        # player's half.  First tries adjacency around (cx, cy), then
        # falls back to a full row scan.
        cx = board.width // 2
        cy = 3 if pid == 1 else board.height - 4

        order: List[Tuple[int, int]] = [
            (cx, cy),
            (cx + 1, cy),
            (cx - 1, cy),
            (cx, cy + 1),
            (cx, cy - 1),
            (cx + 2, cy),
            (cx - 2, cy),
        ]

        if pid == 1:
            order += [
                (x, y)
                for y in range(5, 0, -1)
                for x in range(2, board.width - 2)
            ]
        else:
            order += [
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


def get_child6_action_strategy() -> Callable[..., ActionSet]:
    """Formation-keeping advance: stay near teammates, attack lowest-HP."""
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

        # Focus-fire target: globally lowest-HP enemy
        target = min(enemies, key=lambda p: p.health)
        dist = calculate_distance(current.position, target.position)

        if dist <= current.attack_range:
            # In range — attack, never waste AP on movement
            action.move = False
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
            action.spell = False
            return action

        # Out of range — advance toward the primary target.  Among moves
        # that are equally good for advancing, prefer staying close to
        # teammates (formation tiebreaker).
        from strategy_utils import get_legal_moves

        allies = [
            p for p in env.action_queue
            if p.team == current.team and p.id != current.id and p.is_alive
        ]

        legal_moves = get_legal_moves(env)
        if not legal_moves:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        # Primary criterion: minimise distance to target
        best_d = min(
            calculate_distance(m, target.position) for m in legal_moves
        )
        best_moves = [
            m for m in legal_moves
            if calculate_distance(m, target.position) == best_d
        ]

        if allies and len(best_moves) > 1:
            # Tiebreak: among the best advancing moves, pick the one
            # closest to the average position of alive teammates
            avg_ax = sum(a.position.x for a in allies) / len(allies)
            avg_ay = sum(a.position.y for a in allies) / len(allies)
            centre = Point(int(round(avg_ax)), int(round(avg_ay)))
            best_move = min(
                best_moves,
                key=lambda m: calculate_distance(m, centre),
            )
        else:
            best_move = best_moves[0]

        action.move = True
        action.move_target = best_move

        # Advance-and-attack: if the move brings the focus target into
        # bow range, attack in the same turn
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
