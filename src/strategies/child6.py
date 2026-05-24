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

"""Child6 — cluster formation with centroid-based rally.

Core rules:
  1. All 3 pieces stay within 2.5 tiles of the team centroid.
  2. If >2.5 from centroid → rally back.
  3. ALL pieces attack the same lowest-HP target (focus fire).
  4. Advance together, never alone.
"""

from typing import Callable, List, Tuple
from collections import deque
from itertools import combinations

from env import Environment, InitGameMessage, Board
from strategies._utils import allocate_init_positions, calculate_distance
from utils import ActionSet, AttackContext, PieceArg, Point

_CLUSTER_RADIUS: float = 3.0


def get_child6_init_strategy() -> Callable[..., List[PieceArg]]:
    """Tight-cluster placement: pieces adjacent, near the centre."""

    def strategy(init_message: InitGameMessage) -> List[PieceArg]:
        board = init_message.board
        pid = init_message.id

        def find_best_clusters(cx: int, cy: int) -> List[Tuple[int, int]]:
            queue = deque([(cx, cy)])
            visited = set([(cx, cy)])
            valid_spots: List[Tuple[int, int]] = []

            def is_free(x: int, y: int) -> bool:
                return board.is_within_bounds(Point(x, y)) # and
                    # not board.is_occupied(Point(x, y))
                    # [function `is_occupied` in @src/env.py is not used in any client logic]

            if is_free(cx, cy):
                valid_spots.append((cx, cy))

            while queue and len(valid_spots) < 40:
                current_x, current_y = queue.popleft()
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = current_x + dx, current_y + dy
                    if (nx, ny) not in visited and board.is_within_bounds(Point(nx, ny)):
                        visited.add((nx, ny))
                        queue.append((nx, ny))
                        if is_free(nx, ny):
                            valid_spots.append((nx, ny))

            if len(valid_spots) < init_message.piece_cnt:
                return valid_spots

            best_combination = []
            min_total_dist = float("inf")

            for combo in combinations(valid_spots, init_message.piece_cnt):
                # combinations function example usage:
                #
                # comb = combinations([1, 2, 3], 2)
                #
                # for i in comb:
                #     print(i)
                #
                # (1, 2)
                # (1, 3)
                # (2, 3)
                #
                # So here we use init_message.piece_cnt to generate valid three
                # pieces combination (not permutation because the order doesn't
                # matter)
                internal_dist = 0
                center_dist = 0

                for i in range(len(combo)):
                    center_dist += abs(combo[i][0] - cx) + abs(combo[i][1] - cy)
                    for j in range(i + 1, len(combo)):
                        internal_dist += abs(combo[i][0] - combo[j][0]) + abs(combo[i][1] - combo[j][1])

                # The rank of internal_dist should be higher because we want to
                # first satisfy the close to each other
                score = internal_dist * 10 + center_dist * 1

                if score < min_total_dist:
                    min_total_dist = score
                    best_combination = list(combo)

            return best_combination

        cx = board.width // 2
        cy = board.height // 2 - 1 if pid == 1 else board.height // 2 + 1

        order: List[Tuple[int, int]] = [
            (cx, cy),
            (cx + 1, cy),
            (cx - 1, cy),
            (cx, cy + 1),
            (cx, cy - 1),
            (cx + 2, cy),
            (cx - 2, cy),
        ]

        order += find_best_clusters(cx, cy)

        positions = allocate_init_positions(
            board, pid, init_message.piece_cnt, order,
        )
        piece_args: List[PieceArg] = []
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


def get_child6_action_strategy() -> Callable[..., ActionSet]:
    """Score-based advance with centroid safety brake."""
    def strategy(env: Environment) -> ActionSet:
        action = ActionSet()
        current = env.current_piece

        if current is None or not current.is_alive:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        enemies = [
            p for p in env.action_queue
            if p.team != current.team and p.is_alive
        ]
        if not enemies:
            action.move = False
            action.attack = False
            action.spell = False
            return action

        friends = [
            p for p in env.action_queue
            if p.team == current.team and p.is_alive
        ]
        our_cx = float(sum(f.position.x for f in friends)) / len(friends)
        our_cy = float(sum(f.position.y for f in friends)) / len(friends)

        lowest_hp_target = min(enemies, key=lambda e: e.health)

        from strategy_utils import get_legal_moves
        legal_moves = get_legal_moves(env)
        if not legal_moves:
            # [if current piece cannot reach anywhere it should first try to stay
            # at the same position and attack enemies]
           legal_moves = [current.position]

        # Distance to nearest friendly piece (not counting self)
        friends_other = [f for f in friends if f.id != current.id]

        def d(pos, tx, ty) -> float:
            return abs(pos.x - tx) + abs(pos.y - ty)

        def is_L_shape(p1: Point, p2: Point, p3: Point) -> bool:
            d12 = abs(p1.x - p2.x) + abs(p1.y - p2.y)
            d23 = abs(p2.x - p3.x) + abs(p2.y - p3.y)
            d13 = abs(p1.x - p3.x) + abs(p1.y - p3.y)

            return (d12 + d23 + d13) <= 4

        def safe_cluster(m: Point) -> bool:
            if len(friends_other) < 2:
                return not friends_other or min(
                    calculate_distance(m, f.position) for f in friends_other
                ) <= 1
            return is_L_shape(
                m,
                friends_other[0].position,
                friends_other[1].position
            )

        safe_moves = [m for m in legal_moves if safe_cluster(m)]

        if not safe_moves:
            # when there is no safe moves
            safe_moves = legal_moves

        closest_to_hp_target = min(
            safe_moves,
            key=lambda m: d(m, lowest_hp_target.position.x, lowest_hp_target.position.y)
        )
        distance_to_hp_target = d(
            closest_to_hp_target,
            lowest_hp_target.position.x,
            lowest_hp_target.position.y
        )

        final_target = None
        if distance_to_hp_target <= current.attack_range:
            best = max(
                safe_moves,
                key=lambda m: -d(m, lowest_hp_target.position.x, lowest_hp_target.position.y)
                    - d(m, our_cx, our_cy) * 0.3
            )
            final_target = lowest_hp_target
        else:
            nearest_enemy = min(
                enemies,
                key=lambda e: d(current.position, e.position.x, e.position.y)
            )
            best = max(
                safe_moves,
                key=lambda m: -d(m, nearest_enemy.position.x, nearest_enemy.position.y)
                    - d(m, our_cx, our_cy) * 0.3
            )
            final_target = nearest_enemy

        action.move = (best.x != current.position.x or best.y != current.position.y)
        if action.move:
            action.move_target = best

        pos = action.move_target if action.move else current.position
        if d(pos, final_target.position.x, final_target.position.y) <= current.attack_range:
            action.attack = True
            action.attack_context = AttackContext()
            action.attack_context.attacker = current
            action.attack_context.target = final_target
        else:
            action.attack = False

        action.spell = False

        return action
    return strategy
