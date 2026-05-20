"""Paper-style strategy fingerprint chart — four core tactical indicators."""

from typing import List, Optional, Tuple


# Modern, cohesive color palette
_C = {
    "str": "#4c72b0", "dex": "#55a868", "int": "#c44e52",
    "compactness": "#937860", "ffi": "#4c72b0",
    "kei": "#dd8452", "kei_kite": "#c44e52", "kei_no": "#b0b0b0",
    "red": "#c44e52", "blue": "#4c72b0",
    "bg": "#f9f9fb", "text": "#4a4a4a", "text_light": "#8c8c8c",
}


def _try_init() -> bool:
    try:
        import matplotlib  # noqa: PLC0415
        matplotlib.use("Agg")
        matplotlib.rcParams.update({
            "font.family": "sans-serif",
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 7.5,
            "axes.titlepad": 4,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5,
            "figure.dpi": 150,
            "savefig.dpi": 150,
            "axes.spines.top": False,
            "axes.spines.right": False,
        })
        return True
    except ImportError:
        return False


# ── Fingerprint (6-panel aggregate) ────────────────────────────────────────


def plot_strategy_fingerprint(
    all_indicators: List[dict], agg: dict, output: str,
) -> None:
    """Publication-quality 6-panel strategy fingerprint figure."""
    if not _try_init():
        return
    import matplotlib.pyplot as plt  # noqa: PLC0415

    # ── Layout: 2 rows, row 0 has 4 cols, row 1 has 2 cols ──
    fig = plt.figure(figsize=(12, 6.5))
    gs = fig.add_gridspec(
        2, 4, hspace=0.45, wspace=0.35,
        left=0.06, right=0.97, top=0.90, bottom=0.08,
    )

    build = agg.get("player_build", {})
    nm = agg.get("n_matches", 0)
    wr = agg.get("win_rate", 0)
    dmg = agg.get("avg_damage", 0)
    fb_r = agg.get("avg_first_blood_round", 0)
    fb_wr = agg.get("first_blood_win_rate", 0)
    spells = agg.get("avg_spell_count", 0)

    # ── Row 0: A | B | C | D ──

    # -- A: Build ----------------------------------------------------------
    ax1 = fig.add_subplot(gs[0, 0])
    str_v = (build.get("str") or [29])[0]
    dex_v = (build.get("dex") or [1])[0]
    int_v = (build.get("int") or [0])[0]
    vals = [str_v, dex_v, int_v]
    bars = ax1.bar(
        ["STR", "DEX", "INT"], vals, width=0.5,
        color=[_C["str"], _C["dex"], _C["int"]],
        edgecolor="white", linewidth=0.5,
    )
    ax1.set_ylim(0, 35)
    ax1.set_title("A  Build", loc="left", fontweight="bold", fontsize=9)
    ax1.set_ylabel("Attribute points")
    for bar, v in zip(bars, vals):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.6,
            str(v), ha="center", fontsize=8.5, fontweight="bold",
        )

    # -- B: Focus Fire Index (FFI) -----------------------------------------
    ax2 = fig.add_subplot(gs[0, 1])
    ffi = agg.get("ffi", 0)
    ax2.barh([0], [ffi * 100], height=0.35, color=_C["ffi"],
             edgecolor="white", linewidth=0.5)
    ax2.set_xlim(0, 100)
    ax2.set_yticks([])
    ax2.set_title("B  Focus Fire Index", loc="left", fontweight="bold", fontsize=9)
    ax2.set_xlabel("% attacks on same target (3-rnd window)")
    ax2.text(ffi * 100 + 1.5, 0, f"{ffi:.0%}",
             va="center", fontsize=8.5, fontweight="bold")

    if ffi >= 0.6:
        note = "High coordination — strong focus fire"
    elif ffi >= 0.4:
        note = "Moderate coordination"
    else:
        note = "Low coordination — attacks spread"
    ax2.text(50, -0.65, note, ha="center", fontsize=6.5, color=_C["text_light"])

    # -- C: Kiting Efficiency (KEI) ----------------------------------------
    ax3 = fig.add_subplot(gs[0, 2])
    kei = agg.get("kei_ratio", 0)
    kei_att = agg.get("kei_total_attempts", 0)

    kite_pct = kei * 100
    no_kite_pct = (1 - kei) * 100
    ax3.barh([0], [kite_pct], height=0.35, left=0,
             color=_C["kei_kite"], edgecolor="white", linewidth=0.5)
    ax3.barh([0], [no_kite_pct], height=0.35, left=kite_pct,
             color=_C["kei_no"], edgecolor="white", linewidth=0.5)
    ax3.set_xlim(0, 100)
    ax3.set_yticks([])
    ax3.set_title("C  Kiting Efficiency", loc="left", fontweight="bold", fontsize=9)
    ax3.set_xlabel("% of move+attack actions")
    ax3.text(50, -0.65, f"{kei_att} move+attack actions detected",
             ha="center", fontsize=6.5, color=_C["text_light"])

    # -- D: Compactness ----------------------------------------------
    ax4 = fig.add_subplot(gs[0, 3])
    comp = agg.get("compactness", 0)
    opp_comp = agg.get("opponent_compactness", 0)

    ax4.barh([0.4], [comp], height=0.3, color=_C["compactness"],
             edgecolor="white", linewidth=0.5)
    ax4.barh([0.0], [opp_comp], height=0.3, color=_C["text_light"],
             edgecolor="white", linewidth=0.5, alpha=0.6)
    ax4.set_yticks([0.4, 0.0])
    ax4.set_yticklabels(["Player", "Opponent"], fontsize=6.5)
    ax4.set_title("D  Compactness", loc="left", fontweight="bold", fontsize=9)
    ax4.set_xlabel("MAD from centroid (tiles)")

    xmax = max(comp, opp_comp) * 1.4 + 1
    ax4.set_xlim(0, xmax)
    for y, v in [(0.4, comp), (0.0, opp_comp)]:
        ax4.text(v + 0.2, y, f"{v:.1f}", va="center", fontsize=7.5, fontweight="bold")

    if comp <= 3:
        label = "tight deathball"
    elif comp <= 7:
        label = "medium spread"
    else:
        label = "loose / lane split"
    ax4.text(xmax / 2, -0.65, f"Formation: {label}",
             ha="center", fontsize=6.5, color=_C["text_light"])

    # ── Row 1: [  E: combat + HAI  ] [  F: legend + summary  ] ──
    gs_bottom = gs[1, :].subgridspec(1, 2, wspace=0.30, width_ratios=[1.2, 1])

    # -- E: Combat Stats + HAI ---------------------------------------------
    ax5 = fig.add_subplot(gs_bottom[0])
    ax5.set_title("E  Combat & High Ground", loc="left", fontweight="bold", fontsize=9)
    ax5.set_xlim(0, 1)
    ax5.set_ylim(0, 1)
    ax5.axis("off")

    # Damage gauge
    ax5.text(0.00, 0.85, "Damage / attack", fontsize=7.5, color=_C["text"])
    dmg_norm = min(dmg / 50, 1)
    ax5.barh(0.72, dmg_norm, height=0.12, color=_C["str"],
             edgecolor="white", linewidth=0.5)
    ax5.plot([0, 1], [0.78, 0.78], color="#e0e0e0", linewidth=0.5,
             transform=ax5.transData, zorder=0)
    ax5.text(dmg_norm + 0.01, 0.72, f"{dmg:.1f}",
             va="center", fontsize=8, fontweight="bold")

    # Spells gauge
    ax5.text(0.00, 0.55, "Spells / match", fontsize=7.5, color=_C["text"])
    spell_norm = min(spells / 5, 1)
    ax5.barh(0.42, spell_norm, height=0.12, color=_C["int"],
             edgecolor="white", linewidth=0.5)
    ax5.plot([0, 1], [0.48, 0.48], color="#e0e0e0", linewidth=0.5,
             transform=ax5.transData, zorder=0)
    ax5.text(spell_norm + 0.01, 0.42, f"{spells:.1f}",
             va="center", fontsize=8, fontweight="bold")

    # First blood annotation at bottom
    fb_text = f"R{fb_r:.0f}" if fb_r > 0 else "N/A"
    ax5.text(0.00, -0.10, "First blood", fontsize=7.5, color=_C["text"])
    ax5.text(0.00, -0.20, fb_text, fontsize=13, fontweight="bold",
             color=_C["int"])
    ax5.text(0.12, -0.17, f"(win {fb_wr:.0%})", fontsize=7,
             color=_C["text_light"], va="bottom")

    # -- F: Legend + Text Summary ------------------------------------------
    ax6 = fig.add_subplot(gs_bottom[1])
    ax6.set_xlim(0, 1)
    ax6.set_ylim(0, 1)
    ax6.axis("off")
    ax6.set_title("F  Summary", loc="left", fontweight="bold", fontsize=9)

    col_x = [0.00, 0.36, 0.64]
    avg_r = _mean(ind["total_rounds"] for ind in all_indicators)
    outcomes = [
        ("Wins", f"{agg['n_wins']} / {nm}  ({wr:.0f}%)"),
        ("First blood win", f"{fb_wr:.0%}"),
        ("Avg rounds", f"{avg_r:.1f}"),
    ]
    for i, (title, val) in enumerate(outcomes):
        ax6.text(col_x[i], 0.80, title, fontsize=6.5, color=_C["text_light"])
        ax6.text(col_x[i], 0.64, val, fontsize=10, fontweight="bold")

    ax6.plot([0.02, 0.98], [0.50, 0.50], color="#e0e0e0", linewidth=0.5,
             transform=ax6.transAxes)

    legend_lines = (
        "Four tactical indicators:\n"
        "  Compactness — formation tightness (MAD)\n"
        "  FFI         — focus-fire coordination\n"
        "  HAI         — high-ground utilization\n"
        "  KEI         — hit-and-run (kiting) rate"
    )
    ax6.text(0.02, 0.42, legend_lines, fontsize=6.5, color=_C["text"],
             va="top", linespacing=1.6)

    thresholds = (
        f"Thresholds:\n"
        f"  Compact ≤3 tight  ≤7 medium  >7 loose\n"
        f"  FFI ≥0.6 high coordination\n"
        f"  KEI ≥0.3 active kiting"
    )
    ax6.text(0.02, 0.10, thresholds, fontsize=6, color=_C["text_light"],
             va="top", linespacing=1.4)

    fig.suptitle(
        f"Strategy Fingerprint  ({nm} matches, {agg['n_wins']}W / {nm - agg['n_wins']}L)",
        fontsize=14, fontweight="bold", y=0.97,
    )

    plt.savefig(output)
    plt.close()
    print(f"Strategy fingerprint saved to {output}")


