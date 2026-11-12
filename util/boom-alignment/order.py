"""Out-of-age-order service of missing loads in a gem5 pipe trace (independent L2-hit loads kernel)."""
import subprocess, re, sys, statistics as st
from collections import Counter
trace, elf = sys.argv[1], "/home/claude/work/ubench/utrace_gem5.elf"
nm=subprocess.run(["riscv64-unknown-elf-nm","-n",elf],capture_output=True,text=True).stdout
sym={l.split()[2]:int(l.split()[0],16) for l in nm.splitlines() if len(l.split())==3}
a=sym["k_load_indep"]
dis=subprocess.run(["riscv64-unknown-elf-objdump","-d",elf,f"--start-address={a}",f"--stop-address={a+64}"],capture_output=True,text=True).stdout
ldpc=[int(m.group(1),16) for m in re.finditer(r"^\s*([0-9a-f]+):.*\bld\b",dis,re.M)][0]
rs,de=sym["m5_reset_stats"],sym["m5_dump_stats"]; on=False; seg=[]; segs=[]
for l in open(trace):
    if l[0]=="#" or "|" not in l: continue
    t=l.split("|")[0].split(); pc=int(t[1],16)
    if rs<=pc<rs+16 and not on: on=True; seg=[]
    elif de<=pc<de+16 and on: on=False; segs.append(seg)
    elif on and pc==ldpc: seg.append((int(t[0]),int(t[9])))   # writeback tick of the load = data arrival
lds=segs[9]; res=[sum(1 for s2,c2 in lds if s2<s and c2>c) for s,c in lds]
print(f"none older waiting {100*sum(1 for x in res if x==0)/len(res):.0f}%, mean older waiting {st.mean(res):.2f}")
