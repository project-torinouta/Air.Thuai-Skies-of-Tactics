"""Adaptive Phase v4 — Safety Heatmap & Rule-Constrained Decision Core.

Hard rules enforced:
  1. Net damage = 22/hit (45 base - 23 armour), 5 hits = dead.
  2. Danger heatmap: every position is scored by how many enemies can
     move+attack to reach it (move 22 + range 9 = 31 reach).
  3. Doomed piece: if death is inevitable, trade onto lowest-HP enemy
     and stay in friendly fire coverage.
  4. Full-coverage defence: when all attack-capable positions have
     danger == 3 (full coverage), kite at max range (dist < 9, closest
     to 9 from target).
  5. Lightweight MCTS for multi-step tiebreaking among safe candidates.
"""

import math
import random
from typing import Any, Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions
from utils import ActionSet, AttackContext, PieceArg, Point


def manhattan(a: Point, b: Point) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


# ==============================================================================
#                      1. Armour-aligned physical model
# ==============================================================================

class SimPiece:
    """Virtual piece with net damage after armour."""
    __slots__ = ("id", "team", "position", "health", "attack_range",
                 "max_move", "damage", "armour")

    def __init__(self, raw_piece: Any = None):
        if raw_piece is not None:
            self.id = raw_piece.id
            self.team = raw_piece.team
            self.position = Point(raw_piece.position.x, raw_piece.position.y)
            self.health = raw_piece.health
            self.attack_range = 9
            self.max_move = 22          # 22.5 rounded down
            self.damage = 22            # 45 base - 23 armour = 22 net
            self.armour = 23

    def copy(self) -> "SimPiece":
        new = SimPiece()
        new.id = self.id
        new.team = self.team
        new.position = Point(self.position.x, self.position.y)
        new.health = self.health
        new.attack_range = self.attack_range
        new.max_move = self.max_move
        new.damage = self.damage
        new.armour = self.armour
        return new


# ==============================================================================
#                      2. Safety heatmap state
# ==============================================================================

class SafetyState:
    """Game state with danger heatmap & rule-constrained candidate generation."""

    def __init__(
        self,
        current_pos: Point,
        friends: List[SimPiece],
        enemies: List[SimPiece],
        is_max_turn: bool,
    ):
        self.current_pos = current_pos
        self.friends = friends
        self.enemies = enemies
        self.is_max_turn = is_max_turn

    # -- Danger heatmap -------------------------------------------------------

    def enemy_reach_count(self, pos: Point) -> int:
        """Number of enemies that can move+attack to hit *pos*."""
        count = 0
        for e in self.enemies:
            if manhattan(pos, e.position) <= e.max_move + e.attack_range:
                count += 1
        return count

    def friendly_coverage(self, pos: Point, exclude_id: int) -> int:
        """Number of friendly pieces that can attack *pos*."""
        count = 0
        for f in self.friends:
            if f.id != exclude_id and manhattan(pos, f.position) <= f.attack_range:
                count += 1
        return count

    def _net_health_of(self, piece: SimPiece) -> int:
        """Current effective health in terms of hits-to-live."""
        return piece.health  # each hit does 22 net

    # -- Rule-constrained candidate generation --------------------------------

    def get_filtered_actions(self, legal_moves: List[Point]) -> List[Point]:
        """Generate 1-5 candidates via hard decision rules + safety heatmap."""
        if not legal_moves:
            return [self.current_pos]
        if not self.enemies or not self.friends:
            return [legal_moves[0]]

        target = min(self.enemies, key=lambda e: e.health)
        cx, cy = self.current_pos.x, self.current_pos.y
        tx, ty = target.position.x, target.position.y

        # Current piece in this state
        self_piece = None
        for f in self.friends:
            if (f.position.x == cx and f.position.y == cy) or True:
                self_piece = f
                break
        if self_piece is None:
            self_piece = self.friends[0]
        self_id = self_piece.id

        # All legal moves that can attack the target
        attack_moves = [
            m for m in legal_moves
            if manhattan(m, target.position) <= 9
        ]

        # If no position can attack target, just advance
        if not attack_moves:
            best_rush = min(
                legal_moves,
                key=lambda m: manhattan(m, target.position),
            )
            return [best_rush]

        # --- Rule 1: Doomed → trade mode ------------------------------------
        danger_here = self.enemy_reach_count(self.current_pos)
        if danger_here * 22 >= self_piece.health and self_piece.health < 108:
            # This piece will likely die: trade onto lowest-HP target
            # while staying in friendly fire range
            def trade_score(m: Point) -> float:
                score = 1000.0  # base: we can attack
                score += self.friendly_coverage(m, self_id) * 200.0
                # Prefer closer to target (guarantee the hit lands)
                score -= manhattan(m, target.position) * 5.0
                return score

            return [max(attack_moves, key=trade_score)]

        # --- Rule 2: Full coverage → kite at max range -----------------------
        attack_dangers = [self.enemy_reach_count(m) for m in attack_moves]
        if all(d >= 3 for d in attack_dangers):
            # Every attack position is covered by all enemies
            # Pick position with dist < 9 to target, closest to 9
            def kite_score(m: Point) -> float:
                d = manhattan(m, target.position)
                if d < 9:
                    return float(d)       # closer to 9 is better
                return -float(d)          # beyond 9 → penalised

            return [max(attack_moves, key=kite_score)]

        # --- Rule 3: Normal → pick safest positions -------------------------
        # Sort attack moves by (danger, distance to target)
        scored = sorted(
            attack_moves,
            key=lambda m: (self.enemy_reach_count(m), manhattan(m, target.position)),
        )
        return scored[:5]

    # -- Simulation -----------------------------------------------------------

    def step(self, move_to: Point) -> "SafetyState":
        """One ply: move + attack, then flip turn."""
        next_fs = [f.copy() for f in self.friends]
        next_es = [e.copy() for e in self.enemies]

        if self.is_max_turn:
            if next_es:
                target = min(next_es, key=lambda e: e.health)
                if manhattan(move_to, target.position) <= 9:
                    target.health -= 22
                next_es = [e for e in next_es if e.health > 0]
            return SafetyState(move_to, next_fs, next_es, is_max_turn=False)
        else:
            if next_es and next_fs:
                target = min(next_fs, key=lambda f: f.health)
                striker = min(
                    next_es,
                    key=lambda e: manhattan(e.position, target.position),
                )
                if manhattan(striker.position, target.position) <= 9:
                    target.health -= 22
                next_fs = [f for f in next_fs if f.health > 0]
            return SafetyState(
                self.current_pos, next_fs, next_es, is_max_turn=True,
            )

    def evaluate(self) -> float:
        """Board evaluation with danger heatmap penalty."""
        if not self.friends:
            return -10000.0
        if not self.enemies:
            return 10000.0

        target_enemy = min(self.enemies, key=lambda e: e.health)
        f_hp = sum(f.health for f in self.friends)
        e_hp = sum(e.health for e in self.enemies)

        score = (len(self.friends) - len(self.enemies)) * 500.0
        score += (f_hp - e_hp) * 3.0

        # Danger penalty for current position
        score -= self.enemy_reach_count(self.current_pos) * 200.0

        # Kiting bonus: reward being at range 9 from target
        d = manhattan(self.current_pos, target_enemy.position)
        if d <= 9:
            score += (9 - d) * 10.0  # closer to 9 = more bonus
        else:
            score -= d * 5.0  # too far = penalty

        return score


