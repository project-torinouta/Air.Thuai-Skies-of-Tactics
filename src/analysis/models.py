"""Data models for parsed replay data."""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class SoldierInit:
    """Initial configuration of a single soldier piece.

    :param id: Piece ID.
    :type id: int
    :param soldier_type: Numeric soldier type (1-4).
    :type soldier_type: int
    :param camp: "Red" or "Blue".
    :type camp: str
    :param x: Initial x-coordinate.
    :type x: int
    :param z: Initial z-coordinate (row).
    :type z: int
    :param strength: STR attribute.
    :type strength: int
    :param intelligence: INT attribute.
    :type intelligence: int
    :param health: Initial HP.
    :type health: int
    """

    id: int
    soldier_type: int
    camp: str
    x: int
    z: int
    strength: int
    intelligence: int
    health: int

    @property
    def dexterity(self) -> int:
        """Infer DEX from remaining attribute budget (30)."""
        return 30 - self.strength - self.intelligence

    @property
    def weapon_name(self) -> str:
        """Human-readable weapon name."""
        return {1: "longsword", 2: "shortsword", 3: "bow", 4: "staff"}.get(
            self.soldier_type, f"unknown({self.soldier_type})",
        )


@dataclass
class RoundAction:
    """A single action in a round.

    :param round_number: Round number.
    :type round_number: int
    :param action_type: "Movement", "Attack", "Death", "Spell".
    :type action_type: str
    :param soldier_id: Acting piece ID.
    :type soldier_id: int
    :param target_id: Target piece ID (for Attack/Spell).
    :type target_id: int
    :param path: Movement path waypoints as ``[(x, z), ...]``.
    :type path: List[Tuple[int, int]]
    :param damage: Damage dealt (for Attack).
    :type damage: int
    """

    round_number: int
    action_type: str
    soldier_id: int
    target_id: int = -1
    path: List[Tuple[int, int]] = field(default_factory=list)
    damage: int = 0


@dataclass
class RoundSnapshot:
    """Full state snapshot at the end of a round.

    :param round_number: Round number.
    :type round_number: int
    :param positions: ``{soldier_id: (x, z)}`` for alive pieces.
    :type positions: Dict[int, Tuple[int, int]]
    :param hp: ``{soldier_id: health}`` for alive pieces.
    :type hp: Dict[int, int]
    :param is_end: Whether this is the final round.
    :type is_end: bool
    """

    round_number: int
    positions: Dict[int, Tuple[int, int]] = field(default_factory=dict)
    hp: Dict[int, int] = field(default_factory=dict)
    is_end: bool = False


@dataclass
class ParsedReplay:
    """Fully parsed replay with all indicators.

    :param match_id: Saiblo match ID.
    :type match_id: int
    :param opponent: Opponent username (inferred from filename).
    :type opponent: str
    :param map_width: Board width.
    :type map_width: int
    :param soldiers: Initial soldier configs.
    :type soldiers: List[SoldierInit]
    :param rounds: Round snapshots.
    :type rounds: List[RoundSnapshot]
    :param actions: All actions across all rounds.
    :type actions: List[RoundAction]
    :param winner: Winning camp ("Red", "Blue", or "Draw").
    :type winner: str
    :param ashgrey_camp: Which camp ashgrey played.
    :type ashgrey_camp: str
    """

    match_id: int
    opponent: str
    map_width: int
    soldiers: List[SoldierInit] = field(default_factory=list)
    rounds: List[RoundSnapshot] = field(default_factory=list)
    actions: List[RoundAction] = field(default_factory=list)
    winner: str = "Draw"
    ashgrey_camp: str = "Red"
