# Copyright 2026 AshGrey <ashgrey.huaier@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in the
# Software without restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the
# following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Heuristic-guided sniper — uses MCTS-style heuristic to pick actions.

Each candidate action (move + attack) is evaluated by forking the
environment and scoring the resulting state.  The action with the
highest heuristic score is selected.  This is a greedy one-step
lookahead using the evaluation concepts from MCTS:

- HP advantage
- Numerical advantage (alive pieces)
- Range penalty: penalise pieces that are outside bow range of ALL enemies
- Focus-fire bonus: reward clustering multiple friendlies near one enemy
- Formation bonus: reward keeping friendlies close together
"""

from typing import Callable, List, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from strategy_utils import (
    fork_environment,
    get_attackable_targets,
    get_legal_moves,
    step_with_action,
)
from utils import ActionSet, AttackContext, PieceArg, Point


def _hc_heuristic(env: Environment, team: int) -> float:
    """Score a board state from *team*'s perspective.

    Components:
    - HP difference (1 HP = 1 point)
    - Numerical advantage (50 per extra alive piece)
    - Range penalty (-20 per friendly outside bow range of ALL enemies)
    - Focus-fire bonus (+10 for each extra friendly near same enemy)
    - Formation bonus (-1 per tile average distance between friendlies)
    """
    score = 0.0
    us: List = []
    them: List = []

    for piece in env.action_queue:
        if not piece.is_alive:
            continue
        if piece.team == team:
            us.append(piece)
        else:
            them.append(piece)

    our_hp = sum(p.health for p in us)
    their_hp = sum(p.health for p in them)

    score += our_hp - their_hp
    score += (len(us) - len(them)) * 50.0

    # Range penalty: penalise friendlies that can't attack anyone
    for f in us:
        can_attack = any(
            calculate_distance(f.position, e.position) <= f.attack_range
            for e in them
        )
        if not can_attack:
            score -= 20.0

    # Focus-fire bonus: reward clustering near the same enemy
    for e in them:
        nearby = sum(
            1 for f in us
            if calculate_distance(f.position, e.position) <= f.attack_range
        )
        if nearby >= 2:
            score += 10.0 * (nearby - 1)

    # Formation bonus: reward keeping the team close
    if len(us) >= 2:
        pair_dist = 0.0
        pairs = 0
        for i, a in enumerate(us):
            for b in us[i + 1:]:
                pair_dist += calculate_distance(a.position, b.position)
                pairs += 1
        score -= (pair_dist / pairs)

    return score


def get_hc_sniper_init_strategy() -> Callable[..., List[PieceArg]]:
    """Standard STR 29 / DEX 1 / INT 0, bow + heavy armour."""
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
                (x, y)
                for y in range(board.height - 6, board.height)
                for x in range(board.width - 3, 2, -1)
            ]
        positions = allocate_init_positions(
            board, pid, init_message.piece_cnt, order,
        )
        piece_args: List[PieceArg] = []
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


def get_hc_sniper_action_strategy() -> Callable[..., ActionSet]:
    """Greedy one-step lookahead: fork, apply, evaluate, pick best."""
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

        my_team = current.team
        legal_moves = get_legal_moves(env)
        attackable = get_attackable_targets(env)

        # Pre-select best attack target (lowest HP)
        best_target = min(attackable, key=lambda p: p.health) if attackable else None

        # Sample up to 20 moves closest to nearest enemy for efficiency
        nearest_enemy = min(
            enemies,
            key=lambda e: calculate_distance(current.position, e.position),
        )
        sampled = sorted(
            legal_moves,
            key=lambda m: calculate_distance(m, nearest_enemy.position),
        )[:20]

        best_score = float("-inf")
        best_action: ActionSet = None

        candidates: List[ActionSet] = []

        # Candidate 1: no-move, no-attack (pass)
        noop = ActionSet()
        noop.move = False
        noop.attack = False
        noop.spell = False
        candidates.append(noop)

        # Candidate 2: attack only (if possible)
        if best_target is not None and current.action_points > 0:
            atk = ActionSet()
            atk.move = False
            atk.attack = True
            atk.attack_context = AttackContext()
            atk.attack_context.attacker = current
            atk.attack_context.target = best_target
            atk.spell = False
            candidates.append(atk)

        # Candidates 3+: move + best attack
        for move_pos in sampled:
            act = ActionSet()
            act.move = True
            act.move_target = move_pos

            # Check if target is in range from new position
            in_range = (
                best_target is not None
                and calculate_distance(move_pos, best_target.position) <= current.attack_range
            )
            if in_range and current.action_points > 0:
                act.attack = True
                act.attack_context = AttackContext()
                act.attack_context.attacker = current
                act.attack_context.target = best_target
            else:
                act.attack = False
            act.spell = False
            candidates.append(act)

        for ca in candidates:
            fork = fork_environment(env)
            try:
                step_with_action(fork, ca)
            except Exception:
                continue
            sc = _hc_heuristic(fork, my_team)
            if sc > best_score:
                best_score = sc
                best_action = ca

        if best_action is not None:
            # Remap piece references from the (last) forked env back to the
            # real environment, so the game engine operates on live pieces.
            if best_action.attack and best_action.attack_context:
                best_action.attack_context.attacker = current
                if best_action.attack_context.target is not None:
                    for p in env.action_queue:
                        if p.id == best_action.attack_context.target.id:
                            best_action.attack_context.target = p
                            break
            return best_action

        action.move = False
        action.attack = False
        action.spell = False
        return action

    return strategy
