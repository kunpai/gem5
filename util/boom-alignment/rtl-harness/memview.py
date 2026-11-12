#!/usr/bin/env python3
"""Summarise BOOM memory-side trace events per traced kernel: miss-handler occupancy, refusals, retries."""
import sys, statistics as st
from collections import Counter, defaultdict
NAMES = ["store_load","sl_chain2","sl_indep","call_ret","br_pattern","mul_dep","load_dep_l1","alu_indep","isort","load_indep_l2","load_dep_l2","store_l2","copy_l2"]
ST = "invalid refill_req refill_resp drain_loads meta_read meta_resp1 meta_resp2 meta_clear wb_meta_read wb_req wb_resp commit_line drain_rpq meta_write finish1 finish2 prefetched prefetch".split()
ev = [l.split() for l in open(sys.argv[1])]
segs, cur, last = [], [], None
for e in ev:
    c = int(e[1])
    if last is not None and c - last > 300: segs.append(cur); cur = []
    cur.append(e); last = c
segs.append(cur)
want = sys.argv[2:]
for name, seg in zip(NAMES, segs):
    if want and name not in want: continue
    c0, c1 = int(seg[0][1]), int(seg[-1][1]); K = Counter(e[0] for e in seg)
    print(f"\n== {name}: {c1 - c0} traced cycles; loads fired {K['LI']}, wakeup retries {K['LW']}, responses {K['LR']}, refusals {K['N']}, "
          f"bus requests {K['A']}, data beats {K['G']}, release beats {K['K']}, store commits {K['LS']}")
    # miss-handler occupancy: from leaving state 0 to returning to it
    busy, start, path, occ, per_state = {}, {}, defaultdict(list), [], defaultdict(list)
    lastchg = {}
    for e in seg:
        if e[0] != "M": continue
        c, i, s = int(e[1]), int(e[2]), int(e[3])
        if i in lastchg and i in start: per_state[lastchg[i][1]].append(c - lastchg[i][0])
        lastchg[i] = (c, s)
        if i not in start and s != 0: start[i] = c; path[i] = [s]
        elif i in start:
            if s == 0: occ.append((c - start[i], tuple(path[i]))); del start[i]
            else: path[i].append(s)
    if occ:
        clean = [o for o, p in occ if 10 not in p]; dirty = [o for o, p in occ if 10 in p]
        print(f"   miss handler occupancy: {len(occ)} misses; no writeback: n={len(clean)} mean {st.mean(clean) if clean else 0:.1f} cycles; "
              f"with victim writeback: n={len(dirty)} mean {st.mean(dirty) if dirty else 0:.1f} cycles")
        print("   mean cycles per state: " + ", ".join(f"{ST[s]} {st.mean(v):.1f}" for s, v in sorted(per_state.items()) if s != 0))
        # concurrency: how many handlers busy on average
        t = sorted((int(e[1]), int(e[2]), int(e[3])) for e in seg if e[0] == "M"); state = {}; area = 0; prev = c0; mx = 0
        for c, i, s in t:
            n = sum(1 for v in state.values() if v); area += n * (c - prev); prev = c; state[i] = (s != 0); mx = max(mx, sum(1 for v in state.values() if v))
        print(f"   handlers busy: mean {area / max(1, c1 - c0):.2f}, max {mx}")
    nk = Counter(e[2] for e in seg if e[0] == "N")
    if nk: print("   refusals by cause (victim,writeback,probe flags): " + ", ".join(f"{k or '000'}:{v}" for k, v in nk.items()) + "   (000 = no free handler)")
    lw = defaultdict(list)
    for e in seg:
        if e[0] == "LW": lw[e[2]].append(int(e[1]))
    gaps = [b - a for v in lw.values() for a, b in zip(v, v[1:]) if b - a < 40]
    if gaps: print(f"   interval between retries of the same load entry: " + ", ".join(f"{g} cycles x{n}" for g, n in Counter(gaps).most_common(4)))
