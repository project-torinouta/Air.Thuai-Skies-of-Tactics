# Copyright 2026 saiblo platform <https://saiblo.net>
#
# This SDK copy is distributed from https://api.saiblo.net/api/games/56/download/,
# All rights reserved by saiblo platform. All I modified is translating the
# comment and document string from Chinese to English

"""Core game environment and game logic classes.

This module implements the central game engine including board management,
piece mechanics, combat resolution, spell casting, and the main game loop.
It is used both by the local client and the Saiblo competition platform.
"""

import os
import random
from queue import PriorityQueue
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from local_input import (
    ConsoleInputMethod,
    InputMethodManager,
)
from utils import (
    ActionSet,
    AttackContext,
    InitPolicyMessage,
    Point,
    Spell,
    SpellContext,
    SpellEffectType,
    SpellFactory,
)


class Cell:
    """A single cell on the game board.

    :param state: The cell state: 0=empty, 1=walkable, 2=occupied, -1=blocked.
        Defaults to 1.
    :type state: int
    :param player_id: The occupying player's ID (0=none, 1=player1, 2=player2).
        Defaults to -1.
    :type player_id: int
    :param piece_id: The occupying piece's ID, or -1 if empty. Defaults to -1.
    :type piece_id: int
    """

    def __init__(self, state: int = 1, player_id: int = -1, piece_id: int = -1) -> None:
        self.state = state
        self.player_id = player_id
        self.piece_id = piece_id


class Piece:
    """A game piece (character) on the board.

    Each piece has attributes (strength, dexterity, intelligence), combat
    statistics, resources (action points, spell slots), and a position
    on the board.
    """

    def __init__(self) -> None:
        self.if_log: int = 0

        self.health: int = 0
        self.max_health: int = 0
        self.physical_resist: int = 0
        self.magic_resist: int = 0
        self.physical_damage: int = 0
        self.magic_damage: int = 0
        self.action_points: int = 0
        self.max_action_points: int = 0
        self.spell_slots: int = 0
        self.max_spell_slots: int = 0
        self.movement: float = 0.0
        self.max_movement: float = 0.0
        self.id: int = 0
        self.type: str = ""
        self.strength: int = 0
        self.dexterity: int = 0
        self.intelligence: int = 0
        self.position: Point = Point(0, 0)
        self.height: int = 0
        self.attack_range: int = 0
        self.spell_list: List[int] = []
        self.death_round: int = -1
        self.team: int = 0
        self.queue_index: int = 0
        self.is_alive: bool = True
        self.is_in_turn: bool = False
        self.is_dying: bool = False
        self.spell_range: float = 0.0
        self.weapon_type: int = 0

    def receive_damage(self, damage: int, damage_type: str) -> None:
        """Apply damage to this piece, accounting for resistances.

        :param damage: The raw incoming damage amount.
        :type damage: int
        :param damage_type: Either ``"physical"`` or ``"magic"``.
        :type damage_type: str
        :raises ValueError: If the damage type is not recognised.
        """
        if damage_type == "physical":
            damage = max(0, damage - self.physical_resist)
        elif damage_type == "magic":
            damage = max(0, damage - self.magic_resist)
        else:
            raise ValueError(f"Invalid damage type: {damage_type}")

        self.health -= damage
        if self.if_log:
            print(f"[DEBUG] damage after resist: {damage}")

    def death_check(self) -> bool:
        """Check whether the piece is still alive.

        :returns: Current alive status.
        :rtype: bool
        """
        return self.is_alive

    def get_accessor(self) -> "PieceAccessor":
        """Return a safely-typed accessor for modifying attributes.

        :returns: A PieceAccessor bound to this piece.
        :rtype: PieceAccessor
        """
        return PieceAccessor(self)

    def set_action_points(self, action_points: int) -> None:
        """Set the current action points.

        :param action_points: The new action point value.
        :type action_points: int
        """
        self.action_points = action_points

    def get_action_points(self) -> int:
        """Return the current action points.

        :returns: The current action point count.
        :rtype: int
        """
        return self.action_points


class PieceAccessor:
    """Safely-typed accessor for modifying a piece's attributes.

    Encapsulates mutation of a Piece to prevent direct field writes
    from game-logic code.

    :param piece: The piece to wrap.
    :type piece: Piece
    """

    def __init__(self, piece: Piece) -> None:
        self.piece = piece

    def set_health_to(self, value: int) -> None:
        """Set health to an absolute value."""
        self.piece.health = value

    def change_health_by(self, delta: int) -> None:
        """Add delta to health."""
        self.piece.health += delta

    def set_max_health_to(self, value: int) -> None:
        """Set max health to an absolute value."""
        self.piece.max_health = value

    def set_physical_resist_to(self, value: int) -> None:
        """Set physical resistance."""
        self.piece.physical_resist = value

    def set_magic_resist_to(self, value: int) -> None:
        """Set magic resistance."""
        self.piece.magic_resist = value

    def set_physical_damage_to(self, value: int) -> None:
        """Set physical damage."""
        self.piece.physical_damage = value

    def set_magic_damage_to(self, value: int) -> None:
        """Set magic damage."""
        self.piece.magic_damage = value

    def set_max_movement_to(self, value: float) -> None:
        """Set max movement to an absolute value."""
        self.piece.max_movement = value

    def set_max_movement_by(self, value: float) -> None:
        """Add value to max movement."""
        self.piece.max_movement += value

    def set_movement_to(self, value: float) -> None:
        """Set current movement to an absolute value."""
        self.piece.movement = value

    def set_attack_range_to(self, value: int) -> None:
        """Set the attack range."""
        self.piece.attack_range = value

    def set_max_action_points_to(self, value: int) -> None:
        """Set max action points."""
        self.piece.max_action_points = value

    def set_max_spell_slots_to(self, value: int) -> None:
        """Set max spell slots."""
        self.piece.max_spell_slots = value

    def set_team_to(self, value: int) -> None:
        """Set the team ID."""
        self.piece.team = value

    def set_range_to(self, value: int) -> None:
        """Set the attack range (alias for set_attack_range_to)."""
        self.piece.attack_range = value

    def set_max_action_points(self) -> None:
        """Auto-set max action points based on strength.

        - strength <= 13: 1 point
        - strength <= 21: 2 points
        - otherwise: 3 points
        """
        if self.piece.strength <= 13:
            self.set_max_action_points_to(1)
        elif self.piece.strength <= 21:
            self.set_max_action_points_to(2)
        else:
            self.set_max_action_points_to(3)

    def set_max_spell_slots(self) -> None:
        """Auto-set max spell slots based on intelligence.

        - intelligence <= 3: 1 slot
        - intelligence <= 7: 2 slots
        - intelligence <= 12: 3 slots
        - intelligence <= 16: 5 slots
        - intelligence <= 21: 8 slots
        - otherwise: 9 slots
        """
        if self.piece.intelligence <= 3:
            self.set_max_spell_slots_to(1)
        elif self.piece.intelligence <= 7:
            self.set_max_spell_slots_to(2)
        elif self.piece.intelligence <= 12:
            self.set_max_spell_slots_to(3)
        elif self.piece.intelligence <= 16:
            self.set_max_spell_slots_to(5)
        elif self.piece.intelligence <= 21:
            self.set_max_spell_slots_to(8)
        else:
            self.set_max_spell_slots_to(9)

    def set_strength_to(self, value: int) -> None:
        """Set the strength attribute.

        :raises ValueError: If value is negative.
        """
        if value < 0:
            raise ValueError("Strength cannot be negative")
        self.piece.strength = value

    def set_dexterity_to(self, value: int) -> None:
        """Set the dexterity attribute.

        :raises ValueError: If value is negative.
        """
        if value < 0:
            raise ValueError("Dexterity cannot be negative")
        self.piece.dexterity = value

    def set_intelligence_to(self, value: int) -> None:
        """Set the intelligence attribute.

        :raises ValueError: If value is negative.
        """
        if value < 0:
            raise ValueError("Intelligence cannot be negative")
        self.piece.intelligence = value

    def set_type_to(self, value: int) -> None:
        """Set the piece type from a numeric weapon type.

        :param value: The weapon type (1-4).
        :type value: int
        :raises ValueError: If value is out of range.
        """
        if value < 0:
            raise ValueError("Type cannot be negative")
        if value == 1 or value == 2:
            self.piece.type = "Warrior"
        elif value == 4:
            self.piece.type = "Mage"
        elif value == 3:
            self.piece.type = "Archer"
        else:
            raise ValueError(f"Type out of range: {value}")

    def set_action_points_to(self, value: int) -> None:
        """Set action points."""
        self.piece.action_points = value

    def change_action_points_by(self, delta: int) -> None:
        """Add delta to action points."""
        self.piece.action_points += delta

    def set_spell_slots_to(self, value: int) -> None:
        """Set spell slots."""
        self.piece.spell_slots = value

    def change_spell_slots_by(self, delta: int) -> None:
        """Add delta to spell slots."""
        self.piece.spell_slots += delta

    def set_alive(self, value: bool) -> None:
        """Set the alive status."""
        self.piece.is_alive = value

    def set_dying(self, value: bool) -> None:
        """Set the dying status."""
        self.piece.is_dying = value

    def set_position(self, new_pos: Point) -> None:
        """Set the piece position."""
        self.piece.position = new_pos

    def set_height_to(self, value: int) -> None:
        """Set the height."""
        self.piece.height = value

    def set_magic_resist_by(self, value: int) -> None:
        """Subtract value from magic resistance."""
        self.piece.magic_resist -= value

    def set_physic_resist_by(self, value: int) -> None:
        """Subtract value from physical resistance."""
        self.piece.physical_resist -= value

    def strength_adjustment(self) -> int:
        """Return the strength adjustment tier.

        :returns: 1-4 based on strength threshold.
        :rtype: int
        """
        if self.piece.strength <= 7:
            return 1
        if self.piece.strength <= 13:
            return 2
        if self.piece.strength <= 16:
            return 3
        return 4

    def dexterity_adjustment(self) -> int:
        """Return the dexterity adjustment tier.

        :returns: 1-4 based on dexterity threshold.
        :rtype: int
        """
        if self.piece.dexterity <= 7:
            return 1
        if self.piece.dexterity <= 13:
            return 2
        if self.piece.dexterity <= 16:
            return 3
        return 4

    def intelligence_adjustment(self) -> int:
        """Return the intelligence adjustment tier.

        :returns: 1-4 based on intelligence threshold.
        :rtype: int
        """
        if self.piece.intelligence <= 7:
            return 1
        if self.piece.intelligence <= 13:
            return 2
        if self.piece.intelligence <= 16:
            return 3
        return 4


