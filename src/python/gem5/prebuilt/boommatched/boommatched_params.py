"""Structure sizes and timing of BOOM v3 (SmallBoom, LargeBoom) for the BOOM-matched board.

``STRUCTURE`` is read out of the generated SystemVerilog. ``DEFAULT_TIMING`` is what a user
gets by copying structure sizes only (gem5 defaults). ``CALIBRATED`` holds the values derived
from BOOM RTL source and traces; see util/boom-alignment/SPECS.md for the spec behind each.
Several calibrated values rely on parameters added on the boom-alignment branch
(earlyOutDivider, LSQForwardDelay, fetchLateOverrideBubbles, miss_handler_*).
"""

STRUCTURE = {
    "small": dict(fetch=4, width=1, rob=32, iq=24, issue=3, lq=8, sq=8, intreg=52, fpreg=48,
                  fq=8, ftq=16, alu=1, fetch_buffer=16,
                  l1d="16KiB", l1d_assoc=4, l1i="16KiB", l1i_assoc=4, mshr=2),
    "large": dict(fetch=8, width=3, rob=96, iq=72, issue=5, lq=24, sq=24, intreg=100, fpreg=96,
                  fq=24, ftq=32, alu=3, fetch_buffer=32,
                  l1d="32KiB", l1d_assoc=8, l1i="32KiB", l1i_assoc=8, mshr=4),
}

_COMMON = dict(mul=6, div=4, diveo=1, fadd=7, fmul=7, fdiv=23, l1i=1, l1d=3, l1resp=1,
               l2resp=1, mem="2ns", r2i=3, fwd=3, lob=1, dcs=0)
CALIBRATED = {
    "small": dict(_COMMON, l2=12, l1mshr=1, f2d=2,
                  mh=2, mht=9, mhf=8, mhw=13, mhb=24, mhr=4, mhu=1),
    "large": dict(_COMMON, l2=10, l1mshr=2, f2d=4, memfu=1,
                  mh=4, mht=9, mhf=4, mhw=8, mhb=18, mhr=4, mhu=1),
}


def default_timing(variant: str) -> dict:
    return dict(mul=3, div=20, fadd=2, fmul=4, fdiv=12, l1i=2, l1d=2, l2=10, mem="30ns",
                f2d=1, d2r=1, r2i=2, i2e=1, l2mshr=8, l1mshr=STRUCTURE[variant]["mshr"],
                l1resp=None, l2resp=None, l2w=32, memw=16, l2busf=1, l2busr=1,
                diveo=0, fwd=0, lob=0, sta=0, retry=1, mdp=1, dcs=4, memfu=2, link=0,
                mh=0, mht=0, mhw=0, mhr=0, mhb=0, mhf=0, mhu=0)


def boom_timing(variant: str, calibrated: bool = True, overrides: dict | None = None) -> dict:
    """Timing values for a variant: gem5 defaults, optionally the calibrated set, then overrides."""
    if variant not in STRUCTURE:
        raise ValueError(f"unknown BOOM variant '{variant}', expected one of {list(STRUCTURE)}")
    t = default_timing(variant)
    if calibrated:
        t.update(CALIBRATED[variant])
    for k, v in (overrides or {}).items():
        if k not in t:
            raise KeyError(f"unknown timing key '{k}'")
        t[k] = v
    return t
