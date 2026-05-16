# THUAI9 Celestial Chess Game Rules

## 1. Game Overview

- Two players compete on a grid-based board.
- Each player controls 3 pieces.
- The game is turn-based.
- Each piece can move, attack, or cast spells, depending on action points and
  resource limits.
- The game ends when all pieces of one player are eliminated.

### 1.1 Two Responsibilities of the Player (AI)

- **Initialization Strategy (Deployment)**: At the start of the game, decide the
  attribute points, equipment, and starting position for each piece
  (corresponding to the Python client's initialization strategy function, which
  returns a `PieceArg` list).
- **Action Strategy (Per-Turn Decision-Making)**: When it is your turn to act,
  generate an `ActionSet` for the "currently acting piece", deciding whether to
  move, attack, or cast spells, and their corresponding targets.

### 1.2 Game Flow

The game can be understood as consisting of an **initialization phase** and a
**turn loop**:

#### Initialization Phase

- Load the board (`grid` + `height_map`).
- Both sides submit their piece initialization parameters (attribute points,
  equipment, positions), creating pieces and placing them on the board.
- Determine the action queue based on each piece's initiative value (related to
  `dexterity` and a random dice roll).

#### Turn Loop (until the game ends)

Each round determines a "currently acting piece", and the side (player/AI)
controlling it submits actions. The macro-level order is:

- **Turn Start**: Increment the round number; reset action points for all alive
  pieces (`action_points = max_action_points`).
- **Delayed Spell Advancement**: If there are delayed spells, decrease their
  remaining rounds; when they expire, trigger their effect and remove them from
  the queue.
- **Execute Action (ActionSet)**: The currently acting piece may attempt to
  move, attack, or cast spells in the same turn, provided resources allow
  (whether each action is executed depends on the action switches and whether
  sufficient resources are available).
- **Queue Rotation and Win/Loss Determination**: After the current piece acts,
  it moves to the end of the queue. If one side has no surviving pieces, the
  game ends.

> Note: Move/attack/spell are processed in a fixed order (typically **Move ->
> Attack -> Spell**), and each step checks whether sufficient action
> points/spell slots remain.
>
> "Execute Action" corresponds to the **resolution of a single `ActionSet`**: in
> one `ActionSet`, each of the three action types (move, attack, spell) is
> **executed at most once** (implemented as three sequential `if` branches in
> code). If `max_action_points` is sufficient, it is possible to complete
> "move + attack + spell" within the same `ActionSet`; otherwise, subsequent
> steps are skipped due to insufficient action points.

## 2. Board and Coordinates

- The board is a 2D integer grid, with coordinates represented as `(x, y)`.
- Each cell contains `grid` status and `height_map` height information.
- Movement must pass through traversable cells, using pathfinding algorithms to
  calculate valid paths.
- Distance is measured using Manhattan distance:
  - `distance = abs(x1 - x2) + abs(y1 - y2)`

## 3. Piece Attributes

Each piece has the following core attributes:

- `id`: Piece ID
- `team`: Team number (1 or 2)
- `position`: Current coordinates
- `height`: Current height
- `health`, `max_health`
- `strength`
- `dexterity`
- `intelligence`
- `physical_damage`
- `physical_resist`
- `attack_range`
- `movement`, `max_movement`
- `action_points`, `max_action_points`
- `spell_slots`, `max_spell_slots`
- `is_alive`
- `is_in_turn`
- `death_round`

## 4. Initialization Rules

- Initial attribute points are allocated among `strength`, `dexterity`, and
  `intelligence`.
- The total attribute points for a single piece must not exceed `30`.
- Equipment is represented by `equip = Point(weapon, armor)`:
  - `weapon` ranges from `1` to `4`
  - `armor` ranges from `1` to `3`
- Weapon 4 (Staff) must be paired with armor 1 (Light Armor).
- Starting positions must be within the board boundaries and on valid starting
  cells.

### Initialization Formulas

- `max_health = 30 + strength * 2`
- `max_movement = dexterity + 0.5 * strength + 10`
- `max_spell_slots`: Determined by intelligence thresholds (consistent with
  `client/client/env.py` and `server_python/env.py`):
  - `intelligence <= 3`: 1
  - `intelligence <= 7`: 2
  - `intelligence <= 12`: 3
  - `intelligence <= 16`: 5
  - `intelligence <= 21`: 8
  - `intelligence > 21`: 9

### Initiative / Action Order

- The turn order of pieces is determined by a random dice roll and `dexterity`:
  - `RollDice(1, 10) + dexterity`
- Higher values result in earlier action order.

## 5. Movement

- A move action consumes 1 action point.
- A single move can cover up to `movement` steps.
- The move target must be reachable, and all cells along the path must be
  traversable.
- Movement range is determined by path length, not straight-line distance.
- Both area and range determinations use Manhattan distance.

## 6. Attack

- An attack consumes 1 action point.
- A target is attackable if the Manhattan distance between the target and the
  attacker is less than or equal to `attack_range`.
