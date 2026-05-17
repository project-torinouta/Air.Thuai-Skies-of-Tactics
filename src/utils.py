# Copyright 2026 saiblo platform <https://saiblo.net>
#
# This SDK copy is distributed from https://api.saiblo.net/api/games/56/download/,
# All rights reserved by saiblo platform. All I modified is translating the
# comment and document string from Chinese to English

"""Core data types and enumerations for the THUAI9 game.

This module defines the fundamental data structures used throughout the
game client, including points, actions, spells, and their associated
enumerations. All game-logic modules build upon these types.
"""

from enum import Enum
from typing import Any, List, Optional


class Point:
    """A 2D coordinate on the game board.

    :param x: The x-coordinate (column). Defaults to 0.
    :type x: int
    :param y: The y-coordinate (row). Defaults to 0.
    :type y: int
    """

    def __init__(self, x: int = 0, y: int = 0) -> None:
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"Point({self.x}, {self.y})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))


class ActionSet:
    """Container for a complete action in one turn (move, attack, spell).

    Each action field must be explicitly set to True/False before use,
    as these attributes are not populated by the constructor.
    """

    def __init__(self) -> None:
        self.move_target: Point = Point()
        self.attack: bool = False
        self.attack_context: Optional[AttackContext] = None
        self.spell: bool = False
        self.spell_context: Optional[SpellContext] = None

    def __str__(self) -> str:
        """Return a human-readable representation of this action set.

        :returns: A multi-line string describing move, attack, and spell.
        :rtype: str
        """
        parts = []

        if hasattr(self, "move_target"):
            parts.append(f"move_target: ({self.move_target.x}, {self.move_target.y})")

        if hasattr(self, "attack"):
            parts.append(f"attack: {'yes' if self.attack else 'no'}")
            if self.attack and self.attack_context:
                parts.append("  attack_context:")
                ctx = self.attack_context
                if ctx.attacker is not None:
                    parts.append(f"    attacker_id: {ctx.attacker.id}")
                if ctx.target is not None:
                    parts.append(f"    target_id: {ctx.target.id}")
                if hasattr(ctx, "damage_dealt"):
                    parts.append(f"    damage: {ctx.damage_dealt}")

        if hasattr(self, "spell"):
            parts.append(f"spell: {'yes' if self.spell else 'no'}")
            if self.spell and self.spell_context:
                parts.append("  spell_context:")
                ctx = self.spell_context
                if ctx.spell is not None:
                    parts.append(f"    name: {ctx.spell.name}")
                    parts.append(f"    effect_type: {ctx.spell.effect_type}")
                    parts.append(f"    base_value: {ctx.spell.base_value}")
                if ctx.target is not None:
                    parts.append(f"    target_id: {ctx.target.id}")
                if ctx.target_area is not None:
                    parts.append(
                        f"    target_area: ({ctx.target_area.x}, "
                        f"{ctx.target_area.y}), radius: {ctx.target_area.radius}"
                    )

        return "\n".join(parts)


class InitializationSet:
    """Initialisation parameters for a single piece.

    :param strength: The strength attribute. Defaults to 0.
    :type strength: int
    :param dexterity: The dexterity attribute. Defaults to 0.
    :type dexterity: int
    :param intelligence: The intelligence attribute. Defaults to 0.
    :type intelligence: int
    :param weapon: The weapon type (1=longsword, 2=shortsword, 3=bow, 4=staff).
        Defaults to 0.
    :type weapon: int
    :param armor: The armour type (1=light, 2=medium, 3=heavy). Defaults to 0.
    :type armor: int
    :param position: The initial position on the board. Defaults to origin.
    :type position: Point
    """

    def __init__(
        self,
        strength: int = 0,
        dexterity: int = 0,
        intelligence: int = 0,
        weapon: int = 0,
        armor: int = 0,
        position: Optional[Point] = None,
    ) -> None:
        self.strength = strength
        self.dexterity = dexterity
        self.intelligence = intelligence
        self.weapon = weapon
        self.armor = armor
        self.position = position if position is not None else Point()

    def to_dict(self) -> dict:
        """Serialise this initialisation set to a dictionary.

        :returns: A dict with keys strength, dexterity, intelligence,
            weapon, armor, and position.
        :rtype: dict
        """
        return {
            "strength": self.strength,
            "dexterity": self.dexterity,
            "intelligence": self.intelligence,
            "weapon": self.weapon,
            "armor": self.armor,
            "position": {"x": self.position.x, "y": self.position.y},
        }

    @staticmethod
    def from_dict(data: dict) -> "InitializationSet":
        """Create an InitializationSet from a dictionary.

        :param data: The dictionary containing initialisation data.
        :type data: dict
        :returns: A new InitializationSet instance.
        :rtype: InitializationSet
        """
        pos_data = data.get("position")
        position = Point(pos_data["x"], pos_data["y"]) if pos_data else Point()
        return InitializationSet(
            strength=data.get("strength", 0),
            dexterity=data.get("dexterity", 0),
            intelligence=data.get("intelligence", 0),
            weapon=data.get("weapon", 0),
            armor=data.get("armor", 0),
            position=position,
        )


