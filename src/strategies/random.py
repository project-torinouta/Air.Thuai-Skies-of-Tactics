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

"""Random strategy — randomly delegates to aggressive or defensive."""

from typing import Callable, List
import random

from env import InitGameMessage
from strategies.aggressive import (
    get_aggressive_init_strategy,
    get_aggressive_action_strategy,
)
from strategies.defensive import (
    get_defensive_init_strategy,
    get_defensive_action_strategy,
)
from utils import ActionSet, PieceArg


def get_random_init_strategy() -> Callable[..., List[PieceArg]]:
    """Return a random initialisation strategy.

    Randomly selects between aggressive and defensive strategies.

    :returns: A callable initialisation strategy.
    :rtype: Callable
    """
    strategies = [
        get_aggressive_init_strategy(),
        get_defensive_init_strategy(),
    ]
    return random.choice(strategies)


def get_random_action_strategy() -> Callable[..., ActionSet]:
    """Return a random action strategy.

    Randomly selects between aggressive and defensive strategies.

    :returns: A callable action strategy.
    :rtype: Callable
    """
    strategies = [
        get_aggressive_action_strategy(),
        get_defensive_action_strategy(),
    ]
    return random.choice(strategies)
