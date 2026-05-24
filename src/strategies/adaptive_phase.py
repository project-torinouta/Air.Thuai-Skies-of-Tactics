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

"""Adaptive Phase — phase-switching hybrid MCTS + Alpha-Beta strategy.

Phase 1 (3v3 opening):   Pure MCTS, high rollouts, broad strategic vision.
Phase 2 (mid-game 2v2+): MCTS + Alpha-Beta leaf eval, balanced mix.
Phase 3 (endgame 1v1):   Pure Alpha-Beta, deep search, exact calculation.
"""

import copy
import math
import random
from typing import Callable, List, Optional, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


# ==============================================================================
#  Core: lightweight tactical state for in-memory simulation
# ==============================================================================

class TacticalState:
    """Lightweight game state proxy for in-memory tree search."""

    def __init__(
        self,
        current_pos: Point,
        friends: list,
        enemies: list,
        is_max_turn: bool,
        attack_range: int = 9,
        damage_per_hit: int = 23,
    ):
        self.current_pos = current_pos
        self.friends = copy.deepcopy(friends)
        self.enemies = copy.deepcopy(enemies)
        self.is_max_turn = is_max_turn
        self.attack_range = attack_range
        self.damage_per_hit = damage_per_hit

    def get_filtered_actions(self, legal_moves: List[Point]) -> List[Point]:
        """Strategic move pruning: only 3 high-value candidates."""
        if not legal_moves:
            return [self.current_pos]
        if not self.enemies or not self.friends:
            return [legal_moves[0]]

        target_enemy = min(self.enemies, key=lambda e: e.health)
        strategic = []

        # 1. Rush toward lowest-HP enemy
        best_rush = min(
            legal_moves,
            key=lambda m: abs(m.x - target_enemy.position.x)
                          + abs(m.y - target_enemy.position.y),
        )
        strategic.append(best_rush)

        # 2. Hold position
        if any(m.x == self.current_pos.x and m.y == self.current_pos.y
               for m in legal_moves):
            strategic.append(self.current_pos)

        # 3. Rally toward nearest teammate
        other_fs = [
            f for f in self.friends
            if f.position.x != self.current_pos.x
            or f.position.y != self.current_pos.y
        ]
        if other_fs:
            nearest_f = min(
                other_fs,
                key=lambda f: abs(self.current_pos.x - f.position.x)
                              + abs(self.current_pos.y - f.position.y),
            )
            best_rally = min(
                legal_moves,
                key=lambda m: abs(m.x - nearest_f.position.x)
                              + abs(m.y - nearest_f.position.y),
            )
            strategic.append(best_rally)

        return list(set(strategic))

    def step(self, move_to: Point) -> "TacticalState":
        """Advance one ply in the simulated timeline."""
        next_fs = copy.deepcopy(self.friends)
        next_es = copy.deepcopy(self.enemies)

        if self.is_max_turn:
            if next_es:
                target = min(next_es, key=lambda e: e.health)
                dist = (abs(move_to.x - target.position.x)
                        + abs(move_to.y - target.position.y))
                if dist <= self.attack_range:
                    target.health -= self.damage_per_hit
                next_es = [e for e in next_es if e.health > 0]
            return TacticalState(
                move_to, next_fs, next_es, is_max_turn=False,
                attack_range=self.attack_range, damage_per_hit=self.damage_per_hit,
            )
        else:
            if next_fs:
                next_fs[0].health -= self.damage_per_hit
                next_fs = [f for f in next_fs if f.health > 0]
            return TacticalState(
                self.current_pos, next_fs, next_es, is_max_turn=True,
                attack_range=self.attack_range, damage_per_hit=self.damage_per_hit,
            )

    def evaluate(self) -> float:
        """Multi-dimensional heuristic: numerical advantage dominates."""
        if not self.friends:
            return -2000.0
        if not self.enemies:
            return 2000.0
        f_hp = sum(f.health for f in self.friends)
        e_hp = sum(e.health for e in self.enemies)
        return (len(self.friends) - len(self.enemies)) * 150.0 + (f_hp - e_hp) * 2.0


# ==============================================================================
#  Sub-algo 1: Pure Alpha-Beta deep search (endgame)
# ==============================================================================

def alpha_beta_search(
    state: TacticalState,
    depth: int,
    alpha: float,
    beta: float,
    legal_moves: List[Point],
) -> Tuple[float, Optional[Point]]:
    """Deep alpha-beta for endgame: narrow tree, high depth."""
    if depth == 0 or not state.friends or not state.enemies:
        return state.evaluate(), state.current_pos

    moves = state.get_filtered_actions(legal_moves)
    best_move = state.current_pos

    if state.is_max_turn:
        max_v = -float('inf')
        for m in moves:
            val, _ = alpha_beta_search(state.step(m), depth - 1, alpha, beta, [m])
            if val > max_v:
                max_v = val
                best_move = m
            alpha = max(alpha, val)
            if beta <= alpha:
                break
        return max_v, best_move
    else:
        min_v = float('inf')
        for m in moves:
            val, _ = alpha_beta_search(state.step(m), depth - 1, alpha, beta, [m])
            if val < min_v:
                min_v = val
                best_move = m
            beta = min(beta, val)
            if beta <= alpha:
                break
        return min_v, best_move


