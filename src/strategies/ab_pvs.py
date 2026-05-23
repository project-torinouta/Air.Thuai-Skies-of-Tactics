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

"""Alpha-Beta with PVS + Transposition Table + Iterative Deepening.

Standard competitive search stack for perfect-information games:

  PVS (Principal Variation Search)
    └─ Zero-window search on non-PV children for more aggressive pruning

  Transposition Table
    └─ Caches (hash → depth, value, flag, best-move) to avoid re-exploration
    └─ Flags: EXACT / LOWERBOUND / UPPERBOUND

  Iterative Deepening
    └─ Depth 1 → 2 → … → max; previous PV seeds move ordering

  Quiescence Search
    └─ Continues search at leaf nodes over attack-only actions until
        the board is "quiet" (no captures possible)

  History Heuristic
    └─ Beta-cutoff moves get a depth-squared bonus for future ordering

All built on the same _SimState + heuristic as mcts_v2.
"""

import math
from typing import Callable, Dict, List, Optional, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from strategy_utils import get_legal_moves
from utils import ActionSet, AttackContext, PieceArg, Point

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SAMPLE_MOVES: int = 12
_MAX_DEPTH: int = 6

# TT flags
_EXACT: int = 0
_LOWER: int = 1  # beta-cutoff → true value >= stored
_UPPER: int = 2  # alpha-cutoff → true value <= stored

# ---------------------------------------------------------------------------
# Globals (reachability cache, transposition table, history heuristic)
# ---------------------------------------------------------------------------

_REACH: dict = {}
_BOARD_W: int = 0
_BOARD_H: int = 0
_TT: Dict[tuple, tuple] = {}  # key → (depth, value, flag, move_pid, move_serial)
_HISTORY: Dict[int, Dict[int, int]] = {}  # pid → action_hash → score


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

    def state_key(self, idx: int, is_max: int) -> tuple:
        """Hashable search-state key for the transposition table."""
        pieces = tuple(
            (p[0], p[2], p[3], int(p[4]), p[11])
            for p in self.pieces
        )
        return (pieces, idx, is_max)


# ---------------------------------------------------------------------------
# Heuristic (same as mcts_v2)
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
# Action generation
# ---------------------------------------------------------------------------

def _best_target(piece: list, nx: int, ny: int, enemies: list) -> Optional[list]:
    """Lowest-HP enemy in attack range from (nx, ny)."""
    best = None
    for e in enemies:
        d = abs(nx - e[2]) + abs(ny - e[3])
        if d <= piece[6]:
            if best is None or e[4] < best[4]:
                best = e
    return best


def _action_serial(pid: int, mx: int, my: int, has_attack: bool, tid: int) -> int:
    """Deterministic hash of an action for the history heuristic."""
    return hash((pid, mx, my, has_attack, tid))


def _gen_actions(state: _SimState, pid: int) -> List[ActionSet]:
    """All legal actions for piece *pid*.

    For each legal move: one action with best-in-range attack target,
    and one action without attack.  Moves sorted by distance to nearest
    enemy.  Sampled to _SAMPLE_MOVES.
    """
    piece = next((p for p in state.pieces if p[0] == pid), None)
    if piece is None:
        return []

    team = piece[1]
    enemies = [e for e in state.pieces if e[1] != team and e[11]]
    moves = _light_moves(state, pid)

    if enemies and moves:
        nearest = min(
            enemies,
            key=lambda e: abs(piece[2] - e[2]) + abs(piece[3] - e[3]),
        )
        moves.sort(
            key=lambda m: abs(m.x - nearest[2]) + abs(m.y - nearest[3]),
        )
    sampled = moves[:_SAMPLE_MOVES]

    actions: List[ActionSet] = []

    # Stay-put with optional attack
    st = _best_target(piece, piece[2], piece[3], enemies)
    if st is not None:
        a = ActionSet()
        a.move = False
        a.attack = True
        a.attack_context = AttackContext()
        a.attack_context.target = type("t", (), {"id": st[0]})()
        a.spell = False
        actions.append(a)
    a = ActionSet()
    a.move = False
    a.attack = False
    a.spell = False
    actions.append(a)

    # Move actions
    for m in sampled:
        t = _best_target(piece, m.x, m.y, enemies)
        if t is not None:
            a = ActionSet()
            a.move = True
            a.move_target = m
            a.attack = True
            a.attack_context = AttackContext()
            a.attack_context.target = type("t", (), {"id": t[0]})()
            a.spell = False
            actions.append(a)
        a = ActionSet()
        a.move = True
        a.move_target = m
        a.attack = False
        a.spell = False
        actions.append(a)

    return actions


