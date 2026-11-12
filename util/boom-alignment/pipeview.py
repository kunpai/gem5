#!/usr/bin/env python3
"""Line up per-instruction pipeline timing from BOOM RTL (boomtrace.log) and gem5 O3 (commitPipeTrace).

usage: pipeview.py <cfg small|large> <boomtrace.log> <gem5 trace> <boom elf> <gem5 elf> [bench ...]
"""
import sys, subprocess, re, bisect, statistics as st
cfg, btrace, gtrace, belf, gelf = sys.argv[1:6]; want = sys.argv[6:]
BLK = 16 if cfg == "small" else 32
BENCH = [("store_load", "k_store_load"), ("sl_chain2", "k_sl_chain2"), ("sl_indep", "k_sl_indep"), ("call_ret", "k_call_ret"),
         ("br_pattern", "k_br_pattern"), ("mul_dep", "k_mul_dep"), ("load_dep_l1", "k_load_dep"), ("alu_indep", "k_alu_indep"),
         ("isort", "w_isort_tr")]
def syms(elf):
    out = subprocess.run(["riscv64-unknown-elf-nm", "-n", elf], capture_output=True, text=True).stdout
    return [(int(l.split()[0], 16), l.split()[2]) for l in out.splitlines() if len(l.split()) == 3]
S = syms(gelf); addr = {n: a for a, n in S}; order = sorted(a for a, _ in S)
def rng(sym):
    a = addr[sym]; nxt = [x for x in order if x > a]; return a, (nxt[0] if nxt else a + 4096)
dis = {}
for l in subprocess.run(["riscv64-unknown-elf-objdump", "-d", "-M", "no-aliases", gelf], capture_output=True, text=True).stdout.splitlines():
    m = re.match(r"\s*([0-9a-f]+):\s+[0-9a-f]+\s+(.*)", l)
    if m: dis[int(m.group(1), 16)] = " ".join(m.group(2).split())[:26]

# ---- BOOM: rebuild per-instruction records from the event log ----
ev = [l.split() for l in open(btrace) if l[:1] in "FDICRX"]
segs, cur, last = [], [], None
for e in ev:
    c = int(e[1])
    if last is not None and c - last > 300: segs.append(cur); cur = []
    cur.append(e); last = c
if cur: segs.append(cur)
def boom_records(seg):
    F, live, done = [], {}, []
    for e in seg:
        k, c = e[0], int(e[1])
        if k == "F": F.append((c, int(e[2], 16)))
        elif k == "D":
            pc = int(e[2], 16); idx = int(e[3]); tf = None
            for fc, fpc in reversed(F[-40:]):
                if fc <= c and fpc <= pc < (fpc | (BLK - 1)) + 1: tf = fc; break
            live[idx] = dict(pc=pc, F=tf, D=c, I=[], C=None, R=None)
        elif k == "I":
            r = live.get(int(e[2]))
            if r: r["I"].append(c)
        elif k == "C":
            r = live.get(int(e[2]))
            if r and r["C"] is None: r["C"] = c
        elif k == "R":
            r = live.pop(int(e[2]), None)
            if r: r["R"] = c; r["lane"] = int(e[2]) & (3 if BLK == 32 else 0); done.append(r)
    done.sort(key=lambda r: (r["R"], r["lane"]))   # same-cycle commits print in arbitrary order
    return done

# ---- gem5 ----
G = []
for l in open(gtrace):
    if l[0] == "#" or "|" not in l: continue
    a, d = l.split("|", 1); t = a.split()
    G.append(dict(pc=int(t[1], 16), F=int(t[2]), De=int(t[3]), Rn=int(t[4]), D=int(t[5]), I=int(t[6]), C=int(t[7]), R=int(t[8])))
rs, de = addr["m5_reset_stats"], addr["m5_dump_stats"]
gsegs, cur, on = [], [], False
for r in G:
    if rs <= r["pc"] < rs + 16 and not on: on, cur = True, []
    elif de <= r["pc"] < de + 16 and on: on = False; gsegs.append(cur)
    elif on: cur.append(r)

def f(v, base): return "   ." if v is None or v < 0 else f"{v - base:4d}"
for bi, (name, sym) in enumerate(BENCH):
    if want and name not in want: continue
    if bi >= len(segs) or bi >= len(gsegs): break
    lo, hi = rng(sym)
    b = [r for r in boom_records(segs[bi]) if lo <= r["pc"] < hi]; g = [r for r in gsegs[bi] if lo <= r["pc"] < hi]
    n = min(len(b), len(g)); same = sum(1 for i in range(n) if b[i]["pc"] == g[i]["pc"])
    print(f"\n===== {name} ({cfg}): committed in kernel BOOM {len(b)}, gem5 {len(g)}, same pc at same position {same}/{n}")
    if n < 20: continue
    def rate(x): m = x[len(x) // 4: 3 * len(x) // 4]; return (m[-1]["R"] - m[0]["R"]) / (len(m) - 1)
    print(f"cycles per committed instruction (middle half): BOOM {rate(b):.2f}  gem5 {rate(g):.2f}")
    mid = n // 2
    # start the excerpt at a loop head: first backward jump target after the midpoint
    start = next((i + 1 for i in range(mid, n - 1) if b[i + 1]["pc"] < b[i]["pc"]), mid)
    L = next((i - start + 1 for i in range(start + 1, n - 1) if b[i + 1]["pc"] < b[i]["pc"] and b[i + 1]["pc"] == b[start]["pc"]), 12)
    rows = range(start, min(n, start + min(max(L, 4), 14) + 2))
    b0, g0 = b[start]["D"], g[start]["D"]
    print(f"{'pc':>9s} {'instruction':26s} | BOOM: fetch disp issue(s)      done commit | gem5: fetch  dec  ren disp issue done commit")
    for i in rows:
        x, y = b[i], g[i]; iss = ",".join(str(c - b0) for c in x["I"][:4]) or "."
        tag = "" if x["pc"] == y["pc"] else "  <-- pc differs"
        print(f"{x['pc']:9x} {dis.get(x['pc'], '?'):26s} |      {f(x['F'], b0)} {f(x['D'], b0)} {iss:>13s} {f(x['C'], b0)}   {f(x['R'], b0)} |      "
              f"{f(y['F'], g0)} {f(y['De'], g0)} {f(y['Rn'], g0)} {f(y['D'], g0)}  {f(y['I'], g0)} {f(y['C'], g0)}   {f(y['R'], g0)}{tag}")
    def avg(recs, a, bk, first=True):
        v = []
        for r in recs[len(recs) // 4: 3 * len(recs) // 4]:
            x = r[a] if not isinstance(r[a], list) else (r[a][0] if r[a] else None)
            y = r[bk] if not isinstance(r[bk], list) else ((r[bk][0] if first else r[bk][-1]) if r[bk] else None)
            if x is not None and y is not None and x >= 0 and y >= 0: v.append(y - x)
        return st.mean(v) if v else float("nan")
    print(f"mean stage gaps  fetch->dispatch  dispatch->first issue  last issue->done  done->commit   issues per instruction")
    print(f"   BOOM          {avg(b,'F','D'):8.2f}        {avg(b,'D','I'):8.2f}            {avg(b,'I','C',False):8.2f}      {avg(b,'C','R'):8.2f}        {st.mean(len(r['I']) for r in b):.2f}")
    print(f"   gem5          {avg(g,'F','D'):8.2f}        {avg(g,'D','I'):8.2f}            {avg(g,'I','C'):8.2f}      {avg(g,'C','R'):8.2f}        1.00")
