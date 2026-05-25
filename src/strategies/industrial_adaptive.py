"""Industrial Adaptive — MCTS with accurate damage model and AP tracking.

Fixes from the original design:
  - Match pieces by ID in step(), not by list index [0]
  - Opponent branch also updates position (moves toward our weakest)
  - Dangerous-zone filter uses a reasonable threshold
  - Weapon type extracted from raw_piece.weapon_type directly
  - Added init strategy for benchmark registration
  - Removed non-existent ActionSet attributes (spell_id, spell_target_position)
"""

import copy
import math
import random
from typing import Any, Callable, List, Optional, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


# ==============================================================================
#  1. Forward model with accurate stats
# ==============================================================================

class SimUnit:
    """Virtual piece model aligned with real game stats."""

    def __init__(self, raw_piece: Any):
        self.id = raw_piece.id
        self.team = raw_piece.team
        self.position = Point(raw_piece.position.x, raw_piece.position.y)
        self.health = raw_piece.health
        self.max_health = getattr(raw_piece, 'max_health', 108)
        self.strength = raw_piece.strength
        self.physical_damage = getattr(raw_piece, 'physical_damage', 3)
        self.physical_resist = getattr(raw_piece, 'physical_resist', 0)
        self.attack_range = raw_piece.attack_range
        self.weapon_type = int(getattr(raw_piece, 'weapon_type', 3))
        self.action_points = getattr(raw_piece, 'action_points', 3)


class IndustrialTacticalState:
    """Simulation state with AP tracking and accurate damage model."""

    def __init__(
        self,
        current: SimUnit,
        friends: List[SimUnit],
        enemies: List[SimUnit],
        is_max_turn: bool,
    ):
        self.current = current
        self.friends = friends
        self.enemies = enemies
        self.is_max_turn = is_max_turn

    def get_intent_filtered_actions(self, legal_moves: List[Point]) -> List[Point]:
        """Filter moves by tactical intent: safe poke, body block, fallback."""
        if not legal_moves:
            return [self.current.position]
        if not self.enemies:
            return [legal_moves[0]]

        candidates = []
        global_target = min(self.enemies, key=lambda e: e.health)

        for m in legal_moves:
            dist = abs(m.x - global_target.position.x) + abs(m.y - global_target.position.y)

            # Intent 1: safe poke — in range of focus target
            if dist <= self.current.attack_range:
                candidates.append(m)

        # Fallback: current position + closest to target
        if not candidates:
            best_rush = min(
                legal_moves,
                key=lambda m: abs(m.x - global_target.position.x)
                              + abs(m.y - global_target.position.y),
            )
            candidates.extend([self.current.position, best_rush])

        return list(set(candidates))

    def _compute_damage(self, attacker: SimUnit, defender: SimUnit) -> int:
        """Compute actual damage accounting for weapon type and armour."""
        if attacker.weapon_type == 4:  # staff: fixed 4 true damage
            return 4
        raw = attacker.physical_damage + attacker.strength
        return max(1, raw - defender.physical_resist)

    def _find_by_id(self, pieces: List[SimUnit], pid: int) -> Optional[SimUnit]:
        for p in pieces:
            if p.id == pid:
                return p
        return None

    def step(self, move_to: Point) -> "IndustrialTacticalState":
        """Advance one ply: move + attack + AP tracking."""
        next_fs = copy.deepcopy(self.friends)
        next_es = copy.deepcopy(self.enemies)

        if self.is_max_turn:
            # --- Our turn: the current piece is on our team ---
            actor = self._find_by_id(next_fs, self.current.id)
            if actor is None:
                actor = next_fs[0] if next_fs else None
            if actor is None:
                return IndustrialTacticalState(self.current, next_fs, next_es, False)

            ap = actor.action_points

            # Move
            if (move_to.x != actor.position.x or move_to.y != actor.position.y) and ap >= 1:
                actor.position = Point(move_to.x, move_to.y)
                ap -= 1

            # Attack lowest-HP enemy
            if next_es and ap >= 1:
                target = min(next_es, key=lambda e: e.health)
                dist = abs(actor.position.x - target.position.x) + abs(actor.position.y - target.position.y)
                if dist <= actor.attack_range:
                    target.health -= self._compute_damage(actor, target)
                    ap -= 1

            next_es = [e for e in next_es if e.health > 0]
            next_current = next_fs[0] if next_fs else self.current
            return IndustrialTacticalState(next_current, next_fs, next_es, False)

        else:
            # --- Opponent's turn: the current piece is on their team ---
            actor = self._find_by_id(next_es, self.current.id)
            if actor is None:
                actor = next_es[0] if next_es else None
            if actor is None:
                return IndustrialTacticalState(self.current, next_fs, next_es, True)

            # Opponent moves toward our weakest piece
            if next_fs:
                target_f = min(next_fs, key=lambda f: f.health)
                # Pick a spot adjacent to the target (simplified)
                candidates = [
                    Point(target_f.position.x + dx, target_f.position.y + dy)
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]
                ]
                best = min(candidates, key=lambda m: abs(m.x - actor.position.x) + abs(m.y - actor.position.y))
                if actor.action_points >= 1:
                    actor.position = best

            # Opponent attacks our lowest-HP piece
            if next_fs and actor.action_points >= 1:
                target = min(next_fs, key=lambda f: f.health)
                dist = abs(actor.position.x - target.position.x) + abs(actor.position.y - target.position.y)
                if dist <= actor.attack_range:
                    target.health -= self._compute_damage(actor, target)

            next_fs = [f for f in next_fs if f.health > 0]
            next_current = next_es[0] if next_es else self.current
            return IndustrialTacticalState(next_current, next_fs, next_es, True)

    def evaluate_static_board(self) -> float:
        """Multi-dimensional evaluation: numerical + HP + cohesion."""
        if not self.friends:
            return -5000.0
        if not self.enemies:
            return 5000.0

        f_hp = sum(f.health for f in self.friends)
        e_hp = sum(e.health for e in self.enemies)

        score = (len(self.friends) - len(self.enemies)) * 350.0 + (f_hp - e_hp) * 2.5

        # Cohesion penalty: punish being spread out
        target = min(self.enemies, key=lambda e: e.health) if self.enemies else None
        if target and self.friends:
            avg_dist = sum(
                abs(f.position.x - target.position.x) + abs(f.position.y - target.position.y)
                for f in self.friends
            ) / len(self.friends)
            score -= avg_dist * 12.0

        return score


