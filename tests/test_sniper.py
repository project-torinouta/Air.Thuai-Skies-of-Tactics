"""Tests for the sniper strategy.

Run with: uv run python -m unittest tests/test_sniper.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np

from env import Environment, InitGameMessage, Piece
from strategies.sniper import (
    get_sniper_action_strategy,
    get_sniper_init_strategy,
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


def _make_sniper_env() -> Environment:
    """Two-piece env with pieces close enough for bow range (9)."""
    env = Environment(local_mode=True, if_log=0)
    env.board.init_from_file(BOARD_FILE)
    env.player1.id = 1
    env.player2.id = 2

    p1 = _make_piece(
        team=1, pos=Point(5, 5), strength=28, dexterity=2,
        intelligence=0, weapon=3, armor=3,
    )
    p2 = _make_piece(
        team=2, pos=Point(10, 5), strength=28, dexterity=2,
        intelligence=0, weapon=3, armor=3,
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


def _make_far_env() -> Environment:
    """Two-piece env where the enemy is outside bow range (9)."""
    env = Environment(local_mode=True, if_log=0)
    env.board.init_from_file(BOARD_FILE)
    env.player1.id = 1
    env.player2.id = 2

    p1 = _make_piece(
        team=1, pos=Point(0, 0), strength=28, dexterity=2,
        intelligence=0, weapon=3, armor=3,
    )
    p2 = _make_piece(
        team=2, pos=Point(19, 19), strength=28, dexterity=2,
        intelligence=0, weapon=3, armor=3,
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


def _make_multi_env() -> Environment:
    """Three-piece env with varying enemy health (for focus-fire testing)."""
    env = Environment(local_mode=True, if_log=0)
    env.board.init_from_file(BOARD_FILE)
    env.player1.id = 1
    env.player2.id = 2

    p1 = _make_piece(
        team=1, pos=Point(5, 5), strength=28, dexterity=2,
        intelligence=0, weapon=3, armor=3,
    )
    e1 = _make_piece(
        team=2, pos=Point(8, 5), strength=28, dexterity=2,
        intelligence=0, weapon=3, armor=3,
    )
    e2 = _make_piece(
        team=2, pos=Point(9, 6), strength=28, dexterity=2,
        intelligence=0, weapon=3, armor=3,
    )
    p1.id = 0
    e1.id = 1
    e2.id = 2
    e1.health = 30   # lowest HP → should be primary target
    e1.max_health = 106
    e2.health = 80
    e2.max_health = 106
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


class TestSniperInit(unittest.TestCase):
    def test_returns_list_of_piece_args(self):
        strategy = get_sniper_init_strategy()
        msg = InitGameMessage()
        msg.piece_cnt = 3
        msg.id = 1
        msg.board = _make_sniper_env().board
        result = strategy(msg)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        for arg in result:
            self.assertIsInstance(arg, PieceArg)

    def test_stats_match_config(self):
        strategy = get_sniper_init_strategy()
        msg = InitGameMessage()
        msg.piece_cnt = 1
        msg.id = 1
        msg.board = _make_sniper_env().board
        result = strategy(msg)
        arg = result[0]
        self.assertEqual(arg.strength, 30)
        self.assertEqual(arg.dexterity, 0)
        self.assertEqual(arg.intelligence, 0)
        self.assertEqual(arg.equip.x, 3)
        self.assertEqual(arg.equip.y, 3)

    def test_player2_positioning(self):
        strategy = get_sniper_init_strategy()
        msg = InitGameMessage()
        msg.piece_cnt = 3
        msg.id = 2
        msg.board = _make_sniper_env().board
        result = strategy(msg)
        self.assertEqual(len(result), 3)
        for arg in result:
            self.assertTrue(arg.pos.y > msg.board.boarder)


# =========================================================================
# Action strategy tests
# =========================================================================


class TestSniperAction(unittest.TestCase):
    def setUp(self):
        self.env = _make_sniper_env()
        self.env.max_rounds = 100

    def _strategy(self):
        return get_sniper_action_strategy()

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

    def test_attacks_enemy_in_bow_range(self):
        """Bow range is 9; enemies at distance 5 should be attacked."""
        action = self._strategy()(self.env)
        self.assertTrue(action.attack, "Should attack when enemy in bow range")

    def test_does_not_move_when_in_range(self):
        """When already in bow range, the sniper should not move."""
        action = self._strategy()(self.env)
        self.assertFalse(action.move, "Should not waste AP on movement when in range")

    def test_moves_toward_enemy_when_out_of_range(self):
        """When no enemy is in bow range, the sniper should advance."""
        env = _make_far_env()
        env.max_rounds = 100
        action = self._strategy()(env)
        self.assertTrue(action.move, "Should advance when enemy out of bow range")
        self.assertFalse(action.attack, "Should not attack when enemy out of range")

    def test_dead_current_piece(self):
        self.env.current_piece.is_alive = False
        action = self._strategy()(self.env)
        self.assertIsInstance(action, ActionSet)
        self.assertFalse(action.attack)
        self.assertFalse(action.move)

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
        self.assertFalse(action.attack)
        self.assertFalse(action.move)

    def test_no_legal_moves_out_of_range(self):
        """When out of range but no legal moves, should not crash."""
        env = _make_far_env()
        env.max_rounds = 100
        cx, cy = env.current_piece.position.x, env.current_piece.position.y
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < env.board.width and 0 <= y < env.board.height:
                    env.board.grid[x][y].state = -1
        action = self._strategy()(env)
        self.assertIsInstance(action, ActionSet)

    def test_empty_action_points(self):
        self.env.current_piece.action_points = 0
        action = self._strategy()(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_spell_always_false(self):
        """Sniper never uses spells (INT=0, no spell slots)."""
        action = self._strategy()(self.env)
        self.assertFalse(action.spell)

    def test_focus_fires_lowest_health_enemy(self):
        """Should target the enemy with the lowest health."""
        env = _make_multi_env()
        env.max_rounds = 100
        action = self._strategy()(env)
        self.assertTrue(action.attack)
        self.assertIsNotNone(action.attack_context)
        self.assertIsNotNone(action.attack_context.target)
        # e1 has health=30, e2 has health=80 → should target e1 (id=1)
        self.assertEqual(
            action.attack_context.target.id, 1,
            "Should focus-fire the lowest-health enemy",
        )

    def test_does_not_switch_target_to_closer_enemy(self):
        """Should not switch to a closer enemy if a lower-HP one is in range."""
        env = _make_multi_env()
        env.max_rounds = 100
        # Move e2 (HP=80) closer than e1 (HP=30)
        for p in env.action_queue:
            if p.id == 2:
                p.position = Point(6, 5)  # closer than e1 at (8,5)
        action = self._strategy()(env)
        self.assertTrue(action.attack)
        # Should still target e1 (HP=30) despite e2 being closer
        self.assertEqual(
            action.attack_context.target.id, 1,
            "Should prioritise lowest health over closest distance",
        )


# =========================================================================
# Bow range tests
# =========================================================================


class TestSniperRange(unittest.TestCase):
    def test_bow_range_9(self):
        """Bow attack_range should be 9."""
        env = _make_sniper_env()
        self.assertEqual(env.current_piece.attack_range, 9)

    def test_attacks_at_max_range(self):
        """Enemy at exactly distance 9 should be attackable."""
        env = _make_sniper_env()
        # Place enemy at exactly distance 9 from (5,5): (14, 5)
        for p in env.action_queue:
            if p.team != env.current_piece.team:
                p.position = Point(14, 5)
        action = get_sniper_action_strategy()(env)
        self.assertTrue(action.attack)

    def test_out_of_bow_range(self):
        """Enemy at distance 10 should NOT be attackable."""
        env = _make_sniper_env()
        for p in env.action_queue:
            if p.team != env.current_piece.team:
                p.position = Point(5, 20)
        from strategy_utils import get_attackable_targets
        targets = get_attackable_targets(env)
        self.assertEqual(len(targets), 0)


# =========================================================================
# Edge cases
# =========================================================================


class TestSniperEdgeCases(unittest.TestCase):
    def test_current_piece_none(self):
        env = _make_sniper_env()
        env.current_piece = None
        action = get_sniper_action_strategy()(env)
        self.assertIsInstance(action, ActionSet)
        self.assertFalse(action.attack)
        self.assertFalse(action.move)

    def test_game_over_flag(self):
        env = _make_sniper_env()
        env.is_game_over = True
        action = get_sniper_action_strategy()(env)
        self.assertIsInstance(action, ActionSet)

    def test_no_legal_moves_while_in_range(self):
        """In range but no legal moves — should still attack."""
        env = _make_sniper_env()
        cx, cy = env.current_piece.position.x, env.current_piece.position.y
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < env.board.width and 0 <= y < env.board.height:
                    env.board.grid[x][y].state = -1
        action = get_sniper_action_strategy()(env)
        self.assertIsInstance(action, ActionSet)
        # Should still attack since the enemy is in bow range
        self.assertTrue(action.attack)

    def test_strategy_uses_sniper_stats(self):
        """Verify the strategy init produces correct game stats."""
        strategy = get_sniper_init_strategy()
        msg = InitGameMessage()
        msg.piece_cnt = 1
        msg.id = 1
        msg.board = _make_sniper_env().board
        result = strategy(msg)
        arg = result[0]
        self.assertEqual(arg.strength, 30)
        self.assertEqual(arg.dexterity, 0)
        self.assertEqual(arg.intelligence, 0)


if __name__ == "__main__":
    unittest.main()
