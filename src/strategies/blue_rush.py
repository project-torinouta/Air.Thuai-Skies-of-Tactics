"""Blue Rush — aggressive advance + focus fire, adapted from Blue replay.

Strategy pattern:
  - Standard STR 29 / DEX 1 / INT 0 build (bow + heavy)
  - Aggressively advance toward the lowest-HP enemy
  - Once in range, stand and deliver (minimal unnecessary movement)
  - Focus fire the globally lowest-HP target
"""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


def get_blue_rush_init_strategy() -> Callable[..., List[PieceArg]]:
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


def get_blue_rush_action_strategy() -> Callable[..., ActionSet]:
    """Aggressive advance + focus fire, minimising unnecessary moves."""
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current = env.current_piece
        if current is None or not current.is_alive:
            return action

        enemies = [
            p for p in env.action_queue
            if p.team != current.team and p.is_alive
        ]
        if not enemies:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        target = min(enemies, key=lambda e: e.health)
        distance = calculate_distance(current.position, target.position)
        in_range = distance <= current.attack_range

        from strategy_utils import get_legal_moves
        legal_moves = get_legal_moves(env)

        # --- Move decision ---
        action.move = False
        if legal_moves and not in_range:
            # Advance toward target
            best = min(
                legal_moves,
                key=lambda m: calculate_distance(m, target.position),
            )
            action.move = True
            action.move_target = best
        elif legal_moves and in_range:
            # In range: only move if it improves position (closer to target)
            best = max(
                legal_moves,
                key=lambda m: (
                    100.0
                    if calculate_distance(m, target.position) <= current.attack_range
                    else -100.0
                ) - abs(m.x - current.position.x) - abs(m.y - current.position.y),
            )
            should_move = (best.x != current.position.x
                           or best.y != current.position.y)
            if should_move:
                action.move = True
                action.move_target = best

        # --- Attack decision ---
        pos = action.move_target if action.move else current.position
        if calculate_distance(pos, target.position) <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
        else:
            action.attack = False

        action.spell = False
        return action

    return strategy
