"""Tests for strategy utilities (get_state_score, get_legal_moves,
get_attackable_targets, simulate_move, simulate_attack, fork_environment).

Run with: uv run python -m unittest tests/test_strategy_utils.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np

from env import Board, Environment, Piece, Player
from utils import ActionSet, AttackContext, Point, SpellFactory


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


def _make_simple_action(
    move: bool = False,
    move_target: Point = Point(0, 0),
    attack: bool = False,
    attacker=None,
    target=None,
) -> ActionSet:
    a = ActionSet()
    a.move = move
    a.move_target = move_target
    a.attack = attack
    if attack:
        ctx = AttackContext()
        ctx.attacker = attacker
        ctx.target = target
        a.attack_context = ctx
    a.spell = False
    return a


class _EnvHelper:
    """Helper to build a minimal Environment with two opposing pieces."""

    def __init__(self) -> None:
        self.env = Environment(local_mode=True, if_log=0)
        self.env.board.init_from_file(BOARD_FILE)
        self.env.player1.id = 1
        self.env.player2.id = 2
        p1 = _make_piece(team=1, pos=Point(1, 1))
        p2 = _make_piece(team=2, pos=Point(18, 18))
        p1.id = 0
        p2.id = 1
        self.env.action_queue = np.array([p1, p2], dtype=object)
        self.env.current_piece = p1
        self.env.player1.pieces = np.array([p1], dtype=object)
        self.env.player2.pieces = np.array([p2], dtype=object)
        for p in [p1, p2]:
            self.env.board.grid[p.position.x][p.position.y].state = 2
            self.env.board.grid[p.position.x][p.position.y].player_id = p.team
            self.env.board.grid[p.position.x][p.position.y].piece_id = p.id
        self.p1 = p1
        self.p2 = p2

    def set_current(self, piece: Piece) -> None:
        self.env.current_piece = piece


# =========================================================================
# get_state_score tests
# =========================================================================


class TestGetStateScore(unittest.TestCase):
    def setUp(self):
        self.h = _EnvHelper()

    def _score(self):
        from strategy_utils import get_state_score
        return get_state_score(self.h.env)

    def test_score_is_zero_for_equal_teams(self):
        """Equal teams should produce a score near 0."""
        s = self._score()
        self.assertAlmostEqual(s, 0.0, delta=5.0)  # close to zero

    def test_score_positive_for_own_team_advantage(self):
        """Damaging the enemy should make the score positive."""
        self.h.p2.health = 10  # heavily damaged
        s = self._score()
        self.assertGreater(s, 0.0)

    def test_score_negative_for_enemy_advantage(self):
        """If our piece is damaged, the score should be negative."""
        self.h.p1.health = 10  # our piece damaged
        s = self._score()
        self.assertLess(s, 0.0)

    def test_score_depends_on_team_perspective(self):
        """The score flips sign when the current piece changes team."""
        from strategy_utils import get_state_score
        self.h.p1.health = 10  # our piece damaged
        s1 = get_state_score(self.h.env)  # team 1 perspective
        self.h.set_current(self.h.p2)
        s2 = get_state_score(self.h.env)  # team 2 perspective
        self.assertAlmostEqual(s1, -s2, delta=0.01)

    def test_score_includes_height(self):
        """Height advantage contributes to the score."""
        self.h.p1.height = 5
        self.h.p2.height = 0
        s = self._score()
        self.assertGreater(s, 0.0)

    def test_score_includes_action_points(self):
        """More AP should increase the score from that team's perspective."""
        from strategy_utils import get_state_score
        self.h.p1.action_points = 5
        s1 = get_state_score(self.h.env)  # team 1 perspective
        self.h.p1.action_points = 0
        s2 = get_state_score(self.h.env)
        self.assertGreater(s1, s2)

    def test_score_ignores_dead_pieces(self):
        """Dead pieces should not contribute to the score."""
        self.h.p2.is_alive = False
        s = self._score()
        self.assertGreater(s, 0.0)  # we have all alive, enemy has none

    def test_score_zero_when_no_current_piece(self):
        """If current_piece is None, score should be 0."""
        from strategy_utils import get_state_score
        self.h.env.current_piece = None
        self.assertEqual(get_state_score(self.h.env), 0.0)

    def test_score_symmetric_when_identical(self):
        """Identical teams should yield score always 0 regardless of current."""
        from strategy_utils import get_state_score
        # Both pieces are identical (same stats, full HP)
        s1 = get_state_score(self.h.env)
        self.h.set_current(self.h.p2)
        s2 = get_state_score(self.h.env)
        self.assertAlmostEqual(s1, 0.0, delta=0.01)
        self.assertAlmostEqual(s2, 0.0, delta=0.01)

    def test_score_includes_spell_slots(self):
        """More spell slots should affect the score."""
        from strategy_utils import get_state_score
        self.h.p1.spell_slots = 0
        s_low = get_state_score(self.h.env)
        self.h.p1.spell_slots = 5
        s_high = get_state_score(self.h.env)
        self.assertGreater(s_high, s_low)


