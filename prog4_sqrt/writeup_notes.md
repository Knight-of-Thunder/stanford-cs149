# Program 4 — Writeup Notes

Machine: AMD Ryzen 7 6800H, 8 cores / 16 threads, AVX2. ISPC v1.28.1,
`--target=avx2-i32x8` (8-wide). N = 20,000,000 floats, initialGuess = 1.0,
tolerance 1e-5. Newton iteration for 1/y^2 - x = 0; output = x * y = sqrt(x).
Iteration count depends on x: 0 iters at x=1 (guess is exact), grows toward
x->0 and largest near x=3 (~20 iters). Times are min of 3 in-process runs;
3 process runs shown for stability.

---

## Task 1 — Baseline (starter input: uniform random in [0.001, 2.999])

| Run | Serial (ms) | ISPC (ms) | Task ISPC (ms) | SIMD speedup | Total speedup |
|----:|------------:|----------:|---------------:|-------------:|--------------:|
| 1   | 659.9       | 132.8     | 11.37          | 4.97x        | 58.06x        |
| 2   | 651.1       | 129.3     | 11.11          | 5.04x        | 58.62x        |
| 3   | 659.2       | 131.1     | 10.11          | 5.03x        | 65.20x        |

### Speedup decomposition

- **SIMD (single core, no tasks): ~5.0x** vs ideal 8x -> ~63% lane
  utilization. Uniform-random input means iteration counts vary widely
  across the 8 lanes of a gang (from ~0-1 iters near x=1 to ~20 near x=3),
  so gangs iterate until the slowest lane converges; finished lanes idle.
  Same divergence phenomenon as Program 3's mandel().
