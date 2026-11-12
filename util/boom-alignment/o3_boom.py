"""gem5 O3 configured from BOOM v3 structure sizes (SmallBoom / LargeBoom), bare-metal M-mode.

Only knobs that exist as O3 parameters are set from the RTL; everything else is gem5 default
unless overridden with --set (used later to test which gaps are closable by parameters).
"""
import argparse
import m5
from m5.objects import *

ap = argparse.ArgumentParser()
ap.add_argument("--cfg", choices=["small", "large"], default="small")
ap.add_argument("--binary", required=True)
ap.add_argument("--tuned", action="store_true", help="apply latencies fitted against BOOM RTL")
ap.add_argument("--t", action="append", default=[], help="override a fitted value, key=value")
ap.add_argument("--set", action="append", default=[], help="python assignment on `system`, e.g. cpu.fetchToDecodeDelay=3")
args = ap.parse_args()

_COMMON = dict(mul=6, div=4, diveo=1, fadd=7, fmul=7, fdiv=23, l1i=1, l1d=3, l1resp=1, l2resp=1, mem="2ns", r2i=3, fwd=3, lob=1, dcs=0)
TUNED = {   # fitted against BOOM v3 RTL (see cmp.py); fwd needs the LSQForwardDelay patch
    "small": dict(_COMMON, l2=12, l1mshr=1, f2d=2, mh=2, mht=9, mhf=8, mhw=13, mhb=24, mhr=4),
    "large": dict(_COMMON, l2=10, l1mshr=2, f2d=4, memfu=1, mh=4, mht=9, mhf=4, mhw=8, mhb=18, mhr=4),
}

P = {
    # values read out of the generated SystemVerilog
    "small": dict(fetch=4, width=1, rob=32, iq=24, issue=3, lq=8, sq=8, intreg=52, fpreg=48,
                  fq=8, ftq=16, alu=1, l1d="16KiB", l1d_assoc=4, l1i="16KiB", l1i_assoc=4, mshr=2),
    "large": dict(fetch=8, width=3, rob=96, iq=72, issue=5, lq=24, sq=24, intreg=100, fpreg=96,
                  fq=24, ftq=32, alu=3, l1d="32KiB", l1d_assoc=8, l1i="32KiB", l1i_assoc=8, mshr=4),
}[args.cfg]

# Latencies. "default" = what a user gets by copying structure sizes only.
T = dict(mul=3, div=20, fadd=2, fmul=4, fdiv=12, l1i=2, l1d=2, l2=10, mem="30ns",
         f2d=1, d2r=1, r2i=2, i2e=1, l2mshr=8, l1mshr=P["mshr"], l1resp=None, l2resp=None, l2w=32, memw=16,
         l2busf=1, l2busr=1, diveo=0, fwd=0, lob=0, sta=0, retry=1, mdp=1, dcs=4, memfu=2, link=0, mh=0, mht=0, mhw=0, mhr=0, mhb=0, mhf=0, mhu=0)
if args.tuned:
    T.update(TUNED[args.cfg])
for kv in args.t:
    k, v = kv.split("=")
    T[k] = v if k == "mem" else int(v)

system = System()
system.clk_domain = SrcClockDomain(clock="1GHz", voltage_domain=VoltageDomain())
system.mem_mode = "timing"
system.mem_ranges = [AddrRange(0x80000000, size="256MiB")]

cpu = RiscvO3CPU()
system.cpu = cpu
cpu.fetchWidth = P["fetch"]
cpu.decodeWidth = cpu.renameWidth = cpu.dispatchWidth = cpu.commitWidth = P["width"]
cpu.issueWidth = cpu.wbWidth = P["issue"]
cpu.numROBEntries = P["rob"]
cpu.LQEntries, cpu.SQEntries = P["lq"], P["sq"]
cpu.numPhysIntRegs, cpu.numPhysFloatRegs = P["intreg"], P["fpreg"]
cpu.fetchQueueSize = P["fq"]
cpu.fetchBufferSize = 16 if args.cfg == "small" else 32   # BOOM fetches 4 / 8 instructions per packet


class BoomALU(FUDesc):
    opList = [OpDesc(opClass="IntAlu")]
    count = P["alu"]

class BoomMul(FUDesc):
    opList = [OpDesc(opClass="IntMult", opLat=T["mul"])]
    count = 1

class BoomDiv(FUDesc):      # separate unit: a busy divider does not block multiplies
    opList = [OpDesc(opClass="IntDiv", opLat=T["div"], pipelined=False, earlyOutDivider=bool(T["diveo"]))]
    count = 1

class BoomFP(FUDesc):
    opList = [OpDesc(opClass="FloatAdd", opLat=T["fadd"]), OpDesc(opClass="FloatCmp", opLat=2),
              OpDesc(opClass="FloatCvt", opLat=2), OpDesc(opClass="FloatMult", opLat=T["fmul"]),
              OpDesc(opClass="FloatMultAcc", opLat=5), OpDesc(opClass="FloatMisc", opLat=3),
              ]
    count = 1

