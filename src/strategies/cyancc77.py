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

"""cyancc77 — mixed-STR formation with focus-fire hold.

Replicates the strategy observed in Saiblo replays cyancc77-847268{1,2}:
- Mixed stats per piece (STR 24/25/26, INT 4 each, DEX implied).
- All pieces focus-fire the lowest-HP enemy.
- Advance until the closest enemy is at bow range, then hold.
- After the current target dies, naturally advance toward the next.
"""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


def get_cyancc77_init_strategy() -> Callable[..., List[PieceArg]]:
    """Mixed-stat init: STR 24/25/26, INT 4, bow + heavy armour."""
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
        # Mixed stats: first piece STR 25, second STR 24, third STR 26
        stat_assignments = [
            (25, 1, 4),
            (24, 2, 4),
            (26, 0, 4),
        ]
        piece_args: List[PieceArg] = []
        for i, pos in enumerate(positions):
            s, d, inte = stat_assignments[i]
            arg = PieceArg()
            arg.strength = s
            arg.dexterity = d
            arg.intelligence = inte
            arg.equip = Point(3, 3)
            arg.pos = pos
            piece_args.append(arg)
        return piece_args
    return strategy


def get_cyancc77_action_strategy() -> Callable[..., ActionSet]:
    """Focus lowest-HP, advance to bow range, then hold."""
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

        # Focus the globally lowest-HP enemy
        target = min(enemies, key=lambda p: p.health)
        dist = calculate_distance(current.position, target.position)

        # In range — attack, never move
        if dist <= current.attack_range:
            action.move = False
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
            action.spell = False
            return action

        # Out of range — advance
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

        def move_score(pos: Point) -> float:
            d = calculate_distance(pos, closest.position)
            # Prefer being exactly at bow range (9), stop once there
            if d <= current.attack_range:
                return -abs(d - float(current.attack_range))
            return -d

        best = max(legal_moves, key=move_score)
        action.move = True
        action.move_target = best

        nd = calculate_distance(best, target.position)
        if nd <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
        else:
            action.attack = False

        action.spell = False
        return action

    return strategy
