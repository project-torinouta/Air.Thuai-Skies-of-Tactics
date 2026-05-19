"""Train a policy network using Evolution Strategies (parallel).

Evaluates candidates in parallel across CPU cores. Each candidate plays
``--trials`` games on randomly selected boards. The population mean is
saved after every generation.

Usage:
    uv run python -m ml.train_evolution --generations 200 --pop-size 16 --trials 11
    uv run python -m ml.train_evolution --generations 10 --pop-size 4 --trials 3  # smoke
"""

import argparse
import concurrent.futures
import glob
import os
import sys
import time
from typing import List, Tuple

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ml.es_optimizer import ESOptimizer
from ml.policy_net import init_params, param_count


WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "..", "weights")


def _ensure_weights_dir() -> None:
    os.makedirs(WEIGHTS_DIR, exist_ok=True)


def _eval_one(params: np.ndarray, board: str, p2_name: str, seed: int) -> float:
    """Play one game and return 1 for win, 0 for loss/draw.

    :param params: Policy network weights.
    :param board: Board file path.
    :param p2_name: Opponent strategy name.
    :param seed: Random seed.
    :returns: 1.0 if win, 0.0 otherwise.
    """
    from env import Environment
    from strategies.ml_sniper import make_ml_strategy
    from benchmark import run_single_game
    import contextlib

    p1_init, p1_action = make_ml_strategy(params)

    if p2_name == "sniper":
        from strategies.sniper import get_sniper_init_strategy, get_sniper_action_strategy
        p2_init, p2_action = get_sniper_init_strategy(), get_sniper_action_strategy()
    else:
        from benchmark import get_init_strategy, get_action_strategy
        p2_init, p2_action = get_init_strategy(p2_name), get_action_strategy(p2_name)

    import random as _random
    _random.seed(seed)

    env = Environment(local_mode=True, if_log=0)
    env.max_rounds = 60

    with open(os.devnull, "w") as devnull:
        with contextlib.redirect_stdout(devnull):
            result = run_single_game(board, (p1_init, p1_action), (p2_init, p2_action),
                                     env.max_rounds, verbose=False)
    return 1.0 if result == 1 else 0.0


def evaluate_candidate(
    params: np.ndarray,
    p2_name: str,
    n_games: int,
    boards: List[str],
    base_seed: int,
) -> float:
    """Evaluate a single candidate across n_games.

    :param params: Policy network weights.
    :param p2_name: Opponent strategy name.
    :param n_games: Number of games to play.
    :param boards: Available board files (cycled through).
    :param base_seed: Base random seed.
    :returns: Win rate (0.0 to 1.0).
    """
    wins = 0.0
    for g in range(n_games):
        board = boards[g % len(boards)]
        wins += _eval_one(params, board, p2_name, base_seed + g)
    return wins / n_games


def evaluate_population(
    pop: np.ndarray,
    p2_name: str,
    n_games: int,
    boards: List[str],
    base_seed: int,
    max_workers: int,
) -> np.ndarray:
    """Evaluate all candidates in parallel.

    :param pop: Array of shape ``(pop_size, dim)``.
    :param p2_name: Opponent strategy name.
    :param n_games: Games per candidate.
    :param boards: Available board files.
    :param base_seed: Base seed.
    :param max_workers: Max parallel workers.
    :returns: Fitness array of shape ``(pop_size,)``.
    """
    fitness = np.zeros(len(pop), dtype=np.float32)

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = {}
        for i in range(len(pop)):
            fut = pool.submit(evaluate_candidate, pop[i], p2_name,
                              n_games, boards, base_seed + i * 10000)
            futures[fut] = i

        for fut in concurrent.futures.as_completed(futures):
            i = futures[fut]
            try:
                fitness[i] = fut.result()
            except Exception as e:
                print(f"  [worker {i}] failed: {e}", flush=True)
                fitness[i] = 0.0

    return fitness


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ES training for THUAI9 (parallel)")
    parser.add_argument("--generations", type=int, default=200,
                        help="Number of generations (default: 200)")
    parser.add_argument("--pop-size", type=int, default=16,
                        help="Population per generation (default: 16)")
    parser.add_argument("--trials", type=int, default=11,
                        help="Games per candidate (default: 11)")
    parser.add_argument("--opponent", type=str, default="sniper",
                        help="Opponent strategy (default: sniper)")
    parser.add_argument("--board-dir", type=str,
                        default=os.path.join(os.path.dirname(__file__), "..", "BoardCase"),
                        help="Board directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--workers", type=int, default=0,
                        help="Parallel workers (0 = use all CPUs)")
    parser.add_argument("--resume", type=str, default=None,
                        help="Load mean weights to resume from")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _ensure_weights_dir()

    dim = param_count()
    workers = args.workers if args.workers > 0 else os.cpu_count() or 4
    np.random.seed(args.seed)

    # Discover boards
    boards = sorted(glob.glob(os.path.join(args.board_dir, "*.txt")))
    if not boards:
        boards = [os.path.join(args.board_dir, "case1.txt")]
    print(f"Policy: {dim} params, State: 104 dim, Workers: {workers}")
    print(f"Generations: {args.generations}, Pop: {args.pop_size}, Trials: {args.trials}")
    print(f"Opponent: {args.opponent}, Boards: {len(boards)}, Seed: {args.seed}")
    print()

    es = ESOptimizer(dim, pop_size=args.pop_size, sigma=0.2, seed=args.seed)

    if args.resume and os.path.exists(args.resume):
        es.mean = np.load(args.resume)
        print(f"Resumed mean from {args.resume}")

    best_overall = -1.0
    best_params = None
    t_start = time.time()

    for gen in range(args.generations):
        pop = es.ask()

        t0 = time.time()
        fitness = evaluate_population(
            pop, args.opponent, args.trials, boards,
            args.seed + gen * 100000, workers,
        )
        dt_eval = time.time() - t0

        best_f, mean_f = es.tell(fitness)
        elapsed = time.time() - t_start

        # Reset sigma if collapsed
        mean_sigma = float(np.mean(es.sigma))
        if mean_sigma < 0.005:
            es.sigma = np.full_like(es.sigma, 0.1)
            print(f"  → sigma reset to 0.1 (was {mean_sigma:.4f})")

        print(f"Gen {gen:3d}: best={best_f:.3f} mean={mean_f:.3f} "
              f"sigma={mean_sigma:.4f} "
              f"eval={dt_eval:.0f}s total={elapsed:.0f}s")

        for i in np.argsort(fitness)[-3:]:
            print(f"  top3: idx={i} fitness={fitness[i]:.3f}")

        if best_f > best_overall:
            best_overall = best_f
            best_params = es.mean.copy()
            path = os.path.join(WEIGHTS_DIR, f"ml_sniper_{gen:03d}.npy")
            np.save(path, es.mean)
            np.save(os.path.join(WEIGHTS_DIR, "ml_sniper_latest.npy"), es.mean)
            print(f"  → New best: {path} ({best_overall:.3f})")

    print(f"\nDone. Best fitness: {best_overall:.3f}")
    if best_params is not None:
        np.save(os.path.join(WEIGHTS_DIR, "ml_sniper_best.npy"), best_params)
        print(f"Best weights saved to weights/ml_sniper_best.npy")


if __name__ == "__main__":
    main()