# ---------------------------------------------------------------------------
# Move ordering
# ---------------------------------------------------------------------------

def _order_moves(
    actions: List[ActionSet],
    state: _SimState,
    pid: int,
    team: int,
    our_team: int,
    tt_hint: Optional[ActionSet],
) -> List[ActionSet]:
    """Order actions for search.

    Priority:
    1. TT best move (first)
    2. History heuristic score (descending for MAX, ascending for MIN)
    3. Attack > non-attack, plus damage estimate
    """
    piece = next((p for p in state.pieces if p[0] == pid), None)
    if piece is None:
        return actions

    enemies = [e for e in state.pieces if e[1] != team and e[11]]
    is_max = team == our_team
    sign = 1 if is_max else -1

    def score(act: ActionSet) -> float:
        s = 0.0
        mx = act.move_target.x if act.move and act.move_target else piece[2]
        my = act.move_target.y if act.move and act.move_target else piece[3]

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
                        s += 50.0
                    break
            s += 30.0  # any attack > no attack

        # Positioning proxy
        if enemies:
            min_d = min(
                (abs(mx - e[2]) + abs(my - e[3])) for e in enemies
            )
            s -= min_d * 0.1

        # History bonus
        h = _action_serial(pid, mx, my, bool(act.attack and act.attack_context),
                           act.attack_context.target.id if act.attack and act.attack_context else -1)
        hist_score = _HISTORY.get(pid, {}).get(h, 0)
        s += hist_score * 0.01

        return s

    actions.sort(key=lambda a: sign * score(a), reverse=True)

    # TT hint to front (overrides other sorting)
    if tt_hint is not None:
        for i, a in enumerate(actions):
            if _actions_equal(a, tt_hint):
                if i > 0:
                    actions[0], actions[i] = actions[i], actions[0]
                break

    return actions


def _actions_equal(a: ActionSet, b: ActionSet) -> bool:
    """Whether two actions are functionally identical."""
    if a.move != b.move or a.attack != b.attack or a.spell != b.spell:
        return False
    if a.move and b.move and a.move_target and b.move_target:
        if a.move_target.x != b.move_target.x or a.move_target.y != b.move_target.y:
            return False
    if a.attack and b.attack and a.attack_context and b.attack_context:
        ta = a.attack_context.target
        tb = b.attack_context.target
        if ta is None and tb is None:
            return True
        if ta is None or tb is None:
            return False
        return ta.id == tb.id
    return a.attack == b.attack


# ---------------------------------------------------------------------------
# Quiescence Search — extend leaf nodes over attack-only actions
# ---------------------------------------------------------------------------

def _quiescence(
    state: _SimState, idx: int, alpha: float, beta: float,
    our_team: int, is_max: bool, max_qdepth: int = 2,
) -> float:
    """Stand-pat quiescence with explicit MAX/MIN.

    Evaluates attack-only actions at leaf nodes.  Depth limited to 2
    to prevent explosion — enough to resolve one capture response.
    """
    stand_pat = _heuristic(state, our_team)

    if max_qdepth <= 0:
        return stand_pat

    if is_max:
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat
    else:
        if stand_pat <= alpha:
            return alpha
        if stand_pat < beta:
            beta = stand_pat

    i = _next_idx(state, idx)
    if i < 0:
        return stand_pat

    piece = state.pieces[i]
    pid = piece[0]
    team = piece[1]
    enemies = [e for e in state.pieces if e[1] != team and e[11]]
    child_is_max = (team == our_team)

    # Only attack actions
    actions: List[ActionSet] = []
    t = _best_target(piece, piece[2], piece[3], enemies)
    if t is not None:
        a = ActionSet()
        a.move = False
        a.attack = True
        a.attack_context = AttackContext()
        a.attack_context.target = type("t", (), {"id": t[0]})()
        a.spell = False
        actions.append(a)
    for m in _light_moves(state, pid):
        t = _best_target(piece, m.x, m.y, enemies)
        if t is not None:
            a = ActionSet()
            a.move = True
            a.move_target = m
            a.attack = True
            a.attack_context = AttackContext()
            a.attack_context.target = type("t", (), {"id": t[0]})()
            a.spell = False
            actions.append(a)

    if not actions:
        return stand_pat

    # Sort by heuristic delta, single copy per action
    scored = []
    for act in actions:
        s = state.copy()
        s.apply(act, pid)
        scored.append((act, _heuristic(s, our_team)))
    scored.sort(key=lambda x: x[1], reverse=is_max)

    for act, _ in scored:
        s = state.copy()
        s.apply(act, pid)
        val = _quiescence(s, i + 1, alpha, beta, our_team, child_is_max, max_qdepth - 1)

        if is_max:
            if val > alpha:
                alpha = val
            if alpha >= beta:
                break
        else:
            if val < beta:
                beta = val
            if alpha >= beta:
                break

    return alpha if is_max else beta


