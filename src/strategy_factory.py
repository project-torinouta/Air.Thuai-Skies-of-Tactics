# Copyright 2026 saiblo platform <https://saiblo.net>
#
# This SDK copy is distributed from https://api.saiblo.net/api/games/56/download/,
# All rights reserved by saiblo platform. All I modified is translating the
# comment and document string from Chinese to English

"""Built-in AI strategy implementations.

This module provides pre-defined initialisation and action strategies
that contestants can use directly or reference when implementing their
own. It also includes search-based strategies (Alpha-Beta, MCTS).
"""

import math
import random
from collections.abc import Callable
from typing import Optional

from env import Environment, InitGameMessage
from strategy_utils import (
    fork_environment,
    get_attackable_targets,
    get_legal_moves,
    get_state_score,
    step_with_action,
)
from utils import (
    ActionSet,
    Area,
    AttackContext,
    DamageType,
    PieceArg,
    Point,
    Spell,
    SpellContext,
    SpellEffectType,
)

# Set to False to suppress all [MCTS] debug output
MCTS_VERBOSE: bool = False


def _allocate_init_positions(
    board: "Board",
    player_id: int,
    piece_cnt: int,
    preferred_order: list[tuple[int, int]],
) -> list[Point]:
    """Pick distinct walkable cells on the player's side of the board.

    Tries the preferred positions first, then falls back to scanning all
    cells in scan-line order.

    :param board: The game board.
    :type board: Board
    :param player_id: The player ID (1 or 2).
    :type player_id: int
    :param piece_cnt: Number of pieces to place.
    :type piece_cnt: int
    :param preferred_order: List of (x, y) tuples to try first.
    :type preferred_order: list[tuple[int, int]]
    :returns: A list of placed positions.
    :rtype: list[Point]
    :raises RuntimeError: If no free cell exists on the player's side.
    """
    occupied: set[tuple[int, int]] = set()
    out: list[Point] = []
    bdr = board.boarder

    def cell_ok(x: int, y: int) -> bool:
        if (x, y) in occupied:
            return False
        if not board.is_within_bounds(Point(x, y)):
            return False
        if board.grid[x][y].state != 1:
            return False
        if player_id == 1:
            return y < bdr
        return y > bdr

    for _ in range(piece_cnt):
        pos = None
        for x, y in preferred_order:
            if cell_ok(x, y):
                pos = Point(x, y)
                break
        if pos is None:
            for y in range(board.height):
                for x in range(board.width):
                    if cell_ok(x, y):
                        pos = Point(x, y)
                        break
                if pos is not None:
                    break
        if pos is None:
            raise RuntimeError("No free cell in player's half for placement.")
        out.append(pos)
        occupied.add((pos.x, pos.y))
    return out


