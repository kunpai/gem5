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

On LargeBoom the same 30 runs give 18.4% stock, 53.5% parameters only, and 8.8% with patches,
the byte-exact ordering check (S12) and the single memory port (S15). The stencil is still -38%: RTL counters show about
119,000 load wakeups for 241,000 loads, i.e. the miss-retry behaviour behind S9, which is only
approximated by a halved MSHR count.

## Specs read from lsu.scala (memory ordering)

| ID | Spec | Stock gem5 | Status |
|----|------|-----------|--------|
| S12 | Ordering violations are detected at byte granularity (doubleword match plus byte mask). | violates: `LSQDepCheckShift=4` compares 16-byte blocks, so neighbouring array elements raise false violations, which then train the store-set predictor to serialise the loop | fixed by parameter (`LSQDepCheckShift=0`); insertion sort on LargeBoom goes from +56% to -20% |
| S13 | Loads never wait for a store by prediction. Store addresses resolve independently of store data; a load matching a store whose data is late stays un-executed and is re-fired every third cycle; a load passing a store with unknown address is flushed on a later match. | violates: address and data resolve together; loads wait on PC-indexed store sets | prototype (`LSQResolveStoreAddrEarly`, `memDepPrediction`) builds and is functionally correct but is NOT faithful yet: it retries 4 to 5 times per load where the RTL retries 2.7 times, and does not improve cycle error. Off by default and not part of the calibration. |

## Specs found by lining up per-instruction pipeline traces

`rtl-harness/trace_sv.py` logs fetch, dispatch, issue, completion and commit per ROB entry in
the RTL; gem5's `commitPipeTrace` logs the same stages at commit; `pipeview.py` aligns them.
Every committed instruction matched one-to-one in all traced kernels. Example timelines are in
`results/traces/`.

| ID | Spec | Evidence | Status |
|----|------|----------|--------|
| S14 | The link register written by JAL/JALR is not bypassed: a reader issues 6 cycles after the jump. | trace of call/return; `decode.scala` marks JAL/JALR not bypassable | real, but NOT the cause of the call/return gap. `linkWriteLatency` models it but also delays the jump's own resolution, which makes indirect-jump mispredicts 28 to 36% too slow. Not adopted. |
| S15 | There is one memory issue port. A store issues through it twice when its address and data become ready at different times. | trace of insertion sort on LargeBoom: memory queue never issues more than 1 uop per cycle and is 83% busy | adopted for LargeBoom as a single load/store functional unit (held-out mean 9.7% to 8.8%, stencil -40% to -32%). The double issue of stores is not modelled. On SmallBoom the shared unit makes the store-to-load chain 20% too slow, so it is not applied there. |
| S16 | Dependents of a load are issued speculatively assuming a hit and re-issued if the value is late. With a late-data forward, the re-issue comes 4 or 8 cycles after the store data issues, alternating. | trace of the store-to-load chain on LargeBoom | observed, not modelled. The constant forwarding delay matches the average only. |

The call/return gap on SmallBoom (-25%) is a front-end effect: dispatch stalls about 3 cycles
per iteration after jumps. The tracer does not yet log the fetch stages, so the rule is unknown.

## Not yet explained

Call/return on SmallBoom (-25%), jump chain on LargeBoom (+26%), overlapping DRAM misses (+20%).

## Layout

`o3_boom.py` gem5 config (`--tuned` applies the fits), `cmp.py` / `heldout.py` / `specs.py`
scoring, `ubench/` benchmark sources, `rtl-harness/` Verilator patches and probes,
`results/` RTL measurements and counter dumps. BOOM RTL came pre-generated from
OpenXiangShan/gsim `ready-to-run`. Set `BOOM_ALIGN_ROOT` to the working directory.