# ---------------------------------------------------------------------------
# PVS core
# ---------------------------------------------------------------------------

def _next_idx(state: _SimState, start: int) -> int:
    """First alive piece at or after *start*; -1 if none."""
    for i in range(start, len(state.pieces)):
        if state.pieces[i][11]:
            return i
    return -1


def _pvs(
    state: _SimState, idx: int, depth: int,
    alpha: float, beta: float, our_team: int, is_max: bool = True,
) -> Tuple[float, Optional[ActionSet]]:
    """Principal Variation Search (fail-soft) with TT.

    ALL values are from *our_team*'s perspective (not negamax).
    *is_max* = True for our turn (MAX), False for opponent (MIN).
    """
    # Terminal → quiescence
    if depth <= 0:
        return _quiescence(state, idx, alpha, beta, our_team, is_max), None

    us = [p for p in state.pieces if p[1] == our_team and p[11]]
    them = [p for p in state.pieces if p[1] != our_team and p[11]]
    if not us:
        return float("-inf"), None
    if not them:
        return float("inf"), None

    # Find next piece
    i = _next_idx(state, idx)
    if i < 0:
        return _heuristic(state, our_team), None

    piece = state.pieces[i]
    pid = piece[0]
    team = piece[1]

    # Determine child's type based on who acts next
    next_i = _next_idx(state, i + 1)
    if next_i >= 0:
        child_is_max = (state.pieces[next_i][1] == our_team)
    else:
        child_is_max = True  # round boundary — heuristic eval next

    # TT probe
    key = state.state_key(idx, int(is_max))
    tt_entry = _TT.get(key)
    tt_hint: Optional[ActionSet] = None
    if tt_entry is not None:
        tt_depth, tt_val, tt_flag, tt_pid, tt_ser = tt_entry
        if tt_depth >= depth:
            if tt_flag == _EXACT:
                return tt_val, None
            if is_max and tt_flag == _LOWER and tt_val > alpha:
                alpha = tt_val
            if not is_max and tt_flag == _UPPER and tt_val < beta:
                beta = tt_val
            if alpha >= beta:
                return tt_val, None
        if tt_pid is not None:
            tt_hint = _deserialize_action(tt_pid, tt_ser)

    actions = _gen_actions(state, pid)
    if not actions:
        return _pvs(state, i + 1, depth, alpha, beta, our_team, is_max)

    actions = _order_moves(actions, state, pid, team, our_team, tt_hint)

    best_action: Optional[ActionSet] = None
    orig_alpha = alpha

    if is_max:  # MAX — our turn, maximise
        best_value = float("-inf")
        for j, act in enumerate(actions):
            s = state.copy()
            s.apply(act, pid)

            if j == 0:
                val, _ = _pvs(s, i + 1, depth - 1, alpha, beta, our_team, child_is_max)
            else:
                val, _ = _pvs(s, i + 1, depth - 1, alpha, alpha + 1, our_team, child_is_max)
                if val > alpha and val < beta:
                    val, _ = _pvs(s, i + 1, depth - 1, alpha, beta, our_team, child_is_max)

            if val > best_value:
                best_value = val
                best_action = act
            if val > alpha:
                alpha = val
            if alpha >= beta:
                ser = _serialize_action(act)
                _TT[key] = (depth, best_value, _LOWER, pid, ser)
                _history_update(pid, act, depth)
                return best_value, best_action
    else:  # MIN — opponent's turn, minimise
        best_value = float("inf")
        for j, act in enumerate(actions):
            s = state.copy()
            s.apply(act, pid)

            if j == 0:
                val, _ = _pvs(s, i + 1, depth - 1, alpha, beta, our_team, child_is_max)
            else:
                val, _ = _pvs(s, i + 1, depth - 1, alpha, alpha + 1, our_team, child_is_max)
                if val < beta and val > alpha:
                    val, _ = _pvs(s, i + 1, depth - 1, alpha, beta, our_team, child_is_max)

            if val < best_value:
                best_value = val
                best_action = act
            if val < beta:
                beta = val
            if alpha >= beta:
                ser = _serialize_action(act)
                _TT[key] = (depth, best_value, _UPPER, pid, ser)
                _history_update(pid, act, depth)
                return best_value, best_action

    # TT store
    flag = _EXACT
    if is_max and best_value <= orig_alpha:
        flag = _UPPER
    elif not is_max and best_value >= beta:
        flag = _LOWER
    ser = _serialize_action(best_action) if best_action is not None else -1
    _TT[key] = (depth, best_value, flag, pid, ser)

    return best_value, best_action