- Normal attack damage rules:
  - **Non-Staff (weapon=1/2/3)**:
    `damage = attacker.physical_damage + attacker.strength`, settled against
    physical resistance (physical damage minus `physical_resist`).
  - **Staff (weapon=4)**: Deals **fixed 4 true damage**, ignoring all resistance
    (unaffected by `physical_resist`).
- Minimum damage is `0`.
- Upon death, the corresponding death status is updated.

## 7. Spells

- Casting a spell requires meeting two resource conditions:
  - At least `1` `action_point`
  - Sufficient `spell_slots` to pay the `spell_cost`
- Spell range and target area are determined using Manhattan distance.
- `range_` indicates the maximum Manhattan distance from the caster to the
  target center.
- `area_radius` indicates the Manhattan radius of effect around the target
  center.
- Some spells are delayed spells:
  - When `is_delay_spell=True`, the spell enters the `delayed_spells` queue and
    is executed later.
  - Delayed spells consume 1 action point and the corresponding `spell_cost`
    when enqueued.
- `is_locking_spell=True` indicates that the spell may lock the target or caster
  logic during execution.

### Built-in Spell List

| ID  | Name      | Effect Type | Damage Type | Base Value | Range | Area Radius | Cost | Description                    |
| --- | --------- | ----------- | ----------- | ---------- | ----- | ----------- | ---- | ------------------------------ |
| 1   | Fireball  | DAMAGE      | FIRE        | 30         | 2     | 5           | 1    | Area damage                    |
| 2   | Heal      | HEAL        | NONE        | 30         | 2     | 4           | 1    | Target or center heal          |
| 3   | Arrow Hit | DAMAGE      | PHYSICAL    | 30         | 1     | 7           | 1    | Physical damage                |
| 4   | Trap      | DAMAGE      | PHYSICAL    | 30         | 1     | 0           | 1    | Delayed effect, lasts 2 rounds |
| 5   | Teleport  | MOVE        | PHYSICAL    | 30         | 100   | 100         | 1    | Long-range teleport            |

### Available Spells by Class (per current implementation)

In the current Python implementation, `get_available_spells(piece)` filters
available spells based on the piece's `type` (Warrior/Mage/Archer), meaning
**different classes have different sets of available spells**. Using the
built-in spells above as examples:

- **Warrior**: All spells with `DamageType=PHYSICAL`, as well as `BUFF`-type
  spells (if added in the future).
  - Corresponding to current built-in spells: `Arrow Hit`, `Trap`, `Teleport`
- **Mage**: Elemental damage (`FIRE/ICE/LIGHTNING`) spells, or spells with
  effect type `DAMAGE/DEBUFF`.
  - Corresponding to current built-in spells: `Fireball`, `Arrow Hit`, `Trap`
- **Archer**: Spells named `Arrow Hit` / `Trap`, or spells with effect type
  `MOVE`.
  - Corresponding to current built-in spells: `Arrow Hit`, `Trap`, `Teleport`

> Note: The current implementation **does not have a "can only cast the same
> spell once per game" restriction**. As long as action points, spell slots, and
> target validity requirements are met, the same spell can be cast repeatedly
> across different rounds until `spell_slots` are exhausted.

## 8. Equipment Effects

### Weapons

| Weapon ID | Type        | Physical Damage | Attack Range |
| --------- | ----------- | --------------- | ------------ |
| 1         | Long Sword  | 8               | 5            |
| 2         | Short Sword | 10              | 3            |
| 3         | Bow         | 16              | 9            |
| 4         | Staff       | 0               | 12           |

### Armor

| Armor ID | Type         | Physical Resistance | Movement Adjustment |
| -------- | ------------ | ------------------- | ------------------- |
| 1        | Light Armor  | 8                   | +3                  |
| 2        | Medium Armor | 15                  | 0                   |
| 3        | Heavy Armor  | 23                  | -3                  |

- Armor directly adjusts resistance values.
- Light Armor adds 3 to base movement.
- Heavy Armor subtracts 3 from base movement.
- Staff can only be paired with Light Armor.

> During the first week of the competition, players are welcome to provide
> suggestions and feedback on game balance. If extreme imbalances are found, we
> will make timely adjustments.

## 9. Action Points and Spell Slots

- Each attack consumes 1 action point.
- Each spell cast consumes 1 action point and consumes spell slots.
  - Currently, all built-in spells have `spell_cost` of 1.
- Each move action consumes 1 action point.
- At the start of each turn, a piece receives its `max_action_points` action
  points.
- At the start of each turn, `spell_slots` are **not** automatically restored to
  `max_spell_slots` (meaning each piece can only use a limited number of spells
  throughout the entire game).

## 10. Damage, Healing, and Resistance

- `physical_damage` is determined by weapon and base attributes.
- `physical_resist` is determined by armor and spell effects.
- When taking damage, the corresponding resistance is deducted based on the
  damage type, and the remaining amount is applied to health.
- Healing effects increase health, but cannot exceed `max_health`.

## 11. Death and Victory Conditions

- A piece is alive when its `health` is greater than `0`.
- When health drops to `0` or below, the piece dies and its `death_round` status
  is updated.
- When a player has no surviving pieces, the game ends.
- The player with remaining surviving pieces wins.

---
