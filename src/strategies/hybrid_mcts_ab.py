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

"""Hybrid MCTS + Alpha-Beta strategy.

Combines:
  - MCTS for high-level strategic search (60 rollouts, UCB1 selection)
  - Alpha-Beta (depth 2) for local tactical evaluation at leaf nodes
  - Lightweight SimulatedState for fast forward simulation
  - Strategic move pruning (3 candidates per node)
"""

import copy
import math
import random
from typing import Callable, List, Optional, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


# ==================== 1. Forward model ====================

class SimulatedState:
    """Lightweight forward-simulation state for in-memory game tree search."""

    def __init__(
        self,
        current_pos: Point,
        friends: list,
        enemies: list,
        is_max_turn: bool,
        attack_range: int = 9,
        damage_per_hit: int = 45,
    ):
        self.current_pos = current_pos
        self.friends = copy.deepcopy(friends)
        self.enemies = copy.deepcopy(enemies)
        self.is_max_turn = is_max_turn
        self.attack_range = attack_range
        self.damage_per_hit = damage_per_hit

    def get_strategic_moves(self, legal_moves: List[Point]) -> List[Point]:
        """Prune action space: only 3 strategically valuable moves."""
        if not legal_moves:
            return [self.current_pos]
        if not self.enemies or not self.friends:
            return [legal_moves[0]]

        target_enemy = min(self.enemies, key=lambda e: e.health)
        strategic = []

        # 1. Rush: closest to the lowest-HP enemy
        best_rush = min(
            legal_moves,
            key=lambda m: abs(m.x - target_enemy.position.x)
                          + abs(m.y - target_enemy.position.y),
        )
        strategic.append(best_rush)

        # 2. Hold: stay in place
        if any(m.x == self.current_pos.x and m.y == self.current_pos.y for m in legal_moves):
            strategic.append(self.current_pos)

        # 3. Rally: toward the nearest alive teammate
        other_friends = [
            f for f in self.friends
            if f.position.x != self.current_pos.x
            or f.position.y != self.current_pos.y
        ]
        if other_friends:
            nearest_f = min(
                other_friends,
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

    def simulate_action(self, move_point: Point) -> "SimulatedState":
        """Advance one ply: move + focus-fire attack."""
        next_friends = copy.deepcopy(self.friends)
        next_enemies = copy.deepcopy(self.enemies)

        if self.is_max_turn:
            # Our turn: attack the lowest-HP enemy if in range
            if next_enemies:
                target = min(next_enemies, key=lambda e: e.health)
                dist = (abs(move_point.x - target.position.x)
                        + abs(move_point.y - target.position.y))
                if dist <= self.attack_range:
                    target.health -= self.damage_per_hit
                next_enemies = [e for e in next_enemies if e.health > 0]
            return SimulatedState(
                move_point, next_friends, next_enemies,
                is_max_turn=False,
                attack_range=self.attack_range,
                damage_per_hit=self.damage_per_hit,
            )
        else:
            # Opponent's turn: focus-fire our first piece
            if next_friends:
                next_friends[0].health -= self.damage_per_hit
                next_friends = [f for f in next_friends if f.health > 0]
            return SimulatedState(
                self.current_pos, next_friends, next_enemies,
                is_max_turn=True,
                attack_range=self.attack_range,
                damage_per_hit=self.damage_per_hit,
            )

    def evaluate_heuristic(self) -> float:
        """Heuristic score: numerical advantage dominates."""
        if not self.friends:
            return -1000.0
        if not self.enemies:
            return 1000.0
        f_hp = sum(f.health for f in self.friends)
        e_hp = sum(e.health for e in self.enemies)
        return (len(self.friends) - len(self.enemies)) * 100.0 + (f_hp - e_hp) * 2.0


# ==================== 2. Alpha-Beta leaf eval ====================

def alpha_beta_eval(
    state: SimulatedState,
    depth: int,
    alpha: float,
    beta: float,
    legal_moves: List[Point],
) -> float:
    """Alpha-beta at leaf nodes: 2-ply tactical duel evaluation."""
    if depth == 0 or not state.friends or not state.enemies:
        return state.evaluate_heuristic()

    moves = state.get_strategic_moves(legal_moves)

    if state.is_max_turn:
        max_v = -float('inf')
        for m in moves:
            next_s = state.simulate_action(m)
            v = alpha_beta_eval(next_s, depth - 1, alpha, beta, [m])
            max_v = max(max_v, v)
            alpha = max(alpha, v)
            if beta <= alpha:
                break
        return max_v
    else:
        min_v = float('inf')
        for m in moves:
            next_s = state.simulate_action(m)
            v = alpha_beta_eval(next_s, depth - 1, alpha, beta, [m])
            min_v = min(min_v, v)
            beta = min(beta, v)
            if beta <= alpha:
                break
        return min_v


# ==================== 3. MCTS tree ====================

class MCTSNode:
    """MCTS tree node with UCB1 selection."""

    def __init__(self, state: SimulatedState, parent=None, move_taken=None):
        self.state = state
        self.parent = parent
        self.move_taken = move_taken
        self.children: List[MCTSNode] = []
        self.visits = 0
        self.quality_score = 0.0

    def is_fully_expanded(self, legal_moves: List[Point]) -> bool:
        return len(self.children) == len(self.state.get_strategic_moves(legal_moves))

    def best_child(self, c_param: float = 1.414) -> "MCTSNode":
        """UCB1 selection."""
        weights = [
            (c.quality_score / (c.visits + 1e-6))
            + c_param * math.sqrt(math.log(self.visits + 1) / (c.visits + 1e-6))
            for c in self.children
        ]
        return self.children[weights.index(max(weights))]


# ==================== 4. Strategy wrapper ====================

def get_hybrid_mcts_ab_init_strategy() -> Callable[..., List[PieceArg]]:
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


def get_hybrid_mcts_ab_action_strategy() -> Callable[..., ActionSet]:
    """Hybrid MCTS (strategic) + Alpha-Beta (tactical) AI."""
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

        # Initialise MCTS root
        root_state = SimulatedState(
            current.position, friends, enemies,
            is_max_turn=True,
            attack_range=current.attack_range,
        )
        root_node = MCTSNode(root_state)

        # Core search loop: 60 iterations combining MCTS + Alpha-Beta
        for _ in range(60):
            node = root_node

            # 1. Selection
            while node.is_fully_expanded(legal_moves) and node.children:
                node = node.best_child()

            # 2. Expansion
            all_moves = node.state.get_strategic_moves(legal_moves)
            existing_moves = [c.move_taken for c in node.children]
            unexpanded = [m for m in all_moves if m not in existing_moves]

            if unexpanded:
                chosen = random.choice(unexpanded)
                next_state = node.state.simulate_action(chosen)
                new_node = MCTSNode(next_state, parent=node, move_taken=chosen)
                node.children.append(new_node)
                node = new_node

            # 3. Simulation: Alpha-Beta (depth 2) instead of random rollout
            reward = alpha_beta_eval(
                node.state, depth=2,
                alpha=-float('inf'), beta=float('inf'),
                legal_moves=legal_moves,
            )

            # 4. Backpropagation
            while node is not None:
                node.visits += 1
                node.quality_score += reward
                node = node.parent

        # Pick the most-visited child
        if root_node.children:
            best_node = max(root_node.children, key=lambda c: c.visits)
            best_grid = best_node.move_taken
        else:
            best_grid = current.position

        if best_grid is None:
            best_grid = current.position

        action.move = (best_grid.x != current.position.x
                       or best_grid.y != current.position.y)
        if action.move:
            action.move_target = best_grid

        # Attack
        final_pos = action.move_target if action.move else current.position
        target_enemy = min(enemies, key=lambda e: e.health)

        def d(p1, p2) -> float:
            return abs(p1.x - p2.x) + abs(p1.y - p2.y)

        if d(final_pos, target_enemy.position) <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target_enemy
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
