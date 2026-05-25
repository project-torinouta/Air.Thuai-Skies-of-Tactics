"""Adaptive Phase v3 — Smooth MCTS Depth Evolution (Pure Physical Stream).

Fixes & Enhancements applied:
  1. Abolished separate Alpha-Beta engine to eliminate behavioral schism.
  2. Implemented unified MCTS framework with smooth local depth evolution.
  3. Aligned precision physical damage values (45 per hit) into simulation.
  4. Preserved pure Sniper initialization strategy (STR 29 / DEX 1 / INT 0).
"""

import math
import random
from typing import Any, Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions
from utils import ActionSet, AttackContext, PieceArg, Point


# ==============================================================================
#                      1. Lightweight physical simulation state
# ==============================================================================

class SimPiece:
    """Virtual piece model aligned with real physical stats."""
    __slots__ = ("id", "team", "position", "health", "attack_range", "damage")

    def __init__(self, raw_piece: Any = None):
        if raw_piece is not None:
            self.id = raw_piece.id
            self.team = raw_piece.team
            self.position = Point(raw_piece.position.x, raw_piece.position.y)
            self.health = raw_piece.health
            self.attack_range = raw_piece.attack_range
            self.damage = 45

    def copy(self) -> "SimPiece":
        new = SimPiece()
        new.id = self.id
        new.team = self.team
        new.position = Point(self.position.x, self.position.y)
        new.health = self.health
        new.attack_range = self.attack_range
        new.damage = self.damage
        return new


class UnifiedTacticalState:
    """Single-tree in-memory world: move, damage, turn flip."""

    def __init__(
        self,
        current_pos: Point,
        friends: List[SimPiece],
        enemies: List[SimPiece],
        is_max_turn: bool,
        attack_range: int,
    ):
        self.current_pos = current_pos
        self.friends = friends
        self.enemies = enemies
        self.is_max_turn = is_max_turn
        self.attack_range = attack_range

    def get_filtered_actions(self, legal_moves: List[Point]) -> List[Point]:
        """Strategic move pruning via 5 tactical intent filters."""
        if not legal_moves:
            return [self.current_pos]
        if not self.enemies or not self.friends:
            return [legal_moves[0]]

        target_enemy = min(self.enemies, key=lambda e: e.health)
        strategic = []
        tx, ty = target_enemy.position.x, target_enemy.position.y
        cx, cy = self.current_pos.x, self.current_pos.y

        # 1. Rush: nearest to target
        best_rush = min(
            legal_moves,
            key=lambda m: abs(m.x - tx) + abs(m.y - ty),
        )
        strategic.append(best_rush)

        # 2. Hold position
        if any(m.x == cx and m.y == cy for m in legal_moves):
            strategic.append(self.current_pos)

        # 3. Rally toward nearest teammate (other than self)
        other_fs = [f for f in self.friends if f.position.x != cx or f.position.y != cy]
        if other_fs:
            nearest_f = min(
                other_fs,
                key=lambda f: abs(cx - f.position.x) + abs(cy - f.position.y),
            )
            best_rally = min(
                legal_moves,
                key=lambda m: abs(m.x - nearest_f.position.x)
                              + abs(m.y - nearest_f.position.y),
            )
            if best_rally not in strategic:
                strategic.append(best_rally)

        # 4. Flank: perpendicular to rush direction
        dx, dy = tx - cx, ty - cy
        if abs(dx) > 0 or abs(dy) > 0:
            flank_candidates = [
                m for m in legal_moves
                if (abs(m.x - cx) > 0 and abs(m.y - cy) > 0
                    and (m.x - cx) * dx + (m.y - cy) * dy >= 0)
            ]
            if flank_candidates:
                best_flank = min(
                    flank_candidates,
                    key=lambda m: abs(m.x - tx) + abs(m.y - ty),
                )
                if best_flank not in strategic:
                    strategic.append(best_flank)

        # 5. Centroid (defensive formation)
        f_sum_x = sum(f.position.x for f in self.friends)
        f_sum_y = sum(f.position.y for f in self.friends)
        fn = len(self.friends)
        centroid_x, centroid_y = f_sum_x / fn, f_sum_y / fn
        best_center = min(
            legal_moves, key=lambda m: abs(m.x - centroid_x) + abs(m.y - centroid_y),
        )
        if best_center not in strategic:
            strategic.append(best_center)

        return strategic

    def step(self, move_to: Point) -> "UnifiedTacticalState":
        """Advance one ply: move + attack, flip turn."""
        next_fs = [f.copy() for f in self.friends]
        next_es = [e.copy() for e in self.enemies]

        if self.is_max_turn:
            if next_es:
                target = min(next_es, key=lambda e: e.health)
                dist = (abs(move_to.x - target.position.x)
                        + abs(move_to.y - target.position.y))
                if dist <= self.attack_range:
                    target.health -= 45
                next_es = [e for e in next_es if e.health > 0]

            return UnifiedTacticalState(
                move_to, next_fs, next_es, is_max_turn=False,
                attack_range=self.attack_range,
            )
        else:
            if next_es and next_fs:
                target = min(next_fs, key=lambda f: f.health)
                striker = min(
                    next_es,
                    key=lambda e: abs(e.position.x - target.position.x)
                                  + abs(e.position.y - target.position.y),
                )
                dist = (abs(striker.position.x - target.position.x)
                        + abs(striker.position.y - target.position.y))
                if dist <= striker.attack_range:
                    target.health -= 45
                next_fs = [f for f in next_fs if f.health > 0]

            return UnifiedTacticalState(
                self.current_pos, next_fs, next_es, is_max_turn=True,
                attack_range=self.attack_range,
            )

    def evaluate(self) -> float:
        """Static board evaluation: numerical + HP + formation cohesion."""
        if not self.friends:
            return -5000.0
        if not self.enemies:
            return 5000.0

        f_hp = sum(f.health for f in self.friends)
        e_hp = sum(e.health for e in self.enemies)

        score = (len(self.friends) - len(self.enemies)) * 350.0
        score += (f_hp - e_hp) * 2.5

        target_enemy = min(self.enemies, key=lambda e: e.health)
        avg_dist = sum(
            abs(f.position.x - target_enemy.position.x)
            + abs(f.position.y - target_enemy.position.y)
            for f in self.friends
        ) / len(self.friends)
        score -= avg_dist * 10.0

        return score


