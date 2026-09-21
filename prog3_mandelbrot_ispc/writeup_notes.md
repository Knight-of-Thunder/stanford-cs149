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

## Part 2 — ISPC tasks: fix the 2-task bug

### 1. Baseline (starter code: rowsPerTask = height/2, launch[2])

| View  | Serial (ms) | ISPC (ms) | Task ISPC (ms) | Speedup vs serial |
|:-----:|------------:|----------:|---------------:|------------------:|
| 1     | 259.8       | 42.7      | 24.2           | 10.73x            |
| 2     | 152.6       | 28.4      | 17.6           | 8.67x             |

Only ~1.8x over no-task ISPC: two tasks can occupy at most two cores.

### 2. Benchmarking methodology (important!)

A first back-to-back sweep of 12 task counts gave unstable, misleading results:
the *serial baseline itself* drifted from ~260 ms down to ~150 ms across the
sweep. The laptop Ryzen (45W) boosts high when cool and throttles under
sustained load, so absolute ratios measured minutes apart are not comparable.
To cancel this drift we benchmarked candidates in interleaved rotation
(A,B,C,... repeated 3x, medians reported) so thermal state affects all
candidates equally. (Within a single invocation the three phases run
back-to-back, so that ratio is self-consistent.)

### 3. Task-count sweep (VIEW 1, median of 3 interleaved rounds)

| Tasks | Rows/task | Median speedup |
|------:|----------:|---------------:|
| 2     | 400       | ~12.1x (baseline) |
| 16    | 50        | 36.5x          |
| 32    | 25        | 67.2x          |
| 50    | 16        | **71.7x**      |
| 100   | 8         | 67.3x          |
| 160   | 5         | 67.3x          |
| 400   | 2         | 51.3x          |

Plateau at 32-160 tasks; 5-round head-to-head of the top three:
32 -> median 68.0x (min 59.8), 50 -> median 68.8x (min 63.3),
100 -> median 63.4x. **Chose 50 tasks x 16 rows.**

### 4. Why 50?

- The task system (common/tasksys.cpp) creates one worker per *logical* CPU
  (nThreads = sysconf(_SC_NPROCESSORS_ONLN) - 1, plus the main thread = 16
  workers here), pulling tasks from a shared queue.
- **Too few tasks (16 = 1/worker)**: no rebalancing slack. Tasks are
  contiguous row blocks and the center block is heavy (Program 1's load
  imbalance again) -> the slowest task caps the run (~36x).
- **~3 tasks per worker (50)**: when a worker finishes a cheap block it pulls
  the next task, dynamically smoothing the imbalance, while each task (16
  rows x 1200 px) is still large enough to amortize launch/scheduling
  overhead (~69x).
- **Too many tasks (400 x 2 rows)**: scheduling overhead per tiny task eats
  the gains (~51x).

### 5. Final results (50 tasks)

| View  | Serial (ms) | ISPC (ms) | Task ISPC (ms) | SIMD speedup | Total speedup |
|:-----:|------------:|----------:|---------------:|-------------:|--------------:|
| 1     | 151.3       | 25.3      | 2.10           | 5.98x        | **72.17x**    |
| 2     | 91.6        | 18.1      | 1.88           | 5.06x        | **48.68x**    |

Both views comfortably exceed the assignment's 32x target (which assumed the
4-core myth machines).

Note: total/ISPC = 72.2/5.98 = 12.1x on VIEW 1 — MORE than the 8 physical
cores. This is SMT at work: the task system fills all 16 logical CPUs. The
mechanism is NOT masked-lane bubbles (AVX2 instructions issue full-width;
diverged lanes are computed redundantly — divergence wastes lane output, not
issue slots) and not branch misprediction (loop exits are highly
predictable). It is the loop-carried FP dependency chain (z = f(z) per
iteration, ~15-20 cycles of latency with few independent ops) leaving most
FP issue slots unused by a single thread; the sibling SMT thread's
independent chain fills them. Verified in Program 4 with taskset: multicore
factor ~12x with 16 logical CPUs vs ~7.3x pinned to one thread per physical
core. Consistent with Program 1, where scalar 16 threads beat 8 threads by
~25% on the same compute-bound kernel.

---

## Extra credit — Thread abstraction vs ISPC task abstraction

### The two abstractions

- `std::thread` (Program 1): each thread is an **OS execution context** — its
  own stack (Linux default 8 MB), register state, kernel scheduling entity.
  Creating one is a heavyweight `clone()` syscall; `join()` blocks the caller
  until that *specific* thread exits.
- ISPC task (Program 3): a task is just a **logical unit of work** (a function
  pointer + small data descriptor) pushed onto a queue. A small persistent
  pool of worker threads — created once, roughly one per logical CPU — pulls
  tasks and runs them to completion. `launch` enqueues; the implicit `sync`
  at the end of the export function is a *collective* barrier over the whole
  launched set, not a per-task wait.

### Thought experiment: 10,000 threads vs 10,000 tasks

**10,000 threads** — the machine only has 8 cores, so at most ~16 run
simultaneously; the rest exist as pure overhead:
- Memory: 10,000 x 8 MB stacks = ~80 GB of address space (virtual, but with
  page-table and physical cost for touched pages).
- Creation cost: `clone()` + stack setup is tens of microseconds each ->
  seconds spent just creating, before any work.
- Scheduler collapse: 10,000 runnable entities on 8 cores means constant
  context switching (~µs each), cache/TLB thrashing, and run-queue lock
  contention — the kernel spends more time juggling threads than executing
  user code.

**10,000 ISPC tasks** — nothing dramatic happens:
- The 16 (or so) pool workers simply dequeue and execute them one after
  another. A task descriptor is tens of bytes -> a few MB total.
- No new OS contexts, no context switches beyond normal pool operation;
  "scheduling" is a queue pop (~sub-µs).
- Throughput is bounded by the cores, and per-task overhead is a small
  constant — exactly the regime where our sweep showed 400 tasks still
  performing at ~51x. The same count as threads would fall over.

### Why the difference matters (the subtle part)

The task abstraction **decouples logical parallelism from hardware
parallelism**: the program may express any number of independent pieces
(10,000), while the runtime multiplexes them onto the fixed hardware (8
cores) with dynamic load balancing — a worker that finishes early grabs the
next task (exactly how 50 tasks smoothed the heavy-center imbalance in
Part 2). With raw threads, mapping work to hardware is the programmer's job
(Program 1: we manually interleaved rows), and oversubscribing threads hurts
rather than helps.

Other implications:
- **Join vs sync**: per-thread joins make nested/recursive parallelism
  awkward (thread counts explode); collective task sync composes naturally
  (tasks may launch subtasks).
- **Preemption vs run-to-completion**: OS threads are time-slice preempted
  and can block on I/O for long periods safely. ISPC tasks assume short,
  compute-bound, non-blocking work — a blocking task would monopolize a
  worker, since the pool has no spare threads. So tasks trade generality
  for cheapness.
- **Scheduling granularity**: ISPC tasks additionally each carry a SIMD gang
  (programCount lanes), so the same runtime manages both levels of the
  machine's parallelism (cores + vector units); threads address only cores.

One line: a thread is an *execution resource* you allocate; a task is a
*piece of work* you describe. 10,000 of the former exhausts the OS; 10,000
of the latter is just a long queue.

---
