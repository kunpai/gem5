import statistics as st, cmp
W=cmp.W
V=[("calibrated so far",["--tuned"]),
   ("+ link latency 6",["--tuned","--t","link=6"]),
   ("+ shared memory port",["--tuned","--t","memfu=1"]),
   ("+ both",["--tuned","--t","link=6","--t","memfu=1"])]
for cfg in ("small","large"):
    for suite,label in (("","fitted"),("2","patch-validation"),("3","held-out")):
        B=cmp.rd(f"{W}/results{suite}_boom_{cfg}.txt")
        for i,(name,extra) in enumerate(V):
            G=cmp.run(cfg,extra,tag=f"v{i}",suite=suite); e={k:(G[k][0]-B[k][0])/B[k][0]*100 for k in B}
            a=[abs(v) for v in e.values()]; worst=sorted(e.items(),key=lambda kv:-abs(kv[1]))[:4]
            print(f"{cfg:5s} {label:16s} {name:22s} mean {st.mean(a):5.1f}%  within10 {sum(x<=10 for x in a):2d}/{len(a)}  worst: "+", ".join(f"{k} {v:+.0f}%" for k,v in worst))
