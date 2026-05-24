"""Adaptive Phase v51 — Fixed kiting: retreat when can't attack.

Bug fix over v5:
  Kiting picker penalised d > 9 even when no attack positions exist.
  Fixed: when attack_moves is empty, reward distance (retreat to safety).
  When all_danger_3 but can attack, keep edge-kiting behaviour.
"""

import math
import random
from typing import Any, Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions
from utils import ActionSet, AttackContext, PieceArg, Point


# ==============================================================================
#            1. Discrete physical panel with armour mechanics
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
        """Check if piece will die from incoming net damage (22/hit)."""
        return self.health - danger_count * 22 <= 0


# ==============================================================================
#            2. Absolute safety mask & rule-constrained state
# ==============================================================================

def manhattan(a: Point, b: Point) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


class UltimateTacticalState:
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

    def evaluate_grid_danger(self, target_grid: Point) -> int:
        """Count enemies that can move+attack to hit *target_grid*."""
        count = 0
        for e in self.enemies:
            if manhattan(target_grid, e.position) <= e.max_move + e.attack_range:
                count += 1
        return count

    def get_filtered_actions(self, legal_moves: List[Point]) -> List[Point]:
        """Hard-rule decision filter: trade / kite (with retreat) / safest."""
        if not legal_moves:
            return [self.current_pos]
        if not self.enemies:
            return [legal_moves[0]]
        if not self.friends:
            return [legal_moves[0]]

        lowest_hp_enemy = min(self.enemies, key=lambda e: e.health)
        cx, cy = self.current_pos.x, self.current_pos.y

        # Locate this piece within friends
        current_sim_self = self.friends[0]
        for f in self.friends:
            if f.position.x == cx and f.position.y == cy:
                current_sim_self = f
                break

        current_danger = self.evaluate_grid_danger(self.current_pos)

        # ------------------------------------------------------------------
        # Strategy 1: Doomed → trade mode
        # ------------------------------------------------------------------
        if current_sim_self.will_die_next_round(current_danger):
            def undead_picker(m: Point) -> float:
                d = manhattan(m, lowest_hp_enemy.position)
                can_hit = 5000.0 if d <= 9 else -5000.0

                friendly_cov = 0
                for f in self.friends:
                    if f.id != current_sim_self.id:
                        if manhattan(m, f.position) <= 9:
                            friendly_cov += 500.0

                move_cost = -(abs(m.x - cx) + abs(m.y - cy))
                return can_hit + friendly_cov + move_cost

            return [max(legal_moves, key=undead_picker)]

        # ------------------------------------------------------------------
        # Strategy 2: Kiting / retreat / edge-poking
        # ------------------------------------------------------------------
        attack_moves = [
            m for m in legal_moves
            if manhattan(m, lowest_hp_enemy.position) <= 9
        ]

        all_danger_3 = False
        if attack_moves:
            all_danger_3 = all(
                self.evaluate_grid_danger(m) >= 3 for m in attack_moves
            )

        if all_danger_3 or not attack_moves:
            def kiting_picker(m: Point) -> float:
                d = manhattan(m, lowest_hp_enemy.position)
                if not attack_moves:
                    # Can't hit the target this turn → retreat to safety.
                    # Distance from target = good (survival).
                    return float(d)
                # Can attack but all positions are maximally dangerous.
                # Kite at edge of range: d < 9, closest to 9.
                if d < 9:
                    return float(d)
                elif d == 9:
                    return 8.5
                return -float(d)

            return [max(legal_moves, key=kiting_picker)]

        # Normal: sort attack positions by danger
        attack_moves.sort(key=lambda m: self.evaluate_grid_danger(m))
        return attack_moves[:5]

    def step(self, move_to: Point) -> "UltimateTacticalState":
        """Discrete one-ply simulation: move → attack, flip turn."""
        next_fs = [f.copy() for f in self.friends]
        next_es = [e.copy() for e in self.enemies]

        if self.is_max_turn:
            if next_es:
                target = min(next_es, key=lambda e: e.health)
                if manhattan(move_to, target.position) <= 9:
                    target.health -= 22
                next_es = [e for e in next_es if e.health > 0]
            return UltimateTacticalState(
                move_to, next_fs, next_es, is_max_turn=False,
            )
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
            return UltimateTacticalState(
                self.current_pos, next_fs, next_es, is_max_turn=True,
            )

    def evaluate(self) -> float:
        """Static node evaluation with grid-danger penalty."""
        if not self.friends:
            return -10000.0
        if not self.enemies:
            return 10000.0

        f_hp = sum(f.health for f in self.friends)
        e_hp = sum(e.health for e in self.enemies)

        score = (len(self.friends) - len(self.enemies)) * 1500.0
        score += (f_hp - e_hp) * 5.0
        score -= self.evaluate_grid_danger(self.current_pos) * 200.0

        return score


# ==============================================================================
#                    3. Lightweight rule-constrained MCTS
# ==============================================================================

class MCTSNode:
    def __init__(self, state: UltimateTacticalState, parent=None, move_taken=None):
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


def run_ultimate_mcts(
    legal_moves: List[Point],
    root_state: UltimateTacticalState,
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
#                    4. Strategy entry points
# ==============================================================================

def get_adaptive_phase_v51_init_strategy() -> Callable[..., List[PieceArg]]:
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


def get_adaptive_phase_v51_action_strategy() -> Callable[..., ActionSet]:
    """Safety-hardened decision core with fixed kiting logic."""
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

        initial_state = UltimateTacticalState(
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

        best_grid = run_ultimate_mcts(
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
