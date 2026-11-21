"""Render the paper's two comparisons from the released case-by-case records."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
GRIDS = (24, 48, 96)
COLORS = ("#596575", "#d98234", "#117a80")


def data(name):
    with (ROOT / "results" / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    pairs = data("paired_cases.csv")
    closed = data("closed_loop_cases.csv")
    fig, axs = plt.subplots(1, 2, figsize=(9.4, 3.55), layout="constrained")
    grid_indices = np.arange(len(GRIDS))
    for offset, color, method, label in zip(
        (-0.25, 0, 0.25), COLORS, ("analytic", "block_abs", "two_endpoint"),
        ("Original scalar", "Block magnitude", "Two endpoints"),
    ):
        count = [sum(int(row["fallback"]) for row in closed if
                     int(row["n"]) == n and row["method"] == method) for n in GRIDS]
        bars = axs[0].bar(grid_indices+offset, count, 0.23, color=color, label=label)
        axs[0].bar_label(bars, fontsize=8)
    axs[0].set_xticks(grid_indices, [f"{n} x {n}" for n in GRIDS])
    axs[0].set_ylabel("Full solves during 256 queries")
    axs[0].set_ylim(0, 21)
    axs[0].set_title("(a) Each policy updates its own basis", loc="left", fontsize=10)
    axs[0].legend(loc="upper left", fontsize=7, ncol=3, frameon=False)
    for j, (method, label, color) in enumerate(zip(
        ("block_abs", "block_sign"), ("Block magnitude", "Block sign"), COLORS[1:],
    )):
        ratios = [[float(row[method]) / float(row["analytic"]) for row in pairs if
                   int(row["n"]) == n and row["track"] == "fixed8"] for n in GRIDS]
        boxes = axs[1].boxplot(ratios, positions=grid_indices+(j-0.5)*0.29, widths=0.23,
                               showfliers=False, patch_artist=True, manage_ticks=False,
                               medianprops={"color":"#19222a","linewidth":1.7})
        for artist in boxes["boxes"]:
            artist.set_facecolor(color)
            artist.set_alpha(0.82)
        boxes["boxes"][0].set_label(label)
    axs[1].set_xticks(grid_indices, [f"{n} x {n}" for n in GRIDS])
    axs[1].set_ylabel("Bound / original scalar bound")
    axs[1].set_title("(b) Same fixed-rank predictions", loc="left", fontsize=10)
    axs[1].legend(fontsize=8, frameon=False)
    for ax in axs:
        ax.grid(axis="y", alpha=0.19)
        ax.set_axisbelow(True)
        ax.spines[["top","right"]].set_visible(False)
    fig.savefig(ROOT.parent / "thermal/report/figures/residual_comparison.png", dpi=210)
    plt.close(fig)


if __name__ == "__main__":
    main()
