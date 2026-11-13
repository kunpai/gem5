"""BOOM v3 cache hierarchy: private L1I and L1D, a 512 KiB L2, and the miss-handler model."""
from m5.objects import (
    BadAddr,
    Cache,
    L2XBar,
    Port,
    SystemXBar,
)

from gem5.components.boards.abstract_board import AbstractBoard
from gem5.components.cachehierarchies.abstract_cache_hierarchy import (
    AbstractCacheHierarchy,
)
from gem5.components.cachehierarchies.classic.abstract_classic_cache_hierarchy import (
    AbstractClassicCacheHierarchy,
)
from gem5.utils.override import overrides

from .boommatched_params import (
    STRUCTURE,
    boom_timing,
)


class BoomCacheHierarchy(AbstractClassicCacheHierarchy):
    """
    :param variant: "small" or "large"; sets L1 geometry (16 KiB 4-way / 32 KiB 8-way).
    :param calibrated: apply the latencies and miss-handler occupancy model derived
                       from BOOM RTL traces.
    :param timing_overrides: individual timing keys to override (experiments).
    """

    def __init__(self, variant: str = "small", calibrated: bool = True,
                 timing_overrides: dict | None = None) -> None:
        AbstractClassicCacheHierarchy.__init__(self=self)
        self._P = STRUCTURE[variant]
        self._T = boom_timing(variant, calibrated, timing_overrides)
        self.membus = SystemXBar(width=self._T["memw"])
        # Wrong-path accesses to unmapped addresses must not kill the simulation.
        self.membus.badaddr_responder = BadAddr()
        self.membus.default = self.membus.badaddr_responder.pio

    @overrides(AbstractClassicCacheHierarchy)
    def get_mem_side_port(self) -> Port:
        return self.membus.mem_side_ports

    @overrides(AbstractClassicCacheHierarchy)
    def get_cpu_side_port(self) -> Port:
        return self.membus.cpu_side_ports

    def _l1(self, lat: int, **kw) -> Cache:
        resp = lat if self._T["l1resp"] is None else self._T["l1resp"]
        return Cache(tag_latency=lat, data_latency=lat, response_latency=resp,
                     tgts_per_mshr=8, **kw)

    @overrides(AbstractCacheHierarchy)
    def incorporate_cache(self, board: AbstractBoard) -> None:
        P, T = self._P, self._T
        if board.get_processor().get_num_cores() != 1:
            raise Exception("BoomCacheHierarchy models a single-core BOOM tile.")
        core = board.get_processor().get_cores()[0]

        self.l1icache = self._l1(T["l1i"], size=P["l1i"], assoc=P["l1i_assoc"], mshrs=2)
        self.l1dcache = self._l1(T["l1d"], size=P["l1d"], assoc=P["l1d_assoc"],
                                 mshrs=T["l1mshr"])
        if T["mh"]:
            # Miss-handler occupancy model. The queue of waiting misses is deep (in BOOM
            # the load/store unit holds them); what is limited is how many handlers are
            # outstanding or finishing.
            d = self.l1dcache
            d.mshrs = 16
            d.miss_handlers = T["mh"]
            d.miss_handler_tail = T["mht"]
            d.miss_handler_writeback = T["mhw"]
            d.miss_handler_retry = T["mhr"]
            d.miss_handler_writeback_busy = T["mhb"]
            d.miss_handler_fill = T["mhf"]
            d.miss_handler_unordered = bool(T["mhu"])

        self.l2bus = L2XBar(width=T["l2w"], frontend_latency=T["l2busf"],
                            response_latency=T["l2busr"])
        self.l2cache = Cache(
            size="512KiB", assoc=8, tag_latency=T["l2"], data_latency=T["l2"],
            response_latency=T["l2"] if T["l2resp"] is None else T["l2resp"],
            mshrs=T["l2mshr"], tgts_per_mshr=8,
        )

        core.connect_icache(self.l1icache.cpu_side)
        core.connect_dcache(self.l1dcache.cpu_side)
        self.l1icache.mem_side = self.l2bus.cpu_side_ports
        self.l1dcache.mem_side = self.l2bus.cpu_side_ports
        self.l2cache.cpu_side = self.l2bus.mem_side_ports
        self.l2cache.mem_side = self.membus.cpu_side_ports

        # Page-table walkers go straight to the L2 bus (unused in bare-metal M-mode).
        walker_ports = core.get_mmu().walkerPorts()
        if len(walker_ports) == 1:
            core.connect_walker_ports(self.l2bus.cpu_side_ports, self.l2bus.cpu_side_ports)
        elif len(walker_ports) > 1:
            core.connect_walker_ports(self.l2bus.cpu_side_ports, self.l2bus.cpu_side_ports)
        core.connect_interrupt()

        for cntr in board.get_memory().get_memory_controllers():
            cntr.port = self.membus.mem_side_ports
        board.connect_system_port(self.membus.cpu_side_ports)
