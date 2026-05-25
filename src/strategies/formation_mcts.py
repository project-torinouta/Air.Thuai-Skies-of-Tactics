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

"""Formation MCTS — direction-diverse candidate sampling.

Core insight: mcts_v2 always samples moves toward the nearest enemy,
limiting the search to different distances along a single direction.
This strategy uses **direction-bucketed candidate generation**:
  - Forward moves (toward enemy centroid)
  - Lateral moves (perpendicular to enemy centroid)
  - Backward moves (away from enemy centroid)

This gives the MCTS the option to flank, reposition, or reform rather
than always advancing — discovering better formation positioning against
tight-cluster strategies like child6.

The heuristic is the same as mcts_v2, so any difference in performance
is purely from the expanded candidate diversity.
"""

import math
from typing import Callable, List, Optional

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from strategy_utils import get_legal_moves
from utils import ActionSet, AttackContext, PieceArg, Point

_SAMPLE_MOVES: int = 12
_REACH: dict = {}
_BOARD_W: int = 0
_BOARD_H: int = 0


def _build_reach(env: Environment) -> None:
    global _REACH, _BOARD_W, _BOARD_H
    _BOARD_W, _BOARD_H = env.board.width, env.board.height
    walkable = [
        [env.board.grid[x][y].state == 1 for y in range(_BOARD_H)]
        for x in range(_BOARD_W)
    ]
    for x in range(_BOARD_W):
        for y in range(_BOARD_H):
            if not walkable[x][y]:
                continue
            cells = []
            for dx in range(-22, 23):
                for dy in range(-22, 23):
                    if abs(dx) + abs(dy) <= 22:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < _BOARD_W and 0 <= ny < _BOARD_H and walkable[nx][ny]:
                            cells.append(Point(nx, ny))
            _REACH[(x, y)] = cells


def _light_moves(state: "_SimState", pid: int) -> List[Point]:
    for p in state.pieces:
        if p[0] == pid:
            cx, cy = p[2], p[3]
            occ = {(q[2], q[3]) for q in state.pieces if q[11] and q[0] != pid}
            return [m for m in _REACH.get((cx, cy), []) if (m.x, m.y) not in occ]
    return []


class _SimState:
    """[id, team, x, y, hp, max_hp, atk_range, str, phys_dmg, phys_res, wpn, alive]"""

    def __init__(self, env: Environment) -> None:
        self.pieces: list = []
        for p in env.action_queue:
            if p.is_alive:
                self.pieces.append([
                    p.id, p.team,
                    p.position.x, p.position.y,
                    p.health, p.max_health,
                    p.attack_range, p.strength,
                    p.physical_damage, p.physical_resist,
                    p.weapon_type, 1,
                ])

    def copy(self) -> "_SimState":
        s = _SimState.__new__(_SimState)
        s.pieces = [list(r) for r in self.pieces]
        return s

    def alive(self, team: int) -> list:
        return [p for p in self.pieces if p[1] == team and p[11]]

    def enemies(self, team: int) -> list:
        return [p for p in self.pieces if p[1] != team and p[11]]

    def apply(self, action: "ActionSet", pid: int) -> None:
        for p in self.pieces:
            if p[0] == pid:
                if action.move and action.move_target:
                    p[2] = action.move_target.x
                    p[3] = action.move_target.y
                if action.attack and action.attack_context:
                    tid = action.attack_context.target.id
                    for tp in self.pieces:
                        if tp[0] == tid:
                            raw = p[7] + p[8]
                            dmg = max(0, raw - tp[9])
                            if p[10] == 4:
                                dmg = 4
                            tp[4] = max(0, tp[4] - dmg)
                            if tp[4] <= 0:
                                tp[11] = 0
                            break
                break


def _heuristic(state: _SimState, team: int) -> float:
    """mcts_v2 heuristic: HP, numerical, range gradient, focus fire, cohesion.

    Pure mcts_v2 — no extra formation terms — so the only difference from
    mcts_v2 is the candidate generation (direction-diverse sampling).
    """
    score = 0.0
    us = state.alive(team)
    them = state.enemies(team)

    score += sum(p[4] for p in us) - sum(p[4] for p in them)
    score += (len(us) - len(them)) * 50.0

    for f in us:
        mde = min(
            (abs(f[2] - e[2]) + abs(f[3] - e[3])) for e in them
        ) if them else 999.0
        if mde > f[6]:
            score -= (mde - f[6]) * 3.0
        else:
            score += (f[6] - mde) * 2.0

    for e in them:
        nearby = sum(
            1 for f in us
            if (abs(f[2] - e[2]) + abs(f[3] - e[3])) <= f[6]
        )
        if nearby >= 2:
            score += 10.0 * (nearby - 1)

    if len(us) >= 2:
        total = pairs = 0
        for i, a in enumerate(us):
            for b in us[i + 1:]:
                total += abs(a[2] - b[2]) + abs(a[3] - b[3])
                pairs += 1
        score -= total / pairs if pairs else 0.0

    return score


def get_formation_mcts_init_strategy() -> Callable[..., List[PieceArg]]:
    """Standard STR 29 / DEX 1 / INT 0 sniper init."""
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
        piece_args = []
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


