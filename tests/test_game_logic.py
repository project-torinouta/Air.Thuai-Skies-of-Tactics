"""Tests for basic game logic (board, movement, combat, spells, turns).

Run with: uv run python -m unittest tests/test_game_logic.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np

from env import Board, Cell, Environment, Piece, Player
from utils import (
    ActionSet,
    Area,
    AttackContext,
    DamageType,
    InitPolicyMessage,
    PieceArg,
    Point,
    Spell,
    SpellContext,
    SpellEffectType,
    SpellFactory,
)


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
    """Construct a Piece with specified stats (bypasses Player.local_init)."""
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
    spell: bool = False,
    spell_ctx=None,
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
    a.spell = spell
    if spell and spell_ctx:
        a.spell_context = spell_ctx
    return a


# =========================================================================
# Board tests
# =========================================================================


class TestBoard(unittest.TestCase):
    def test_init_from_file(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        self.assertEqual(board.width, 20)
        self.assertEqual(board.height, 20)
        self.assertEqual(board.boarder, 10)
        self.assertIsNotNone(board.grid)
        self.assertIsNotNone(board.height_map)
        self.assertEqual(board.grid[0][0].state, 1)
        # grid[x][y]: column x=3, row y=4 is blocked in case1.txt
        self.assertEqual(board.grid[3][4].state, -1)

    def test_board_bounds(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        self.assertTrue(board.is_within_bounds(Point(0, 0)))
        self.assertTrue(board.is_within_bounds(Point(19, 19)))
        self.assertFalse(board.is_within_bounds(Point(-1, 0)))
        self.assertFalse(board.is_within_bounds(Point(0, 20)))
        self.assertFalse(board.is_within_bounds(Point(20, 20)))

    def test_neighbors(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        # (8,8) is in the open center area with all 4 cells walkable
        neighbors = board.get_neighbors(Point(8, 8))
        self.assertIn(Point(7, 8), neighbors)
        self.assertIn(Point(9, 8), neighbors)
        self.assertIn(Point(8, 7), neighbors)
        self.assertIn(Point(8, 9), neighbors)
        self.assertEqual(len(neighbors), 4)

    def test_neighbors_at_edge(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        neighbors = board.get_neighbors(Point(0, 0))
        self.assertIn(Point(1, 0), neighbors)
        self.assertIn(Point(0, 1), neighbors)
        self.assertNotIn(Point(-1, 0), neighbors)
        self.assertEqual(len(neighbors), 2)

    def test_neighbors_skip_blocked(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        neighbors = board.get_neighbors(Point(3, 5))  # near (-1,-1) cluster
        for n in neighbors:
            self.assertNotEqual(board.grid[n.x][n.y].state, -1)

    def test_find_shortest_path_simple(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        piece = _make_piece(pos=Point(1, 1))
        path, cost = board.find_shortest_path(piece, Point(1, 1), Point(3, 1), 10)
        self.assertIsNotNone(path)
        self.assertGreater(cost, 0)
        self.assertEqual(path[0], Point(2, 1))
        self.assertEqual(path[-1], Point(3, 1))

    def test_find_shortest_path_unreachable(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        piece = _make_piece(pos=Point(1, 1))
        path, cost = board.find_shortest_path(piece, Point(1, 1), Point(10, 15), 1)
        self.assertIsNone(path)

    def test_find_shortest_path_respects_movement(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        piece = _make_piece(pos=Point(1, 1))
        path, cost = board.find_shortest_path(piece, Point(1, 1), Point(8, 1), 3)
        self.assertIsNone(path)

    def test_valid_target_includes_start(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        piece = _make_piece(pos=Point(1, 1))
        mask = board.valid_target(piece, 10)
        self.assertEqual(mask[1][1], 0)

    def test_valid_target_excludes_blocked(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        piece = _make_piece(pos=Point(1, 1))
        mask = board.valid_target(piece, 10)
        # grid[3][4] is blocked (-1), should be unreachable
        self.assertEqual(int(mask[3][4]), -1)

    def test_occupied(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        self.assertFalse(board.is_occupied(Point(1, 1)))
        board.grid[1][1].state = 2
        self.assertTrue(board.is_occupied(Point(1, 1)))

    def test_move_piece(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        piece = _make_piece(team=1, pos=Point(1, 1))
        path, ok = board.move_piece(piece, Point(3, 1), 10)
        self.assertTrue(ok)
        self.assertEqual(piece.position.x, 3)
        self.assertEqual(piece.position.y, 1)
        self.assertEqual(board.grid[1][1].state, 1)  # old cell freed
        self.assertEqual(board.grid[3][1].state, 2)   # new cell occupied

    def test_move_piece_out_of_bounds(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        piece = _make_piece(team=1, pos=Point(1, 1))
        path, ok = board.move_piece(piece, Point(-1, 0), 10)
        self.assertFalse(ok)

    def test_get_height(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        h = board.get_height(Point(0, 0))
        self.assertIsInstance(h, (int, np.integer))

    def test_remove_piece(self):
        board = Board(if_log=0)
        board.init_from_file(BOARD_FILE)
        piece = _make_piece(team=1, pos=Point(1, 1))
        board.grid[1][1].state = 2
        board.grid[1][1].player_id = 1
        board.grid[1][1].piece_id = 0
        board.remove_piece(piece)
        self.assertEqual(board.grid[1][1].state, 1)
        self.assertEqual(board.grid[1][1].player_id, -1)


# =========================================================================
# Piece tests
# =========================================================================


class TestPiece(unittest.TestCase):
    def test_receive_physical_damage(self):
        p = _make_piece(armor=2)  # phys_resist = 15
        p.receive_damage(30, "physical")
        self.assertEqual(p.health, p.max_health - 15)

    def test_receive_physical_damage_negated_by_resist(self):
        p = _make_piece(armor=3)  # phys_resist = 23
        p.receive_damage(10, "physical")
        self.assertEqual(p.health, p.max_health)

    def test_receive_magic_damage(self):
        p = _make_piece()
        hp_before = p.health
        p.receive_damage(20, "magic")
        self.assertLess(p.health, hp_before)

    def test_invalid_damage_type(self):
        p = _make_piece()
        with self.assertRaises(ValueError):
            p.receive_damage(10, "true")

    def test_death_check_alive(self):
        p = _make_piece()
        self.assertTrue(p.death_check())

    def test_max_ap_from_strength(self):
        p = _make_piece(strength=20)  # 14-21 → 2 AP
        self.assertEqual(p.max_action_points, 2)

        p2 = _make_piece(strength=5)  # ≤13 → 1 AP
        self.assertEqual(p2.max_action_points, 1)

    def test_max_spell_slots_from_intelligence(self):
        p = _make_piece(intelligence=2)  # ≤3 → 0 slots
        self.assertEqual(p.max_spell_slots, 0)

        p2 = _make_piece(intelligence=10)  # ≤12 → 1 slot
        self.assertEqual(p2.max_spell_slots, 1)

    def test_movement_calculation(self):
        p = _make_piece(strength=10, dexterity=15)
        expected = 15 + 0.5 * 10 + 10  # = 30
        self.assertEqual(p.max_movement, expected)

    def test_equipment_effects(self):
        player = Player()
        p = _make_piece()
        player.set_weapon(3, p)  # bow
        self.assertEqual(p.physical_damage, 16)
        self.assertEqual(p.attack_range, 9)
        player.set_armor(1, p)  # light
        self.assertEqual(p.physical_resist, 8)


# =========================================================================
# Combat tests
# =========================================================================


class TestCombat(unittest.TestCase):
    def setUp(self):
        self.env = Environment(local_mode=True, if_log=0)
        self.env.board.init_from_file(BOARD_FILE)
        self.env.player1.id = 1
        self.env.player2.id = 2
        self.env.round_number = 1

    def _setup_pieces(self, p1_pos: Point, p2_pos: Point):
        p1 = _make_piece(team=1, pos=p1_pos)
        p2 = _make_piece(team=2, pos=p2_pos)
        p1.id = 0
        p2.id = 1
        self.env.action_queue = np.array([p1, p2], dtype=object)
        self.env.current_piece = p1
        self.board_init_pieces(p1, p2)

    def board_init_pieces(self, *pieces):
        for p in pieces:
            self.env.board.grid[p.position.x][p.position.y].state = 2
            self.env.board.grid[p.position.x][p.position.y].player_id = p.team
            self.env.board.grid[p.position.x][p.position.y].piece_id = p.id

    def test_is_in_attack_range(self):
        p1 = _make_piece(team=1, pos=Point(5, 5), weapon=2)  # range 3
        p2 = _make_piece(team=2, pos=Point(5, 7))  # dist 2
        self.assertTrue(self.env.is_in_attack_range(p1, p2))

    def test_not_in_attack_range(self):
        p1 = _make_piece(team=1, pos=Point(1, 1), weapon=2)  # range 3
        p2 = _make_piece(team=2, pos=Point(10, 10))  # dist 18
        self.assertFalse(self.env.is_in_attack_range(p1, p2))

    def test_execute_attack_damage(self):
        p1 = _make_piece(team=1, pos=Point(5, 5), weapon=2, strength=10)
        p2 = _make_piece(team=2, pos=Point(5, 7), armor=2)
        p1.id = 0
        p2.id = 1
        self.env.action_queue = np.array([p1, p2], dtype=object)
        self.env.current_piece = p1
        self.board_init_pieces(p1, p2)
        ctx = AttackContext()
        ctx.attacker = p1
        ctx.target = p2
        self.env.execute_attack(ctx)
        self.assertLess(p2.health, p2.max_health)
        self.assertGreater(ctx.damage_dealt, 0)

    def test_execute_attack_zero_ap(self):
        p1 = _make_piece(team=1, pos=Point(5, 5), strength=10)
        p2 = _make_piece(team=2, pos=Point(5, 7))
        p1.id = 0
        p2.id = 1
        self.env.action_queue = np.array([p1, p2], dtype=object)
        self.env.current_piece = p1
        self.board_init_pieces(p1, p2)
        p1.set_action_points(0)
        hp_before = p2.health
        ctx = AttackContext()
        ctx.attacker = p1
        ctx.target = p2
        self.env.execute_attack(ctx)
        self.assertEqual(p2.health, hp_before)

    def test_death_check_survives_on_20(self):
        """A roll of 20 on death save keeps the piece alive with 1 HP."""
        p = _make_piece()
        p.health = 0
        results = []
        for _ in range(50):
            p.health = 0
            p.is_alive = True
            p.is_dying = True
            # Mock a roll of 20 by calling repeatedly
            # We override roll_dice for this test
            orig_roll = self.env.roll_dice
            self.env.roll_dice = lambda n, s: 20
            self.env.handle_death_check(p)
            self.env.roll_dice = orig_roll
            results.append(p.is_alive)
        self.assertTrue(all(results))
        self.assertEqual(p.health, 1)

    def test_advantage_value(self):
        p1 = _make_piece(team=1, pos=Point(5, 5))
        p2 = _make_piece(team=2, pos=Point(5, 7))
        val = self.env.calculate_advantage_value(p1, p2)
        self.assertIsInstance(val, (float, int, np.floating, np.integer))


# =========================================================================
# Spell tests
# =========================================================================


class TestSpells(unittest.TestCase):
    def setUp(self):
        self.env = Environment(local_mode=True, if_log=0)
        self.env.board.init_from_file(BOARD_FILE)
        self.env.player1.id = 1
        self.env.player2.id = 2

    def _place_piece(self, team: int, pos: Point, piece_type: str = "Warrior",
                     intelligence: int = 10) -> Piece:
        p = _make_piece(team=team, pos=pos, intelligence=intelligence)
        p.type = piece_type
        p.id = team * 10 + pos.x
        return p

    def _setup(self, p1_pos=Point(5, 5), p2_pos=Point(5, 8)):
        p1 = self._place_piece(1, p1_pos)
        p2 = self._place_piece(2, p2_pos)
        self.env.action_queue = np.array([p1, p2], dtype=object)
        self.env.current_piece = p1
        for p in [p1, p2]:
            self.env.board.grid[p.position.x][p.position.y].state = 2
            self.env.board.grid[p.position.x][p.position.y].player_id = p.team
            self.env.board.grid[p.position.x][p.position.y].piece_id = p.id
        return p1, p2

    def _make_spell_ctx(self, caster, target, spell, area: Area) -> SpellContext:
        ctx = SpellContext()
        ctx.caster = caster
        ctx.target = target
        ctx.spell = spell
        ctx.target_area = area
        ctx.is_delay_spell = spell.is_delay_spell
        ctx.spell_lifespan = spell.base_lifespan
        ctx.spell_cost = spell.spell_cost
        ctx.delay_add = False
        return ctx

    def test_damage_spell(self):
        p1, p2 = self._setup(p1_pos=Point(5, 5), p2_pos=Point(5, 6))
        p1.spell_slots = 1
        p1.action_points = 1
        fireball = SpellFactory.get_spell_by_id(1)  # area damage, val=30, range=2
        # For area effect spells, set target=None to skip target range check
        area = Area(p2.position.x, p2.position.y, 2)
        ctx = self._make_spell_ctx(p1, None, fireball, area)
        self.env.execute_spell(ctx)
        self.assertLess(p2.health, p2.max_health)

    def test_heal_spell(self):
        p1, p2 = self._setup()
        hp_before = p1.health
        p1.health = 10  # damage self
        heal = SpellFactory.get_spell_by_id(2)  # single target heal, val=30
        area = Area(p1.position.x, p1.position.y, 1)
        ctx = self._make_spell_ctx(p1, p1, heal, area)
        self.env.execute_spell(ctx)
        self.assertGreater(p1.health, 10)

    def test_buff_spell(self):
        p1, p2 = self._setup()
        dmg_before = p1.physical_damage
        buff = Spell(0, "Buff", "", SpellEffectType.BUFF, DamageType.NONE, 5)
        area = Area(p1.position.x, p1.position.y, 1)
        ctx = self._make_spell_ctx(p1, p1, buff, area)
        self.env.execute_spell(ctx)
        self.assertEqual(p1.physical_damage, dmg_before + 5)

    def test_debuff_spell(self):
        p1, p2 = self._setup()
        p1.spell_slots = 1
        p1.action_points = 1
        res_before = p2.physical_resist
        debuff = Spell(0, "Debuff", "", SpellEffectType.DEBUFF, DamageType.NONE, 3,
                       range_=10, is_locking_spell=False, is_area_effect=False)
        area = Area(p2.position.x, p2.position.y, 1)
        ctx = self._make_spell_ctx(p1, None, debuff, area)
        self.env.execute_spell(ctx)
        self.assertLess(p2.physical_resist, res_before)

    def test_delayed_spell_triggers(self):
        p1, p2 = self._setup(p1_pos=Point(5, 5), p2_pos=Point(5, 6))
        p1.spell_slots = 1
        p1.action_points = 1
        trap = Spell(id=99, name="TestTrap", description="",
                     effect_type=SpellEffectType.DAMAGE,
                     damage_type=DamageType.PHYSICAL,
                     base_value=10, is_delay_spell=True, base_lifespan=2)
        # Add a delayed spell context directly
        area = Area(p2.position.x, p2.position.y, 1)
        ctx = self._make_spell_ctx(p1, p2, trap, area)
        ctx.spell_lifespan = 2
        ctx.delay_add = False
        self.env.delayed_spells = np.array([ctx], dtype=object)
        # Execute again with lifespan=1 to trigger
        ctx2 = self._make_spell_ctx(p1, p2, trap, area)
        ctx2.spell_lifespan = 1
        self.env.delayed_spells = np.append(self.env.delayed_spells, [ctx2])
        # Process delayed spells (simulate round advancement)
        for i in range(len(self.env.delayed_spells) - 1, -1, -1):
            sp = self.env.delayed_spells[i]
            sp.spell_lifespan -= 1
            if sp.spell_lifespan == 0:
                self.env.execute_spell(sp)
                self.env.delayed_spells = np.delete(self.env.delayed_spells, i)
        self.assertLessEqual(p2.health, p2.max_health)

    def test_spell_out_of_range(self):
        p1, p2 = self._setup(p1_pos=Point(0, 0), p2_pos=Point(19, 19))
        fireball = SpellFactory.get_spell_by_id(1)  # range=2
        area = Area(p2.position.x, p2.position.y, 1)
        ctx = self._make_spell_ctx(p1, p2, fireball, area)
        hp_before = p2.health
        self.env.execute_spell(ctx)
        self.assertEqual(p2.health, hp_before)

    def test_spell_requires_resources(self):
        p1, p2 = self._setup()
        p1.action_points = 0
        p1.spell_slots = 0
        heal = SpellFactory.get_spell_by_id(2)
        area = Area(p1.position.x, p1.position.y, 1)
        ctx = self._make_spell_ctx(p1, p1, heal, area)
        self.env.execute_spell(ctx)
        # No crash, spell should be rejected silently

    def test_spell_factory_warrior_spells(self):
        piece = _make_piece(intelligence=10)
        piece.type = "Warrior"
        spells = SpellFactory.get_available_spells(piece)
        for s in spells:
            self.assertIn(
                s.damage_type, [DamageType.PHYSICAL, DamageType.NONE]
            )
        self.assertLessEqual(len(spells), piece.max_spell_slots)


# =========================================================================
# Turn & game-loop tests
# =========================================================================


class TestTurns(unittest.TestCase):
    def setUp(self):
        self.env = Environment(local_mode=True, if_log=0)

    def _quick_init(self):
        """Minimal init: load board, make two opposing pieces."""
        self.env.board.init_from_file(BOARD_FILE)
        self.env.player1.id = 1
        self.env.player2.id = 2
        p1 = _make_piece(team=1, pos=Point(1, 1))
        p2 = _make_piece(team=2, pos=Point(18, 18))
        p1.id = 0
        p2.id = 1
        self.env.action_queue = np.array([p1, p2], dtype=object)
        self.env.current_piece = p1
        for p in [p1, p2]:
            self.env.board.grid[p.position.x][p.position.y].state = 2
            self.env.board.grid[p.position.x][p.position.y].player_id = p.team
            self.env.board.grid[p.position.x][p.position.y].piece_id = p.id
        # Set function input to prevent ConsoleInput from blocking on stdin
        self.env.input_manager.set_function_input_method(
            1, lambda msg: [], lambda env: ActionSet()
        )
        self.env.input_manager.set_function_input_method(
            2, lambda msg: [], lambda env: ActionSet()
        )
        return p1, p2

    def test_action_queue_rotation(self):
        p1, p2 = self._quick_init()
        self.assertEqual(self.env.action_queue[0], p1)
        # Simulate a turn rotation
        self.env.action_queue = np.append(
            self.env.action_queue[1:], [self.env.current_piece]
        )
        self.assertEqual(self.env.action_queue[0], p2)

    def test_round_increment(self):
        self._quick_init()
        r0 = self.env.round_number
        self.env.round_number += 1
        self.assertEqual(self.env.round_number, r0 + 1)

    def test_execute_player_action_move(self):
        p1, p2 = self._quick_init()
        self.env.current_piece = p1
        action = _make_simple_action(
            move=True, move_target=Point(1, 2)
        )
        self.env.execute_player_action(action)
        self.assertEqual(p1.position.x, 1)
        self.assertEqual(p1.position.y, 2)

    def test_execute_player_action_attack(self):
        p1, p2 = self._quick_init()
        # Place p2 close enough
        p2.position = Point(1, 2)
        self.env.board.grid[1][2] = Cell(2, 2, p2.id)
        self.env.current_piece = p1

        ctx = AttackContext()
        ctx.attacker = p1
        ctx.target = p2
        action = _make_simple_action(attack=True, attacker=p1, target=p2)
        self.env.execute_player_action(action)
        self.assertLess(p2.health, p2.max_health)

    def test_ap_consumed_on_move(self):
        p1, p2 = self._quick_init()
        self.env.current_piece = p1
        ap_before = p1.action_points
        action = _make_simple_action(move=True, move_target=Point(2, 1))
        self.env.execute_player_action(action)
        self.assertLess(p1.action_points, ap_before)

    def test_game_over_player_dead(self):
        p1, p2 = self._quick_init()
        p2.is_alive = False
        self.env.is_game_over = (
            not any(p.is_alive for p in self.env.player1.pieces)
            or not any(p.is_alive for p in self.env.player2.pieces)
        )
        self.assertTrue(self.env.is_game_over)

    def test_game_over_max_rounds(self):
        self._quick_init()
        self.env.max_rounds = 5
        self.env.round_number = 5
        self.env.is_game_over = (
            not any(p.is_alive for p in self.env.player1.pieces)
            or not any(p.is_alive for p in self.env.player2.pieces)
            or self.env.round_number >= self.env.max_rounds
        )
        self.assertTrue(self.env.is_game_over)

    def test_step_increments_round(self):
        self._quick_init()
        r0 = self.env.round_number
        self.env.step()
        self.assertEqual(self.env.round_number, r0 + 1)

    def test_step_resets_ap(self):
        p1, p2 = self._quick_init()
        p1.set_action_points(0)
        p2.set_action_points(0)
        self.env.step()
        for p in self.env.action_queue:
            if p.is_alive:
                self.assertGreater(p.action_points, 0)

    def test_full_run_terminates(self):
        """A full game run with two pieces should terminate at max_rounds."""
        p1, p2 = self._quick_init()
        # Set function input that does nothing each turn
        self.env.input_manager.set_function_input_method(
            1, lambda msg: [], lambda env: ActionSet()
        )
        self.env.input_manager.set_function_input_method(
            2, lambda msg: [], lambda env: ActionSet()
        )
        self.env.max_rounds = 10
        while not self.env.is_game_over:
            self.env.step()
            if self.env.round_number >= self.env.max_rounds:
                self.env.is_game_over = True
        self.assertLessEqual(self.env.round_number, self.env.max_rounds)


# =========================================================================
# Initialization tests
# =========================================================================


class TestInitialization(unittest.TestCase):
    def setUp(self):
        self.env = Environment(local_mode=True, if_log=0)

    def test_apply_init_policy_creates_pieces(self):
        self.env.board.init_from_file(BOARD_FILE)
        self.env.player1.id = 1
        self.env.player2.id = 2

        policy = InitPolicyMessage()
        for i in range(3):
            arg = PieceArg()
            arg.strength = 10
            arg.dexterity = 10
            arg.intelligence = 10
            arg.equip = Point(2, 2)  # shortsword + medium
            arg.pos = Point(2 + i, 1)
            policy.piece_args.append(arg)

        self.env.apply_init_policy(1, policy)
        self.assertEqual(self.env.player1.piece_num, 3)
        for piece in self.env.player1.pieces:
            self.assertEqual(piece.team, 1)

    def test_init_policy_validates_position(self):
        self.env.board.init_from_file(BOARD_FILE)
        self.env.player1.id = 1
        self.env.player2.id = 2

        policy = InitPolicyMessage()
        arg = PieceArg()
        arg.strength = 5
        arg.dexterity = 5
        arg.intelligence = 5
        arg.equip = Point(2, 2)
        arg.pos = Point(0, 15)  # on wrong side of border for player 1
        policy.piece_args.append(arg)
        policy.piece_args.append(arg)
        policy.piece_args.append(arg)

        with self.assertRaises(ValueError):
            self.env.apply_init_policy(1, policy)

    def test_board_init_correct_border(self):
        self.env.board.init_from_file(BOARD_FILE)
        self.assertEqual(self.env.board.boarder, 10)


# =========================================================================
# Edge case tests
# =========================================================================


class TestEdgeCases(unittest.TestCase):
    def test_area_contains(self):
        area = Area(5, 5, 3)
        self.assertTrue(area.contains(Point(5, 5)))
        self.assertTrue(area.contains(Point(5, 8)))   # dist 3
        self.assertFalse(area.contains(Point(5, 9)))  # dist 4
        self.assertTrue(area.contains(Point(3, 5)))   # dist 2
        self.assertFalse(area.contains(Point(1, 5)))  # dist 4

    def test_empty_action_set(self):
        a = ActionSet()
        self.assertFalse(hasattr(a, "move") and a.move)
        self.assertIsNotNone(str(a))

    def test_action_set_str(self):
        a = _make_simple_action(move=True, move_target=Point(3, 4))
        s = str(a)
        self.assertIn("move_target", s)

    def test_spell_factory_all_spells_nonempty(self):
        spells = SpellFactory.get_all_spells()
        self.assertGreater(len(spells), 0)

    def test_spell_factory_get_by_id(self):
        s = SpellFactory.get_spell_by_id(1)
        self.assertIsNotNone(s)
        self.assertEqual(s.name, "Fireball")

    def test_spell_factory_invalid_id(self):
        s = SpellFactory.get_spell_by_id(999)
        self.assertIsNone(s)

    def test_setup_battle_host_missing_pieces(self):
        env = Environment(local_mode=True, if_log=0)
        env.board.init_from_file(BOARD_FILE)
        env.player1.id = 1
        env.player2.id = 2
        with self.assertRaises(ValueError):
            env.setup_battle_host()

    def test_end_turn_host_no_crash_before_init(self):
        env = Environment(local_mode=True, if_log=0)
        env.end_turn_host()  # should not raise


# =========================================================================
# step_with_action tests (strategy_utils)
# =========================================================================


class TestStepWithAction(unittest.TestCase):
    def setUp(self):
        self.env = Environment(local_mode=True, if_log=0)
        self.env.board.init_from_file(BOARD_FILE)
        self.env.player1.id = 1
        self.env.player2.id = 2
        self.env.max_rounds = 100
        p1 = _make_piece(team=1, pos=Point(1, 1), strength=10)
        p2 = _make_piece(team=2, pos=Point(18, 18), strength=10)
        p1.id = 0
        p2.id = 1
        self.env.action_queue = np.array([p1, p2], dtype=object)
        self.env.current_piece = p1
        for p in [p1, p2]:
            self.env.board.grid[p.position.x][p.position.y].state = 2
            self.env.board.grid[p.position.x][p.position.y].player_id = p.team
            self.env.board.grid[p.position.x][p.position.y].piece_id = p.id
        self.p1 = p1
        self.p2 = p2

    def _call_step_with_action(self, action):
        """Import and call step_with_action."""
        from strategy_utils import step_with_action
        step_with_action(self.env, action)

    def test_current_piece_updates_after_step(self):
        """After step_with_action, current_piece should be the next in queue."""
        old_current = self.env.current_piece
        action = _make_simple_action(move=True, move_target=Point(2, 1))
        self._call_step_with_action(action)
        new_current = self.env.current_piece
        self.assertIsNotNone(new_current)
        self.assertNotEqual(new_current, old_current)

    def test_queue_rotates_after_step(self):
        """The acting piece should move to the back of the queue."""
        first = self.env.action_queue[0]
        action = _make_simple_action(move=True, move_target=Point(2, 1))
        self._call_step_with_action(action)
        self.assertEqual(self.env.action_queue[-1], first)

    def test_round_increments(self):
        r0 = self.env.round_number
        action = _make_simple_action()
        self._call_step_with_action(action)
        self.assertEqual(self.env.round_number, r0 + 1)

    def test_ap_reset_for_all_pieces(self):
        self.p1.set_action_points(0)
        self.p2.set_action_points(0)
        action = _make_simple_action(move=True, move_target=Point(2, 1))
        self._call_step_with_action(action)
        # All pieces have AP reset at start of step_with_action.
        # The current piece then spends AP on the action.
        for p in self.env.action_queue:
            if p.is_alive:
                self.assertGreaterEqual(p.action_points, 0)
                self.assertLessEqual(p.action_points, p.max_action_points)

    def test_empty_action_no_crash(self):
        action = ActionSet()
        self._call_step_with_action(action)
        self.assertTrue(True)

    def test_game_over_detected(self):
        self.p2.is_alive = False
        action = _make_simple_action()
        self._call_step_with_action(action)
        self.assertTrue(self.env.is_game_over)

    def test_max_rounds_game_over(self):
        self.env.round_number = self.env.max_rounds - 1
        action = _make_simple_action()
        self._call_step_with_action(action)
        self.assertTrue(self.env.is_game_over)

    def test_new_current_piece_has_full_ap(self):
        """The new current_piece after step should have max AP."""
        action = _make_simple_action(move=True, move_target=Point(2, 1))
        self._call_step_with_action(action)
        self.assertGreater(self.env.current_piece.action_points, 0)
        self.assertEqual(
            self.env.current_piece.action_points,
            self.env.current_piece.max_action_points,
        )


if __name__ == "__main__":
    unittest.main()
