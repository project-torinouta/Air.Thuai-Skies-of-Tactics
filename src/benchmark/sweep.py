"""Attribute sweep — benchmark win rate across the STR/DEX/INT space.

Generates a heatmap showing how different attribute allocations (STR, DEX, INT)
perform against the standard sniper (STR 29/DEX 1/INT 0, bow + heavy armour).
All contestants use the same action strategy (sniper's advance-and-attack)
and equipment (bow + heavy armour), isolating the effect of attributes alone.
"""

import random
import sys
from typing import Callable, List, Optional

from env import InitGameMessage
from strategies._utils import allocate_init_positions
from strategies.sniper import get_sniper_action_strategy
from utils import PieceArg, Point

from benchmark.runner import run_single_game


# STR range: 22-30 (below 22 loses the 3rd AP, above 30 is impossible)
_STR_RANGE = list(range(22, 31))
# INT range: 0-8 (higher is pointless — 0 spell slots, just wastes stats)
_INT_RANGE = list(range(0, 9))


def _make_sweep_init(strength: int, dexterity: int, intelligence: int) -> Callable[..., List[PieceArg]]:
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
) -> None:
    """Benchmark every (STR, INT) combination and save a heatmap.

    STR varies 22-30, INT varies 0-8 (with STR + INT <= 30 so DEX >= 0).
    Each cell plays ``games_per_cell`` games vs the standard sniper
    (STR 29/DEX 1/INT 0). The resulting win-rate heatmap is saved to
    ``output`` (PNG/SVG, inferred from extension).

    :param output: Output file path (.png or .svg).
    :type output: str
    :param games_per_cell: Games per attribute cell. Defaults to 8.
    :type games_per_cell: int
    :param max_rounds: Max in-game rounds. Defaults to 100.
    :type max_rounds: int
    :param board_files: Board file paths. Defaults to ``["./BoardCase/case1.txt"]``.
    :type board_files: Optional[List[str]]
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    from matplotlib.colors import ListedColormap

    if board_files is None:
        board_files = ["./BoardCase/case1.txt"]

    rows = len(_STR_RANGE)
    cols = len(_INT_RANGE)
    win_rate = np.full((rows, cols), np.nan)
    valid_cells = 0

    opponent = (
        _make_sweep_init(29, 1, 0),
        get_sniper_action_strategy(),
    )

    print(f"Attribute sweep: {rows}x{cols} grid, {games_per_cell} games each")
    print(f"  STR range: {_STR_RANGE[0]}-{_STR_RANGE[-1]}")
    print(f"  INT range: {_INT_RANGE[0]}-{_INT_RANGE[-1]}")
    print()

    for si, str_val in enumerate(_STR_RANGE):
        for ii, int_val in enumerate(_INT_RANGE):
            dex_val = 30 - str_val - int_val
            if dex_val < 0:
                continue  # invalid allocation
            valid_cells += 1

            candidate = (
                _make_sweep_init(str_val, dex_val, int_val),
                get_sniper_action_strategy(),
            )

            wins = 0
            sys.stdout.write(f"\r  STR {str_val:2d} INT {int_val:2d} DEX {dex_val:2d}  ")
            sys.stdout.flush()
            for _ in range(games_per_cell):
                board = random.choice(board_files)
                gr = run_single_game(board, candidate, opponent, max_rounds)
                if gr.result == 1:
                    wins += 1
                sys.stdout.write(".")
                sys.stdout.flush()

            win_rate[si, ii] = wins / games_per_cell * 100

    print(f"\n\n{valid_cells} valid cells benchmarked.")

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(10, 7))

    # Mask invalid cells
    mask = np.isnan(win_rate)
    cmap = plt.colormaps["Blues"]

    im = ax.imshow(win_rate, cmap=cmap, vmin=0, vmax=100, aspect="auto",
                   origin="lower", interpolation="nearest")

    # Overlay invalid cells in white
    if mask.any():
        overlay = np.full_like(win_rate, 0.0, dtype=float)
        overlay_masked = np.ma.masked_where(~mask, overlay)
        ax.imshow(overlay_masked, cmap=ListedColormap(["white"]),
                  aspect="auto", origin="lower", interpolation="nearest")

    # Annotate each cell
    for si in range(rows):
        for ii in range(cols):
            if not mask[si, ii]:
                val = win_rate[si, ii]
                ax.text(ii, si, f"{val:.0f}%", ha="center", va="center",
                        fontsize=8, fontweight="bold",
                        color="white" if val > 60 else "black")

    ax.set_xticks(range(cols))
    ax.set_xticklabels([str(i) for i in _INT_RANGE])
    ax.set_xlabel("Intelligence", fontsize=11)

    ax.set_yticks(range(rows))
    ax.set_yticklabels([str(s) for s in _STR_RANGE])
    ax.set_ylabel("Strength", fontsize=11)

    # Add DEX annotation (top axis showing implied DEX)
    dex_labels = []
    for si in range(rows):
        str_val = _STR_RANGE[si]
        max_int_in_row = max(ii for ii in range(cols)
                             if 30 - str_val - _INT_RANGE[ii] >= 0)
        dex_at_max_int = 30 - str_val - _INT_RANGE[max_int_in_row]
        dex_labels.append(f"DEX={dex_at_max_int}")
    ax2 = ax.secondary_yaxis("right")
    ax2.set_yticks(range(rows))
    ax2.set_yticklabels(dex_labels, fontsize=7)

    cbar = fig.colorbar(im, ax=ax, label="Win Rate vs Sniper (%)")
    ax.set_title(
        f"Win Rate by Attribute Allocation\n"
        f"({games_per_cell} games per cell, bow + heavy armour, sniper action strategy)",
        fontsize=11,
    )

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"Sweep chart saved to {output}")
