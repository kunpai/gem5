"""Run a bare-metal binary on the BOOM-matched stdlib board (gem5.prebuilt.boommatched).

  gem5 o3_boom.py --cfg large --tuned --binary prog.elf

--tuned applies the calibration derived from BOOM RTL; without it the board has BOOM's
structure sizes and gem5's default latencies. --t overrides one timing key (see
boommatched_params.py); --set runs a Python assignment with `board`, `cpu`, `icache`,
`dcache`, `l2` in scope, e.g. --set "cpu.commitPipeTrace='trace.log'".
o3_boom_raw.py is the original non-stdlib config, kept as the regression reference.
"""
import argparse
import os
import sys

import m5

try:
    from gem5.prebuilt.boommatched import BoomMatchedBoard
except ImportError:  # binary built before the package was added: import from the source tree
    here = os.path.dirname(os.path.realpath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "..", "src", "python", "gem5", "prebuilt"))
    from boommatched import BoomMatchedBoard

from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator

ap = argparse.ArgumentParser()
ap.add_argument("--cfg", choices=["small", "large"], default="small")
ap.add_argument("--binary", required=True)
ap.add_argument("--tuned", action="store_true", help="apply the calibration derived from BOOM RTL")
ap.add_argument("--t", action="append", default=[], help="override a timing key, key=value")
ap.add_argument("--set", action="append", default=[], help="python assignment, e.g. cpu.fetchToDecodeDelay=3")
args = ap.parse_args()

overrides = {}
for kv in args.t:
    k, v = kv.split("=")
    overrides[k] = v if k == "mem" else int(v)

board = BoomMatchedBoard(variant=args.cfg, calibrated=args.tuned, timing_overrides=overrides)
board.set_bare_metal_workload(BinaryResource(local_path=args.binary))

if args.set:
    # The caches exist only once the board has connected its components, which the
    # Simulator does in _pre_instantiate; apply the assignments right after that.
    _orig_pre = board._pre_instantiate

    def _pre(*a, **kw):
        root = _orig_pre(*a, **kw)
        ch = board.get_cache_hierarchy()
        scope = dict(board=board, cpu=board.get_processor().get_cores()[0].get_simobject(),
                     icache=ch.l1icache, dcache=ch.l1dcache, l2=ch.l2cache)
        for s in args.set:
            exec(s, scope)
        return root

    board._pre_instantiate = _pre

simulator = Simulator(board=board)
simulator.run()
print("EXIT:", simulator.get_last_exit_event_cause(), "tick", m5.curTick())
