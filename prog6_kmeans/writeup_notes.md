# Program 6 — Writeup Notes (K-Means optimization)

Machine: AMD Ryzen 7 6800H (8C/16T). Data: M=1,000,000 points, N=100 dims,
K=3 clusters, epsilon=0.1 (locally generated, statistically equivalent to
the Stanford data.dat). Correctness checked against starter-generated
start_starter_ref.log / end_starter_ref.log and via plot.py.

Method: "I measured ... which led me to believe X. So I tried ... resulting
in a speedup/slowdown of ..."

---

## Step 1 — Profile the main loop (find the hotspot)

Added per-function timers around computeAssignments / computeCentroids /
computeCost in the main while-loop.

| Function            | Time (ms) | Share |
|:--------------------|----------:|------:|
| computeAssignments  | 5457-5940 | ~68%  |
| computeCost         | 1535-1671 | ~19%  |
| computeCentroids    |  967-1048 | ~12%  |
| (iters)             | 24        |       |
| Total               | ~8000     |       |

Conclusion: **computeAssignments dominates (~68%)** and is the primary
target. It performs K x M = 3,000,000 dist() calls per iteration, each over
N=100 dims. Secondary suspicion: dist() uses pow(x, 2) (libm) instead of a
plain multiply, affecting all three functions.

(Note: 24 iterations, not the ~3-5 first guessed from the 6.76 s cold run —
in-loop work is what matters, fixed startup is negligible.)

---

## Step 2 — First cut: replace pow(diff, 2) with diff*diff in dist()

Rationale: dist() is called by all three functions; libm pow() is much
slower than a multiply. Math-identical, so functionality is unchanged.

| | Total (ms) | computeAssignments (ms) |
|:-|----------:|------------------------:|
| Step 1 baseline | ~8000 | ~5700 |
| Step 2 (mult)   | ~6690 | ~4550 |
| **Speedup**     | **1.19x** | 1.29x |

Smaller than expected — at -O3 the compiler already strength-reduces
pow(x,2) somewhat; the bulk of the cost is the 3M-calls-per-iter loop
itself, not pow. Correctness: end.log centroids identical to the starter
reference. Next target remains computeAssignments (still ~68%).

---