class BoomFDiv(FUDesc):     # BOOM's FDivSqrt unit is separate from the FMA pipeline
    opList = [OpDesc(opClass="FloatDiv", opLat=T["fdiv"], pipelined=False),
              OpDesc(opClass="FloatSqrt", opLat=24, pipelined=False)]
    count = 1

class BoomLoad(FUDesc):
    opList = [OpDesc(opClass="MemRead"), OpDesc(opClass="FloatMemRead")]
    count = 1

class BoomStore(FUDesc):
    opList = [OpDesc(opClass="MemWrite"), OpDesc(opClass="FloatMemWrite")]
    count = 1

class BoomMem(FUDesc):     # one memory port shared by loads and stores (LargeBoom mem issue width is 1)
    opList = [OpDesc(opClass="MemRead"), OpDesc(opClass="FloatMemRead"),
              OpDesc(opClass="MemWrite"), OpDesc(opClass="FloatMemWrite")]
    count = 1

class BoomFUPool(FUPool):
    FUList = [BoomALU(), BoomMul(), BoomDiv(), BoomFP(), BoomFDiv()] + ([BoomMem()] if T["memfu"] == 1 else [BoomLoad(), BoomStore()]) + [System_Unit()]

cpu.instQueues = [IQUnit(numEntries=P["iq"], fuPool=BoomFUPool())]

cpu.branchPred = BranchPredictor(
    conditionalBranchPred=LTAGE(),
    btb=SimpleBTB(numEntries=256, associativity=2),
    ras=ReturnAddrStack(numEntries=32),
)


def L1(lat, **kw):
    resp = lat if T["l1resp"] is None else T["l1resp"]
    return Cache(tag_latency=lat, data_latency=lat, response_latency=resp, tgts_per_mshr=8, **kw)

cpu.icache = L1(T["l1i"], size=P["l1i"], assoc=P["l1i_assoc"], mshrs=2)
cpu.dcache = L1(T["l1d"], size=P["l1d"], assoc=P["l1d_assoc"], mshrs=T["l1mshr"])
if T["mh"]:
    # miss-handler occupancy model: the queue of waiting misses is deep (the LSU holds them in
    # BOOM); what is limited is how many handlers are outstanding or finishing
    cpu.dcache.mshrs = 16
    cpu.dcache.miss_handlers = T["mh"]
    cpu.dcache.miss_handler_tail = T["mht"]
    cpu.dcache.miss_handler_writeback = T["mhw"]
    cpu.dcache.miss_handler_retry = T["mhr"]
    cpu.dcache.miss_handler_writeback_busy = T["mhb"]
    cpu.dcache.miss_handler_fill = T["mhf"]
    cpu.dcache.miss_handler_unordered = bool(T["mhu"])
cpu.LSQForwardDelay = T["fwd"]
cpu.LSQResolveStoreAddrEarly = bool(T["sta"])
cpu.LSQStoreDataRetryDelay = T["retry"]
cpu.memDepPrediction = bool(T["mdp"])
cpu.LSQDepCheckShift = T["dcs"]
cpu.linkWriteLatency = T["link"]
cpu.fetchLateOverrideBubbles = T["lob"]
cpu.fetchToDecodeDelay, cpu.decodeToRenameDelay = T["f2d"], T["d2r"]
cpu.renameToIEWDelay, cpu.issueToExecuteDelay = T["r2i"], T["i2e"]
system.l2bus = L2XBar(width=T["l2w"], frontend_latency=T["l2busf"], response_latency=T["l2busr"])
system.l2 = Cache(size="512KiB", assoc=8, tag_latency=T["l2"], data_latency=T["l2"], response_latency=T["l2"] if T["l2resp"] is None else T["l2resp"],
                  mshrs=T["l2mshr"], tgts_per_mshr=8)
system.membus = SystemXBar(width=T["memw"])
cpu.icache.cpu_side = cpu.icache_port
cpu.dcache.cpu_side = cpu.dcache_port
cpu.icache.mem_side = system.l2bus.cpu_side_ports
cpu.dcache.mem_side = system.l2bus.cpu_side_ports
system.l2.cpu_side = system.l2bus.mem_side_ports
system.l2.mem_side = system.membus.cpu_side_ports
cpu.createThreads()
cpu.createInterruptController()
system.mem_ctrl = SimpleMemory(range=system.mem_ranges[0], latency=T["mem"])
system.mem_ctrl.port = system.membus.mem_side_ports
system.system_port = system.membus.cpu_side_ports
# wrong-path accesses to unmapped addresses must not kill the simulation
system.membus.badaddr_responder = BadAddr()
system.membus.default = system.membus.badaddr_responder.pio
system.workload = RiscvBareMetal(bootloader=args.binary, semihosting=RiscvSemihosting())

for s in args.set:
    exec("system." + s)

root = Root(full_system=True, system=system)
m5.instantiate()
ev = m5.simulate()
print("EXIT:", ev.getCause(), "tick", m5.curTick())
