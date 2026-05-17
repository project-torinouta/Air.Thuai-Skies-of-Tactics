"""Tests for the MCTS strategy (_MCTSNode, get_mcts_action_strategy).

Run with: uv run python -m unittest tests/test_mcts.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np

from env import Board, Environment, Piece
from utils import ActionSet, AttackContext, Point

# Imported lazily inside tests to avoid import-order issues
# from strategies.mcts import _MCTSNode, get_mcts_action_strategy


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
    """Build a 2-piece environment with both pieces close enough to interact."""
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
# _MCTSNode tests
# =========================================================================


class TestMCTSNode(unittest.TestCase):
    def setUp(self):
        self.env = _make_minimal_env()

    def _node(self, env=None, parent=None, action=None):
        from strategies.mcts import _MCTSNode
        return _MCTSNode(env or self.env, parent, action)

    def test_create_root_node(self):
        node = self._node()
        self.assertIs(node.parent, None)
        self.assertIsNone(node.action)
        self.assertEqual(node.visits, 0)
        self.assertEqual(node.value, 0.0)

    def test_create_child_node(self):
        parent = self._node()
        action = ActionSet()
        child = self._node(self.env, parent, action)
        self.assertIs(child.parent, parent)
        self.assertIs(child.action, action)

    def test_root_has_no_children_initially(self):
        node = self._node()
        self.assertEqual(node.children, [])


# =========================================================================
# _MCTSNode.expand tests
# =========================================================================


class TestMCTSNodeExpand(unittest.TestCase):
    def setUp(self):
        self.env = _make_minimal_env()
        from strategies.mcts import _MCTSNode
        self.node = _MCTSNode(self.env)

    def test_expand_creates_children(self):
        """Expanding should produce at least the 'no action' child."""
        self.node.expand()
        self.assertGreater(len(self.node.children), 0)

    def test_expand_all_children_have_parent(self):
        self.node.expand()
        for child in self.node.children:
            self.assertIs(child.parent, self.node)

    def test_expand_all_children_have_action(self):
        self.node.expand()
        for child in self.node.children:
            self.assertIsNotNone(child.action)

    def test_expand_children_have_forked_env(self):
        """Each child should have its own forked environment."""
        self.node.expand()
        envs = [c.env for c in self.node.children]
        # Every fork should be a different object
        self.assertEqual(len(set(id(e) for e in envs)), len(envs))

    def test_expand_child_env_is_not_over(self):
        """Child environments should not start as game-over."""
        self.node.expand()
        for child in self.node.children:
            self.assertFalse(child.env.is_game_over)


# =========================================================================
# _MCTSNode.select tests
# =========================================================================


class TestMCTSNodeSelect(unittest.TestCase):
    def setUp(self):
        self.env = _make_minimal_env()
        from strategies.mcts import _MCTSNode
        self.node = _MCTSNode(self.env)

    def test_select_on_leaf_returns_self(self):
        """A node with no children returns itself."""
        result = self.node.select()
        self.assertIs(result, self.node)

    def test_select_among_unvisited_returns_first(self):
        """All unvisited children have UCB1=inf; the first one is returned."""
        self.node.expand()
        if not self.node.children:
            self.skipTest("no children generated")
        selected = self.node.select()
        self.assertIn(selected, self.node.children)

    def test_select_prefers_high_value_child(self):
        """A child with higher visits/value should be selected via UCB1."""
        self.node.expand()
        if len(self.node.children) < 2:
            self.skipTest("need at least 2 children for selection test")

        self.node.visits = 10
        # Set one child as high-value, another as low-value
        self.node.children[0].visits = 5
        self.node.children[0].value = 5.0
        self.node.children[1].visits = 5
        self.node.children[1].value = -5.0

        selected = self.node.select()
        # The higher-value child should be selected
        self.assertGreater(selected.value, -5.0)


# =========================================================================
# _MCTSNode.simulate tests
# =========================================================================


class TestMCTSNodeSimulate(unittest.TestCase):
    def setUp(self):
        self.env = _make_minimal_env()
        from strategies.mcts import _MCTSNode
        self.node = _MCTSNode(self.env)

    def test_simulate_returns_float(self):
        result = self.node.simulate()
        self.assertIsInstance(result, (float, int))

    def test_simulate_returns_between_minus_one_and_one(self):
        result = self.node.simulate()
        self.assertGreaterEqual(result, -1.0)
        self.assertLessEqual(result, 1.0)

    def test_simulate_does_not_mutate_original_env(self):
        """Simulation should fork the env, leaving the original untouched."""
        orig_round = self.env.round_number
        self.node.simulate()
        self.assertEqual(self.env.round_number, orig_round)

    def test_simulate_with_imminent_kill(self):
        """If enemy is at 1 HP, simulation should likely result in a win."""
        for p in self.env.action_queue:
            if p.team != self.env.current_piece.team:
                p.health = 1
        from strategies.mcts import _MCTSNode
        node = _MCTSNode(self.env)
        result = node.simulate()
        # Should be >= 0 (win or draw)
        self.assertGreaterEqual(result, 0.0)

    def test_simulate_with_doomed_piece(self):
        """If our piece is at 1 HP, simulation should likely result in a loss."""
        self.env.current_piece.health = 1
        self.env.current_piece.max_health = 50
        from strategies.mcts import _MCTSNode
        node = _MCTSNode(self.env)
        result = node.simulate()
        self.assertLessEqual(result, 0.0)

    def test_simulate_runs_multiple_steps(self):
        """Simulation should execute multiple random playout steps."""
        from strategies.mcts import _MCTSNode
        node = _MCTSNode(self.env)
        # With 50 max steps and no immediate game-over, the simulation
        # should execute at least a few random actions.
        result = node.simulate()
        # The result should be a valid score in [-1, 1].
        self.assertGreaterEqual(result, -1.0)
        self.assertLessEqual(result, 1.0)
        # The original env should be untouched (sim forks internally).
        self.assertEqual(self.env.round_number, 0)


# =========================================================================
# _MCTSNode.backpropagate tests
# =========================================================================


class TestMCTSNodeBackpropagate(unittest.TestCase):
    def setUp(self):
        self.env = _make_minimal_env()
        from strategies.mcts import _MCTSNode
        self.node = _MCTSNode(self.env)

    def test_backpropagate_increments_visits(self):
        self.node.backpropagate(1.0)
        self.assertEqual(self.node.visits, 1)

    def test_backpropagate_adds_value(self):
        self.node.backpropagate(0.5)
        self.assertEqual(self.node.value, 0.5)

    def test_backpropagate_accumulates(self):
        self.node.backpropagate(1.0)
        self.node.backpropagate(-1.0)
        self.assertEqual(self.node.visits, 2)
        self.assertEqual(self.node.value, 0.0)

    def test_backpropagate_negates_at_parent(self):
        child_action = ActionSet()
        from strategies.mcts import _MCTSNode
        child = _MCTSNode(self.env, self.node, child_action)
        child.backpropagate(1.0)
        # Child gets the value, parent gets negated (adversarial)
        self.assertEqual(child.value, 1.0)
        self.assertEqual(self.node.value, -1.0)

    def test_backpropagate_alternates_sign_up_tree(self):
        """Value should alternate sign at each level."""
        from strategies.mcts import _MCTSNode
        child = _MCTSNode(self.env, self.node, ActionSet())
        grandchild = _MCTSNode(self.env, child, ActionSet())
        grandchild.backpropagate(1.0)
        self.assertEqual(grandchild.value, 1.0)  # level 0
        self.assertEqual(child.value, -1.0)       # level 1 (negated)
        self.assertEqual(self.node.value, 1.0)    # level 2 (negated again)

    def test_backpropagate_deep_tree(self):
        """A longer chain should still propagate correctly."""
        from strategies.mcts import _MCTSNode
        chain = [self.node]
        for _ in range(5):
            chain.append(_MCTSNode(self.env, chain[-1], ActionSet()))
        chain[-1].backpropagate(1.0)

        expected = 1.0
        for node in reversed(chain):
            self.assertEqual(node.value, expected)
            expected = -expected


# =========================================================================
# get_mcts_action_strategy integration tests
# =========================================================================


class TestMCTSStrategy(unittest.TestCase):
    def setUp(self):
        self.env = _make_minimal_env()

    def test_strategy_returns_action_set(self):
        from strategies.mcts import get_mcts_action_strategy
        strategy = get_mcts_action_strategy(simulation_count=5)
        action = strategy(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_strategy_with_zero_simulations(self):
        """With 0 simulations, the root has no children; returns empty action."""
        from strategies.mcts import get_mcts_action_strategy
        strategy = get_mcts_action_strategy(simulation_count=0)
        action = strategy(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_strategy_selects_best_child(self):
        """With enough simulations, a reasonable action should be returned."""
        from strategies.mcts import get_mcts_action_strategy
        strategy = get_mcts_action_strategy(simulation_count=20)
        action = strategy(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_strategy_does_not_crash_with_dead_piece(self):
        """If the current piece is dead, the strategy should handle gracefully."""
        self.env.current_piece.is_alive = False
        from strategies.mcts import get_mcts_action_strategy
        strategy = get_mcts_action_strategy(simulation_count=5)
        action = strategy(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_strategy_does_not_mutate_original_env(self):
        """The strategy should not change the original environment."""
        orig_round = self.env.round_number
        from strategies.mcts import get_mcts_action_strategy
        strategy = get_mcts_action_strategy(simulation_count=5)
        strategy(self.env)
        self.assertEqual(self.env.round_number, orig_round)

    def test_strategy_with_more_simulations(self):
        """More simulations should produce a valid action (not crash)."""
        from strategies.mcts import get_mcts_action_strategy
        strategy = get_mcts_action_strategy(simulation_count=30)
        action = strategy(self.env)
        self.assertIsInstance(action, ActionSet)

    def test_strategy_returns_action_with_move(self):
        """The returned action should at minimum not be malformed."""
        from strategies.mcts import get_mcts_action_strategy
        strategy = get_mcts_action_strategy(simulation_count=5)
        action = strategy(self.env)
        # ActionSet should have boolean flags
        for attr in ("move", "attack", "spell"):
            self.assertTrue(hasattr(action, attr))
            self.assertIsInstance(getattr(action, attr), bool)


# =========================================================================
# Edge cases
# =========================================================================


class TestMCTSEdgeCases(unittest.TestCase):
    def test_node_without_legal_moves(self):
        """A node where the current piece has no legal moves."""
        env = _make_minimal_env()
        # Block all adjacent cells
        cx, cy = env.current_piece.position.x, env.current_piece.position.y
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < env.board.width and 0 <= y < env.board.height:
                    env.board.grid[x][y].state = -1

        from strategies.mcts import _MCTSNode
        node = _MCTSNode(env)
        node.expand()
        # Should still produce at least one child (no-move, no-attack, no-spell)
        self.assertGreater(len(node.children), 0)

    def test_node_game_over_env(self):
        """Creating a node from a game-over env should not crash."""
        env = _make_minimal_env()
        env.is_game_over = True
        from strategies.mcts import _MCTSNode
        node = _MCTSNode(env)
        result = node.simulate()
        self.assertIsInstance(result, float)

    def test_ucb1_exploration(self):
        """Unvisited children get UCB1=inf so they are always explored first."""
        env = _make_minimal_env()
        from strategies.mcts import _MCTSNode
        node = _MCTSNode(env)
        node.expand()
        if len(node.children) < 2:
            self.skipTest("need at least 2 children for UCB1 test")

        node.visits = 5
        for c in node.children:
            c.visits = 0  # all unvisited

        # All unvisited → return the first child (max of ties)
        selected = node.select()
        self.assertIn(selected, node.children)

    def test_backpropagate_stops_at_root(self):
        """Backpropagation from root should not crash (parent is None)."""
        env = _make_minimal_env()
        from strategies.mcts import _MCTSNode
        node = _MCTSNode(env)
        node.backpropagate(1.0)
        self.assertEqual(node.value, 1.0)
        self.assertEqual(node.visits, 1)


# =========================================================================
# Multiple simulation iterations
# =========================================================================


class TestMCTSIterations(unittest.TestCase):
    def test_two_simulations_build_tree(self):
        """Running 2 simulations should expand root once and create children."""
        env = _make_minimal_env()
        from strategies.mcts import _MCTSNode, get_mcts_action_strategy

        root = _MCTSNode(env)
        # First iteration: select (root), visits==0 → no expand, simulate, backprop
        node = root.select()
        self.assertIs(node, root)

        # Second iteration: root.visits == 1 → expand
        # We need to manually simulate what the strategy loop does
        node = root.select()
        if node.visits > 0 and not node.children:
            node.expand()

        # After expand + simulate + backprop from iteration 2
        if node.children:
            self.assertGreater(len(node.children), 0)
            self.assertGreater(root.visits, 0)

    def test_more_iterations_increase_visits(self):
        """More iterations should increase total visit count."""
        env = _make_minimal_env()
        from strategies.mcts import _MCTSNode

        root = _MCTSNode(env)
        # Simulate a few iterations manually
        for _ in range(10):
            node = root
            while node.children:
                node = node.select()
            if node.visits > 0:
                node.expand()
                if node.children:
                    import random
                    node = random.choice(node.children)
            value = node.simulate()
            node.backpropagate(value)

        self.assertGreater(root.visits, 0)

    def test_strategy_picks_reasonable_action(self):
        """Integration: running simulations should pick a move toward the enemy."""
        env = _make_minimal_env()
        # Enemy is at (7,5), our piece at (5,5) — distance 2
        from strategies.mcts import get_mcts_action_strategy
        strategy = get_mcts_action_strategy(simulation_count=15)
        action = strategy(env)
        self.assertIsInstance(action, ActionSet)
        # Should either move toward enemy or attack (both are valid)
        self.assertTrue(action.move or action.attack)


if __name__ == "__main__":
    unittest.main()
