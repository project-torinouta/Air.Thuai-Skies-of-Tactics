# Copyright 2026 AshGrey <ashgrey.huaier@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in the
# Software without restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the
# following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Spearhead — reverse-engineered from Saiblo replay 8513422 (Blue team).

Pattern (derived from replay):
  1. **One scout** rushes aggressively toward the enemy to spot and engage.
  2. **Two anchors** hold position at the formation and provide covering fire.
  3. **All pieces focus fire** on the same target (lowest HP in range).
  4. **Scout retreats** to the anchors after initial engagement.
  5. **Final phase**: all 3 pieces cluster and shoot from range 9.

The scout is determined dynamically each turn: it is the friendly piece
closest to the enemy centroid.  This naturally handles retreat — as the
scout backs off, another piece becomes the scout.
"""

from typing import Callable, List, Optional, Tuple

from env import Environment, InitGameMessage
from strategies._utils import allocate_init_positions, calculate_distance
from strategy_utils import get_attackable_targets, get_legal_moves
from utils import ActionSet, AttackContext, PieceArg, Point

# ---------------------------------------------------------------------------
# Initial placement
# ---------------------------------------------------------------------------

def get_spearhead_init_strategy() -> Callable[..., List[PieceArg]]:
    """Standard STR 29 / DEX 1 / INT 0 sniper init."""
    def strategy(init_message: InitGameMessage) -> List[PieceArg]:
        board = init_message.board
        pid = init_message.id
        if pid == 1:
            order = [
                (x, y) for y in range(5, 0, -1)
                for x in range(2, board.width - 2)
            ]
        else:
            order = [
                (x, y) for y in range(board.height - 6, board.height)
                for x in range(board.width - 3, 2, -1)
            ]
        positions = allocate_init_positions(
            board, pid, init_message.piece_cnt, order,
        )
        piece_args = []
        for pos in positions:
            arg = PieceArg()
            arg.strength = 29
            arg.dexterity = 1
            arg.intelligence = 0
            arg.equip = Point(3, 3)
            arg.pos = pos
            piece_args.append(arg)
        return piece_args
    return strategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enemies(env: Environment, team: int) -> list:
    return [p for p in env.action_queue if p.is_alive and p.team != team]


def _friends(env: Environment, team: int) -> list:
    return [p for p in env.action_queue if p.is_alive and p.team == team]


def _centroid(pieces: list) -> Tuple[float, float]:
    if not pieces:
        return (0.0, 0.0)
    cx = sum(p.position.x for p in pieces) / len(pieces)
    cy = sum(p.position.y for p in pieces) / len(pieces)
    return (cx, cy)


def _focus_target(env: Environment, team: int) -> Optional[object]:
    """Enemy with lowest HP among those in range of any friendly piece."""
    friends = _friends(env, team)
    enemies = _enemies(env, team)
    best = None
    for e in enemies:
        in_range = any(
            abs(f.position.x - e.position.x) + abs(f.position.y - e.position.y) <= f.attack_range
            for f in friends
        )
        if in_range:
            if best is None or e.health < best.health:
                best = e
    return best


def _nearest_enemy(piece: object, enemies: list) -> Optional[object]:
    if not enemies:
        return None
    return min(
        enemies,
        key=lambda e: calculate_distance(piece.position, e.position),
    )


# ---------------------------------------------------------------------------
# Action strategy
# ---------------------------------------------------------------------------

def get_spearhead_action_strategy() -> Callable[..., ActionSet]:
    """Spearhead strategy: scout + anchors + focus fire."""
    def strategy(env: Environment) -> ActionSet:
        team = env.current_piece.team
        current = env.current_piece
        pid = current.id

        friends = _friends(env, team)
        enemies = _enemies(env, team)
        if not enemies:
            return ActionSet()

        # Focus target: lowest HP enemy in range of ANY friend
        focus = _focus_target(env, team)
        if focus is None:
            # No enemy in range — use nearest enemy overall
            focus = _nearest_enemy(current, enemies)
        if focus is None:
            return ActionSet()

        # Determine who the scout is: the friendly piece closest to the enemy centroid
        their_cx, their_cy = _centroid(enemies)
        scout_id = None
        if len(friends) > 1:
            scout_id = min(
                friends,
                key=lambda f: abs(f.position.x - their_cx) + abs(f.position.y - their_cy),
            ).id

        is_scout = (pid == scout_id)

        # Get legal moves and attackable targets
        all_moves = get_legal_moves(env)
        attackable = get_attackable_targets(env)
        if not all_moves and not attackable:
            act = ActionSet()
            act.move = False
            act.attack = False
            act.spell = False
            return act

        # ---- 1. Can we attack the focus target? ----
        can_attack_focus = False
        for at in attackable:
            if at.id == focus.id:
                can_attack_focus = True
                break

        # ---- 2. Decision logic ----
        chosen_move = None
        chosen_attack = focus if can_attack_focus else None

        if is_scout:
            # **Scout behaviour** — advance toward focus, then retreat when close
            if can_attack_focus:
                # In range — consider retreating toward team centroid
                our_cx, our_cy = _centroid(friends)
                retreat_moves = [
                    m for m in all_moves
                    if abs(m.x - our_cx) + abs(m.y - our_cy)
                    < abs(current.position.x - our_cx) + abs(current.position.y - our_cy)
                ]
                if retreat_moves:
                    # Pick retreat move closest to centroid
                    chosen_move = min(
                        retreat_moves,
                        key=lambda m: abs(m.x - our_cx) + abs(m.y - our_cy),
                    )
                else:
                    # Stay put
                    chosen_move = None
            else:
                # Advance toward focus target
                chosen_move = min(
                    all_moves,
                    key=lambda m: calculate_distance(m, focus.position),
                )
        else:
            # **Anchor behaviour** — hold formation, fire from range
            if can_attack_focus:
                # In range — stay put or minimally adjust
                our_cx, our_cy = _centroid(friends)
                nearby = [
                    m for m in all_moves
                    if abs(m.x - our_cx) + abs(m.y - our_cy) <= 2.0
                ]
                # Can we attack while moving?
                moves_with_attack = []
                for m in nearby:
                    d = abs(m.x - focus.position.x) + abs(m.y - focus.position.y)
                    if d <= current.attack_range:
                        moves_with_attack.append(m)
                if moves_with_attack:
                    chosen_move = None  # shoot from current position
                    chosen_attack = focus
                else:
                    chosen_move = None
                    chosen_attack = focus
            else:
                # Not in range — advance slowly, stay near centroid
                our_cx, our_cy = _centroid(friends)
                # Prefer moves that stay near centroid while advancing toward focus
                scored = []
                for m in all_moves:
                    d_enemy = calculate_distance(m, focus.position)
                    d_centroid = abs(m.x - our_cx) + abs(m.y - our_cy)
                    scored.append((m, d_enemy + d_centroid * 2.0))
                scored.sort(key=lambda x: x[1])
                chosen_move = scored[0][0] if scored else None

        # ---- 3. Check if we can attack from the chosen move position ----
        if chosen_move is not None:
            mp = chosen_move
            # Re-evaluate attack from new position
            best_atk = None
            for e in enemies:
                d = abs(mp.x - e.position.x) + abs(mp.y - e.position.y)
                if d <= current.attack_range:
                    if best_atk is None or e.health < best_atk.health:
                        best_atk = e
            chosen_attack = best_atk

        # ---- 4. Build ActionSet ----
        act = ActionSet()
        if chosen_move is not None:
            act.move = True
            act.move_target = chosen_move
        else:
            act.move = False
        if chosen_attack is not None:
            act.attack = True
            act.attack_context = AttackContext()
            act.attack_context.attacker = current
            act.attack_context.target = chosen_attack
        else:
            # Check for any attackable target as fallback
            if attackable:
                best = min(attackable, key=lambda e: e.health)
                act.attack = True
                act.attack_context = AttackContext()
                act.attack_context.attacker = current
                act.attack_context.target = best
            else:
                act.attack = False
        act.spell = False
        return act

    return strategy