# =========================================================================
# get_legal_moves tests
# =========================================================================


class TestGetLegalMoves(unittest.TestCase):
    def setUp(self):
        self.h = _EnvHelper()

    def test_returns_reachable_positions(self):
        from strategy_utils import get_legal_moves
        moves = get_legal_moves(self.h.env)
        self.assertGreater(len(moves), 0)
        self.assertIn(Point(1, 1), moves)  # current position always reachable

    def test_excludes_blocked_cells(self):
        from strategy_utils import get_legal_moves
        # grid[3][4] is blocked in case1.txt
        moves = get_legal_moves(self.h.env)
        self.assertNotIn(Point(3, 4), moves)

    def test_specific_piece(self):
        from strategy_utils import get_legal_moves
        # Place a piece elsewhere with limited movement
        piece = _make_piece(team=2, pos=Point(10, 10), dexterity=1, strength=1)
        moves = get_legal_moves(self.h.env, piece)
        self.assertGreater(len(moves), 0)
        self.assertIn(Point(10, 10), moves)

    def test_dead_piece_returns_empty(self):
        from strategy_utils import get_legal_moves
        piece = _make_piece(team=2, pos=Point(10, 10))
        piece.is_alive = False
        moves = get_legal_moves(self.h.env, piece)
        self.assertEqual(moves, [])

    def test_none_piece_falls_back_to_current(self):
        from strategy_utils import get_legal_moves
        moves_with_current = get_legal_moves(self.h.env)
        moves_with_none = get_legal_moves(self.h.env, None)
        self.assertEqual(moves_with_current, moves_with_none)

    def test_no_current_piece_returns_empty(self):
        from strategy_utils import get_legal_moves
        self.h.env.current_piece = None
        moves = get_legal_moves(self.h.env)
        self.assertEqual(moves, [])


# =========================================================================
# get_attackable_targets tests
# =========================================================================


