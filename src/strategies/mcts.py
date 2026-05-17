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

"""Monte Carlo Tree Search (MCTS) action strategy."""

import math
import random
from typing import Callable, List, Optional

from env import Environment
from strategy_utils import (
    fork_environment,
    get_attackable_targets,
    get_legal_moves,
    step_with_action,
)
from utils import (
    ActionSet,
    Area,
    AttackContext,
    Point,
    SpellContext,
    SpellEffectType,
)

MCTS_VERBOSE: bool = False


class _MCTSNode:
    """A node in the MCTS tree."""

    def __init__(
        self,
        env: Environment,
        parent: Optional["_MCTSNode"] = None,
        action: Optional[ActionSet] = None,
    ) -> None:
        self.env = env
        self.parent = parent
        self.action = action
        self.children: List["_MCTSNode"] = []
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
                        continue

                    step_with_action(next_env, action)
                    child = _MCTSNode(next_env, self, action)
                    self.children.append(child)

    def select(self) -> "_MCTSNode":
        """Select the most promising child using UCB1.

        :returns: The child node with the highest UCB1 score.
        :rtype: _MCTSNode
        """
        if not self.children:
            return self

        def ucb1(node: _MCTSNode) -> float:
            if node.visits == 0:
                return float("inf")
            return node.value / node.visits + math.sqrt(
                2 * math.log(self.visits) / node.visits
            )

        return max(self.children, key=ucb1)

    def simulate(self) -> float:
        """Run a random playout from this node.

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
                action.attack_context.target = random.choice(attackable_targets)
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

        t1_health = sum(p.health for p in sim_env.player1.pieces if p.is_alive)
        t2_health = sum(p.health for p in sim_env.player2.pieces if p.is_alive)

        if t1_health > t2_health:
            return 1.0 if initial_team == 1 else -1.0
        if t2_health > t1_health:
            return 1.0 if initial_team == 2 else -1.0
        return 0.0

    def backpropagate(self, value: float) -> None:
        """Back-propagate the simulation result up the tree.

        :param value: The result to propagate.
        :type value: float
        """
        node = self
        while node is not None:
            node.visits += 1
            node.value += value
            node = node.parent
            value = -value


def get_mcts_action_strategy(
    simulation_count: int = 10,
) -> Callable[..., ActionSet]:
    """Return an MCTS action strategy.

    Builds a search tree by simulating random playouts and selects
    the most-visited child action.

    :param simulation_count: Number of simulations per decision point.
        Defaults to 10.
    :type simulation_count: int
    :returns: A callable action strategy.
    :rtype: Callable
    """
    def strategy(env: Environment) -> ActionSet:
        root = _MCTSNode(env)

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
                print(f"\n[MCTS] No child nodes generated. "
                      f"Piece: ID={env.current_piece.id if env.current_piece else None}, "
                      f"Legal moves: {len(get_legal_moves(env))}, "
                      f"Attackable: {len(get_attackable_targets(env))}, "
                      f"Spells: {len(env.get_available_spells())}")
            return ActionSet()

        if MCTS_VERBOSE:
            print(f"\n[MCTS] Found {len(root.children)} actions.")
        best_child = max(root.children, key=lambda c: c.visits)
        if MCTS_VERBOSE:
            print(f"[MCTS] Best: visits={best_child.visits}, score={best_child.value}")
        return best_child.action

    return strategy
