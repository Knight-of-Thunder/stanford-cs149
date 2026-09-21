# Program 3 — Writeup Notes

Machine: AMD Ryzen 7 6800H, 8 cores / 16 threads, AVX2 (8-wide floats).
ISPC v1.28.1, `--target=avx2-i32x8` (as in the Makefile), `--opt=disable-fma`
(per Makefile comment, to match the reference output). Image 1200x800,
maxIterations=256. Times are min of 3 runs (as main.cpp does).
Assignment's reference machine is a 4-core i7-7700K; absolute speedup targets
differ on 8 cores — noted per section.

---

## Part 1 — ISPC basics, single-core SIMD (no tasks)

### Question: what maximum speedup do you expect, and why is the observed number lower?

The compiler emits 8-wide AVX2 vector code, and per the handout we can assume
about as many 8-wide vector FP units as scalar FP units on one core. So the
**ideal SIMD speedup is 8x** on a single core (no tasks yet — one gang mapped
to SIMD lanes on one core).

Measured:

| View  | Serial (ms) | ISPC (ms) | Speedup | Fraction of ideal 8x |
|:-----:|------------:|----------:|--------:|---------------------:|
| 1     | 249.9       | 43.2      | 5.78x   | 72%                   |
| 2     | 155.2       | 31.4      | 4.95x   | 62%                   |

### Why less than 8x: SIMD divergence (same phenomenon as Program 2)

A gang of 8 program instances executes in lockstep — one vector instruction
does the same step for 8 pixels at once. Each pixel's `mandel()` loop runs
until that pixel escapes (up to 256 iterations). When the 8 pixels in a gang
have different escape counts, the gang must iterate until the LONGEST one
finishes; finished lanes are masked off and idle for the remaining
iterations. Those idle lane-slots are wasted execution → utilization < 100% →
speedup < 8x.

### Why VIEW 2 (4.95x) is worse than VIEW 1 (5.78x)

Divergence only hurts where neighboring pixels differ in cost:
- VIEW 1: large uniform-cost regions — the deep interior (all pixels hit the
  256 cap, uniform → no divergence) and the far exterior (all escape after
  few iterations → little divergence). Only the thin boundary ring has
  high cost variance.
- VIEW 2: zooms into the boundary/filament region, where iteration counts
  vary sharply pixel-to-pixel. Nearly every gang contains both cheap and
  expensive pixels → severe divergence almost everywhere.

So the boundary-heavy view wastes more SIMD lanes, confirming the divergence
explanation. (5.78/8 = 72% lane utilization on VIEW 1 vs 62% on VIEW 2.)

---
