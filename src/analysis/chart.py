"""Generate charts from computed indicators."""

from typing import Dict, List, Tuple


def _try_init() -> bool:
    try:
        import matplotlib  # noqa: PLC0415
        matplotlib.use("Agg")
        return True
    except ImportError:
        return False


def plot_build_distribution(
    builds: List[Tuple[int, int, int]],
    output: str,
) -> None:
    """Scatter plot of STR/DEX allocation across all opponents.

    :param builds: List of ``(strength, dexterity, intelligence)`` tuples.
    :type builds: List[Tuple[int, int, int]]
    :param output: Output file path.
    :type output: str
    """
    if not _try_init():
        return
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    strs = [b[0] for b in builds]
    dexs = [b[1] for b in builds]
    ints = [b[2] for b in builds]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # STR vs DEX scatter
    sc = ax1.scatter(strs, dexs, c=ints, cmap="Blues", s=40, alpha=0.7,
                     edgecolors="white", linewidth=0.5)
    ax1.set_xlabel("Strength")
    ax1.set_ylabel("Dexterity")
    ax1.set_title("STR vs DEX (color = INT)")
    fig.colorbar(sc, ax=ax1, label="INT")
    ax1.spines[["top", "right"]].set_visible(False)

    # STR histogram
    ax2.hist(strs, bins=range(18, 33), color="#3498db", edgecolor="white",
             alpha=0.8)
    ax2.set_xlabel("Strength")
    ax2.set_ylabel("Count")
    ax2.set_title("STR Distribution")
    ax2.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"Build distribution saved to {output}")


def plot_target_preference(
    ratios: List[float],
    labels: List[str],
    output: str,
) -> None:
    """Bar chart of target-lowest-HP ratio per opponent.

    :param ratios: List of ratios (0.0 to 1.0).
    :type ratios: List[float]
    :param labels: Opponent labels.
    :type labels: List[str]
    :param output: Output file path.
    :type output: str
    """
    if not _try_init():
        return
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    _, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.35)))

    colors = ["#27ae60" if r > 0.5 else "#e74c3c" for r in ratios]
    bars = ax.barh(labels, ratios, color=colors, height=0.6)

    for bar, r in zip(bars, ratios):
        ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
                f"{r:.0%}", va="center", fontsize=8)

    ax.axvline(x=0.5, color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Ratio of Attacks on Lowest-HP Enemy")
    ax.set_title("Target Preference: Lowest-HP vs Other")
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"Target preference saved to {output}")


def plot_focus_fire(
    all_indicators: List[dict],
    labels: List[str],
    output: str,
) -> None:
    """Bar chart of focus-fire events per match.

    :param all_indicators: List of per-match indicator dicts.
    :type all_indicators: List[dict]
    :param labels: Opponent labels.
    :type labels: List[str]
    :param output: Output file path.
    :type output: str
    """
    if not _try_init():
        return
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    ff = [ind["focus_fire_events"] for ind in all_indicators]
    rounds = [ind["total_rounds"] for ind in all_indicators]

    _, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.35)))

    y = range(len(labels))
    ax.barh(y, ff, height=0.5, color="#3498db", alpha=0.8, label="Focus-fire")
    ax.barh(y, rounds, height=0.5, color="#bdc3c7", alpha=0.4,
             label="Total rounds")

    for i, (f, r) in enumerate(zip(ff, rounds)):
        ax.text(r + 0.3, i, f"{f}/{r}", va="center", fontsize=7, color="gray")

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Rounds")
    ax.set_title("Focus-Fire Events per Match")
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"Focus-fire chart saved to {output}")


def plot_first_blood_summary(
    all_indicators: List[dict],
    labels: List[str],
    output: str,
) -> None:
    """Bar chart of first-blood round and who got it.

    :param all_indicators: List of per-match indicator dicts.
    :type all_indicators: List[dict]
    :param labels: Opponent labels.
    :type labels: List[str]
    :param output: Output file path.
    :type output: str
    """
    if not _try_init():
        return
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    fb_rounds = [ind["first_blood_round"] for ind in all_indicators]
    fb_camps = [ind["first_blood_camp"] for ind in all_indicators]
    won = [ind["player_won"] for ind in all_indicators]

    colors = []
    for camp, w in zip(fb_camps, won):
        if camp == "":
            colors.append("#95a5a6")  # no fb
        elif (camp == "Red" and w) or (camp == "Blue" and not w):
            colors.append("#27ae60")  # good fb
        else:
            colors.append("#e74c3c")  # bad fb

    _, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.35)))

    bars = ax.barh(labels, fb_rounds, color=colors, height=0.6)

    for bar, r, c in zip(bars, fb_rounds, fb_camps):
        if r > 0:
            ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                    f"R{r} ({c})", va="center", fontsize=7, color="gray")

    ax.set_xlabel("First-Blood Round")
    ax.set_title("First Blood: Round and Side")
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"First-blood summary saved to {output}")


def plot_death_sequence(
    all_indicators: List[dict],
    labels: List[str],
    output: str,
) -> None:
    """Gantt-like chart showing when each piece died.

    :param all_indicators: List of per-match indicator dicts.
    :type all_indicators: List[dict]
    :param labels: Opponent labels.
    :type labels: List[str]
    :param output: Output file path.
    :type output: str
    """
    if not _try_init():
        return
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    _, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.5)))

    for i, (ind, label) in enumerate(zip(all_indicators, labels)):
        total_r = ind["total_rounds"]
        deaths = ind["death_sequence"]

        # Bar for total match length
        ax.barh(i, total_r, height=0.4, color="#ecf0f1", edgecolor="none")

        # Mark deaths
        for dr, sid, camp in deaths:
            color = "#e74c3c" if (camp == "Red") else "#3498db"
            ax.plot(dr, i, marker="x", color=color, markersize=8,
                    markeredgewidth=2)

        # Mark first blood
        fb = ind["first_blood_round"]
        if fb > 0:
            ax.plot(fb, i, marker="D", color="#f39c12", markersize=6)

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Round")
    ax.set_title("Death Sequence (× = death, ♦ = first blood)")
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"Death sequence chart saved to {output}")
