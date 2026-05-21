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

"""PPO-trained sniper strategy — policy network trained by PPO.

Uses the same STR 29 / DEX 1 build as the base sniper. The action
policy is a PyTorch network trained via PPO with behavior cloning
pretraining from the hand-coded sniper.
"""

import os
from typing import Callable, List, Optional, Tuple

import numpy as np
import torch

from env import Environment, InitGameMessage
from ml.action_decoder_ppo import decode_ppo_action
from ml.ppo import PPOPolicy
from ml.state_encoder import encode_state
from strategies._utils import allocate_init_positions
from utils import ActionSet, PieceArg, Point

_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _resolve_weights() -> Optional[str]:
    """Find PPO weights in standard locations.

    :returns: Path to weights file, or None.
    :rtype: Optional[str]
    """
    candidates = [
        "weights/ppo_latest.pt",
        os.path.join(os.path.dirname(__file__), "..", "weights", "ppo_latest.pt"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
    return None


_global_policy: Optional[PPOPolicy] = None


def load_policy(path: Optional[str] = None) -> PPOPolicy:
    """Load PPO policy from saved weights.

    :param path: Path to .pt weights. If None, searches standard locations.
    :type path: Optional[str]
    :returns: Loaded policy network.
    :rtype: PPOPolicy
    :raises FileNotFoundError: If no weights file found.
    """
    global _global_policy
    if path is not None:
        _global_policy = PPOPolicy().to(_DEVICE)
        _global_policy.load_state_dict(torch.load(path, map_location=_DEVICE))
    elif _global_policy is None:
        found = _resolve_weights()
        if found is None:
            raise FileNotFoundError(
                "No trained PPO weights found. "
                "Run `uv run python -m ml.train_ppo` first."
            )
        _global_policy = PPOPolicy().to(_DEVICE)
        _global_policy.load_state_dict(torch.load(found, map_location=_DEVICE))
    return _global_policy


def make_ppo_strategy(
    policy: Optional[PPOPolicy] = None,
) -> Tuple[Callable[..., List[PieceArg]], Callable[..., ActionSet]]:
    """Create init and action strategy functions using PPO policy.

    :param policy: PPO policy network. If None, loads from file.
    :type policy: Optional[PPOPolicy]
    :returns: ``(init_strategy, action_strategy)`` callables.
    :rtype: Tuple[Callable, Callable]
    """
    if policy is None:
        policy = load_policy()

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
        action, _, _ = policy.sample_action(state, deterministic=True)
        return decode_ppo_action(action, env)

    return init_strategy, action_strategy


def get_ppo_sniper_init_strategy() -> Callable[..., List[PieceArg]]:
    """Return the PPO-trained init strategy."""
    init_fn, _ = make_ppo_strategy()
    return init_fn


def get_ppo_sniper_action_strategy() -> Callable[..., ActionSet]:
    """Return the PPO-trained action strategy."""
    _, action_fn = make_ppo_strategy()
    return action_fn
