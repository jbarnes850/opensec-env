"""Generate the page-1 teaser figure for the OpenSec ICML paper (v2).

Full-width two-model episode timeline showing the calibration gap:
GPT-5.2 (uncalibrated) vs Sonnet 4.5 (partially calibrated).
Kill chain at top, color-coded steps, TTFC markers, injection exposure.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# ── ICML style ──
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Computer Modern Roman", "CMU Serif", "DejaVu Serif", "Times New Roman"],
    "text.usetex": False,
    "font.size": 8.5,
    "axes.labelsize": 8.5,
    "figure.dpi": 300,
})

# ── Data ──
# Representative episodes for the two extreme models
# GPT-5.2: TTFC=4.1, FP=82.5%, Cont=100%, EGAR=37.5%
gpt_episode = [
    ("investigate", "query_logs"),      # 1
    ("investigate", "fetch_alert"),     # 2
    ("investigate", "fetch_email"),     # 3  <- injection exposure
    ("fp",          "isolate_host"),    # 4  <- TTFC
    ("correct",     "block_domain"),    # 5
    ("fp",          "isolate_host"),    # 6
    ("fp",          "reset_user"),      # 7
    ("investigate", "query_logs"),      # 8
    ("correct",     "isolate_host"),    # 9
    ("fp",          "block_domain"),    # 10
    ("investigate", "query_logs"),      # 11
    ("report",      "submit_report"),   # 12
    ("idle",        ""),                # 13
    ("idle",        ""),                # 14
    ("idle",        ""),                # 15
]

# Sonnet 4.5: TTFC=10.6, FP=45%, Cont=62.5%, EGAR=39.2%
sonnet_episode = [
    ("investigate", "query_logs"),      # 1
    ("investigate", "fetch_alert"),     # 2
    ("investigate", "query_logs"),      # 3
    ("investigate", "fetch_email"),     # 4
    ("investigate", "query_logs"),      # 5
    ("investigate", "fetch_alert"),     # 6
    ("investigate", "fetch_email"),     # 7  <- injection exposure
    ("investigate", "query_logs"),      # 8
    ("investigate", "fetch_alert"),     # 9
    ("investigate", "query_logs"),      # 10
    ("correct",     "isolate_host"),    # 11  <- TTFC
    ("correct",     "block_domain"),    # 12
    ("fp",          "reset_user"),      # 13
    ("report",      "submit_report"),   # 14
    ("idle",        ""),                # 15
]

# Kill chain stages (attacker progression regardless of defender)
kill_stages = [
    ("Phish Sent",     0, 2,  "#f0e4d0"),
    ("Creds Used",     2, 5,  "#e4cab0"),
    ("Lateral Move",   5, 8,  "#d8b490"),
    ("Data Access",    8, 11, "#cca070"),
    ("Exfil Attempt", 11, 15, "#c08850"),
]

# ── Colors ──
colors = {
    "investigate": "#c4d2e0",   # slightly more saturated blue-grey
    "correct":     "#3d8b5e",   # strong green
    "fp":          "#c43c3c",   # strong red
    "report":      "#7c8d9c",   # steel
    "idle":        "#f5f5f5",   # near-white
    "injection":   "#e89040",   # amber for injection markers
}

# ── Layout ──
n_steps = 15
cell_w = 0.92
cell_h = 0.75
corner_r = 0.06

# Vertical layout: more breathing room between step numbers and GPT row
gpt_y = 2.4
sonnet_y = 0.5
kill_y = 4.5
step_num_y = 4.05  # step numbers row
sep_y = (gpt_y + sonnet_y + cell_h) / 2  # midpoint between rows

fig_w, fig_h = 6.75, 3.2
fig, ax = plt.subplots(figsize=(fig_w, fig_h))
ax.set_xlim(-2.2, 17.0)
ax.set_ylim(-1.1, 5.8)
ax.set_aspect("equal")
for sp in ax.spines.values():
    sp.set_visible(False)
ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)


def draw_episode_row(episode, y_base, model_name, ttfc_step, fp_pct, ttfc_val,
                     threshold_label, injection_step):
    """Draw one model's episode row."""

    # Model name -- primary hierarchy element (11pt bold)
    ax.text(
        -0.7, y_base + cell_h / 2 + 0.12,
        model_name,
        ha="right", va="center", fontsize=11, fontweight="bold", color="#1a1a1a",
    )
    # Threshold classification -- secondary (8pt, normal weight)
    ax.text(
        -0.7, y_base + cell_h / 2 - 0.25,
        threshold_label,
        ha="right", va="center", fontsize=7.5, color="#777777",
    )

    # Step cells
    for i, (atype, alabel) in enumerate(episode):
        x = i
        c = colors[atype]

        # Idle cells get dashed edge to signal "empty step"
        if atype == "idle":
            rect = FancyBboxPatch(
                (x - cell_w / 2, y_base), cell_w, cell_h,
                boxstyle=f"round,pad={corner_r}",
                facecolor=c, edgecolor="#d8d8d8", linewidth=0.5,
                linestyle="--", zorder=3,
            )
        else:
            rect = FancyBboxPatch(
                (x - cell_w / 2, y_base), cell_w, cell_h,
                boxstyle=f"round,pad={corner_r}",
                facecolor=c, edgecolor="#dcdcdc", linewidth=0.6,
                zorder=3,
            )
        ax.add_patch(rect)

        # No in-cell text -- color alone encodes the action category,
        # and abbreviations require a lookup table not present in the figure.

    # TTFC marker (triangle + vertical line)
    ttfc_x = ttfc_step - 1  # 0-indexed
    ax.plot(
        [ttfc_x, ttfc_x], [y_base - 0.18, y_base + cell_h + 0.08],
        color="#111111", linewidth=1.8, zorder=6, solid_capstyle="round",
    )
    ax.plot(
        ttfc_x, y_base + cell_h + 0.08,
        marker="v", color="#111111", markersize=5, zorder=6,
    )
    ax.text(
        ttfc_x, y_base + cell_h + 0.28,
        f"TTFC {ttfc_val}",
        ha="center", va="bottom", fontsize=6.5, color="#333333",
        fontweight="bold",
    )

    # Injection exposure marker (amber diamond below the cell)
    inj_x = injection_step - 1  # 0-indexed
    ax.plot(
        inj_x, y_base - 0.18,
        marker="D", markersize=4.5, color=colors["injection"],
        markeredgecolor="#c07028", markeredgewidth=0.5,
        zorder=5,
    )

    # FP stat (right side) -- secondary hierarchy (10pt bold, anchored outside grid)
    ax.text(
        n_steps + 0.1, y_base + cell_h / 2,
        f"FP {fp_pct}%",
        ha="left", va="center", fontsize=10, fontweight="bold",
        color=colors["fp"],
    )

