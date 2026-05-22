"""Sweep benchmarks — attribute allocation and action-parameter heatmaps.

``run_sweep_init`` — benchmark win rate across the STR/DEX/INT space.
  All contestants use the same action strategy (sniper's advance-and-attack)
  and equipment (bow + heavy armour).

``run_sweep_action`` — benchmark win rate across tactical parameters.
  All contestants use the same fixed build (STR 29/DEX 1/INT 0).
  Varies the action-strategy knobs from :mod:`strategies.factory`.

Two init-sweep modes:
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


def run_sweep_init(
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
            for i in range(games_per_cell):
                board = random.choice(board_files)
                gr = run_single_game(board, candidate, opponent, max_rounds)
                if gr.result == 1:
                    wins += 1
                sys.stdout.write(f"\r  {i + 1}/{games_per_cell}")
                sys.stdout.flush()

            win_rate[si, ci] = wins / games_per_cell * 100

    print(f"\n\n{valid_cells} valid cells benchmarked.")

    #  Plot
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


# Action-parameter sweep

# Parameter ranges for action sweeps
_ACTION_PARAM_RANGES = {
    "target_mode": ["closest", "lowest_hp", "highest_hp"],
    "formation_spacing": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
    "advance_mode": ["always", "edge"],
    "retreat_hp": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90],
}

_ACTION_PARAM_LABELS = {
    "target_mode": "Target",
    "formation_spacing": "Spacing",
    "advance_mode": "Advance",
    "retreat_hp": "Retreat HP",
}


def run_sweep_action(
    output: str,
    param_x: str = "target_mode",
    param_y: str = "formation_spacing",
    games_per_cell: int = 8,
    max_rounds: int = 100,
    board_files: Optional[List[str]] = None,
) -> None:
    """Benchmark every (param_x, param_y) combination and save a heatmap.

    Each cell plays ``games_per_cell`` games vs the standard sniper
    (STR 29/DEX 1/INT 0, closest-target, always-advance).
    The resulting win-rate heatmap is saved to ``output``.

    :param output: Output file path (.png or .svg).
    :type output: str
    :param param_x: Name of the parameter for the x-axis.
    :type param_x: str
    :param param_y: Name of the parameter for the y-axis.
    :type param_y: str
    :param games_per_cell: Games per parameter cell. Defaults to 8.
    :type games_per_cell: int
    :param max_rounds: Max in-game rounds. Defaults to 100.
    :type max_rounds: int
    :param board_files: Board file paths.
    :type board_files: Optional[List[str]]
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415

    from strategies.factory import make_strategy
    from strategies.sniper import get_sniper_action_strategy

    if board_files is None:
        board_files = ["./BoardCase/case1.txt"]

    x_values = _ACTION_PARAM_RANGES[param_x]
    y_values = _ACTION_PARAM_RANGES[param_y]
    x_label = _ACTION_PARAM_LABELS[param_x]
    y_label = _ACTION_PARAM_LABELS[param_y]

    rows = len(y_values)
    cols = len(x_values)
    win_rate = np.full((rows, cols), np.nan)

    opponent = (
        _make_sweep_init(29, 1, 0),
        get_sniper_action_strategy(),
    )

    print(
        f"Action sweep ({param_y} vs {param_x}): "
        f"{rows}x{cols} grid, {games_per_cell} games each"
    )
    print(f"  {y_label} range: {y_values}")
    print(f"  {x_label} range: {x_values}")
    print()

    for ri, y_val in enumerate(y_values):
        for ci, x_val in enumerate(x_values):
            kwargs = {param_y: y_val, param_x: x_val}
            candidate = make_strategy(**kwargs)

            wins = 0
            sys.stdout.write(
                f"\r  {y_label}={y_val}  {x_label}={x_val}  "
            )
            sys.stdout.flush()
            for i in range(games_per_cell):
                board = random.choice(board_files)
                gr = run_single_game(board, candidate, opponent, max_rounds)
                if gr.result == 1:
                    wins += 1
                sys.stdout.write(f"\r  {i + 1}/{games_per_cell}")
                sys.stdout.flush()

            win_rate[ri, ci] = wins / games_per_cell * 100

    print(f"\n\nAll cells benchmarked.")

    # Plot
    fig, ax = plt.subplots(figsize=(10, 7))

    mask = np.isnan(win_rate)
    cmap = plt.colormaps["Blues"]

    im = ax.imshow(
        win_rate, cmap=cmap, vmin=0, vmax=100,
        aspect="auto", origin="lower", interpolation="nearest",
    )

    for ri in range(rows):
        for ci in range(cols):
            if not mask[ri, ci]:
                val = win_rate[ri, ci]
                ax.text(
                    ci, ri, f"{val:.0f}%",
                    ha="center", va="center",
                    fontsize=8, fontweight="bold",
                    color="white" if val > 60 else "black",
                )

    ax.set_xticks(range(cols))
    ax.set_xticklabels([str(v) for v in x_values], fontsize=8)
    ax.set_xlabel(x_label, fontsize=11)

    ax.set_yticks(range(rows))
    ax.set_yticklabels([str(v) for v in y_values], fontsize=8)
    ax.set_ylabel(y_label, fontsize=11)

    cbar = fig.colorbar(im, ax=ax, label="Win Rate vs Sniper (%)")
    ax.set_title(
        f"Win Rate by Action Parameters ({param_y} vs {param_x})\n"
        f"({games_per_cell} games per cell, STR 29/DEX 1/INT 0)",
        fontsize=11,
    )

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"Action sweep chart saved to {output}")