# ── Average timeline charts (4 independent PNGs, mean ± std) ─────────────


def plot_average_timelines(
    avg_data: dict, output_dir: str, n_matches: int,
    camp_labels: Optional[dict] = None,
    player_camp: Optional[str] = None,
) -> None:
    """Generate four average ± std timeline PNGs (player's camp only).

    Files produced::

        {output_dir}/compactness_timeline.png
        {output_dir}/focus_fire_timeline.png
        {output_dir}/kiting_efficiency_timeline.png

    :param camp_labels: Optional ``{"Red": "Red (name)", "Blue": "Blue (name)"}``.
    :type camp_labels: dict or None
    :param player_camp: Only plot this camp ("Red"/"Blue").
    :type player_camp: str or None
    """
    if not _try_init():
        return
    import matplotlib.pyplot as plt  # noqa: PLC0415

    rn = avg_data["rounds"]
    cl = camp_labels or {}

    _avg_linechart(
        rn, avg_data["compactness"],
        "Compactness", "MAD from centroid (tiles)",
        f"{output_dir}/compactness_timeline.png",
        camp_labels=cl, player_camp=player_camp,
    )
    _avg_linechart(
        rn, avg_data["ffi"],
        "Focus Fire Index (3-rnd window)", "FFI",
        f"{output_dir}/focus_fire_timeline.png",
        y_lim=(0, 1.05), camp_labels=cl, player_camp=player_camp,
    )
    _avg_linechart(
        rn, avg_data["kiting"],
        "Kiting Efficiency (per round)", "Kite (1=kited)",
        f"{output_dir}/kiting_efficiency_timeline.png",
        y_lim=(-0.05, 1.05), camp_labels=cl, player_camp=player_camp,
    )

    print(f"  Average timeline charts saved to {output_dir}/ (n={n_matches})")


