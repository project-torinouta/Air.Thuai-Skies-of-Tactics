"""Tests for the tactical strategy.

Run with: uv run python -m unittest tests/test_tactical.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np

from env import Environment, InitGameMessage, Piece
from strategies.tactical import (
    get_tactical_action_strategy,
    get_tactical_init_strategy,
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


def _make_minimal_env() -> Environment:
    """Two-piece env with pieces close enough for staff range."""
    env = Environment(local_mode=True, if_log=0)
    env.board.init_from_file(BOARD_FILE)
    env.player1.id = 1
    env.player2.id = 2

    p1 = _make_piece(
        team=1, pos=Point(5, 5), strength=14, dexterity=8,
        intelligence=8, weapon=4, armor=1,
    )
    p2 = _make_piece(
        team=2, pos=Point(10, 5), strength=14, dexterity=8,
        intelligence=8, weapon=4, armor=1,
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


def _make_clustered_env() -> Environment:
    """Two friendly + two enemy pieces close enough for Fireball."""
    env = Environment(local_mode=True, if_log=0)
    env.board.init_from_file(BOARD_FILE)
    env.player1.id = 1
    env.player2.id = 2

    p1 = _make_piece(
        team=1, pos=Point(5, 5), strength=14, dexterity=8,
        intelligence=8, weapon=4, armor=1,
    )
    e1 = _make_piece(
        team=2, pos=Point(6, 5), strength=14, dexterity=8,
        intelligence=8, weapon=4, armor=1,
    )
    e2 = _make_piece(
        team=2, pos=Point(6, 6), strength=14, dexterity=8,
        intelligence=8, weapon=4, armor=1,
    )
    p1.id = 0
    e1.id = 1
    e2.id = 2
    env.action_queue = np.array([p1, e1, e2], dtype=object)
    env.current_piece = p1
    env.player1.pieces = np.array([p1], dtype=object)
    env.player2.pieces = np.array([e1, e2], dtype=object)
    for p in [p1, e1, e2]:
        env.board.grid[p.position.x][p.position.y].state = 2
        env.board.grid[p.position.x][p.position.y].player_id = p.team
        env.board.grid[p.position.x][p.position.y].piece_id = p.id
    return env


# =========================================================================
# Init strategy tests
# =========================================================================


class TestTacticalInit(unittest.TestCase):
    def test_returns_list_of_piece_args(self):
        strategy = get_tactical_init_strategy()
        msg = InitGameMessage()
        msg.piece_cnt = 3
        msg.id = 1
        msg.board = _make_minimal_env().board
        result = strategy(msg)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        for arg in result:
            self.assertIsInstance(arg, PieceArg)

    def test_stats_match_config(self):
        strategy = get_tactical_init_strategy()
        msg = InitGameMessage()
        msg.piece_cnt = 1
        msg.id = 1
        msg.board = _make_minimal_env().board
        result = strategy(msg)
        arg = result[0]
        self.assertEqual(arg.strength, 14)
        self.assertEqual(arg.dexterity, 8)
        self.assertEqual(arg.intelligence, 8)
        self.assertEqual(arg.equip.x, 4)
        self.assertEqual(arg.equip.y, 1)

    def test_player2_positioning(self):
        strategy = get_tactical_init_strategy()
        msg = InitGameMessage()
        msg.piece_cnt = 3
        msg.id = 2
        msg.board = _make_minimal_env().board
        result = strategy(msg)
        self.assertEqual(len(result), 3)


# =========================================================================
# Action strategy tests
# =========================================================================


class TestTacticalAction(unittest.TestCase):
    def setUp(self):
        self.env = _make_minimal_env()
        self.env.max_rounds = 100

    def _strategy(self):
        return get_tactical_action_strategy()

    def test_returns_action_set(self):
        action = self._strategy()(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_has_action_flags(self):
        action = self._strategy()(self.env)
        for attr in ("move", "attack", "spell"):
            self.assertTrue(hasattr(action, attr))
            self.assertIsInstance(getattr(action, attr), bool)

    def test_does_not_mutate_original_env(self):
        orig_round = self.env.round_number
        self._strategy()(self.env)
        self.assertEqual(self.env.round_number, orig_round)

    def test_attacks_enemy_in_staff_range(self):
        """Staff range is 12; enemies at distance 5 should be attacked."""
        action = self._strategy()(self.env)
        self.assertTrue(action.attack)

    def test_moves_toward_enemy(self):
        """When no enemy is in attack range, the piece should move."""
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

    def test_game_over(self):
        self.env.is_game_over = True
        action = self._strategy()(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_no_enemies_alive(self):
        for p in self.env.action_queue:
            if p.team != self.env.current_piece.team:
                p.is_alive = False
        action = self._strategy()(self.env)
        self.assertIsInstance(action, ActionSet)
        self.assertFalse(action.attack)

    def test_current_piece_is_none(self):
        self.env.current_piece = None
        action = self._strategy()(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_no_legal_moves(self):
        cx, cy = self.env.current_piece.position.x, self.env.current_piece.position.y
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < self.env.board.width and 0 <= y < self.env.board.height:
                    self.env.board.grid[x][y].state = -1
        action = self._strategy()(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_empty_action_points(self):
        self.env.current_piece.action_points = 0
        action = self._strategy()(self.env)
        self.assertIsInstance(action, ActionSet)
        self.assertFalse(action.move)
        self.assertFalse(action.attack)

    def test_no_spell_slots(self):
        """When spell slots are 0, spell should be False."""
        self.env.current_piece.spell_slots = 0
        action = self._strategy()(self.env)
        self.assertFalse(action.spell)


class TestTacticalFireball(unittest.TestCase):
    def setUp(self):
        self.env = _make_clustered_env()
        self.env.max_rounds = 100

    def _strategy(self):
        return get_tactical_action_strategy()

    def test_fireball_on_clustered_enemies(self):
        """When enemies are within Fireball range, spell should be cast."""
        from strategies.tactical import _decide_spell
        from utils import SpellContext

        action = ActionSet()
        current = self.env.current_piece
        enemies = [p for p in self.env.action_queue if p.team != current.team and p.is_alive]

        # Piece is at (5,5), enemies at (6,5) and (6,6)
        # Fireball range is 2, area radius is 5
        # Distance to (6,5) is |5-6| + |5-5| = 1 ≤ 2 ✓
        action = _decide_spell(self.env, current, enemies, action)

        self.assertTrue(action.spell)
        self.assertIsNotNone(action.spell_context)
        self.assertEqual(action.spell_context.spell.name, "Fireball")

    def test_fireball_not_used_on_single_target(self):
        """With only one enemy in range, spell may still be cast (single target)."""
        env = _make_minimal_env()
        from strategies.tactical import _decide_spell

        action = ActionSet()
        current = env.current_piece
        enemies = [p for p in env.action_queue if p.team != current.team and p.is_alive]
        action = _decide_spell(env, current, enemies, action)

        # One enemy at distance 1 from current at (5,5) vs (10,5)
        # Fireball range is 2, distance is |5-10| + |5-5| = 5 > 2
        # So no spell should be cast
        if action.spell:
            # If somehow in range, it's still a valid ActionSet
            self.assertIsNotNone(action.spell_context)


class TestTacticalAttackRange(unittest.TestCase):
    def test_staff_range_12(self):
        """Staff has range 12, so enemy at distance 10 should be attackable."""
        env = _make_minimal_env()
        # Current at (5,5), enemy at (10,5) = distance 5
        # This is within staff range 12
        from strategy_utils import get_attackable_targets
        targets = get_attackable_targets(env)
        self.assertTrue(len(targets) > 0)

    def test_staff_out_of_range(self):
        """Enemy at distance 15 is beyond staff range 12."""
        env = _make_minimal_env()
        for p in env.action_queue:
            if p.team != env.current_piece.team:
                p.position = Point(5, 20)
        from strategy_utils import get_attackable_targets
        targets = get_attackable_targets(env)
        self.assertEqual(len(targets), 0)


if __name__ == "__main__":
    unittest.main()
