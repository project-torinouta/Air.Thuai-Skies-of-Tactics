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

"""Warrior strategy — high-strength burst from game-replay analysis.

Based on the dominant warrior playstyle observed across all 6 game replays
(``assets/8367*.json``):

- High strength (STR 24) for 3 action points per turn
- Sword + light armour for balanced mobility and damage
- Focus-fire the lowest-health enemy
- Burst combo per turn: move + attack (34 damage) + Arrow Hit (30 damage)

``_RangedVariant`` uses a bow instead of a shortsword to counter the
tactical mage kiting strategy at range.
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


def get_warrior_init_strategy() -> Callable[..., List[PieceArg]]:
    """Return a warrior initialisation strategy.

    Each piece is a high-strength melee build: shortsword + light armour
    for 3 action points per turn and balanced mobility.

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
            arg.strength = 24
            arg.dexterity = 6
            arg.intelligence = 0
            arg.equip = Point(2, 1)
            arg.pos = pos
            piece_args.append(arg)
        return piece_args

    return strategy


def get_warrior_action_strategy() -> Callable[..., ActionSet]:
    """Return a warrior action strategy (shortsword melee).

    Priority per turn:
    1. Cast Arrow Hit on an adjacent enemy (30 damage)
    2. Attack the lowest-health enemy in weapon range (34 damage)
    3. Move toward the nearest enemy

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
        primary = enemies[0]

        action = _arrow_hit(env, current, enemies, action)
        action = _melee_attack(env, current, enemies, action)
        action = _advance(env, current, primary, action)

        for attr in ("move", "attack", "spell"):
            if not hasattr(action, attr):
                setattr(action, attr, False)

        return action

    return strategy


def get_ranger_init_strategy() -> Callable[..., List[PieceArg]]:
    """Return a ranger (bow) initialisation strategy.

    High-strength archer build with a bow to out-trade the tactical
    mage at range (bow range 9, staff range 12, but bow damage is 8x).

    :returns: A callable init strategy.
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
            arg.strength = 22
            arg.dexterity = 8
            arg.intelligence = 0
            arg.equip = Point(3, 1)
            arg.pos = pos
            piece_args.append(arg)
        return piece_args

    return strategy


def get_ranger_action_strategy() -> Callable[..., ActionSet]:
    """Return a ranger (bow) action strategy.

    Uses the bow's range 9 to out-damage the tactical mage:
    - Bow attack: 38 damage per hit (vs staff 4)
    - Closes the 3-tile range gap with superior movement

    Priority: arrow hit (adjacent) → bow attack → move toward target.

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
        primary = enemies[0]

        action = _arrow_hit(env, current, enemies, action)
        action = _melee_attack(env, current, enemies, action)
        action = _advance(env, current, primary, action)

        for attr in ("move", "attack", "spell"):
            if not hasattr(action, attr):
                setattr(action, attr, False)

        return action

    return strategy


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _arrow_hit(
    env: Environment,
    current: object,
    enemies: List,
    action: ActionSet,
) -> ActionSet:
    """Cast Arrow Hit on the lowest-health adjacent enemy.

    :param env: The game environment.
    :type env: Environment
    :param current: The current piece.
    :type current: Piece
    :param enemies: Alive enemies sorted by health ascending.
    :type enemies: List[Piece]
    :param action: The action being built.
    :type action: ActionSet
    :returns: The (possibly modified) action.
    :rtype: ActionSet
    """
    if current.spell_slots <= 0 or current.action_points <= 0:
        return action

    spells = env.get_available_spells(current)
    arrow_hit: Optional[Spell] = next(
        (s for s in spells if s.name == "Arrow Hit"), None
    )
    if arrow_hit is None:
        return action

    adjacent = [
        e for e in enemies
        if calculate_distance(current.position, e.position) <= arrow_hit.range
    ]
    if not adjacent:
        return action

    target = min(adjacent, key=lambda e: e.health)
    action.spell = True
    action.spell_context = SpellContext()
    action.spell_context.caster = current
    action.spell_context.spell = arrow_hit
    action.spell_context.target = target
    action.spell_context.target_area = Area(
        target.position.x, target.position.y, arrow_hit.area_radius,
    )
    return action


def _melee_attack(
    env: Environment,
    current: object,
    enemies: List,
    action: ActionSet,
) -> ActionSet:
    """Attack the lowest-health enemy in weapon range.

    :param env: The game environment.
    :type env: Environment
    :param current: The current piece.
    :type current: Piece
    :param enemies: Alive enemies sorted by health ascending.
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
    if not attackable:
        return action

    target = min(attackable, key=lambda e: e.health)
    action.attack = True
    action.attack_context = AttackContext()
    action.attack_context.attacker = current
    action.attack_context.target = target
    return action


def _advance(
    env: Environment,
    current: object,
    primary: object,
    action: ActionSet,
) -> ActionSet:
    """Move toward the primary target.

    :param env: The game environment.
    :type env: Environment
    :param current: The current piece.
    :type current: Piece
    :param primary: The primary target to advance on.
    :type primary: Piece
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

    best_move: Optional[Point] = None
    best_dist = float("inf")
    for move in legal_moves:
        d = calculate_distance(move, primary.position)
        if d < best_dist:
            best_dist = d
            best_move = move

    if best_move is not None:
        action.move = True
        action.move_target = best_move

    return action
