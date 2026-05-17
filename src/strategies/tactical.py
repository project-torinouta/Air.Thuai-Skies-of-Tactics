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

"""Tactical strategy — spell-focused combat based on replay analysis.

Emulates the winning mage playstyle from the game replay
(``assets/8369951.json``):

- Uses staff attacks at range (weapon type 4, range 12)
- Casts Fireball AoE when enemies cluster within close range
- Focuses fire on low-health targets
- Maintains distance while kiting
"""

from typing import Callable, List, Optional

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import (
    ActionSet,
    Area,
    AttackContext,
    PieceArg,
    Point,
    Spell,
    SpellContext,
)


def get_tactical_init_strategy() -> Callable[..., List[PieceArg]]:
    """Return a tactical initialisation strategy.

    Each piece is a mage build: staff + light armour for max range
    and mobility, with 3 spell slots for Fireball AoE.

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
                for y in range(3, board.boarder)
                for x in range(3, board.width - 3)
            ]
        else:
            order = [
                (x, y)
                for y in range(board.height - 1, board.boarder, -1)
                for x in range(board.width - 4, 3, -1)
            ]
        positions = allocate_init_positions(board, pid, init_message.piece_cnt, order)
        piece_args: List[PieceArg] = []
        for pos in positions:
            arg = PieceArg()
            arg.strength = 14
            arg.dexterity = 8
            arg.intelligence = 8
            arg.equip = Point(4, 1)
            arg.pos = pos
            piece_args.append(arg)
        return piece_args

    return strategy


def get_tactical_action_strategy() -> Callable[..., ActionSet]:
    """Return a tactical action strategy.

    Priority per turn:
    1. Cast Fireball on enemy clusters (if in close range)
    2. Attack the lowest-health enemy in attack range
    3. Move to maintain optimal kiting distance

    :returns: A callable action strategy.
    :rtype: Callable
    """
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current = env.current_piece

        if current is None:
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

        enemies.sort(key=lambda p: p.health)
        primary_target = enemies[0]

        action = _decide_spell(env, current, enemies, action)
        action = _decide_attack(env, current, enemies, action)
        action = _decide_move(env, current, primary_target, action)

        if not hasattr(action, "move"):
            action.move = False
        if not hasattr(action, "attack"):
            action.attack = False
        if not hasattr(action, "spell"):
            action.spell = False

        return action

    return strategy


def _decide_spell(
    env: Environment,
    current: object,
    enemies: List,
    action: ActionSet,
) -> ActionSet:
    """Decide whether to cast a spell.

    Prefers Fireball when multiple enemies are clustered within its
    area radius.  Falls back to any available damaging spell on the
    lowest-health target.

    :param env: The game environment.
    :type env: Environment
    :param current: The current piece.
    :type current: Piece
    :param enemies: All alive enemy pieces, sorted by health ascending.
    :type enemies: List[Piece]
    :param action: The action being built.
    :type action: ActionSet
    :returns: The (possibly modified) action.
    :rtype: ActionSet
    """
    if current.spell_slots <= 0 or current.action_points <= 0:
        return action

    spells = env.get_available_spells(current)
    if not spells:
        return action

    fireball: Optional[Spell] = next(
        (s for s in spells if s.name == "Fireball"), None
    )

    if fireball and fireball.range > 0:
        in_range: List = [
            e for e in enemies
            if calculate_distance(current.position, e.position) <= fireball.range
        ]
        if in_range:
            # Pick the in-range enemy with the most friends in the blast radius
            best_target = max(
                in_range,
                key=lambda e: sum(
                    1 for other in enemies
                    if other is not e
                    and calculate_distance(other.position, e.position)
                    <= fireball.area_radius
                ),
            )
            action.spell = True
            action.spell_context = SpellContext()
            action.spell_context.caster = current
            action.spell_context.spell = fireball
            action.spell_context.target = best_target
            action.spell_context.target_area = Area(
                best_target.position.x,
                best_target.position.y,
                fireball.area_radius,
            )
            return action

    arrow_hit: Optional[Spell] = next(
        (s for s in spells if s.name == "Arrow Hit" and s.range > 0), None
    )
    if arrow_hit and arrow_hit.range > 0:
        in_range = [
            e for e in enemies
            if calculate_distance(current.position, e.position) <= arrow_hit.range
        ]
        if in_range:
            action.spell = True
            action.spell_context = SpellContext()
            action.spell_context.caster = current
            action.spell_context.spell = arrow_hit
            action.spell_context.target = in_range[0]
            location = in_range[0].position
            action.spell_context.target_area = Area(
                location.x, location.y, arrow_hit.area_radius,
            )
            return action

    return action


def _decide_attack(
    env: Environment,
    current: object,
    enemies: List,
    action: ActionSet,
) -> ActionSet:
    """Decide whether to perform a basic attack.

    Attacks the lowest-health enemy in attack range.

    :param env: The game environment.
    :type env: Environment
    :param current: The current piece.
    :type current: Piece
    :param enemies: All alive enemy pieces, sorted by health ascending.
    :type enemies: List[Piece]
    :param action: The action being built.
    :type action: ActionSet
    :returns: The (possibly modified) action.
    :rtype: ActionSet
    """
    _ = env
    if current.action_points <= 0:
        return action

    attackable = [
        e for e in enemies
        if calculate_distance(current.position, e.position) <= current.attack_range
    ]
    if attackable:
        target = min(attackable, key=lambda e: e.health)
        action.attack = True
        action.attack_context = AttackContext()
        action.attack_context.attacker = current
        action.attack_context.target = target

    return action


def _decide_move(
    env: Environment,
    current: object,
    primary_target: object,
    action: ActionSet,
) -> ActionSet:
    """Decide where to move.

    Seeks a position within attack range of the primary target while
    maintaining ~80 % of max range.

    :param env: The game environment.
    :type env: Environment
    :param current: The current piece.
    :type current: Piece
    :param primary_target: The primary target to move toward.
    :type primary_target: Piece
    :param action: The action being built.
    :type action: ActionSet
    :returns: The (possibly modified) action.
    :rtype: ActionSet
    """
    if current.action_points <= 0:
        return action

    from strategy_utils import get_legal_moves

    legal_moves = get_legal_moves(env)
    if not legal_moves:
        return action

    ideal_distance = current.attack_range * 0.8
    best_move: Optional[Point] = None
    best_score = float("inf")

    for move in legal_moves:
        d = calculate_distance(move, primary_target.position)
        score = abs(d - ideal_distance)
        if d < 3:
            score += 20
        if score < best_score:
            best_score = score
            best_move = move

    if best_move is not None:
        action.move = True
        action.move_target = best_move

    return action
