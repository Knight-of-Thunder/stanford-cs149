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

## Task 2 — Utilization vs VECTOR_WIDTH (./myexp -s 10000)

Changed `#define VECTOR_WIDTH` in CS149intrin.h, rebuilt, and re-ran:

| VECTOR_WIDTH | Total Vec Instr | Vector Utilization |
|-------------:|----------------:|-------------------:|
| 2            | 167515          | 87.9%              |
| 4            | 97071           | 82.7%              |
| 8            | 52877           | 80.0%              |
| 16           | 27592           | 78.8%              |

**Utilization DECREASES as VECTOR_WIDTH increases** (and the decrease shrinks,
approaching an asymptote).

Why: all the wasted lane-slots come from the multiply loop, which is
data-divergent. Exponents are uniform in [0, 9]. A batch's loop runs
max(exponents in that batch) iterations, and on iteration k only lanes with
exponent >= k are still active; lanes that already finished sit idle (masked)
for the rest of the loop. As VECTOR_WIDTH grows, (1) the maximum exponent
within a batch tends to be larger (max of more samples), so the loop runs
longer, and (2) more lanes are idle during those extra "tail" iterations.
Both raise the fraction of wasted lane-slots, so average utilization falls.
The non-divergent instructions (load/store/vset/clamp) are always fully
utilized; only the divergent loop loses lanes.

(Total Vector Instructions roughly halves each time the width doubles, since
each instruction now does twice the work — that's the SIMD speedup, separate
from utilization.)

---

