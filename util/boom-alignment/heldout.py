import sys, statistics as st, cmp
W = cmp.W
stages = [("baseline (sizes only)", []), ("+ parameters", ["--tuned", "--t", "diveo=0", "--t", "div=69", "--t", "fwd=0", "--t", "lob=0", "--t", "mh=0", "--t", "dcs=4", "--t", "memfu=2"]), ("+ code patches", ["--tuned"])]
for cfg in sys.argv[1:]:
    B = cmp.rd(f"{W}/results3_boom_{cfg}.txt"); cols = []
    for i, (name, extra) in enumerate(stages):
        G = cmp.run(cfg, extra, tag=f"ho{i}", suite="3")
        assert all(B[k][1] == G[k][1] for k in B), "instret mismatch"
        cols.append({k: (G[k][0] - B[k][0]) / B[k][0] * 100 for k in B})
    print(f"== held-out, {cfg}: cycle error vs BOOM RTL (baseline | +params | +patches)")
    for k in B: print(f"  {k:14s} boom={B[k][0]:8d} " + " ".join(f"{c[k]:+7.1f}%" for c in cols))
    for (name, _), c in zip(stages, cols):
        a = [abs(v) for v in c.values()]
        print(f"  {name:22s} mean|err| {st.mean(a):5.1f}%  median {st.median(a):4.1f}%  max {max(a):5.1f}%  within10%: {sum(x<=10 for x in a)}/{len(a)}")
