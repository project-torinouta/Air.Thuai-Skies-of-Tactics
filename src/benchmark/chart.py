"""Chart rendering via matplotlib.

- ``plot_win_rate_curve`` — line chart of cumulative win rate vs games played
- ``plot_head_to_head`` — heatmap matrix of pairwise win rates
- ``plot_game_length_histogram`` — violin plot of game round counts
- ``plot_first_blood_histogram`` — boxen plot of first-blood rounds
- ``plot_survivor_count`` — stacked bar chart of match decisiveness
"""

from typing import Dict, List, Tuple


_CURVE_COLORS = [
    "#2ecc71", "#e74c3c", "#3498db", "#f39c12", "#9b59b6",
    "#1abc9c", "#e67e22", "#2c3e50", "#8e44ad", "#d35400",
    "#27ae60", "#c0392b", "#16a085", "#7f8c8d",
]


def try_init_matplotlib() -> bool:
    """Import matplotlib and switch to Agg backend.

    :returns: True if matplotlib is available.
    :rtype: bool
    """
    try:
        import matplotlib  # noqa: PLC0415
        matplotlib.use("Agg")
        return True
    except ImportError:
        return False


def plot_win_rate_curve(
    series: Dict[str, List[int]],
    output: str,
    subtitle: str,
) -> None:
    """Draw a line chart of cumulative win rate vs games played.

    Each entry maps a label (strategy or matchup label) to a list of
    per-game results (0=draw, 1=side wins, 2=opponent wins).
    The win rate is plotted cumulatively — after each game the winning
    percentage so far is plotted, producing a convergence curve.

    :param series: Mapping of label → per-game results.
    :type series: Dict[str, List[int]]
    :param output: File path for the chart image.
    :type output: str
    :param subtitle: Board description or subtitle text.
    :type subtitle: str
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    _, ax = plt.subplots(figsize=(10, 6))

    for idx, (label, seq) in enumerate(series.items()):
        if not seq:
            continue
        color = _CURVE_COLORS[idx % len(_CURVE_COLORS)]
        cumulative_wins = np.cumsum(np.array([1 if r == 1 else 0 for r in seq]))
        games = np.arange(1, len(seq) + 1)
        win_rates = cumulative_wins / games * 100

        ax.plot(games, win_rates, color=color, linewidth=1.5, alpha=0.85,
                label=f"{label} ({win_rates[-1]:.1f}%)")

        ax.text(len(seq) + 0.3, win_rates[-1], f"{win_rates[-1]:.0f}%",
                fontsize=8, color=color, va="center")

    ax.axhline(y=50, color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.set_xlabel("Games Played")
    ax.set_ylabel("Cumulative Win Rate (%)")
    ax.set_title("Win Rate vs Games", fontsize=13)
    ax.set_xlim(1, None)
    ax.set_ylim(-5, 105)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, loc="best")

    if subtitle:
        ax.text(0.98, 0.02, subtitle, transform=ax.transAxes,
                fontsize=8, color="gray", ha="right", va="bottom")

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"Chart saved to {output}")


def aggregate_strategy_series(
    all_series: Dict[Tuple[str, str], List[int]],
    strategy_names: List[str],
) -> Dict[str, List[int]]:
    """Aggregate per-game results across all matchups for each strategy.

    For each strategy, interleaves games it played as P1 and as P2,
    recording 1 if it won that game and 0 otherwise.

    :param all_series: Mapping of (p1, p2) to list of game results.
    :type all_series: Dict[Tuple[str, str], List[int]]
    :param strategy_names: Ordered list of strategy names.
    :type strategy_names: List[str]
    :returns: Mapping of strategy name → list of 1/0 win indicators.
    :rtype: Dict[str, List[int]]
    """
    aggregated: Dict[str, List[int]] = {n: [] for n in strategy_names}
    for (p1, p2), seq in all_series.items():
        for result in seq:
            if result == 1:
                aggregated[p1].append(1)
                aggregated[p2].append(0)
            elif result == 2:
                aggregated[p1].append(0)
                aggregated[p2].append(1)
            else:
                aggregated[p1].append(0)
                aggregated[p2].append(0)
    return aggregated


def plot_head_to_head(
    results: Dict[Tuple[str, str], Tuple[int, int, int]],
    strategy_names: List[str],
    output: str,
    subtitle: str,
) -> None:
    """Draw a heatmap of pairwise win rates.

    Cell (i, j) = win rate of strategy ``i`` (as P1) against strategy ``j``
    (as P2).  Diagonal is self-play (always 50%).

    :param results: Mapping of (p1, p2) to (p1_wins, p2_wins, draws).
    :type results: Dict[Tuple[str, str], Tuple[int, int, int]]
    :param strategy_names: Ordered list of strategy names.
    :type strategy_names: List[str]
    :param output: File path for the chart image.
    :type output: str
    :param subtitle: Board description.
    :type subtitle: str
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    n = len(strategy_names)
    matrix = np.full((n, n), np.nan)

    for (p1, p2), (w1, w2, d) in results.items():
        i = strategy_names.index(p1) if p1 in strategy_names else -1
        j = strategy_names.index(p2) if p2 in strategy_names else -1
        if i < 0 or j < 0:
            continue
        total = w1 + w2 + d
        matrix[i, j] = (w1 / total * 100) if total > 0 else 50.0

    # Symmetrise: P1 win rate at (i,j) means P2 loss rate at (j,i) = 100 - value
    # We leave the upper triangle filled and mirror the lower
    for i in range(n):
        for j in range(n):
            if i != j and not np.isnan(matrix[i, j]):
                matrix[j, i] = 100.0 - matrix[i, j]

    # Diagonal = 50% (self-play)
    np.fill_diagonal(matrix, 50.0)

    fig, ax = plt.subplots(figsize=(max(8, n * 0.55), max(7, n * 0.5)))

    cmap = plt.colormaps["Blues"]
    im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=100, aspect="equal",
                   interpolation="nearest")

    # Annotate cells
    for i in range(n):
        for j in range(n):
            val = matrix[i, j]
            if np.isnan(val):
                continue
            txt = f"{val:.0f}"
            if i == j:
                txt = "—"  # em dash for diagonal
            ax.text(j, i, txt, ha="center", va="center",
                    fontsize=6, fontweight="bold",
                    color="white" if val > 60 else "black")

    ax.set_xticks(range(n))
    ax.set_xticklabels(strategy_names, fontsize=7, rotation=45, ha="right")
    ax.set_yticks(range(n))
    ax.set_yticklabels(strategy_names, fontsize=7)

    ax.set_xlabel("Opponent (P2)", fontsize=9)
    ax.set_ylabel("Strategy (P1)", fontsize=9)

    fig.colorbar(im, ax=ax, label="Win Rate (%)", shrink=0.8)
    ax.set_title(
        f"Head-to-Head Win Rates",
        fontsize=12,
    )
    if subtitle:
        ax.text(0.5, -0.06, subtitle, transform=ax.transAxes,
                fontsize=8, color="gray", ha="center")

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"Head-to-head matrix saved to {output}")


