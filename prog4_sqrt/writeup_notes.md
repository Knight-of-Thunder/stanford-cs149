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
  the single highly-predictable back-edge. ~10 vector uops spread over a
  >= 15-cycle dependent chain -> ~20-25% FP-pipe occupancy for one thread,
  consistent with the measured +~50% per-core throughput from SMT.
  Sources: agner.org instruction tables / uops.info (vmulps Zen 3: latency
  3, throughput 0.5 = 2 mul pipes); wikichip Zen 3 (FP pipes, 2-way SMT);
  Tullsen et al., ISCA 1995 (SMT fills issue slots); Hennessy & Patterson
  Ch. 3 (OoO / reservation stations).
- Total = SIMD x multicore ~ 5.0 x 12 ~ 58-65x, matching the reported
  task-ISPC speedups.

---
