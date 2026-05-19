"""Simple evolution strategies (ES) optimizer — no external dependencies.

Implements a basic ES with a population sampled from a multivariate Gaussian.
The mean and diagonal covariance are updated using the top-k fitness samples.

Simplified CMA-ES suitable for ~10⁴-dimensional problems. Uses diagonal
covariance to guarantee positive-definiteness.
"""

from typing import Optional, Tuple

import numpy as np


class ESOptimizer:
    """Evolution Strategies optimizer with adaptive diagonal covariance."""

    def __init__(
        self,
        dim: int,
        pop_size: int = 20,
        sigma: float = 0.1,
        seed: Optional[int] = None,
    ) -> None:
        """Initialise the ES optimizer.

        :param dim: Number of parameters to optimise.
        :type dim: int
        :param pop_size: Population size per generation.
        :type pop_size: int
        :param sigma: Initial step size (standard deviation for sampling).
        :type sigma: float
        :param seed: Random seed.
        :type seed: Optional[int]
        """
        self.dim = dim
        self.pop_size = pop_size
        self.base_sigma = sigma
        self.rng = np.random.RandomState(seed) if seed is not None else np.random

        self.mean = self.rng.randn(dim).astype(np.float32) * 0.1
        self.sigma = np.full(dim, sigma, dtype=np.float32)

        self.elite_frac = 0.25
        self.lr_mean = 0.5
        self.lr_sigma = 0.2
        self._recent_pop = np.zeros((pop_size, dim), dtype=np.float32)

    def ask(self) -> np.ndarray:
        """Sample a population of candidate parameter vectors.

        :returns: Array of shape ``(pop_size, dim)``.
        :rtype: np.ndarray
        """
        noise = self.rng.randn(self.pop_size, self.dim).astype(np.float32)
        samples = self.mean + noise * self.sigma
        self._recent_pop = samples
        return samples

    def tell(self, fitness: np.ndarray) -> Tuple[float, float]:
        """Update the distribution based on fitness scores.

        :param fitness: Fitness array of shape ``(pop_size,)``.
            Higher = better.
        :type fitness: np.ndarray
        :returns: ``(best_fitness, mean_fitness)`` for the generation.
        :rtype: Tuple[float, float]
        """
        n_elite = max(1, int(self.pop_size * self.elite_frac))
        elite_idx = np.argsort(fitness)[-n_elite:]

        elite_params = self._recent_pop[elite_idx]
        elite_fitness = fitness[elite_idx]

        # Weighted update toward elite (softmax weights)
        weights = np.exp(elite_fitness - np.max(elite_fitness))
        weights /= np.sum(weights) + 1e-10

        # Compute weighted elite center
        elite_center = np.sum(elite_params * weights.reshape(-1, 1), axis=0)

        # Update mean
        self.mean = (1.0 - self.lr_mean) * self.mean + self.lr_mean * elite_center

        # Update per-dim sigma (std) from elite deviations
        deviations = elite_params - self.mean
        weighted_var = np.sum(deviations ** 2 * weights.reshape(-1, 1), axis=0)
        target_sigma = np.sqrt(weighted_var + 1e-8)
        self.sigma = ((1.0 - self.lr_sigma) * self.sigma
                      + self.lr_sigma * target_sigma)
        # Clamp sigma to prevent collapse or explosion
        self.sigma = np.clip(self.sigma, self.base_sigma * 0.01, self.base_sigma * 5.0)

        best_f = float(np.max(fitness))
        mean_f = float(np.mean(fitness))
        return best_f, mean_f
