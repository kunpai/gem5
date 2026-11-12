"""Add event counters to the (already patched) BOOM SV. UART byte 0x01 snapshots, 0x02 prints deltas."""
import re, sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()
T = "TestHarness.chiptop0.system.tile_prci_domain.element_reset_domain_boom_tile"
PROBES = [  # (module, instance path, [(name, expr-of-signals)])
    ("BoomFrontend", T + ".frontend", [("f1clr", "f1_clear"), ("f2clr", "f2_clear"), ("f4clr", "f4_clear"),
                                       ("f1red", "f1_do_redirect"), ("f2red", "f2_do_redirect")]),
    ("BoomCore", T + ".core", [("misp", "b2_mispredict"), ("flush", "_rob_io_flush_valid"),
                               ("sfb0", "dec_fire_0 & _decode_units_0_io_deq_uop_is_sfb"),
                               ("sfb1", "dec_fire_1 & _decode_units_1_io_deq_uop_is_sfb"),
                               ("sfb2", "dec_fire_2 & _decode_units_2_io_deq_uop_is_sfb")]),
    ("LSU", T + ".lsu", [("ldinc", "will_fire_load_incoming_0_will_fire"), ("ldretry", "will_fire_load_retry_0_will_fire"),
                         ("ldwake", "will_fire_load_wakeup_0_will_fire"), ("fwd", "wb_forward_valid_0"),
                         ("ldmiss", "io_core_ld_miss")]),
    ("ICache", T + ".frontend.icache", [("icrefill", "refill_fire")]),
]
refs = []
for mod, path, plist in PROBES:
    i = s.index("module %s(" % mod); j = s.index("\nendmodule", i); body = s[i:j]
    add = ""
    for name, expr in plist:
        sigs = re.findall(r"[A-Za-z_]\w*", expr)
        if not all(re.search(r"^\s*(?:wire|reg|input|output)\s+(?:\[[^\]]+\]\s+)?" + re.escape(g) + r"\b", body, re.M) for g in sigs):
            print("skip", mod, name); continue
        add += f"\n  reg [63:0] cnt_{name}; always @(posedge clock) if ({expr}) cnt_{name} <= cnt_{name} + 64'd1;"
        refs.append((name, f"{path}.cnt_{name}"))
    s = s[:j] + add + s[j:]
decl = "".join(f"  reg [63:0] snap_{n};\n" for n, _ in refs)
snap = "".join(f" snap_{n} <= {p};" for n, p in refs)
fmt = " ".join(f"{n}=%0d" for n, _ in refs)
args = ", ".join(f"{p} - snap_{n}" for n, p in refs)
old = "$finish;\n      else $write"
assert s.count(old) == 1
m = re.search(r"if \((\S+) == 8'h04\) \$finish;", s); bits = m.group(1)
s = s.replace(f"      if ({bits} == 8'h04) $finish;\n      else $write(\"%c\", {bits});",
 f"      if ({bits} == 8'h04) $finish;\n      else if ({bits} == 8'h01) begin{snap} end\n      else if ({bits} == 8'h02) $write(\"PROBE {fmt}\\n\", {args});\n      else $write(\"%c\", {bits});")
k = s.index("  always @(posedge clock) begin\n    if (~reset & ("); s = s[:k] + decl + s[k:]
open(dst, "w").write(s); print("probes:", [n for n, _ in refs])
