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

"""MCTS (original reference) — tree structure with _SimState.

Same tree logic (expand-all + UCB1 + random playout) but replaces
expensive ``fork_environment`` calls with lightweight ``_SimState``
backed by a pre-computed reachability cache.
"""

import math
import random
from typing import Callable, List, Optional, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from strategy_utils import (
    get_attackable_targets,
    get_legal_moves,
)
from utils import (
    ActionSet,
    AttackContext,
    PieceArg,
    Point,
)

MCTS_VERBOSE: bool = False

# ---------------------------------------------------------------------------
# Reachability cache — computed once per game
# ---------------------------------------------------------------------------
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
    """Legal moves for *pid* using reachability cache."""
    for p in state.pieces:
        if p[0] == pid:
            cx, cy = p[2], p[3]
            occ = {(q[2], q[3]) for q in state.pieces if q[11] and q[0] != pid}
            return [m for m in _REACH.get((cx, cy), []) if (m.x, m.y) not in occ]
    return []


def _light_attackable(state: "_SimState", pid: int, enemy_team: int) -> list:
    """Enemy pieces within attack range of *pid*."""
    for p in state.pieces:
        if p[0] == pid:
            rng = p[6]
            return [
                e for e in state.pieces
                if e[11] and e[1] == enemy_team
                and (abs(p[2] - e[2]) + abs(p[3] - e[3])) <= rng
            ]
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
# Init
# ---------------------------------------------------------------------------
def get_mcts_original_init_strategy() -> Callable[..., List[PieceArg]]:
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
# MCTS with _SimState
# ---------------------------------------------------------------------------
def get_mcts_original_action_strategy(
    simulation_count: int = 300,
) -> Callable[..., ActionSet]:
    """Return MCTS action strategy using _SimState + random playout.

    :param simulation_count: Simulations per decision (default 300).
    :type simulation_count: int
    :returns: A callable action strategy.
    :rtype: Callable
    """
    class MCTSNode:
        def __init__(
            self,
            state: "_SimState",
            parent: Optional["MCTSNode"] = None,
            action: Optional[ActionSet] = None,
            pid: int = -1,
        ):
            self.state = state
            self.parent = parent
            self.action = action
            self.pid = pid
            self.children: List["MCTSNode"] = []
            self.visits = 0
            self.value = 0.0

    # Max moves to expand per node (sample closest to nearest enemy)
    _SAMPLE_MOVES: int = 10

    def expand_node(node: MCTSNode, env: Environment, team: int) -> None:
        """Generate children for *team* — sampled to keep branching manageable."""
        current = env.current_piece
        all_moves = get_legal_moves(env)
        attackable = get_attackable_targets(env)
        pid = current.id

        # Sort moves by distance to nearest enemy, take top _SAMPLE_MOVES
        enemies = [p for p in env.action_queue if p.is_alive and p.team != team]
        if enemies and all_moves:
            nearest = min(enemies, key=lambda e: calculate_distance(current.position, e.position))
            all_moves.sort(key=lambda m: calculate_distance(m, nearest.position))
        moves = [None] + all_moves[:_SAMPLE_MOVES]

        for move_pos in moves:
            atk_target = None
            if attackable:
                mp = move_pos if move_pos else current.position
                for at in attackable:
                    d = abs(mp.x - at.position.x) + abs(mp.y - at.position.y)
                    if d <= current.attack_range:
                        atk_target = at
                        break

            act = ActionSet()
            if move_pos is not None:
                act.move = True
                act.move_target = move_pos
            else:
                act.move = False
            if atk_target is not None:
                act.attack = True
                act.attack_context = AttackContext()
                act.attack_context.attacker = current
                act.attack_context.target = atk_target
            else:
                act.attack = False
            act.spell = False

            child_state = node.state.copy()
            child_state.apply(act, pid)
            child = MCTSNode(child_state, node, act, pid)
            node.children.append(child)

    def simulate(state: _SimState, team: int) -> float:
        """Random playout (max 50 steps) on a _SimState."""
        sim = state.copy()
        max_steps = 50
        ct = team  # current team to act

        while max_steps > 0:
            pieces = sim.alive(ct)
            if not pieces:
                break
            # Pick the piece to act (lowest HP on current team)
            piece = min(pieces, key=lambda p: p[4])
            pid = piece[0]
            legal = _light_moves(sim, pid)
            atkable = _light_attackable(sim, pid, 2 if ct == 1 else 1)

            act = ActionSet()
            if legal and random.random() < 0.7:
                act.move = True
                act.move_target = random.choice(legal)
            else:
                act.move = False
            if atkable and random.random() < 0.8:
                tgt = random.choice(atkable)
                act.attack = True
                act.attack_context = AttackContext()
                act.attack_context.target = type("t", (), {"id": tgt[0]})()
            else:
                act.attack = False
            act.spell = False

            sim.apply(act, pid)
            ct = 2 if ct == 1 else 1
            max_steps -= 1

        my_hp = sum(p[4] for p in sim.alive(team))
        opp_hp = sum(p[4] for p in sim.enemies(team))
        if my_hp > opp_hp:
            return 1.0
        if opp_hp > my_hp:
            return -1.0
        return 0.0

    def backpropagate(node: MCTSNode, value: float) -> None:
        while node is not None:
            node.visits += 1
            node.value += value
            node = node.parent
            value = -value

    def ucb1(node: MCTSNode, parent_visits: int) -> float:
        if node.visits == 0:
            return float("inf")
        return node.value / node.visits + math.sqrt(
            2 * math.log(parent_visits) / node.visits,
        )

    def strategy(env: Environment) -> ActionSet:
        if not _REACH:
            _build_reach(env)

        my_team = env.current_piece.team
        root_state = _SimState(env)
        root = MCTSNode(root_state)

        # Expand all children at root using the real env
        expand_node(root, env, my_team)
        if not root.children:
            return ActionSet()

        for _ in range(simulation_count):
            node = root
            while node.children:
                node = max(node.children, key=lambda c: ucb1(c, node.visits if node is root else node.parent.visits if node.parent else 1))
            value = simulate(node.state, my_team)
            backpropagate(node, value)

        best = max(root.children, key=lambda c: c.visits)
        if MCTS_VERBOSE:
            print(f"[MCTS] Best: visits={best.visits}, value={best.value}")
        return _remap_action(best.action, env)

    return strategy
