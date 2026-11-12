#!/usr/bin/env python3
"""Implicit behaviour specs of BOOM v3, learned by differencing RTL against gem5 O3.

Each spec is a statement about timing that the RTL obeys but that is written down nowhere
as a parameter. It carries an executable check over microbenchmark observations, so any
model (the RTL itself, stock gem5, patched gem5) can be scored for conformance.
"""
import sys, cmp
W = cmp.W
WIDTH = {"small": 1, "large": 3}
N = dict(alu_dep=10000, alu_indep=10000, mul_dep=10000, div_dep=1500, br_loop=40000, br_random=8000, br_pattern=10000,
         call_ret=10000, indirect=10000, load_dep_l1=15000, load_dep_l2=6000, load_dep_mem=1500, load_indep_l1=15000,
         load_indep_l2=6000, load_indep_mem=1500, store_load=15000, fadd_dep=8000, fmul_dep=8000, fdiv_dep=2000,
         sl_chain2=6000, sl_indep=6000)
DIV = {  # name: (kind, dividend, divisor) for suite 2
    "div_62_1": ("div", 0x7fffffffffffffff, 3), "div_40_1": ("div", 1 << 40, 3), "div_20_1": ("div", 1 << 20, 3),
    "div_6_1": ("div", 100, 3), "div_1_20": ("div", 3, 1 << 20), "div_neg_pos": ("div", -(1 << 40), 3),
    "div_pos_neg": ("div", 1 << 40, -3), "div_neg_neg": ("div", -(1 << 40), -3), "div_by_zero": ("div", 1 << 40, 0),
    "div_zero_num": ("div", 0, 5), "divu_63_1": ("divu", 2**64 - 1, 3), "divu_40_1": ("divu", 1 << 40, 3),
    "rem_40_1": ("rem", 1 << 40, 3), "rem_neg_pos": ("rem", -(1 << 40), 3), "remu_40_10": ("remu", 1 << 40, 1000),
    "divw_30_1": ("divw", 1 << 30, 3), "divw_neg": ("divw", -(1 << 30), 3)}

def div_latency(kind, a, b):
    """S3: rocket-chip radix-2 early-out divider as instantiated by BOOM (fixed overhead 4)."""
    signed = "u" not in kind.rstrip("w")[-1:]; rem = kind.startswith("rem")
    ln, rn = signed and a < 0, signed and b < 0
    d, s = abs(a) if signed else a, abs(b) if signed else b
    msb = lambda v: v.bit_length() - 1 if v else 0
    e = (63 - (msb(d) - msb(s))) & 63
    it = 65 if (s == 0 or e == 0) else 66 - e
    neg_out = (ln if rem else ln != rn) and not (s == 0 and not rem)
    return 4 + it + (1 if (ln or rn) else 0) + (1 if neg_out else 0)

def per(res, k): return res[k][0] / N[k]
def near(x, y, tol=0.05): return abs(x - y) <= tol * y