def plot_game_length_histogram(
    all_lengths: Dict[Tuple[str, str], List[int]],
    strategy_names: List[str],
    output: str,
) -> None:
    """Draw a violin plot of game lengths (rounds per game).

    For each strategy, collects all game round counts across every matchup
    and plots them as a violin (fusiform) chart.  Shows whether a strategy
    dominates quickly (low rounds) or grinds (high rounds).  Medians and
    quartiles are marked inside each violin.

    :param all_lengths: Mapping of (p1, p2) → list of round counts.
    :type all_lengths: Dict[Tuple[str, str], List[int]]
    :param strategy_names: Ordered list of strategy names.
    :type strategy_names: List[str]
    :param output: File path for the chart image.
    :type output: str
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    # Aggregate round counts per strategy (both as P1 and P2)
    per_strategy: Dict[str, List[int]] = {n: [] for n in strategy_names}
    for (p1, p2), lengths in all_lengths.items():
        per_strategy[p1].extend(lengths)
        per_strategy[p2].extend(lengths)

    names = [n for n in strategy_names if per_strategy[n]]
    if not names:
        print("No game length data to plot.")
        return

    data = [per_strategy[n] for n in names]

    _, ax = plt.subplots(figsize=(max(8, len(names) * 0.8), 6))

    colors = [plt.colormaps["Blues"](0.3 + 0.6 * i / max(len(names), 1))
              for i in range(len(names))]

    # Violin (fusiform) plot
    parts = ax.violinplot(data, positions=range(1, len(names) + 1),
                          showmeans=False, showmedians=False, widths=0.7)

    for i, pc in enumerate(parts["bodies"]):
        pc.set_facecolor(colors[i])
        pc.set_edgecolor("none")
        pc.set_alpha(0.7)

    # Quartile lines inside each violin
    for i, vals in enumerate(data):
        q1, med, q3 = np.percentile(vals, [25, 50, 75])
        pos = i + 1
        ax.plot([pos - 0.2, pos + 0.2], [med, med], color="white",
                linewidth=2, solid_capstyle="butt")
        ax.plot([pos - 0.1, pos + 0.1], [q1, q1], color="white",
                linewidth=1, solid_capstyle="butt", alpha=0.7)
        ax.plot([pos - 0.1, pos + 0.1], [q3, q3], color="white",
                linewidth=1, solid_capstyle="butt", alpha=0.7)

    ax.set_xticks(range(1, len(names) + 1))
    ax.set_xticklabels(names, fontsize=8, rotation=30, ha="right")
    ax.set_ylabel("Game Length (rounds)", fontsize=10)
    ax.set_title("Game Length Distribution", fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"Game length histogram saved to {output}")


def plot_first_blood_histogram(
    all_first_bloods: Dict[Tuple[str, str], List[int]],
    strategy_names: List[str],
    output: str,
) -> None:
    """Draw a violin plot of first-blood rounds per strategy.

    Lower first-blood rounds = faster first kill = more aggressive.

    :param all_first_bloods: Mapping of (p1, p2) → list of first-blood
        rounds per game (-1 means no death occurred).
    :type all_first_bloods: Dict[Tuple[str, str], List[int]]
    :param strategy_names: Ordered list of strategy names.
    :type strategy_names: List[str]
    :param output: File path for the chart image.
    :type output: str
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    per_strategy: Dict[str, List[int]] = {n: [] for n in strategy_names}
    for (p1, p2), fb_list in all_first_bloods.items():
        # Only count games where a death actually occurred
        per_strategy[p1].extend(fb for fb in fb_list if fb > 0)
        per_strategy[p2].extend(fb for fb in fb_list if fb > 0)

    names = [n for n in strategy_names if per_strategy[n]]
    if not names:
        print("No first-blood data to plot.")
        return

    data = [per_strategy[n] for n in names]
    colors = [plt.colormaps["Blues"](0.3 + 0.6 * i / max(len(names), 1))
              for i in range(len(names))]

    _, ax = plt.subplots(figsize=(max(8, len(names) * 0.8), 5.5))

    parts = ax.violinplot(data, positions=range(1, len(names) + 1),
                          showmeans=False, showmedians=False, widths=0.7)
    for i, pc in enumerate(parts["bodies"]):
        pc.set_facecolor(colors[i])
        pc.set_edgecolor("none")
        pc.set_alpha(0.7)

    for i, vals in enumerate(data):
        if not vals:
            continue
        med = np.median(vals)
        pos = i + 1
        ax.plot([pos - 0.2, pos + 0.2], [med, med], color="white",
                linewidth=2, solid_capstyle="butt")
        ax.text(pos, max(vals) + 0.5, f"med={med:.0f}",
                ha="center", fontsize=7, color="gray")

    ax.set_xticks(range(1, len(names) + 1))
    ax.set_xticklabels(names, fontsize=8, rotation=30, ha="right")
    ax.set_ylabel("First-Blood Round", fontsize=10)
    ax.set_title("First-Blood Timing", fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"First-blood chart saved to {output}")