def _avg_linechart(
    x: List[int],
    camp_data: dict,
    title: str, ylabel: str, path: str,
    y_lim: Optional[Tuple[float, float]] = None,
    camp_labels: Optional[dict] = None,
    player_camp: Optional[str] = None,
) -> None:
    import matplotlib.pyplot as plt  # noqa: PLC0415

    fig, ax = plt.subplots(figsize=(7, 3.5))
    cl = camp_labels or {}

    camps_to_plot = [player_camp] if player_camp else ["Red", "Blue"]

    for camp in camps_to_plot:
        color = _C["red"] if camp == "Red" else _C["blue"]
        label = cl.get(camp, camp)
        d = camp_data[camp]
        mean = d["mean"]
        std = d["std"]
        upper = [m + s for m, s in zip(mean, std)]
        lower = [m - s for m, s in zip(mean, std)]
        ax.plot(x, mean, color=color, label=label, linewidth=1.4)
        ax.fill_between(x, lower, upper, color=color, alpha=0.12)

    if y_lim:
        ax.set_ylim(*y_lim)
    ax.set_xlabel("Round")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold")
    ax.legend(frameon=False)
    ax.set_facecolor(_C["bg"])
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def _mean(iterator):
    vals = list(iterator)
    return sum(vals) / len(vals) if vals else 0.0
