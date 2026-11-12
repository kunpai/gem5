#!/usr/bin/env python3
"""Run gem5 O3 with a config and compare per-benchmark cycles against the BOOM RTL results."""
import subprocess, sys, statistics as st, os
W = os.environ.get("BOOM_ALIGN_ROOT", "/home/claude/work")
def rd(p):
    d = {}
    for l in open(p):
        t = l.split()
        if t and t[0] == "RES": d[t[1]] = (int(t[2]), int(t[3]))
    return d
def run(cfg, extra=(), binary=None, gem5=None, tag="tmp", cfgfile="o3_boom.py", suite=""):
    gem5 = gem5 or f"{W}/gem5/build/RISCV/gem5.fast"
    binary = binary or f"{W}/ubench/ubench{suite}_gem5.elf"
    out = f"{W}/g5/out_{tag}_{cfg}"
    r = subprocess.run([gem5, "-d", out, f"{W}/g5/{cfgfile}", "--cfg", cfg, "--binary", binary, *extra],
                       capture_output=True, text=True)
    open(out + ".txt", "w").write(r.stdout)
    if "DONE" not in r.stdout: print(r.stdout[-800:], r.stderr[-1500:])
    return rd(out + ".txt")
def table(cfg, G, boom=None, quiet=False):
    B = rd(boom or f"{W}/results_boom_{cfg}.txt"); errs = []
    for k in B:
        if k not in G: continue
        assert B[k][1] == G[k][1], ("instret mismatch", k)
        e = (G[k][0] - B[k][0]) / B[k][0] * 100; errs.append(abs(e))
        if not quiet: print(f"  {k:15s} boom={B[k][0]:7d} gem5={G[k][0]:7d} {e:+7.1f}%")
    print(f"[{cfg}] mean |err| {st.mean(errs):.1f}%  median {st.median(errs):.1f}%  max {max(errs):.1f}%  within 10%: {sum(e<=10 for e in errs)}/{len(errs)}")
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--gem5"); ap.add_argument("--tag", default="tmp")
    ap.add_argument("--cfgfile", default="o3_boom.py"); ap.add_argument("--quiet", action="store_true"); ap.add_argument("--suite", default="")
    ap.add_argument("--cfgs", default="small,large"); ap.add_argument("extra", nargs="*")
    a = ap.parse_args()
    for c in a.cfgs.split(","):
        table(c, run(c, a.extra, gem5=a.gem5, tag=a.tag, cfgfile=a.cfgfile, suite=a.suite), boom=f"{W}/results{a.suite}_boom_{c}.txt" if a.suite else None, quiet=a.quiet)
