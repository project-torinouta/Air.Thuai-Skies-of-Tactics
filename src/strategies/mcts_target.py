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

"""MCTS-Target — attack-centred candidate generation + kill-pressure heuristic.

Key improvements over mcts_v2 / formation_mcts:

  1. **Attack-centred candidates** — instead of sampling moves by proximity
     to the nearest enemy, we sample moves by target enemy.  For each enemy
     we generate 1-2 move positions that are optimal for attacking IT.
     This lets UCB1 choose WHICH enemy to focus, not just WHERE to stand.

  2. **Kill-pressure heuristic** — adds a term that estimates how many
     turns it takes to kill each enemy vs how many turns for them to kill
     us.  This directly models the damage race rather than just comparing
     total HP.

The core flat-tree MCTS structure is unchanged.
"""

import math
from typing import Callable, List, Optional, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from strategy_utils import get_attackable_targets, get_legal_moves
from utils import ActionSet, AttackContext, PieceArg, Point

_SAMPLE_MOVES: int = 10
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


# ---------------------------------------------------------------------------
# Heuristic with kill pressure
# ---------------------------------------------------------------------------

def _heuristic(state: _SimState, team: int) -> float:
    """mcts_v2 heuristic + kill-pressure term.

    Kill pressure estimates the damage race: how many actions does it take
    for us to kill each enemy, vs for them to kill each of us.
    """
    score = 0.0
    us = state.alive(team)
    them = state.enemies(team)

    if not us:
        return float("-inf")
    if not them:
        return float("inf")

    # --- HP and numerical advantage (same as mcts_v2) ---
    our_hp = sum(p[4] for p in us)
    their_hp = sum(p[4] for p in them)
    score += our_hp - their_hp
    score += (len(us) - len(them)) * 50.0

    # --- Range gradient (same as mcts_v2) ---
    for f in us:
        mde = min(
            (abs(f[2] - e[2]) + abs(f[3] - e[3])) for e in them
        ) if them else 999.0
        if mde > f[6]:
            score -= (mde - f[6]) * 3.0
        else:
            score += (f[6] - mde) * 2.0

    # --- Focus fire bonus (same as mcts_v2) ---
    for e in them:
        nearby = sum(
            1 for f in us
            if (abs(f[2] - e[2]) + abs(f[3] - e[3])) <= f[6]
        )
        if nearby >= 2:
            score += 10.0 * (nearby - 1)

    # --- Formation penalty (same as mcts_v2) ---
    if len(us) >= 2:
        total = pairs = 0
        for i, a in enumerate(us):
            for b in us[i + 1:]:
                total += abs(a[2] - b[2]) + abs(a[3] - b[3])
                pairs += 1
        score -= total / pairs if pairs else 0.0

    # --- Kill pressure: damage race estimate ---
    # How many of OUR actions to kill each enemy (lower = better for us)
    our_actions_to_kill = 0.0
    for e in them:
        if e[10] == 4:  # staff — always 4 true damage
            dmg_per_hit = 4.0
        else:
            dmg_per_hit = max(1.0, float(e[7] + e[8]))  # str + phys_dmg
        # Account for our armour
        for f in us:
            raw = dmg_per_hit
            actual = max(0.0, raw - e[9])  # Wait, this is wrong. This should be:
            # We're estimating: how many of OUR hits to kill THEM
            break
        # Actually: our_damage_to_them = our_str + our_phys_dmg - their_phys_res
        our_dmg_to_e = 0.0
        for f in us:
            piece_dmg = f[7] + f[8] - e[9]  # str + phys_dmg - target's phys_res
            if piece_dmg <= 0:
                piece_dmg = 1.0  # minimum 1 damage
            if piece_dmg > our_dmg_to_e:
                our_dmg_to_e = piece_dmg
        # If staff, use 4
        for f in us:
            if f[10] == 4:
                our_dmg_to_e = 4.0
                break

        if our_dmg_to_e > 0:
            hits = e[4] / our_dmg_to_e
            # How many of us are in range of this enemy?
            our_in_range = sum(
                1 for f in us
                if abs(f[2] - e[2]) + abs(f[3] - e[3]) <= f[6]
            )
            if our_in_range >= 2:
                hits /= our_in_range  # multiple attackers speed up the kill
            our_actions_to_kill += hits

    # How many of THEIR actions to kill each of us (lower = better for them)
    their_actions_to_kill = 0.0
    for f in us:
        their_dmg_to_p = 0.0
        for e in them:
            piece_dmg = e[7] + e[8] - f[9]
            if piece_dmg <= 0:
                piece_dmg = 1.0
            if e[10] == 4:
                piece_dmg = 4.0
            if piece_dmg > their_dmg_to_p:
                their_dmg_to_p = piece_dmg

        if their_dmg_to_p > 0:
            hits = f[4] / their_dmg_to_p
            # How many enemies in range of this piece?
            enemies_in_range = sum(
                1 for e in them
                if abs(f[2] - e[2]) + abs(f[3] - e[3]) <= e[6]
            )
            if enemies_in_range >= 2:
                hits /= enemies_in_range
            their_actions_to_kill += hits

    # Kill advantage: positive = we kill them faster than they kill us
    kill_advantage = their_actions_to_kill - our_actions_to_kill
    score += kill_advantage * 8.0

    return score


# ---------------------------------------------------------------------------
# Attack-centred candidate generation
# ---------------------------------------------------------------------------

