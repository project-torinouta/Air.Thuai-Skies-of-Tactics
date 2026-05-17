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