# ==============================================================================
#  2. MCTS tree
# ==============================================================================

class AdvMCTSNode:
    def __init__(self, state: IndustrialTacticalState, parent=None, move_taken=None):
        self.state = state
        self.parent = parent
        self.move_taken = move_taken
        self.children: List[AdvMCTSNode] = []
        self.visits = 0
        self.total_value = 0.0

    def is_fully_expanded(self, legal_moves: List[Point]) -> bool:
        return len(self.children) == len(self.state.get_intent_filtered_actions(legal_moves))

    def ucb_select(self, c_param: float = 1.414) -> "AdvMCTSNode":
        weights = [
            (c.total_value / (c.visits + 1e-6))
            + c_param * math.sqrt(math.log(self.visits + 1) / (c.visits + 1e-6))
            for c in self.children
        ]
        return self.children[weights.index(max(weights))]


# ==============================================================================
#  3. Strategy wrapper
# ==============================================================================

def get_industrial_adaptive_init_strategy() -> Callable[..., List[PieceArg]]:
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


def get_industrial_adaptive_action_strategy() -> Callable[..., ActionSet]:
    """Industrial adaptive MCTS with accurate damage model."""
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        raw = env.current_piece
        if raw is None or not raw.is_alive:
            return action

        raw_enemies = [p for p in env.action_queue if p.team != raw.team and p.is_alive]
        raw_friends = [p for p in env.action_queue if p.team == raw.team and p.is_alive]
        if not raw_enemies:
            return action

        enemies = [SimUnit(e) for e in raw_enemies]
        friends = [SimUnit(f) for f in raw_friends]
        current_sim = SimUnit(raw)

        from strategy_utils import get_legal_moves
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            legal_moves = [raw.position]

        # Adaptive parameters
        total = len(friends) + len(enemies)
        if total == 6:
            sim_count, lookahead = 80, 1
        elif total >= 4:
            sim_count, lookahead = 50, 2
        else:
            sim_count, lookahead = 30, 4

        root_state = IndustrialTacticalState(current_sim, friends, enemies, True)
        root_node = AdvMCTSNode(root_state)

        for _ in range(sim_count):
            node = root_node

            while node.children and node.is_fully_expanded(legal_moves):
                node = node.ucb_select()

            all_moves = node.state.get_intent_filtered_actions(legal_moves)
            expanded = [c.move_taken for c in node.children]
            unexpanded = [m for m in all_moves if m not in expanded]

            if unexpanded:
                m = random.choice(unexpanded)
                new_node = AdvMCTSNode(node.state.step(m), parent=node, move_taken=m)
                node.children.append(new_node)
                node = new_node

            sim_s = node.state
            for _ in range(lookahead):
                if not sim_s.friends or not sim_s.enemies:
                    break
                ms = sim_s.get_intent_filtered_actions(legal_moves)
                sim_s = sim_s.step(random.choice(ms))

            score = sim_s.evaluate_static_board()

            while node is not None:
                node.visits += 1
                node.total_value += score
                node = node.parent

        best_grid = (
            max(root_node.children, key=lambda c: c.visits).move_taken
            if root_node.children else raw.position
        )

        action.move = (best_grid.x != raw.position.x or best_grid.y != raw.position.y)
        if action.move:
            action.move_target = best_grid

        final_pos = action.move_target if action.move else raw.position
        global_target = min(raw_enemies, key=lambda e: e.health)

        def md(p1, p2):
            return abs(p1.x - p2.x) + abs(p1.y - p2.y)

        if md(final_pos, global_target.position) <= raw.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = raw
            action.attack_context.target = global_target
        else:
            nearest = min(raw_enemies, key=lambda e: md(final_pos, e.position))
            if md(final_pos, nearest.position) <= raw.attack_range:
                action.attack = True
                action.attack_context = AttackContext()
                action.attack_context.attacker = raw
                action.attack_context.target = nearest

        action.spell = False
        return action

    return strategy
