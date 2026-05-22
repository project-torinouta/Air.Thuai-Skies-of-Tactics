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

"""Beam-search action strategy with tactical heuristic.

Uses environment forking to evaluate candidate actions, scored by a
custom heuristic that captures:
- HP advantage and numerical advantage
- Focus-fire coordination
- Range positioning (prefer bow-range edge)
"""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from strategy_utils import (
    fork_environment,
    get_attackable_targets,
    get_legal_moves,
)
from utils import ActionSet, AttackContext, PieceArg, Point


def get_search_init_strategy() -> Callable[..., List[PieceArg]]:
    """Standard sniper init — STR 29 / DEX 1 / INT 0, bow + heavy armour."""
    def strategy(init_message: InitGameMessage) -> List[PieceArg]:
        board = init_message.board
        pid = init_message.id
        if pid == 1:
            order = [
                (x, y) for y in range(5, 0, -1)
                for x in range(2, board.width - 2)
            ]
        else:
            order = [
                (x, y) for y in range(board.height - 6, board.height)
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


def _heuristic(env: Environment, team: int) -> float:
    """Score the board state from *team*'s perspective.

    Components:
    - HP difference (1 HP = 1 point)
    - Numerical advantage (alive piece = 30 points)
    - Focus fire bonus: reward when an enemy is low (finishing potential)
    - Center control: reward being near the middle of the board
    """
    score = 0.0
    n_us = 0
    n_them = 0
    our_hp = 0.0
    their_hp = 0.0
    min_enemy_hp = 999.0
    center_x = env.board.width / 2.0
    center_y = env.board.height / 2.0
    our_center_dist = 0.0

    for piece in env.action_queue:
        if not piece.is_alive:
            continue
        if piece.team == team:
            n_us += 1
            our_hp += piece.health
            our_center_dist += abs(piece.position.x - center_x) + \
                abs(piece.position.y - center_y)
        else:
            n_them += 1
            their_hp += piece.health
            if piece.health < min_enemy_hp:
                min_enemy_hp = piece.health

    score += our_hp - their_hp
    score += (n_us - n_them) * 30.0

    # Focus fire bonus: reward when an enemy is low HP (kill potential)
    if min_enemy_hp < 50:
        score += (50 - min_enemy_hp) * 0.5

    # Center control penalty (less penalty = closer to center)
    if n_us > 0:
        avg_center_dist = our_center_dist / n_us
        score -= avg_center_dist * 0.2

    return score


def _eval_action(
    env: Environment,
    move_target: Point,
    attack_target,
    team: int,
    depth: int = 1,
) -> float:
    """Score an action by forking the environment and applying effects."""
    fork = fork_environment(env)
    piece = fork.current_piece

    enemies = [
        p for p in fork.action_queue
        if p.team != team and p.is_alive
    ]

    if move_target is not None:
        piece.position = move_target
        piece.height = fork.board.height_map[move_target.x][move_target.y]

    if attack_target is not None:
        forked_tgt = None
        for p in fork.action_queue:
            if p.id == attack_target.id and p.team == attack_target.team:
                forked_tgt = p
                break
        if forked_tgt is not None and forked_tgt.is_alive:
            nd = calculate_distance(piece.position, forked_tgt.position)
            if nd <= piece.attack_range:
                raw = piece.physical_damage + piece.strength
                dmg = max(0, raw - forked_tgt.physical_resist)
                forked_tgt.health = max(0, forked_tgt.health - dmg)

    # Depth >= 2: simulate opponent's most likely response
    if depth >= 2:
        opp = fork.current_piece
        if opp and opp.is_alive and opp.team != team:
            opp_enemies = [
                p for p in fork.action_queue
                if p.team == team and p.is_alive
            ]
            if opp_enemies:
                opp_tgt = min(
                    opp_enemies,
                    key=lambda e: calculate_distance(opp.position, e.position),
                )
                opp_moves = get_legal_moves(fork, opp)
                if opp_moves:
                    best_opp = min(
                        opp_moves,
                        key=lambda m: calculate_distance(m, opp_tgt.position),
                    )
                    opp.position = best_opp
                    nd = calculate_distance(best_opp, opp_tgt.position)
                    if nd <= opp.attack_range:
                        raw = opp.physical_damage + opp.strength
                        dmg = max(0, raw - opp_tgt.physical_resist)
                        opp_tgt.health = max(0, opp_tgt.health - dmg)

    base = _heuristic(fork, team)

    # Position quality
    penalty = 0.0

    if enemies:
        new_dist = min(
            calculate_distance(piece.position, e.position) for e in enemies
        )
        penalty += abs(new_dist - float(piece.attack_range)) * 0.3

    # Heavily penalise corners and edges (dead-end positions)
    cx, cy = piece.position.x, piece.position.y
    bw, bh = fork.board.width, fork.board.height
    edge_penalty = 0.0
    if cx <= 1 or cx >= bw - 2:
        edge_penalty += 5.0
    if cy <= 1 or cy >= bh - 2:
        edge_penalty += 5.0
    penalty += edge_penalty

    return base - penalty


# Maximum Manhattan distance from current position for move candidates.
# Reduces candidates from ~400 to ~50, focusing on nearby tactical moves.
_MAX_MOVE_DIST = 5.0


def _nearby_moves(legal_moves, current_pos, max_dist=_MAX_MOVE_DIST):
    """Filter legal moves to only those within *max_dist* of *current_pos*."""
    return [
        p for p in legal_moves
        if calculate_distance(p, current_pos) <= max_dist
    ]


def get_search_action_strategy(
    depth: int = 2,
) -> Callable[..., ActionSet]:
    """Return a beam-search action strategy.

    :param depth: Look-ahead depth (1 or 2).  Defaults to 1.
    :type depth: int
    :returns: An action strategy callable.
    :rtype: Callable
    """
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current = env.current_piece

        if current is None or not current.is_alive:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        team = current.team
        all_legal_moves = get_legal_moves(env)
        legal_moves = _nearby_moves(all_legal_moves, current.position)
        attackable = get_attackable_targets(env)
        action.move = False
        action.attack = False
        action.spell = False

        candidates: List[tuple] = []

        for pos in legal_moves:
            sc = _eval_action(env, pos, None, team, depth)
            candidates.append((pos, None, sc))
            for atk in attackable:
                nd = calculate_distance(pos, atk.position)
                if nd <= current.attack_range:
                    sc = _eval_action(env, pos, atk, team, depth)
                    candidates.append((pos, atk, sc))

        for atk in attackable:
            d = calculate_distance(current.position, atk.position)
            if d <= current.attack_range:
                sc = _eval_action(env, None, atk, team, depth)
                candidates.append((None, atk, sc))

        if not candidates:
            return action

        best_move, best_atk, best_sc = max(candidates, key=lambda c: c[2])

        if best_move is not None:
            action.move = True
            action.move_target = best_move
        else:
            action.move = False

        if best_atk is not None:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = best_atk
        else:
            action.attack = False

        return action

    return strategy
