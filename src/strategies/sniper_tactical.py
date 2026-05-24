"""Sniper Tactical — replicated from Red team (Sniper) replay behaviour.

Core: extreme focus-fire + close-range positional denial.
"""

from typing import Callable, List

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions
from utils import ActionSet, AttackContext, PieceArg, Point


def get_sniper_tactical_init_strategy() -> Callable[..., List[PieceArg]]:
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


def get_sniper_tactical_action_strategy() -> Callable[..., ActionSet]:
    """Red-team (Sniper) replication: focus-fire + close-range denial."""
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current = env.current_piece

        if current is None or not current.is_alive:
            action.move = False
            action.attack = False
            action.spell = False
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

        def target_priority(e):
            dist = abs(current.position.x - e.position.x) + abs(current.position.y - e.position.y)
            return e.health * 1.0 + dist * 2.0

        global_target = min(enemies, key=target_priority)

        from strategy_utils import get_legal_moves
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            legal_moves = [current.position]

        def d(pos, tx, ty) -> float:
            return abs(pos.x - tx) + abs(pos.y - ty)

        best_move = current.position
        best_score = -999999.0

        for m in legal_moves:
            dist_to_target = d(m, global_target.position.x, global_target.position.y)
            score = -dist_to_target * 10.0
            if dist_to_target == 1:
                score += 5.0
            if dist_to_target == 0:
                score -= 100.0
            if score > best_score:
                best_score = score
                best_move = m

        action.move = (best_move.x != current.position.x or best_move.y != current.position.y)
        if action.move:
            action.move_target = best_move

        final_pos = action.move_target if action.move else current.position
        if d(final_pos, global_target.position.x, global_target.position.y) <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = global_target
        else:
            reachable_enemies = [
                e for e in enemies
                if d(final_pos, e.position.x, e.position.y) <= current.attack_range
            ]
            if reachable_enemies:
                fallback_target = min(reachable_enemies, key=lambda e: e.health)
                action.attack = True
                action.attack_context = AttackContext()
                action.attack_context.attacker = current
                action.attack_context.target = fallback_target
            else:
                action.attack = False

        action.spell = False
        return action

    return strategy
