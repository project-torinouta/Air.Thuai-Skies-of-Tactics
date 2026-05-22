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

"""Parameterised strategy factory — generate variants by tweaking knobs.

Used by ``--sweep-action`` to explore the tactical parameter space.
"""

from typing import Callable, List, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point

# Type alias matching benchmark.StrategyPair
StrategyPair = Tuple[Callable[..., List[PieceArg]], Callable[..., ActionSet]]


def _default_init_strategy(strength=29, dexterity=1, intelligence=0,
                           weapon=3, armor=3) -> Callable[..., List[PieceArg]]:
    """Standard sniper init with given attributes/equipment."""
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
            arg.strength = strength
            arg.dexterity = dexterity
            arg.intelligence = intelligence
            arg.equip = Point(weapon, armor)
            arg.pos = pos
            piece_args.append(arg)
        return piece_args
    return strategy


def make_strategy(
    target_mode: str = "closest",
    formation_spacing: float = 0.0,
    advance_mode: str = "always",
    retreat_hp: int = 0,
) -> StrategyPair:
    """Create a strategy pair by setting tactical knobs.

    :param target_mode: ``"closest"``, ``"lowest_hp"``, or ``"highest_hp"``.
    :type target_mode: str
    :param formation_spacing: Minimum distance from allies (0 = none).
    :type formation_spacing: float
    :param advance_mode: ``"always"`` (keep pushing) or ``"edge"`` (stop
        once the closest enemy is at bow range).
    :type advance_mode: str
    :param retreat_hp: Retreat when own HP is below this (0 = never).
    :type retreat_hp: int
    :returns: An (init_fn, action_fn) pair.
    :rtype: StrategyPair
    """
    init = _default_init_strategy()

    def action_strategy(env: Environment) -> ActionSet:
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

        # --- Target selection ---
        if target_mode == "closest":
            target = min(
                enemies,
                key=lambda e: calculate_distance(current.position, e.position),
            )
        elif target_mode == "highest_hp":
            target = max(enemies, key=lambda p: p.health)
        else:  # lowest_hp
            target = min(enemies, key=lambda p: p.health)

        dist = calculate_distance(current.position, target.position)
        closest_enemy = min(
            enemies,
            key=lambda e: calculate_distance(current.position, e.position),
        )

        # --- Retreat check ---
        if retreat_hp > 0 and current.health < retreat_hp:
            legal = get_legal_moves(env)
            if legal:
                best = max(
                    legal,
                    key=lambda p: calculate_distance(p, closest_enemy.position),
                )
                action.move = True
                action.move_target = best
            action.attack = False
            action.spell = False
            return action

        # ---- IN RANGE — attack ----
        if dist <= current.attack_range:
            action.move = False
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
            action.spell = False
            return action

        # ---- OUT OF RANGE — advance ----
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        def move_score(pos: Point) -> float:
            d = calculate_distance(pos, closest_enemy.position)

            # Formation spacing
            spacing_penalty = 0.0
            if formation_spacing > 0:
                for ally in allies:
                    ad = calculate_distance(pos, ally.position)
                    if ad < formation_spacing:
                        spacing_penalty += (formation_spacing - ad) * 2.0

            # Advance mode
            if advance_mode == "edge":
                if d <= current.attack_range:
                    range_score = -abs(d - float(current.attack_range))
                else:
                    range_score = -d
            else:
                range_score = -d

            return range_score - spacing_penalty

        best_move = max(legal_moves, key=move_score)
        action.move = True
        action.move_target = best_move

        nd = calculate_distance(best_move, target.position)
        if nd <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
        else:
            action.attack = False

        action.spell = False
        return action

    return (init, action_strategy)
