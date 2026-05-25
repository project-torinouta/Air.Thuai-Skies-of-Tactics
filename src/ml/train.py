"""Training loop — evolve policy network weights via ES.

Usage:
    uv run python -m ml.train --generations 50 --trials 3 --workers 4
"""

import argparse
import contextlib
import os
import sys
import time
from typing import List, Optional

import numpy as np

# Ensure we can import from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from env import Environment
from ml.action_decoder import decode_action
from ml.es_optimizer import ESOptimizer
from ml.policy_net import forward, init_params, param_count
from ml.state_encoder import encode_state
from strategies.child6 import (
    get_child6_action_strategy,
    get_child6_init_strategy,
)
from strategies.sniper import (
    get_sniper_action_strategy,
    get_sniper_init_strategy,
)
from utils import ActionSet, PieceArg, Point


WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "..", "weights")
BOARD_FILE = os.path.join(os.path.dirname(__file__), "..", "BoardCase", "case1.txt")

# Pre-load init strategies (they don't need the env to be created first)
_P1_INIT = get_sniper_init_strategy()
_P2_INIT = get_child6_init_strategy()


def play_game(params: np.ndarray, opponent_init, opponent_action, verbose: bool = False) -> int:
    """Play one game of !our (P1) vs opponent (P2).

    Returns 1 for win, 0 for loss, 0 for draw.
    """
    env = Environment(local_mode=True, if_log=0)

    p1_init_fn = lambda msg: _P1_INIT(msg)
    p1_action_fn = lambda e: _p1_action(e, params)

    env.input_manager.set_function_input_method(1, p1_init_fn, p1_action_fn)
    env.input_manager.set_function_input_method(2, opponent_init, opponent_action)

    try:
        with open(os.devnull, "w") as sink:
            with contextlib.redirect_stdout(sink):
                env.initialize(BOARD_FILE)
                while not env.is_game_over:
                    env.step()
    except Exception:
        return 0

    p1_alive = any(p.is_alive for p in env.player1.pieces)
    p2_alive = any(p.is_alive for p in env.player2.pieces)

    if p1_alive and not p2_alive:
        return 1
    if p2_alive and not p1_alive:
        return 0
    return 0  # draw


def _p1_action(env, params: np.ndarray) -> ActionSet:
    """Policy network action for player 1 (our evolved strategy)."""
    state = encode_state(env)
    logits = forward(params, state)
    return decode_action(logits, env)


def evaluate_candidate(params: np.ndarray, n_trials: int) -> float:
    """Evaluate a single candidate's win rate over *n_trials* games.

    Always plays as P1 (P2 = child6).
    """
    child6_action = get_child6_action_strategy()

    wins = 0
    for _ in range(n_trials):
        result = play_game(params, _P2_INIT, child6_action)
        wins += result

    return wins / n_trials


def evaluate_population(
    population: np.ndarray,
    n_trials: int,
    start_idx: int = 0,
) -> np.ndarray:
    """Evaluate all candidates in the population.

    :param population: (pop_size, dim) array of candidate weights.
    :param n_trials: Games per candidate.
    :param start_idx: Starting index for display.
    :returns: (pop_size,) array of win rates.
    """
    pop_size = population.shape[0]
    fitness = np.zeros(pop_size, dtype=np.float32)

    for i in range(pop_size):
        t0 = time.time()
        wr = evaluate_candidate(population[i], n_trials)
        fitness[i] = wr
        elapsed = time.time() - t0
        print(f"  [{start_idx + i + 1}/{pop_size}] win rate = {wr:.1%} ({elapsed:.1f}s)")

    return fitness


def save_weights(params: np.ndarray, name: str) -> str:
    """Save weights to the weights directory."""
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    path = os.path.join(WEIGHTS_DIR, name)
    np.save(path, params)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="ES training for THUAI9 sniper")
    parser.add_argument("--generations", type=int, default=20,
                        help="Number of ES generations (default: 20)")
    parser.add_argument("--trials", type=int, default=3,
                        help="Games per candidate per generation (default: 3)")
    parser.add_argument("--pop-size", type=int, default=16,
                        help="Population size (default: 16)")
    parser.add_argument("--sigma", type=float, default=0.15,
                        help="Initial mutation strength (default: 0.15)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--resume", type=str, default=None,
                        help="Path to .npy weights to resume from")
    args = parser.parse_args()

    dim = param_count()
    print(f"ML Sniper Training")
    print(f"  Parameters:     {dim:,}")
    print(f"  Generations:    {args.generations}")
    print(f"  Trials/gen:     {args.trials}")
    print(f"  Population:     {args.pop_size}")
    print(f"  Board:          {BOARD_FILE}")
    print()

    es = ESOptimizer(dim=dim, pop_size=args.pop_size, sigma=args.sigma, seed=args.seed)

    if args.resume:
        loaded = np.load(args.resume)
        if loaded.shape[0] == dim:
            es.mean = loaded.astype(np.float32)
            print(f"Resumed from {args.resume}")
        else:
            print(f"WARNING: {args.resume} dim mismatch ({loaded.shape[0]} vs {dim}), ignoring")

    best_ever_fitness = 0.0
    best_ever_params = None

    for gen in range(args.generations):
        print(f"\n=== Generation {gen + 1}/{args.generations} ===")
        t_start = time.time()

        population = es.ask()
        fitness = evaluate_population(population, args.trials)

        best_f, mean_f = es.tell(fitness)
        gen_time = time.time() - t_start

        print(f"  -> Gen {gen + 1}: best={best_f:.1%} mean={mean_f:.1%} "
              f"sigma_avg={float(np.mean(es.sigma)):.4f} ({gen_time:.0f}s)")

        # Track best-ever
        if best_f > best_ever_fitness:
            best_ever_fitness = best_f
            best_idx = int(np.argmax(fitness))
            best_ever_params = population[best_idx].copy()
            path = save_weights(best_ever_params, "ml_sniper_best.npy")
            print(f"  *** New best ({best_f:.1%}) saved to {path}")

        # Save latest
        path = save_weights(es.mean, "ml_sniper_latest.npy")
        print(f"  Latest mean saved to {path}")

    print(f"\n=== Training Complete ===")
    print(f"  Best ever win rate: {best_ever_fitness:.1%}")
    if best_ever_params is not None:
        path = save_weights(best_ever_params, "ml_sniper_best.npy")
        print(f"  Best weights: {path}")


if __name__ == "__main__":
    main()