def _remap_action(action: ActionSet, real_env: Environment) -> ActionSet:
    new = ActionSet()
    new.move = action.move
    new.attack = action.attack
    new.spell = action.spell
    new.move_target = action.move_target
    if action.attack and action.attack_context:
        ctx = AttackContext()
        ctx.attacker = real_env.current_piece
        ft = action.attack_context.target
        if ft is not None:
            for p in real_env.action_queue:
                if p.id == ft.id and p.team != real_env.current_piece.team:
                    ctx.target = p
                    break
        ctx.damage_dealt = action.attack_context.damage_dealt
        new.attack_context = ctx
    return new


def get_formation_mcts_action_strategy(
    simulation_count: int = 1000,
) -> Callable[..., ActionSet]:
    """Formation-aware MCTS with direction-diverse candidate sampling.

    Unlike mcts_v2 which only samples moves toward the nearest enemy, this
    strategy samples from three direction buckets relative to the enemy
    centroid: forward, lateral, and backward.  This gives the MCTS the
    option to flank, reposition, or reform rather than always advancing.

    :param simulation_count: UCB1 iterations per decision (default 1000).
    :type simulation_count: int
    :returns: A callable action strategy.
    :rtype: Callable
    """
    def strategy(env: Environment) -> ActionSet:
        if not _REACH:
            _build_reach(env)

        team = env.current_piece.team
        current = env.current_piece
        pid = current.id
        all_moves = get_legal_moves(env)
        enemies = [
            p for p in env.action_queue if p.is_alive and p.team != team
        ]

        if not all_moves:
            return ActionSet()

        # Direction-bucketed candidate generation
        if enemies and len(all_moves) > 1:
            # Compute centroids for reference direction
            us_list = [
                p for p in env.action_queue
                if p.is_alive and p.team == team
            ]
            our_cx = sum(p.position.x for p in us_list) / len(us_list)
            our_cy = sum(p.position.y for p in us_list) / len(us_list)
            their_cx = sum(p.position.x for p in enemies) / len(enemies)
            their_cy = sum(p.position.y for p in enemies) / len(enemies)
            ref_dx = their_cx - our_cx
            ref_dy = their_cy - our_cy
            ref_mag = abs(ref_dx) + abs(ref_dy)

            # Bucket by Manhattan normalised dot product
            forward: List[Point] = []
            lateral: List[Point] = []
            backward: List[Point] = []

            if ref_mag > 0.01:
                for m in all_moves:
                    dx = m.x - current.position.x
                    dy = m.y - current.position.y
                    ndot = (dx * ref_dx + dy * ref_dy) / ref_mag
                    # ndot ≈ +d for toward enemy, -d for away, 0 for lateral
                    # d is 1-3 for typical moves
                    if ndot > 0.6:
                        forward.append(m)
                    elif ndot < -0.6:
                        backward.append(m)
                    else:
                        lateral.append(m)

                nearest = min(
                    enemies,
                    key=lambda e: calculate_distance(
                        current.position, e.position,
                    ),
                )

                def to_enemy(p: Point) -> float:
                    return calculate_distance(p, nearest.position)

                forward.sort(key=to_enemy)
                lateral.sort(key=to_enemy)
                backward.sort(key=to_enemy)

                # Sample 5 forward + 4 lateral + 3 backward + stay
                sampled: List[Optional[Point]] = [None]
                seen = {(current.position.x, current.position.y)}
                for pool, wt in [(forward, 5), (lateral, 4), (backward, 3)]:
                    for m in pool:
                        if len(sampled) >= _SAMPLE_MOVES + 1:
                            break
                        k = (m.x, m.y)
                        if k not in seen:
                            seen.add(k)
                            sampled.append(m)
                        wt -= 1
                        if wt <= 0:
                            break

                sampled = sampled[:_SAMPLE_MOVES + 1]
            else:
                # Centroids coincide — all directions treated the same
                sampled = [None] + all_moves[:_SAMPLE_MOVES]
        else:
            sampled = [None] + all_moves[:_SAMPLE_MOVES]

        # Build children
        base = _SimState(env)
        children = []

        for move_pos in sampled:
            atk = None
            if enemies:
                mp = move_pos if move_pos else current.position
                for e in enemies:
                    d = abs(mp.x - e.position.x) + abs(mp.y - e.position.y)
                    if d <= current.attack_range:
                        if atk is None or e.health < atk.health:
                            atk = e

            act = ActionSet()
            if move_pos is not None:
                act.move = True
                act.move_target = move_pos
            else:
                act.move = False
            if atk is not None:
                act.attack = True
                act.attack_context = AttackContext()
                act.attack_context.attacker = current
                act.attack_context.target = atk
            else:
                act.attack = False
            act.spell = False

            st = base.copy()
            st.apply(act, pid)
            children.append((act, st, 0, 0.0))

        if not children:
            return ActionSet()

        # UCB1 loop (same mcts_v2 structure)
        for _ in range(simulation_count):
            total_v = sum(c[2] for c in children)
            best_idx = 0
            best_ucb = float("-inf")
            for i, (_, _, v, val) in enumerate(children):
                if v == 0:
                    best_idx = i
                    break
                ucb = val / v + math.sqrt(2 * math.log(total_v) / v)
                if ucb > best_ucb:
                    best_ucb = ucb
                    best_idx = i

            act, st, visits, val = children[best_idx]
            sc = _heuristic(st, team)
            children[best_idx] = (act, st, visits + 1, val + sc)

        best = max(children, key=lambda c: c[2])
        return _remap_action(best[0], env)

    return strategy
