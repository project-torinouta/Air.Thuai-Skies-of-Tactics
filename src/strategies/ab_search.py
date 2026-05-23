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

"""Alpha-Beta Search with negamax framework and iterative deepening.

Each ply is one piece's action (move + optional attack).  With depth=6
the search covers one full round (all 6 pieces), which naturally handles
multi-piece coordination: each team's formation is built across plies
and the opponent responds before the round ends.

Key insight over flat-tree MCTS: α-β evaluates a complete sequence of
actions (all 3 pieces for each team), so formation-level properties
(centroid, cohesion, focus fire) can be assessed on a state where ALL
pieces have acted — not just one.
"""

import math
from typing import Callable, List, Optional

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from strategy_utils import get_legal_moves
from utils import ActionSet, AttackContext, PieceArg, Point

_SAMPLE_MOVES: int = 12
_SEARCH_DEPTH: int = 6
_REACH: dict = {}
_BOARD_W: int = 0
_BOARD_H: int = 0


# ---------------------------------------------------------------------------
# Reachability cache
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Lightweight simulation state
# ---------------------------------------------------------------------------

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
# Heuristic (same as mcts_v2, minus lethal threat)
# ---------------------------------------------------------------------------

def _heuristic(state: _SimState, team: int) -> float:
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


# ---------------------------------------------------------------------------
# Action generator
# ---------------------------------------------------------------------------

def _gen_actions(state: _SimState, pid: int) -> List[ActionSet]:
    """All legal actions for piece *pid* in *state*.

    For each legal move, generates one action with the best attack target.
    Also generates a stay-put action (with optional attack).
    """
    piece = None
    for p in state.pieces:
        if p[0] == pid:
            piece = p
            break
    if piece is None:
        return []

    team = piece[1]
    enemies = [e for e in state.pieces if e[1] != team and e[11]]
    moves = _light_moves(state, pid)

    # Sort moves by proximity to nearest enemy, sample
    if enemies:
        nearest = min(
            enemies,
            key=lambda e: abs(piece[2] - e[2]) + abs(piece[3] - e[3]),
        )
        moves.sort(
            key=lambda m: abs(m.x - nearest[2]) + abs(m.y - nearest[3]),
        )
    sampled = moves[:_SAMPLE_MOVES]

    actions: List[ActionSet] = []

    # Stay-put action
    stay_target = _best_attack_target(piece, piece[2], piece[3], enemies)
    if stay_target is not None:
        a = ActionSet()
        a.move = False
        a.attack = True
        a.attack_context = AttackContext()
        a.attack_context.target = type("t", (), {"id": stay_target[0]})()
        a.spell = False
        actions.append(a)
    a = ActionSet()
    a.move = False
    a.attack = False
    a.spell = False
    actions.append(a)

    # Move actions
    for m in sampled:
        target = _best_attack_target(piece, m.x, m.y, enemies)
        if target is not None:
            a = ActionSet()
            a.move = True
            a.move_target = m
            a.attack = True
            a.attack_context = AttackContext()
            a.attack_context.target = type("t", (), {"id": target[0]})()
            a.spell = False
            actions.append(a)
        a = ActionSet()
        a.move = True
        a.move_target = m
        a.attack = False
        a.spell = False
        actions.append(a)

    return actions


def _best_attack_target(
    piece: list, nx: int, ny: int, enemies: list,
) -> Optional[list]:
    """Lowest-HP enemy in attack range from (nx, ny), or *None*."""
    best = None
    for e in enemies:
        d = abs(nx - e[2]) + abs(ny - e[3])
        if d <= piece[6]:
            if best is None or e[4] < best[4]:
                best = e
    return best


# ---------------------------------------------------------------------------
# Alpha-Beta core
# ---------------------------------------------------------------------------

