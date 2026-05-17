"""Aggressive strategy — close-range rush with high strength."""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point


def get_aggressive_init_strategy() -> Callable[..., List[PieceArg]]:
    """Return an aggressive initialisation strategy.

    Prioritises high strength and frontline positioning. Each piece
    is configured with strength=20, dexterity=8, intelligence=2,
    shortsword + heavy armour.

    :returns: A callable that takes an ``InitGameMessage`` and returns
        a list of ``PieceArg``.
    :rtype: Callable
    """
    def strategy(init_message: InitGameMessage) -> List[PieceArg]:
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
        positions = allocate_init_positions(board, pid, init_message.piece_cnt, order)
        piece_args: List[PieceArg] = []
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
                distance = calculate_distance(
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

        from strategy_utils import get_legal_moves

        legal_moves = get_legal_moves(env)
        if legal_moves:
            best_move = None
            min_distance = float("inf")
            for move in legal_moves:
                distance = calculate_distance(move, target_enemy.position)
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
