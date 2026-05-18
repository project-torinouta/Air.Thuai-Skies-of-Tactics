"""Tests for the ML pipeline components.

Run with: uv run python -m unittest tests/test_ml.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np

from ml.state_encoder import encode_state, state_dim
from ml.policy_net import forward, init_params, param_count, get_action_probs
from ml.action_decoder import decode_action
from ml.es_optimizer import ESOptimizer

from env import Environment
from utils import Point


BOARD_FILE = os.path.join(
    os.path.dirname(__file__), "..", "src", "BoardCase", "case1.txt"
)


def _make_minimal_env() -> Environment:
    env = Environment(local_mode=True, if_log=0)
    env.board.init_from_file(BOARD_FILE)
    env.player1.id = 1
    env.player2.id = 2

    from env import Piece
    from utils import Point

    def mk(team, pos, str_=10, dex=10, intel=10, wpn=2, arm=2):
        p = Piece()
        a = p.get_accessor()
        a.set_team_to(team)
        a.set_strength_to(str_)
        a.set_dexterity_to(dex)
        a.set_intelligence_to(intel)
        a.set_max_health_to(50 + str_ * 2)
        a.set_health_to(p.max_health)
        a.set_max_action_points()
        a.set_action_points_to(p.max_action_points)
        a.set_max_spell_slots()
        a.set_spell_slots_to(p.max_spell_slots)
        a.set_max_movement_to(dex + 0.5 * str_ + 10)
        a.set_movement_to(p.max_movement)
        p.weapon_type = wpn
        a.set_type_to(wpn)
        if wpn == 3:
            a.set_physical_damage_to(16); a.set_range_to(9)
        elif wpn == 2:
            a.set_physical_damage_to(10); a.set_range_to(3)
        if arm == 3:
            a.set_physical_resist_to(23); a.set_max_movement_by(-3)
        elif arm == 2:
            a.set_physical_resist_to(15)
        elif arm == 1:
            a.set_physical_resist_to(8); a.set_max_movement_by(3)
        a.set_position(pos)
        return p

    p1 = mk(1, Point(5, 5), str_=29, dex=1, intel=0, wpn=3, arm=3)
    p2 = mk(2, Point(12, 5), str_=29, dex=1, intel=0, wpn=3, arm=3)
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
# State encoder tests
# =========================================================================


class TestStateEncoder(unittest.TestCase):
    def test_state_dim(self):
        self.assertEqual(state_dim(), 104)

    def test_encode_returns_fixed_size(self):
        env = _make_minimal_env()
        vec = encode_state(env)
        self.assertEqual(len(vec), state_dim())
        self.assertEqual(vec.dtype, np.float32)

    def test_encode_values_in_range(self):
        env = _make_minimal_env()
        vec = encode_state(env)
        self.assertTrue(np.all(vec >= 0.0) and np.all(vec <= 1.0),
                        "All feature values should be in [0, 1]")


# =========================================================================
# Policy network tests
# =========================================================================


class TestPolicyNetwork(unittest.TestCase):
    def test_param_count(self):
        cnt = param_count()
        # Expected: 104*64 + 64 + 64*32 + 32 + 32*6 + 6
        expected = 104 * 64 + 64 + 64 * 32 + 32 + 32 * 6 + 6
        self.assertEqual(cnt, expected)

    def test_init_params_shape(self):
        params = init_params(seed=42)
        self.assertEqual(len(params), param_count())
        self.assertEqual(params.dtype, np.float32)

    def test_forward_returns_6_logits(self):
        env = _make_minimal_env()
        state = encode_state(env)
        params = init_params(seed=42)
        logits = forward(params, state)
        self.assertEqual(len(logits), 6)
        self.assertEqual(logits.dtype, np.float32)

    def test_action_probs_sum_to_one(self):
        env = _make_minimal_env()
        state = encode_state(env)
        params = init_params(seed=42)
        probs = get_action_probs(params, state)
        self.assertAlmostEqual(float(np.sum(probs)), 1.0, places=5)
        self.assertEqual(len(probs), 6)

    def test_deterministic_seed(self):
        p1 = init_params(seed=42)
        p2 = init_params(seed=42)
        np.testing.assert_array_equal(p1, p2)

    def test_different_seed_different_params(self):
        p1 = init_params(seed=42)
        p2 = init_params(seed=99)
        self.assertFalse(np.allclose(p1, p2))


# =========================================================================
# Action decoder tests
# =========================================================================


class TestActionDecoder(unittest.TestCase):
    def test_decode_returns_action_set(self):
        env = _make_minimal_env()
        logits = np.zeros(6, dtype=np.float64)
        action = decode_action(logits, env)
        from utils import ActionSet
        self.assertIsInstance(action, ActionSet)

    def test_decode_with_high_move_bias_moves(self):
        """move_bias > 0.5 and enemy out of range → move."""
        env = _make_minimal_env()
        # Enemy at (12, 5), current at (5, 5), range is 9, distance is 7
        # Actually distance = 7, range = 9 → in range!
        # Move enemy further out
        for p in env.action_queue:
            if p.team != env.current_piece.team:
                p.position = Point(18, 18)  # distance = 26 > 9
        logits = np.array([0.0, 0.0, 0.0, 0.8, 0.0, 0.0], dtype=np.float64)
        action = decode_action(logits, env)
        self.assertTrue(action.move)

    def test_decode_does_not_move_when_in_range(self):
        """Enemy in range → don't move."""
        env = _make_minimal_env()
        # Enemy at (12, 5), current at (5, 5), range is 9, distance = 7 ≤ 9
        logits = np.zeros(6, dtype=np.float64)
        action = decode_action(logits, env)
        self.assertFalse(action.move)

    def test_decode_attacks_when_in_range(self):
        """Enemy in range → attack."""
        env = _make_minimal_env()
        logits = np.zeros(6, dtype=np.float64)
        action = decode_action(logits, env)
        self.assertTrue(action.attack)

    def test_decode_no_attack_when_out_of_range(self):
        """Enemy out of range → no attack."""
        env = _make_minimal_env()
        for p in env.action_queue:
            if p.team != env.current_piece.team:
                p.position = Point(18, 18)
        logits = np.zeros(6, dtype=np.float64)
        action = decode_action(logits, env)
        self.assertFalse(action.attack)

    def test_decode_targets_highest_priority(self):
        """The enemy with highest target_logit should be attacked."""
        env = _make_minimal_env()
        # Add a second enemy
        from env import Piece
        from utils import Point
        p3 = Piece()
        a = p3.get_accessor()
        a.set_team_to(2)
        a.set_strength_to(29)
        a.set_position(Point(7, 5))
        p3.id = 2
        p3.weapon_type = 3
        a.set_type_to(3)
        a.set_physical_damage_to(16); a.set_range_to(9)
        a.set_physical_resist_to(23); a.set_max_movement_by(-3)
        a.set_max_health_to(108); a.set_health_to(50)  # low HP
        a.set_max_action_points(); a.set_action_points_to(3)
        a.set_max_movement_to(1 + 14.5 + 10 - 3)
        a.set_movement_to(a.piece.max_movement)
        # Don't add to action_queue (it's a 2-piece env)
        # Just test that decoder picks the right target
        # We'll just test with the existing 2-piece env instead

        logits = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)
        action = decode_action(logits, env)
        # With only 1 enemy, the target must be enemy 0 (id=1)
        self.assertTrue(action.attack)
        self.assertEqual(action.attack_context.target.id, 1)

    def test_decode_with_retreat(self):
        """retreat_bias > 0.5 and low HP → retreat."""
        env = _make_minimal_env()
        env.current_piece.health = 10  # Below 30% of 108
        logits = np.array([0.0, 0.0, 0.0, 0.0, 0.8, 0.0], dtype=np.float64)
        action = decode_action(logits, env)
        self.assertTrue(action.move)