def _build_candidates(env: Environment) -> "List[Tuple[ActionSet, _SimState]]":
    """Generate candidates organised by target enemy.

    For each enemy piece E, find 1-2 move positions from which the current
    piece can attack E.  If no position can reach E, include an advance
    move toward E.  Also adds formation-hold + stay-put options.

    This lets UCB1 choose WHICH enemy to focus fire, not just where to move.
    """
    current = env.current_piece
    team = current.team
    pid = current.id
    all_moves = get_legal_moves(env)
    enemies = [p for p in env.action_queue if p.is_alive and p.team != team]
    base = _SimState(env)

    candidates = []
    seen_dest = set()

    def add(act: ActionSet) -> None:
        st = base.copy()
        st.apply(act, pid)
        candidates.append((act, st, 0, 0.0))

    # -- 1. Per-target options --
    for e in enemies:
        ex, ey = e.position.x, e.position.y
        # Moves that put us in range to attack THIS enemy
        attack_moves = []
        for m in all_moves:
            d = abs(m.x - ex) + abs(m.y - ey)
            if d <= current.attack_range:
                attack_moves.append((m, d))

        if attack_moves:
            # Closest 2 positions for attacking this enemy
            attack_moves.sort(key=lambda x: x[1])
            for m, _ in attack_moves[:2]:
                k = (m.x, m.y)
                if k in seen_dest:
                    continue
                seen_dest.add(k)
                act = ActionSet()
                act.move = True
                act.move_target = m
                act.attack = True
                act.attack_context = AttackContext()
                act.attack_context.attacker = current
                act.attack_context.target = e
                act.spell = False
                add(act)
        else:
            # Not in range — advance toward this enemy
            best = min(all_moves, key=lambda m: abs(m.x - ex) + abs(m.y - ey))
            k = (best.x, best.y)
            if k not in seen_dest:
                seen_dest.add(k)
                act = ActionSet()
                act.move = True
                act.move_target = best
                act.attack = False
                act.spell = False
                add(act)

    if not enemies:
        # -- 2. If no enemies: just hold --
        act = ActionSet()
        act.move = False
        act.attack = False
        act.spell = False
        add(act)
        return candidates

    # -- 3. Stay-put + optional attack --
    stay_attack = None
    for e in enemies:
        d = abs(current.position.x - e.position.x) + abs(current.position.y - e.position.y)
        if d <= current.attack_range:
            if stay_attack is None or e.health < stay_attack.health:
                stay_attack = e
    if stay_attack is not None:
        act = ActionSet()
        act.move = False
        act.attack = True
        act.attack_context = AttackContext()
        act.attack_context.attacker = current
        act.attack_context.target = stay_attack
        act.spell = False
        add(act)
    act = ActionSet()
    act.move = False
    act.attack = False
    act.spell = False
    add(act)

    # -- 4. Fill remaining slots with closest-to-enemy moves (any target) --
    if len(candidates) < _SAMPLE_MOVES + 2 and all_moves:
        nearest = min(
            enemies,
            key=lambda e: calculate_distance(current.position, e.position),
        )
        all_moves.sort(key=lambda m: calculate_distance(m, nearest.position))
        for m in all_moves:
            if len(candidates) >= _SAMPLE_MOVES + 3:
                break
            k = (m.x, m.y)
            if k in seen_dest:
                continue
            seen_dest.add(k)
            # Best attack from this position
            atk = None
            for e in enemies:
                d = abs(m.x - e.position.x) + abs(m.y - e.position.y)
                if d <= current.attack_range:
                    if atk is None or e.health < atk.health:
                        atk = e
            act = ActionSet()
            act.move = True
            act.move_target = m
            act.move = True
            act.attack = atk is not None
            if atk is not None:
                act.attack_context = AttackContext()
                act.attack_context.attacker = current
                act.attack_context.target = atk
            act.spell = False
            add(act)

    return candidates


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def get_mcts_target_init_strategy() -> Callable[..., List[PieceArg]]:
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


# ---------------------------------------------------------------------------
# Remap
# ---------------------------------------------------------------------------

def _remap_action(action: ActionSet, real_env: Environment) -> ActionSet:
    new = ActionSet()
    new.move = getattr(action, 'move', False)
    new.attack = getattr(action, 'attack', False)
    new.spell = getattr(action, 'spell', False)
    new.move_target = getattr(action, 'move_target', None)
    if getattr(action, 'attack', False) and getattr(action, 'attack_context', None):
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


# ---------------------------------------------------------------------------
# Main strategy
# ---------------------------------------------------------------------------

def get_mcts_target_action_strategy(
    simulation_count: int = 1000,
) -> Callable[..., ActionSet]:
    """MCTS with target-centred candidates and kill-pressure heuristic.

    :param simulation_count: UCB1 iterations per decision (default 1000).
    :type simulation_count: int
    :returns: A callable action strategy.
    :rtype: Callable
    """
    def strategy(env: Environment) -> ActionSet:
        if not _REACH:
            _build_reach(env)

        team = env.current_piece.team

        candidates = _build_candidates(env)
        if not candidates:
            return ActionSet()

        # UCB1 loop
        for _ in range(simulation_count):
            total_v = sum(c[2] for c in candidates)
            best_idx = 0
            best_ucb = float("-inf")
            for i, (_, _, v, val) in enumerate(candidates):
                if v == 0:
                    best_idx = i
                    break
                ucb = val / v + math.sqrt(2 * math.log(total_v) / v)
                if ucb > best_ucb:
                    best_ucb = ucb
                    best_idx = i

            act, st, visits, val = candidates[best_idx]
            sc = _heuristic(st, team)
            candidates[best_idx] = (act, st, visits + 1, val + sc)

        best = max(candidates, key=lambda c: c[2])
        return _remap_action(best[0], env)

    return strategy
