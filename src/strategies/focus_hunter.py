"""Focus Hunter — replicated from Red team (sniper) in replay 8534361.

Core rules (reverse-engineered from Red's behaviour):
  1. ALL 3 pieces attack the SAME target — globally lowest-HP enemy.
  2. Each piece moves independently to get within attack range.
  3. No formation constraints, no cluster radius, no L-shape.
  4. After a target dies, immediately switch to the next lowest-HP enemy.
  5. If no attack possible, advance toward the target.
"""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


def get_focus_hunter_init_strategy() -> Callable[..., List[PieceArg]]:
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


def get_focus_hunter_action_strategy() -> Callable[..., ActionSet]:
    """All pieces focus-fire the globally lowest-HP enemy."""
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current = env.current_piece

        enemies = [
            p for p in env.action_queue
            if p.team != current.team and p.is_alive
        ]
        if not enemies:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        # Globally lowest-HP enemy = focus target
        target = min(enemies, key=lambda e: e.health)

        from strategy_utils import get_legal_moves
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            legal_moves = [current.position]

        in_range = calculate_distance(current.position, target.position) <= current.attack_range

        if in_range:
            # Attack from current position (shuffle if better position available)
            best = max(
                legal_moves,
                key=lambda m: (
                    100.0 if calculate_distance(m, target.position) <= current.attack_range
                    else -100.0
                ) - abs(m.x - current.position.x) - abs(m.y - current.position.y),
            )
            action.move = (best.x != current.position.x or best.y != current.position.y)
            if action.move:
                action.move_target = best
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = target
        else:
            # Advance toward target
            best = min(
                legal_moves,
                key=lambda m: calculate_distance(m, target.position),
            )
            action.move = (best.x != current.position.x or best.y != current.position.y)
            if action.move:
                action.move_target = best

            # Check if attack possible from new position
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
