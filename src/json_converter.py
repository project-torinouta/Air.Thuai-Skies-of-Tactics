# Copyright 2026 saiblo platform <https://saiblo.net>
#
# This SDK copy is distributed from https://api.saiblo.net/api/games/56/download/,
# All rights reserved by saiblo platform. All I modified is translating the
# comment and document string from Chinese to English

"""JSON state serialisation and deserialisation for the THUAI9 protocol.

Deserialises game state JSON (from the C#/Python game engine) into
Environment objects, and serialises ActionSet objects into the JSON
format expected by the game engine.

Field names align with ``GameEngine.cs`` / ``server_python game_engine`` DTOs.
"""

from typing import Any, Optional

import numpy as np

from env import Board, Cell, Environment, Piece, Player, SpellContext

from utils import Area, Point, SpellFactory, TargetType


def _target_type_from_index(idx: int) -> TargetType:
    """Convert an integer index to the corresponding TargetType enum member.

    :param idx: The target type index (0-based).
    :type idx: int
    :returns: The matching TargetType, or TargetType.SINGLE if out of range.
    :rtype: TargetType
    """
    members = list(TargetType)
    if 0 <= int(idx) < len(members):
        return members[int(idx)]
    return TargetType.SINGLE


def _piece_by_id(queue: Any, piece_id: Optional[int]) -> Optional[Piece]:
    """Find a piece in the action queue by its ID.

    :param queue: The action queue (iterable of Piece objects).
    :type queue: Any
    :param piece_id: The piece ID to search for. None or negative returns None.
    :type piece_id: Optional[int]
    :returns: The matching Piece, or None if not found.
    :rtype: Optional[Piece]
    """
    if piece_id is None or int(piece_id) < 0:
        return None
    pid = int(piece_id)
    for p in queue:
        if int(p.id) == pid:
            return p
    return None