class Player:
    """Represents a player and their pieces.

    :param id: The player ID (1 or 2).
    :type id: int
    :param pieces: Array of owned Piece objects.
    :type pieces: numpy.ndarray
    :param feature_total: Total attribute points available for distribution.
    :type feature_total: int
    :param piece_num: Number of pieces owned.
    :type piece_num: int
    """

    PIECE_CNT: int = 3

    def __init__(self) -> None:
        self.id: int = 0
        self.pieces: np.ndarray = np.array([], dtype=object)
        self.feature_total: int = 30
        self.piece_num: int = 0

    def set_weapon(self, weapon: int, piece: Piece) -> None:
        """Configure a piece's weapon and update its combat stats.

        :param weapon: Weapon type (1=longsword, 2=shortsword, 3=bow, 4=staff).
        :type weapon: int
        :param piece: The piece to equip.
        :type piece: Piece
        :raises ValueError: If the weapon type is invalid.
        """
        accessor = piece.get_accessor()
        piece.weapon_type = int(weapon)
        accessor.set_type_to(weapon)

        if weapon == 1:
            accessor.set_physical_damage_to(8)
            accessor.set_magic_damage_to(0)
            accessor.set_range_to(5)
        elif weapon == 2:
            accessor.set_physical_damage_to(10)
            accessor.set_magic_damage_to(0)
            accessor.set_range_to(3)
        elif weapon == 3:
            accessor.set_physical_damage_to(16)
            accessor.set_magic_damage_to(0)
            accessor.set_range_to(9)
        elif weapon == 4:
            accessor.set_physical_damage_to(0)
            accessor.set_magic_damage_to(18)
            accessor.set_range_to(12)
        else:
            raise ValueError(f"Wrong weapon type: {weapon}")

    def set_armor(self, armor: int, piece: Piece) -> None:
        """Configure a piece's armour and update its defences.

        :param armor: Armour type (1=light, 2=medium, 3=heavy).
        :type armor: int
        :param piece: The piece to equip.
        :type piece: Piece
        :raises ValueError: If the armour type is invalid.
        """
        accessor = piece.get_accessor()

        if armor == 1:
            accessor.set_physical_resist_to(8)
            accessor.set_magic_resist_to(0)
            accessor.set_max_movement_by(3)
        elif armor == 2:
            accessor.set_physical_resist_to(15)
            accessor.set_magic_resist_to(0)
        elif armor == 3:
            accessor.set_physical_resist_to(23)
            accessor.set_magic_resist_to(0)
            accessor.set_max_movement_by(-3)
        else:
            raise ValueError(f"Wrong armor type: {armor}")

    @staticmethod
    def validate_piece_init(
        board: "Board",
        player_id: int,
        arg: Any,
        index: int,
        occupied_same_player: List[Tuple[int, int]],
    ) -> None:
        """Validate piece initialisation parameters.

        Checks attributes, equipment, and position against game rules.
        Mirrors the validation logic in ``C# Player.localInit``.

        :param board: The game board.
        :type board: Board
        :param player_id: The player's ID (1 or 2).
        :type player_id: int
        :param arg: The piece initialisation parameters.
        :type arg: PieceArg
        :param index: The index of this piece among the player's pieces.
        :type index: int
        :param occupied_same_player: List of (x, y) tuples already occupied
            by the same player's pieces.
        :type occupied_same_player: List[Tuple[int, int]]
        :raises ValueError: If any validation check fails.
        """
        prefix = f"Piece {index + 1}"
        if arg.strength < 0 or arg.dexterity < 0 or arg.intelligence < 0:
            raise ValueError(f"{prefix}: stats cannot be negative")
        if arg.strength + arg.dexterity + arg.intelligence > 30:
            raise ValueError(f"{prefix}: stat total exceeds 30")
        eq = arg.equip
        if eq.x < 1 or eq.x > 4:
            raise ValueError(f"{prefix}: invalid weapon type {eq.x} (allowed 1-4)")
        if eq.y < 1 or eq.y > 3:
            raise ValueError(f"{prefix}: invalid armour type {eq.y} (allowed 1-3)")
        if eq.x == 4 and eq.y != 1:
            raise ValueError(f"{prefix}: staff must be paired with light armour")
        pos = arg.pos
        if pos.x < 0 or pos.x >= board.width or pos.y < 0 or pos.y >= board.height:
            raise ValueError(
                f"{prefix}: position ({pos.x},{pos.y}) is out of bounds"
            )
        st = board.grid[pos.x][pos.y].state
        if int(st) != 1:
            raise ValueError(
                f"{prefix}: target cell state is not walkable (state={st})"
            )
        for ox, oy in occupied_same_player:
            if ox == pos.x and oy == pos.y:
                raise ValueError(f"{prefix}: position already occupied by another piece")
        if player_id == 1 and pos.y >= board.boarder:
            raise ValueError(
                f"{prefix}: player 1's piece must be below the border "
                f"(y < {board.boarder})"
            )
        if player_id == 2 and pos.y <= board.boarder:
            raise ValueError(
                f"{prefix}: player 2's piece must be above the border "
                f"(y > {board.boarder})"
            )

    def local_init(self, board: "Board", player_id: int) -> None:
        """Initialise all pieces via console input.

        :param board: The game board.
        :type board: Board
        :param player_id: The player's ID (1 or 2).
        :type player_id: int
        """
        pieces_list = []

        for i in range(self.PIECE_CNT):
            print(f"--- Player {player_id}, initialising piece {i + 1} ---")
            piece = Piece()
            pieces_list.append(piece)

            accessor = piece.get_accessor()
            accessor.set_team_to(player_id)

            features = self.init_input(board, player_id)
            self.piece_num += 1

            strength, dexterity, intelligence = features[0], features[1], features[2]
            accessor.set_strength_to(strength)
            accessor.set_dexterity_to(dexterity)
            accessor.set_intelligence_to(intelligence)

            weapon, armor = features[3], features[4]

            accessor.set_max_health_to(30 + strength * 2)
            accessor.set_health_to(piece.max_health)

            accessor.set_max_action_points()
            accessor.set_action_points_to(piece.max_action_points)

            accessor.set_max_spell_slots()
            accessor.set_spell_slots_to(piece.max_spell_slots)

            accessor.set_max_movement_to(dexterity + 0.5 * strength + 10)
            accessor.set_movement_to(piece.max_movement)

            self.set_weapon(weapon, piece)
            self.set_armor(armor, piece)

            position = Point(features[5], features[6])
            accessor.set_position(position)
            accessor.set_height_to(board.height_map[position.x][position.y])

        self.pieces = np.array(pieces_list, dtype=object)

    def init_input(self, board: "Board", player_id: int) -> List[int]:
        """Read piece initialisation from the console.

        Prompts the user for attributes, equipment, and position.

        :param board: The game board.
        :type board: Board
        :param player_id: The player's ID.
        :type player_id: int
        :returns: A list of [strength, dexterity, intelligence, weapon,
            armor, x, y].
        :rtype: List[int]
        """
        initialization_set: List[int] = []
        try:
            while True:
                print("Enter attribute allocation (format: strength dexterity intelligence, total <= 30):")
                user_input = input()
                if user_input:
                    try:
                        inputs = user_input.split()
                        nums = [int(x) for x in inputs]
                        if len(nums) != 3:
                            print("Expected exactly 3 integers.")
                            continue

                        strength, dexterity, intelligence = nums

                        if any(n < 0 for n in nums):
                            print("Attributes cannot be negative.")
                            continue

                        if sum(nums) > 30:
                            print("Attribute total exceeds 30.")
                            continue

                        initialization_set.extend(nums)
                        break
                    except ValueError:
                        print("Invalid integer input.")
                        continue

            print()
            print("Weapon / Armour table:")
            print("Weapon:          Phys Dmg    Magic Dmg   Range")
            print("1-Longsword      8           0           5")
            print("2-Shortsword     10          0           3")
            print("3-Bow            16          0           9")
            print("4-Staff          0           18          12")
            print("Armour:          Phys Res    Magic Res   Move Effect")
            print("1-Light          8           0           +3")
            print("2-Medium         15          0           0")
            print("3-Heavy          23          0           -3")

            while True:
                print()
                print("Enter weapon and armour (format: weapon_type(1-4) armour_type(1-3)):")
                user_input = input()
                if user_input:
                    try:
                        inputs = user_input.split()
                        if len(inputs) != 2:
                            print("Expected exactly 2 integers.")
                            continue

                        weapon, armor = map(int, inputs)

                        if not (1 <= weapon <= 4 and 1 <= armor <= 3):
                            print("Values out of range.")
                            continue

                        if weapon == 4 and armor != 1:
                            print("Staff must be paired with light armour.")
                            continue

                        initialization_set.extend([weapon, armor])
                        break
                    except ValueError:
                        print("Invalid integer input.")
                        continue

            while True:
                rows = board.height
                cols = board.width
                boarder = board.boarder

                print()
                print("Enter initial position (format: x y):")
                user_input = input()
                if user_input:
                    try:
                        inputs = user_input.split()
                        if len(inputs) != 2:
                            print("Expected exactly 2 integers.")
                            continue

                        x, y = map(int, inputs)

                        if not (0 <= x < cols and 0 <= y < rows):
                            print("Position out of bounds.")
                            continue

                        if board.grid[x][y].state != 1:
                            print("Target cell is not walkable.")
                            continue

                        if player_id == 1 and y >= boarder:
                            print(f"Player 1 pieces must be below border {boarder}.")
                            continue
                        if player_id == 2 and y <= boarder:
                            print(f"Player 2 pieces must be above border {boarder}.")
                            continue

                        is_valid = True
                        for existing_piece in self.pieces:
                            if x == existing_piece.position.x and y == existing_piece.position.y:
                                print("Position already occupied by another piece.")
                                is_valid = False
                                break

                        if not is_valid:
                            continue

                        initialization_set.extend([x, y])
                        break
                    except ValueError:
                        print("Invalid integer input.")
                        continue

        except Exception as e:
            print(f"Input error: {e}")
            raise

        return initialization_set