# ==============================================================================
#  Sub-algo 2: MCTS tree with UCB1
# ==============================================================================

class MCTSNode:
    """MCTS tree node with UCB1 selection."""

    def __init__(self, state: TacticalState, parent=None, move_taken=None):
        self.state = state
        self.parent = parent
        self.move_taken = move_taken
        self.children: List[MCTSNode] = []
        self.visits = 0
        self.total_value = 0.0

    def ucb_select(self, c_param: float = 1.414) -> "MCTSNode":
        weights = [
            (c.total_value / (c.visits + 1e-6))
            + c_param * math.sqrt(math.log(self.visits + 1) / (c.visits + 1e-6))
            for c in self.children
        ]
        return self.children[weights.index(max(weights))]


def run_hybrid_engine(
    legal_moves: List[Point],
    root_state: TacticalState,
    sim_count: int,
    use_ab_cutoff: bool,
) -> Optional[Point]:
    """Core hybrid search engine: MCTS + optional Alpha-Beta leaf eval."""
    root_node = MCTSNode(root_state)

    for _ in range(sim_count):
        node = root_node

        # 1. Selection
        while (
            node.children
            and len(node.children) == len(node.state.get_filtered_actions(legal_moves))
        ):
            node = node.ucb_select()

        # 2. Expansion
        all_moves = node.state.get_filtered_actions(legal_moves)
        expanded_moves = [c.move_taken for c in node.children]
        unexpanded = [m for m in all_moves if m not in expanded_moves]

        if unexpanded:
            m = random.choice(unexpanded)
            new_node = MCTSNode(node.state.step(m), parent=node, move_taken=m)
            node.children.append(new_node)
            node = new_node

        # 3. Simulation / Cutoff
        if use_ab_cutoff:
            score = alpha_beta_search(
                node.state, depth=2,
                alpha=-float('inf'), beta=float('inf'),
                legal_moves=legal_moves,
            )[0]
        else:
            sim_s = node.state
            for _ in range(3):
                if not sim_s.friends or not sim_s.enemies:
                    break
                ms = sim_s.get_filtered_actions(legal_moves)
                sim_s = sim_s.step(random.choice(ms))
            score = sim_s.evaluate()

        # 4. Backpropagation
        while node is not None:
            node.visits += 1
            node.total_value += score
            node = node.parent

    if root_node.children:
        return max(root_node.children, key=lambda c: c.visits).move_taken
    return root_state.current_pos


# ==============================================================================
#  Main: phase-adaptive command centre
# ==============================================================================

def get_adaptive_phase_init_strategy() -> Callable[..., List[PieceArg]]:
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


def get_adaptive_phase_action_strategy() -> Callable[..., ActionSet]:
    """Phase-adaptive hybrid strategy."""
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current = env.current_piece

        if current is None or not current.is_alive:
            return action

        enemies = [
            p for p in env.action_queue
            if p.team != current.team and p.is_alive
        ]
        friends = [
            p for p in env.action_queue
            if p.team == current.team and p.is_alive
        ]
        if not enemies:
            return action

        from strategy_utils import get_legal_moves
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            legal_moves = [current.position]

        initial_state = TacticalState(
            current.position, friends, enemies, is_max_turn=True,
            attack_range=current.attack_range,
        )
        best_grid: Optional[Point] = current.position

        f_cnt, e_cnt = len(friends), len(enemies)

        if f_cnt == 3 and e_cnt == 3:
            # Phase 1: 3v3 opening — pure MCTS, broad strategic vision
            best_grid = run_hybrid_engine(
                legal_moves, initial_state, sim_count=1000, use_ab_cutoff=False,
            )
        elif f_cnt >= 2 and e_cnt >= 2:
            # Phase 2: mid-game — MCTS + Alpha-Beta leaf eval
            best_grid = run_hybrid_engine(
                legal_moves, initial_state, sim_count=1000, use_ab_cutoff=True,
            )
        else:
            # Phase 3: endgame — pure Alpha-Beta deep search
            _, best_grid = alpha_beta_search(
                initial_state, depth=10,
                alpha=-float('inf'), beta=float('inf'),
                legal_moves=legal_moves,
            )

        if best_grid is None:
            best_grid = current.position

        action.move = (best_grid.x != current.position.x
                       or best_grid.y != current.position.y)
        if action.move:
            action.move_target = best_grid

        final_pos = action.move_target if action.move else current.position
        global_target = min(enemies, key=lambda e: e.health)

        def d(p1, p2) -> float:
            return abs(p1.x - p2.x) + abs(p1.y - p2.y)

        if d(final_pos, global_target.position) <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = global_target
        else:
            nearest = min(enemies, key=lambda e: d(final_pos, e.position))
            if d(final_pos, nearest.position) <= current.attack_range:
                action.attack = True
                action.attack_context = AttackContext()
                action.attack_context.attacker = current
                action.attack_context.target = nearest
            else:
                action.attack = False

        action.spell = False
        return action

    return strategy
