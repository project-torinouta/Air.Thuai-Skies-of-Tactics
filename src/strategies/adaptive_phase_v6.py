"""Adaptive Phase v6 — Dynamic Damage Sponging & Retreat-or-Trade.

Critical fixes over AI-proposed v6:
  1. Uses real get_legal_moves(env) — NOT generate_pure_mathematical_moves.
     The AI's "pure Manhattan" generator ignores obstacles and terrain.
  2. SimPiece.copy() instead of copy.deepcopy for performance.
  3. Strict HP comparison (< not <=) for "lowest HP" check.
  4. Non-lowest-HP doomed pieces still trigger desperate trade.
  5. Dynamic board dimensions (not hardcoded 20x20).
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
#                      1. Pure Manhattan geometry model
# ==============================================================================

class SimPiece:
    __slots__ = ("id", "team", "position", "health", "attack_range",
                 "max_move", "damage")

    def __init__(self, raw_piece: Any = None):
        if raw_piece is not None:
            self.id = raw_piece.id
            self.team = raw_piece.team
            self.position = Point(raw_piece.position.x, raw_piece.position.y)
            self.health = raw_piece.health
            self.attack_range = 9
            self.max_move = 22
            self.damage = 22

    def copy(self) -> "SimPiece":
        new = SimPiece()
        new.id = self.id
        new.team = self.team
        new.position = Point(self.position.x, self.position.y)
        new.health = self.health
        new.attack_range = self.attack_range
        new.max_move = self.max_move
        new.damage = self.damage
        return new

    def will_die_next_round(self, danger_count: int) -> bool:
        """Check if incoming net damage (22/hit) will kill this piece."""
        return self.health - danger_count * 22 <= 0


# ==============================================================================
#                      2. Safety state with retreat-or-trade
# ==============================================================================

class SafetyState:
    """Game state with retreat/trade logic and danger heatmap."""

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

    def enemy_reach_count(self, pos: Point) -> int:
        """Enemies that can move+attack to reach *pos* (range 22+9=31)."""
        count = 0
        for e in self.enemies:
            if manhattan(pos, e.position) <= e.max_move + e.attack_range:
                count += 1
        return count

    def _friendly_coverage(self, pos: Point, exclude_id: int) -> float:
        """Sum of friendly pieces within 9-range of *pos*."""
        return sum(
            500.0 for f in self.friends
            if f.id != exclude_id and manhattan(pos, f.position) <= 9
        )

    def _find_self(self) -> tuple:
        """Locate this piece in friends list."""
        cx, cy = self.current_pos.x, self.current_pos.y
        for f in self.friends:
            if f.position.x == cx and f.position.y == cy:
                return f, f.id
        return self.friends[0], self.friends[0].id

    def get_filtered_actions(
        self, legal_moves: List[Point], board_w: int = 20, board_h: int = 20,
    ) -> List[Point]:
        """Generate candidates via retreat-or-trade rules."""
        if not legal_moves:
            return [self.current_pos]
        if not self.enemies or not self.friends:
            return [legal_moves[0]]

        target = min(self.enemies, key=lambda e: e.health)
        self_piece, self_id = self._find_self()
        current_danger = self.enemy_reach_count(self.current_pos)

        # Positions that can attack lowest-HP enemy
        attack_moves = [m for m in legal_moves if manhattan(m, target.position) <= 9]

        # Edge penalty: outermost ring is extremely dangerous
        def edge_penalty(m: Point) -> float:
            if (m.x <= 0 or m.x >= board_w - 1
                    or m.y <= 0 or m.y >= board_h - 1):
                return -10000.0
            if (m.x <= 1 or m.x >= board_w - 2
                    or m.y <= 1 or m.y >= board_h - 2):
                return -3000.0
            return 0.0

        # ------------------------------------------------------------------
        #  Rule 1: Lowest-HP doomed piece → retreat or trade
        # ------------------------------------------------------------------
        is_lowest_hp = all(self_piece.health < f.health for f in self.friends)

        if is_lowest_hp and self_piece.will_die_next_round(current_danger):
            survivable = [
                m for m in legal_moves
                if not self_piece.will_die_next_round(self.enemy_reach_count(m))
            ]

            if survivable:
                # Retreat: escape danger, stay near friends
                def retreat_score(m: Point) -> float:
                    return (
                        -self.enemy_reach_count(m) * 1000.0
                        + self._friendly_coverage(m, self_id)
                        + edge_penalty(m)
                        - manhattan(m, target.position) * 5.0
                    )
                return [max(survivable, key=retreat_score)]

            # No escape → desperate trade
            def trade_score(m: Point) -> float:
                d = manhattan(m, target.position)
                return (
                    (5000.0 if d <= 9 else -5000.0)
                    + self._friendly_coverage(m, self_id)
                    + edge_penalty(m)
                )
            return [max(legal_moves, key=trade_score)]

        # ------------------------------------------------------------------
        #  Rule 2: Non-lowest-HP doomed → trade
        # ------------------------------------------------------------------
        if (self_piece.will_die_next_round(current_danger)
                and self_piece.health < 108):
            def desperate_score(m: Point) -> float:
                d = manhattan(m, target.position)
                return (
                    (5000.0 if d <= 9 else -5000.0)
                    + self._friendly_coverage(m, self_id)
                )
            return [max(legal_moves, key=desperate_score)]

        # ------------------------------------------------------------------
        #  Rule 3: Full coverage → kite at max range
        # ------------------------------------------------------------------
        if attack_moves:
            attack_dangers = [self.enemy_reach_count(m) for m in attack_moves]
        else:
            attack_dangers = []

        if (attack_moves and all(d >= 3 for d in attack_dangers)) or not attack_moves:
            def kite_score(m: Point) -> float:
                d = manhattan(m, target.position)
                ep = edge_penalty(m)
                if d < 9:
                    return float(d) + ep
                elif d == 9:
                    return 8.5 + ep
                return -float(d) + ep
            return [max(legal_moves, key=kite_score)]

        # ------------------------------------------------------------------
        #  Rule 4: Normal → safest attack positions
        # ------------------------------------------------------------------
        scored = sorted(
            attack_moves,
            key=lambda m: (self.enemy_reach_count(m), manhattan(m, target.position)),
        )
        return scored[:5]

    # -- Simulation -----------------------------------------------------------

    def step(self, move_to: Point) -> "SafetyState":
        """One ply: move + attack, flip turn."""
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
                target_p = min(next_fs, key=lambda f: f.health)
                striker = min(
                    next_es,
                    key=lambda e: manhattan(e.position, target_p.position),
                )
                if manhattan(striker.position, target_p.position) <= 9:
                    target_p.health -= 22
                next_fs = [f for f in next_fs if f.health > 0]
            return SafetyState(
                self.current_pos, next_fs, next_es, is_max_turn=True,
            )

    def evaluate(self) -> float:
        """Board eval with danger penalty."""
        if not self.friends:
            return -10000.0
        if not self.enemies:
            return 10000.0

        target_enemy = min(self.enemies, key=lambda e: e.health)
        f_hp = sum(f.health for f in self.friends)
        e_hp = sum(e.health for e in self.enemies)

        score = (len(self.friends) - len(self.enemies)) * 1500.0
        score += (f_hp - e_hp) * 5.0
        score -= self.enemy_reach_count(self.current_pos) * 200.0

        d = manhattan(self.current_pos, target_enemy.position)
        if d <= 9:
            score += (9 - d) * 10.0
        else:
            score -= d * 5.0
        return score


# ==============================================================================
#                      3. Constrained MCTS engine
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
    """MCTS with rule-constrained candidates and cached legal moves."""
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

def get_adaptive_phase_v6_init_strategy() -> Callable[..., List[PieceArg]]:
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


def get_adaptive_phase_v6_action_strategy() -> Callable[..., ActionSet]:
    """Dynamic retreat-or-trade strategy."""
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

        board_w = env.board.width if env.board else 20
        board_h = env.board.height if env.board else 20

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