class TestGetAttackableTargets(unittest.TestCase):
    def setUp(self):
        self.h = _EnvHelper()

    def test_returns_enemy_in_range(self):
        from strategy_utils import get_attackable_targets
        # Place p1 with long range, p2 close
        self.h.p1 = _make_piece(team=1, pos=Point(5, 5), weapon=3)  # bow, range 9
        self.h.p2 = _make_piece(team=2, pos=Point(5, 8))  # distance 3
        self.h.env.action_queue = np.array([self.h.p1, self.h.p2], dtype=object)
        self.h.set_current(self.h.p1)
        for p in [self.h.p1, self.h.p2]:
            self.h.env.board.grid[p.position.x][p.position.y].state = 2
            self.h.env.board.grid[p.position.x][p.position.y].player_id = p.team
            self.h.env.board.grid[p.position.x][p.position.y].piece_id = p.id
        targets = get_attackable_targets(self.h.env)
        self.assertIn(self.h.p2, targets)

    def test_no_enemies_in_range(self):
        from strategy_utils import get_attackable_targets
        # Place enemies far apart
        self.h.p1 = _make_piece(team=1, pos=Point(1, 1), weapon=2)  # range 3
        self.h.p2 = _make_piece(team=2, pos=Point(19, 19))  # very far
        self.h.env.action_queue = np.array([self.h.p1, self.h.p2], dtype=object)
        self.h.set_current(self.h.p1)
        for p in [self.h.p1, self.h.p2]:
            self.h.env.board.grid[p.position.x][p.position.y].state = 2
            self.h.env.board.grid[p.position.x][p.position.y].player_id = p.team
            self.h.env.board.grid[p.position.x][p.position.y].piece_id = p.id
        targets = get_attackable_targets(self.h.env)
        self.assertEqual(targets, [])

    def test_dead_piece_not_targetable(self):
        from strategy_utils import get_attackable_targets
        self.h.p1 = _make_piece(team=1, pos=Point(5, 5), weapon=3)
        self.h.p2 = _make_piece(team=2, pos=Point(5, 8))
        self.h.p2.is_alive = False
        self.h.env.action_queue = np.array([self.h.p1, self.h.p2], dtype=object)
        self.h.set_current(self.h.p1)
        for p in [self.h.p1, self.h.p2]:
            self.h.env.board.grid[p.position.x][p.position.y].state = 2
            self.h.env.board.grid[p.position.x][p.position.y].player_id = p.team
            self.h.env.board.grid[p.position.x][p.position.y].piece_id = p.id
        targets = get_attackable_targets(self.h.env)
        self.assertNotIn(self.h.p2, targets)

    def test_cannot_target_own_team(self):
        from strategy_utils import get_attackable_targets
        self.h.p1 = _make_piece(team=1, pos=Point(5, 5), weapon=3)
        ally = _make_piece(team=1, pos=Point(5, 6))
        ally.id = 2
        self.h.env.action_queue = np.array([self.h.p1, ally], dtype=object)
        self.h.set_current(self.h.p1)
        for p in [self.h.p1, ally]:
            self.h.env.board.grid[p.position.x][p.position.y].state = 2
            self.h.env.board.grid[p.position.x][p.position.y].player_id = p.team
            self.h.env.board.grid[p.position.x][p.position.y].piece_id = p.id
        targets = get_attackable_targets(self.h.env)
        self.assertNotIn(ally, targets)

    def test_specific_piece(self):
        from strategy_utils import get_attackable_targets
        self.h.p1 = _make_piece(team=1, pos=Point(5, 5), weapon=3)
        self.h.p2 = _make_piece(team=2, pos=Point(5, 8))
        self.h.env.action_queue = np.array([self.h.p1, self.h.p2], dtype=object)
        self.h.set_current(self.h.p1)
        for p in [self.h.p1, self.h.p2]:
            self.h.env.board.grid[p.position.x][p.position.y].state = 2
            self.h.env.board.grid[p.position.x][p.position.y].player_id = p.team
            self.h.env.board.grid[p.position.x][p.position.y].piece_id = p.id
        # Query from p2's perspective
        targets = get_attackable_targets(self.h.env, self.h.p2)
        self.assertIn(self.h.p1, targets)

    def test_dead_attacker_returns_empty(self):
        from strategy_utils import get_attackable_targets
        self.h.p1.is_alive = False
        targets = get_attackable_targets(self.h.env, self.h.p1)
        self.assertEqual(targets, [])

    def test_none_piece_falls_back_to_current(self):
        from strategy_utils import get_attackable_targets
        # Place current piece far from any enemy
        self.h.p1.position = Point(1, 1)
        self.h.p2.position = Point(19, 19)
        t1 = get_attackable_targets(self.h.env)
        t2 = get_attackable_targets(self.h.env, None)
        self.assertEqual(t1, t2)


# =========================================================================
# simulate_move tests
# =========================================================================


class TestSimulateMove(unittest.TestCase):
    def setUp(self):
        self.h = _EnvHelper()

    def test_reachable_move(self):
        from strategy_utils import simulate_move
        result = simulate_move(self.h.env, self.h.p1, Point(2, 1))
        self.assertTrue(result)

    def test_unreachable_move(self):
        from strategy_utils import simulate_move
        result = simulate_move(self.h.env, self.h.p1, Point(19, 19))
        self.assertFalse(result)

    def test_blocked_target(self):
        from strategy_utils import simulate_move
        # grid[3][4] is blocked
        result = simulate_move(self.h.env, self.h.p1, Point(3, 4))
        self.assertFalse(result)

    def test_dead_piece(self):
        from strategy_utils import simulate_move
        self.h.p1.is_alive = False
        result = simulate_move(self.h.env, self.h.p1, Point(2, 1))
        self.assertFalse(result)

    def test_move_to_current_position(self):
        """Staying in place should always be valid."""
        from strategy_utils import simulate_move
        result = simulate_move(self.h.env, self.h.p1, self.h.p1.position)
        self.assertTrue(result)


# =========================================================================
# simulate_attack tests
# =========================================================================