# ==============================================================================
#                      3. Lightweight rule-constrained MCTS
# ==============================================================================

class MCTSNode:
    def __init__(self, state: SafetyState, parent=None, move_taken=None):
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


def run_safety_mcts(
    legal_moves: List[Point],
    root_state: SafetyState,
    sim_count: int,
    lookahead_depth: int,
) -> Point:
    """MCTS with rule-constrained candidates and deterministic simulation."""
    root_node = MCTSNode(root_state)

    for _ in range(sim_count):
        node = root_node
        filtered = node.state.get_filtered_actions(legal_moves)

        while node.children and len(node.children) == len(filtered):
            node = node.ucb_select()
            filtered = node.state.get_filtered_actions(legal_moves)

        all_moves = filtered
        expanded = [c.move_taken for c in node.children]
        unexpanded = [m for m in all_moves if m not in expanded]

        if unexpanded:
            m = random.choice(unexpanded)
            new_node = MCTSNode(node.state.step(m), parent=node, move_taken=m)
            node.children.append(new_node)
            node = new_node

        sim_s = node.state
        for _ in range(lookahead_depth):
            if not sim_s.friends or not sim_s.enemies:
                break
            fs = sim_s.get_filtered_actions(legal_moves)
            if not fs:
                break
            best_m = min(
                fs,
                key=lambda m: manhattan(
                    m, min(sim_s.enemies, key=lambda e: e.health).position,
                ),
            )
            sim_s = sim_s.step(best_m)

        score = sim_s.evaluate()

        while node is not None:
            node.visits += 1
            node.total_value += score
            node = node.parent

    if root_node.children:
        return max(root_node.children, key=lambda c: c.visits).move_taken
    return root_state.current_pos


# ==============================================================================
#                        4. Strategy entry points
# ==============================================================================

def get_adaptive_phase_v4_init_strategy() -> Callable[..., List[PieceArg]]:
    """STR 29 / DEX 1 / INT 0, bow + heavy armour."""
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


def get_adaptive_phase_v4_action_strategy() -> Callable[..., ActionSet]:
    """Safety-heatmap constrained MCTS strategy."""
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

        initial_state = SafetyState(
            current.position, friends, enemies, is_max_turn=True,
        )

        total_units = len(friends) + len(enemies)
        if total_units == 6:
            sim_count = 200
            lookahead_depth = 1
        elif total_units >= 4:
            sim_count = 150
            lookahead_depth = 2
        else:
            sim_count = 100
            lookahead_depth = 5

        best_grid = run_safety_mcts(
            legal_moves, initial_state,
            sim_count=sim_count, lookahead_depth=lookahead_depth,
        )

        action.move = (best_grid.x != current.position.x
                       or best_grid.y != current.position.y)
        if action.move:
            action.move_target = best_grid

        final_pos = action.move_target if action.move else current.position
        global_target = min(raw_enemies, key=lambda e: e.health)

        if manhattan(final_pos, global_target.position) <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = global_target
        else:
            nearest = min(
                raw_enemies,
                key=lambda e: manhattan(final_pos, e.position),
            )
            if manhattan(final_pos, nearest.position) <= current.attack_range:
                action.attack = True
                action.attack_context = AttackContext()
                action.attack_context.attacker = current
                action.attack_context.target = nearest
            else:
                action.attack = False

        action.spell = False
        return action

    return strategy
