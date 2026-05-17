# Copyright 2026 saiblo platform <https://saiblo.net>
#
# This SDK copy is distributed from https://api.saiblo.net/api/games/56/download/,
# All rights reserved by saiblo platform. All I modified is translating the
# comment and document string from Chinese to English

"""Input method abstractions for the THUAI9 game environment.

Provides pluggable input methods (console, function, remote) and a
manager that dispatches initialisation and action requests to the
appropriate method per player.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from utils import ActionSet, Area, AttackContext, InitPolicyMessage, Point, SpellContext, SpellFactory

if TYPE_CHECKING:
    from env import Environment, InitGameMessage, InitPolicyMessage


class IInputMethod:
    """Interface for all input methods.

    Subclasses must implement ``handle_init_input`` and
    ``handle_action_input``.
    """

    def handle_init_input(
        self, init_message: "InitGameMessage"
    ) -> "InitPolicyMessage":
        """Handle piece initialisation input.

        :param init_message: The initialisation game message.
        :type init_message: InitGameMessage
        :returns: The initialisation policy.
        :rtype: InitPolicyMessage
        """
        raise NotImplementedError()

    def handle_action_input(self, env: "Environment") -> ActionSet:
        """Handle per-turn action input.

        :param env: The game environment.
        :type env: Environment
        :returns: The chosen action set.
        :rtype: ActionSet
        """
        raise NotImplementedError()

    @property
    def name(self) -> str:
        """Return a human-readable name for this input method.

        :returns: The method name.
        :rtype: str
        """
        raise NotImplementedError()


class ConsoleInputMethod(IInputMethod):
    """Console-based input method.

    Reads initialisation and action decisions interactively from stdin.
    """

    @property
    def name(self) -> str:
        return "ConsoleInput"

    def handle_init_input(
        self, init_message: "InitGameMessage"
    ) -> "InitPolicyMessage":
        """Read piece initialisation from the console.

        Prompts for attributes, equipment, and position for each piece.

        :param init_message: The initialisation game message.
        :type init_message: InitGameMessage
        :returns: The initialisation policy.
        :rtype: InitPolicyMessage
        """
        from env import PieceArg

        policy = InitPolicyMessage()  # type: ignore[attr-defined]
        policy.piece_args = []  # type: ignore[attr-defined]

        for i in range(init_message.piece_cnt):
            print(f"--- Player {init_message.id}, piece {i + 1} initialisation ---")
            piece_arg = PieceArg()

            while True:
                print(
                    "Enter attributes (format: strength dexterity intelligence, total <= 30):"
                )
                user_input = input()
                if user_input:
                    try:
                        parts = user_input.split()
                        nums = [int(x) for x in parts]
                        if len(nums) != 3:
                            print("Expected exactly 3 integers.")
                            continue

                        s, d, ig = nums
                        if any(n < 0 for n in nums):
                            print("Attributes cannot be negative.")
                            continue
                        if sum(nums) > 30:
                            print("Attribute total exceeds 30.")
                            continue

                        piece_arg.strength = s
                        piece_arg.dexterity = d
                        piece_arg.intelligence = ig
                        break
                    except ValueError:
                        print("Invalid integer input.")
                        continue

            print()
            print("Weapon / Armour table:")
            print("Weapon:         Phys Dmg    Magic Dmg   Range")
            print("1-Longsword     18          0           5")
            print("2-Shortsword    24          0           3")
            print("3-Bow           16          0           9")
            print("4-Staff         0           22          12")
            print("Armour:         Phys Res    Magic Res   Move Effect")
            print("1-Light         8           10          +3")
            print("2-Medium        15          13          0")
            print("3-Heavy         23          17          -3")

            while True:
                print()
                print("Enter equipment (format: weapon_type(1-4) armour_type(1-3)):")
                user_input = input()
                if user_input:
                    try:
                        parts = user_input.split()
                        if len(parts) != 2:
                            print("Expected exactly 2 integers.")
                            continue

                        weapon, armor = map(int, parts)

                        if not (1 <= weapon <= 4 and 1 <= armor <= 3):
                            print("Values out of range.")
                            continue

                        if weapon == 4 and armor != 1:
                            print("Staff must be paired with light armour.")
                            continue

                        piece_arg.equip = Point(weapon, armor)
                        break
                    except ValueError:
                        print("Invalid integer input.")
                        continue

            while True:
                rows = init_message.board.height
                cols = init_message.board.width
                boarder = init_message.board.boarder

                print()
                print("Enter initial position (format: x y):")
                user_input = input()
                if user_input:
                    try:
                        parts = user_input.split()
                        if len(parts) != 2:
                            print("Expected exactly 2 integers.")
                            continue

                        x, y = map(int, parts)

                        if not (0 <= x < cols and 0 <= y < rows):
                            print("Position out of bounds.")
                            continue

                        if init_message.board.grid[x][y].state != 1:
                            print("Target cell is not walkable.")
                            continue

                        if init_message.id == 1 and y >= boarder:
                            print(
                                f"Player 1 pieces must be below border {boarder}."
                            )
                            continue
                        if init_message.id == 2 and y <= boarder:
                            print(
                                f"Player 2 pieces must be above border {boarder}."
                            )
                            continue

                        is_valid = True
                        for existing_arg in policy.piece_args:  # type: ignore[attr-defined]
                            if x == existing_arg.pos.x and y == existing_arg.pos.y:
                                print("Position already occupied by another piece.")
                                is_valid = False
                                break

                        if not is_valid:
                            continue

                        piece_arg.pos = Point(x, y)
                        break
                    except ValueError:
                        print("Invalid integer input.")
                        continue

            policy.piece_args.append(piece_arg)  # type: ignore[attr-defined]

        return policy

    def handle_action_input(self, env: "Environment") -> ActionSet:
        """Read a turn action from the console.

        :param env: The game environment.
        :type env: Environment
        :returns: The chosen action set.
        :rtype: ActionSet
        """
        print(
            f"\nPlayer {env.current_piece.team}'s turn - "
            f"Piece ID: {env.current_piece.id}"
        )
        print(
            f"Position: ({env.current_piece.position.x}, "
            f"{env.current_piece.position.y})"
        )
        print(
            f"HP: {env.current_piece.health}/{env.current_piece.max_health}"
        )
        print(f"Action points: {env.current_piece.action_points}")
        print(f"Spell slots: {env.current_piece.spell_slots}")

        env.visualize_board()

        action = ActionSet()

        while True:
            print()
            print("Enter move target (format: x y, or -1 -1 to skip):")
            try:
                user_input = input()
                parts = user_input.split()
                if len(parts) != 2:
                    print("Expected exactly 2 integers.")
                    continue

                x, y = map(int, parts)

                if x == -1 or y == -1:
                    action.move = False
                    break

                if not (0 <= x < env.board.width and 0 <= y < env.board.height):
                    print("Target out of bounds.")
                    continue

                if env.board.grid[x][y].state != 1:
                    print("Target cell is not walkable.")
                    continue

                path, cost = env.board.find_shortest_path(
                    env.current_piece,
                    env.current_piece.position,
                    Point(x, y),
                    env.current_piece.movement,
                )
                if path is None or cost > env.current_piece.movement:
                    print("Target out of movement range.")
                    continue

                action.move = True
                action.move_target = Point(x, y)
                break
            except ValueError:
                print("Invalid integer input.")
                continue

        while True:
            print()
            print("Enter target piece ID to attack (or -1 to skip):")
            try:
                target_id = int(input())
                if target_id == -1:
                    action.attack = False
                    break

                target = next(
                    (
                        p
                        for p in env.action_queue
                        if p.id == target_id and p.is_alive
                    ),
                    None,
                )
                if target is None:
                    print("Piece not found.")
                    continue

                if target.team == env.current_piece.team:
                    print("Cannot attack own piece.")
                    continue

                if not env.is_in_attack_range(env.current_piece, target):
                    print("Target out of attack range.")
                    continue

                action.attack = True
                action.attack_context = AttackContext()
                action.attack_context.attacker = env.current_piece
                action.attack_context.target = target
                break
            except ValueError:
                print("Invalid integer input.")
                continue

        print("Cast a spell? (1/-1):")
        spell_choice = input()
        if spell_choice and spell_choice.strip() == "1":
            while True:
                print()
                print("Enter spell ID to cast (or -1 to skip):")
                try:
                    spell_id = int(input())
                    if spell_id == -1:
                        action.spell = False
                        break

                    if env.current_piece.spell_slots <= 0:
                        print("No spell slots remaining.")
                        action.spell = False
                        break

                    spell = SpellFactory.get_spell_by_id(spell_id)
                    if spell is None:
                        print("Spell not found.")
                        continue

                    print(f"\nSelected spell: {spell.name}")
                    print(f"Effect type: {spell.effect_type}")
                    print(f"Base value: {spell.base_value}")
                    print(f"Range: {spell.range}")

                    spell_targets = env.get_spell_targets(spell)
                    if not spell_targets and not spell.is_area_effect:
                        print("No valid targets.")
                        continue

                    print("Enter spell centre coordinates (format: x y):")
                    coords = input().split()
                    if len(coords) != 2:
                        print("Invalid format.")
                        continue

                    cx, cy = map(int, coords)

                    dist = (
                        abs(env.current_piece.position.x - cx)
                        + abs(env.current_piece.position.y - cy)
                    )
                    if dist > spell.range:
                        print(f"Casting range exceeded (max: {spell.range}).")
                        continue

                    target: object | None = None
                    if not spell.is_area_effect:
                        print("Enter target piece ID:")
                        try:
                            tid = int(input())
                            target = next(
                                (p for p in spell_targets if p.id == tid), None
                            )
                            if target is None:
                                print("Invalid target.")
                                continue
                        except ValueError:
                            print("Invalid integer input.")
                            continue

                    action.spell = True
                    action.spell_context = SpellContext()
                    action.spell_context.caster = env.current_piece
                    action.spell_context.target = target
                    action.spell_context.spell = spell
                    action.spell_context.target_area = Area(
                        cx, cy, spell.area_radius
                    )
                    action.spell_context.is_delay_spell = spell.is_delay_spell
                    action.spell_context.spell_lifespan = spell.base_lifespan
                    break
                except ValueError:
                    print("Invalid integer input.")
                    continue
        else:
            action.spell = False

        return action


class FunctionInputMethod(IInputMethod):
    """Function-based input method for AI strategies.

    Wraps callable init and action handlers for use with the input
    method system.

    :param init_handler: A callable that takes an InitGameMessage and
        returns a list of PieceArg.
    :type init_handler: Callable
    :param action_handler: A callable that takes an Environment and
        returns an ActionSet.
    :type action_handler: Callable
    """

    def __init__(
        self,
        init_handler: Callable[..., list],
        action_handler: Callable[..., ActionSet],
    ) -> None:
        self._init_handler = init_handler
        self._action_handler = action_handler

    @property
    def name(self) -> str:
        return "FunctionInput"

    def handle_init_input(
        self, init_message: "InitGameMessage"
    ) -> "InitPolicyMessage":
        """Execute the registered init handler.

        :param init_message: The initialisation game message.
        :type init_message: InitGameMessage
        :returns: The initialisation policy.
        :rtype: InitPolicyMessage
        """
        piece_args = self._init_handler(init_message)
        policy = InitPolicyMessage()  # type: ignore[attr-defined]
        policy.piece_args = piece_args
        return policy

    def handle_action_input(self, env: "Environment") -> ActionSet:
        """Execute the registered action handler.

        :param env: The game environment.
        :type env: Environment
        :returns: The chosen action set.
        :rtype: ActionSet
        """
        print(
            f"[FunctionInput] Executing action handler for "
            f"player {env.current_piece.team}"
        )
        try:
            action = self._action_handler(env)
            print("[FunctionInput] Action handler executed successfully.")
            return action
        except Exception as e:
            print(f"[FunctionInput] Error: {e}")
            raise


class RemoteInputMethod(IInputMethod):
    """Remote input method stub.

    Not used in the current implementation; remote input is handled
    via the Saiblo protocol directly.
    """

    def __init__(self, env: "Environment") -> None:
        self._env = env

    @property
    def name(self) -> str:
        return "RemoteInput"

    def handle_init_input(
        self, init_message: "InitGameMessage"
    ) -> "InitPolicyMessage":
        raise NotImplementedError(
            "Remote input method uses gRPC client for initialisation."
        )

    def handle_action_input(self, env: "Environment") -> ActionSet:
        raise NotImplementedError(
            "Remote input method uses gRPC client for action input."
        )


class InputMethodManager:
    """Manages input methods per player.

    :param env: The game environment.
    :type env: Environment
    """

    def __init__(self, env: "Environment") -> None:
        self._env = env
        self._player_input_methods: dict = {}

        self.set_console_input_method(1)
        self.set_console_input_method(2)

    def set_input_method(self, player_id: int, input_method: IInputMethod) -> None:
        """Set the input method for a player.

        :param player_id: The player ID (1 or 2).
        :type player_id: int
        :param input_method: The input method to use.
        :type input_method: IInputMethod
        """
        self._player_input_methods[player_id] = input_method

    def get_input_method(self, player_id: int) -> IInputMethod:
        """Get the input method for a player.

        Defaults to ``ConsoleInputMethod`` if none has been set.

        :param player_id: The player ID (1 or 2).
        :type player_id: int
        :returns: The player's input method.
        :rtype: IInputMethod
        """
        if player_id in self._player_input_methods:
            return self._player_input_methods[player_id]

        default = ConsoleInputMethod()
        self._player_input_methods[player_id] = default
        return default

    def set_function_input_method(
        self,
        player_id: int,
        init_handler: Callable[..., list],
        action_handler: Callable[..., ActionSet],
    ) -> None:
        """Set a function-based input method for a player.

        :param player_id: The player ID (1 or 2).
        :type player_id: int
        :param init_handler: The initialisation handler.
        :type init_handler: Callable
        :param action_handler: The action handler.
        :type action_handler: Callable
        """
        method = FunctionInputMethod(init_handler, action_handler)
        self.set_input_method(player_id, method)

    def set_console_input_method(self, player_id: int) -> None:
        """Set console input method for a player.

        :param player_id: The player ID (1 or 2).
        :type player_id: int
        """
        self.set_input_method(player_id, ConsoleInputMethod())

    def set_remote_input_method(self, player_id: int) -> None:
        """Set remote input method for a player.

        :param player_id: The player ID (1 or 2).
        :type player_id: int
        """
        self.set_input_method(player_id, RemoteInputMethod(self._env))

    def handle_init_input(
        self, player_id: int, init_message: "InitGameMessage"
    ) -> "InitPolicyMessage":
        """Dispatch an init request to the player's input method.

        :param player_id: The player ID.
        :type player_id: int
        :param init_message: The initialisation message.
        :type init_message: InitGameMessage
        :returns: The initialisation policy.
        :rtype: InitPolicyMessage
        :raises ValueError: If the input method is remote.
        """
        method = self.get_input_method(player_id)
        if isinstance(method, RemoteInputMethod):
            raise ValueError(
                "Remote input method uses gRPC client for initialisation."
            )
        return method.handle_init_input(init_message)

    def handle_action_input(
        self, player_id: int, env: "Environment"
    ) -> ActionSet:
        """Dispatch an action request to the player's input method.

        :param player_id: The player ID.
        :type player_id: int
        :param env: The game environment.
        :type env: Environment
        :returns: The chosen action set.
        :rtype: ActionSet
        :raises ValueError: If the input method is remote.
        """
        method = self.get_input_method(player_id)
        print(
            f"[InputManager] Player {player_id} input method: "
            f"{method.name}"
        )

        if isinstance(method, RemoteInputMethod):
            raise ValueError(
                "Remote input method uses gRPC client for action input."
            )

        print(f"[InputManager] Processing action for player {player_id}.")
        action = method.handle_action_input(env)
        print(f"[InputManager] Action for player {player_id} completed.")
        return action

    def is_remote_input(self, player_id: int) -> bool:
        """Check whether a player is using remote input.

        :param player_id: The player ID.
        :type player_id: int
        :returns: True if the player uses remote input.
        :rtype: bool
        """
        return isinstance(self.get_input_method(player_id), RemoteInputMethod)
