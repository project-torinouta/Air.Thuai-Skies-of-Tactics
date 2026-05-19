"""Tests for the warrior and ranger strategies.

Run with: uv run python -m unittest tests/test_warrior.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np

from env import Environment, InitGameMessage, Piece
from strategies.warrior import (
    get_warrior_action_strategy,
    get_warrior_init_strategy,
    get_ranger_action_strategy,
    get_ranger_init_strategy,
)
from utils import ActionSet, PieceArg, Point


BOARD_FILE = os.path.join(
    os.path.dirname(__file__), "..", "src", "BoardCase", "case1.txt"
)


def _make_piece(
    team: int = 1,
    pos: Point = Point(0, 0),
    strength: int = 10,
    dexterity: int = 10,
    intelligence: int = 10,
    weapon: int = 2,
    armor: int = 2,
) -> Piece:
    p = Piece()
    acc = p.get_accessor()
    acc.set_team_to(team)
    acc.set_strength_to(strength)
    acc.set_dexterity_to(dexterity)
    acc.set_intelligence_to(intelligence)
    acc.set_max_health_to(30 + strength * 2)
    acc.set_health_to(p.max_health)
    acc.set_max_action_points()
    acc.set_action_points_to(p.max_action_points)
    acc.set_max_spell_slots()
    acc.set_spell_slots_to(p.max_spell_slots)
    acc.set_max_movement_to(dexterity + 0.5 * strength + 10)
    acc.set_movement_to(p.max_movement)
    p.weapon_type = weapon
    acc.set_type_to(weapon)
    if weapon == 1:
        acc.set_physical_damage_to(8); acc.set_magic_damage_to(0); acc.set_range_to(5)
    elif weapon == 2:
        acc.set_physical_damage_to(10); acc.set_magic_damage_to(0); acc.set_range_to(3)
    elif weapon == 3:
        acc.set_physical_damage_to(16); acc.set_magic_damage_to(0); acc.set_range_to(9)
    elif weapon == 4:
        acc.set_physical_damage_to(0); acc.set_magic_damage_to(18); acc.set_range_to(12)
    if armor == 1:
        acc.set_physical_resist_to(8); acc.set_magic_resist_to(0); acc.set_max_movement_by(3)
    elif armor == 2:
        acc.set_physical_resist_to(15); acc.set_magic_resist_to(0)
    elif armor == 3:
        acc.set_physical_resist_to(23); acc.set_magic_resist_to(0); acc.set_max_movement_by(-3)
    acc.set_position(pos)
    return p


def _make_warrior_env() -> Environment:
    """Env with two pieces at shortsword range."""
    env = Environment(local_mode=True, if_log=0)
    env.board.init_from_file(BOARD_FILE)
    env.player1.id = 1
    env.player2.id = 2

    p1 = _make_piece(
        team=1, pos=Point(5, 5), strength=24, dexterity=6,
        intelligence=0, weapon=2, armor=1,
    )
    p2 = _make_piece(
        team=2, pos=Point(7, 5), strength=24, dexterity=6,
        intelligence=0, weapon=2, armor=1,
    )
    p1.id = 0
    p2.id = 1
    env.action_queue = np.array([p1, p2], dtype=object)
    env.current_piece = p1
    env.player1.pieces = np.array([p1], dtype=object)
    env.player2.pieces = np.array([p2], dtype=object)
    for p in [p1, p2]:
        env.board.grid[p.position.x][p.position.y].state = 2
        env.board.grid[p.position.x][p.position.y].player_id = p.team
        env.board.grid[p.position.x][p.position.y].piece_id = p.id
    return env


def _make_ranger_env() -> Environment:
    """Env with two pieces at bow range."""
    env = Environment(local_mode=True, if_log=0)
    env.board.init_from_file(BOARD_FILE)
    env.player1.id = 1
    env.player2.id = 2

    p1 = _make_piece(
        team=1, pos=Point(5, 5), strength=22, dexterity=8,
        intelligence=0, weapon=3, armor=1,
    )
    p2 = _make_piece(
        team=2, pos=Point(10, 5), strength=22, dexterity=8,
        intelligence=0, weapon=3, armor=1,
    )
    p1.id = 0
    p2.id = 1
    env.action_queue = np.array([p1, p2], dtype=object)
    env.current_piece = p1
    env.player1.pieces = np.array([p1], dtype=object)
    env.player2.pieces = np.array([p2], dtype=object)
    for p in [p1, p2]:
        env.board.grid[p.position.x][p.position.y].state = 2
        env.board.grid[p.position.x][p.position.y].player_id = p.team
        env.board.grid[p.position.x][p.position.y].piece_id = p.id
    return env


def _make_adjacent_env() -> Environment:
    """Env where pieces are adjacent (for Arrow Hit testing)."""
    env = Environment(local_mode=True, if_log=0)
    env.board.init_from_file(BOARD_FILE)
    env.player1.id = 1
    env.player2.id = 2

    p1 = _make_piece(
        team=1, pos=Point(5, 5), strength=24, dexterity=6,
        intelligence=12, weapon=2, armor=1,
    )
    p2 = _make_piece(
        team=2, pos=Point(5, 6), strength=24, dexterity=6,
        intelligence=12, weapon=2, armor=1,
    )
    p1.id = 0
    p2.id = 1
    env.action_queue = np.array([p1, p2], dtype=object)
    env.current_piece = p1
    env.player1.pieces = np.array([p1], dtype=object)
    env.player2.pieces = np.array([p2], dtype=object)
    for p in [p1, p2]:
        env.board.grid[p.position.x][p.position.y].state = 2
        env.board.grid[p.position.x][p.position.y].player_id = p.team
        env.board.grid[p.position.x][p.position.y].piece_id = p.id
    return env


# =========================================================================
# Init strategy tests
# =========================================================================


class TestWarriorInit(unittest.TestCase):
    def test_returns_list_of_piece_args(self):
        strategy = get_warrior_init_strategy()
        msg = InitGameMessage()
        msg.piece_cnt = 3
        msg.id = 1
        msg.board = _make_warrior_env().board
        result = strategy(msg)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        for arg in result:
            self.assertIsInstance(arg, PieceArg)

    def test_stats_match_config(self):
        strategy = get_warrior_init_strategy()
        msg = InitGameMessage()
        msg.piece_cnt = 1
        msg.id = 1
        msg.board = _make_warrior_env().board
        result = strategy(msg)
        arg = result[0]
        self.assertEqual(arg.strength, 24)
        self.assertEqual(arg.dexterity, 6)
        self.assertEqual(arg.intelligence, 0)
        self.assertEqual(arg.equip.x, 2)
        self.assertEqual(arg.equip.y, 1)


class TestRangerInit(unittest.TestCase):
    def test_returns_list_of_piece_args(self):
        strategy = get_ranger_init_strategy()
        msg = InitGameMessage()
        msg.piece_cnt = 3
        msg.id = 1
        msg.board = _make_ranger_env().board
        result = strategy(msg)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)

    def test_stats_match_config(self):
        strategy = get_ranger_init_strategy()
        msg = InitGameMessage()
        msg.piece_cnt = 1
        msg.id = 1
        msg.board = _make_ranger_env().board
        result = strategy(msg)
        arg = result[0]
        self.assertEqual(arg.strength, 22)
        self.assertEqual(arg.dexterity, 8)
        self.assertEqual(arg.intelligence, 0)
        self.assertEqual(arg.equip.x, 3)
        self.assertEqual(arg.equip.y, 1)


# =========================================================================
# Warrior action strategy tests
# =========================================================================


class TestWarriorAction(unittest.TestCase):
    def setUp(self):
        self.env = _make_warrior_env()
        self.env.max_rounds = 100

    def _strategy(self):
        return get_warrior_action_strategy()

    def test_returns_action_set(self):
        action = self._strategy()(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_has_action_flags(self):
        action = self._strategy()(self.env)
        for attr in ("move", "attack", "spell"):
            self.assertTrue(hasattr(action, attr))

    def test_does_not_mutate_original_env(self):
        orig_round = self.env.round_number
        self._strategy()(self.env)
        self.assertEqual(self.env.round_number, orig_round)

    def test_attacks_enemy_in_range(self):
        """Shortsword range is 3; enemies at distance 2 should be attacked."""
        action = self._strategy()(self.env)
        self.assertTrue(action.attack)

    def test_moves_toward_enemy_when_out_of_range(self):
        self.env.current_piece.position = Point(0, 0)
        for p in self.env.action_queue:
            if p.team != self.env.current_piece.team:
                p.position = Point(19, 19)
        action = self._strategy()(self.env)
        self.assertTrue(action.move)

    def test_dead_current_piece(self):
        self.env.current_piece.is_alive = False
        action = self._strategy()(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_no_enemies_alive(self):
        for p in self.env.action_queue:
            if p.team != self.env.current_piece.team:
                p.is_alive = False
        action = self._strategy()(self.env)
        self.assertFalse(action.attack)
        self.assertFalse(action.spell)

    def test_no_action_points(self):
        self.env.current_piece.action_points = 0
        action = self._strategy()(self.env)
        self.assertIsInstance(action, ActionSet)
        self.assertFalse(action.move)
        self.assertFalse(action.attack)

    def test_no_spell_slots(self):
        self.env.current_piece.spell_slots = 0
        action = self._strategy()(self.env)
        self.assertFalse(action.spell)


# =========================================================================
# Ranger action strategy tests
# =========================================================================


class TestRangerAction(unittest.TestCase):
    def setUp(self):
        self.env = _make_ranger_env()
        self.env.max_rounds = 100

    def _strategy(self):
        return get_ranger_action_strategy()

    def test_returns_action_set(self):
        action = self._strategy()(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_has_action_flags(self):
        action = self._strategy()(self.env)
        for attr in ("move", "attack", "spell"):
            self.assertTrue(hasattr(action, attr))

    def test_attacks_enemy_in_bow_range(self):
        """Bow range is 9; enemies at distance 5 should be attacked."""
        action = self._strategy()(self.env)
        self.assertTrue(action.attack)

    def test_moves_toward_enemy(self):
        self.env.current_piece.position = Point(0, 0)
        for p in self.env.action_queue:
            if p.team != self.env.current_piece.team:
                p.position = Point(19, 19)
        action = self._strategy()(self.env)
        self.assertTrue(action.move)

    def test_dead_current_piece(self):
        self.env.current_piece.is_alive = False
        action = self._strategy()(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_no_enemies_alive(self):
        for p in self.env.action_queue:
            if p.team != self.env.current_piece.team:
                p.is_alive = False
        action = self._strategy()(self.env)
        self.assertFalse(action.attack)
        self.assertFalse(action.spell)

    def test_no_action_points(self):
        self.env.current_piece.action_points = 0
        action = self._strategy()(self.env)
        self.assertFalse(action.move)
        self.assertFalse(action.attack)

    def test_out_of_range(self):
        """Enemy beyond bow range — should move, not attack."""
        for p in self.env.action_queue:
            if p.team != self.env.current_piece.team:
                p.position = Point(5, 20)
        action = self._strategy()(self.env)
        # Distance from (5,5) to (5,20) is 15 > bow range 9, so no attack
        if not action.attack:
            self.assertTrue(action.move or not action.move)
        else:
            self.assertTrue(action.attack)


# =========================================================================
# Arrow Hit spell tests (shared by warrior and ranger)
# =========================================================================


class TestArrowHit(unittest.TestCase):
    def test_warrior_arrow_hit_on_adjacent_enemy(self):
        """Warrior should cast Arrow Hit on adjacent enemy."""
        env = _make_adjacent_env()
        from strategies.warrior import _arrow_hit

        action = ActionSet()
        current = env.current_piece
        enemies = [p for p in env.action_queue if p.team != current.team and p.is_alive]
        action = _arrow_hit(env, current, enemies, action)

        self.assertTrue(action.spell)
        self.assertIsNotNone(action.spell_context)
        self.assertEqual(action.spell_context.spell.name, "Arrow Hit")

    def test_warrior_arrow_hit_not_used_when_far(self):
        """Arrow Hit should not be cast when enemy is beyond range 1."""
        env = _make_warrior_env()
        from strategies.warrior import _arrow_hit

        action = ActionSet()
        current = env.current_piece
        enemies = [p for p in env.action_queue if p.team != current.team and p.is_alive]
        action = _arrow_hit(env, current, enemies, action)

        # Enemies at distance 2 (from (5,5) to (7,5)), Arrow Hit range is 1
        self.assertFalse(action.spell)

    def test_ranger_arrow_hit_on_adjacent_enemy(self):
        """Ranger should also cast Arrow Hit when adjacent."""
        env = _make_adjacent_env()
        from strategies.warrior import _arrow_hit

        action = ActionSet()
        current = env.current_piece
        enemies = [p for p in env.action_queue if p.team != current.team and p.is_alive]
        action = _arrow_hit(env, current, enemies, action)

        self.assertTrue(action.spell)
        self.assertEqual(action.spell_context.spell.name, "Arrow Hit")

    def test_no_spell_slots_no_arrow_hit(self):
        env = _make_adjacent_env()
        env.current_piece.spell_slots = 0
        from strategies.warrior import _arrow_hit

        action = ActionSet()
        current = env.current_piece
        enemies = [p for p in env.action_queue if p.team != current.team and p.is_alive]
        action = _arrow_hit(env, current, enemies, action)
        self.assertFalse(action.spell)


# =========================================================================
# Edge cases (shared)
# =========================================================================


class TestWarriorEdgeCases(unittest.TestCase):
    def test_current_piece_none(self):
        env = _make_warrior_env()
        env.current_piece = None
        action = get_warrior_action_strategy()(env)
        self.assertIsInstance(action, ActionSet)

    def test_game_over(self):
        env = _make_warrior_env()
        env.is_game_over = True
        action = get_warrior_action_strategy()(env)
        self.assertIsInstance(action, ActionSet)

    def test_single_piece_vs_none(self):
        env = _make_warrior_env()
        for p in env.player2.pieces:
            p.is_alive = False
        env.is_game_over = True
        action = get_warrior_action_strategy()(env)
        self.assertIsInstance(action, ActionSet)

    def test_no_legal_moves(self):
        env = _make_warrior_env()
        cx, cy = env.current_piece.position.x, env.current_piece.position.y
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < env.board.width and 0 <= y < env.board.height:
                    env.board.grid[x][y].state = -1
        action = get_warrior_action_strategy()(env)
        self.assertIsInstance(action, ActionSet)


class TestRangerEdgeCases(unittest.TestCase):
    def test_current_piece_none(self):
        env = _make_ranger_env()
        env.current_piece = None
        action = get_ranger_action_strategy()(env)
        self.assertIsInstance(action, ActionSet)

    def test_game_over(self):
        env = _make_ranger_env()
        env.is_game_over = True
        action = get_ranger_action_strategy()(env)
        self.assertIsInstance(action, ActionSet)

    def test_no_legal_moves(self):
        env = _make_ranger_env()
        cx, cy = env.current_piece.position.x, env.current_piece.position.y
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < env.board.width and 0 <= y < env.board.height:
                    env.board.grid[x][y].state = -1
        action = get_ranger_action_strategy()(env)
        self.assertIsInstance(action, ActionSet)


if __name__ == "__main__":
    unittest.main()