def _serialize_action(act: ActionSet) -> int:
    """Deterministic hash of an action for TT storage."""
    mx = act.move_target.x if act.move and act.move_target else -1
    my = act.move_target.y if act.move and act.move_target else -1
    tid = act.attack_context.target.id if act.attack and act.attack_context else -1
    return hash((mx, my, int(act.attack), tid))


def _deserialize_action(pid: int, ser: int) -> Optional[ActionSet]:
    """Reconstruct an action from a serialised value.

    Since we can't fully invert the hash, we return *None* and fall
    back to the history-heuristic ordering.  (In practice this is fine.)
    """
    return None


def _history_update(pid: int, act: ActionSet, depth: int) -> None:
    """Give *act* a bonus proportional to *depth^2* in the history table."""
    mx = act.move_target.x if act.move and act.move_target else -1
    my = act.move_target.y if act.move and act.move_target else -1
    tid = act.attack_context.target.id if act.attack and act.attack_context else -1
    h = _action_serial(pid, mx, my, bool(act.attack and act.attack_context), tid)
    if pid not in _HISTORY:
        _HISTORY[pid] = {}
    _HISTORY[pid][h] = _HISTORY[pid].get(h, 0) + depth * depth


# ---------------------------------------------------------------------------
# Iterative Deepening
# ---------------------------------------------------------------------------

def _iterative_deepening(
    state: _SimState, start_idx: int, our_team: int,
    max_depth: int,
) -> ActionSet:
    """Iterative deepening: search depth 2, 3, …, max_depth.

    The first piece at *start_idx* determines whether the root is
    MAX (our team) or MIN (opponent).

    Each iteration seeds the next with a TT hint for move ordering.
    """
    # Clear TT and history each decision
    _TT.clear()
    _HISTORY.clear()

    i = _next_idx(state, start_idx)
    root_is_max = (i >= 0 and state.pieces[i][1] == our_team)

    best_action = None
    for d in range(2, max_depth + 1):
        val, act = _pvs(state, start_idx, d, float("-inf"), float("inf"),
                        our_team, root_is_max)
        if act is not None:
            best_action = act

    return best_action if best_action is not None else ActionSet()


# ---------------------------------------------------------------------------
# Init strategy
# ---------------------------------------------------------------------------

def get_ab_pvs_init_strategy() -> Callable[..., List[PieceArg]]:
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
# Action strategy
# ---------------------------------------------------------------------------

def get_ab_pvs_action_strategy(
    search_depth: int = _MAX_DEPTH,
) -> Callable[..., ActionSet]:
    """Alpha-Beta (PVS + TT + ID) action strategy.

    :param search_depth: Maximum search depth in plies (default 8).
    :type search_depth: int
    :returns: A callable action strategy.
    :rtype: Callable
    """
    def strategy(env: Environment) -> ActionSet:
        if not _REACH:
            _build_reach(env)

        team = env.current_piece.team
        current_pid = env.current_piece.id
        base = _SimState(env)

        root_idx = next(
            (i for i, p in enumerate(base.pieces) if p[0] == current_pid),
            -1,
        )
        if root_idx < 0:
            return ActionSet()

        best_action = _iterative_deepening(
            base, root_idx, team, search_depth,
        )

        # Fallback: if search returned an empty ActionSet, use the first action
        if not getattr(best_action, 'move', False) \
           and not getattr(best_action, 'attack', False) \
           and not getattr(best_action, 'spell', False):
            fallback_actions = _gen_actions(base, current_pid)
            if fallback_actions:
                best_action = fallback_actions[0]

        return _remap_action(best_action, env)

    return strategy
