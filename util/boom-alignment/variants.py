import statistics as st, cmp, sys
W=cmp.W
V=[("calibrated (as pushed)",["--tuned"]),
   ("+ byte-exact violation check",["--tuned","--t","dcs=0"]),
   ("+ store-address model r1",["--tuned","--t","dcs=0","--t","sta=1","--t","mdp=0","--t","retry=1"]),
   ("+ store-address model r2",["--tuned","--t","dcs=0","--t","sta=1","--t","mdp=0","--t","retry=2"]),
   ("store-addr r2, store sets on",["--tuned","--t","dcs=0","--t","sta=1","--t","retry=2"])]
for cfg in ("small","large"):
    for suite,label in (("","fitted"),("2","patch-validation"),("3","held-out")):
        B=cmp.rd(f"{W}/results{suite}_boom_{cfg}.txt")
        for i,(name,extra) in enumerate(V):
            G=cmp.run(cfg,extra,tag=f"v{i}",suite=suite); e={k:(G[k][0]-B[k][0])/B[k][0]*100 for k in B}
            a=[abs(v) for v in e.values()]; worst=sorted(e.items(),key=lambda kv:-abs(kv[1]))[:3]
            print(f"{cfg:5s} {label:16s} {name:30s} mean {st.mean(a):5.1f}%  within10 {sum(x<=10 for x in a):2d}/{len(a)}  worst: "+", ".join(f"{k} {v:+.0f}%" for k,v in worst))
