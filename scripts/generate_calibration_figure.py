"""Generate TTFC vs FP Rate calibration scatter plot for the paper.

ICML-grade: Computer Modern fonts, minimal chrome, data-driven annotation.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os

# Use Computer Modern (LaTeX) fonts to match ICML paper
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Computer Modern Roman", "CMU Serif", "Times New Roman"],
    "mathtext.fontset": "cm",
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8,
    "figure.dpi": 300,
})

# v2 baseline data (40 standard-tier episodes per model)
models = {
    "GPT-5.2":      {"ttfc": 4.1,  "fp": 82.5, "egar": 37.5, "threshold": "Uncalibrated"},
    "Sonnet 4.5":   {"ttfc": 10.6, "fp": 45.0, "egar": 39.2, "threshold": "Partially Calibrated"},
    "Gemini 3":     {"ttfc": 8.6,  "fp": 57.5, "egar": 42.9, "threshold": "Partially Calibrated"},
    "DeepSeek 3.2": {"ttfc": 9.0,  "fp": 65.0, "egar": 54.2, "threshold": "Partially Calibrated"},
}

names = list(models.keys())
ttfc = np.array([models[n]["ttfc"] for n in names])
fp = np.array([models[n]["fp"] for n in names])
egar = np.array([models[n]["egar"] for n in names])

# Single-column ICML figure: 3.25in wide
fig, ax = plt.subplots(figsize=(3.25, 2.6))

# Uniform marker style -- no color encoding (cleaner for single-column)
marker_size = 50
ax.scatter(ttfc, fp, s=marker_size, c="black", edgecolors="black",
           linewidths=0.6, zorder=5)

# Labels with manual offsets for no overlap
label_config = {
    "GPT-5.2":      {"dx": 0.4,  "dy": -4.0, "ha": "left",  "va": "top"},
    "Sonnet 4.5":   {"dx": -0.3, "dy": -4.0, "ha": "right", "va": "top"},
    "Gemini 3":     {"dx": -0.3, "dy": 2.5,  "ha": "right", "va": "bottom"},
    "DeepSeek 3.2": {"dx": 0.4,  "dy": 2.0,  "ha": "left",  "va": "bottom"},
}

for name, d in models.items():
    cfg = label_config[name]
    ax.annotate(
        name,
        (d["ttfc"], d["fp"]),
        xytext=(d["ttfc"] + cfg["dx"], d["fp"] + cfg["dy"]),
        fontsize=7.5,
        ha=cfg["ha"],
        va=cfg["va"],
    )

# Linear trend line
z = np.polyfit(ttfc, fp, 1)
p = np.poly1d(z)
x_line = np.linspace(3.0, 12.0, 100)
ax.plot(x_line, p(x_line), color="gray", linewidth=0.8, linestyle="--",
        zorder=2, alpha=0.7)

# Axes
ax.set_xlabel("Time to First Containment (steps)")
ax.set_ylabel("False Positive Rate (%)")
ax.set_xlim(2.5, 12.5)
ax.set_ylim(35, 92)
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%d%%"))

# Minimal chrome
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_linewidth(0.6)
ax.spines["bottom"].set_linewidth(0.6)
ax.tick_params(width=0.6)

plt.tight_layout(pad=0.3)

# Save
out_dir = os.path.join(os.path.dirname(__file__), "..", "paper", "figures")
out_path = os.path.join(out_dir, "calibration-tradeoff.png")
fig.savefig(out_path, dpi=300, bbox_inches="tight")
print(f"Saved: {out_path}")

out_pdf = os.path.join(out_dir, "calibration-tradeoff.pdf")
fig.savefig(out_pdf, bbox_inches="tight")
print(f"Saved: {out_pdf}")

plt.close()