class Board:
    """The game board, consisting of a grid of cells and a height map.

    :param if_log: Whether to enable diagnostic logging (1=enabled, 0=disabled).
        Defaults to 1.
    :type if_log: int
    """

    def __init__(self, if_log: int = 1) -> None:
        self.width: int = 0
        self.height: int = 0
        self.grid: Optional[np.ndarray] = None
        self.height_map: Optional[np.ndarray] = None
        self.boarder: int = 0
        self.if_log: int = if_log

    def get_width(self) -> int:
        """Return the board width."""
        return self.width

    def get_height(self) -> int:
        """Return the board height."""
        return self.height

    def valid_target(self, piece: Piece, movement: float) -> List[List[int]]:
        """Compute all reachable positions using Dijkstra's algorithm.

        Returns a 2D grid where each cell contains the movement cost to
        reach it, or -1 if unreachable.

        :param piece: The piece to move (used for position and ignoring
            its own occupied cell).
        :type piece: Piece
        :param movement: The available movement points.
        :type movement: float
        :returns: A width x height grid of movement costs (-1 = unreachable).
        :rtype: List[List[int]]
        """
        mask = [[-1 for _ in range(self.height)] for _ in range(self.width)]
        start = piece.position

        frontier: PriorityQueue = PriorityQueue()
        frontier.put((0, (start.x, start.y)))
        visited = set()
        mask[start.x][start.y] = 0

        while not frontier.empty():
            current_cost, current_pos = frontier.get()
            current_x, current_y = current_pos

            if current_pos in visited:
                continue
            visited.add(current_pos)

            if current_cost > movement:
                continue

            current_point = Point(current_x, current_y)
            for next_pos in self.get_neighbors(current_point):
                next_x, next_y = next_pos.x, next_pos.y
                next_tuple = (next_x, next_y)

                if next_tuple in visited or self.grid[next_x][next_y].state != 1:
                    continue

                height_diff = (
                    self.height_map[next_x][next_y] - self.height_map[current_x][current_y]
                )
                move_cost = 1 + max(0, height_diff)
                new_cost = current_cost + move_cost

                if new_cost <= movement and (
                    mask[next_x][next_y] == -1 or new_cost < mask[next_x][next_y]
                ):
                    mask[next_x][next_y] = new_cost
                    frontier.put((new_cost, next_tuple))

        return mask

    def move_piece(
        self, piece: Piece, to: Point, movement: float
    ) -> Tuple[Optional[List[Point]], bool]:
        """Move a piece to a target position if reachable.

        :param piece: The piece to move.
        :type piece: Piece
        :param to: The target position.
        :type to: Point
        :param movement: The movement points available.
        :type movement: float
        :returns: A tuple of (path, success). Path is the list of waypoints
            on success, or None on failure.
        :rtype: Tuple[Optional[List[Point]], bool]
        """
        if not self.is_within_bounds(to):
            if self.if_log:
                print(f"Target ({to.x}, {to.y}) is out of bounds.")
            return None, False

        if self.grid[to.x][to.y].state != 1:
            if self.if_log:
                print(f"Target ({to.x}, {to.y}) is occupied.")
            return None, False

        path, cost = self.find_shortest_path(piece, piece.position, to, movement)
        if path is None or cost > movement:
            if self.if_log:
                print(f"Target ({to.x}, {to.y}) is unreachable.")
            return None, False

        old_x, old_y = piece.position.x, piece.position.y
        old_height = piece.height

        try:
            self.grid[old_x][old_y].state = 1
            self.grid[old_x][old_y].player_id = -1
            self.grid[old_x][old_y].piece_id = -1

            self.grid[to.x][to.y].state = 2
            self.grid[to.x][to.y].player_id = piece.team
            self.grid[to.x][to.y].piece_id = piece.id

            piece.position = to
            piece.height = self.height_map[to.x][to.y]

            return path, True

        except Exception as e:
            if self.if_log:
                print(f"Move error: {e}")
            self.grid[old_x][old_y].state = 2
            self.grid[old_x][old_y].player_id = piece.team
            self.grid[old_x][old_y].piece_id = piece.id

            self.grid[to.x][to.y].state = 1
            self.grid[to.x][to.y].player_id = -1
            self.grid[to.x][to.y].piece_id = -1

            piece.position = Point(old_x, old_y)
            piece.height = old_height
            return None, False

    def is_occupied(self, point: Point) -> bool:
        """Check whether a cell is occupied.

        :param point: The position to check.
        :type point: Point
        :returns: True if the cell state is 2 (occupied).
        :rtype: bool
        """
        return self.grid[point.x][point.y].state == 2

    def get_height(self, point: Point) -> int:
        """Return the height at a given position.

        :param point: The position to query.
        :type point: Point
        :returns: The height value.
        :rtype: int
        """
        return self.height_map[point.x][point.y]

    def remove_piece(self, piece: Piece) -> None:
        """Remove a piece from the board, freeing its cell.

        :param piece: The piece to remove.
        :type piece: Piece
        """
        x, y = piece.position.x, piece.position.y
        self.grid[x][y].state = 1
        self.grid[x][y].player_id = -1
        self.grid[x][y].piece_id = -1

    def is_within_bounds(self, point: Point) -> bool:
        """Check whether a position lies within the board boundaries.

        :param point: The position to test.
        :type point: Point
        :returns: True if the position is inside the board.
        :rtype: bool
        """
        return 0 <= point.x < self.width and 0 <= point.y < self.height

    def get_neighbors(self, point: Point) -> List[Point]:
        """Return all walkable adjacent cells (4-directional).

        :param point: The centre position.
        :type point: Point
        :returns: List of neighbouring walkable Points.
        :rtype: List[Point]
        """
        candidates = [
            Point(point.x - 1, point.y),
            Point(point.x + 1, point.y),
            Point(point.x, point.y - 1),
            Point(point.x, point.y + 1),
        ]
        return [
            n
            for n in candidates
            if self.is_within_bounds(n) and self.grid[n.x][n.y].state == 1
        ]

    def find_shortest_path(
        self, piece: Piece, start: Point, goal: Point, movement: float
    ) -> Tuple[Optional[List[Point]], float]:
        """Find the shortest path from start to goal using Dijkstra.

        :param piece: The moving piece (unused, for signature compatibility).
        :type piece: Piece
        :param start: The start position.
        :type start: Point
        :param goal: The goal position.
        :type goal: Point
        :param movement: The movement budget.
        :type movement: float
        :returns: A tuple of (path, cost). Path is None if unreachable.
        :rtype: Tuple[Optional[List[Point]], float]
        """
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        cost_so_far: Dict[Tuple[int, int], float] = {}
        frontier: PriorityQueue = PriorityQueue()

        frontier.put((0, (start.x, start.y)))
        came_from[(start.x, start.y)] = (start.x, start.y)
        cost_so_far[(start.x, start.y)] = 0

        while not frontier.empty():
            _, current_pos = frontier.get()
            cx, cy = current_pos

            if cx == goal.x and cy == goal.y:
                break

            current_point = Point(cx, cy)
            for next_pos in self.get_neighbors(current_point):
                nxt = (next_pos.x, next_pos.y)
                hd = self.height_map[next_pos.x][next_pos.y] - self.height_map[cx][cy]
                move_cost = 1 + max(0, hd)
                new_cost = cost_so_far[current_pos] + move_cost

                if new_cost > movement:
                    continue

                if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                    cost_so_far[nxt] = new_cost
                    frontier.put((new_cost, nxt))
                    came_from[nxt] = current_pos

        goal_tuple = (goal.x, goal.y)
        if goal_tuple not in came_from:
            return None, 0

        path: List[Point] = []
        temp = goal_tuple
        start_tuple = (start.x, start.y)
        while temp != start_tuple:
            path.append(Point(temp[0], temp[1]))
            temp = came_from[temp]

        path.reverse()
        return path, cost_so_far[goal_tuple]

    def init_from_file(self, file_path: str) -> None:
        """Initialise the board from a text file.

        File format::

            width height
            <blank line>
            grid rows (comma-separated cell states)
            <blank line>
            height map rows (comma-separated heights)

        :param file_path: Path to the board definition file.
        :type file_path: str
        """
        with open(file_path) as f:
            lines = f.readlines()

        dimensions = lines[0].strip().split()
        self.width = int(dimensions[0])
        self.height = int(dimensions[1])
        print(f"Width: {self.width}, Height: {self.height}")

        self.grid = np.array(
            [[Cell() for _ in range(self.height)] for _ in range(self.width)],
            dtype=object,
        )
        self.height_map = np.zeros((self.width, self.height), dtype=int)
        self.boarder = self.height // 2

        line_index = 2

        for y in range(self.height):
            values = lines[line_index].strip().split(",")
            for x in range(self.width):
                self.grid[x][y].state = int(values[x].strip())
            line_index += 1

        line_index += 1

        for x in range(self.width):
            for y in range(self.height):
                self.grid[x][y].player_id = -1
                self.grid[x][y].piece_id = -1

        for y in range(self.height):
            values = lines[line_index].strip().split(",")
            for x in range(self.width):
                self.height_map[x][y] = int(values[x].strip())
            line_index += 1

    def init_pieces_location(
        self, player1_pieces: List[Piece], player2_pieces: List[Piece]
    ) -> None:
        """Place both players' pieces on the board.

        Validates that player 1 pieces are below the border and player 2
        pieces are above the border.

        :param player1_pieces: List of player 1's pieces.
        :type player1_pieces: List[Piece]
        :param player2_pieces: List of player 2's pieces.
        :type player2_pieces: List[Piece]
        :raises ValueError: If any piece is on the wrong side.
        """
        for piece in player1_pieces:
            if piece.position.y >= self.boarder:
                raise ValueError(
                    f"Player 1 piece (ID:{piece.id}) at y={piece.position.y} "
                    f"must be below border {self.boarder}"
                )
            self.grid[piece.position.x][piece.position.y].state = 2
            self.grid[piece.position.x][piece.position.y].player_id = piece.team
            self.grid[piece.position.x][piece.position.y].piece_id = piece.id

        for piece in player2_pieces:
            if piece.position.y <= self.boarder:
                raise ValueError(
                    f"Player 2 piece (ID:{piece.id}) at y={piece.position.y} "
                    f"must be above border {self.boarder}"
                )
            self.grid[piece.position.x][piece.position.y].state = 2
            self.grid[piece.position.x][piece.position.y].player_id = piece.team
            self.grid[piece.position.x][piece.position.y].piece_id = piece.id


