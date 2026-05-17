# THUAI9 Client API Documentation

This document provides a complete API reference for the client Python code.

---

## Table of Contents

0. [Quick Start Guide](#0-quick-start-guide)
1. [Core Data Structures](#1-core-data-structures)
2. [Environment Class](#2-environment-class)
3. [Piece-Related Classes](#3-piece-related-classes)
4. [Board Class](#4-board-class)
5. [Strategy Utilities (strategy_utils.py)](#5-strategy-utilities-strategy_utilspy)
6. [Strategy Factory (strategy_factory.py)](#6-strategy-factory-strategy_factorypy)
7. [Input Methods](#7-input-methods)
8. [Enumerations](#8-enumerations)
9. [Spell System](#9-spell-system)

---

## 0. Quick Start Guide

### 0.1 File Structure

```
client/
├── local_client.py      # Local test entry point (primary usage for contestants)
├── main.py              # Saiblo evaluation entry point (contestants only need to select strategy)
├── env.py               # Core game environment class
├── strategy_factory.py  # Strategy factory (contestants need to modify this file)
├── strategy_utils.py    # Strategy utility functions (helper functions for agent development, see Section 5, can use or modify)
├── utils.py             # Utility classes and enum definitions
└── local_input.py       # Input method management
```

### 0.2 How to Run Local Tests

#### Method 1: Console Two-Player Mode (Test Board and Rules)

```bash
cd client/client
python local_client.py --mode local --board ./BoardCase/case1.txt
```

**Parameters:**

| Parameter | Description     | Options              | Default                 |
| --------- | --------------- | -------------------- | ----------------------- |
| `--mode`  | Run mode        | `local` / `function` | `local`                 |
| `--board` | Board file path | Any valid path       | `./BoardCase/case1.txt` |

#### Method 2: AI Battle (Test Your Strategy)

```bash
# Use predefined strategies for AI battle
python local_client.py --mode function --strategy aggressive
python local_client.py --mode function --strategy defensive
python local_client.py --mode function --strategy mcts --mcts-simulations 25
```

**Parameters:**

| Parameter            | Description           | Options                             | Default      |
| -------------------- | --------------------- | ----------------------------------- | ------------ |
| `--mode`             | Run mode              | `function`                          | -            |
| `--strategy`         | AI strategy type      | `aggressive` / `defensive` / `mcts` | `aggressive` |
| `--mcts-simulations` | MCTS simulation count | Positive integer                    | 25           |

### 0.3 Files Contestants Need to Modify

**Primary file to modify: `strategy_factory.py`**

You need to implement the following two functions:

1. **Initialization Strategy Function** - Configure your piece attributes and
   starting positions

   ```python
   def your_init_strategy(init_message: InitGameMessage) -> List[PieceArg]:
       # Implement your initialization logic
       return piece_args
   ```

2. **Action Strategy Function** - Decide actions for each turn

   ```python
   def your_action_strategy(env: Environment) -> ActionSet:
       # Implement your action decision logic
       return action
   ```

### 0.4 Using Custom Strategies

The recommended approach is to **add a pair of "custom strategy functions"**
rather than modifying the built-in example strategies.

#### Step 1: Add Two Factory Methods in `client/client/strategy_factory.py`

Add the following to the `StrategyFactory` class:

- `get_custom_init_strategy() -> Callable[[InitGameMessage], List[PieceArg]]`
- `get_custom_action_strategy() -> Callable[[Environment], ActionSet]`

Example (structural only, implement your own logic):

```python
from typing import Callable, List
from env import Environment, InitGameMessage
from utils import ActionSet, PieceArg

class StrategyFactory:
    @staticmethod
    def get_custom_init_strategy() -> Callable[[InitGameMessage], List[PieceArg]]:
        def strategy(init_message: InitGameMessage) -> List[PieceArg]:
            piece_args: List[PieceArg] = []
            # TODO: Construct piece_args (length should be init_message.piece_cnt)
            return piece_args
        return strategy

    @staticmethod
    def get_custom_action_strategy() -> Callable[[Environment], ActionSet]:
        def strategy(env: Environment) -> ActionSet:
            action = ActionSet()
            # TODO: Fill action.move / action.attack / action.spell etc.
            return action
        return strategy
```

#### Step 2: Make the Entry Point Use Your Custom Strategy

> Both changes below simply replace the "strategy retrieval" part with
> `get_custom_*`, leaving the rest of the flow unchanged.

**Local battle entry point**: `client/client/local_client.py`

Replace the line in `main()` where the function mode retrieves the strategy
(line 70) with:

```python
init_strategy = StrategyFactory.get_custom_init_strategy()
action_strategy = StrategyFactory.get_custom_action_strategy()
```

Keep the original binding logic:

```python
env.input_manager.set_function_input_method(1, init_strategy, action_strategy)
env.input_manager.set_function_input_method(2, init_strategy, action_strategy)
```

**Saiblo entry point**: `client/client/main.py`

Note: Saiblo evaluation does not rely on command-line arguments, so this part
does not need to consider them when modifying main.py.

Replace the entire "strategy selection" section at the start of `run()` (lines
58~66) with:

```python
init_strategy = StrategyFactory.get_custom_init_strategy()
action_strategy = StrategyFactory.get_custom_action_strategy()
```

---

## 1. Core Data Structures

### 1.1 Point

```python
from utils import Point

# Constructor
Point(x: int, y: int)

# Attributes
point.x  # X coordinate
point.y  # Y coordinate
```

### 1.2 ActionSet

Represents a complete set of actions (move, attack, spell) for one turn.

```python
from utils import ActionSet

action = ActionSet()

# Attributes
action.move              # bool - whether to move (note: this field is not a mandatory constructor field; assign it explicitly before use, e.g., action.move = True/False)
action.move_target       # Point - movement target position
action.attack            # bool - whether to attack
action.attack_context    # AttackContext - attack context
action.spell             # bool - whether to cast a spell
action.spell_context     # SpellContext - spell context
```

### 1.3 PieceArg - Piece Initialization Parameters

```python
from utils import PieceArg

piece_arg = PieceArg()

# Attributes
piece_arg.strength      # int - strength attribute (0-30, total sum <= 30)
piece_arg.dexterity     # int - dexterity attribute (0-30, total sum <= 30)
piece_arg.intelligence  # int - intelligence attribute (0-30, total sum <= 30)
piece_arg.equip         # Point - equipment (x=weapon type 1-4, y=armor type 1-3)
piece_arg.pos           # Point - starting position
```

### 1.4 InitGameMessage

Input parameter for the initialization strategy function, containing game
initialization information.

```python
from utils import InitGameMessage

# Attributes
init_message.id           # int - player ID (1 or 2)
init_message.piece_cnt    # int - number of pieces
init_message.board        # Board - board object
```

### 1.5 AttackContext

```python
from utils import AttackContext

ctx = AttackContext()

# Attributes
ctx.attacker         # Piece - attacker
ctx.target           # Piece - target
ctx.damage_dealt     # int - damage dealt
ctx.attackPosition   # Point - attack position
```

### 1.6 SpellContext

```python
from utils import SpellContext

ctx = SpellContext()

# Attributes
ctx.caster           # Piece - spell caster
ctx.target           # Piece - target
ctx.spell            # Spell - spell object
ctx.target_area      # Area - target area
ctx.is_delay_spell   # bool - whether it is a delayed spell
ctx.spell_lifespan   # int - delayed spell duration in rounds
```

### 1.7 Area

```python
from utils import Area

area = Area(x: int, y: int, radius: int)

# Methods
area.contains(point: Point) -> bool  # Check if a point is within the area
```

---

## 2. Environment Class

Core game controller, managing the entire game flow.

### 2.1 Constructor

```python
from env import Environment

# Parameters
# local_mode: bool - whether in local mode (default True)
# if_log: int - log control, 1 enable, 0 disable (default 1)
env = Environment(local_mode=True, if_log=1)
```

### 2.2 Initialization Methods

```python
# Initialize the game
env.initialize(board_file: str = "./BoardCase/case1.txt") -> None

# Load board only (for external piece configuration)
env.init_board_only(board_file: Optional[str] = None) -> None

# Set up battle (call after configuring both sides' pieces)
env.setup_battle_host() -> None
```

### 2.3 Game Flow Control

```python
# Run the complete game
env.run(board_file: str = "./BoardCase/case1.txt") -> None

# Single turn step
env.step() -> None

# Begin turn
env.begin_turn_host() -> None

# Execute action
env.apply_action_host(action: ActionSet) -> None

# End turn
env.end_turn_host() -> None
```

### 2.4 State Queries

```python
# Get the current active piece
env.current_piece  # Piece - currently acting piece

# Get the board
env.board  # Board - board object

# Get players
env.player1  # Player - player 1
env.player2  # Player - player 2

# Get action queue
env.action_queue  # np.ndarray - action order queue

# Game state
env.is_game_over           # bool - whether the game is over
env.round_number           # int - current round number
env.is_battle_initialized  # bool - whether the battle has been initialized
```

### 2.5 Piece Operations

```python
# Get available spells for the current piece
env.get_available_spells(piece: Optional[Piece] = None) -> List[Spell]

# Get spell target options
env.get_spell_targets(spell: Spell, caster: Optional[Piece] = None) -> List[Piece]

# Check if within attack range
env.is_in_attack_range(attacker: Piece, target: Piece) -> bool

# Calculate advantage value (height + environment)
env.calculate_advantage_value(attacker: Piece, target: Piece) -> float
```

### 2.6 Helper Methods

```python
# Roll dice
env.roll_dice(n: int, sides: int) -> int

# Visualize board
env.visualize_board() -> None
```

---

## 3. Piece-Related Classes

### 3.1 Piece

```python
from env import Piece

piece = Piece()

# Attributes
piece.id              # int - piece ID
piece.type            # str - piece type ("Warrior", "Mage", "Archer")
piece.team            # int - team (1 or 2)
piece.position        # Point - current position
piece.height          # int - current height

# Health
piece.health          # int - current health
piece.max_health      # int - maximum health

# Attributes
piece.strength        # int - strength
piece.dexterity       # int - dexterity
piece.intelligence    # int - intelligence

# Combat attributes
piece.physical_damage     # int - physical damage
piece.physical_resist     # int - physical resistance
piece.attack_range        # int - attack range

# Resources
piece.action_points       # int - current action points
piece.max_action_points   # int - maximum action points
piece.spell_slots         # int - current spell slots
piece.max_spell_slots     # int - maximum spell slots
piece.movement            # float - current movement
piece.max_movement        # float - maximum movement

# Status
piece.is_alive        # bool - whether alive
piece.is_in_turn      # bool - whether currently acting
piece.is_dying        # bool - whether dying
piece.death_round     # int - death round (-1 if not dead)

# Methods
piece.receive_damage(damage: int, damage_type: str) -> None
piece.get_accessor() -> PieceAccessor
piece.set_action_points(action_points: int) -> None
piece.get_action_points() -> int
```

### 3.2 PieceAccessor

A safe interface for modifying piece attributes.

```python
accessor = piece.get_accessor()

# Attribute setter methods
accessor.set_health_to(value: int)
accessor.set_max_health_to(value: int)
accessor.set_strength_to(value: int)
accessor.set_dexterity_to(value: int)
accessor.set_intelligence_to(value: int)
accessor.set_physical_damage_to(value: int)
accessor.set_physical_resist_to(value: int)
accessor.set_attack_range_to(value: int)
accessor.set_max_movement_to(value: float)
accessor.set_movement_to(value: float)
accessor.set_position(new_pos: Point)
accessor.set_team_to(value: int)
accessor.set_alive(value: bool)

# Attribute adjustment methods
accessor.change_health_by(delta: int)
accessor.change_action_points_by(delta: int)
accessor.change_spell_slots_by(delta: int)
accessor.set_max_movement_by(value: float)
accessor.set_physic_resist_by(value: int)

# Auto-set methods
accessor.set_max_action_points()  # Auto-set based on strength
accessor.set_max_spell_slots()    # Auto-set based on intelligence
```

### 3.3 Player

```python
from env import Player

player = Player()

# Attributes
player.id          # int - player ID (1 or 2)
player.pieces      # np.ndarray - list of player's pieces
player.piece_num   # int - number of pieces
player.feature_total  # int - total attribute point limit (30)

# Methods
player.set_weapon(weapon: int, piece: Piece)  # Set weapon
player.set_armor(armor: int, piece: Piece)    # Set armor

# Static methods
Player.validate_piece_init(board, player_id, arg, index, occupied_same_player)  # Validate piece initialization
```

---

## 4. Board Class

```python
from env import Board

board = Board(if_log: int = 1)

# Attributes
board.width      # int - board width
board.height     # int - board height
board.grid       # 2D array - grid status
board.height_map # 2D array - height map
board.boarder    # int - border line position

# Methods
board.get_width() -> int
board.get_height() -> int

# Movement
board.valid_target(piece: Piece, movement: float) -> List[List[int]]
# Returns a 2D array indicating movement cost for each position, -1 means unreachable

board.move_piece(piece: Piece, to: Point, movement: float) -> Tuple[List[Point], bool]
# Returns (path, success) - path and whether successful

board.find_shortest_path(piece: Piece, start: Point, goal: Point, movement: float) -> Tuple[List[Point], float]
# Returns (path, cost) - path and cost

# State queries
board.is_occupied(point: Point) -> bool
board.get_height(point: Point) -> int
board.is_within_bounds(point: Point) -> bool
board.get_neighbors(point: Point) -> List[Point]

# Piece management
board.remove_piece(piece: Piece) -> None
board.init_pieces_location(player1_pieces, player2_pieces) -> None

# Initialization
board.init_from_file(file_path: str) -> None
```

---

## 5. Strategy Utilities (strategy_utils.py)

These functions are located in `strategy_utils.py` and are used for AI strategy
development. **Contestants can use these functions directly, and may also modify
them as needed.**

### 5.1 get_state_score

```python
from strategy_utils import get_state_score

# Get the score for the current game state
score = get_state_score(env: Environment) -> float

# Parameters:
#   env: Environment - game environment object

# Returns:
#   float - state score (positive for own team, negative for opponent)

# Scoring factors:
#   - Piece health ratio * 10
#   - Height * 0.5
#   - Action points * 2
#   - Spell slots * 1.5
#   - Damage value * 0.3
#   - Resistance value * 0.2
```

### 5.2 get_legal_moves

```python
from strategy_utils import get_legal_moves

# Get all legal move positions for the current piece
moves = get_legal_moves(env: Environment, piece: Optional[Piece] = None) -> List[Point]

# Parameters:
#   env: Environment - game environment object
#   piece: Optional[Piece] - piece object, defaults to the currently acting piece

# Returns:
#   List[Point] - list of legal move positions
```

### 5.3 get_attackable_targets

```python
from strategy_utils import get_attackable_targets

# Get the list of attackable targets for the current piece
targets = get_attackable_targets(env: Environment, piece: Optional[Piece] = None) -> List[Piece]

# Parameters:
#   env: Environment - game environment object
#   piece: Optional[Piece] - piece object, defaults to the currently acting piece

# Returns:
#   List[Piece] - list of attackable enemy pieces
```

### 5.4 simulate_move

```python
from strategy_utils import simulate_move

# Check if a move is feasible
can_move = simulate_move(env: Environment, piece: Piece, target: Point) -> bool

# Parameters:
#   env: Environment - game environment object
#   piece: Piece - piece object
#   target: Point - target position

# Returns:
#   bool - whether the piece can move to the target position
```

### 5.5 simulate_attack

```python
from strategy_utils import simulate_attack

# Simulate an attack and return estimated damage
damage = simulate_attack(env: Environment, attacker: Piece, target: Piece) -> float

# Parameters:
#   env: Environment - game environment object
#   attacker: Piece - attacking piece
#   target: Piece - target piece

# Returns:
#   float - estimated damage
```

### 5.6 step_with_action

```python
from strategy_utils import step_with_action

# Execute one turn step (does not modify the original environment)
step_with_action(env: Environment, action: ActionSet) -> None

# Parameters:
#   env: Environment - game environment object
#   action: ActionSet - set of actions

# Note: This function modifies the env object, used for simulating game progress
```

### 5.7 fork_environment

```python
from strategy_utils import fork_environment

# Create a copy of the environment (for search/simulation)
new_env = fork_environment(env: Environment) -> Environment

# Parameters:
#   env: Environment - the game environment object to copy

# Returns:
#   Environment - a deep copy of the environment

# Usage: For simulations in search algorithms such as Minimax, Alpha-Beta, MCTS
```

---

## 6. Strategy Factory (strategy_factory.py)

**This is the primary file contestants need to modify!** Provides predefined
strategy functions. Several simple strategies have already been implemented and
can be used directly or as references.

### 6.1 Initialization Strategy Functions

#### get_aggressive_init_strategy

```python
from strategy_factory import StrategyFactory

init_strategy = StrategyFactory.get_aggressive_init_strategy()
# Returns: Callable[[InitGameMessage], List[PieceArg]]

# Input parameters:
#   init_message: InitGameMessage - initialization game message
#       - init_message.id: int - player ID (1 or 2)
#       - init_message.piece_cnt: int - number of pieces
#       - init_message.board: Board - board object

# Returns:
#   List[PieceArg] - list of piece initialization parameters

# Strategy characteristics:
#   - High strength (20)
#   - Medium dexterity (8)
#   - Low intelligence (2)
#   - Equipment: Short Sword + Heavy Armor
#   - Position: Front line
```

#### get_defensive_init_strategy

```python
init_strategy = StrategyFactory.get_defensive_init_strategy()
# Returns: Callable[[InitGameMessage], List[PieceArg]]

# Strategy characteristics:
#   - Low strength (5)
#   - High dexterity (15)
#   - Medium intelligence (10)
#   - Equipment: Bow + Light Armor
#   - Position: Back line
```

#### get_random_init_strategy

```python
init_strategy = StrategyFactory.get_random_init_strategy()
# Returns: Callable[[InitGameMessage], List[PieceArg]]

# Strategy characteristics:
#   - Random attribute allocation
#   - Random equipment selection
#   - Random position placement
```

### 6.2 Action Strategy Functions

#### get_aggressive_action_strategy

```python
action_strategy = StrategyFactory.get_aggressive_action_strategy()
# Returns: Callable[[Environment], ActionSet]

# Input parameters:
#   env: Environment - game environment object

# Returns:
#   ActionSet - set of actions

# Strategy logic:
#   1. Find the nearest enemy
#   2. Move toward the enemy (choose the legal position closest to the enemy)
#   3. Attack if within range
#   4. Does not use spells
```

#### get_defensive_action_strategy

```python
action_strategy = StrategyFactory.get_defensive_action_strategy()
# Returns: Callable[[Environment], ActionSet]

# Strategy logic:
#   1. Find the nearest enemy
#   2. Keep distance (do not enter enemy attack range)
#   3. Use ranged attacks (bow)
#   4. Does not use spells
```

#### get_random_action_strategy

```python
action_strategy = StrategyFactory.get_random_action_strategy()
# Returns: Callable[[Environment], ActionSet]

# Strategy logic:
#   - Randomly choose move position
#   - Randomly choose attack target
#   - Randomly decide whether to use spells
```

#### get_alpha_beta_action_strategy

```python
action_strategy = StrategyFactory.get_alpha_beta_action_strategy(max_depth: int = 3)
# Parameters:
#   max_depth: int - search depth (default 3)
# Returns: Callable[[Environment], ActionSet]

# Input parameters:
#   env: Environment - game environment object

# Returns:
#   ActionSet - set of actions

# Strategy logic:
#   1. Uses Alpha-Beta pruning search
#   2. Evaluation function: get_state_score
#   3. Considers all legal moves and attacks
```

#### get_mcts_action_strategy

```python
action_strategy = StrategyFactory.get_mcts_action_strategy(simulation_count: int = 10)
# Parameters:
#   simulation_count: int - number of simulations per decision point (default 10)
# Returns: Callable[[Environment], ActionSet]

# Input parameters:
#   env: Environment - game environment object

# Returns:
#   ActionSet - set of actions

# Strategy logic:
#   1. Uses Monte Carlo Tree Search (MCTS)
#   2. Randomly expands the game tree
#   3. Selects the action with the highest win rate
```

### 6.3 Helper Methods

#### calculate_distance

```python
distance = StrategyFactory.calculate_distance(p1: Point, p2: Point) -> float

# Parameters:
#   p1: Point - starting point
#   p2: Point - ending point

# Returns:
#   float - Manhattan distance (|x1-x2| + |y1-y2|)
```

### 6.4 Custom Strategy Example

```python
# Add your strategy in strategy_factory.py

@staticmethod
def get_my_init_strategy() -> Callable[[InitGameMessage], List[PieceArg]]:
    """My initialization strategy"""
    def strategy(init_message: InitGameMessage) -> List[PieceArg]:
        piece_args = []

        for i in range(init_message.piece_cnt):
            arg = PieceArg()
            # Custom attribute allocation
            arg.strength = 15
            arg.dexterity = 10
            arg.intelligence = 5
            arg.equip = Point(1, 2)  # Weapon 1 + Armor 2
            arg.pos = Point(5 + i, 5)  # Custom position

            piece_args.append(arg)

        return piece_args

    return strategy


@staticmethod
def get_my_action_strategy() -> Callable[[Environment], ActionSet]:
    """My action strategy"""
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current = env.current_piece

        # Get legal moves
        moves = get_legal_moves(env)

        # Get attackable targets
        targets = get_attackable_targets(env)

        # Your strategy logic
        if targets:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = targets[0]

        if moves:
            action.move = True
            action.move_target = moves[0]

        return action

    return strategy
```

---

## 7. Input Methods

### 7.1 Input Method Interface

```python
from local_input import IInputMethod, FunctionInputMethod, InputMethodManager

# Create a functional input method
def my_init_handler(init_message):
    # Returns List[PieceArg]
    pass

def my_action_handler(env):
    # Returns ActionSet
    pass

input_method = FunctionInputMethod(my_init_handler, my_action_handler)

# Set up the manager
manager = InputMethodManager(env)
manager.set_function_input_method(player_id, my_init_handler, my_action_handler)
```

### 7.2 InputMethodManager Methods

```python
manager = InputMethodManager(env)

# Set a player's input method
manager.set_input_method(player_id: int, input_method: IInputMethod)

# Get a player's input method
method = manager.get_input_method(player_id: int) -> IInputMethod

# Set console input
manager.set_console_input_method(player_id: int)

# Set remote input
manager.set_remote_input_method(player_id: int)

# Check if using remote input
is_remote = manager.is_remote_input(player_id: int) -> bool
```

---

## 8. Enumerations

### 8.1 AttackType

```python
from utils import AttackType

AttackType.PHYSICAL   # Physical attack
AttackType.SPELL      # Spell attack
AttackType.EXCELLENCE # Excellence attack
```

### 8.2 SpellEffectType

```python
from utils import SpellEffectType

SpellEffectType.DAMAGE   # Damage
SpellEffectType.HEAL     # Heal
SpellEffectType.BUFF     # Buff
SpellEffectType.DEBUFF   # Debuff
SpellEffectType.MOVE     # Move
```

### 8.3 DamageType

```python
from utils import DamageType

DamageType.FIRE       # Fire
DamageType.ICE        # Ice
DamageType.LIGHTNING  # Lightning
DamageType.PHYSICAL   # Physical
DamageType.PURE       # Pure
DamageType.NONE       # None
```

### 8.4 TargetType

```python
from utils import TargetType

TargetType.SINGLE   # Single target
TargetType.AREA     # Area
TargetType.SELF     # Self
TargetType.CHAIN    # Chain
```

---

## 9. Spell System

### 9.1 Spell

```python
from utils import Spell

spell = Spell(
    id=0,
    name="",
    description="",
    effect_type=None,
    damage_type=None,
    base_value=0,
    range_=0,
    area_radius=0,
    spell_cost=0,
    base_lifespan=0,
    is_area_effect=False,
    is_delay_spell=False,
    is_locking_spell=False
)

# Attributes
spell.id              # int - spell ID
spell.name            # str - spell name
spell.description     # str - description
spell.effect_type     # SpellEffectType - effect type
spell.damage_type     # DamageType - damage type
spell.base_value      # int - base value
spell.range           # int - casting range
spell.area_radius     # int - area radius
spell.spell_cost      # int - spell slot cost
spell.base_lifespan   # int - duration in rounds
spell.is_area_effect  # bool - whether it is an area spell
spell.is_delay_spell  # bool - whether it is a delayed spell
spell.is_locking_spell # bool - whether it is a locking spell
```

### 9.2 SpellFactory

```python
from utils import SpellFactory

# Get all spells
spells = SpellFactory.get_all_spells() -> List[Spell]

# Get a spell by ID
spell = SpellFactory.get_spell_by_id(spell_id: int) -> Optional[Spell]

# Get spells available to a piece
available_spells = SpellFactory.get_available_spells(piece: Piece) -> List[Spell]
```

### 9.3 Built-in Spell List

| ID  | Name      | Effect Type | Damage Type | Base Value | Range | Area Radius | Cost | Description                         |
| --- | --------- | ----------- | ----------- | ---------- | ----- | ----------- | ---- | ----------------------------------- |
| 1   | Fireball  | DAMAGE      | FIRE        | 10         | 4     | 2           | 1    | Area damage (enemy only)            |
| 2   | Heal      | HEAL        | NONE        | 15         | 4     | 1           | 1    | Area heal (ally only, can be empty) |
| 3   | Arrow Hit | DAMAGE      | PHYSICAL    | 10         | 7     | 1           | 1    | Locking single-target damage        |
| 5   | Teleport  | MOVE        | PHYSICAL    | 30         | 100   | 100         | 1    | Teleport to target location         |

> **Trap (ID 4)** is disabled in the current version and is not in
> `SpellFactory.get_all_spells()`.

---

## Appendix: Attribute Calculation Formulas

### Health

- `max_health = 50 + strength * 2`

### Action Points

- Strength ≤ 13: 1 point
- Strength ≤ 21: 2 points
- Strength > 21: 3 points

### Spell Slots (`max_spell_slots`)

- Intelligence ≤ 3: 0 slots
- Intelligence ≤ 12: 1 slot
- Intelligence ≤ 16: 2 slots
- Intelligence ≤ 21: 3 slots
- Intelligence > 21: 5 slots

### Movement

- `max_movement = dexterity + 0.5 * strength + 10`

### Weapon Attributes

| Type | Name        | Physical Damage | Range | Notes                                                        |
| ---- | ----------- | --------------- | ----- | ------------------------------------------------------------ |
| 1    | Long Sword  | 8               | 5     | -                                                            |
| 2    | Short Sword | 10              | 3     | -                                                            |
| 3    | Bow         | 16              | 9     | -                                                            |
| 4    | Staff       | 0               | 12    | Normal attack deals fixed 4 true damage (ignores resistance) |

### Armor Attributes

| Type | Name         | Physical Resistance | Movement Effect |
| ---- | ------------ | ------------------- | --------------- |
| 1    | Light Armor  | 8                   | +3              |
| 2    | Medium Armor | 15                  | 0               |
| 3    | Heavy Armor  | 23                  | -3              |

---

_Document Version: 2.2 (THUAI9)_ _Last Updated: May 2026_