# ==============================================================================
#                  2. Unified adaptive-depth MCTS engine
# ==============================================================================

class SmoothMCTSNode:
    def __init__(self, state: UnifiedTacticalState, parent=None, move_taken=None):
        self.state = state
        self.parent = parent
        self.move_taken = move_taken
        self.children: List[SmoothMCTSNode] = []
        self.visits = 0
        self.total_value = 0.0

    def ucb_select(self, c_param: float = 1.414) -> "SmoothMCTSNode":
        weights = [
            (c.total_value / (c.visits + 1e-6))
            + c_param * math.sqrt(math.log(self.visits + 1) / (c.visits + 1e-6))
            for c in self.children
        ]
        return self.children[weights.index(max(weights))]


def run_adaptive_mcts_engine(
    legal_moves: List[Point],
    root_state: UnifiedTacticalState,
    sim_count: int,
    lookahead_depth: int,
) -> Point:
    """Unified MCTS with deterministic evaluation (no random rollouts)."""
    root_node = SmoothMCTSNode(root_state)

    for _ in range(sim_count):
        node = root_node
        filtered = node.state.get_filtered_actions(legal_moves)

        # Selection
        while node.children and len(node.children) == len(filtered):
            node = node.ucb_select()
            filtered = node.state.get_filtered_actions(legal_moves)

        # Expansion
        all_moves = filtered
        expanded = [c.move_taken for c in node.children]
        unexpanded = [m for m in all_moves if m not in expanded]

        if unexpanded:
            m = random.choice(unexpanded)
            new_node = SmoothMCTSNode(node.state.step(m), parent=node, move_taken=m)
            node.children.append(new_node)
            node = new_node

        # Simulation: deterministic best-move chain (no random rollouts)
        sim_s = node.state
        for _ in range(lookahead_depth):
            if not sim_s.friends or not sim_s.enemies:
                break
            fs = sim_s.get_filtered_actions(legal_moves)
            if not fs:
                break
            best_m = min(
                fs,
                key=lambda m: (
                    abs(m.x - min(sim_s.enemies, key=lambda e: e.health).position.x)
                    + abs(m.y - min(sim_s.enemies, key=lambda e: e.health).position.y)
                ),
            )
            sim_s = sim_s.step(best_m)

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
#                        3. Strategy entry points
# ==============================================================================

def get_adaptive_phase_v3_init_strategy() -> Callable[..., List[PieceArg]]:
    """STR 29 / DEX 1 / INT 0 sniper init."""
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


def get_adaptive_phase_v3_action_strategy() -> Callable[..., ActionSet]:
    """Single-tree adaptive-depth MCTS strategy."""
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current = env.current_piece
        if current is None or not current.is_alive:
            return action

        raw_enemies = [
            p for p in env.action_queue
            if p.team != current.team and p.is_alive
        ]
        raw_friends = [
            p for p in env.action_queue
            if p.team == current.team and p.is_alive
        ]
        if not raw_enemies:
            return action

        enemies = [SimPiece(e) for e in raw_enemies]
        friends = [SimPiece(f) for f in raw_friends]

        from strategy_utils import get_legal_moves
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            legal_moves = [current.position]

        initial_state = UnifiedTacticalState(
            current.position, friends, enemies, is_max_turn=True,
            attack_range=current.attack_range,
        )

        f_cnt, e_cnt = len(friends), len(enemies)
        total_units = f_cnt + e_cnt

        if total_units == 6:
            sim_count = 200
            lookahead_depth = 1
        elif total_units >= 4:
            sim_count = 150
            lookahead_depth = 2
        else:
            sim_count = 100
            lookahead_depth = 5

        best_grid = run_adaptive_mcts_engine(
            legal_moves, initial_state,
            sim_count=sim_count, lookahead_depth=lookahead_depth,
        )

        action.move = (best_grid.x != current.position.x
                       or best_grid.y != current.position.y)
        if action.move:
            action.move_target = best_grid

        final_pos = action.move_target if action.move else current.position
        global_target = min(raw_enemies, key=lambda e: e.health)

        def d(p1, p2) -> float:
            return abs(p1.x - p2.x) + abs(p1.y - p2.y)

        if d(final_pos, global_target.position) <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = global_target
        else:
            nearest = min(raw_enemies, key=lambda e: d(final_pos, e.position))
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
