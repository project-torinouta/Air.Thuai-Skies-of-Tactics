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

"""Shared utilities for strategy implementations."""

from typing import List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from env import Board

from utils import Point


def allocate_init_positions(
    board: "Board",
    player_id: int,
    piece_cnt: int,
    preferred_order: List[Tuple[int, int]],
) -> List[Point]:
    """Pick distinct walkable cells on the player's side of the board.

    Tries the preferred positions first, then falls back to scanning all
    cells in scan-line order.

    :param board: The game board.
    :type board: Board
    :param player_id: The player ID (1 or 2).
    :type player_id: int
    :param piece_cnt: Number of pieces to place.
    :type piece_cnt: int
    :param preferred_order: List of (x, y) tuples to try first.
    :type preferred_order: List[Tuple[int, int]]
    :returns: A list of placed positions.
    :rtype: List[Point]
    :raises RuntimeError: If no free cell exists on the player's side.
    """
    occupied: Set[Tuple[int, int]] = set()
    out: List[Point] = []
    bdr = board.boarder

    def cell_ok(x: int, y: int) -> bool:
        if (x, y) in occupied:
            return False
        if not board.is_within_bounds(Point(x, y)):
            return False
        if board.grid[x][y].state != 1:
            return False
        if player_id == 1:
            return y < bdr
        return y > bdr

    for _ in range(piece_cnt):
        pos: Optional[Point] = None
        for x, y in preferred_order:
            if cell_ok(x, y):
                pos = Point(x, y)
                break
        if pos is None:
            for y in range(board.height):
                for x in range(board.width):
                    if cell_ok(x, y):
                        pos = Point(x, y)
                        break
                if pos is not None:
                    break
        if pos is None:
            raise RuntimeError("No free cell in player's half for placement.")
        out.append(pos)
        occupied.add((pos.x, pos.y))
    return out


def calculate_distance(p1: Point, p2: Point) -> float:
    """Calculate the Manhattan distance between two points.

    :param p1: The first point.
    :type p1: Point
    :param p2: The second point.
    :type p2: Point
    :returns: The Manhattan distance ``|x1-x2| + |y1-y2|``.
    :rtype: float
    """
    return float(abs(p1.x - p2.x) + abs(p1.y - p2.y))
