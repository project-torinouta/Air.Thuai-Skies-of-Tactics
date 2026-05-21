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

Game state changes behaviour:
- **Outnumbered** (2v3, 1v3): defensive kiting.  Stay at max bow range,
  avoid extending, try to focus one target to even the odds.
- **Advantage** (3v2, 3v1): aggressive push.  Close distance, finish
  wounded enemies, never let them regroup.
- **Even** (3v3, 2v2, 1v1): standard advance-and-attack with focus fire.
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

    Adapts behaviour based on the current piece count:
    - **Outnumbered**: maintain distance, stay at max bow range, don't
      overextend, focus fire on one target.
    - **Advantage**: push forward aggressively, chase down wounded foes.
    - **Even**: standard advance and attack.
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

        # --- Game state ---
        n_enemies = len(enemies)
        n_allies = len(allies) + 1  # +1 for self
        outnumbered = n_enemies > n_allies
        advantage = n_allies > n_enemies

        # Globally lowest-HP enemy for focus fire
        primary = min(enemies, key=lambda p: p.health)
        # Closest enemy for positioning
        closest = min(
            enemies,
            key=lambda e: calculate_distance(current.position, e.position),
        )

        dist = calculate_distance(current.position, primary.position)

        # ================================================================
        # IN RANGE — attack (always, no wasted AP)
        # ================================================================
        if dist <= current.attack_range:
            # Outnumbered: reposition to maintain distance after shooting
            if outnumbered:
                legal = get_legal_moves(env)
                if legal:
                    # Find a position that keeps target in range but
                    # maximises distance from the closest enemy
                    def retreat_score(pos: Point) -> float:
                        new_d = calculate_distance(pos, primary.position)
                        if new_d > current.attack_range:
                            return -999.0
                        return calculate_distance(pos, closest.position)
                    best = max(legal, key=retreat_score)
                    action.move = True
                    action.move_target = best
                else:
                    action.move = False
            else:
                action.move = False

            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = primary
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

        def advance_score(pos: Point) -> float:
            d = calculate_distance(pos, primary.position)
            if advantage:
                # Aggressive: minimise distance
                return -d
            elif outnumbered:
                # Defensive: prefer positions close to own side
                pid = current.team
                if pid == 1:
                    retreat = float(pos.y)
                else:
                    retreat = float(env.board.height - 1 - pos.y)
                return -d * 0.8 + retreat * 0.2
            else:
                # Even: standard advance
                return -d

        best_move = max(legal_moves, key=advance_score)
        action.move = True
        action.move_target = best_move

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
