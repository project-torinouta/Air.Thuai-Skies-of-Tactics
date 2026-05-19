"""Data models for benchmark results and game statistics."""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class GameResult:
    """Outcome of a single game.

    :param result: 0=draw, 1=P1 wins, 2=P2 wins, -1=error.
    :type result: int
    :param rounds: Total rounds played.
    :type rounds: int
    :param first_blood: Round of the first death, or -1 if none.
    :type first_blood: int
    :param survivors_p1: Number of surviving pieces for player 1.
    :type survivors_p1: int
    :param survivors_p2: Number of surviving pieces for player 2.
    :type survivors_p2: int
    """

    result: int
    rounds: int
    first_blood: int = -1
    survivors_p1: int = 0
    survivors_p2: int = 0


@dataclass
class MatchupSeries:
    """Aggregated data from a series of games between two strategies.

    :param results: Per-game result (0=draw, 1=P1 wins, 2=P2 wins).
    :type results: List[int]
    :param lengths: Per-game round counts.
    :type lengths: List[int]
    :param first_bloods: Per-game first-blood round (-1 if none).
    :type first_bloods: List[int]
    :param survivors: Per-game ``(survivors_p1, survivors_p2)``.
    :type survivors: List[Tuple[int, int]]
    """

    results: List[int] = field(default_factory=list)
    lengths: List[int] = field(default_factory=list)
    first_bloods: List[int] = field(default_factory=list)
    survivors: List[Tuple[int, int]] = field(default_factory=list)