def _order_actions(
    actions: List[ActionSet], state: _SimState, pid: int, team: int, our_team: int,
) -> List[ActionSet]:
    """Sort actions by cheap proxy for better α-β pruning.

    Avoids full heuristic eval per action (too expensive).  Instead uses:
    - Attack actions > non-attack (attacking generally dominates)
    - Among attacks: lower-HP target = better kill pressure
    - Among moves: closer to nearest enemy = better positioning

    For MAX nodes (our team) sort descending; for MIN nodes ascending.
    """
    piece = None
    for p in state.pieces:
        if p[0] == pid:
            piece = p
            break
    if piece is None:
        return actions

    enemies = [e for e in state.pieces if e[1] != team and e[11]]

    def score(act: ActionSet) -> float:
        s = 0.0
        if act.attack and act.attack_context:
            tid = act.attack_context.target.id
            for e in enemies:
                if e[0] == tid:
                    raw = piece[7] + piece[8]
                    dmg = max(0, raw - e[9])
                    if piece[10] == 4:
                        dmg = 4
                    s += dmg
                    if dmg >= e[4]:
                        s += 50.0  # killing blow
                    break
            s += 30.0  # any attack is better than no attack
        if act.move and act.move_target:
            mx, my = act.move_target.x, act.move_target.y
            min_d = min(
                (abs(mx - e[2]) + abs(my - e[3])) for e in enemies
            ) if enemies else 999.0
            s -= min_d * 0.1  # closer = slightly better positioning
        return s

    sign = 1 if team == our_team else -1
    actions.sort(key=lambda a: sign * score(a), reverse=True)
    return actions


def _next_idx(state: _SimState, start: int) -> int:
    """Index of the first alive piece at or after *start*."""
    n = len(state.pieces)
    for i in range(start, n):
        if state.pieces[i][11]:
            return i
    return -1


def _alpha_beta(
    state: _SimState, idx: int, depth: int,
    alpha: float, beta: float, our_team: int,
) -> float:
    """Recursive negamax-style α-β search.

    *idx* is the next action-queue index to consider.
    Returns a heuristic score from *our_team*'s perspective.
    """
    # Terminal checks
    if depth <= 0:
        return _heuristic(state, our_team)

    us = [p for p in state.pieces if p[1] == our_team and p[11]]
    them = [p for p in state.pieces if p[1] != our_team and p[11]]
    if not us:
        return float("-inf")
    if not them:
        return float("inf")

    i = _next_idx(state, idx)
    if i < 0:
        # All pieces acted — round boundary; evaluate current state
        return _heuristic(state, our_team)

    piece = state.pieces[i]
    pid = piece[0]
    team = piece[1]

    actions = _gen_actions(state, pid)
    if not actions:
        return _alpha_beta(state, i + 1, depth, alpha, beta, our_team)

    actions = _order_actions(actions, state, pid, team, our_team)

    if team == our_team:
        # MAX node — we choose
        value = float("-inf")
        for act in actions:
            s = state.copy()
            s.apply(act, pid)
            v = _alpha_beta(s, i + 1, depth - 1, alpha, beta, our_team)
            if v > value:
                value = v
            if value > alpha:
                alpha = value
            if alpha >= beta:
                break
        return value
    else:
        # MIN node — opponent chooses
        value = float("inf")
        for act in actions:
            s = state.copy()
            s.apply(act, pid)
            v = _alpha_beta(s, i + 1, depth - 1, alpha, beta, our_team)
            if v < value:
                value = v
            if value < beta:
                beta = value
            if alpha >= beta:
                break
        return value


# ---------------------------------------------------------------------------
# Init strategy
# ---------------------------------------------------------------------------

def get_ab_search_init_strategy() -> Callable[..., List[PieceArg]]:
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


# ---------------------------------------------------------------------------
# Action strategy
# ---------------------------------------------------------------------------

def get_ab_search_action_strategy(
    search_depth: int = _SEARCH_DEPTH,
) -> Callable[..., ActionSet]:
    """Alpha-Beta action strategy with iterative deepening.

    :param search_depth: Search depth in plies (default 6 = one full round).
    :type search_depth: int
    :returns: A callable action strategy.
    :rtype: Callable
    """
    def strategy(env: Environment) -> ActionSet:
        if not _REACH:
            _build_reach(env)

        team = env.current_piece.team
        current = env.current_piece
        current_pid = current.id
        base = _SimState(env)

        # Find current piece's index in the action queue
        root_idx = 0
        for i, p in enumerate(base.pieces):
            if p[0] == current_pid:
                root_idx = i
                break

        # Generate root actions for the current piece
        root_actions = _gen_actions(base, current_pid)
        if not root_actions:
            return ActionSet()

        # Order root actions
        root_actions = _order_actions(root_actions, base, current_pid, team, team)

        # Search each root action with α-β, pick the best
        best_action = root_actions[0]
        best_value = float("-inf")

        for act in root_actions:
            s = base.copy()
            s.apply(act, current_pid)
            v = _alpha_beta(
                s, root_idx + 1, search_depth - 1,
                float("-inf"), float("inf"), team,
            )
            if v > best_value:
                best_value = v
                best_action = act

        return _remap_action(best_action, env)

    return strategy
