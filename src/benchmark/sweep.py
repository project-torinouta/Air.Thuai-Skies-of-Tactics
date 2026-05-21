"""Attribute sweep — benchmark win rate across the STR/DEX/INT space.

Generates a heatmap showing how different attribute allocations (STR, DEX, INT)
perform against the standard sniper (STR 29/DEX 1/INT 0, bow + heavy armour).
All contestants use the same action strategy (sniper's advance-and-attack)
and equipment (bow + heavy armour), isolating the effect of attributes alone.

Two sweep modes:
- ``str-int``: STR on y-axis, INT on x-axis, DEX implied as 30-STR-INT
- ``str-dex``: STR on y-axis, DEX on x-axis, INT implied as 30-STR-DEX
"""

import random
import sys
from typing import Callable, List, Optional

import numpy as np

from env import InitGameMessage
from strategies._utils import allocate_init_positions
from strategies.sniper import get_sniper_action_strategy
from utils import PieceArg, Point

from benchmark.runner import run_single_game


# STR range: 22-30 (below 22 loses the 3rd AP, above 30 is impossible)
_STR_RANGE = list(range(22, 31))
# INT range: 0-8 (higher is pointless — 0 spell slots, just wastes stats)
_INT_RANGE = list(range(0, 9))
# DEX range: same as INT for symmetry
_DEX_RANGE = list(range(0, 9))


def _make_sweep_init(
    strength: int, dexterity: int, intelligence: int,
) -> Callable[..., List[PieceArg]]:
    """Create an init strategy with the given attribute allocation.

    Equipment is fixed: bow (3) + heavy armour (3).

    :param strength: STR attribute value.
    :type strength: int
    :param dexterity: DEX attribute value.
    :type dexterity: int
    :param intelligence: INT attribute value.
    :type intelligence: int
    :returns: An init strategy callable.
    :rtype: Callable
    """
    def strategy(init_message: InitGameMessage) -> List[PieceArg]:
        board = init_message.board
        pid = init_message.id
        if pid == 1:
            order = [
                (x, y)
                for y in range(5, 0, -1)
                for x in range(2, board.width - 2)
            ]
        else:
            order = [
                (x, y)
                for y in range(board.height - 6, board.height)
                for x in range(board.width - 3, 2, -1)
            ]
        positions = allocate_init_positions(board, pid, init_message.piece_cnt, order)
        piece_args: List[PieceArg] = []
        for pos in positions:
            arg = PieceArg()
            arg.strength = strength
            arg.dexterity = dexterity
            arg.intelligence = intelligence
            arg.equip = Point(3, 3)
            arg.pos = pos
            piece_args.append(arg)
        return piece_args

    return strategy


