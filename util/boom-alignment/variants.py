import statistics as st, cmp, sys
W=cmp.W
MH={"small":["--t","mh=2","--t","mht=9","--t","mhf=8","--t","mhw=13","--t","mhb=24","--t","mhr=4"],"large":["--t","mh=4","--t","mht=9","--t","mhf=4","--t","mhw=8","--t","mhb=18","--t","mhr=4"]}
V=[("calibrated so far",lambda c:["--tuned"]),
   ("+ miss-handler model",lambda c:["--tuned"]+MH[c])]
for cfg in ("small","large"):
    for suite,label in (("","fitted"),("3","held-out")):
        B=cmp.rd(f"{W}/results{suite}_boom_{cfg}.txt")
        for i,(name,ex) in enumerate(V):
            G=cmp.run(cfg,ex(cfg),tag=f"v{i}",suite=suite)
            if not G: print(cfg,label,name,"RUN FAILED"); continue
            e={k:(G[k][0]-B[k][0])/B[k][0]*100 for k in B}
            a=[abs(v) for v in e.values()]
            mem=[k for k in e if any(x in k for x in ("_l2","_mem","stencil","list","hash","str_"))]
            print(f"{cfg:5s} {label:9s} {name:26s} mean {st.mean(a):5.1f}%  within10 {sum(x<=10 for x in a):2d}/{len(a)}  | "+" ".join(f"{k.replace('load_','ld_').replace('_warm','_w').replace('_cold','_c')} {e[k]:+.0f}" for k in mem))
