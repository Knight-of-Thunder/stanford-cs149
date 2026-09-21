# Program 5 — Writeup Notes

Machine: AMD Ryzen 7 6800H (8C/16T, DDR5 dual-channel), WSL2.
N = 20M floats per array; saxpy: result = 2*X + Y.

---

## Task 1 — Baseline & why tasks barely help

### Measurements (min of 3, 3 process runs)

| Impl        | Time (ms) | Bandwidth* | GFLOPS |
|:------------|----------:|-----------:|-------:|
| ISPC (1 core)   | 10.9-11.6 | 25.7-27.3 GB/s | 3.4-3.7 |
| ISPC + tasks    | 7.5-7.7   | 38.7-39.6 GB/s | 5.2-5.3 |
| **Speedup from tasks** | | | **1.45-1.51x** |

*Bandwidth as the program counts it: TOTAL_BYTES = 4·N·4B (see extra credit).

### Evidence: the machine's bandwidth ceiling (STREAM-triad, same access pattern)

Scratch benchmark (a[i] = 2·b[i]+c[i], 20M floats, min of 4, 2 interleaved
rounds; GB/s counted at 16B/element like the program's 4N formula):

| Threads | GB/s @16B/elem |
|--------:|---------------:|
| 1       | 29.9 / 32.8 |
| 2       | 42.1 / 40.3 |
| 4       | 44.1 / 42.6 |
| 8       | 42.7 / 40.4 |
| 16      | 41.0 / 40.7 |

**The ceiling (~40-44 GB/s) is reached with only 2 threads.** More threads
do not raise bandwidth — the DRAM/memory controller saturates.

### Reconciliation

- Single-core saxpy: 27 GB/s ≈ single-thread triad (~30) → one core is
  already near its fill rate.
- With tasks: 39-40 GB/s ≈ the all-core ceiling (~42-44) → saxpy with tasks
  is already at ~92% of the machine's physical limit.
- The observed 1.45-1.51x is essentially ALL the headroom that exists
  (40/27 ≈ 1.5).

### Arithmetic-intensity view

2 FLOPs per 16 bytes moved = 0.125 FLOP/B. At 40 GB/s that yields 5 GFLOPS
(measured) vs the chip's ~500+ GFLOPS FP peak → **the CPU is ~1% busy
computing; the program is purely memory-bound.**

### Handout Q: can it be substantially improved? Near-linear speedup?

**No.** Near-linear (e.g. 8x with 8 cores) would require ~8×27 = 216 GB/s —
5x beyond the machine's DRAM ceiling. Cores share one memory system; once
its bandwidth is saturated (by 2 cores!), extra cores only queue. The only
real improvements come from *moving fewer bytes* (e.g. non-temporal stores
to skip the write-allocate read: 16→12 B/elem, theoretical max ~1.33x) —
extra-credit territory, still nowhere near linear.

### Metric caveat: the printed GB/s is an *effective* rate, not measured traffic

Both GB/s and GFLOPS are (algorithmic-model total) / (measured time):
traffic is *assumed* to be 16 B/element (2 reads + write-allocate), FLOPs
*assumed* 2/element. No hardware counters are involved. Verified with an
amortized triad (threads spawned once, inner reps): with N=1M (12 MB, fits
the 16 MB L3) the same formula yields **97 GB/s**, and with N=100k (L1/L2
hot) **144 GB/s** — both above the 76.8 GB/s DRAM physical limit, i.e.
fictitious as DRAM bandwidth because the cache supplied the data. Saxpy's
80 MB arrays make the model valid, so its 26-40 GB/s is genuine DRAM
traffic. (Also: measuring tiny workloads with per-measurement thread
spawn/join pollutes results with ~0.1 ms fixed overhead — amortize first.)

---

## Extra credit 1 — Why TOTAL_BYTES = 4·N·sizeof(float) is correct

Naively the kernel touches 3 words per element — read X[i], read Y[i],
write result[i] — which would give 3·N·4 bytes. The program counts a 4th
word, and it is correct. The reason is the cache's **write-allocate**
policy (read-for-ownership, RFO):

1. Caches operate on **64-byte lines**, not individual words, and the line
   is the unit of coherence: a store may modify only part of a line, so
   the cache must hold the *entire* line to write it back consistently.
2. Stores in compiled code are ordinary **write-back cached stores**. On a
   store miss (the line is not in cache), the memory system first **reads
   the full 64B line from DRAM into the cache**, merges the 4B store into
   it, and the dirty line is **written back to DRAM on eviction**.
3. Per element (sequential streaming, 16 floats per line, so each line is
   fetched once and evicted once — 64B/16 = 4B amortized per element):

   | Traffic per element | Bytes |
   |:--------------------|------:|
   | read X[i] (streamed, no reuse)      | 4 |
   | read Y[i] (streamed, no reuse)      | 4 |
   | write result[i]: RFO read of line   | 4 |
   | write result[i]: write-back of line | 4 |
   | **total**                           | **16 = 4 words** |

So the true DRAM traffic is 4·N·4B, exactly TOTAL_BYTES. (Our STREAM-triad
measurements counted 16B/element for the same reason.) The only way to
avoid the RFO read is to store in a way that does not require line
ownership — e.g. non-temporal streaming stores — which is precisely the
extra-credit-2 idea: it cuts traffic to 12B/elem, and at a fixed ~42 GB/s
byte limit that buys at most 16/12 ≈ 1.33x.

---
