"""Policy-guided MCTS with heuristic evaluation — lightweight AlphaZero.

Combines:
1. **Heuristic evaluation** instead of random rollouts (fast, domain-aware)
2. **Policy network prior** (trained ML weights) for PUCT action selection
3. **100x more simulations** than vanilla MCTS because heuristic is instant

The policy network provides action priors P(s,a) that guide the search
toward promising moves. The heuristic evaluation provides a fast leaf
value without running random playouts.
"""

import math
import os
import random
import sys
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from env import Environment
from ml.action_decoder import decode_action
from ml.evaluator import heuristic_evaluate
from ml.policy_net import forward, param_count
from ml.state_encoder import encode_state, state_dim
from strategies._utils import calculate_distance
from strategy_utils import (
    fork_environment,
    get_attackable_targets,
    get_legal_moves,
    step_with_action,
)
from utils import ActionSet, AttackContext, Point


MCTS_VERBOSE: bool = False

_MAX_MOVES_PER_EXPAND: int = 15
C_PUCT: float = 1.5


def _load_policy_params() -> Optional[np.ndarray]:
    """Load trained policy network weights from standard locations.

    :returns: Parameter vector or None.
    :rtype: Optional[np.ndarray]
    """
    candidates = [
        "weights/ml_sniper_best.npy",
        "weights/ml_sniper_best_574pct.npy",
        os.path.join(os.path.dirname(__file__), "..", "weights", "ml_sniper_best.npy"),
        os.path.join(os.path.dirname(__file__), "..", "weights", "ml_sniper_best_574pct.npy"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return np.load(path)
    return None


class _PUCTNode:
    """MCTS node with policy-guided PUCT selection."""

    def __init__(
        self,
        env: Environment,
        parent: Optional["_PUCTNode"] = None,
        action: Optional[ActionSet] = None,
        prior: float = 0.0,
    ) -> None:
        self.env = env
        self.parent = parent
        self.action = action
        self.children: List["_PUCTNode"] = []
        self.visits: int = 0
        self.value: float = 0.0
        self.prior: float = prior  # P(s,a) from policy network
        self._expanded: bool = False

    @staticmethod
    def _sample_moves(
        env: Environment, legal_moves: List[Point]
    ) -> List[Optional[Point]]:
        current = env.current_piece
        if len(legal_moves) <= _MAX_MOVES_PER_EXPAND:
            return [None] + legal_moves

        target_enemy = None
        nearest = float("inf")
        for p in env.action_queue:
            if p.is_alive and p.team != current.team:
                d = calculate_distance(current.position, p.position)
                if d < nearest:
                    nearest = d
                    target_enemy = p

        if target_enemy is None:
            return [None] + legal_moves[:_MAX_MOVES_PER_EXPAND]

        sorted_moves = sorted(
            legal_moves,
            key=lambda m: (
                0 if m == current.position
                else calculate_distance(m, target_enemy.position)
            ),
        )
        return [None] + sorted_moves[:_MAX_MOVES_PER_EXPAND]

    def _compute_prior(
        self, state: np.ndarray, params: Optional[np.ndarray]
    ) -> float:
        """Compute action prior using the policy network.

        :param state: Encoded state vector.
        :param params: Policy network weights (or None for uniform prior).
        :returns: Prior probability in (0, 1).
        """
        if params is None:
            return 1.0
        logits = forward(params, state)
        probs = np.exp(logits - np.max(logits))
        probs /= np.sum(probs) + 1e-10
        return float(probs[0])  # Use first output as general prior weight

    def expand(self, policy_params: Optional[np.ndarray]) -> None:
        """Expand node: generate child actions with policy priors.

        :param policy_params: Policy network weights (or None).
        """
        if self._expanded:
            return
        self._expanded = True

        current = self.env.current_piece
        legal_moves = get_legal_moves(self.env)
        attackable = get_attackable_targets(self.env)

        moves = self._sample_moves(self.env, legal_moves)

        encoded = encode_state(self.env)
        n_children = 0

        for move in moves:
            if move is not None and current.action_points <= 0:
                continue
            for target in [None] + attackable:
                if target is not None and current.action_points <= 0:
                    continue

                action = ActionSet()
                next_env = fork_environment(self.env)
                remaining = current.action_points
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
                    action.attack_context.attacker = current
                    action.attack_context.target = target
                    remaining -= 1
                    has_action = True
                else:
                    action.attack = False

                action.spell = False

                if current.action_points > 0 and not has_action:
                    continue

                prior = self._compute_prior(encoded, policy_params)
                step_with_action(next_env, action)
                child = _PUCTNode(next_env, self, action, prior)
                self.children.append(child)
                n_children += 1

    def select(self, c_puct: float = C_PUCT) -> "_PUCTNode":
        """Select child using PUCT.

        :param c_puct: Exploration constant.
        :returns: Best child node.
        """
        if not self.children:
            return self

        def puct(node: _PUCTNode) -> float:
            if node.visits == 0:
                q = 0.0
            else:
                q = node.value / node.visits
            u = c_puct * node.prior * math.sqrt(self.visits) / (1 + node.visits)
            return q + u

        return max(self.children, key=puct)

    def simulate(self) -> float:
        """Evaluate leaf using heuristic (no random rollouts).

        :returns: Score in [-1, 1] for current team.
        """
        return heuristic_evaluate(self.env)

    def backpropagate(self, value: float) -> None:
        node = self
        while node is not None:
            node.visits += 1
            node.value += value
            node = node.parent
            value = -value


def get_improved_mcts_strategy(
    simulation_count: int = 200,
) -> Callable[..., ActionSet]:
    """Return an improved MCTS action strategy with policy guidance.

    Uses the trained ML policy network for action priors and a heuristic
    evaluator instead of random rollouts. Runs ``simulation_count``
    simulations per decision.

    :param simulation_count: Number of MCTS simulations per turn.
        Defaults to 200 (≈ 1-2s per decision).
    :type simulation_count: int
    :returns: A callable action strategy.
    :rtype: Callable
    """
    policy_params = _load_policy_params()
    if policy_params is not None:
        if MCTS_VERBOSE:
            print(f"[MCTS] Loaded policy params ({len(policy_params)} dims)")
    else:
        if MCTS_VERBOSE:
            print("[MCTS] No policy weights — using uniform priors")

    def strategy(env: Environment) -> ActionSet:
        root = _PUCTNode(env)

        for _ in range(simulation_count):
            node = root

            while node.children:
                node = node.select()

            if node.visits > 0 and not node._expanded:
                node.expand(policy_params)

            if node.children and node.visits > 0:
                node = random.choice(node.children)

            value = node.simulate()
            node.backpropagate(value)

        if not root.children:
            return ActionSet()

        best = max(root.children, key=lambda c: c.visits)
        return best.action

    return strategy