class PieceArg:
    """Parameters for initialising a single piece on the board."""

    def __init__(self) -> None:
        self.strength: int = 0
        self.intelligence: int = 0
        self.dexterity: int = 0
        self.equip: Point = Point()
        self.pos: Point = Point()


class InitPolicyMessage:
    """Message carrying the initialisation policy for a player's pieces."""

    def __init__(self) -> None:
        self.piece_args: List[PieceArg] = []


class AttackContext:
    """Context data for an attack action.

    Records the attacker, target, damage dealt, and associated metadata
    for a single attack attempt.
    """

    def __init__(self) -> None:
        self.attacker: Optional[Any] = None  # Piece
        self.target: Optional[Any] = None  # Piece
        self.attack_type: Optional[AttackType] = None
        self.is_critical: bool = False
        self.damage_dealt: int = 0
        self.is_hit: bool = False
        self.advantage_value: int = 0
        self.attack_position: Point = Point()
        self.attack_roll: int = 0
        self.defense_value: int = 0
        self.caused_death: bool = False
        self.death_roll: int = 0


class AttackType(Enum):
    """Enumeration of attack types."""

    PHYSICAL = "Physical"
    SPELL = "Spell"
    EXCELLENCE = "Excellence"


class SpellContext:
    """Context data for a spell cast.

    Records the caster, target, spell details, area of effect, and
    associated metadata for a single spell cast.
    """

    def __init__(self) -> None:
        self.caster: Optional[Any] = None  # Piece
        self.spell: Optional[Spell] = None
        self.spell_power: int = 0
        self.target_type: Optional[TargetType] = None
        self.target: Optional[Any] = None  # Piece
        self.target_area: Optional[Area] = None
        self.spell_range: float = 0.0
        self.effect_type: Optional[SpellEffectType] = None
        self.damage_type: Optional[DamageType] = None
        self.damage_value: int = 0
        self.heal_value: int = 0
        self.effect_value: int = 0
        self.is_delay_spell: bool = False
        self.base_lifespan: int = 0
        self.spell_lifespan: int = 0
        self.is_damage_spell: bool = False
        self.is_area_effect: bool = False
        self.is_locking_spell: bool = False
        self.spell_cost: int = 0
        self.action_cost: int = 0
        self.is_hit: bool = False
        self.is_critical: bool = False


class TargetType(Enum):
    """Enumeration of spell target types."""

    SINGLE = "Single"
    AREA = "Area"
    SELF = "Self"
    CHAIN = "Chain"


class SpellEffectType(Enum):
    """Enumeration of spell effect types."""

    DAMAGE = "Damage"
    HEAL = "Heal"
    BUFF = "Buff"
    DEBUFF = "Debuff"
    MOVE = "Move"


class DamageType(Enum):
    """Enumeration of damage types."""

    FIRE = "Fire"
    ICE = "Ice"
    LIGHTNING = "Lightning"
    PHYSICAL = "Physical"
    PURE = "Pure"
    NONE = "None"


class Area:
    """A circular area on the game board.

    :param x: The x-coordinate of the centre. Defaults to 0.
    :type x: int
    :param y: The y-coordinate of the centre. Defaults to 0.
    :type y: int
    :param radius: The radius in Manhattan distance. Defaults to 0.
    :type radius: int
    """

    def __init__(self, x: int = 0, y: int = 0, radius: int = 0) -> None:
        self.x = x
        self.y = y
        self.radius = radius

    def contains(self, point: Point) -> bool:
        """Check whether a point lies within this area (Manhattan distance).

        :param point: The point to test.
        :type point: Point
        :returns: True if the point is within the area.
        :rtype: bool
        """
        distance = abs(point.x - self.x) + abs(point.y - self.y)
        return distance <= self.radius


class Spell:
    """Definition of a single spell.

    :param id: The unique spell identifier.
    :type id: int
    :param name: The display name of the spell.
    :type name: str
    :param description: A brief description of the spell's effect.
    :type description: str
    :param effect_type: The category of effect this spell produces.
    :type effect_type: Optional[SpellEffectType]
    :param damage_type: The damage type, if applicable.
    :type damage_type: Optional[DamageType]
    :param base_value: The base power or healing amount.
    :type base_value: int
    :param range_: The maximum casting range (Manhattan distance).
    :type range_: int
    :param area_radius: The radius of the area of effect.
    :type area_radius: int
    :param spell_cost: The number of spell slots consumed.
    :type spell_cost: int
    :param base_lifespan: The base duration for delayed spells.
    :type base_lifespan: int
    :param is_area_effect: Whether this spell affects an area.
    :type is_area_effect: bool
    :param is_delay_spell: Whether this spell has a delayed trigger.
    :type is_delay_spell: bool
    :param is_locking_spell: Whether this spell locks onto a target.
    :type is_locking_spell: bool
    """

    def __init__(
        self,
        id: int = 0,
        name: str = "",
        description: str = "",
        effect_type: Optional[SpellEffectType] = None,
        damage_type: Optional[DamageType] = None,
        base_value: int = 0,
        range_: int = 0,
        area_radius: int = 0,
        spell_cost: int = 0,
        base_lifespan: int = 0,
        is_area_effect: bool = False,
        is_delay_spell: bool = False,
        is_locking_spell: bool = False,
    ) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.effect_type = effect_type
        self.damage_type = damage_type
        self.base_value = base_value
        self.range = range_
        self.area_radius = area_radius
        self.spell_cost = spell_cost
        self.base_lifespan = base_lifespan
        self.is_area_effect = is_area_effect
        self.is_delay_spell = is_delay_spell
        self.is_locking_spell = is_locking_spell