class GameState:
    """Represents the complete state of a game at a given moment.

    Includes the action queue, current piece, round number, delayed
    spells, both players, the board, and death tracking.
    """

    def __init__(self) -> None:
        self.action_queue: np.ndarray = np.array([], dtype=object)
        self.current_piece: Optional[Piece] = None
        self.round_number: int = 0
        self.delayed_spells: List[Any] = []
        self.player1: Optional[Player] = None
        self.player2: Optional[Player] = None
        self.board: Optional[Board] = None
        self.is_game_over: bool = False
        self.new_dead_this_round: np.ndarray = np.array([], dtype=object)
        self.last_round_dead_pieces: np.ndarray = np.array([], dtype=object)


class InitGameMessage:
    """Message sent at game start carrying initialisation context.

    :param piece_cnt: Number of pieces this player controls.
    :type piece_cnt: int
    :param id: The player ID (1 or 2).
    :type id: int
    :param board: The game board.
    :type board: Optional[Board]
    """

    def __init__(self) -> None:
        self.piece_cnt: int = 0
        self.id: int = 0
        self.board: Optional[Board] = None


class Environment:
    """Core game environment and controller.

    Manages the game loop, board state, piece actions, combat resolution,
    spell casting, and turn progression. Supports both local console play
    and remote (Saiblo) competition.

    :param local_mode: True for local console mode, False for remote/Saiblo
        mode. Defaults to True.
    :type local_mode: bool
    :param if_log: 1 to enable diagnostic logging, 0 to disable. Defaults to 1.
    :type if_log: int
    """

    def __init__(self, local_mode: bool = True, if_log: int = 1) -> None:
        self.mode: int = 0 if local_mode else 1
        self.if_log: int = if_log
        self.input_manager: InputMethodManager = InputMethodManager(self)
        self.action_queue: np.ndarray = np.array([], dtype=object)
        self.current_piece: Optional[Piece] = None
        self.round_number: int = 0
        self.delayed_spells: List[Any] = []
        self.player1: Player = Player()
        self.player2: Player = Player()
        self.board: Board = Board(if_log=if_log)
        self.is_game_over: bool = False
        self.is_battle_initialized: bool = False
        self.max_rounds: int = 100
        self.logdata: Any = None
        self.new_dead_this_round: np.ndarray = np.array([], dtype=object)
        self.last_round_dead_pieces: np.ndarray = np.array([], dtype=object)

    # ------------------------------------------------------------------
    # Dice / random helpers
    # ------------------------------------------------------------------

    @staticmethod
    def roll_dice(n: int, sides: int) -> int:
        """Roll a dice.

        :param n: Number of dice.
        :type n: int
        :param sides: Number of sides per die.
        :type sides: int
        :returns: The total roll.
        :rtype: int
        """
        return random.randint(1, sides)

    @staticmethod
    def step_modified_func(num: int) -> int:
        """Return a step modifier based on a numeric threshold.

        :param num: The input value.
        :type num: int
        :returns: 1-4 depending on the threshold.
        :rtype: int
        """
        if num <= 10:
            return 1
        if num <= 20:
            return 2
        if num <= 30:
            return 3
        return 4

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initialize(self, board_file: str = "./BoardCase/case1.txt") -> None:
        """Fully initialise a new game: board, players, and turn queue.

        :param board_file: Path to the board definition file. Defaults to
            ``./BoardCase/case1.txt``.
        :type board_file: str
        """
        if board_file is None:
            board_file = os.path.join(
                os.path.dirname(__file__), "..", "server", "server", "BoardCase", "case1.txt"
            )
            if not os.path.exists(board_file):
                self.create_default_board()
            else:
                self.board.init_from_file(board_file)
        else:
            self.board.init_from_file(board_file)

        self.player1.id = 1
        self.player2.id = 2

        init_message1 = InitGameMessage()
        init_message1.piece_cnt = Player.PIECE_CNT
        init_message1.id = 1
        init_message1.board = self.board

        init_message2 = InitGameMessage()
        init_message2.piece_cnt = Player.PIECE_CNT
        init_message2.id = 2
        init_message2.board = self.board

        init_policy1 = self.input_manager.handle_init_input(1, init_message1)
        init_policy2 = self.input_manager.handle_init_input(2, init_message2)

        self.apply_init_policy(1, init_policy1)
        self.apply_init_policy(2, init_policy2)

        self.action_queue = np.array([], dtype=object)
        self.delayed_spells = np.array([], dtype=object)
        self.is_game_over = False
        self.round_number = 0
        self.new_dead_this_round = np.array([], dtype=object)

        piece_priority: Dict[Piece, int] = {}
        for piece in self.player1.pieces:
            piece_priority[piece] = self.roll_dice(1, 10) + piece.dexterity
        for piece in self.player2.pieces:
            piece_priority[piece] = self.roll_dice(1, 10) + piece.dexterity

        sorted_pieces = sorted(piece_priority.keys(), key=lambda x: -piece_priority[x])
        self.action_queue = np.array(sorted_pieces, dtype=object)

        for i, piece in enumerate(self.action_queue):
            piece.id = i

        self.board.init_pieces_location(list(self.player1.pieces), list(self.player2.pieces))
        self.last_round_dead_pieces = np.array([], dtype=object)

    def apply_init_policy(self, player_id: int, policy: InitPolicyMessage) -> None:
        """Apply an initialisation policy to a player's pieces.

        :param player_id: The player ID (1 or 2).
        :type player_id: int
        :param policy: The initialisation policy containing piece arguments.
        :type policy: InitPolicyMessage
        :raises ValueError: If the policy is invalid.
        """
        if policy is None or policy.piece_args is None:
            raise ValueError("Init policy cannot be empty.")
        if len(policy.piece_args) < Player.PIECE_CNT:
            raise ValueError(
                f"Need {Player.PIECE_CNT} piece args, got {len(policy.piece_args)}"
            )
        piece_args_use = policy.piece_args[: Player.PIECE_CNT]
        player = self.player1 if player_id == 1 else self.player2
        pieces_list: List[Piece] = []
        occupied: List[Tuple[int, int]] = []

        for idx, piece_arg in enumerate(piece_args_use):
            if piece_arg is None:
                raise ValueError(f"Piece arg {idx + 1} is None.")
            Player.validate_piece_init(self.board, player_id, piece_arg, idx, occupied)
            occupied.append((piece_arg.pos.x, piece_arg.pos.y))

        for piece_arg in piece_args_use:
            piece = Piece()
            pieces_list.append(piece)

            accessor = piece.get_accessor()
            accessor.set_team_to(player_id)

            accessor.set_strength_to(piece_arg.strength)
            accessor.set_dexterity_to(piece_arg.dexterity)
            accessor.set_intelligence_to(piece_arg.intelligence)

            player.set_weapon(piece_arg.equip.x, piece)
            player.set_armor(piece_arg.equip.y, piece)

            accessor.set_position(piece_arg.pos)
            hm = self.board.height_map
            if hasattr(hm, "shape"):
                h0 = int(hm[piece_arg.pos.x, piece_arg.pos.y])
            else:
                h0 = int(hm[piece_arg.pos.x][piece_arg.pos.y])
            accessor.set_height_to(h0)

            accessor.set_max_health_to(30 + piece_arg.strength * 2)
            accessor.set_health_to(piece.max_health)
            accessor.set_max_action_points()
            accessor.set_action_points_to(piece.max_action_points)
            accessor.set_max_spell_slots()
            accessor.set_spell_slots_to(piece.max_spell_slots)
            accessor.set_max_movement_to(
                piece_arg.dexterity + 0.5 * piece_arg.strength + 10
            )
            accessor.set_movement_to(piece.max_movement)

        player.pieces = np.array(pieces_list, dtype=object)
        player.piece_num = len(pieces_list)

    def create_default_board(self) -> None:
        """Create a simple 10x10 default board with obstacles."""
        self.board.width = 10
        self.board.height = 10
        self.board.boarder = 5

        self.board.grid = [
            [Cell(1) for _ in range(self.board.height)] for _ in range(self.board.width)
        ]
        self.board.height_map = [
            [0 for _ in range(self.board.height)] for _ in range(self.board.width)
        ]

        for i in range(2, 8):
            self.board.grid[i][5].state = -1
            self.board.height_map[i][5] = 3

    # ------------------------------------------------------------------
    # Combat helpers
    # ------------------------------------------------------------------

    def is_in_attack_range(self, attacker: Piece, target: Piece) -> bool:
        """Check whether a target is within the attacker's range.

        :param attacker: The attacking piece.
        :type attacker: Piece
        :param target: The target piece.
        :type target: Piece
        :returns: True if the target is within range.
        :rtype: bool
        """
        distance = (
            abs(attacker.position.x - target.position.x)
            + abs(attacker.position.y - target.position.y)
        )
        return distance <= attacker.attack_range

    def calculate_advantage_value(self, attacker: Piece, target: Piece) -> float:
        """Calculate the combat advantage value from height and environment.

        :param attacker: The attacking piece.
        :type attacker: Piece
        :param target: The target piece.
        :type target: Piece
        :returns: The advantage value.
        :rtype: float
        """
        height_advantage = 2 * (attacker.height - target.height)
        attacker_env = self.calculate_environment_value(attacker)
        target_env = self.calculate_environment_value(target)
        env_advantage = 3 * (attacker_env - target_env)
        return height_advantage + env_advantage

    def calculate_environment_value(self, piece: Piece) -> int:
        """Calculate the environmental value for a piece based on delayed spells.

        :param piece: The piece to evaluate.
        :type piece: Piece
        :returns: The net environmental modifier.
        :rtype: int
        """
        env_value = 0
        for ctx in self.delayed_spells:
            sp = getattr(ctx, "spell", None)
            ta = getattr(ctx, "target_area", None)
            if sp is None or ta is None or not ta.contains(piece.position):
                continue
            et = sp.effect_type
            if et == SpellEffectType.BUFF:
                env_value += 1
            if et == SpellEffectType.DAMAGE:
                env_value -= 1
        return env_value

    # ------------------------------------------------------------------
    # Death / combat execution
    # ------------------------------------------------------------------

    def handle_death_check(self, target: Piece) -> None:
        """Roll for death: on a 20 the piece survives with 1 HP.

        :param target: The piece to check.
        :type target: Piece
        """
        death_roll = self.roll_dice(1, 20)
        if self.if_log:
            print(f"[DeathCheck] Roll: {death_roll}")

        if death_roll == 20:
            target.get_accessor().set_health_to(1)
            target.get_accessor().set_dying(False)
            target.get_accessor().set_alive(True)
        else:
            target.get_accessor().set_alive(False)
            if self.logdata is not None:
                self.logdata.add_death(target)
            self.board.remove_piece(target)
            self.action_queue = np.array(
                [p for p in self.action_queue if p != target], dtype=object
            )
            self.new_dead_this_round = np.append(self.new_dead_this_round, [target])
            target.death_round = self.round_number

    def execute_attack(self, attack_context: AttackContext) -> None:
        """Execute an attack between two pieces.

        Handles damage calculation including staff true damage, physical
        resistance, and death checks.

        :param attack_context: The full attack context.
        :type attack_context: AttackContext
        """
        if (
            attack_context.attacker is None
            or attack_context.target is None
            or not attack_context.attacker.is_alive
            or not attack_context.target.is_alive
        ):
            return

        if attack_context.attacker.action_points <= 0:
            if self.if_log:
                print("[Attack] Failed: not enough action points.")
            return

        if not self.is_in_attack_range(attack_context.attacker, attack_context.target):
            if self.if_log:
                print("[Attack] Failed: out of range.")
            return

        if self.if_log:
            print("[Attack] Auto hit.")

        if getattr(attack_context.attacker, "weapon_type", 0) == 4:
            damage = 4
            if self.if_log:
                print(f"[Attack] Staff true damage: {damage}")
            accessor = attack_context.target.get_accessor()
            accessor.set_health_to(max(attack_context.target.health - damage, 0))
        else:
            damage = (
                attack_context.attacker.physical_damage + attack_context.attacker.strength
            )
            if self.if_log:
                print(f"[Attack] Dealing {damage} damage.")
            attack_context.target.receive_damage(damage, "physical")

        attack_context.damage_dealt = damage

        if attack_context.target.health <= 0:
            self.handle_death_check(attack_context.target)

        attack_context.attacker.get_accessor().change_action_points_by(-1)

    def get_available_spells(self, piece: Optional[Piece] = None) -> List[Spell]:
        """Get the list of spells available to a piece.

        :param piece: The piece to query. Defaults to the current piece.
        :type piece: Optional[Piece]
        :returns: Available spells for the piece.
        :rtype: List[Spell]
        """
        if piece is None:
            piece = self.current_piece

        if piece is None or not piece.is_alive:
            return []

        return SpellFactory.get_available_spells(piece)

    def get_spell_targets(
        self, spell: Spell, caster: Optional[Piece] = None
    ) -> List[Piece]:
        """Get valid targets for a spell.

        Filters by range, effect type, and team alignment.

        :param spell: The spell to check.
        :type spell: Spell
        :param caster: The caster. Defaults to the current piece.
        :type caster: Optional[Piece]
        :returns: List of valid target pieces.
        :rtype: List[Piece]
        """
        if caster is None:
            caster = self.current_piece

        if caster is None or not caster.is_alive:
            return []

        targets: List[Piece] = []
        for piece in self.action_queue:
            if not piece.is_alive:
                continue

            distance = (
                abs(caster.position.x - piece.position.x)
                + abs(caster.position.y - piece.position.y)
            )
            if distance > spell.range:
                continue

            if spell.effect_type in [SpellEffectType.DAMAGE, SpellEffectType.DEBUFF]:
                if piece.team != caster.team:
                    targets.append(piece)
            elif spell.effect_type in [SpellEffectType.HEAL, SpellEffectType.BUFF]:
                if piece.team == caster.team:
                    targets.append(piece)
            elif spell.effect_type == SpellEffectType.MOVE:
                if piece == caster:
                    targets.append(piece)

        return targets

    def execute_spell(self, spell_context: SpellContext) -> None:
        """Execute a spell cast.

        Handles resource consumption, range checks, delayed spells,
        locking spells, and area-of-effect spells.

        :param spell_context: The full spell context.
        :type spell_context: SpellContext
        """
        if spell_context.caster is None or not spell_context.caster.is_alive:
            if self.if_log:
                print("[Spell] Failed: invalid caster.")
            return

        if (
            spell_context.caster.action_points <= 0
            or spell_context.caster.spell_slots < spell_context.spell_cost
        ):
            if self.if_log:
                print("[Spell] Failed: not enough resources.")
            return

        if spell_context.target is not None:
            distance = (
                abs(spell_context.caster.position.x - spell_context.target.position.x)
                + abs(spell_context.caster.position.y - spell_context.target.position.y)
            )
            if distance > spell_context.spell.range:
                if self.if_log:
                    print("[Spell] Failed: target out of range.")
                return

        if spell_context.is_delay_spell and not spell_context.delay_add:
            spell_context.delay_add = True
            self.delayed_spells = np.append(self.delayed_spells, [spell_context])
            spell_context.caster.get_accessor().change_action_points_by(-1)
            spell_context.caster.get_accessor().change_spell_slots_by(-1)
            if self.if_log:
                print("[Spell] Delayed spell added.")
            return

        if spell_context.spell.is_locking_spell:
            if spell_context.target is None:
                if self.if_log:
                    print("[Spell] Failed: no target for locking spell.")
                return

            if not spell_context.target_area.contains(spell_context.target.position):
                if self.if_log:
                    print("[Spell] Target out of range.")
                return
            print(f"spell_context.type: {spell_context.spell.effect_type}")
            self.apply_spell_effect(spell_context.target, spell_context)
            if self.if_log:
                print("[Spell] Effect applied to single target.")
            if self.logdata is not None:
                self.logdata.add_spell(spell_context, self.board)

        else:
            targets: List[Piece] = []
            for piece in self.action_queue:
                if not piece.is_alive:
                    continue

                if not spell_context.target_area.contains(piece.position):
                    continue

                if spell_context.spell.effect_type in [
                    SpellEffectType.DAMAGE,
                    SpellEffectType.DEBUFF,
                ]:
                    if piece.team != spell_context.caster.team:
                        targets.append(piece)
                elif spell_context.spell.effect_type in [
                    SpellEffectType.HEAL,
                    SpellEffectType.BUFF,
                ]:
                    if piece.team == spell_context.caster.team:
                        targets.append(piece)
                elif spell_context.spell.effect_type == SpellEffectType.MOVE:
                    if piece == spell_context.caster:
                        targets.append(piece)

            spell_context.hit_pieces = targets
            for target in targets:
                self.apply_spell_effect(target, spell_context)
                if self.if_log:
                    print("[Spell] Effect applied to target.")
            if self.logdata is not None and targets:
                self.logdata.add_spell(spell_context, self.board)

        spell_context.caster.get_accessor().change_action_points_by(-1)
        spell_context.caster.get_accessor().change_spell_slots_by(-1)

    def apply_spell_effect(self, target: Piece, spell_context: SpellContext) -> None:
        """Apply a spell's effect to a single target piece.

        :param target: The target piece.
        :type target: Piece
        :param spell_context: The spell context containing effect parameters.
        :type spell_context: SpellContext
        """
        accessor = target.get_accessor()

        if spell_context.spell.effect_type == SpellEffectType.DAMAGE:
            accessor.set_health_to(
                max(target.health - spell_context.spell.base_value, 0)
            )
            if target.health <= 0:
                self.handle_death_check(target)
        elif spell_context.spell.effect_type == SpellEffectType.HEAL:
            accessor.set_health_to(
                min(target.health + spell_context.spell.base_value, target.max_health)
            )
        elif spell_context.spell.effect_type == SpellEffectType.BUFF:
            accessor.set_physical_damage_to(
                target.physical_damage + spell_context.spell.base_value
            )
        elif spell_context.spell.effect_type == SpellEffectType.DEBUFF:
            accessor.set_physic_resist_by(spell_context.spell.base_value)
            accessor.set_magic_resist_by(spell_context.spell.base_value)
        elif spell_context.spell.effect_type == SpellEffectType.MOVE:
            if not spell_context.target_area:
                if self.if_log:
                    print("[Spell:Move] Error: no target area specified.")
                return

            target_pos = Point(
                spell_context.target_area.x, spell_context.target_area.y
            )
            path, success = self.board.move_piece(target, target_pos, 100.0)

            if self.if_log:
                print(f"[Spell:Move] Move success: {success}")

            if success:
                target.set_action_points(target.get_action_points() - 1)
                accessor.set_position(target_pos)
            else:
                if self.if_log:
                    print("[Move] Failed: out of range.")

    # ------------------------------------------------------------------
    # Turn management
    # ------------------------------------------------------------------

    def step(self) -> None:
        """Execute a single turn step.

        Resets action points, processes delayed spells, gets player input,
        executes the action, and advances the turn queue.
        """
        self.round_number += 1
        if self.if_log:
            print(f"\n===== Round {self.round_number} =====")

        for piece in self.action_queue:
            if piece.is_alive:
                piece.set_action_points(piece.max_action_points)

        self.current_piece = self.action_queue[0]
        current_player = self.current_piece.team

        if self.if_log:
            print(
                f"Current piece: ID={self.current_piece.id}, player={current_player}"
            )

        for i in range(len(self.delayed_spells) - 1, -1, -1):
            spell = self.delayed_spells[i]
            spell.spell_lifespan -= 1

            if spell.spell_lifespan == 0:
                self.execute_spell(spell)
                self.delayed_spells = np.delete(self.delayed_spells, i)
                if self.if_log:
                    print("[Spell] Delayed spell triggered and removed.")
            elif spell.spell_lifespan < 0:
                self.delayed_spells = np.delete(self.delayed_spells, i)
                if self.if_log:
                    print("[Spell] Delayed spell expired and removed.")

        action = self.input_manager.handle_action_input(current_player, self)
        print(f"envState:{self.if_log}")
        if self.if_log:
            print(f"action: {action}")

        self.action_queue = np.append(self.action_queue[1:], [self.current_piece])

        if action:
            self.execute_player_action(action)

        self.is_game_over = (
            not any(p.is_alive for p in self.player1.pieces)
            or not any(p.is_alive for p in self.player2.pieces)
        )

        if self.is_game_over and self.if_log:
            print("Game over!")
            winner = 1 if any(p.is_alive for p in self.player1.pieces) else 2
            print(f"Player {winner} wins!")

        self.last_round_dead_pieces = np.array(self.new_dead_this_round, dtype=object)
        self.new_dead_this_round = np.array([], dtype=object)

    def execute_player_action(self, action: ActionSet) -> None:
        """Execute a player's action set (move, attack, spell).

        :param action: The action set containing move/attack/spell decisions.
        :type action: ActionSet
        """
        if (
            hasattr(action, "move")
            and action.move
            and self.current_piece.get_action_points() > 0
        ):
            target = action.move_target
            path, success = self.board.move_piece(
                self.current_piece, target, self.current_piece.movement
            )
            if success:
                self.current_piece.set_action_points(
                    self.current_piece.get_action_points() - 1
                )
                if self.logdata is not None and path:
                    self.logdata.add_move(self.current_piece, path, self.board)
                if self.if_log:
                    print(f"Moved to ({target.x}, {target.y}).")
            elif self.if_log:
                print("Move failed.")

        if (
            hasattr(action, "attack")
            and action.attack
            and self.current_piece.get_action_points() > 0
        ):
            if hasattr(action, "attack_context") and action.attack_context:
                self.execute_attack(action.attack_context)
                if self.logdata is not None:
                    self.logdata.add_attack(action.attack_context)
                if (
                    action.attack_context.damage_dealt > 0
                    and self.if_log
                ):
                    print(
                        f"Dealt {action.attack_context.damage_dealt} damage "
                        f"to piece {action.attack_context.target.id}."
                    )
            elif self.if_log:
                print("Invalid attack target.")

        if (
            hasattr(action, "spell")
            and action.spell
            and self.current_piece.spell_slots > 0
            and self.current_piece.get_action_points() > 0
        ):
            if hasattr(action, "spell_context") and action.spell_context:
                self.execute_spell(action.spell_context)
            elif self.if_log:
                print("Invalid spell target.")

    # ------------------------------------------------------------------
    # Board visualisation
    # ------------------------------------------------------------------

    def visualize_board(self) -> None:
        """Display the current board state.

        In local mode (mode == 0), uses colourised terminal output from
        the ``board_visual`` module. Otherwise, uses plain text.
        """
        if self.mode == 0:
            from board_visual import visualize_board as _viz

            _viz(self)
            return

        print("\nCurrent board:")
        print("   ", end="")
        for x in range(self.board.width):
            print(f"{x:2d} ", end="")
        print("\n")

        for y in range(self.board.height):
            print(f"{y:2d} ", end="")
            for x in range(self.board.width):
                cell = self.board.grid[x][y]
                if cell.state == 2:
                    piece = next(
                        (p for p in self.action_queue if p.id == cell.piece_id), None
                    )
                    if piece:
                        print(f"{piece.id:2d} ", end="")
                    else:
                        print("X  ", end="")
                elif cell.state == -1:
                    print("## ", end="")
                else:
                    print(f"{cell.state:2d} ", end="")
            print()
        print()

    # ------------------------------------------------------------------
    # Host-mode methods (used by Saiblo / external game engines)
    # ------------------------------------------------------------------

    def init_board_only(self, board_file: Optional[str] = None) -> None:
        """Load only the board and empty players (no pieces).

        Used by the Saiblo entry point or external game engine to prepare
        the environment before pieces are configured.

        :param board_file: Path to the board file. If None, uses the
            default ``BoardCase/case1.txt``.
        :type board_file: Optional[str]
        """
        path = board_file
        if path is None:
            path = os.path.join(os.path.dirname(__file__), "BoardCase", "case1.txt")
        self.board.init_from_file(path)
        self.player1.id = 1
        self.player2.id = 2
        self.player1.pieces = np.array([], dtype=object)
        self.player2.pieces = np.array([], dtype=object)
        self.action_queue = np.array([], dtype=object)
        self.delayed_spells = np.array([], dtype=object)
        self.last_round_dead_pieces = np.array([], dtype=object)
        self.new_dead_this_round = np.array([], dtype=object)
        self.is_game_over = False
        self.round_number = 0
        self.current_piece = None
        self.is_battle_initialized = False
        self.logdata = None

    def setup_battle_host(self) -> None:
        """Initialise the action queue and board occupancy after both
        players' pieces have been configured.

        :raises ValueError: If either player has no pieces.
        """
        if self.player1.pieces is None or len(self.player1.pieces) == 0:
            raise ValueError("Player 1 pieces not configured.")
        if self.player2.pieces is None or len(self.player2.pieces) == 0:
            raise ValueError("Player 2 pieces not configured.")

        piece_priority: Dict[Piece, int] = {}
        for piece in self.player1.pieces:
            piece_priority[piece] = self.roll_dice(1, 10) + piece.dexterity
        for piece in self.player2.pieces:
            piece_priority[piece] = self.roll_dice(1, 10) + piece.dexterity

        sorted_pieces = sorted(piece_priority.keys(), key=lambda x: -piece_priority[x])
        self.action_queue = np.array(sorted_pieces, dtype=object)
        for i, piece in enumerate(self.action_queue):
            piece.id = i

        self.board.init_pieces_location(
            list(self.player1.pieces), list(self.player2.pieces)
        )
        self.last_round_dead_pieces = np.array([], dtype=object)
        self.is_battle_initialized = True

        from log_converter import LogConverter

        self.logdata = LogConverter()
        self.logdata.init(list(self.action_queue), self.board)

    def begin_turn_host(self) -> None:
        """Begin a new turn: increment round counter, reset action points,
        and set the current piece.

        Does not perform logging.
        """
        if not self.is_battle_initialized or self.is_game_over:
            return
        self.round_number += 1
        for piece in self.action_queue:
            if piece.is_alive:
                piece.set_action_points(piece.max_action_points)
        self.current_piece = self.action_queue[0]
        if self.logdata is not None:
            self.logdata.add_round(self.round_number, list(self.action_queue))

    def apply_action_host(self, action: ActionSet) -> None:
        """Execute the current piece's action and process delayed spells.

        :param action: The action to execute.
        :type action: ActionSet
        """
        if not self.is_battle_initialized or self.is_game_over or self.current_piece is None:
            return
        if action:
            self.execute_player_action(action)

        for i in range(len(self.delayed_spells) - 1, -1, -1):
            spell = self.delayed_spells[i]
            spell.spell_lifespan -= 1
            if spell.spell_lifespan == 0:
                self.execute_spell(spell)
                self.delayed_spells = np.delete(self.delayed_spells, i)
            elif spell.spell_lifespan < 0:
                self.delayed_spells = np.delete(self.delayed_spells, i)

    def end_turn_host(self) -> None:
        """Rotate the action queue, check for game over, and finalise
        the round.

        """
        if not self.is_battle_initialized or self.is_game_over or self.current_piece is None:
            return

        self.action_queue = np.append(self.action_queue[1:], [self.current_piece])

        self.is_game_over = (
            not any(p.is_alive for p in self.player1.pieces)
            or not any(p.is_alive for p in self.player2.pieces)
        )
        if not self.is_game_over and self.round_number >= self.max_rounds:
            self.is_game_over = True

        if self.logdata is not None:
            self.logdata.finish_round(
                self.round_number,
                list(self.action_queue),
                len(self.player1.pieces),
                len(self.player2.pieces),
                self.is_game_over,
                piece_cnt=Player.PIECE_CNT,
            )

        self.last_round_dead_pieces = np.array(self.new_dead_this_round, dtype=object)
        self.new_dead_this_round = np.array([], dtype=object)

    def run(self, board_file: str = "./BoardCase/case1.txt") -> None:
        """Run the full game loop from initialisation to game over.

        :param board_file: Path to the board definition file.
        :type board_file: str
        """
        self.initialize(board_file)

        if self.if_log:
            print("Game initialised, starting game!")
            self.visualize_board()

        while not self.is_game_over:
            self.step()
            if self.if_log:
                self.visualize_board()

            if isinstance(
                self.input_manager.get_input_method(1), ConsoleInputMethod
            ) or isinstance(
                self.input_manager.get_input_method(2), ConsoleInputMethod
            ):
                if input("\nContinue to next round? (y/n): ").lower() != "y":
                    break
