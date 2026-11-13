"""An O3 core sized and timed after BOOM v3."""
from m5.objects import (
    BranchPredictor,
    FUDesc,
    FUPool,
    IQUnit,
    LTAGE,
    OpDesc,
    ReturnAddrStack,
    RiscvO3CPU,
    SimpleBTB,
)
from m5.objects.FuncUnitConfig import System_Unit

from gem5.components.processors.base_cpu_core import BaseCPUCore
from gem5.isas import ISA

from .boommatched_params import (
    STRUCTURE,
    boom_timing,
)


def _fu_pool(P: dict, T: dict) -> FUPool:
    alu = FUDesc(opList=[OpDesc(opClass="IntAlu")], count=P["alu"])
    mul = FUDesc(opList=[OpDesc(opClass="IntMult", opLat=T["mul"])], count=1)
    # Separate unit: a busy divider does not block multiplies.
    div = FUDesc(
        opList=[OpDesc(opClass="IntDiv", opLat=T["div"], pipelined=False,
                       earlyOutDivider=bool(T["diveo"]))],
        count=1,
    )
    fp = FUDesc(
        opList=[
            OpDesc(opClass="FloatAdd", opLat=T["fadd"]),
            OpDesc(opClass="FloatCmp", opLat=2),
            OpDesc(opClass="FloatCvt", opLat=2),
            OpDesc(opClass="FloatMult", opLat=T["fmul"]),
            OpDesc(opClass="FloatMultAcc", opLat=5),
            OpDesc(opClass="FloatMisc", opLat=3),
        ],
        count=1,
    )
    # BOOM's FDivSqrt unit is separate from the FMA pipeline.
    fdiv = FUDesc(
        opList=[OpDesc(opClass="FloatDiv", opLat=T["fdiv"], pipelined=False),
                OpDesc(opClass="FloatSqrt", opLat=24, pipelined=False)],
        count=1,
    )
    rd = [OpDesc(opClass="MemRead"), OpDesc(opClass="FloatMemRead")]
    wr = [OpDesc(opClass="MemWrite"), OpDesc(opClass="FloatMemWrite")]
    if T["memfu"] == 1:
        # One memory port shared by loads and stores.
        mem = [FUDesc(opList=rd + wr, count=1)]
    else:
        mem = [FUDesc(opList=rd, count=1), FUDesc(opList=wr, count=1)]
    return FUPool(FUList=[alu, mul, div, fp, fdiv] + mem + [System_Unit()])


class BoomCore(BaseCPUCore):
    """One BOOM v3 core as a gem5 O3 CPU.

    :param variant: "small" (SmallBoom, 1-wide) or "large" (LargeBoom, 3-wide).
    :param calibrated: apply the timing derived from BOOM RTL. False gives the
                       structure sizes with gem5's default latencies.
    :param timing_overrides: individual timing keys to override (experiments).
    """

    def __init__(self, core_id: int = 0, variant: str = "small", calibrated: bool = True,
                 timing_overrides: dict | None = None) -> None:
        P = STRUCTURE[variant]
        T = boom_timing(variant, calibrated, timing_overrides)
        cpu = RiscvO3CPU(cpu_id=core_id)

        cpu.fetchWidth = P["fetch"]
        cpu.decodeWidth = cpu.renameWidth = cpu.dispatchWidth = cpu.commitWidth = P["width"]
        cpu.issueWidth = cpu.wbWidth = P["issue"]
        cpu.numROBEntries = P["rob"]
        cpu.LQEntries, cpu.SQEntries = P["lq"], P["sq"]
        cpu.numPhysIntRegs, cpu.numPhysFloatRegs = P["intreg"], P["fpreg"]
        cpu.fetchQueueSize = P["fq"]
        cpu.fetchBufferSize = P["fetch_buffer"]  # 4 / 8 instructions per fetch packet

        cpu.instQueues = [IQUnit(numEntries=P["iq"], fuPool=_fu_pool(P, T))]
        cpu.branchPred = BranchPredictor(
            conditionalBranchPred=LTAGE(),
            btb=SimpleBTB(numEntries=256, associativity=2),
            ras=ReturnAddrStack(numEntries=32),
        )

        cpu.LSQForwardDelay = T["fwd"]
        cpu.LSQResolveStoreAddrEarly = bool(T["sta"])
        cpu.LSQStoreDataRetryDelay = T["retry"]
        cpu.memDepPrediction = bool(T["mdp"])
        cpu.LSQDepCheckShift = T["dcs"]
        cpu.linkWriteLatency = T["link"]
        cpu.fetchLateOverrideBubbles = T["lob"]
        cpu.fetchToDecodeDelay, cpu.decodeToRenameDelay = T["f2d"], T["d2r"]
        cpu.renameToIEWDelay, cpu.issueToExecuteDelay = T["r2i"], T["i2e"]

        super().__init__(core=cpu, isa=ISA.RISCV)
