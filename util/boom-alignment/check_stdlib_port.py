#!/usr/bin/env python3
"""Regression: the stdlib BOOM-matched board must give the same cycle and instruction counts
as the original raw config (o3_boom_raw.py) on every suite, both variants, stock and calibrated."""
import cmp, sys
ok = True
for suite in ("", "2", "3"):
    for cfg in ("small", "large"):
        for name, extra in (("stock", []), ("calibrated", ["--tuned"]), ("override", ["--tuned", "--t", "mh=0", "--t", "fwd=0", "--t", "mem=30ns"])):
            a = cmp.run(cfg, extra, tag="port_raw", suite=suite, cfgfile="o3_boom_raw.py")
            b = cmp.run(cfg, extra, tag="port_std", suite=suite, cfgfile="o3_boom.py")
            diff = [k for k in a if a[k] != b.get(k)]
            same = bool(a) and not diff and len(a) == len(b)
            ok &= same
            print(f"suite{suite or '1'} {cfg:5s} {name:10s} {len(a):2d} results  {'identical' if same else 'DIFFERENT: ' + ', '.join(f'{k} {a[k][0]} vs {b.get(k, (None,))[0]}' for k in diff[:4])}")
print("PORT OK" if ok else "PORT MISMATCH"); sys.exit(0 if ok else 1)
