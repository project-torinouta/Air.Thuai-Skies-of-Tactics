"""Train a policy network using Evolution Strategies.

Usage:
    uv run python -m ml.train_evolution              # Full training (100 gen)
    uv run python -m ml.train_evolution --generations 10 --trials 2   # Smoke test

Output:
    Saves best weights to ``weights/ml_sniper_{gen}.npy`` after each generation.
    The latest weights are always at ``weights/ml_sniper_latest.npy``.
"""

import argparse
import os
import sys
import time
from typing import List

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ml.es_optimizer import ESOptimizer
from ml.policy_net import forward, init_params, param_count
from ml.state_encoder import encode_state, state_dim
from ml.action_decoder import decode_action


WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "..", "weights")


def _ensure_weights_dir() -> None:
    os.makedirs(WEIGHTS_DIR, exist_ok=True)


def _evaluate_candidate(
    params: np.ndarray,
    p2_strategy_name: str,
    n_games: int,
    board_dir: str,
    seed: int,
) -> float:
    """Play n_games against a fixed opponent and return win rate.

    :param params: Flattened policy network parameters.
    :type params: np.ndarray
    :param p2_strategy_name: Opponent strategy name for benchmark.py.
    :type p2_strategy_name: str
    :param n_games: Number of games to play.
    :type n_games: int
    :param board_dir: Board directory.
    :type board_dir: str
    :param seed: Random seed.
    :type seed: int
    :returns: Win rate (0.0 to 1.0).
    :rtype: float
    """
    # Run benchmark with a subprocess calling benchmark.py
    # We use --p1 random as a placeholder and hook into the game via a custom env
    from env import Environment
    from strategies.sniper import get_sniper_init_strategy, get_sniper_action_strategy
    import contextlib

    # Create our strategy that uses the learned params
    from strategies.ml_sniper import make_ml_strategy
    p1_init, p1_action = make_ml_strategy(params)

    # Get opponent strategy
    if p2_strategy_name == "sniper":
        p2_init = get_sniper_init_strategy()
        p2_action = get_sniper_action_strategy()
    elif p2_strategy_name == "sniper_v103":
        from strategies.sniper_v103 import get_sniper_init_strategy_v103, get_sniper_action_strategy_v103
        p2_init = get_sniper_init_strategy_v103()
        p2_action = get_sniper_action_strategy_v103()
    else:
        from benchmark import get_init_strategy, get_action_strategy
        p2_init = get_init_strategy(p2_strategy_name)
        p2_action = get_action_strategy(p2_strategy_name)

    wins = 0
    for game in range(n_games):
        env = Environment(local_mode=True, if_log=0)
        env.max_rounds = 60

        from benchmark import run_single_game
        # Import glob to find board files
        import glob
        boards = sorted(glob.glob(os.path.join(board_dir, "*.txt")))
        if not boards:
            boards = [os.path.join(board_dir, "case1.txt")]
        board_file = boards[game % len(boards)]

        with open(os.devnull, "w") as devnull:
            with contextlib.redirect_stdout(devnull):
                from benchmark import run_single_game as rsg
                result = rsg(
                    board_file,
                    (p1_init, p1_action),
                    (p2_init, p2_action),
                    env.max_rounds,
                    verbose=False,
                )
        if result == 1:
            wins += 1
        elif result == -1:
            # Error — count as loss
            pass

    return wins / max(n_games, 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ES training for THUAI9")
    parser.add_argument("--generations", type=int, default=100,
                        help="Number of generations (default: 100)")
    parser.add_argument("--pop-size", type=int, default=16,
                        help="Population per generation (default: 16)")
    parser.add_argument("--trials", type=int, default=3,
                        help="Games per candidate evaluation (default: 3)")
    parser.add_argument("--opponent", type=str, default="sniper",
                        help="Opponent strategy (default: sniper)")
    parser.add_argument("--board-dir", type=str,
                        default=os.path.join(os.path.dirname(__file__), "..", "BoardCase"),
                        help="Board directory (default: BoardCase/)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--resume", type=str, default=None,
                        help="Load weights from file to resume training")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _ensure_weights_dir()

    dim = param_count()
    print(f"Policy network: {dim} parameters")
    print(f"State dimension: {state_dim()}")
    print(f"Generations: {args.generations}, Population: {args.pop_size}, "
          f"Trials per candidate: {args.trials}")
    print(f"Opponent: {args.opponent}")
    print()

    if args.resume and os.path.exists(args.resume):
        mean = np.load(args.resume)
        es = ESOptimizer(dim, pop_size=args.pop_size, seed=args.seed)
        es.mean = mean
        print(f"Resumed from {args.resume}")
    else:
        es = ESOptimizer(dim, pop_size=args.pop_size, seed=args.seed)

    best_overall = -1.0
    best_params = None

    for gen in range(args.generations):
        t0 = time.time()
        pop = es.ask()
        es._store_pop(pop)

        fitness = np.zeros(args.pop_size, dtype=np.float32)
        for i in range(args.pop_size):
            t1 = time.time()
            wr = _evaluate_candidate(
                pop[i], args.opponent, args.trials, args.board_dir, args.seed + gen * args.pop_size + i
            )
            fitness[i] = wr
            dt = time.time() - t1
            print(f"  [{gen:3d}/{i:2d}] fitness={wr:.2f} ({dt:.1f}s)", flush=True)

        best_f, mean_f = es.tell(fitness)
        dt = time.time() - t0
        print(f"Gen {gen:3d}: best={best_f:.3f}, mean={mean_f:.3f}, "
              f"sigma={es.sigma:.4f}, time={dt:.0f}s")

        if best_f > best_overall:
            best_overall = best_f
            best_params = es.mean.copy()
            path = os.path.join(WEIGHTS_DIR, f"ml_sniper_{gen:03d}.npy")
            np.save(path, es.mean)
            np.save(os.path.join(WEIGHTS_DIR, "ml_sniper_latest.npy"), es.mean)
            print(f"  → New best saved to {path}")

        if best_f >= 1.0:
            print("Perfect fitness achieved! Stopping early.")
            break

    print(f"\nDone. Best fitness: {best_overall:.3f}")
    if best_params is not None:
        final_path = os.path.join(WEIGHTS_DIR, "ml_sniper_best.npy")
        np.save(final_path, best_params)
        print(f"Best weights saved to {final_path}")


if __name__ == "__main__":
    main()
