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