# ── Kill chain header ──
# Compute box positions from the same cell grid for alignment
for label, start, end, kc in kill_stages:
    box_x = start - cell_w / 2
    box_w = (end - start) - (1 - cell_w)  # align to cell edges
    rect = FancyBboxPatch(
        (box_x, kill_y), box_w, 0.55,
        boxstyle="round,pad=0.04",
        facecolor=kc, edgecolor="none", linewidth=0,
        zorder=2,
    )
    ax.add_patch(rect)
    # True center of the box
    ax.text(
        box_x + box_w / 2, kill_y + 0.275,
        label, ha="center", va="center", fontsize=6.5,
        color="#3a2218", fontweight="bold",
    )

ax.text(
    -0.7, kill_y + 0.275,
    "Attacker",
    ha="right", va="center", fontsize=8, color="#8a6040", fontweight="bold",
)

# "Steps" label (left-aligned with model names)
ax.text(
    -0.7, step_num_y,
    "Steps",
    ha="right", va="center", fontsize=7.5, color="#999999", fontstyle="italic",
)

# Step numbers (slightly larger and darker for print legibility)
for i in range(n_steps):
    ax.text(
        i, step_num_y,
        str(i + 1),
        ha="center", va="center", fontsize=6.5, color="#999999",
    )

# ── Draw the two model rows ──
draw_episode_row(
    gpt_episode, y_base=gpt_y, model_name="GPT-5.2",
    ttfc_step=4, fp_pct=82, ttfc_val=4.1,
    threshold_label="Uncalibrated",
    injection_step=3,
)

draw_episode_row(
    sonnet_episode, y_base=sonnet_y, model_name="Sonnet 4.5",
    ttfc_step=11, fp_pct=45, ttfc_val=10.6,
    threshold_label="Partially Calibrated",
    injection_step=7,
)

# ── Separator line between models (stronger for print) ──
ax.plot(
    [-0.5, 14.5], [sep_y, sep_y],
    color="#cccccc", linewidth=0.6, zorder=1,
)

# ── Legend (fixed-width columns for even spacing) ──
leg_y = -0.75
leg_items = [
    ("Investigation", colors["investigate"]),
    ("Correct Containment", colors["correct"]),
    ("False Positive", colors["fp"]),
    ("Report", colors["report"]),
]

# Fixed-width column positions -- wider spacing to prevent text overlap
col_positions = [-0.5, 2.8, 6.5, 9.2]
for (label, fcolor), x_pos in zip(leg_items, col_positions):
    rect = FancyBboxPatch(
        (x_pos, leg_y - 0.12), 0.5, 0.3,
        boxstyle=f"round,pad={corner_r}",
        facecolor=fcolor, edgecolor="#d0d0d0", linewidth=0.4,
        zorder=3,
    )
    ax.add_patch(rect)
    ax.text(
        x_pos + 0.72, leg_y + 0.02,
        label,
        ha="left", va="center", fontsize=6, color="#555555",
    )

# TTFC legend (marker group, right of action types)
ttfc_leg_x = 11.5
ax.plot(
    [ttfc_leg_x, ttfc_leg_x], [leg_y - 0.08, leg_y + 0.16],
    color="#111111", linewidth=1.5, zorder=5,
)
ax.plot(ttfc_leg_x, leg_y + 0.16, marker="v", color="#111111", markersize=4, zorder=5)
ax.text(
    ttfc_leg_x + 0.3, leg_y + 0.02,
    "First Containment",
    ha="left", va="center", fontsize=6, color="#555555",
)

# Injection legend
inj_leg_x = 14.5
ax.plot(
    inj_leg_x, leg_y + 0.02,
    marker="D", markersize=5, color=colors["injection"],
    markeredgecolor="#c07028", markeredgewidth=0.5,
    zorder=5,
)
ax.text(
    inj_leg_x + 0.35, leg_y + 0.02,
    "Injection",
    ha="left", va="center", fontsize=6, color="#555555",
)

plt.tight_layout(pad=0.2)
plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

out = "/Users/jarrodbarnes/opensec-env/paper/opensec-arxiv/figures/calibration-timeline-v2.png"
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
print(f"Saved to {out}")

import shutil
shutil.copy(out, "/Users/jarrodbarnes/opensec-env/assets/calibration-timeline-v2.png")
print("Copied to assets/")
