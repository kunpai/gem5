import sys, itertools, concurrent.futures as cf, json
import cmp
BASE = ["--t","mul=6","--t","div=69","--t","fadd=7","--t","fmul=7","--t","fdiv=23","--t","l1i=1","--t","l1d=3"]
def one(args):
    cfg, kv, keys = args
    extra = BASE + [x for k, v in kv.items() for x in ("--t", f"{k}={v}")]
    tag = "sw_" + "_".join(f"{k}{v}" for k, v in kv.items())
    G = cmp.run(cfg, extra, tag=tag)
    B = cmp.rd(f"{cmp.W}/results_boom_{cfg}.txt")
    e = {k: (G[k][0] - B[k][0]) / B[k][0] * 100 for k in keys if k in G}
    return cfg, kv, e
def sweep(cfg, grid, keys, top=8):
    names = list(grid); combos = [dict(zip(names, c)) for c in itertools.product(*grid.values())]
    with cf.ThreadPoolExecutor(2) as ex:
        res = list(ex.map(one, [(cfg, c, keys) for c in combos]))
    res.sort(key=lambda r: sum(abs(x) for x in r[2].values()) if r[2] else 1e9)
    for cfg, kv, e in res[:top]:
        print(cfg, kv, " ".join(f"{k}={v:+.1f}" for k, v in e.items()), "| sum %.1f" % sum(abs(x) for x in e.values()))
    return res
if __name__ == "__main__":
    cfg = sys.argv[1]; grid = json.loads(sys.argv[2]); keys = sys.argv[3].split(",")
    sweep(cfg, grid, keys, top=int(sys.argv[4]) if len(sys.argv) > 4 else 8)
