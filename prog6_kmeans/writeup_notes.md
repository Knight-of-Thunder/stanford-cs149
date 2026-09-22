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

## Step 3 — Parallelize computeAssignments with std::thread (8 threads)

The starter loops centroid-major (k outer, m inner) sharing a per-point
minDist[] array. To parallelize safely I restructured it point-major (m
outer, k inner) and split the M points across 8 threads: each point m is
written by exactly one thread, so there is NO synchronization and no shared
minDist[] (it becomes a per-point local). Main thread does chunk 0; 7
std::threads do the rest; join at the end. Only computeAssignments is
parallelized (satisfies the "parallelize only one function" rule).

| Stage | Total (ms) | computeAssignments (ms) |
|:------|-----------:|------------------------:|
| Step 1 baseline        | ~8000 | ~5700 |
| Step 2 (pow->mult)     | ~6690 | ~4550 |
| **Step 3 (8 threads)** | **~2770** | **~580** |

- computeAssignments: 4550 -> 580 ms = **7.8x** (near-linear on 8 cores;
  it's compute-bound with disjoint writes, so it scales well).
- **Total speedup vs original starter: 8000/2770 = 2.89x** — exceeds the
  2.1x target.

Correctness verified: end.log centroids identical to the starter reference,
and plot.py produces the expected 3-cluster figure (red-star centroids at
cluster centers, matching the handout).

Now the bottleneck has shifted: computeCost (~1280 ms, ~46%) and
computeCentroids (~890 ms) dominate the remaining 2.77 s. Further gains
would need parallelizing those too, but the rules allow only one function —
so 2.89x is the final result. (The pow->mult cut in Step 2 legitimately
helped all three; only the threading is restricted to one function.)

---


