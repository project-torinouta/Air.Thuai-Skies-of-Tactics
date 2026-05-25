"""PPO training entry point.

Usage:
    cd src && uv run python -m battle_rl.train --steps 50000 --save checkpoints/model.pt
"""

import argparse
import csv
import os
import time
from typing import Optional

import numpy as np

from battle_rl.gym_env import BattleEnv
from battle_rl.ppo import PPO, RolloutBuffer


def collect_trajectory(
    env: BattleEnv,
    agent: PPO,
    n_steps: int,
) -> RolloutBuffer:
    """Run the policy for *n_steps* and collect experience."""
    buffer = RolloutBuffer()
    obs = env.reset()

    for _ in range(n_steps):
        action, value, log_prob = agent.act(obs)
        next_obs, reward, done, _ = env.step(action)

        buffer.add(obs, action, reward, done, value, log_prob)

        if done:
            obs = env.reset()
        else:
            obs = next_obs

    return buffer


def evaluate(env: BattleEnv, agent: PPO, n_games: int = 10) -> float:
    """Evaluate win rate over *n_games*."""
    wins = 0
    for _ in range(n_games):
        obs = env.reset()
        done = False
        while not done:
            action, _, _ = agent.act(obs)
            obs, _, done, _ = env.step(action)
        # Check result
        if env.env is not None:
            p1_alive = any(p.is_alive for p in env.env.player1.pieces)
            p2_alive = any(p.is_alive for p in env.env.player2.pieces)
            if p1_alive and not p2_alive:
                wins += 1
    return wins / n_games


def main() -> None:
    parser = argparse.ArgumentParser(description="PPO training for THUAI9")
    parser.add_argument("--steps", type=int, default=50000,
                        help="Total timesteps (default: 50000)")
    parser.add_argument("--eval-interval", type=int, default=5000,
                        help="Evaluate every N steps (default: 5000)")
    parser.add_argument("--eval-games", type=int, default=5,
                        help="Games per evaluation (default: 5)")
    parser.add_argument("--save", type=str, default="checkpoints/ppo_model.pt",
                        help="Model save path")
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--horizon", type=int, default=512,
                        help="Steps per trajectory (default: 512)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--opponent", type=str, default="child6",
                        choices=["child6", "sniper"],
                        help="Opponent strategy")
    args = parser.parse_args()

    np.random.seed(args.seed)

    print("=" * 60)
    print("PPO Training — THUAI9 Skies of Tactics")
    print("=" * 60)
    print(f"  Opponent:   {args.opponent}")
    print(f"  Total steps: {args.steps:,}")
    print(f"  Horizon:    {args.horizon}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  Epochs:     {args.epochs}")
    print(f"  LR:         {args.lr}")
    print()

    # Environment
    env = BattleEnv(opponent_action_strategy=None)  # default child6

    # Agent
    agent = PPO(
        obs_dim=env.obs_dim,
        action_dim=env.action_dim,
        lr=args.lr,
    )

    # Logging
    os.makedirs(os.path.dirname(args.save) or ".", exist_ok=True)
    log_file = args.save.replace(".pt", "_log.csv")
    log_fp = open(log_file, "w", newline="")
    log_writer = csv.writer(log_fp)
    log_writer.writerow(["step", "win_rate", "pg_loss", "vf_loss", "entropy", "elapsed"])

    step = 0
    best_wr = 0.0
    t_start = time.time()

    while step < args.steps:
        # Collect trajectory
        t0 = time.time()
        buffer = collect_trajectory(env, agent, args.horizon)
        collect_time = time.time() - t0

        # Update
        t0 = time.time()
        metrics = agent.update(buffer, epochs=args.epochs, batch_size=args.batch_size)
        update_time = time.time() - t0

        step += args.horizon

        # Evaluate
        if step % args.eval_interval < args.horizon or step >= args.steps:
            wr = evaluate(env, agent, n_games=args.eval_games)
            elapsed = time.time() - t_start
            print(
                f"Step {step:>6d} | WR {wr:.1%} | "
                f"PG {metrics['pg_loss']:.3f} | VF {metrics['vf_loss']:.3f} | "
                f"Ent {metrics['entropy']:.3f} | "
                f"C {collect_time:.1f}s U {update_time:.1f}s"
            )

            log_writer.writerow([
                step, f"{wr:.3f}",
                f"{metrics['pg_loss']:.4f}",
                f"{metrics['vf_loss']:.4f}",
                f"{metrics['entropy']:.4f}",
                f"{elapsed:.0f}",
            ])
            log_fp.flush()

            if wr > best_wr and wr > 0.1:
                best_wr = wr
                agent.save(args.save)
                print(f"  → Saved (WR={wr:.1%})")

    log_fp.close()
    agent.save(args.save)

    elapsed = time.time() - t_start
    print(f"\nDone in {elapsed:.0f}s. Best WR: {best_wr:.1%}. Model: {args.save}")


if __name__ == "__main__":
    main()
