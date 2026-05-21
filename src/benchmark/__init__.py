"""Core types, strategy registry, and configuration for the benchmark suite."""

from typing import Callable, List, Tuple
from strategies.aggressive import (
    get_aggressive_action_strategy,
    get_aggressive_init_strategy,
)
from strategies.alpha_beta import get_alpha_beta_action_strategy
from strategies.defensive import (
    get_defensive_action_strategy,
    get_defensive_init_strategy,
)
from strategies.mcts import get_mcts_action_strategy
from ml.mcts_improved import get_improved_mcts_strategy
from strategies.random import (
    get_random_action_strategy,
    get_random_init_strategy,
)
from strategies.tactical import (
    get_tactical_action_strategy,
    get_tactical_init_strategy,
)
from strategies.sniper_v102 import (
    get_sniper_init_strategy_v102,
    get_sniper_action_strategy_v102,
)
from strategies.sniper_v103 import (
    get_sniper_init_strategy_v103,
    get_sniper_action_strategy_v103,
)
from strategies.sniper import (
    get_sniper_action_strategy,
    get_sniper_init_strategy,
)
from strategies.sniper_tactical import (
    get_sniper_tactical_action_strategy,
    get_sniper_tactical_init_strategy,
)
from strategies.ml_sniper import (
    get_ml_sniper_action_strategy,
    get_ml_sniper_init_strategy,
)
from strategies.ppo_sniper import (
    get_ppo_sniper_action_strategy,
    get_ppo_sniper_init_strategy,
)
from strategies.warrior import (
    get_warrior_action_strategy,
    get_warrior_init_strategy,
    get_ranger_action_strategy,
    get_ranger_init_strategy,
)
from utils import ActionSet, PieceArg


StrategyPair = Tuple[Callable[..., List[PieceArg]], Callable[..., ActionSet]]

STRATEGY_NAMES: List[str] = [
    "aggressive",
    "defensive",
    "mcts",
    "mcts_improved",
    "alpha_beta",
    "tactical",
    "warrior",
    "ranger",
    "random",
    "sniper",
    "sniper_tactical",
    "sniper_v102",
    "sniper_v103",
    "ml_sniper",
    "ppo_sniper",
]

INIT_NAMES: List[str] = [
    "aggressive",
    "defensive",
    "tactical",
    "warrior",
    "ranger",
    "random",
    "sniper",
    "sniper_tactical",
    "sniper_v102",
    "sniper_v103",
    "ml_sniper",
    "ppo_sniper",
]

ACTION_NAMES: List[str] = [
    "aggressive",
    "defensive",
    "mcts",
    "mcts_improved",
    "alpha_beta",
    "tactical",
    "warrior",
    "ranger",
    "random",
    "sniper",
    "sniper_tactical",
    "sniper_v102",
    "sniper_v103",
    "ml_sniper",
    "ppo_sniper",
]


def get_init_strategy(name: str) -> Callable[..., List[PieceArg]]:
    """Resolve a strategy name to an init strategy callable.

    :param name: Strategy name from INIT_NAMES.
    :type name: str
    :returns: An initialisation strategy callable.
    :rtype: Callable
    :raises ValueError: If the name is unknown.
    """
    if name == "aggressive":
        return get_aggressive_init_strategy()
    if name == "defensive":
        return get_defensive_init_strategy()
    if name == "tactical":
        return get_tactical_init_strategy()
    if name == "warrior":
        return get_warrior_init_strategy()
    if name == "ranger":
        return get_ranger_init_strategy()
    if name == "sniper":
        return get_sniper_init_strategy()
    if name == "sniper_tactical":
        return get_sniper_tactical_init_strategy()
    if name == "sniper_v102":
        return get_sniper_init_strategy_v102()
    if name == "sniper_v103":
        return get_sniper_init_strategy_v103()
    if name == "ml_sniper":
        return get_ml_sniper_init_strategy()
    if name == "ppo_sniper":
        return get_ppo_sniper_init_strategy()
    if name == "random":
        return get_random_init_strategy()
    raise ValueError(f"Unknown init strategy: {name}")


def get_action_strategy(
    name: str,
    mcts_simulations: int = 10,
    alpha_beta_depth: int = 3,
) -> Callable[..., ActionSet]:
    """Resolve a strategy name to an action strategy callable.

    :param name: Strategy name from ACTION_NAMES.
    :type name: str
    :param mcts_simulations: MCTS simulation count (only for mcts). Defaults to 10.
    :type mcts_simulations: int
    :param alpha_beta_depth: Alpha-beta search depth (only for alpha_beta).
        Defaults to 3.
    :type alpha_beta_depth: int
    :returns: An action strategy callable.
    :rtype: Callable
    :raises ValueError: If the name is unknown.
    """
    if name == "aggressive":
        return get_aggressive_action_strategy()
    if name == "defensive":
        return get_defensive_action_strategy()
    if name == "mcts":
        return get_mcts_action_strategy(mcts_simulations)
    if name == "mcts_improved":
        return get_improved_mcts_strategy(simulation_count=200)
    if name == "alpha_beta":
        return get_alpha_beta_action_strategy(alpha_beta_depth)
    if name == "tactical":
        return get_tactical_action_strategy()
    if name == "warrior":
        return get_warrior_action_strategy()
    if name == "ranger":
        return get_ranger_action_strategy()
    if name == "sniper":
        return get_sniper_action_strategy()
    if name == "sniper_tactical":
        return get_sniper_tactical_action_strategy()
    if name == "sniper_v102":
        return get_sniper_action_strategy_v102()
    if name == "sniper_v103":
        return get_sniper_action_strategy_v103()
    if name == "ml_sniper":
        return get_ml_sniper_action_strategy()
    if name == "ppo_sniper":
        return get_ppo_sniper_action_strategy()
    if name == "random":
        return get_random_action_strategy()
    raise ValueError(f"Unknown action strategy: {name}")


def get_strategy_pair(
    name: str,
    mcts_simulations: int = 10,
    alpha_beta_depth: int = 3,
) -> StrategyPair:
    """Resolve a strategy name to an (init_fn, action_fn) pair.

    :param name: Strategy name from STRATEGY_NAMES.
    :type name: str
    :param mcts_simulations: MCTS simulation count (only for mcts). Defaults to 10.
    :type mcts_simulations: int
    :param alpha_beta_depth: Alpha-beta search depth (only for alpha_beta).
        Defaults to 3.
    :type alpha_beta_depth: int
    :returns: A tuple of (init_strategy, action_strategy) callables.
    :rtype: StrategyPair
    :raises ValueError: If the strategy name is unknown.
    """
    if name in INIT_NAMES:
        init_fn = get_init_strategy(name)
    else:
        from strategies.defensive import get_defensive_init_strategy
        init_fn = get_defensive_init_strategy()
    return (init_fn, get_action_strategy(name, mcts_simulations, alpha_beta_depth))
