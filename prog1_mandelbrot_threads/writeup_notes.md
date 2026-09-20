# Program 1 — Writeup Notes

Machine: AMD Ryzen 7 6800H, 8 physical cores / 16 threads (SMT), AVX2+FMA.
(Reference machine in the assignment is Intel i7-7700K, 4 cores / 8 threads, so
speedup-curve shape will differ from the handout's expectations — noted here.)

Image: 1600x1200, maxIterations=256. Timings are the min of 5 runs (as main.cpp does).

---

## Step 1 — Two-thread spatial decomposition (top/bottom half)

| Threads | View | Serial (ms) | Thread (ms) | Speedup |
|--------:|:----:|------------:|------------:|--------:|
| 2       | 1    | 356.6       | 175.0       | 2.04x   |

Observation: ~2x (even slightly super-linear). The Mandelbrot set is symmetric
about the real axis (y=0); VIEW 1's y-range [-1,1] is centered on 0, so the top
and bottom halves carry nearly identical work → the two threads finish at almost
the same time, giving a well-balanced ~2x.

---

## Step 2 — Generalized contiguous-block decomposition (2..8 threads)

Code: thread i computes contiguous row-block i; last thread absorbs the
remainder rows.

### VIEW 1 (contiguous blocks)

| Threads | Serial (ms) | Thread (ms) | Speedup |
|--------:|------------:|------------:|--------:|
| 2       | 398.8       | 179.0       | 2.23x   |
| 3       | 344.4       | 209.6       | **1.64x** |
| 4       | 341.4       | 144.6       | 2.36x   |
| 5       | 341.8       | 138.2       | 2.47x   |
| 6       | 344.4       | 108.7       | 3.17x   |
| 7       | 342.9       | 101.1       | 3.39x   |
| 8       | 343.0       | 85.5        | 4.01x   |

### VIEW 2 (contiguous blocks)

| Threads | Serial (ms) | Thread (ms) | Speedup |
|--------:|------------:|------------:|--------:|
| 2       | 300.5       | 146.5       | 2.05x   |
| 3       | 212.1       | 90.5        | 2.34x   |
| 4       | 203.2       | 78.2        | 2.60x   |
| 5       | 205.4       | 68.5        | 3.00x   |
| 6       | 204.2       | 60.7        | 3.36x   |
| 7       | 206.0       | 53.8        | 3.83x   |
| 8       | 204.3       | 48.5        | 4.21x   |

### Is speedup linear? No. Hypothesis:

Speedup is far from linear (8 threads only ~4x, not 8x). The cause is
**load imbalance**: with contiguous row-blocks the pixels are not equal
cost. The black interior of the Mandelbrot set costs the full 256
iterations per pixel, while pixels outside escape in a few iterations.
Whichever thread's block overlaps the heavy interior does most of the
work, and the whole render waits for that slowest thread.

The **3-thread dip in VIEW 1 (1.64x, below the 2-thread 2.23x)** is the
tell: in VIEW 1 the heavy interior sits in the vertical center of the
image. With 2 threads the top/bottom split is symmetric about y=0, so the
heavy center divides evenly -> balanced ~2x. With 3 threads the *middle*
block captures almost the entire heavy center while the top and bottom
blocks are cheap -> the middle thread dominates runtime -> speedup
collapses toward (total work / middle-block work) ~ 1.6x.

VIEW 2 is a zoomed-in region with a different (more even) spread of heavy
pixels across rows, so it shows no 3-thread dip and rises monotonically.

Step 3 will confirm this by timing each thread individually.

---

## Step 3 — Per-thread timing (confirms the load-imbalance hypothesis)

Added timestamps around the `mandelbrotSerial` call in `workerThreadStart`
and printed each thread's row-range and elapsed time.

### 3 threads, VIEW 1 (the anomaly)

| Thread | Rows        | Time (ms) |
|-------:|:------------|----------:|
| 0      | [0, 400)    | ~68       |
| 1      | [400, 800)  | **~213**  |
| 2      | [800, 1200) | ~72       |

The middle thread does ~3x the work of the edge threads. Total wall time
(211 ms) is set by thread 1 alone. Sum of per-thread times ~354 ms ~=
serial 352 ms (work isn't added, just unevenly split). Middle block is
~60% of the work, so speedup is capped near 354/213 ~ 1.66x -> matches the
measured 1.67x. Confirms: contiguous blocks put the heavy central body
almost entirely in one thread.

### 2 threads, VIEW 1 (balanced)

| Thread | Rows        | Time (ms) |
|-------:|:------------|----------:|
| 0      | [0, 600)    | 177.9     |
| 1      | [600, 1200) | 180.2     |

Nearly equal -> symmetric split about y=0 balances the load -> ~2x.

### 8 threads, VIEW 1 (severe imbalance)

| Thread | Rows          | Time (ms) |
|-------:|:--------------|----------:|
| 7      | [1050, 1200)  | 6.2       |
| 0      | [0, 150)      | 16.6      |
| 6      | [900, 1050)   | 31.7      |
| 1      | [150, 300)    | 42.4      |
| 5      | [750, 900)    | 63.9      |
| 2      | [300, 450)    | 69.3      |
| 3      | [450, 600)    | 93.2      |
| 4      | [600, 750)    | 96.0      |

Slowest/fastest ~= 15x. Wall time is bounded by the slowest thread (~96 ms,
the central rows 600-750), so 343/96 ~ 3.6x, close to the measured ~4x.
Threads owning the vertical-center blocks (3, 4) are heaviest; edge threads
(0, 7) are nearly idle.

### How this explains the speedup graph

The parallel time is set by the *slowest* thread, not the average. Because
the heavy interior clusters in the vertical center, contiguous row-blocks
give one (or few) central threads far more work than the rest. Adding
threads shrinks each block but the central block stays heavy relative to
the others, so speedup grows slowly and non-monotonically (the 3-thread
case is worst because a single middle block captures nearly the entire
heavy center). Fixing this needs a decomposition that spreads heavy rows
across all threads -> Step 4 (interleaving).

---

## Step 4 — Interleaved (round-robin) decomposition

Approach: thread i computes rows i, i+numThreads, i+2*numThreads, ...
(each thread loops with stride numThreads, calling mandelbrotSerial one row
at a time). This scatters the heavy central rows evenly across all threads,
so every thread gets a near-identical mix of heavy and cheap rows. No
synchronization is used (threads write disjoint rows), and the same single
policy works for every thread count. Row indices >= height are simply never
claimed, so height-not-divisible-by-numThreads is handled for free.

### Speedup: contiguous vs interleaved

| Threads | VIEW1 blocks | VIEW1 interleaved | VIEW2 blocks | VIEW2 interleaved |
|--------:|-------------:|------------------:|-------------:|------------------:|
| 2       | 2.23x        | 2.27x             | 2.05x        | 1.91x             |
| 3       | **1.64x**    | **2.90x**         | 2.34x        | 2.80x             |
| 4       | 2.36x        | 3.81x             | 2.60x        | 3.69x             |
| 5       | 2.47x        | 4.71x             | 3.00x        | 4.55x             |
| 6       | 3.17x        | 5.79x             | 3.36x        | 5.45x             |
| 7       | 3.39x        | 6.56x             | 3.83x        | 6.18x             |
| 8       | 4.01x        | **7.20x**         | 4.21x        | **6.64x**         |

Per-thread times are now balanced: e.g. 3 threads VIEW 1 = 122/122/122 ms
(was 68/213/72). The 3-thread dip is gone and speedup is monotonic and
near-linear (~0.9x per added thread).

**Final 8-thread speedup: VIEW 1 = 7.20x, VIEW 2 = 6.64x** (8 physical
cores, so 8x is the ceiling; ~90% / ~83% parallel efficiency). Meets the
"about 7-8x on both views" target.

---
