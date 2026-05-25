"""Evaluate a trained PPO model with optional visualisation.

Usage:
    cd src && uv run python -m battle_rl.evaluate --model checkpoints/model.pt --render --games 3
"""

import argparse
import time

import numpy as np

from battle_rl.gym_env import BattleEnv
from battle_rl.ppo import PPO


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate PPO model")
    parser.add_argument("--model", type=str, required=True,
                        help="Path to .pt model weights")
    parser.add_argument("--games", type=int, default=50,
                        help="Number of evaluation games")
    parser.add_argument("--render", action="store_true",
                        help="Show board after each round")
    parser.add_argument("--opponent", type=str, default="child6",
                        choices=["child6", "sniper", "mcts_v2"],
                        help="Opponent strategy")
    args = parser.parse_args()

    env = BattleEnv()
    agent = PPO(obs_dim=env.obs_dim, action_dim=env.action_dim)
    agent.load(args.model)

    wins = 0
    total_hp_remaining = 0.0

    print(f"Evaluating {args.model} vs {args.opponent} ({args.games} games)")
    print()

    for g in range(1, args.games + 1):
        obs = env.reset()
        done = False
        step_count = 0

        while not done:
            action, _, _ = agent.act(obs)
            obs, reward, done, _ = env.step(action)
            step_count += 1

            if args.render and step_count % 3 == 0:
                print(f"\n--- Game {g}, step {step_count} ---")
                env.render(print)

        # Result
        p1_alive = any(p.is_alive for p in env.env.player1.pieces)
        p2_alive = any(p.is_alive for p in env.env.player2.pieces)
        p1_hp = sum(p.health for p in env.env.player1.pieces if p.is_alive)

        if p1_alive and not p2_alive:
            wins += 1
            total_hp_remaining += p1_hp
            result = "WIN"
        elif p2_alive and not p1_alive:
            result = "LOSS"
        else:
            result = "DRAW"

        if args.render:
            print(f"Game {g}: {result} (P1 HP remaining: {p1_hp:.0f})")
        elif g % 10 == 0:
            print(f"  {g}/{args.games} games — current WR: {wins/g:.1%}")

    wr = wins / args.games
    avg_hp = total_hp_remaining / max(wins, 1)
    print(f"\nResults ({args.games} games):")
    print(f"  Win rate:  {wr:.1%}")
    print(f"  Avg HP remaining (wins): {avg_hp:.0f}")


if __name__ == "__main__":
    main()
