"""Policy network — tiny feedforward neural network in pure numpy.

Architecture:
- Input: 104-dim state vector from state_encoder
- Hidden 1: 64 neurons, ReLU
- Hidden 2: 32 neurons, ReLU
- Output: 6-dim action logits (see action_decoder.py)

Total parameters: 104×64 + 64 + 64×32 + 32 + 32×6 + 6 = 9,062 floats.
Forward pass: ~microseconds (pure numpy, no framework overhead).
"""

from typing import List, Optional

import numpy as np

from ml.state_encoder import state_dim


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, x)


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / (np.sum(e) + 1e-10)


def param_count() -> int:
    """Return the total number of trainable parameters.

    :returns: Parameter count.
    :rtype: int
    """
    inp = state_dim()
    h1 = 64
    h2 = 32
    out = 6
    return inp * h1 + h1 + h1 * h2 + h2 + h2 * out + out


def init_params(seed: Optional[int] = None) -> np.ndarray:
    """Initialise network weights using Xavier initialisation.

    :param seed: Random seed for reproducibility.
    :type seed: Optional[int]
    :returns: Flattened parameter vector.
    :rtype: np.ndarray
    """
    if seed is not None:
        rng = np.random.RandomState(seed)
    else:
        rng = np.random

    inp = state_dim()
    h1, h2, out = 64, 32, 6

    layers = [
        (inp, h1), (h1, h2), (h2, out),
    ]
    params: List[np.ndarray] = []
    for fan_in, fan_out in layers:
        limit = np.sqrt(6.0 / (fan_in + fan_out))
        w = rng.uniform(-limit, limit, (fan_in, fan_out)).astype(np.float32)
        b = np.zeros(fan_out, dtype=np.float32)
        params.extend([w.ravel(), b])

    return np.concatenate(params)


def forward(params: np.ndarray, state: np.ndarray) -> np.ndarray:
    """Run a forward pass through the policy network.

    :param params: Flattened parameter vector (see :func:`init_params`).
    :type params: np.ndarray
    :param state: Encoded state vector (see :func:`ml.state_encoder.encode_state`).
    :type state: np.ndarray
    :returns: 6-dim action logits.
    :rtype: np.ndarray
    """
    inp = state_dim()
    h1, h2, out = 64, 32, 6

    # Unpack weights
    idx = 0
    w1 = params[idx:idx + inp * h1].reshape(inp, h1); idx += inp * h1
    b1 = params[idx:idx + h1]; idx += h1
    w2 = params[idx:idx + h1 * h2].reshape(h1, h2); idx += h1 * h2
    b2 = params[idx:idx + h2]; idx += h2
    w3 = params[idx:idx + h2 * out].reshape(h2, out); idx += h2 * out
    b3 = params[idx:idx + out]

    h = _relu(state @ w1 + b1)
    h = _relu(h @ w2 + b2)
    logits = h @ w3 + b3
    return logits


def get_action_probs(params: np.ndarray, state: np.ndarray) -> np.ndarray:
    """Return softmax-normalised action probabilities.

    :param params: Flattened parameter vector.
    :type params: np.ndarray
    :param state: Encoded state vector.
    :type state: np.ndarray
    :returns: 6-dim probability vector summing to 1.
    :rtype: np.ndarray
    """
    return _softmax(forward(params, state))
