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

"""Vanguard — sacrificial frontline + fire support.

Uses the enemy's closest-target AI against them:
- **Vanguard** (closest piece to the enemy): pushes ahead aggressively,
  drawing all 3 enemies' focus fire (they all target the closest).
- **Support** (other 2 pieces): hang back 2-3 tiles behind the vanguard,
  taking free shots while the vanguard tanks.
- All pieces focus the same lowest-HP target.
"""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


def get_vanguard_init_strategy() -> Callable[..., List[PieceArg]]:
    """Standard sniper init — STR 29 / DEX 1 / INT 0, bow + heavy armour."""
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


def get_vanguard_action_strategy() -> Callable[..., ActionSet]:
    """Return the vanguard action strategy.

    Each piece checks whether it is the closest alive ally to the enemy.
    - **Vanguard** (closest): advance aggressively, close distance.
    - **Support** (not closest): maintain gap, shoot from safety.
    All pieces focus the globally lowest-HP enemy.
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

        allies = [
            p for p in env.action_queue
            if p.team == current.team and p.id != current.id and p.is_alive
        ]

        # Global focus-fire target: lowest-HP enemy
        target = min(enemies, key=lambda p: p.health)

        # Determine role: am I the closest alive ally to the enemy team?
        my_dist_to_enemy = min(
            calculate_distance(current.position, e.position) for e in enemies
        )
        is_vanguard = True
        for ally in allies:
            ally_dist = min(
                calculate_distance(ally.position, e.position) for e in enemies
            )
            if ally_dist < my_dist_to_enemy:
                is_vanguard = False
                break

        # ================================================================
        # IN RANGE — attack the focus target (lowest-HP enemy).
        # Always prioritise the primary to concentrate fire.
        # ================================================================
        dist = calculate_distance(current.position, target.position)
        if dist <= current.attack_range:
            action.move = False
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
            action.spell = False
            return action

        # ================================================================
        # OUT OF RANGE — move
        # ================================================================
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        def move_score(pos: Point) -> float:
            d = calculate_distance(pos, target.position)

            if is_vanguard:
                # Vanguard: close distance aggressively to bait
                return -d
            else:
                # Support: stay close to vanguard but out of enemy focus
                # Find the closest ally (likely the vanguard) and stick near them
                d_to_ally = min(
                    calculate_distance(pos, a.position) for a in allies
                )
                # Prefer being 3-4 tiles behind the vanguard
                spacing = abs(d_to_ally - 3.5)
                return -d - spacing * 0.5

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