class TestSimulateAttack(unittest.TestCase):
    def setUp(self):
        self.h = _EnvHelper()

    def _attack_damage(self, attacker: Piece, target: Piece) -> float:
        from strategy_utils import simulate_attack
        return simulate_attack(self.h.env, attacker, target)

    def test_shortsword_damage(self):
        """shortsword: phys_damage=10, str=10, target phys_resist=15"""
        attacker = _make_piece(weapon=2, strength=10)  # phys_damage=10
        target = _make_piece(armor=2)  # phys_resist=15
        dmg = self._attack_damage(attacker, target)
        expected = max(0, 10 + 10 - 15)  # = 5
        self.assertEqual(dmg, float(expected))

    def test_bow_damage(self):
        """bow: phys_damage=16, str=10, target phys_resist=15"""
        attacker = _make_piece(weapon=3, strength=10)
        target = _make_piece(armor=2)
        dmg = self._attack_damage(attacker, target)
        expected = max(0, 16 + 10 - 15)  # = 11
        self.assertEqual(dmg, float(expected))

    def test_staff_true_damage(self):
        """staff deals fixed 4 true damage regardless of target."""
        attacker = _make_piece(weapon=4)  # staff
        target = _make_piece(armor=3)  # heavy armour, phys_resist=23
        dmg = self._attack_damage(attacker, target)
        self.assertEqual(dmg, 4.0)

    def test_damage_negated_by_high_resist(self):
        """If resistance exceeds damage, result is 0."""
        attacker = _make_piece(weapon=1, strength=1)  # phys_damage=8 + 1 = 9
        target = _make_piece(armor=3)  # phys_resist=23
        dmg = self._attack_damage(attacker, target)
        self.assertEqual(dmg, 0.0)

    def test_dead_attacker(self):
        attacker = _make_piece()
        attacker.is_alive = False
        target = _make_piece()
        dmg = self._attack_damage(attacker, target)
        self.assertEqual(dmg, 0.0)

    def test_dead_target(self):
        attacker = _make_piece(weapon=2, strength=10)
        target = _make_piece()
        target.is_alive = False
        dmg = self._attack_damage(attacker, target)
        self.assertEqual(dmg, 0.0)


# =========================================================================
# fork_environment tests
# =========================================================================


class TestForkEnvironment(unittest.TestCase):
    def setUp(self):
        self.h = _EnvHelper()
        self.h.env.max_rounds = 50
        self.h.env.round_number = 5
        self.h.env.is_game_over = False

    def _fork(self):
        from strategy_utils import fork_environment
        return fork_environment(self.h.env)

    def test_fork_is_independent_copy(self):
        """Mutation on the fork should not affect the original."""
        fork = self._fork()
        # Mutate the fork
        fork.current_piece.health = 1
        # Original should be unchanged
        self.assertNotEqual(
            self.h.env.current_piece.health,
            fork.current_piece.health,
        )

    def test_fork_preserves_round_number(self):
        fork = self._fork()
        self.assertEqual(fork.round_number, self.h.env.round_number)

    def test_fork_preserves_action_queue_length(self):
        fork = self._fork()
        self.assertEqual(len(fork.action_queue), len(self.h.env.action_queue))

    def test_fork_preserves_board_geometry(self):
        fork = self._fork()
        self.assertEqual(fork.board.width, self.h.env.board.width)
        self.assertEqual(fork.board.height, self.h.env.board.height)
        self.assertEqual(fork.board.boarder, self.h.env.board.boarder)

    def test_fork_preserves_max_rounds(self):
        fork = self._fork()
        self.assertEqual(fork.max_rounds, self.h.env.max_rounds)

    def test_fork_preserves_team_identity(self):
        fork = self._fork()
        self.assertEqual(fork.player1.id, self.h.env.player1.id)
        self.assertEqual(fork.player2.id, self.h.env.player2.id)

    def test_fork_current_piece_matches_id(self):
        fork = self._fork()
        self.assertIsNotNone(fork.current_piece)
        self.assertEqual(fork.current_piece.id, self.h.env.current_piece.id)

    def test_fork_action_queue_order(self):
        """The relative order of pieces should be preserved."""
        fork = self._fork()
        for orig, fk in zip(self.h.env.action_queue, fork.action_queue):
            self.assertEqual(orig.id, fk.id)

    def test_mutate_one_piece_in_fork(self):
        """Changing a piece in the fork shouldn't change the original."""
        fork = self._fork()
        fork.action_queue[0].health = 999
        self.assertNotEqual(
            self.h.env.action_queue[0].health,
            fork.action_queue[0].health,
        )

    def test_fork_preserves_game_over_state(self):
        fork = self._fork()
        self.assertEqual(fork.is_game_over, self.h.env.is_game_over)

    def test_fork_with_current_none(self):
        from strategy_utils import fork_environment
        self.h.env.current_piece = None
        fork = fork_environment(self.h.env)
        self.assertIsNone(fork.current_piece)

    def test_fork_preserves_board_height_map(self):
        fork = self._fork()
        for x in range(self.h.env.board.width):
            for y in range(self.h.env.board.height):
                self.assertEqual(
                    fork.board.height_map[x][y],
                    self.h.env.board.height_map[x][y],
                )

    def test_forked_env_can_step(self):
        """A forked environment should be able to run step_with_action."""
        from strategy_utils import fork_environment, step_with_action
        fork = fork_environment(self.h.env)
        action = _make_simple_action(move=True, move_target=Point(2, 1))
        step_with_action(fork, action)
        self.assertIsNotNone(fork.current_piece)
        self.assertGreater(fork.round_number, self.h.env.round_number)


