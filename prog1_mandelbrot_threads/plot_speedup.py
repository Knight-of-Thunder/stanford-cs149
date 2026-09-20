#!/usr/bin/env python3
"""Plot Program 1 speedup vs thread count: contiguous vs interleaved
decomposition, for VIEW 1 and VIEW 2. Data from writeup_notes.md
(min of 5 runs, AMD Ryzen 7 6800H, 8 cores / 16 threads)."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

threads = [2, 3, 4, 5, 6, 7, 8]

data = {
    "VIEW 1": {
        "contiguous":  [2.23, 1.64, 2.36, 2.47, 3.17, 3.39, 4.01],
        "interleaved": [2.27, 2.90, 3.81, 4.71, 5.79, 6.56, 7.20],
    },
    "VIEW 2": {
        "contiguous":  [2.05, 2.34, 2.60, 3.00, 3.36, 3.83, 4.21],
        "interleaved": [1.91, 2.80, 3.69, 4.55, 5.45, 6.18, 6.64],
    },
}

# Colorblind-safe categorical pair (validated: CVD dE 29.2), gray ideal line.
C_CONTIG = "#0072B2"   # blue
C_INTER  = "#E69F00"   # orange
C_IDEAL  = "#9a9a9a"   # neutral gray
INK      = "#222222"

fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)

for ax, view in zip(axes, ["VIEW 1", "VIEW 2"]):
    # Ideal linear speedup reference (y = x).
    ax.plot(threads, threads, linestyle="--", linewidth=1.5, color=C_IDEAL,
            zorder=1, label="ideal linear")

    for name, color in [("contiguous", C_CONTIG), ("interleaved", C_INTER)]:
        y = data[view][name]
        ax.plot(threads, y, marker="o", markersize=7, linewidth=2,
                color=color, zorder=3, label=name)
        # Direct-label the 8-thread endpoint (relief for low-contrast orange).
        ax.annotate(f"{y[-1]:.2f}x", (threads[-1], y[-1]),
                    textcoords="offset points", xytext=(8, -2),
                    fontsize=9, color=color, fontweight="bold")

    ax.set_title(view, fontsize=12, color=INK)
    ax.set_xlabel("Threads", fontsize=11, color=INK)
    ax.set_xticks(threads)
    ax.set_xlim(1.7, 9.2)
    ax.grid(True, linewidth=0.5, color="#dddddd", zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

axes[0].set_ylabel("Speedup (vs serial)", fontsize=11, color=INK)
axes[0].set_ylim(0, 9)
axes[0].legend(loc="upper left", frameon=False, fontsize=10)

fig.suptitle("Program 1: Mandelbrot speedup — contiguous vs interleaved rows\n"
             "(AMD Ryzen 7 6800H, 8 cores / 16 threads)",
             fontsize=12.5, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.93))
fig.savefig("speedup.png", dpi=150)
print("Wrote speedup.png")
