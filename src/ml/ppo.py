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

"""PPO policy network — PyTorch, discrete action spaces, value head.

Architecture:
- Input: 104-dim state vector (from state_encoder)
- Shared: 64 → 32 (ReLU)
- Policy heads: move(3) — advance/stay/retreat, target(3), attack(2)
- Value head: 1 (scalar)
"""

from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from ml.state_encoder import state_dim

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def layer_init(layer: nn.Linear, std: float = np.sqrt(2), bias_const: float = 0.0):
    """Orthogonal initialisation common in RL implementations."""
    torch.nn.init.orthogonal_(layer.weight, std)
    torch.nn.init.constant_(layer.bias, bias_const)
    return layer


class PPOPolicy(nn.Module):
    """Policy network with separate action heads and value head."""

    def __init__(
        self,
        n_move: int = 3,
        n_target: int = 3,
        n_attack: int = 2,
        n_spell: int = 1,
    ):
        super().__init__()
        inp = state_dim()
        self.shared = nn.Sequential(
            layer_init(nn.Linear(inp, 64)),
            nn.ReLU(),
            layer_init(nn.Linear(64, 32)),
            nn.ReLU(),
        )
        self.move_head = layer_init(nn.Linear(32, n_move), std=0.01)
        self.target_head = layer_init(nn.Linear(32, n_target), std=0.01)
        self.attack_head = layer_init(nn.Linear(32, n_attack), std=0.01)
        self.spell_head = layer_init(nn.Linear(32, n_spell), std=0.01)
        self.value_head = layer_init(nn.Linear(32, 1), std=1.0)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, ...]:
        """Return (move_logits, target_logits, attack_logits, spell_logits, value)."""
        h = self.shared(x)
        return (
            self.move_head(h),
            self.target_head(h),
            self.attack_head(h),
            self.spell_head(h),
            self.value_head(h),
        )

    def get_value(self, x: torch.Tensor) -> torch.Tensor:
        """Compute value for a given state."""
        h = self.shared(x)
        return self.value_head(h)

    def sample_action(
        self, state: np.ndarray, deterministic: bool = False,
    ) -> Tuple[np.ndarray, torch.Tensor, torch.Tensor]:
        """Sample an action from the policy.

        :param state: 104-dim state vector.
        :param deterministic: If True, take argmax instead of sample.
        :returns: (action_array, log_prob, entropy) where
            action_array = [move_idx, target_idx, attack_idx, spell_idx]
        """
        state_t = torch.FloatTensor(state).unsqueeze(0).to(DEVICE)
        move_l, target_l, attack_l, spell_l, _ = self.forward(state_t)

        if deterministic:
            move_a = move_l.argmax(dim=-1)
            target_a = target_l.argmax(dim=-1)
            attack_a = attack_l.argmax(dim=-1)
            spell_a = spell_l.argmax(dim=-1)
            log_prob = torch.zeros(1, device=DEVICE)
            entropy = torch.zeros(1, device=DEVICE)
        else:
            move_dist = torch.distributions.Categorical(logits=move_l)
            target_dist = torch.distributions.Categorical(logits=target_l)
            attack_dist = torch.distributions.Categorical(logits=attack_l)
            spell_dist = torch.distributions.Categorical(logits=spell_l)

            move_a = move_dist.sample()
            target_a = target_dist.sample()
            attack_a = attack_dist.sample()
            spell_a = spell_dist.sample()

            log_prob = (
                move_dist.log_prob(move_a)
                + target_dist.log_prob(target_a)
                + attack_dist.log_prob(attack_a)
                + spell_dist.log_prob(spell_a)
            )
            entropy = (
                move_dist.entropy()
                + target_dist.entropy()
                + attack_dist.entropy()
                + spell_dist.entropy()
            ).mean()

        action = np.array([
            move_a.cpu().item(),
            target_a.cpu().item(),
            attack_a.cpu().item(),
            spell_a.cpu().item(),
        ], dtype=np.int64)
        return action, log_prob, entropy

    def evaluate_actions(
        self, states: torch.Tensor, actions: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Compute log probs, entropy, and values for a batch of (state, action).

        :param states: (B, 104)
        :param actions: (B, 4) with columns [move, target, attack, spell]
        :returns: (log_probs, entropy, values)
        """
        move_l, target_l, attack_l, spell_l, values = self.forward(states)
        values = values.squeeze(-1)

        move_dist = torch.distributions.Categorical(logits=move_l)
        target_dist = torch.distributions.Categorical(logits=target_l)
        attack_dist = torch.distributions.Categorical(logits=attack_l)
        spell_dist = torch.distributions.Categorical(logits=spell_l)

        log_probs = (
            move_dist.log_prob(actions[:, 0])
            + target_dist.log_prob(actions[:, 1])
            + attack_dist.log_prob(actions[:, 2])
            + spell_dist.log_prob(actions[:, 3])
        )
        entropy = (
            move_dist.entropy()
            + target_dist.entropy()
            + attack_dist.entropy()
            + spell_dist.entropy()
        ).mean()

        return log_probs, entropy, values


#
# Rollout buffer
#


class RolloutBuffer:
    """Stores trajectories for PPO updates."""

    def __init__(self):
        self.states: List[np.ndarray] = []
        self.actions: List[np.ndarray] = []
        self.log_probs: List[float] = []
        self.rewards: List[float] = []
        self.dones: List[bool] = []
        self.values: List[float] = []

    def add(
        self,
        state: np.ndarray,
        action: np.ndarray,
        log_prob: float,
        reward: float,
        done: bool,
        value: float,
    ):
        self.states.append(state)
        self.actions.append(action)
        self.log_probs.append(log_prob)
        self.rewards.append(reward)
        self.dones.append(done)
        self.values.append(value)

    def clear(self):
        self.states.clear()
        self.actions.clear()
        self.log_probs.clear()
        self.rewards.clear()
        self.dones.clear()
        self.values.clear()

    def __len__(self) -> int:
        return len(self.states)


#
# PPO updater
#


def compute_gae(
    rewards: List[float],
    values: List[float],
    dones: List[bool],
    gamma: float = 0.99,
    lam: float = 0.95,
) -> List[float]:
    """Generalized Advantage Estimation.

    :param rewards: Per-step rewards.
    :param values: Per-step value estimates.
    :param dones: Whether each step ended an episode.
    :param gamma: Discount factor.
    :param lam: GAE lambda.
    :returns: Per-step advantages.
    """
    advantages = []
    gae = 0.0
    for t in reversed(range(len(rewards))):
        if t == len(rewards) - 1:
            next_val = 0.0 if dones[t] else values[t]
        else:
            next_val = 0.0 if dones[t] else values[t + 1]
        delta = rewards[t] + gamma * next_val - values[t]
        gae = delta + gamma * lam * (0.0 if dones[t] else gae)
        advantages.insert(0, gae)
    return advantages


def update_policy(
    policy: PPOPolicy,
    optimizer: torch.optim.Optimizer,
    buffer: RolloutBuffer,
    gamma: float = 0.99,
    lam: float = 0.95,
    clip_eps: float = 0.2,
    vf_coef: float = 0.5,
    ent_coef: float = 0.01,
    k_epochs: int = 4,
    batch_size: int = 64,
) -> dict:
    """Perform one PPO update from a rollout buffer.

    :param policy: The policy network.
    :param optimizer: Torch optimizer.
    :param buffer: Filled rollout buffer.
    :returns: Dict of loss components for logging.
    """
    n = len(buffer)
    if n == 0:
        return {"loss": 0.0, "policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}

    states = torch.FloatTensor(np.array(buffer.states)).to(DEVICE)
    actions = torch.LongTensor(np.array(buffer.actions)).to(DEVICE)
    old_log_probs = torch.FloatTensor(buffer.log_probs).to(DEVICE)
    advantages = torch.FloatTensor(
        compute_gae(buffer.rewards, buffer.values, buffer.dones, gamma, lam),
    ).to(DEVICE)
    returns = advantages + torch.FloatTensor(buffer.values).to(DEVICE)

    advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

    # Mini-batch updates
    indices = np.arange(n)
    total_loss = 0.0
    total_policy = 0.0
    total_value = 0.0
    total_entropy = 0.0

    for _ in range(k_epochs):
        np.random.shuffle(indices)
        for start in range(0, n, batch_size):
            batch = indices[start:start + batch_size]
            b_states = states[batch]
            b_actions = actions[batch]
            b_old_log = old_log_probs[batch]
            b_adv = advantages[batch]
            b_ret = returns[batch]

            log_probs, entropy, values = policy.evaluate_actions(b_states, b_actions)

            ratio = torch.exp(log_probs - b_old_log)
            surr1 = ratio * b_adv
            surr2 = torch.clamp(ratio, 1.0 - clip_eps, 1.0 + clip_eps) * b_adv
            policy_loss = -torch.min(surr1, surr2).mean()

            value_loss = F.mse_loss(values, b_ret)

            loss = policy_loss + vf_coef * value_loss - ent_coef * entropy

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), 0.5)
            optimizer.step()

            total_loss += loss.item()
            total_policy += policy_loss.item()
            total_value += value_loss.item()
            total_entropy += entropy.item()

    n_updates = k_epochs * ((n + batch_size - 1) // batch_size)
    return {
        "loss": total_loss / n_updates,
        "policy_loss": total_policy / n_updates,
        "value_loss": total_value / n_updates,
        "entropy": total_entropy / n_updates,
    }
