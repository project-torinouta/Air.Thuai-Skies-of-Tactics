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

"""Alpha-Beta pruning search strategy."""

from typing import Callable, List, Optional, Tuple

from env import Environment
from strategies._utils import calculate_distance
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
    Point,
    Spell,
    SpellContext,
    SpellEffectType,
    DamageType,
)

_MAX_MOVES_PER_NODE: int = 20


def _sample_moves(
    env: Environment, legal_moves: List[Point]
) -> List[Optional[Point]]:
    """Pick a subset of legal moves for the search node.

    Always includes the current position and the closest
    ``_MAX_MOVES_PER_NODE`` positions to the nearest enemy.

    :param env: The game environment.
    :type env: Environment
    :param legal_moves: All reachable positions.
    :type legal_moves: List[Point]
    :returns: ``[None, move_1, ...]``.
    :rtype: List[Optional[Point]]
    """
    if len(legal_moves) <= _MAX_MOVES_PER_NODE:
        return [None] + legal_moves
    current = env.current_piece
    if current is None:
        return [None] + legal_moves[:_MAX_MOVES_PER_NODE]
    target_enemy = None
    nearest = float("inf")
    for p in env.action_queue:
        if p.is_alive and p.team != current.team:
            d = calculate_distance(current.position, p.position)
            if d < nearest:
                nearest = d
                target_enemy = p
    if target_enemy is None:
        return [None] + legal_moves[:_MAX_MOVES_PER_NODE]
    sorted_moves = sorted(
        legal_moves,
        key=lambda m: (
            0 if m == current.position
            else calculate_distance(m, target_enemy.position)
        ),
    )
    return [None] + sorted_moves[:_MAX_MOVES_PER_NODE]


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
    def _alpha_beta(
        env: Environment,
        depth: int,
        alpha: float,
        beta: float,
        maximizing: bool,
        root_team: int,
    ) -> Tuple[float, Optional[ActionSet]]:
        if depth == 0 or env.is_game_over:
            score = get_state_score(env)
            if env.current_piece is not None and env.current_piece.team != root_team:
                score = -score
            return score, None

        current_piece = env.current_piece
        if current_piece is None:
            return get_state_score(env), None

        if maximizing:
            return _maximize(env, current_piece, depth, alpha, beta, root_team)
        else:
            return _minimize(env, current_piece, depth, alpha, beta, root_team)

    def _maximize(
        env: Environment,
        current_piece: object,
        depth: int,
        alpha: float,
        beta: float,
        root_team: int,
    ) -> Tuple[float, Optional[ActionSet]]:
        max_eval = float("-inf")
        best_action = None

        legal_moves = get_legal_moves(env)
        attackable_targets = get_attackable_targets(env)
        spells: List[Spell] = (
            env.get_available_spells(current_piece) if depth > 0 else []
        )

        for move in _sample_moves(env, legal_moves) if legal_moves else [None]:
            if move is not None and current_piece.action_points <= 0:
                continue
            targets = [None] + attackable_targets if attackable_targets else [None]
            for target in targets:
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

                    if (
                        spell is not None
                        and remaining > 0
                        and current_piece.spell_slots > 0
                    ):
                        action.spell = True
                        action.spell_context = SpellContext()
                        action.spell_context.caster = current_piece
                        action.spell_context.target = target if target else current_piece
                        action.spell_context.spell = spell
                        action.spell_context.target_area = Area(
                            current_piece.position.x,
                            current_piece.position.y,
                            2,
                        )
                    else:
                        action.spell = False

                    step_with_action(next_env, action)
                    eval_score, _ = _alpha_beta(
                        next_env, depth - 1, alpha, beta, False, root_team
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

    def _minimize(
        env: Environment,
        current_piece: object,
        depth: int,
        alpha: float,
        beta: float,
        root_team: int,
    ) -> Tuple[float, Optional[ActionSet]]:
        min_eval = float("inf")
        best_action = None

        legal_moves = get_legal_moves(env)
        attackable_targets = get_attackable_targets(env)

        base_spells: List[Spell] = env.get_available_spells(current_piece)

        moves = _sample_moves(env, legal_moves) if legal_moves else [None]
        for move in moves:
            if move is not None and current_piece.action_points <= 0:
                continue
            targets = [None] + attackable_targets if attackable_targets else [None]
            for target in targets:
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

                    if (
                        spell is not None
                        and remaining > 0
                        and current_piece.spell_slots > 0
                    ):
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
                            best_target = (
                                min(spell_targets, key=lambda p: p.health)
                                if spell.effect_type
                                in [SpellEffectType.DAMAGE, SpellEffectType.DEBUFF]
                                else (
                                    min(
                                        spell_targets,
                                        key=lambda p: p.health / p.max_health,
                                    )
                                    if spell.effect_type
                                    in [SpellEffectType.HEAL, SpellEffectType.BUFF]
                                    else current_piece
                                )
                            )
                            action.spell_context.target = best_target
                            action.spell_context.target_area = Area(
                                best_target.position.x,
                                best_target.position.y,
                                0,
                            )
                    else:
                        action.spell = False

                    step_with_action(next_env, action)
                    eval_score, _ = _alpha_beta(
                        next_env, depth - 1, alpha, beta, True, root_team
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
        root_team = env.current_piece.team if env.current_piece is not None else 1
        _, best_action = _alpha_beta(
            env, max_depth, float("-inf"), float("inf"), True, root_team
        )
        return best_action if best_action is not None else ActionSet()

    return strategy
