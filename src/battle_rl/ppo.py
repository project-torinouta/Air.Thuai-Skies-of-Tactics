"""PPO implementation — clipped surrogate, GAE, minibatch updates.

Usage:
    agent = PPO(obs_dim=104, action_dim=6)
    for epoch in range(num_epochs):
        traj = collect_trajectory(env, agent)
        agent.update(traj)
"""

from typing import List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from battle_rl.model import ActorCritic


class RolloutBuffer:
    """Stores one trajectory for PPO updates."""

    def __init__(self) -> None:
        self.obs: List[np.ndarray] = []
        self.actions: List[np.ndarray] = []
        self.rewards: List[float] = []
        self.dones: List[bool] = []
        self.values: List[float] = []
        self.log_probs: List[float] = []

    def add(
        self,
        obs: np.ndarray,
        action: np.ndarray,
        reward: float,
        done: bool,
        value: float,
        log_prob: float,
    ) -> None:
        self.obs.append(obs)
        self.actions.append(action)
        self.rewards.append(reward)
        self.dones.append(done)
        self.values.append(value)
        self.log_probs.append(log_prob)

    def to_tensor(self) -> dict:
        return {
            "obs": torch.FloatTensor(np.array(self.obs)),
            "actions": torch.FloatTensor(np.array(self.actions)),
            "rewards": torch.FloatTensor(self.rewards),
            "dones": torch.BoolTensor(self.dones),
            "values": torch.FloatTensor(self.values),
            "log_probs": torch.FloatTensor(self.log_probs),
        }


def compute_gae(
    rewards: torch.Tensor,
    dones: torch.Tensor,
    values: torch.Tensor,
    gamma: float = 0.99,
    gae_lambda: float = 0.95,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Generalized Advantage Estimation.

    Returns (advantages, returns) tensors.
    """
    T = rewards.shape[0]
    advantages = torch.zeros(T)
    gae = 0.0

    for t in reversed(range(T)):
        if t == T - 1:
            delta = rewards[t] - values[t]
        else:
            delta = rewards[t] + gamma * values[t + 1] * (1 - dones[t + 1].float()) - values[t]
        gae = delta + gamma * gae_lambda * (1 - dones[t].float()) * gae
        advantages[t] = gae

    returns = advantages + values
    return advantages, returns


class PPO:
    """PPO agent with clipped surrogate objective."""

    def __init__(
        self,
        obs_dim: int = 104,
        action_dim: int = 6,
        lr: float = 3e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_range: float = 0.2,
        ent_coef: float = 0.01,
        vf_coef: float = 0.5,
        max_grad_norm: float = 0.5,
        device: str = "cpu",
    ):
        self.device = torch.device(device)
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_range = clip_range
        self.ent_coef = ent_coef
        self.vf_coef = vf_coef
        self.max_grad_norm = max_grad_norm

        self.net = ActorCritic(obs_dim, action_dim=action_dim).to(self.device)
        self.optimizer = optim.Adam(self.net.parameters(), lr=lr)

    @torch.no_grad()
    def act(self, obs: np.ndarray) -> Tuple[np.ndarray, float, float]:
        """Single-step action selection. Returns (action, value, log_prob)."""
        obs_t = torch.FloatTensor(obs).unsqueeze(0).to(self.device)
        action, log_prob, value = self.net(obs_t)
        return (
            action.cpu().numpy()[0],
            value.cpu().item(),
            log_prob.cpu().item(),
        )

    def update(self, buffer: RolloutBuffer, epochs: int = 4, batch_size: int = 64) -> dict:
        """Update policy using PPO clipped surrogate.

        Returns dict of loss metrics.
        """
        data = buffer.to_tensor()
        obs = data["obs"].to(self.device)
        actions = data["actions"].to(self.device)
        old_log_probs = data["log_probs"].to(self.device)
        old_values = data["values"].to(self.device)

        advantages, returns = compute_gae(
            data["rewards"].to(self.device),
            data["dones"].to(self.device),
            old_values,
            self.gamma,
            self.gae_lambda,
        )
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        n = obs.shape[0]
        indices = np.arange(n)
        pg_losses, vf_losses, entropies = [], [], []

        for _ in range(epochs):
            np.random.shuffle(indices)
            for start in range(0, n, batch_size):
                batch = indices[start: start + batch_size]
                b_obs = obs[batch]
                b_actions = actions[batch]
                b_adv = advantages[batch]
                b_ret = returns[batch]
                b_old_log = old_log_probs[batch]

                log_prob, entropy, value = self.net.evaluate(b_obs, b_actions)

                # Clipped PPO objective
                ratio = torch.exp(log_prob - b_old_log)
                surr1 = ratio * b_adv
                surr2 = torch.clamp(ratio, 1.0 - self.clip_range, 1.0 + self.clip_range) * b_adv
                pg_loss = -torch.min(surr1, surr2).mean()

                # Value loss
                vf_loss = nn.MSELoss()(value, b_ret)

                # Entropy bonus
                entropy_loss = -entropy.mean()

                loss = pg_loss + self.vf_coef * vf_loss + self.ent_coef * entropy_loss

                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.net.parameters(), self.max_grad_norm)
                self.optimizer.step()

                pg_losses.append(pg_loss.item())
                vf_losses.append(vf_loss.item())
                entropies.append(entropy.mean().item())

        return {
            "pg_loss": float(np.mean(pg_losses)),
            "vf_loss": float(np.mean(vf_losses)),
            "entropy": float(np.mean(entropies)),
            "approx_kl": float(np.mean(
                (old_log_probs - data["log_probs"].to(self.device)).detach().cpu().numpy() ** 2
            )),
        }

    def save(self, path: str) -> None:
        torch.save(self.net.state_dict(), path)

    def load(self, path: str) -> None:
        self.net.load_state_dict(torch.load(path, map_location=self.device))