class SpellFactory:
    """Factory providing all available spell definitions."""

    @staticmethod
    def get_all_spells() -> List[Spell]:
        """Return the full list of available spells.

        :returns: A list of all defined Spell objects.
        :rtype: List[Spell]
        """
        return [
            Spell(
                id=1,
                name="Fireball",
                description="Deals fire damage to enemies within the area.",
                effect_type=SpellEffectType.DAMAGE,
                damage_type=DamageType.FIRE,
                base_value=30,
                range_=2,
                area_radius=5,
                spell_cost=1,
                base_lifespan=0,
                is_area_effect=True,
                is_delay_spell=False,
                is_locking_spell=False,
            ),
            Spell(
                id=2,
                name="Heal",
                description="Restores health to an ally unit.",
                effect_type=SpellEffectType.HEAL,
                damage_type=DamageType.NONE,
                base_value=30,
                range_=2,
                area_radius=4,
                spell_cost=1,
                base_lifespan=0,
                is_area_effect=False,
                is_delay_spell=False,
                is_locking_spell=True,
            ),
            Spell(
                id=3,
                name="Arrow Hit",
                description="A physical arrow strike.",
                effect_type=SpellEffectType.DAMAGE,
                damage_type=DamageType.PHYSICAL,
                base_value=30,
                range_=1,
                area_radius=7,
                spell_cost=1,
                base_lifespan=0,
                is_area_effect=False,
                is_delay_spell=False,
                is_locking_spell=True,
            ),
            Spell(
                id=4,
                name="Trap",
                description="Sets a trap that triggers after a delay.",
                effect_type=SpellEffectType.DAMAGE,
                damage_type=DamageType.PHYSICAL,
                base_value=30,
                range_=1,
                area_radius=0,
                spell_cost=1,
                base_lifespan=2,
                is_area_effect=False,
                is_delay_spell=True,
                is_locking_spell=False,
            ),
            Spell(
                id=5,
                name="Teleport",
                description="Instantly moves the caster to a target position.",
                effect_type=SpellEffectType.MOVE,
                damage_type=DamageType.PHYSICAL,
                base_value=30,
                range_=100,
                area_radius=100,
                spell_cost=1,
                base_lifespan=2,
                is_area_effect=False,
                is_delay_spell=False,
                is_locking_spell=True,
            ),
        ]

    @staticmethod
    def get_spell_by_id(spell_id: int) -> Optional[Spell]:
        """Look up a spell by its identifier.

        :param spell_id: The spell ID to search for.
        :type spell_id: int
        :returns: The matching Spell, or None if not found.
        :rtype: Optional[Spell]
        """
        return next(
            (spell for spell in SpellFactory.get_all_spells() if spell.id == spell_id),
            None,
        )

    @staticmethod
    def get_available_spells(piece: Any) -> List[Spell]:
        """Return the list of spells available to a given piece.

        Spells are filtered by piece type and capped by the piece's
        maximum spell slot capacity.

        :param piece: The piece whose available spells are queried.
        :type piece: Piece
        :returns: A list of spells the piece can cast.
        :rtype: List[Spell]
        """
        all_spells = SpellFactory.get_all_spells()
        available: List[Spell] = []

        if piece.type == "Warrior":
            available.extend(
                spell
                for spell in all_spells
                if spell.damage_type == DamageType.PHYSICAL
                or spell.effect_type == SpellEffectType.BUFF
            )
        elif piece.type == "Mage":
            available.extend(
                spell
                for spell in all_spells
                if spell.damage_type
                in [DamageType.FIRE, DamageType.ICE, DamageType.LIGHTNING]
                or spell.effect_type in [SpellEffectType.DAMAGE, SpellEffectType.DEBUFF]
            )
        elif piece.type == "Archer":
            available.extend(
                spell
                for spell in all_spells
                if spell.name in ["Arrow Hit", "Trap"]
                or spell.effect_type == SpellEffectType.MOVE
            )

        max_spells = getattr(piece, "max_spell_slots", None)
        if max_spells is None:
            max_spells = piece.intelligence // 5 + 1
        max_spells = max(0, int(max_spells))
        return available[:max_spells]
