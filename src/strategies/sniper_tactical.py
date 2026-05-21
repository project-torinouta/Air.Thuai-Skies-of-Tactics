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

"""Tactical sniper — STR 29, bow + heavy armour, focus-fire kill chain.

HL analysis of 10 games showed the decisive factor is **trade speed**: when
we lose first blood but trade back within 1-2 rounds we win; when the enemy
gets a free kill we lose 100%.  This version maximises kill-chain speed:

- **Zero formation spacing** — all pieces converge on the globally lowest-HP
  enemy, same as the base sniper converges on closest, but we finish kills
  faster by picking the right target.
- **Every turn in range: reposition for height** — does not waste AP standing
  still.  Moves to the highest adjacent tile that keeps the target in range.
- **Never retreat** — every trade is favourable at STR 29.
"""

from typing import Callable, List, Optional

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


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

    Kill-chain maximisation:
    1. ALL pieces target the globally lowest-HP enemy for instant focus fire.
    2. When in range: move to the highest tile that holds the target in range,
       then attack — never waste AP standing still.
    3. When out of range: advance directly (no spacing penalty).
    4. Never retreat.
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

        # Global focus-fire target: lowest-HP enemy across the whole team
        primary_target = min(enemies, key=lambda p: p.health)

        # ---- helpers ----

        def _height(pos: Point) -> int:
            return env.board.height_map[pos.x][pos.y]

        def _best_shot_position(
            positions: List[Point], target: Point,
        ) -> Optional[Point]:
            """Among positions that keep *target* in range, pick the highest."""
            best: Optional[Point] = None
            best_h = -1
            for pos in positions:
                if calculate_distance(pos, target) <= current.attack_range:
                    h = _height(pos)
                    if h > best_h:
                        best = pos
                        best_h = h
            return best

        dist = calculate_distance(current.position, primary_target.position)

        # ================================================================
        # 1. IN RANGE — attack, reposition for height
        # ================================================================
        if dist <= current.attack_range:
            legal = get_legal_moves(env)
            better = _best_shot_position(legal, primary_target.position) if legal else None

            if better is not None:
                action.move = True
                action.move_target = better
            else:
                action.move = False

            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = primary_target
            action.spell = False
            return action

        # ================================================================
        # 2. OUT OF RANGE — advance directly
        # ================================================================
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        def move_score(pos: Point) -> float:
            d_to_enemy = calculate_distance(pos, primary_target.position)
            h_bonus = float(_height(pos)) * 2.0
            return -d_to_enemy + h_bonus

        best_move = max(legal_moves, key=move_score)
        action.move = True
        action.move_target = best_move

        new_dist = calculate_distance(best_move, primary_target.position)
        if new_dist <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = primary_target
        else:
            action.attack = False

        action.spell = False
        return action

    return strategy