def plot_survivor_count(
    all_survivors: Dict[Tuple[str, str], List[Tuple[int, int]]],
    strategy_names: List[str],
    output: str,
) -> None:
    """Draw a stacked bar chart of match outcomes by survivor count.

    Categories:
    - "3-0 stomp": won with all 3 pieces alive
    - "3-1 edge": won with 2 alive
    - "3-2 close": won with 1 alive (last piece standing)
    - "Loss": lost the match

    :param all_survivors: Mapping of (p1, p2) → list of ``(surv_p1,
        surv_p2)`` tuples.
    :type all_survivors: Dict[Tuple[str, str], List[Tuple[int, int]]]
    :param strategy_names: Ordered list of strategy names.
    :type strategy_names: List[str]
    :param output: File path for the chart image.
    :type output: str
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    counts: Dict[str, Dict[str, int]] = {n: {"3-0": 0, "3-1": 0, "3-2": 0, "Loss": 0}
                                         for n in strategy_names}

    for (p1, p2), survivors_list in all_survivors.items():
        for (sp1, sp2) in survivors_list:
            # P1 perspective
            if sp2 == 0:
                if sp1 == 3:
                    counts[p1]["3-0"] += 1
                elif sp1 == 2:
                    counts[p1]["3-1"] += 1
                else:
                    counts[p1]["3-2"] += 1
            else:
                counts[p1]["Loss"] += 1

            # P2 perspective
            if sp1 == 0:
                if sp2 == 3:
                    counts[p2]["3-0"] += 1
                elif sp2 == 2:
                    counts[p2]["3-1"] += 1
                else:
                    counts[p2]["3-2"] += 1
            else:
                counts[p2]["Loss"] += 1

    names = [n for n in strategy_names
             if sum(counts[n].values()) > 0]
    if not names:
        print("No survivor data to plot.")
        return

    categories = ["3-0", "3-1", "3-2", "Loss"]
    colors = {"3-0": "#27ae60", "3-1": "#85c1a8",
              "3-2": "#f5b041", "Loss": "#e74c3c"}

    _, ax = plt.subplots(figsize=(max(8, len(names) * 0.6), 5.5))

    x = np.arange(len(names))
    bottom = np.zeros(len(names))
    bars_data = {}

    for cat in categories:
        values = [counts[n][cat] for n in names]
        b = ax.bar(x, values, bottom=bottom, label=cat,
                   color=colors[cat], width=0.6, edgecolor="white")
        bars_data[cat] = b
        bottom += values

    # Annotate percentages in each bar segment
    for i, name in enumerate(names):
        total = sum(counts[name].values())
        cum = 0
        for cat in categories:
            v = counts[name][cat]
            if v > 0 and total > 0:
                pct = v / total * 100
                ax.text(i, cum + v / 2, f"{pct:.0f}%",
                        ha="center", va="center", fontsize=7,
                        color="white" if pct > 15 else "black",
                        fontweight="bold")
            cum += v

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=8, rotation=30, ha="right")
    ax.set_ylabel("Games", fontsize=10)
    ax.set_title("Match Decisiveness", fontsize=12)
    ax.legend(fontsize=8, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"Survivor chart saved to {output}")
