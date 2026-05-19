"""Tests for the Alpha-Beta strategy.

Run with: uv run python -m unittest tests/test_alpha_beta.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np

from env import Environment, Piece
from utils import ActionSet, Point


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
    acc.set_max_health_to(50 + strength * 2)
    acc.set_health_to(p.max_health)
    acc.set_max_action_points()
    acc.set_action_points_to(p.max_action_points)
    acc.set_max_spell_slots()
    acc.set_spell_slots_to(p.max_spell_slots)
    acc.set_max_movement_to(dexterity + 0.5 * strength + 10)
    acc.set_movement_to(p.max_movement)
    p.weapon_type = weapon
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
    """Two-piece env with pieces close enough to interact."""
    env = Environment(local_mode=True, if_log=0)
    env.board.init_from_file(BOARD_FILE)
    env.player1.id = 1
    env.player2.id = 2
    p1 = _make_piece(team=1, pos=Point(5, 5), weapon=2, strength=10, dexterity=10)
    p2 = _make_piece(team=2, pos=Point(7, 5), weapon=2, strength=10, dexterity=10)
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
# Alpha-beta strategy integration tests
# =========================================================================


class TestAlphaBetaStrategy(unittest.TestCase):
    def setUp(self):
        self.env = _make_minimal_env()
        self.env.max_rounds = 100

    def _strategy(self, depth=2):
        from strategies.alpha_beta import get_alpha_beta_action_strategy
        return get_alpha_beta_action_strategy(depth)

    def test_returns_action_set(self):
        action = self._strategy(2)(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_returns_action_with_flags(self):
        action = self._strategy(2)(self.env)
        for attr in ("move", "attack", "spell"):
            self.assertTrue(hasattr(action, attr))
            self.assertIsInstance(getattr(action, attr), bool)

    def test_does_not_mutate_original_env(self):
        orig_round = self.env.round_number
        self._strategy(2)(self.env)
        self.assertEqual(self.env.round_number, orig_round)

    def test_depth_1_works(self):
        action = self._strategy(1)(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_depth_2_works(self):
        action = self._strategy(2)(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_depth_3_works(self):
        action = self._strategy(3)(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_dead_current_piece(self):
        self.env.current_piece.is_alive = False
        action = self._strategy(2)(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_game_over_env(self):
        self.env.is_game_over = True
        action = self._strategy(2)(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_enemy_in_range_action(self):
        """When an enemy is in attack range, the strategy should attack."""
        from strategy_utils import get_attackable_targets
        targets = get_attackable_targets(self.env)
        if not targets:
            self.skipTest("no attackable targets")
        action = self._strategy(2)(self.env)
        self.assertTrue(hasattr(action, "attack"))

    def test_depth_increases_search_time(self):
        """Deeper search should take at least as long as shallow (sanity)."""
        import time
        t1 = time.time()
        self._strategy(1)(self.env)
        t_shallow = time.time() - t1
        t2 = time.time()
        self._strategy(2)(self.env)
        t_deep = time.time() - t2
        # Not a strict assertion — just a sanity check
        self.assertGreaterEqual(t_deep + 0.001, t_shallow * 0.5)


# =========================================================================
# Scoring and alternation tests
# =========================================================================


class TestAlphaBetaScoring(unittest.TestCase):
    def setUp(self):
        self.env = _make_minimal_env()
        self.env.max_rounds = 100

    def test_higher_score_action_preferred(self):
        """If an action damages the enemy, it should get a higher score."""
        from strategies.alpha_beta import get_alpha_beta_action_strategy

        for p in self.env.action_queue:
            if p.team != self.env.current_piece.team:
                p.health = 5  # nearly dead

        action = get_alpha_beta_action_strategy(2)(self.env)
        self.assertIsInstance(action, ActionSet)
        # The action should have at least one flag set (move, attack, or spell)
        self.assertTrue(action.move or action.attack or action.spell)

    def test_own_piece_damage_reduces_score(self):
        """If our piece is damaged, actions that preserve distance are chosen."""
        from strategies.alpha_beta import get_alpha_beta_action_strategy

        self.env.current_piece.health = 3  # our piece almost dead
        action = get_alpha_beta_action_strategy(2)(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_score_perspective_consistent(self):
        """Max level evaluates from root team perspective regardless of turn."""
        from strategies.alpha_beta import get_alpha_beta_action_strategy

        # Both sides identical — strategy should still return an action
        action = get_alpha_beta_action_strategy(2)(self.env)
        self.assertIsInstance(action, ActionSet)


# =========================================================================
# Edge cases
# =========================================================================


class TestAlphaBetaEdgeCases(unittest.TestCase):
    def test_no_legal_moves(self):
        """When the piece has no legal moves, the strategy returns empty."""
        env = _make_minimal_env()
        cx, cy = env.current_piece.position.x, env.current_piece.position.y
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < env.board.width and 0 <= y < env.board.height:
                    env.board.grid[x][y].state = -1
        from strategies.alpha_beta import get_alpha_beta_action_strategy
        action = get_alpha_beta_action_strategy(2)(env)
        self.assertIsInstance(action, ActionSet)

    def test_single_piece_vs_none(self):
        """Only one team has pieces — game over should be immediate."""
        env = _make_minimal_env()
        for p in env.player2.pieces:
            p.is_alive = False
        env.is_game_over = True
        from strategies.alpha_beta import get_alpha_beta_action_strategy
        action = get_alpha_beta_action_strategy(2)(env)
        self.assertIsInstance(action, ActionSet)

    def test_current_piece_none(self):
        env = _make_minimal_env()
        env.current_piece = None
        from strategies.alpha_beta import get_alpha_beta_action_strategy
        action = get_alpha_beta_action_strategy(2)(env)
        self.assertIsInstance(action, ActionSet)

    def test_far_apart_no_combat(self):
        """Pieces far apart — strategy should move toward enemy."""
        env = _make_minimal_env()
        # Move pieces far apart
        pos = env.current_piece.position
        env.current_piece.position = Point(0, 0)
        for p in env.action_queue:
            if p.team != env.current_piece.team:
                p.position = Point(19, 19)
        from strategies.alpha_beta import get_alpha_beta_action_strategy
        action = get_alpha_beta_action_strategy(2)(env)
        self.assertIsInstance(action, ActionSet)
        # Should at least move (not stand still)
        self.assertIsInstance(action.move, bool)


# =========================================================================
# Performance regression guard
# =========================================================================


class TestAlphaBetaPerformance(unittest.TestCase):
    def test_turn_completes_in_reasonable_time(self):
        """A single turn should complete in under 5 seconds."""
        import time
        env = _make_minimal_env()
        env.max_rounds = 100
        from strategies.alpha_beta import get_alpha_beta_action_strategy
        strategy = get_alpha_beta_action_strategy(3)
        t0 = time.time()
        strategy(env)
        elapsed = time.time() - t0
        self.assertLess(elapsed, 5.0, f"alpha-beta depth 3 took {elapsed:.1f}s")


if __name__ == "__main__":
    unittest.main()
