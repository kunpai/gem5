"""A single-core processor of BoomCore."""
from gem5.components.processors.base_cpu_processor import BaseCPUProcessor

from .boommatched_core import BoomCore


class BoomProcessor(BaseCPUProcessor):
    def __init__(self, variant: str = "small", calibrated: bool = True,
                 timing_overrides: dict | None = None, clk_freq: str = "1GHz") -> None:
        self._variant = variant
        super().__init__(
            cores=[BoomCore(core_id=0, variant=variant, calibrated=calibrated,
                            timing_overrides=timing_overrides)],
            clk_freq=clk_freq,
        )

    def get_variant(self) -> str:
        return self._variant