SPECS = [
 ("S1", "Bypassed ALU results wake dependents in the next cycle: a dependent ALU chain costs 1 cycle per op.",
  "core.scala fast_wakeup for bypassable uops", lambda r, c, ref: near(per(r, "alu_dep"), max(8, 10 / WIDTH[c]))),
 ("S2", "Results of non-bypassable units (multiply, FP) wake dependents only at register-file writeback: "
        "effective latency = pipeline stages + 3 (multiply 3+3, FMA 4+3).",
  "core.scala slow wakeup path; imulStages=3, dfmaStages=4",
  lambda r, c, ref: near(per(r, "mul_dep") / 4, 6) and near(per(r, "fadd_dep") / 4, 7) and near(per(r, "fmul_dep") / 4, 7)),
 ("S3", "Integer divide latency is a function of the operands: 4 + (3 + msb|dividend| - msb|divisor|) iterations, "
        "+1 if an input is negative, +1 if the result is negated; divide-by-zero and tiny dividends run the full 65.",
  "rocket-chip Multiplier.scala (divEarlyOut)",
  lambda r, c, ref: all(near(r[k][0] / 400, div_latency(*v) + 1, 0.04) for k, v in DIV.items())),
 ("S4", "Load-to-use latency on an L1 hit is 4 cycles.", "measured",
  lambda r, c, ref: near(per(r, "load_dep_l1"), 8)),
 ("S5", "The front end delivers one fetch packet per cycle even when a loop body spans two packets "
        "(instruction-cache access is pipelined), so straight-line throughput reaches the core width.",
  "frontend.scala F0-F3 pipeline",
  lambda r, c, ref: near(per(r, "alu_indep"), 10 / WIDTH[c]) and near(per(r, "load_indep_l1"), 7 / WIDTH[c])),
 ("S6", "A taken branch predicted by the first-stage predictor costs no fetch bubble: a 2-instruction loop runs "
        "at one iteration per cycle on a core at least 2 wide.", "frontend.scala f1 redirect",
  lambda r, c, ref: near(per(r, "br_loop"), max(1.0, 2 / WIDTH[c]), 0.08)),
 ("S7", "When the main direction predictor disagrees with the fast first-stage prediction, the packets fetched "
        "in between are dropped (visible only when the core is wide enough to drain the fetch buffer).",
  "frontend.scala f3 redirect clears F1 and F2; RTL counter f2_clear",
  lambda r, c, ref: near(per(r, "br_pattern"), per(ref, "br_pattern"))),
 ("S8", "A load that forwards from a store whose data arrives late is put to sleep and retried: a "
        "store->load->add chain costs about 6.7 cycles on the 3-wide core, while forwarding off the critical path is free.",
  "RTL counters ld_wakeup (2.7 retries per load) and ld_miss",
  lambda r, c, ref: near(per(r, "store_load"), per(ref, "store_load"), 0.10) and near(per(r, "sl_chain2"), per(ref, "sl_chain2"), 0.10)),
 ("S9", "L1 data-cache misses overlap far less than the MSHR count suggests: independent L2-hit misses run at "
        "0.82x (2 MSHRs) and 0.44x (4 MSHRs) of the fully serialised cost.",
  "RTL counter ld_wakeup (about 8 retries per missing load)",
  lambda r, c, ref: near(per(r, "load_indep_l2") / per(r, "load_dep_l2"), per(ref, "load_indep_l2") / per(ref, "load_dep_l2"), 0.12)),
 ("S10", "A branch mispredict costs about 12 cycles end to end (resolve to first corrected instruction issued).",
  "measured with a 50% random branch and an alternating indirect jump",
  lambda r, c, ref: near(per(r, "br_random"), per(ref, "br_random")) and near(per(r, "indirect"), per(ref, "indirect"), 0.07)),
 ("S11", "FP divide takes 23 cycles for these operands and occupies its own unit; it does not block FP add/multiply.",
  "exu: FDivSqrtUnit separate from FPUUnit; measured", lambda r, c, ref: near(per(r, "fdiv_dep") / 2, 23)),
]

def load_boom(c):
    r = cmp.rd(f"{W}/results_boom_{c}.txt"); r.update(cmp.rd(f"{W}/results2_boom_{c}.txt")); return r
def run_gem5(c, extra, tag):
    r = cmp.run(c, extra, tag=tag); r.update(cmp.run(c, extra, tag=tag + "s2", suite="2")); return r

if __name__ == "__main__":
    models = [("BOOM RTL", None), ("gem5 stock", []), ("gem5 +params", ["--tuned", "--t", "diveo=0", "--t", "div=69", "--t", "fwd=0", "--t", "lob=0"]),
              ("gem5 +patches", ["--tuned"])]
    rows = {}
    for c in ("small", "large"):
        ref = load_boom(c)
        for mi, (name, extra) in enumerate(models):
            r = ref if extra is None else run_gem5(c, extra, f"spec{mi}")
            for sid, text, src, chk in SPECS:
                try: ok = bool(chk(r, c, ref))
                except Exception as e: ok = None
                rows.setdefault(sid, {})[(name, c)] = ok
    hdr = [f"{n} ({c[0].upper()})" for n, _ in models for c in ("small", "large")]
    print("spec  " + "  ".join(f"{h:>17s}" for h in hdr))
    for sid, text, src, chk in SPECS:
        print(f"{sid:5s} " + "  ".join(f"{('pass' if rows[sid][(n, c)] else 'FAIL' if rows[sid][(n, c)] is not None else 'n/a'):>17s}" for n, _ in models for c in ("small", "large")))
    for n, _ in models:
        tot = sum(1 for sid in rows for c in ("small", "large") if rows[sid][(n, c)]); print(f"{n}: {tot}/{2*len(SPECS)} spec checks pass")