# =========================================================================
# step_with_action additional tests
# =========================================================================


class TestStepWithAction(unittest.TestCase):
    """Tests for step_with_action beyond what test_game_logic covers."""

    def setUp(self):
        self.h = _EnvHelper()
        self.h.env.max_rounds = 100

    def _step(self, action: ActionSet) -> None:
        from strategy_utils import step_with_action
        step_with_action(self.h.env, action)

    def test_current_piece_changes_each_step(self):
        """The current piece should cycle through the queue."""
        first = self.h.env.current_piece.id
        action = _make_simple_action()
        self._step(action)
        second = self.h.env.current_piece.id
        self._step(action)
        third = self.h.env.current_piece.id
        self.assertNotEqual(first, second)
        self.assertEqual(first, third)  # full cycle for 2 pieces

    def test_move_actuates_piece(self):
        pos_before = self.h.p1.position
        action = _make_simple_action(move=True, move_target=Point(2, 1),
                                     attacker=self.h.p1, target=self.h.p2)
        self._step(action)
        self.assertNotEqual(self.h.p1.position, pos_before)
        self.assertEqual(self.h.p1.position, Point(2, 1))

    def test_attack_deals_damage(self):
        """Attacking the enemy in step_with_action should reduce HP."""
        self.h.p1 = _make_piece(team=1, pos=Point(5, 5), weapon=3, strength=10)
        self.h.p2 = _make_piece(team=2, pos=Point(5, 8), armor=2)
        self.h.env.action_queue = np.array([self.h.p1, self.h.p2], dtype=object)
        self.h.env.current_piece = self.h.p1
        for p in [self.h.p1, self.h.p2]:
            self.h.env.board.grid[p.position.x][p.position.y].state = 2
            self.h.env.board.grid[p.position.x][p.position.y].player_id = p.team
            self.h.env.board.grid[p.position.x][p.position.y].piece_id = p.id

        hp_before = self.h.p2.health
        ctx = AttackContext()
        ctx.attacker = self.h.p1
        ctx.target = self.h.p2
        action = _make_simple_action(attack=True, attacker=self.h.p1, target=self.h.p2)
        self._step(action)
        self.assertLess(self.h.p2.health, hp_before)

    def test_round_number_increments(self):
        r0 = self.h.env.round_number
        self._step(_make_simple_action())
        self.assertEqual(self.h.env.round_number, r0 + 1)

    def test_game_over_after_all_dead(self):
        self.h.p2.is_alive = False
        self._step(_make_simple_action())
        self.assertTrue(self.h.env.is_game_over)

    def test_game_over_at_max_rounds(self):
        self.h.env.round_number = self.h.env.max_rounds - 1
        self._step(_make_simple_action())
        self.assertTrue(self.h.env.is_game_over)

    def test_alive_piece_keeps_game_going(self):
        self._step(_make_simple_action())
        self.assertFalse(self.h.env.is_game_over)

    def test_delayed_spell_expires(self):
        """A delayed spell with negative lifespan is removed."""
        spell = SpellFactory.get_spell_by_id(4)  # trap, lifespan=2
        from utils import SpellContext
        ctx = SpellContext()
        ctx.spell = spell
        ctx.spell_lifespan = -1
        ctx.caster = self.h.p1
        self.h.env.delayed_spells = np.array([ctx], dtype=object)
        self._step(_make_simple_action())
        self.assertEqual(len(self.h.env.delayed_spells), 0)

    def test_new_current_piece_has_full_ap(self):
        self.h.p1.set_action_points(0)
        action = _make_simple_action(move=True, move_target=Point(2, 1))
        self._step(action)
        # The new current piece should have its AP reset
        self.assertGreater(self.h.env.current_piece.action_points, 0)


if __name__ == "__main__":
    unittest.main()
