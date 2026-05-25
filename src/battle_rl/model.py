"""Actor-Critic network for PPO.

Architecture:
  Input (104) → MLP(128, ReLU) → MLP(128, ReLU)
    → Actor: Tanh to scale output to [-1, 1] (6 meta-parameters)
    → Critic: Linear(1) for state value

Total params: 104×128 + 128 + 128×128 + 128 + 128×6 + 6 + 128×1 + 1 ≈ 31K
"""

from typing import Tuple

import torch
import torch.nn as nn


class ActorCritic(nn.Module):
    """Shared-encoder Actor-Critic for continuous meta-parameter control."""

    def __init__(self, obs_dim: int = 104, hidden_dim: int = 128, action_dim: int = 6):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        self.actor_mean = nn.Linear(hidden_dim, action_dim)
        self.actor_logstd = nn.Parameter(torch.zeros(action_dim))
        self.critic = nn.Linear(hidden_dim, 1)

        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=0.01 if m is self.actor_mean else 1.0)
                nn.init.zeros_(m.bias)

    def forward(
        self, obs: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Return (action, log_prob, value)."""
        h = self.encoder(obs)
        mean = torch.tanh(self.actor_mean(h))  # [-1, 1]
        logstd = self.actor_logstd.expand_as(mean)
        std = torch.exp(logstd)

        dist = torch.distributions.Normal(mean, std)
        action = dist.sample()
        action = torch.clamp(action, -1.0, 1.0)
        log_prob = dist.log_prob(action).sum(dim=-1)

        value = self.critic(h).squeeze(-1)
        return action, log_prob, value

    def evaluate(
        self, obs: torch.Tensor, action: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Return (log_prob, entropy, value) for a given (obs, action)."""
        h = self.encoder(obs)
        mean = torch.tanh(self.actor_mean(h))
        logstd = self.actor_logstd.expand_as(mean)
        std = torch.exp(logstd)

        dist = torch.distributions.Normal(mean, std)
        log_prob = dist.log_prob(action).sum(dim=-1)
        entropy = dist.entropy().sum(dim=-1)

        value = self.critic(h).squeeze(-1)
        return log_prob, entropy, value
