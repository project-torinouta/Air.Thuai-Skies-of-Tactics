"""Alpha-Beta Tactical — minimax search with strategic move pruning.

Combines alpha-beta pruning with domain-specific heuristics:
- Strategic move pruning: only 3 candidate actions per node
- Simplified combat simulation for deep search
- HP + numerical advantage evaluation
"""

import copy
from typing import Callable, List, Optional, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


# ==================== 1. Evaluation function ====================

def evaluate_state(friends: list, enemies: list) -> float:
    """Score a simulated board state. Higher = better for the evaluating side."""
    if not friends:
        return -999999.0
    if not enemies:
        return 999999.0

    HP_WEIGHT = 2.0
    NUM_WEIGHT = 50.0

    friend_hp = sum(f.health for f in friends)
    enemy_hp = sum(e.health for e in enemies)

    score = (len(friends) - len(enemies)) * NUM_WEIGHT + (friend_hp - enemy_hp) * HP_WEIGHT
    return score


# ==================== 2. Alpha-Beta search ====================

def minimax_alpha_beta(
    depth: int,
    is_max_turn: bool,
    current_pos: Point,
    friends: list,
    enemies: list,
    legal_moves: List[Point],
    alpha: float,
    beta: float,
    attack_range: int = 9,
    damage_per_hit: int = 45,
) -> Tuple[float, Optional[Point]]:
    """Alpha-beta pruning search with strategic move sampling.

    Only 3 high-value moves are evaluated per node (rush target, hold, rally).
    Returns (best_score, best_move_position).
    """
    if depth == 0 or not friends or not enemies:
        return evaluate_state(friends, enemies), current_pos

    target_enemy = min(enemies, key=lambda e: e.health)

    # Strategic move pruning: only 3 candidate moves
    strategic_moves = []

    # Move 1: rush toward the lowest-HP target
    best_rush = min(
        legal_moves,
        key=lambda m: abs(m.x - target_enemy.position.x)
                      + abs(m.y - target_enemy.position.y),
    )
    strategic_moves.append(best_rush)

    # Move 2: stay put (defensive hold)
    if any(m.x == current_pos.x and m.y == current_pos.y for m in legal_moves):
        strategic_moves.append(current_pos)

    # Move 3: rally toward the nearest friendly piece
    friends_other = [
        f for f in friends
        if f.position.x != current_pos.x or f.position.y != current_pos.y
    ]
    if friends_other:
        nearest_friend = min(
            friends_other,
            key=lambda f: abs(current_pos.x - f.position.x)
                          + abs(current_pos.y - f.position.y),
        )
        best_rally = min(
            legal_moves,
            key=lambda m: abs(m.x - nearest_friend.position.x)
                          + abs(m.y - nearest_friend.position.y),
        )
        strategic_moves.append(best_rally)

    # Deduplicate
    seen = set()
    unique_moves = []
    for m in strategic_moves:
        k = (m.x, m.y)
        if k not in seen:
            seen.add(k)
            unique_moves.append(m)

    best_move = current_pos

    if is_max_turn:
        # Our turn — maximise
        max_eval = -float('inf')
        for move in unique_moves:
            simulated_enemies = copy.deepcopy(enemies)
            for e in simulated_enemies:
                if e.id == target_enemy.id:
                    dist = abs(move.x - e.position.x) + abs(move.y - e.position.y)
                    if dist <= attack_range:
                        e.health -= damage_per_hit
            simulated_enemies = [e for e in simulated_enemies if e.health > 0]

            evaluation, _ = minimax_alpha_beta(
                depth - 1, False, move, friends,
                simulated_enemies, [move], alpha, beta,
                attack_range, damage_per_hit,
            )

            if evaluation > max_eval:
                max_eval = evaluation
                best_move = move

            alpha = max(alpha, evaluation)
            if beta <= alpha:
                break

        return max_eval, best_move

    else:
        # Opponent's turn — minimise
        min_eval = float('inf')
        for move in unique_moves:
            simulated_friends = copy.deepcopy(friends)
            if simulated_friends:
                simulated_friends[0].health -= damage_per_hit
            simulated_friends = [f for f in simulated_friends if f.health > 0]

            evaluation, _ = minimax_alpha_beta(
                depth - 1, True, move, simulated_friends,
                enemies, [move], alpha, beta,
                attack_range, damage_per_hit,
            )

            if evaluation < min_eval:
                min_eval = evaluation
                best_move = move

            beta = min(beta, evaluation)
            if beta <= alpha:
                break

        return min_eval, best_move


# ==================== 3. Strategy wrapper ====================

def get_alpha_beta_tactical_init_strategy() -> Callable[..., List[PieceArg]]:
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


def get_alpha_beta_tactical_action_strategy(
    search_depth: int = 3,
) -> Callable[..., ActionSet]:
    """Alpha-beta tactical action strategy with strategic move pruning."""
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

        # Search: find the best position 3 plies ahead
        _, best_grid = minimax_alpha_beta(
            depth=search_depth,
            is_max_turn=True,
            current_pos=current.position,
            friends=friends,
            enemies=enemies,
            legal_moves=legal_moves,
            alpha=-float('inf'),
            beta=float('inf'),
            attack_range=current.attack_range,
        )

        if best_grid is None:
            best_grid = current.position

        action.move = (best_grid.x != current.position.x
                       or best_grid.y != current.position.y)
        if action.move:
            action.move_target = best_grid

        # Attack: focus lowest-HP enemy if in range
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
