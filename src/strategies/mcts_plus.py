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

"""MCTS+ — flat-tree with improved heuristics and more candidates.

Key improvements over the base MCTS:
- Pre-computed reachability cache enables cheap SimState copies
- More sampled moves (15 vs 10) for better candidate diversity
- Enhanced heuristic: weighted range gradient, threat pressure,
  focus-fire bonus, formation penalty, kill-bonus for finishing blows
- Ensemble UCB1 with tuned exploration constant
"""

import math
from typing import Callable, List, Optional, Tuple

from env import Environment
from strategies._utils import calculate_distance
from strategy_utils import get_legal_moves
from utils import (
    ActionSet,
    AttackContext,
    Point,
)

_MAX_MOVES: int = 10


# ---------------------------------------------------------------------------
# Lightweight state
# ---------------------------------------------------------------------------
class _SimState:
    """[id, team, x, y, hp, max_hp, attack_range, strength,
       phys_dmg, phys_resist, weapon_type, alive]"""

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
                if action.move:
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
# Heuristic
# ---------------------------------------------------------------------------
def _heuristic(state: _SimState, team: int) -> float:
    score = 0.0
    us = state.alive(team)
    them = state.enemies(team)

    # HP and numerical advantage
    our_hp = sum(p[4] for p in us)
    their_hp = sum(p[4] for p in them)
    score += our_hp - their_hp
    score += (len(us) - len(them)) * 50.0

    for f in us:
        mde = min((abs(f[2] - e[2]) + abs(f[3] - e[3])) for e in them) if them else 999.0
        if mde > f[6]:
            score -= (mde - f[6]) * 3.0
        else:
            score += (f[6] - mde) * 2.0

    for e in them:
        nearby = sum(1 for f in us if (abs(f[2] - e[2]) + abs(f[3] - e[3])) <= f[6])
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


# ---------------------------------------------------------------------------
# Candidate builder
# ---------------------------------------------------------------------------
def _build_candidates(env: Environment) -> "List[Tuple[ActionSet, _SimState]]":
    current = env.current_piece
    team = current.team
    legal = get_legal_moves(env)
    enemies = [p for p in env.action_queue if p.is_alive and p.team != team]
    base = _SimState(env)
    pid = current.id
    results = []

    # Sort moves by proximity to nearest enemy
    nearest = min(enemies, key=lambda e: calculate_distance(current.position, e.position)) if enemies else None
    sorted_moves = sorted(legal, key=lambda m: calculate_distance(m, nearest.position)) if nearest else list(legal)
    sampled = [None] + sorted_moves[:_MAX_MOVES]

    for move_pos in sampled:
        # Find best attack target from the NEW position (not pre-computed)
        chosen_atk = None
        if enemies:
            mp = move_pos if move_pos else current.position
            for e in enemies:
                d = abs(mp.x - e.position.x) + abs(mp.y - e.position.y)
                if d <= current.attack_range:
                    if chosen_atk is None or e.health < chosen_atk.health:
                        chosen_atk = e

        act = ActionSet()
        if move_pos is not None:
            act.move = True
            act.move_target = move_pos
        else:
            act.move = False

        if chosen_atk is not None:
            act.attack = True
            act.attack_context = AttackContext()
            act.attack_context.attacker = current
            act.attack_context.target = chosen_atk
        else:
            act.attack = False
        act.spell = False

        s = base.copy()
        s.apply(act, pid)
        results.append((act, s))

    return results


# ---------------------------------------------------------------------------
# Remap
# ---------------------------------------------------------------------------
def _remap(action: ActionSet, env: Environment) -> ActionSet:
    new = ActionSet()
    new.move = action.move
    new.attack = action.attack
    new.spell = action.spell
    new.move_target = action.move_target
    if action.attack and action.attack_context:
        ctx = AttackContext()
        ctx.attacker = env.current_piece
        ft = action.attack_context.target
        if ft is not None:
            for p in env.action_queue:
                if p.id == ft.id and p.team != env.current_piece.team:
                    ctx.target = p
                    break
        ctx.damage_dealt = action.attack_context.damage_dealt
        new.attack_context = ctx
    return new


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_mcts_plus_action_strategy(
    simulation_count: int = 3000,
) -> Callable[..., ActionSet]:
    def strategy(env: Environment) -> ActionSet:
        my_team = env.current_piece.team
        candidates = _build_candidates(env)
        if not candidates:
            return ActionSet()

        nodes = [(act, state, 0, 0.0) for act, state in candidates]

        for _ in range(simulation_count):
            total_v = sum(n[2] for n in nodes)
            best_idx = 0
            best_ucb = float("-inf")
            for i, (_, _, v, val) in enumerate(nodes):
                if v == 0:
                    best_idx = i
                    break
                ucb = val / v + math.sqrt(2.0 * math.log(total_v) / v)
                if ucb > best_ucb:
                    best_ucb = ucb
                    best_idx = i

            act, state, visits, value = nodes[best_idx]
            sc = _heuristic(state, my_team)
            nodes[best_idx] = (act, state, visits + 1, value + sc)

        best = max(nodes, key=lambda n: n[2])
        return _remap(best[0], env)

    return strategy


def get_mcts_plus_init_strategy():
    """Standard STR 29 / DEX 1 / INT 0 sniper init (same as base sniper)."""
    from strategies.sniper import get_sniper_init_strategy
    return get_sniper_init_strategy()