def env_from_state_json(state: dict, env: Environment) -> None:
    """Deserialise a JSON game state dict into an Environment object (in-place).

    :param state: The game state dictionary from the game engine.
    :type state: dict
    :param env: The environment object to update.
    :type env: Environment
    """
    env.round_number = state.get("currentRound", 0)
    env.is_game_over = state.get("isGameOver", False)

    board_data = state.get("board")
    if board_data:
        board = Board(if_log=0)
        board.width = board_data["width"]
        board.height = board_data["height"]
        board.boarder = board_data.get("boarder", board.height // 2)

        grid_flat = board_data.get("grid", [])
        board.grid = np.empty((board.width, board.height), dtype=object)
        for i, cell_data in enumerate(grid_flat):
            x = i // board.height
            y = i % board.height
            board.grid[x][y] = Cell(
                state=cell_data.get("state", 1),
                player_id=cell_data.get("playerId", -1),
                piece_id=cell_data.get("pieceId", -1),
            )

        hmap = board_data.get("height_map", [])
        board.height_map = np.zeros((board.width, board.height), dtype=int)
        for i, val in enumerate(hmap):
            x = i // board.height
            y = i % board.height
            board.height_map[x][y] = val

        env.board = board

    pieces: list = []
    for p in state.get("actionQueue", []):
        piece = Piece()
        piece.id = p.get("id", 0)
        piece.team = p.get("team", 0)
        piece.health = p.get("health", 0)
        piece.max_health = p.get("max_health", 0)
        piece.physical_resist = p.get("physical_resist", 0)
        piece.magic_resist = p.get("magic_resist", 0)
        piece.physical_damage = p.get("physical_damage", 0)
        piece.magic_damage = p.get("magic_damage", 0)
        piece.action_points = p.get("action_points", 0)
        piece.max_action_points = p.get("max_action_points", 0)
        piece.spell_slots = p.get("spell_slots", 0)
        piece.max_spell_slots = p.get("max_spell_slots", 0)
        piece.movement = p.get("movement", 0.0)
        piece.max_movement = p.get("max_movement", 0.0)
        piece.strength = p.get("strength", 0)
        piece.dexterity = p.get("dexterity", 0)
        piece.intelligence = p.get("intelligence", 0)
        pos = p.get("position", {})
        piece.position = Point(pos.get("x", 0), pos.get("y", 0))
        piece.height = p.get("height", 0)
        piece.attack_range = p.get("attack_range", 0)
        piece.spell_range = p.get("spell_range", 0.0)
        piece.is_alive = p.get("is_alive", True)
        piece.is_in_turn = p.get("is_in_turn", False)
        piece.is_dying = p.get("is_dying", False)
        piece.death_round = p.get("deathRound", -1)
        piece.queue_index = p.get("queue_index", 0)
        sl = p.get("spell_list")
        if isinstance(sl, list):
            piece.spell_list = [int(x) for x in sl]
        else:
            piece.spell_list = []
        piece.weapon_type = int(p.get("weapon_type", p.get("weaponType", 0)))

        atk_range = piece.attack_range
        if piece.magic_damage > 0:
            piece.type = "Mage"
        elif atk_range >= 9:
            piece.type = "Archer"
        else:
            piece.type = "Warrior"
        pieces.append(piece)

    env.action_queue = np.array(pieces, dtype=object)

    current_id = state.get("currentPieceID", -1)
    env.current_piece = next(
        (p for p in env.action_queue if p.id == current_id), None
    )

    if env.player1 is None:
        env.player1 = Player()
        env.player1.id = 1
    if env.player2 is None:
        env.player2 = Player()
        env.player2.id = 2
    env.player1.pieces = np.array(
        [p for p in env.action_queue if p.team == 1], dtype=object
    )
    env.player2.pieces = np.array(
        [p for p in env.action_queue if p.team == 2], dtype=object
    )

    delayed = []
    for ds in state.get("delayedSpells", []):
        sc = SpellContext()
        sc.spell_lifespan = int(ds.get("spellLifespan", 0))
        spell_id = int(ds.get("spellID", 0))
        sc.spell = SpellFactory.get_spell_by_id(spell_id)
        sc.target_type = _target_type_from_index(int(ds.get("targetType", 0)))
        sc.caster = _piece_by_id(env.action_queue, ds.get("caster"))
        tid = ds.get("target", -1)
        sc.target = _piece_by_id(env.action_queue, tid)
        area = ds.get("targetArea")
        if area:
            sc.target_area = Area(
                int(area.get("x", 0)),
                int(area.get("y", 0)),
                int(area.get("radius", 0)),
            )
        delayed.append(sc)
    env.delayed_spells = np.array(delayed, dtype=object)


def action_to_dict(action: Any, player_id: int) -> dict:
    """Serialise an ActionSet into the ActionSetDto JSON format.

    The output format matches the contract expected by
    ``GameEngine.ExecuteAction``.

    :param action: The ActionSet to serialise.
    :type action: ActionSet
    :param player_id: The player's Saiblo ID (0-based).
    :type player_id: int
    :returns: A dictionary representing the action DTO.
    :rtype: dict
    """
    d: dict = {
        "move": bool(getattr(action, "move", False)),
        "attack": bool(getattr(action, "attack", False)),
        "spell": bool(getattr(action, "spell", False)),
    }

    if d["move"] and getattr(action, "move_target", None):
        d["move_target"] = {
            "x": action.move_target.x,
            "y": action.move_target.y,
        }

    if d["attack"] and getattr(action, "attack_context", None):
        ctx = action.attack_context
        d["attack_context"] = {
            "target": ctx.target.id if ctx.target else -1,
        }

    if d["spell"] and getattr(action, "spell_context", None):
        ctx = action.spell_context
        tt = getattr(ctx, "target_type", None)
        members = list(TargetType)
        tt_idx = members.index(tt) if tt in members else 0

        sc: dict = {
            "spellID": ctx.spell.id if ctx.spell else 0,
            "targetType": tt_idx,
            "target": ctx.target.id if ctx.target else -1,
            "spellLifespan": getattr(ctx, "spell_lifespan", 0),
        }
        if getattr(ctx, "target_area", None):
            sc["targetArea"] = {
                "x": ctx.target_area.x,
                "y": ctx.target_area.y,
                "radius": ctx.target_area.radius,
            }
        d["spell_context"] = sc

    return d
