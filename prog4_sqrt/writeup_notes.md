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
- **Multi-core (tasks / no-tasks): ~131/11.2 = ~11.7x.** More than the 8
  physical cores: the task system (64 tasks, span N/64) fills all 16 logical
  CPUs, and divergent masked-off lanes leave execution bubbles that the
  second SMT thread on each core can fill (same effect measured in
  Program 3: 12.1x multicore factor there).
- Total = SIMD x multicore ~ 5.0 x 11.7 ~ 58-65x, matching the reported
  task-ISPC speedups.

---
