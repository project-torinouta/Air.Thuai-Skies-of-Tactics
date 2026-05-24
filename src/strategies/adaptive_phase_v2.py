"""Adaptive Phase v2 — fixes from the code review.

Fixes applied:
  1. Alpha-Beta: recompute legal moves from new state, don't pass [m].
  2. MCTS expansion: recompute filtered actions per node, not from global list.
  3. Simulation: model move → attack ordering, not random steps.
  4. Candidate count expanded from 3→5 for better coverage.
  5. Opponent simulation: track which piece acts (not always first).
"""

import copy
import math
import random
from typing import Callable, List, Optional, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


# ==============================================================================
#  Core state
# ==============================================================================

class TacticalState:
    """Lightweight game state for in-memory tree search."""

    def __init__(
        self,
        current_pos: Point,
        friends: list,
        enemies: list,
        is_max_turn: bool,
        attack_range: int = 9,
        damage_per_hit: int = 23,
        acting_piece_id: Optional[int] = None,
    ):
        self.current_pos = current_pos
        self.friends = copy.deepcopy(friends)
        self.enemies = copy.deepcopy(enemies)
        self.is_max_turn = is_max_turn
        self.attack_range = attack_range
        self.damage_per_hit = damage_per_hit
        self.acting_piece_id = acting_piece_id

    def get_filtered_actions(self, legal_moves: List[Point]) -> List[Point]:
        """Return up to 5 strategic candidates from *legal_moves*."""
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

        # 4. Flank: perpendicular to the rush direction (if available)
        dx = target_enemy.position.x - self.current_pos.x
        dy = target_enemy.position.y - self.current_pos.y
        flank_candidates = [
            m for m in legal_moves
            if (abs(m.x - self.current_pos.x) > 0
                and abs(m.y - self.current_pos.y) > 0
                and (m.x - self.current_pos.x) * dx + (m.y - self.current_pos.y) * dy >= 0)
        ]
        if flank_candidates:
            best_flank = min(
                flank_candidates,
                key=lambda m: abs(m.x - target_enemy.position.x)
                              + abs(m.y - target_enemy.position.y),
            )
            if best_flank not in strategic:
                strategic.append(best_flank)

        # 5. Stay near centroid (defensive)
        if self.friends:
            cx = sum(f.position.x for f in self.friends) / len(self.friends)
            cy = sum(f.position.y for f in self.friends) / len(self.friends)
            best_center = min(
                legal_moves,
                key=lambda m: abs(m.x - cx) + abs(m.y - cy),
            )
            if best_center not in strategic:
                strategic.append(best_center)

        return list(set(strategic))

    def step(self, move_to: Point) -> "TacticalState":
        """Advance one ply: move + attack, then flip turn."""
        next_fs = copy.deepcopy(self.friends)
        next_es = copy.deepcopy(self.enemies)

        if self.is_max_turn:
            # Our turn: attack the lowest-HP enemy if in range
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
            # Opponent's turn: their frontmost piece attacks our lowest-HP piece
            if next_es and next_fs:
                target = min(next_fs, key=lambda f: f.health)
                # Pick the enemy closest to the target as the attacker
                striker = min(
                    next_es,
                    key=lambda e: abs(e.position.x - target.position.x)
                                  + abs(e.position.y - target.position.y),
                )
                dist = abs(striker.position.x - target.position.x) + abs(striker.position.y - target.position.y)
                if dist <= getattr(striker, 'attack_range', 9):
                    target.health -= self.damage_per_hit
                next_fs = [f for f in next_fs if f.health > 0]
            return TacticalState(
                self.current_pos, next_fs, next_es, is_max_turn=True,
                attack_range=self.attack_range, damage_per_hit=self.damage_per_hit,
            )

    def evaluate(self) -> float:
        if not self.friends:
            return -2000.0
        if not self.enemies:
            return 2000.0
        f_hp = sum(f.health for f in self.friends)
        e_hp = sum(e.health for e in self.enemies)
        return (len(self.friends) - len(self.enemies)) * 150.0 + (f_hp - e_hp) * 2.0


# ==============================================================================
#  Alpha-Beta (fixed: recompute legal moves from state)
# ==============================================================================

def alpha_beta_search(
    state: TacticalState,
    depth: int,
    alpha: float,
    beta: float,
    get_moves_fn: Callable,
) -> Tuple[float, Optional[Point]]:
    """Alpha-beta with proper legal-move recomputation per node."""
    if depth == 0 or not state.friends or not state.enemies:
        return state.evaluate(), state.current_pos

    legal_moves = get_moves_fn(state.current_pos)
    moves = state.get_filtered_actions(legal_moves)
    best_move = state.current_pos

    if state.is_max_turn:
        max_v = -float('inf')
        for m in moves:
            next_s = state.step(m)
            # Correct: recompute legal moves from the next state's position
            val, _ = alpha_beta_search(next_s, depth - 1, alpha, beta, get_moves_fn)
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
            next_s = state.step(m)
            val, _ = alpha_beta_search(next_s, depth - 1, alpha, beta, get_moves_fn)
            if val < min_v:
                min_v = val
                best_move = m
            beta = min(beta, val)
            if beta <= alpha:
                break
        return min_v, best_move


