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
