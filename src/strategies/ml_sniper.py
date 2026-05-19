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

"""ML-evolved sniper strategy — neural network policy evolved by CMA-ES.

Uses a tiny feedforward network (2 hidden layers, ~9K params) evolved to
make tactical decisions: target selection, positioning, advance vs hold,
and retreat threshold. Runs in microseconds per decision.

Build: STR 29, DEX 1, bow + heavy (same as sniper) — the stats are optimal,
the ML only improves tactical decisions.
"""

import os
from typing import Callable, List, Optional, Tuple

import numpy as np

from env import Environment, InitGameMessage
from ml.action_decoder import decode_action
from ml.policy_net import forward, param_count
from ml.state_encoder import encode_state, state_dim
from strategies._utils import allocate_init_positions
from utils import ActionSet, PieceArg, Point


def _resolve_weights_path() -> Optional[str]:
    """Look for trained weights in standard locations.

    :returns: Path to weights file, or None.
    :rtype: Optional[str]
    """
    candidates = [
        "weights/ml_sniper_best.npy",
        "weights/ml_sniper_latest.npy",
        os.path.join(os.path.dirname(__file__), "..", "weights", "ml_sniper_best.npy"),
        os.path.join(os.path.dirname(__file__), "..", "weights", "ml_sniper_latest.npy"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
    return None


_global_params: Optional[np.ndarray] = None


def load_weights(path: Optional[str] = None) -> np.ndarray:
    """Load policy network weights from file.

    :param path: Path to .npy weights file. If None, searches standard locations.
    :type path: Optional[str]
    :returns: Parameter vector.
    :rtype: np.ndarray
    :raises FileNotFoundError: If no weights file found.
    """
    global _global_params
    if path is not None:
        _global_params = np.load(path)
    elif _global_params is None:
        found = _resolve_weights_path()
        if found is None:
            raise FileNotFoundError(
                "No trained weights found. Run `uv run python -m ml.train_evolution` first."
            )
        _global_params = np.load(found)
    return _global_params


def make_ml_strategy(
    params: Optional[np.ndarray] = None,
) -> Tuple[Callable[..., List[PieceArg]], Callable[..., ActionSet]]:
    """Create init and action strategy functions using learned weights.

    :param params: Policy network parameters. If None, loads from file.
    :type params: Optional[np.ndarray]
    :returns: ``(init_strategy, action_strategy)`` callables.
    :rtype: Tuple[Callable, Callable]
    """
    if params is None:
        params = load_weights()

    def init_strategy(init_message: InitGameMessage) -> List[PieceArg]:
        board = init_message.board
        pid = init_message.id
        if pid == 1:
            order = [
                (x, y)
                for y in range(5, 0, -1)
                for x in range(2, board.width - 2)
            ]
        else:
            order = [
                (x, y)
                for y in range(board.height - 6, board.height)
                for x in range(board.width - 3, 2, -1)
            ]
        positions = allocate_init_positions(board, pid, init_message.piece_cnt, order)
        piece_args: List[PieceArg] = []
        for pos in positions:
            arg = PieceArg()
            arg.strength = 29
            arg.dexterity = 1
            arg.intelligence = 0
            arg.equip = Point(3, 3)
            arg.pos = pos
            piece_args.append(arg)
        return piece_args

    def action_strategy(env: Environment) -> ActionSet:
        state = encode_state(env)
        logits = forward(params, state)
        return decode_action(logits, env)

    return init_strategy, action_strategy


# Convenience accessors for benchmark.py integration

def get_ml_sniper_init_strategy() -> Callable[..., List[PieceArg]]:
    """Return the ML-evolved init strategy (loads weights from file)."""
    init_fn, _ = make_ml_strategy()
    return init_fn


def get_ml_sniper_action_strategy() -> Callable[..., ActionSet]:
    """Return the ML-evolved action strategy (loads weights from file)."""
    _, action_fn = make_ml_strategy()
    return action_fn
