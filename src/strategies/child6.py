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

"""Child6 — formation rally from replay ashgrey-8497768.

Replicates the strategy observed in the child6 tournament replay where
child6 (Red) beats ashgrey (Blue):

- Standard STR 29 / DEX 1 / INT 0, bow + heavy armour.
- **Anchor rally**: the friendly piece closest to the focus target is
  the formation anchor.  All other pieces prefer staying near it.
- **Weighted scoring**: each move is scored by  both advancement and
  formation closeness, without a hard cutoff.  Formation gets ~30%
  weight — pieces stay roughly together but won't sacrifice advancing.
- **Shuffle in range**: when the target can be attacked, formation
  weight increases to keep the cluster tight.
- **Focus fire**: globally lowest-HP enemy.
"""

from typing import Callable, List, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point

# Weight of formation closeness vs advancement in the scoring function.
# Higher = tighter cluster but less aggressive advance.
_FORMATION_WEIGHT = 0.3

# Weight of formation closeness when already in attack range.
# Higher = tighter shuffle within the cluster.
_SHUFFLE_WEIGHT = 1.0


def get_child6_init_strategy() -> Callable[..., List[PieceArg]]:
    """Tight-cluster placement: pieces adjacent, near the centre."""
    def strategy(init_message: InitGameMessage) -> List[PieceArg]:
        board = init_message.board
        pid = init_message.id

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
    """Weighted-scoring advance: prefer advancement + formation."""
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

        friends = [
            p for p in env.action_queue
            if p.team == current.team and p.is_alive
        ]

        # Focus-fire target: globally lowest-HP enemy.
        target = min(enemies, key=lambda p: p.health)

        # Formation anchor: the friendly piece closest to the target.
        anchor = min(
            friends,
            key=lambda f: calculate_distance(f.position, target.position),
        )

        from strategy_utils import get_legal_moves
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        def dist_to_anchor(pos: Point) -> float:
            return calculate_distance(pos, anchor.position)

        can_attack_now = (
            calculate_distance(current.position, target.position)
            <= current.attack_range
        )
        fw = _SHUFFLE_WEIGHT if can_attack_now else _FORMATION_WEIGHT

        def move_score(pos: Point) -> float:
            d_tgt = calculate_distance(pos, target.position)
            d_anc = dist_to_anchor(pos)
            return -d_tgt - d_anc * fw

        best_move = max(legal_moves, key=move_score)
        best_d = calculate_distance(best_move, target.position)
        current_d = calculate_distance(current.position, target.position)

        if best_move == current.position or best_d >= current_d:
            action.move = False
        else:
            action.move = True
            action.move_target = best_move

        new_d = calculate_distance(
            best_move if action.move else current.position,
            target.position,
        )
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