- **Multi-core (tasks / no-tasks): ~131/10.8 = ~12x.** More than the 8
  physical cores because the task system (64 tasks, span N/64) fills all 16
  logical CPUs. Verified directly with taskset (interleaved A/B runs):

  | CPUs available | Task-ISPC (ms) | Multicore factor |
  |:--------------|---------------:|-----------------:|
  | 16 logical (SMT on)  | 10.0-11.6 | ~12x  |
  | 8 physical (0,2,4,...,14 — one per core, siblings idle) | 17.4-18.0 | ~7.3x |

  **Why SMT helps — mechanism (important correction):** NOT branch
  misprediction (the while-exit branch is highly predictable: ~1 mispredict
  per gang amortized over ~20 iterations, negligible), and NOT masked-off
  lanes leaving bubbles (AVX2 vector instructions always issue full-width;
  converged lanes are computed redundantly / blended — divergence wastes
  vector-lane *output*, not issue slots). The real source is the
  **loop-carried floating-point dependency chain**: guess_{n+1} = f(guess_n)
  stalls ~15-20 cycles per iteration on FP latency with only ~5 FP ops to
  offer, so one thread sustains only ~25-30% of the core's FP issue slots.
  The sibling SMT thread's independent Newton chain fills those slots.
  Cross-evidence: Program 1's *scalar* C++ mandelbrot (no SIMD, no masks)
  showed the same +25-27% from 16 vs 8 threads.

  Direct evidence from our own binary (`objdump -d objs/sqrt_ispc.o`): the
  Newton loop body is four back-to-back `vmulps` all serialized on the same
  `%ymm13` (>= 3-cycle latency each on Zen 3 per Agner Fog's tables), then a
  `vblendvps` that overwrites converged lanes with their old values — i.e.
  full-width instructions execute for converged lanes redundantly
  (divergence wastes lane output, not issue slots), and the only branch is
  the single highly-predictable back-edge. Occupancy arithmetic: 4 chained
  muls x 3 cyc = >=12 cycles; one full iteration ~17-20 cycles issuing ~5
  muls -> mul-pipe occupancy 5/(2 pipes x 17 cyc) ~= **15%** (corrects the
  earlier ~25-30% estimate). Theory bounds SMT gain in (1x, 2x) and, being
  far from saturation, predicts close to 2x.

  **Co-residency experiment (two processes, ispc-no-tasks phase):**

  | Placement | ispc time each |
  |:---------|:---------------|
  | solo (1 process on cpu0)                      | 131-133 ms |
  | same core (cpu0 + sibling cpu1, concurrently) | 133-135 ms |
  | different cores (cpu0 + cpu2, concurrently)   | 133-134 ms |

  Two latency-bound Newton loops sharing one core via SMT interfere ~zero:
  per-core compute throughput ~2x, matching the 15%-occupancy prediction.

  **What actually caps the multicore factor: DVFS (power-limited
  frequency), not scheduling.** Two further experiments:
  1. N-scaling (20M -> 80M): per-core factors unchanged (1.51 -> 1.47 at 16
     logical; 0.92 -> 0.89 at 8 physical). A fixed task-launch/wake cost
     would amortize with N; it didn't -> the deficit is per-byte/per-cycle,
     not fixed overhead.
  2. Frequency test (cpu0 single-thread ispc, cpu0's SMT sibling idle in
     all cases, so no direct resource sharing):

     | Chip state | cpu0 ispc time | relative speed |
     |:-----------|:---------------|:---------------|
     | idle                          | 130.4 ms | 1.00 (max boost) |
     | other 7 physical cores loaded | 152.0 ms | 0.86 |
     | other 14 logical CPUs loaded  | 182.7 ms | 0.71 |

     The 45W laptop chip throttles as the power budget is spread across
     cores. Reconciliation: 16-logical per-core factor = 2 x 0.714 = 1.43
     (measured 1.47); 8-physical = 0.857 (measured 0.90). The speedup
     denominator (ispc-no-tasks) is measured at single-core boost, so
     multicore speedups on this chip are structurally capped by DVFS.
     (Also explains Program 3's 12.1x multicore factor on the same chip.)
  The tasksys busy-wait tail (source FIXME: "extra wasteful in a world
  with hyper-threading") and per-launch sem_posts remain minor µs-scale
  effects. Earlier attribution of the gap to "task-system overhead" was
  wrong — corrected by the N-scaling experiment.
  Sources: agner.org instruction tables / uops.info (vmulps Zen 3: latency
  3, throughput 0.5 = 2 mul pipes); wikichip Zen 3 (FP pipes, 2-way SMT);
  Tullsen et al., ISCA 1995 (SMT fills issue slots); Hennessy & Patterson
  Ch. 3 (OoO / reservation stations).
- Total = SIMD x multicore ~ 5.0 x 12 ~ 58-65x, matching the reported
  task-ISPC speedups.

---

## Task 2 — Input that maximizes speedup: all values = 2.999f

Every element set to 2.999f (worst convergence in the valid range, ~20
Newton iterations): the serial denominator is maximized AND every gang lane
converges in lockstep -> zero SIMD divergence.

| Metric | Baseline (random) | All 2.999f |
|:-------|------------------:|-----------:|
| Serial (ms)             | ~655    | ~1363 (2.08x slower) |
| SIMD speedup (no tasks) | 5.0x    | **6.6-6.7x**  |
| Multicore factor (tasks/no-tasks) | ~11.7-12x | ~11.5x |
| Total speedup           | 58-65x  | **74.5-78.9x** |

Answers to the handout's questions:
- **Does it improve SIMD speedup?** Yes: 5.0x -> 6.6-6.7x (~82% of the
  ideal 8x). With zero divergence all lanes stay active; the remaining gap
  is per-iteration overhead (compare/mask/blend/test instructions issue
  every iteration even when all lanes are active) and gang loop control.
- **Does it improve multi-core speedup (the benefit of adding tasks)?**
  No: ~11.5x vs ~11.7-12x baseline, essentially unchanged. Divergence is an
  intra-core lane-level property; how much tasks help depends on core
  count / SMT / DVFS, not on the input's per-element iteration spread.

---

## Task 3 — Input that minimizes ISPC (no-tasks) speedup

Input: period-8 pattern — `(i % 8 == 0) ? 2.999f : 1.0f`, i.e. 1 slow
element (~20 Newton iterations) + 7 instant-converging elements per gang.
Serial skips through 7/8 of the array almost free, but every 8-lane gang is
held hostage by its single slow lane and iterates ~20 times with 7/8 of the
lanes masked off. Pattern period 8 => exactly one slow element per gang no
matter how foreach maps iterations to lanes.

| Metric | Value |
|:-------|------:|
| Serial (ms)   | ~186   |
| ISPC (ms)     | ~202 (== all-2.999f's 205 ms, as predicted) |
| **Speedup**   | **0.91-0.93x — vector is SLOWER than serial** |

The reason for the loss of efficiency: the gang's while loop runs
max(iterations in gang) times; masked-off lanes idle but still cost
full-width compare/blend/test instructions each iteration, so the vector
unit does ~8x the useful work's instruction issue for 1/8 the useful
lanes. SIMD is worse than useless under extreme divergence.

### Divergence trend across all three constructed inputs

| Input pattern | Lane utilization (theory) | SIMD speedup (measured) |
|:--------------|--------------------------:|------------------------:|
| all 2.999f (uniform, 20 iters)   | 100%  | 6.6-6.7x |
| alternating 4 slow + 4 fast      | 52.5% | 3.33x    |
| 1 slow + 7 fast (period 8)       | ~17%  | **0.92x**|

Measured speedup ~= 8 x utilization x ~0.8 overhead factor across all
three points — the divergence model quantitatively matches. (With tasks
the worst case recovers to ~11x total, since multicore scaling is
unaffected by intra-gang divergence.)

---
