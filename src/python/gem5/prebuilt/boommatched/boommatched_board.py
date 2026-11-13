"""A prebuilt board matched to BOOM v3 RTL (SmallBoom / LargeBoom), for bare-metal binaries.

The board mirrors the RTL test harness used for the alignment work: one core, 256 MiB of
memory at 0x80000000, no devices, M-mode programs that print through semihosting and use
m5 ops to reset/dump stats and exit.

    board = BoomMatchedBoard(variant="large")
    board.set_bare_metal_workload(BinaryResource(local_path="prog.elf"))
    Simulator(board=board).run()
"""
from m5.objects import (
    AddrRange,
    IOXBar,
    PciHost,
    Port,
    RiscvBareMetal,
    RiscvSemihosting,
)

from gem5.components.boards.abstract_system_board import AbstractSystemBoard
from gem5.components.memory.simple import SingleChannelSimpleMemory
from gem5.resources.resource import BinaryResource
from gem5.utils.override import overrides

from .boommatched_cache import BoomCacheHierarchy
from .boommatched_params import boom_timing
from .boommatched_processor import BoomProcessor


_MEM_BASE = 0x80000000  # where the RTL harness loads programs


class BoomMatchedBoard(AbstractSystemBoard):
    """
    :param variant: "small" (SmallBoom) or "large" (LargeBoom).
    :param calibrated: True applies the timing derived from BOOM RTL; False keeps
                       BOOM's structure sizes with gem5's default latencies.
    :param timing_overrides: individual timing keys to override (experiments).
    """

    def __init__(self, variant: str = "small", calibrated: bool = True,
                 timing_overrides: dict | None = None, clk_freq: str = "1GHz",
                 mem_size: str = "256MiB") -> None:
        T = boom_timing(variant, calibrated, timing_overrides)
        self._variant = variant
        super().__init__(
            clk_freq=clk_freq,
            processor=BoomProcessor(variant, calibrated, timing_overrides, clk_freq),
            memory=SingleChannelSimpleMemory(
                latency=T["mem"], latency_var="0ns", bandwidth="12.8GiB/s", size=mem_size
            ),
            cache_hierarchy=BoomCacheHierarchy(variant, calibrated, timing_overrides),
        )

    def get_variant(self) -> str:
        return self._variant

    def set_bare_metal_workload(self, binary: BinaryResource) -> None:
        """Run a bare-metal RISC-V ELF linked at 0x80000000, with semihosting enabled."""
        if self.is_workload_set():
            raise Exception("Workload has been set more than once!")
        self.set_is_workload_set(True)
        self._set_fullsystem(True)
        self.workload = RiscvBareMetal(
            bootloader=binary.get_local_path(), semihosting=RiscvSemihosting()
        )

    @overrides(AbstractSystemBoard)
    def _setup_board(self) -> None:
        pass

    @overrides(AbstractSystemBoard)
    def _setup_memory_ranges(self) -> None:
        memory = self.get_memory()
        self.mem_ranges = [AddrRange(_MEM_BASE, size=memory.get_size())]
        memory.set_memory_range(self.mem_ranges)

    @overrides(AbstractSystemBoard)
    def has_io_bus(self) -> bool:
        return False

    @overrides(AbstractSystemBoard)
    def get_io_bus(self) -> IOXBar:
        raise NotImplementedError("BoomMatchedBoard has no IO bus.")

    @overrides(AbstractSystemBoard)
    def has_pci_host(self) -> bool:
        return False

    @overrides(AbstractSystemBoard)
    def get_pci_host(self) -> PciHost:
        raise NotImplementedError("BoomMatchedBoard has no PCI host.")

    @overrides(AbstractSystemBoard)
    def has_dma_ports(self) -> bool:
        return False

    @overrides(AbstractSystemBoard)
    def get_dma_ports(self) -> list[Port]:
        raise NotImplementedError("BoomMatchedBoard has no DMA ports.")

    @overrides(AbstractSystemBoard)
    def has_coherent_io(self) -> bool:
        return False

    @overrides(AbstractSystemBoard)
    def get_mem_side_coherent_io_port(self) -> Port:
        raise NotImplementedError("BoomMatchedBoard has no coherent IO.")
