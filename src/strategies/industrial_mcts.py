"""Industrial MCTS — adaptive-depth tree search with static evaluation.

Key features:
  - UnifiedTacticalState with dynamic candidate filtering
  - No random rollouts: deterministic multi-dimensional static evaluation
  - Adaptive search depth based on remaining unit count
  - Continuous simulation allocation: 3v3→80 sims, mid→50, endgame→30
"""

import copy
import math
import random
from typing import Callable, List, Optional, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


# ==================== State representation ====================

class UnifiedTacticalState:
    """Lightweight game state with tactical candidate filtering."""

    def __init__(self, current_piece, friends, enemies):
        self.current = current_piece
        self.friends = copy.deepcopy(friends)
        self.enemies = copy.deepcopy(enemies)

    def get_tactical_candidates(self, legal_moves: List[Point]) -> List[Point]:
        """Filter moves by tactical intent: safe poke, body block, fallback."""
        if not legal_moves:
            return [self.current.position]
        if not self.enemies:
            return [legal_moves[0]]

        candidates = []
        global_target = min(self.enemies, key=lambda e: e.health)

        for m in legal_moves:
            dist = abs(m.x - global_target.position.x) + abs(m.y - global_target.position.y)

            # Intent 1: safe poke — in range of the focus target
            if dist <= self.current.attack_range:
                candidates.append(m)

            # Intent 2: body block — adjacent to any enemy
            for e in self.enemies:
                if abs(m.x - e.position.x) + abs(m.y - e.position.y) == 1:
                    candidates.append(m)

        # Fallback: current position + rush toward target
        if not candidates:
            best_rush = min(
                legal_moves,
                key=lambda m: abs(m.x - global_target.position.x)
                              + abs(m.y - global_target.position.y),
            )
            candidates.extend([self.current.position, best_rush])

        return list(set(candidates))

    def step(self, move_to: Point) -> "UnifiedTacticalState":
        """Advance one ply: move + focus-fire attack."""
        next_fs = copy.deepcopy(self.friends)
        next_es = copy.deepcopy(self.enemies)

        if next_es:
            target = min(next_es, key=lambda e: e.health)
            dist = abs(move_to.x - target.position.x) + abs(move_to.y - target.position.y)
            if dist <= 9:  # attack range
                target.health -= 45
            next_es = [e for e in next_es if e.health > 0]

        # Opponent counter: focus our first piece
        if next_fs:
            next_fs[0].health -= 45
            next_fs = [f for f in next_fs if f.health > 0]

        atk_range = getattr(self.current, 'attack_range', 9)

        class MockPiece:
            def __init__(self, pos, ar):
                self.position = pos
                self.attack_range = ar

        mock = MockPiece(move_to, atk_range)
        return UnifiedTacticalState(mock, next_fs, next_es)

    def evaluate_static_board(self) -> float:
        """Deterministic multi-dimensional board evaluation."""
        if not self.friends:
            return -5000.0
        if not self.enemies:
            return 5000.0

        f_hp = sum(f.health for f in self.friends)
        e_hp = sum(e.health for e in self.enemies)

        score = (len(self.friends) - len(self.enemies)) * 300.0 + (f_hp - e_hp) * 2.0

        target = min(self.enemies, key=lambda e: e.health)
        avg_dist = sum(
            abs(f.position.x - target.position.x) + abs(f.position.y - target.position.y)
            for f in self.friends
        ) / max(len(self.friends), 1)
        score -= avg_dist * 10.0

        return score


# ==================== MCTS node ====================

class MCTSNode:
    def __init__(self, state: UnifiedTacticalState, parent=None, move_taken=None):
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


def _run_mcts(
    root_state: UnifiedTacticalState,
    legal_moves: List[Point],
    sim_count: int,
    search_depth: int,
) -> Optional[Point]:
    """MCTS with depth-limited static evaluation (no random rollouts)."""
    root_node = MCTSNode(root_state)

    for _ in range(sim_count):
        node = root_node

        # Selection
        while (
            node.children
            and len(node.children) == len(node.state.get_tactical_candidates(legal_moves))
        ):
            node = node.ucb_select()

        # Expansion
        all_moves = node.state.get_tactical_candidates(legal_moves)
        expanded = [c.move_taken for c in node.children]
        unexpanded = [m for m in all_moves if m not in expanded]

        if unexpanded:
            m = random.choice(unexpanded)
            new_node = MCTSNode(node.state.step(m), parent=node, move_taken=m)
            node.children.append(new_node)
            node = new_node

        # Simulation: depth-limited static evaluation
        sim_s = node.state
        for _ in range(search_depth):
            if not sim_s.friends or not sim_s.enemies:
                break
            ms = sim_s.get_tactical_candidates(legal_moves)
            sim_s = sim_s.step(random.choice(ms))
        score = sim_s.evaluate_static_board()

        # Backpropagation
        while node is not None:
            node.visits += 1
            node.total_value += score
            node = node.parent

    if root_node.children:
        return max(root_node.children, key=lambda c: c.visits).move_taken
    return None


# ==================== Strategy wrapper ====================

def get_industrial_mcts_init_strategy() -> Callable[..., List[PieceArg]]:
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


def get_industrial_mcts_action_strategy() -> Callable[..., ActionSet]:
    """Industrial MCTS: adaptive-depth tree search + static evaluation."""
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current = env.current_piece
        if current is None or not current.is_alive:
            return action

        enemies = [p for p in env.action_queue if p.team != current.team and p.is_alive]
        friends = [p for p in env.action_queue if p.team == current.team and p.is_alive]
        if not enemies:
            return action

        from strategy_utils import get_legal_moves
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            legal_moves = [current.position]

        # Adaptive parameters based on total units remaining
        total_units = len(friends) + len(enemies)
        if total_units == 6:
            sim_count, search_depth = 80, 1
        elif total_units >= 4:
            sim_count, search_depth = 50, 2
        else:
            sim_count, search_depth = 30, 4

        root_state = UnifiedTacticalState(current, friends, enemies)
        best_grid = _run_mcts(root_state, legal_moves, sim_count, search_depth)
        if best_grid is None:
            best_grid = current.position

        action.move = (best_grid.x != current.position.x or best_grid.y != current.position.y)
        if action.move:
            action.move_target = best_grid

        final_pos = action.move_target if action.move else current.position
        global_target = min(enemies, key=lambda e: e.health)

        def d(p1, p2):
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

        action.spell = False
        return action

    return strategy
