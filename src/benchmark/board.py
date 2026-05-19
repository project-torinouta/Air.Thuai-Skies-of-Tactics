"""Board discovery and random board generation."""

import glob
import os
import random
from typing import List


_GENERATED_BOARD_DIR: str = "BoardCase"


def _make_grid(
    rows: int,
    cols: int,
    obstacle_density: float,
    border: int,
) -> List[List[int]]:
    """Generate a random grid of cell states for a board.

    Produces a ``rows x cols`` grid where most cells are walkable (1) and
    some are blocked (-1).  Guarantees at least 15 walkable cells on each
    side of the border so that pieces can be placed.

    :param rows: Number of rows in the grid.
    :type rows: int
    :param cols: Number of columns in the grid.
    :type cols: int
    :param obstacle_density: Probability that a cell is blocked.
    :type obstacle_density: float
    :param border: The y-coordinate of the border (split between players).
    :type border: int
    :returns: A 2D list of cell states (1 = walkable, -1 = blocked).
    :rtype: List[List[int]]
    """
    grid: List[List[int]] = [
        [1 for _ in range(rows)] for _ in range(cols)
    ]

    for x in range(cols):
        for y in range(rows):
            if random.random() < obstacle_density:
                grid[x][y] = -1

    for half_border in (border, rows):
        half_start = 0 if half_border == border else border + 1
        blocked = [
            (x, y)
            for x in range(cols)
            for y in range(half_start, half_border)
            if grid[x][y] == -1
        ]
        open_cnt = cols * (half_border - half_start) - len(blocked)
        needed = max(0, 15 - open_cnt)
        for x, y in blocked[:needed]:
            grid[x][y] = 1

    return grid


def _make_height_map(rows: int, cols: int) -> List[List[int]]:
    """Generate a random height map using a simple smoothing approach.

    Heights range from 0 to 3.

    :param rows: Number of rows.
    :type rows: int
    :param cols: Number of columns.
    :type cols: int
    :returns: A 2D list of height values.
    :rtype: List[List[int]]
    """
    heights: List[List[int]] = [
        [random.randint(0, 3) for _ in range(rows)] for _ in range(cols)
    ]

    for _ in range(2):
        smoothed: List[List[int]] = [
            [0 for _ in range(rows)] for _ in range(cols)
        ]
        for x in range(cols):
            for y in range(rows):
                neighbors = [heights[x][y]]
                if x > 0:
                    neighbors.append(heights[x - 1][y])
                if x < cols - 1:
                    neighbors.append(heights[x + 1][y])
                if y > 0:
                    neighbors.append(heights[x][y - 1])
                if y < rows - 1:
                    neighbors.append(heights[x][y + 1])
                smoothed[x][y] = round(sum(neighbors) / len(neighbors))
        heights = smoothed

    return heights


def generate_random_board(
    file_path: str,
    rows: int = 20,
    cols: int = 20,
    obstacle_density: float = 0.1,
) -> None:
    """Generate a random board file at the given path.

    :param file_path: Output path for the board file.
    :type file_path: str
    :param rows: Number of rows. Defaults to 20.
    :type rows: int
    :param cols: Number of columns. Defaults to 20.
    :type cols: int
    :param obstacle_density: Probability a cell is blocked (0.0-1.0).
        Defaults to 0.1.
    :type obstacle_density: float
    """
    border = rows // 2
    grid = _make_grid(rows, cols, obstacle_density, border)
    heights = _make_height_map(rows, cols)

    with open(file_path, "w") as f:
        f.write(f"{cols} {rows}\n\n")
        for y in range(rows):
            f.write(", ".join(str(grid[x][y]) for x in range(cols)) + "\n")
        f.write("\n")
        for y in range(rows):
            f.write(", ".join(str(heights[x][y]) for x in range(cols)) + "\n")


def resolve_boards(args: object) -> List[str]:
    """Build the list of board file paths based on CLI arguments.

    Order of precedence:
    1. ``--board`` pointing to a single file.
    2. ``--board`` pointing to a directory (scans for ``*.txt``).
    3. ``--board-dir`` (scans for ``*.txt`` in that directory).
    4. ``--generate-boards N`` (creates N random boards).
    5. Default: ``./BoardCase/case1.txt``.

    :param args: Parsed command-line arguments.
    :type args: argparse.Namespace
    :returns: A list of board file paths.
    :rtype: List[str]
    """
    boards: List[str] = []

    if args.board is not None:
        if os.path.isdir(args.board):
            boards = sorted(glob.glob(os.path.join(args.board, "*.txt")))
            if not boards:
                print(
                    f"Warning: no .txt files found in {args.board}, "
                    f"using default board"
                )
        else:
            boards = [args.board]
    elif args.board_dir is not None:
        boards = sorted(glob.glob(os.path.join(args.board_dir, "*.txt")))
        if not boards:
            print(
                f"Warning: no .txt files found in {args.board_dir}, "
                f"using default board"
            )
    elif args.generate_boards > 0:
        os.makedirs(_GENERATED_BOARD_DIR, exist_ok=True)
        for i in range(args.generate_boards):
            path = os.path.join(_GENERATED_BOARD_DIR, f"generated_{i}.txt")
            generate_random_board(
                path,
                rows=args.board_rows,
                cols=args.board_cols,
                obstacle_density=args.obstacle_density,
            )
            boards.append(path)
        print(
            f"Generated {args.generate_boards} random board files "
            f"({args.board_cols}x{args.board_rows})"
        )
        print(f"  Density: {args.obstacle_density}")
    else:
        default = "./BoardCase/case1.txt"
        if os.path.exists(default):
            boards = [default]

    if not boards:
        print("Warning: no board files found, using default ./BoardCase/case1.txt")
        boards = ["./BoardCase/case1.txt"]

    return boards
