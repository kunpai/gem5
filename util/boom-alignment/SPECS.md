# Implicit behaviour specs of BOOM v3, and how gem5 O3 measures up

These are timing behaviours that the BOOM RTL obeys but that no parameter states. They were
found by running the same bare-metal binaries on Verilated BOOM (SmallBoom and LargeBoom, v3)
and on gem5 O3, then explaining each gap from RTL source and RTL event counters. Each spec has
an executable check in `specs.py`; `results/spec_conformance.txt` is the current matrix.

| ID | Spec | Evidence | Stock gem5 | Fix |
|----|------|----------|-----------|-----|
| S1 | A bypassed ALU result wakes its dependents in the next cycle. | `core.scala` fast wakeup | conforms | none |
| S2 | Multiply and FP results wake dependents only at register-file writeback, so effective latency is pipeline stages + 3 (multiply 6, FMA 7). | `core.scala` slow wakeup; `imulStages=3`, `dfmaStages=4` | violates: chain cost equals `opLat` | parameter (`opLat` = effective latency) |
| S3 | Integer divide latency is 4 + (3 + msb(dividend) - msb(divisor)) cycles, +1 for a negative input, +1 for a negated result; divide by zero runs the full 65 iterations. | rocket-chip `Multiplier.scala`, 17 operand cases on RTL | violates: constant latency | code: `OpDesc.earlyOutDivider` |
| S4 | L1-hit load-to-use latency is 4 cycles. | measured | violates at default cache latency | parameter |
| S5 | The front end delivers one fetch packet per cycle even when a loop spans two packets. | `frontend.scala` F0 to F3 | violates on the 3-wide core: each packet switch pays the full I-cache latency | parameter (I-cache latency 1, depth moved to fetch-to-decode) |
| S6 | A taken branch predicted in the first stage costs no bubble. | `frontend.scala` F1 redirect | conforms | none |
| S7 | When the main predictor overrides the fast first-stage prediction, the packets fetched meanwhile are dropped. | `frontend.scala` F3 redirect; RTL counter `f2_clear` | violates on the 3-wide core | code: `fetchLateOverrideBubbles` |
| S8 | A load forwarding from a store whose data arrives late sleeps and is retried (2.7 retries per load); forwarding off the critical path is free. | RTL counters `ld_wakeup`, `ld_miss` | violates on the 3-wide core | code: `LSQForwardDelay` (approximation) |
| S9 | L1D misses overlap far less than the MSHR count suggests. | RTL counter `ld_wakeup` (about 8 retries per missing load) | violates | parameter (MSHRs halved; mechanism not modelled) |
| S10 | A mispredict costs about 12 cycles end to end. | random branch, alternating indirect jump | violates at default stage delays | parameter |
| S11 | FP divide and integer divide occupy their own units and do not block multiply/add. | separate `FDivSqrtUnit` / `DivUnit` | depends on FU pool written by the user | config |

## What generalises

On 15 held-out C workloads (30 cold/warm runs, SmallBoom), mean cycle error is 9.9% for stock
gem5, 42.5% with fitted parameters alone, and 4.2% with parameters plus patches. Parameter
fitting overfits wherever the true behaviour is a function (S3): the single divide latency that
fits one operand pair is wrong for every other.

On LargeBoom the same 30 runs give 18.4% stock, 55.9% parameters only, 11.9% with patches.
Two workloads show that a fix does not generalise: insertion sort is +56% because the constant
`LSQForwardDelay` charges every forwarded load, while the RTL (S8) only penalises loads whose
store data arrives late; the stencil is -38%, a store-heavy pattern over 320 KiB that no spec
here covers yet.

## Not yet explained

Call/return on SmallBoom (-25%), jump chain on LargeBoom (+26%), overlapping DRAM misses (+20%).

## Layout

`o3_boom.py` gem5 config (`--tuned` applies the fits), `cmp.py` / `heldout.py` / `specs.py`
scoring, `ubench/` benchmark sources, `rtl-harness/` Verilator patches and probes,
`results/` RTL measurements and counter dumps. BOOM RTL came pre-generated from
OpenXiangShan/gsim `ready-to-run`. Set `BOOM_ALIGN_ROOT` to the working directory.
