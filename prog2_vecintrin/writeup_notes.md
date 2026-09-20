# Program 2 — Writeup Notes

Machine: AMD Ryzen 7 6800H. This program uses CS149's *fake* vector
intrinsics (simulated in CS149intrin.cpp), so results are independent of the
host CPU's real SIMD width. "Performance" = Total Vector Instructions;
utilization = fraction of vector lanes active across all vector instructions.

---

## Task 1 — Vectorize clampedExpSerial -> clampedExpVector

Approach:
- Process the array in batches of VECTOR_WIDTH lanes.
- Per batch: result = 1.0 in all lanes; multiply by x once per unit of the
  exponent, masking off lanes whose exponent counter has reached 0. Looping
  until every lane is done naturally handles the per-lane variable trip count
  (SIMD divergence). Starting from 1.0 also folds in the y==0 case.
- Clamp lanes > 9.999999 with a compare-mask + masked set.
- Tail (N % VECTOR_WIDTH != 0): init count to 0 in all lanes, then load only
  the first `width` lanes via _cs149_init_ones(width); unused lanes are never
  loaded/stored, so no out-of-bounds access.

Correctness (VECTOR_WIDTH = 4):

| Test          | Result   | Total Vec Instr | Utilization |
|---------------|----------|----------------:|------------:|
| ./myexp -s 3  | Passed   | 36              | 86.1%       |
| ./myexp -s 16 | Passed   | 155             | 86.8%       |
| ./myexp -s 10000 | Passed | 97071          | 82.7%       |

-s 3 exercises the N < VECTOR_WIDTH tail path and passes (no out-of-bounds
write reported by verifyResult).

---
