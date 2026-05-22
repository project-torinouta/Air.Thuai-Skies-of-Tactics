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
# HELDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Dynamic sniper — STR 29 / DEX 1 / INT 0, behaviour adapts to the battle.

Three modes switched by piece count:
- **Outnumbered** (2v3, 1v3): flee.  Do not advance toward enemies.  Only
  shoot if already in range — never chase.  Move away from the enemy team.
- **Advantage** (3v2, 3v1): chase.  Close distance, finish wounded enemies.
- **Even** (3v3, 2v2, 1v1): standard advance with focus fire.
"""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


def get_dynamic_init_strategy() -> Callable[..., List[PieceArg]]:
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


def get_dynamic_action_strategy() -> Callable[..., ActionSet]:
    """Return the dynamic action strategy.

    Behaviour switches on piece count:
    - **Outnumbered**: desperation focus fire.  ALL pieces target the globally
      lowest-HP enemy.  No retreat — need to even the odds by trading a kill.
    - **Advantage**: chase.  Close distance, finish wounded enemies.
    - **Even**: standard advance with focus fire on lowest-HP target.
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

        n_enemies = len(enemies)
        n_allies = len(allies) + 1
        outnumbered = n_enemies > n_allies
        advantage = n_allies > n_enemies

        # Even & outnumbered: focus lowest-HP enemy to force a kill.
        # Advantage: target closest to confirm the kill quickly.
        if advantage:
            target = min(
                enemies,
                key=lambda e: calculate_distance(current.position, e.position),
            )
        else:
            target = min(enemies, key=lambda p: p.health)

        dist = calculate_distance(current.position, target.position)

        # ================================================================
        # IN RANGE — attack, never waste AP on movement
        # ================================================================
        if dist <= current.attack_range:
            action.move = False
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
            action.spell = False
            return action

        # ================================================================
        # OUT OF RANGE
        # ================================================================
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        def move_score(pos: Point) -> float:
            d = calculate_distance(pos, target.position)
            h = float(env.board.height_map[pos.x][pos.y])

            if advantage:
                # Chase: close distance for the kill, prefer high ground
                return -d + h
            else:
                # Even & outnumbered: advance and focus fire
                return -d + h

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