class StrategyFactory:
    """Factory providing pre-built initialisation and action strategies.

    Each static method returns a callable strategy function that can be
    plugged into the Environment's input method system.
    """

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_distance(p1: Point, p2: Point) -> float:
        """Calculate the Manhattan distance between two points.

        :param p1: The first point.
        :type p1: Point
        :param p2: The second point.
        :type p2: Point
        :returns: The Manhattan distance ``|x1-x2| + |y1-y2|``.
        :rtype: float
        """
        return float(abs(p1.x - p2.x) + abs(p1.y - p2.y))

    # ------------------------------------------------------------------
    # Initialisation strategies
    # ------------------------------------------------------------------

    @staticmethod
    def get_aggressive_init_strategy() -> Callable[..., list[PieceArg]]:
        """Return an aggressive initialisation strategy.

        Prioritises high strength and frontline positioning. Each piece
        is configured with strength=20, dexterity=8, intelligence=2,
        shortsword + heavy armour.

        :returns: A callable that takes an ``InitGameMessage`` and returns
            a list of ``PieceArg``.
        :rtype: Callable
        """
        def strategy(init_message: InitGameMessage) -> list[PieceArg]:
            board = init_message.board
            pid = init_message.id
            if pid == 1:
                order = [
                    (x, y)
                    for y in range(5, 0, -1)
                    for x in range(2, board.width - 2)
                ]
            else:
                order = [
                    (x, y)
                    for y in range(board.height - 6, board.height)
                    for x in range(board.width - 3, 2, -1)
                ]
            positions = _allocate_init_positions(board, pid, init_message.piece_cnt, order)
            piece_args: list[PieceArg] = []
            for pos in positions:
                arg = PieceArg()
                arg.strength = 20
                arg.dexterity = 8
                arg.intelligence = 2
                arg.equip = Point(2, 3)
                arg.pos = pos
                piece_args.append(arg)
            return piece_args

        return strategy

    @staticmethod
    def get_defensive_init_strategy() -> Callable[..., list[PieceArg]]:
        """Return a defensive initialisation strategy.

        Prioritises dexterity and intelligence with rearline positioning.
        Each piece is configured with strength=5, dexterity=15,
        intelligence=10, bow + light armour.

        :returns: A callable that takes an ``InitGameMessage`` and returns
            a list of ``PieceArg``.
        :rtype: Callable
        """
        def strategy(init_message: InitGameMessage) -> list[PieceArg]:
            board = init_message.board
            pid = init_message.id
            if pid == 1:
                order = [
                    (x, y)
                    for y in range(3, board.boarder)
                    for x in range(3, board.width - 3)
                ]
            else:
                order = [
                    (x, y)
                    for y in range(board.height - 1, board.boarder, -1)
                    for x in range(board.width - 4, 3, -1)
                ]
            positions = _allocate_init_positions(board, pid, init_message.piece_cnt, order)
            piece_args: list[PieceArg] = []
            for pos in positions:
                arg = PieceArg()
                arg.strength = 5
                arg.dexterity = 15
                arg.intelligence = 10
                arg.equip = Point(3, 1)
                arg.pos = pos
                piece_args.append(arg)
            return piece_args

        return strategy

    @staticmethod
    def get_random_init_strategy() -> Callable[..., list[PieceArg]]:
        """Return a random initialisation strategy.

        Randomly selects between aggressive and defensive strategies.

        :returns: A callable initialisation strategy.
        :rtype: Callable
        """
        strategies = [
            StrategyFactory.get_aggressive_init_strategy(),
            StrategyFactory.get_defensive_init_strategy(),
        ]
        return random.choice(strategies)

    # ------------------------------------------------------------------
    # Action strategies
    # ------------------------------------------------------------------

    @staticmethod
    def get_aggressive_action_strategy() -> Callable[..., ActionSet]:
        """Return an aggressive action strategy.

        The piece moves toward the nearest enemy and attacks when in range.
        No spells are used.

        :returns: A callable action strategy.
        :rtype: Callable
        """
        def strategy(env: Environment) -> ActionSet:
            action = ActionSet()
            current_piece = env.current_piece

            target_enemy = None
            nearest_distance = float("inf")

            for piece in env.action_queue:
                if piece.team != current_piece.team and piece.is_alive:
                    distance = StrategyFactory.calculate_distance(
                        Point(current_piece.position.x, current_piece.position.y),
                        Point(piece.position.x, piece.position.y),
                    )
                    if distance < nearest_distance:
                        nearest_distance = distance
                        target_enemy = piece

            if target_enemy is None:
                action.move = False
                action.attack = False
                action.spell = False
                return action

            legal_moves = get_legal_moves(env)
            if legal_moves:
                best_move = None
                min_distance = float("inf")
                for move in legal_moves:
                    distance = StrategyFactory.calculate_distance(move, target_enemy.position)
                    if distance < min_distance:
                        min_distance = distance
                        best_move = move

                if best_move:
                    action.move = True
                    action.move_target = best_move
                else:
                    action.move = False
            else:
                action.move = False

            if nearest_distance <= current_piece.attack_range:
                action.attack = True
                action.attack_context = AttackContext()
                action.attack_context.attacker = current_piece
                action.attack_context.target = target_enemy
            else:
                action.attack = False

            action.spell = False
            return action

        return strategy

    @staticmethod
    def get_defensive_action_strategy() -> Callable[..., ActionSet]:
        """Return a defensive action strategy.

        The piece maintains distance from enemies (targeting ~70% of
        attack range) and uses ranged attacks. No spells are used.

        :returns: A callable action strategy.
        :rtype: Callable
        """
        def strategy(env: Environment) -> ActionSet:
            action = ActionSet()
            current_piece = env.current_piece

            target_enemy = None
            nearest_distance = float("inf")

            for piece in env.action_queue:
                if piece.team != current_piece.team and piece.is_alive:
                    distance = StrategyFactory.calculate_distance(
                        Point(current_piece.position.x, current_piece.position.y),
                        Point(piece.position.x, piece.position.y),
                    )
                    if distance < nearest_distance:
                        nearest_distance = distance
                        target_enemy = piece

            if target_enemy is None:
                action.move = False
                action.attack = False
                action.spell = False
                return action

            legal_moves = get_legal_moves(env)
            if legal_moves:
                ideal_distance = current_piece.attack_range * 0.7
                best_move = None
                min_distance_diff = float("inf")

                for move in legal_moves:
                    distance_to_enemy = StrategyFactory.calculate_distance(
                        move, target_enemy.position
                    )
                    distance_diff = abs(distance_to_enemy - ideal_distance)

                    if nearest_distance < ideal_distance - 2:
                        if distance_to_enemy > nearest_distance:
                            min_distance_diff = distance_diff
                            best_move = move
                    elif nearest_distance > ideal_distance + 2:
                        if distance_to_enemy < nearest_distance:
                            min_distance_diff = distance_diff
                            best_move = move
                    else:
                        min_distance_diff = distance_diff
                        best_move = move

                if best_move:
                    action.move = True
                    action.move_target = best_move
                else:
                    action.move = False
            else:
                action.move = False

            if nearest_distance <= current_piece.attack_range:
                action.attack = True
                action.attack_context = AttackContext()
                action.attack_context.attacker = current_piece
                action.attack_context.target = target_enemy
            else:
                action.attack = False

            action.spell = False
            return action

        return strategy

    @staticmethod
    def get_random_action_strategy() -> Callable[..., ActionSet]:
        """Return a random action strategy.

        Randomly selects between aggressive and defensive strategies.

        :returns: A callable action strategy.
        :rtype: Callable
        """
        strategies = [
            StrategyFactory.get_aggressive_action_strategy(),
            StrategyFactory.get_defensive_action_strategy(),
        ]
        return random.choice(strategies)

    @staticmethod
    def get_alpha_beta_action_strategy(
        max_depth: int = 3,
    ) -> Callable[..., ActionSet]:
        """Return an Alpha-Beta pruning search strategy.

        Searches the game tree up to a given depth to find the best action.

        :param max_depth: The maximum search depth. Defaults to 3.
        :type max_depth: int
        :returns: A callable action strategy.
        :rtype: Callable
        """
        def alpha_beta(
            env: Environment,
            depth: int,
            alpha: float,
            beta: float,
            maximizing: bool,
        ) -> tuple[float, ActionSet | None]:
            if depth == 0 or env.is_game_over:
                return get_state_score(env), None

            current_piece = env.current_piece

            if maximizing:
                max_eval = float("-inf")
                best_action = None

                legal_moves = get_legal_moves(env)
                attackable_targets = get_attackable_targets(env)
                spells = env.get_available_spells(current_piece) if depth > 0 else []

                for move in [None] + legal_moves:
                    if move is not None and current_piece.action_points <= 0:
                        continue
                    for target in [None] + attackable_targets:
                        if target is not None and current_piece.action_points <= 0:
                            continue
                        for spell in [None] + spells:
                            if spell is not None and (
                                current_piece.action_points <= 0
                                or current_piece.spell_slots <= 0
                            ):
                                continue

                            action = ActionSet()
                            next_env = fork_environment(env)
                            remaining = current_piece.action_points

                            if move is not None and remaining > 0:
                                action.move = True
                                action.move_target = move
                                remaining -= 1
                            else:
                                action.move = False

                            if target is not None and remaining > 0:
                                action.attack = True
                                action.attack_context = AttackContext()
                                action.attack_context.attacker = current_piece
                                action.attack_context.target = target
                                remaining -= 1
                            else:
                                action.attack = False

                            if spell is not None and remaining > 0 and current_piece.spell_slots > 0:
                                action.spell = True
                                action.spell_context = SpellContext()
                                action.spell_context.caster = current_piece
                                action.spell_context.target = (
                                    target if target else current_piece
                                )
                                action.spell_context.spell = spell
                                action.spell_context.target_area = Area(
                                    current_piece.position.x,
                                    current_piece.position.y,
                                    2,
                                )
                            else:
                                action.spell = False

                            next_env.execute_player_action(action)
                            eval_score, _ = alpha_beta(
                                next_env, depth - 1, alpha, beta, False
                            )
                            if eval_score > max_eval:
                                max_eval = eval_score
                                best_action = action

                            alpha = max(alpha, eval_score)
                            if beta <= alpha:
                                break
                        if beta <= alpha:
                            break
                    if beta <= alpha:
                        break

                return max_eval, best_action
            else:
                min_eval = float("inf")
                best_action = None

                legal_moves = get_legal_moves(env)
                attackable_targets = get_attackable_targets(env)

                base_spells: list[Spell] = []
                if current_piece.spell_slots > 0:
                    base_spells.extend([
                        Spell(0, "Damage", "", SpellEffectType.DAMAGE, DamageType.PHYSICAL, 10, 0, 0, 0, 0),
                        Spell(0, "Heal", "", SpellEffectType.HEAL, DamageType.NONE, 8, 0, 0, 0, 0),
                        Spell(0, "Buff", "", SpellEffectType.BUFF, DamageType.NONE, 5, 0, 0, 0, 0),
                        Spell(0, "Debuff", "", SpellEffectType.DEBUFF, DamageType.NONE, 3, 0, 0, 0, 0),
                    ])

                for move in [None] + legal_moves:
                    if move is not None and current_piece.action_points <= 0:
                        continue
                    for target in [None] + attackable_targets:
                        if target is not None and current_piece.action_points <= 0:
                            continue
                        for spell in [None] + base_spells:
                            if spell is not None and (
                                current_piece.action_points <= 0
                                or current_piece.spell_slots <= 0
                            ):
                                continue

                            action = ActionSet()
                            next_env = fork_environment(env)
                            remaining = current_piece.action_points

                            if move is not None and remaining > 0:
                                action.move = True
                                action.move_target = move
                                remaining -= 1
                            else:
                                action.move = False

                            if target is not None and remaining > 0:
                                action.attack = True
                                action.attack_context = AttackContext()
                                action.attack_context.attacker = current_piece
                                action.attack_context.target = target
                                remaining -= 1
                            else:
                                action.attack = False

                            if spell is not None and remaining > 0 and current_piece.spell_slots > 0:
                                spell_targets = env.get_spell_targets(spell, current_piece)
                                if not spell_targets and not spell.is_area_effect:
                                    continue

                                action.spell = True
                                action.spell_context = SpellContext()
                                action.spell_context.caster = current_piece
                                action.spell_context.spell = spell

                                if spell.is_area_effect:
                                    action.spell_context.target = None
                                    action.spell_context.target_area = Area(
                                        current_piece.position.x,
                                        current_piece.position.y,
                                        spell.area_radius,
                                    )
                                else:
                                    best_target = None
                                    if spell.effect_type in [
                                        SpellEffectType.DAMAGE,
                                        SpellEffectType.DEBUFF,
                                    ]:
                                        best_target = min(
                                            spell_targets, key=lambda p: p.health
                                        )
                                    elif spell.effect_type in [
                                        SpellEffectType.HEAL,
                                        SpellEffectType.BUFF,
                                    ]:
                                        best_target = min(
                                            spell_targets,
                                            key=lambda p: p.health / p.max_health,
                                        )
                                    elif spell.effect_type == SpellEffectType.MOVE:
                                        best_target = current_piece

                                    action.spell_context.target = best_target
                                    action.spell_context.target_area = Area(
                                        best_target.position.x,
                                        best_target.position.y,
                                        0,
                                    )
                            else:
                                action.spell = False

                            next_env.execute_player_action(action)
                            eval_score, _ = alpha_beta(
                                next_env, depth - 1, alpha, beta, True
                            )
                            if eval_score < min_eval:
                                min_eval = eval_score
                                best_action = action

                            beta = min(beta, eval_score)
                            if beta <= alpha:
                                break
                        if beta <= alpha:
                            break
                    if beta <= alpha:
                        break

                return min_eval, best_action

        def strategy(env: Environment) -> ActionSet:
            _, best_action = alpha_beta(
                env, max_depth, float("-inf"), float("inf"), True
            )
            return best_action if best_action is not None else ActionSet()

        return strategy

    @staticmethod
    def get_mcts_action_strategy(
        simulation_count: int = 10,
    ) -> Callable[..., ActionSet]:
        """Return a Monte Carlo Tree Search (MCTS) action strategy.

        Builds a search tree by simulating random playouts and selects
        the most-visited child action.

        :param simulation_count: Number of simulations per decision point.
            Defaults to 10.
        :type simulation_count: int
        :returns: A callable action strategy.
        :rtype: Callable
        """
        class MCTSNode:
            def __init__(
                self,
                env: Environment,
                parent: Optional["MCTSNode"] = None,
                action: ActionSet | None = None,
            ) -> None:
                self.env = env
                self.parent = parent
                self.action = action
                self.children: list[MCTSNode] = []
                self.visits: int = 0
                self.value: float = 0.0

            def expand(self) -> None:
                """Expand the node by generating all possible child actions."""
                current_piece = self.env.current_piece
                legal_moves = get_legal_moves(self.env)
                attackable_targets = get_attackable_targets(self.env)
                spells = self.env.get_available_spells(current_piece)

                for move in [None] + legal_moves:
                    if move is not None and current_piece.action_points <= 0:
                        if MCTS_VERBOSE:
                            print("[MCTS] Skip move: insufficient action points.")
                        continue

                    for target in [None] + attackable_targets:
                        if target is not None and current_piece.action_points <= 0:
                            if MCTS_VERBOSE:
                                print("[MCTS] Skip attack: insufficient action points.")
                            continue

                        for spell in [None] + spells:
                            if spell is not None and (
                                current_piece.action_points <= 0
                                or current_piece.spell_slots <= 0
                            ):
                                if MCTS_VERBOSE:
                                    print("[MCTS] Skip spell: insufficient resources.")
                                continue

                            action = ActionSet()
                            next_env = fork_environment(self.env)
                            remaining = current_piece.action_points
                            has_action = False

                            if move is not None and remaining > 0:
                                action.move = True
                                action.move_target = move
                                remaining -= 1
                                has_action = True
                            else:
                                action.move = False

                            if target is not None and remaining > 0:
                                action.attack = True
                                action.attack_context = AttackContext()
                                action.attack_context.attacker = current_piece
                                action.attack_context.target = target
                                remaining -= 1
                                has_action = True
                            else:
                                action.attack = False

                            if (
                                spell is not None
                                and remaining > 0
                                and current_piece.spell_slots > 0
                            ):
                                spell_targets = self.env.get_spell_targets(
                                    spell, current_piece
                                )
                                if not spell_targets and not spell.is_area_effect:
                                    if MCTS_VERBOSE:
                                        print("[MCTS] Skip spell: no valid target.")
                                    continue

                                has_action = True
                                action.spell = True
                                action.spell_context = SpellContext()
                                action.spell_context.caster = current_piece
                                action.spell_context.spell = spell

                                if spell.is_area_effect:
                                    action.spell_context.target = None
                                    action.spell_context.target_area = Area(
                                        current_piece.position.x,
                                        current_piece.position.y,
                                        spell.area_radius,
                                    )
                                else:
                                    best_target = None
                                    if spell.effect_type in [
                                        SpellEffectType.DAMAGE,
                                        SpellEffectType.DEBUFF,
                                    ]:
                                        best_target = min(
                                            spell_targets, key=lambda p: p.health
                                        )
                                    elif spell.effect_type in [
                                        SpellEffectType.HEAL,
                                        SpellEffectType.BUFF,
                                    ]:
                                        best_target = min(
                                            spell_targets,
                                            key=lambda p: p.health / p.max_health,
                                        )
                                    elif spell.effect_type == SpellEffectType.MOVE:
                                        best_target = current_piece

                                    action.spell_context.target = best_target
                                    action.spell_context.target_area = Area(
                                        best_target.position.x,
                                        best_target.position.y,
                                        spell.area_radius,
                                    )
                            else:
                                action.spell = False

                            if current_piece.action_points > 0 and not has_action:
                                if MCTS_VERBOSE:
                                    print(
                                        "[MCTS] Skip: action points but no action."
                                    )
                                continue

                            step_with_action(next_env, action)
                            child = MCTSNode(next_env, self, action)
                            self.children.append(child)

            def select(self) -> "MCTSNode":
                """Select the most promising child using UCB1.

                :returns: The child node with the highest UCB1 score.
                :rtype: MCTSNode
                """
                if not self.children:
                    return self

                def ucb1(node: MCTSNode) -> float:
                    if node.visits == 0:
                        return float("inf")
                    return node.value / node.visits + math.sqrt(
                        2 * math.log(self.visits) / node.visits
                    )

                return max(self.children, key=ucb1)

            def simulate(self) -> float:
                """Run a random playout from this node.

                Simulates until game over or a maximum number of steps,
                then returns a score based on the winner or health ratio.

                :returns: 1.0 for current-team win, -1.0 for loss, 0.0
                    for draw, -0.5 for no-action penalty.
                :rtype: float
                """
                sim_env = fork_environment(self.env)
                max_steps = 50
                initial_team = sim_env.current_piece.team

                while not sim_env.is_game_over and max_steps > 0:
                    legal_moves = get_legal_moves(sim_env)
                    attackable_targets = get_attackable_targets(sim_env)

                    action = ActionSet()

                    if legal_moves and random.random() < 0.7:
                        action.move = True
                        action.move_target = random.choice(legal_moves)
                    else:
                        action.move = False

                    if attackable_targets and random.random() < 0.8:
                        action.attack = True
                        action.attack_context = AttackContext()
                        action.attack_context.attacker = sim_env.current_piece
                        action.attack_context.target = random.choice(
                            attackable_targets
                        )
                    else:
                        action.attack = False

                    action.spell = False
                    step_with_action(sim_env, action)
                    max_steps -= 1

                if sim_env.is_game_over:
                    t1 = any(p.is_alive for p in sim_env.player1.pieces)
                    t2 = any(p.is_alive for p in sim_env.player2.pieces)
                    if t1 and not t2:
                        return 1.0 if initial_team == 1 else -1.0
                    if t2 and not t1:
                        return 1.0 if initial_team == 2 else -1.0
                    return 0.0

                if not (action.move or action.attack or action.spell):
                    return -0.5

                t1_health = sum(
                    p.health for p in sim_env.player1.pieces if p.is_alive
                )
                t2_health = sum(
                    p.health for p in sim_env.player2.pieces if p.is_alive
                )

                if t1_health > t2_health:
                    return 1.0 if initial_team == 1 else -1.0
                if t2_health > t1_health:
                    return 1.0 if initial_team == 2 else -1.0
                return 0.0

            def backpropagate(self, value: float) -> None:
                """Back-propagate the simulation result up the tree.

                Values are negated at each level for adversarial search.

                :param value: The result to propagate.
                :type value: float
                """
                node = self
                while node is not None:
                    node.visits += 1
                    node.value += value
                    node = node.parent
                    value = -value

        def strategy(env: Environment) -> ActionSet:
            root = MCTSNode(env)

            for _ in range(simulation_count):
                node = root

                while node.children:
                    node = node.select()

                if node.visits > 0:
                    node.expand()
                    if node.children:
                        node = random.choice(node.children)

                value = node.simulate()
                node.backpropagate(value)

            if not root.children:
                if MCTS_VERBOSE:
                    print("\n[MCTS] Warning: no child nodes generated.")
                    print(
                        f"[MCTS] Current piece: "
                        f"ID={env.current_piece.id if env.current_piece else None}"
                    )
                    print(
                        f"[MCTS] Legal moves: {len(get_legal_moves(env))}"
                    )
                    print(
                        f"[MCTS] Attackable targets: "
                        f"{len(get_attackable_targets(env))}"
                    )
                    print(
                        f"[MCTS] Available spells: "
                        f"{len(env.get_available_spells())}"
                    )
                    print(
                        f"[MCTS] Action points: "
                        f"{env.current_piece.action_points if env.current_piece else 0}"
                    )
                    print(
                        f"[MCTS] Spell slots: "
                        f"{env.current_piece.spell_slots if env.current_piece else 0}"
                    )
                return ActionSet()

            if MCTS_VERBOSE:
                print(
                    f"\n[MCTS] Found {len(root.children)} possible actions."
                )
            best_child = max(root.children, key=lambda c: c.visits)
            if MCTS_VERBOSE:
                print(
                    f"[MCTS] Best action: visits={best_child.visits}, "
                    f"score={best_child.value}"
                )
            return best_child.action

        return strategy