def run_sweep(
    output: str,
    games_per_cell: int = 8,
    max_rounds: int = 100,
    board_files: Optional[List[str]] = None,
    sweep_type: str = "str-int",
) -> None:
    """Benchmark every (STR, second_attr) combination and save a heatmap.

    In ``str-int`` mode, second axis is INT (DEX implied).
    In ``str-dex`` mode, second axis is DEX (INT implied).

    Each cell plays ``games_per_cell`` games vs the standard sniper
    (STR 29/DEX 1/INT 0). The resulting win-rate heatmap is saved to
    ``output`` (PNG/SVG, inferred from extension).

    :param output: Output file path (.png or .svg).
    :type output: str
    :param games_per_cell: Games per attribute cell. Defaults to 8.
    :type games_per_cell: int
    :param max_rounds: Max in-game rounds. Defaults to 100.
    :type max_rounds: int
    :param board_files: Board file paths.
    :type board_files: Optional[List[str]]
    :param sweep_type: ``"str-int"`` or ``"str-dex"``. Defaults to ``"str-int"``.
    :type sweep_type: str
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415
    from matplotlib.colors import ListedColormap

    if board_files is None:
        board_files = ["./BoardCase/case1.txt"]

    if sweep_type == "str-dex":
        second_range = _DEX_RANGE
        second_label = "Dexterity"
        implied_label = "INT"
    else:
        second_range = _INT_RANGE
        second_label = "Intelligence"
        implied_label = "DEX"

    rows = len(_STR_RANGE)
    cols = len(second_range)
    win_rate = np.full((rows, cols), np.nan)
    valid_cells = 0

    opponent = (
        _make_sweep_init(29, 1, 0),
        get_sniper_action_strategy(),
    )

    print(f"Attribute sweep ({sweep_type}): {rows}x{cols} grid, {games_per_cell} games each")
    print(f"  STR range: {_STR_RANGE[0]}-{_STR_RANGE[-1]}")
    print(f"  {second_label} range: {second_range[0]}-{second_range[-1]}")
    print()

    for si, str_val in enumerate(_STR_RANGE):
        for ci, second_val in enumerate(second_range):
            if sweep_type == "str-dex":
                dex_val = second_val
                int_val = 30 - str_val - dex_val
            else:
                int_val = second_val
                dex_val = 30 - str_val - int_val

            if dex_val < 0 or int_val < 0:
                continue
            valid_cells += 1

            candidate = (
                _make_sweep_init(str_val, dex_val, int_val),
                get_sniper_action_strategy(),
            )

            wins = 0
            sys.stdout.write(
                f"\r  STR {str_val:2d} {second_label[:3]} {second_val:2d}"
                f" {implied_label} {30 - str_val - second_val:2d}  "
            )
            sys.stdout.flush()
            for _ in range(games_per_cell):
                board = random.choice(board_files)
                gr = run_single_game(board, candidate, opponent, max_rounds)
                if gr.result == 1:
                    wins += 1
                sys.stdout.write(".")
                sys.stdout.flush()

            win_rate[si, ci] = wins / games_per_cell * 100

    print(f"\n\n{valid_cells} valid cells benchmarked.")

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(10, 7))

    mask = np.isnan(win_rate)
    cmap = plt.colormaps["Blues"]

    im = ax.imshow(
        win_rate, cmap=cmap, vmin=0, vmax=100,
        aspect="auto", origin="lower", interpolation="nearest",
    )

    if mask.any():
        overlay = np.full_like(win_rate, 0.0, dtype=float)
        overlay_masked = np.ma.masked_where(~mask, overlay)
        ax.imshow(
            overlay_masked, cmap=ListedColormap(["white"]),
            aspect="auto", origin="lower", interpolation="nearest",
        )

    for si in range(rows):
        for ci in range(cols):
            if not mask[si, ci]:
                val = win_rate[si, ci]
                ax.text(
                    ci, si, f"{val:.0f}%",
                    ha="center", va="center",
                    fontsize=8, fontweight="bold",
                    color="white" if val > 60 else "black",
                )

    ax.set_xticks(range(cols))
    ax.set_xticklabels([str(v) for v in second_range])
    ax.set_xlabel(second_label, fontsize=11)

    ax.set_yticks(range(rows))
    ax.set_yticklabels([str(s) for s in _STR_RANGE])
    ax.set_ylabel("Strength", fontsize=11)

    # Right axis: show implied third attribute
    implied_labels = []
    for si in range(rows):
        str_val = _STR_RANGE[si]
        max_c = max(
            ci for ci in range(cols)
            if 30 - str_val - second_range[ci] >= 0
        )
        implied_val = 30 - str_val - second_range[max_c]
        implied_labels.append(f"{implied_label}={implied_val}")
    ax2 = ax.secondary_yaxis("right")
    ax2.set_yticks(range(rows))
    ax2.set_yticklabels(implied_labels, fontsize=7)

    cbar = fig.colorbar(im, ax=ax, label="Win Rate vs Sniper (%)")
    ax.set_title(
        f"Win Rate by Attribute Allocation ({sweep_type})\n"
        f"({games_per_cell} games per cell, bow + heavy armour, sniper action strategy)",
        fontsize=11,
    )

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"Sweep chart saved to {output}")
