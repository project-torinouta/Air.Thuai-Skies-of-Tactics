"""Alpha-Beta pruning search strategy."""

from typing import Callable, List, Optional, Tuple

from env import Environment
from strategy_utils import (
    fork_environment,
    get_attackable_targets,
    get_legal_moves,
    get_state_score,
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
    ) -> Tuple[float, Optional[ActionSet]]:
        if depth == 0 or env.is_game_over:
            return get_state_score(env), None

        current_piece = env.current_piece

        if maximizing:
            return _maximize(env, current_piece, depth, alpha, beta)
        else:
            return _minimize(env, current_piece, depth, alpha, beta)

    def _maximize(
        env: Environment,
        current_piece: object,
        depth: int,
        alpha: float,
        beta: float,
    ) -> Tuple[float, Optional[ActionSet]]:
        max_eval = float("-inf")
        best_action = None

        legal_moves = get_legal_moves(env)
        attackable_targets = get_attackable_targets(env)
        spells: List[Spell] = (
            env.get_available_spells(current_piece) if depth > 0 else []
        )

        for move in ([None] + legal_moves) if legal_moves is not None else [None]:
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

                    next_env.execute_player_action(action)
                    eval_score, _ = _alpha_beta(
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

    def _minimize(
        env: Environment,
        current_piece: object,
        depth: int,
        alpha: float,
        beta: float,
    ) -> Tuple[float, Optional[ActionSet]]:
        min_eval = float("inf")
        best_action = None

        legal_moves = get_legal_moves(env)
        attackable_targets = get_attackable_targets(env)

        base_spells: List[Spell] = []
        if current_piece.spell_slots > 0:
            base_spells = [
                Spell(0, "Damage", "", SpellEffectType.DAMAGE, DamageType.PHYSICAL, 10),
                Spell(0, "Heal", "", SpellEffectType.HEAL, DamageType.NONE, 8),
                Spell(0, "Buff", "", SpellEffectType.BUFF, DamageType.NONE, 5),
                Spell(0, "Debuff", "", SpellEffectType.DEBUFF, DamageType.NONE, 3),
            ]

        moves = [None] + legal_moves if legal_moves else [None]
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

                    next_env.execute_player_action(action)
                    eval_score, _ = _alpha_beta(
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
        _, best_action = _alpha_beta(
            env, max_depth, float("-inf"), float("inf"), True
        )
        return best_action if best_action is not None else ActionSet()

    return strategy