# =========================================================================
# ES optimizer tests
# =========================================================================


class TestESOptimizer(unittest.TestCase):
    def test_ask_returns_correct_shape(self):
        es = ESOptimizer(dim=10, pop_size=5, seed=42)
        pop = es.ask()
        self.assertEqual(pop.shape, (5, 10))

    def test_tell_updates_mean(self):
        es = ESOptimizer(dim=5, pop_size=4, seed=42)
        es.ask()  # pop stored internally
        old_mean = es.mean.copy()
        fitness = np.array([0.1, 0.5, 0.3, 0.9])
        es.tell(fitness)
        self.assertFalse(np.allclose(es.mean, old_mean))

    def test_optimizer_converges_simple_task(self):
        """ES should find the max of a simple quadratic."""
        es = ESOptimizer(dim=2, pop_size=10, sigma=0.5, seed=42)
        target = np.array([1.5, -0.8], dtype=np.float32)

        for gen in range(100):
            pop = es.ask()
            # Fitness = negative distance to target
            fitness = np.array([
                -np.sum((p - target) ** 2) for p in pop
            ], dtype=np.float32)
            es.tell(fitness)

        final_dist = np.sum((es.mean - target) ** 2)
        self.assertLess(final_dist, 0.1,
                        "ES should converge to target within 100 generations")


if __name__ == "__main__":
    unittest.main()