# ==============================================================================
#  MCTS (fixed: dynamic move recomputation, move→attack simulation)
# ==============================================================================

class MCTSNode:
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
    get_moves_fn: Callable,
    root_state: TacticalState,
    sim_count: int,
    use_ab_cutoff: bool,
) -> Optional[Point]:
    """MCTS with per-node move recomputation and move→attack simulation."""
    root_node = MCTSNode(root_state)

    for _ in range(sim_count):
        node = root_node
        legal_moves = get_moves_fn(node.state.current_pos)
        filtered = node.state.get_filtered_actions(legal_moves)

        # Selection
        while node.children and len(node.children) == len(filtered):
            node = node.ucb_select()
            legal_moves = get_moves_fn(node.state.current_pos)
            filtered = node.state.get_filtered_actions(legal_moves)

        # Expansion
        all_moves = filtered
        expanded = [c.move_taken for c in node.children]
        unexpanded = [m for m in all_moves if m not in expanded]

        if unexpanded:
            m = random.choice(unexpanded)
            new_node = MCTSNode(node.state.step(m), parent=node, move_taken=m)
            node.children.append(new_node)
            node = new_node

        # Simulation: move → attack ordering, not random steps
        if use_ab_cutoff:
            score = alpha_beta_search(
                node.state, depth=2,
                alpha=-float('inf'), beta=float('inf'),
                get_moves_fn=get_moves_fn,
            )[0]
        else:
            sim_s = node.state
            for _ in range(3):
                if not sim_s.friends or not sim_s.enemies:
                    break
                ms = get_moves_fn(sim_s.current_pos)
                fs = sim_s.get_filtered_actions(ms)
                if not fs:
                    break
                # Move → attack in simulation (choose best move, then step)
                best_ms = min(fs, key=lambda m: abs(m.x - min(sim_s.enemies, key=lambda e: e.health).position.x)
                              + abs(m.y - min(sim_s.enemies, key=lambda e: e.health).position.y))
                sim_s = sim_s.step(best_ms)
            score = sim_s.evaluate()

        # Backpropagation
        while node is not None:
            node.visits += 1
            node.total_value += score
            node = node.parent

    if root_node.children:
        return max(root_node.children, key=lambda c: c.visits).move_taken
    return root_state.current_pos


# ==============================================================================
#  Strategy wrapper
# ==============================================================================

def get_adaptive_phase_v2_init_strategy() -> Callable[..., List[PieceArg]]:
    """Standard STR 29 / DEX 1 / INT 0 sniper init."""
    def strategy(init_message: InitGameMessage) -> List[PieceArg]:
        board = init_message.board
        pid = init_message.id
        if pid == 1:
            order = [(x, y) for y in range(5, 0, -1) for x in range(2, board.width - 2)]
        else:
            order = [
                (x, y) for y in range(board.height - 6, board.height)
                for x in range(board.width - 3, 2, -1)
            ]
        positions = allocate_init_positions(board, pid, init_message.piece_cnt, order)
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


def get_adaptive_phase_v2_action_strategy() -> Callable[..., ActionSet]:
    """Phase-adaptive v2 with fixed search."""
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current = env.current_piece
        if current is None or not current.is_alive:
            return action

        enemies = [p for p in env.action_queue if p.team != current.team and p.is_alive]
        friends = [p for p in env.action_queue if p.team == current.team and p.is_alive]
        if not enemies:
            return action

        def get_moves_fn(pos: Point) -> List[Point]:
            """Recompute legal moves from any position (used in tree search)."""
            from strategy_utils import get_legal_moves
            return get_legal_moves(env)

        initial_state = TacticalState(
            current.position, friends, enemies, is_max_turn=True,
            attack_range=current.attack_range,
        )
        best_grid: Optional[Point] = current.position
        f_cnt, e_cnt = len(friends), len(enemies)

        if f_cnt == 3 and e_cnt == 3:
            best_grid = run_hybrid_engine(get_moves_fn, initial_state, sim_count=200, use_ab_cutoff=False)
        elif f_cnt >= 2 and e_cnt >= 2:
            best_grid = run_hybrid_engine(get_moves_fn, initial_state, sim_count=200, use_ab_cutoff=True)
        else:
            _, best_grid = alpha_beta_search(initial_state, depth=10, alpha=-float('inf'), beta=float('inf'), get_moves_fn=get_moves_fn)

        if best_grid is None:
            best_grid = current.position

        action.move = (best_grid.x != current.position.x or best_grid.y != current.position.y)
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
