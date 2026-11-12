"""Add a per-instruction pipeline event trace to the patched BOOM SV.
UART byte 0x01 turns tracing on, 0x02 off. Events go to boomtrace.log:
  F cyc pc            fetch packet enters the fetch buffer
  D cyc pc rob_idx    instruction dispatched (enters ROB)
  I cyc rob_idx q     issued from int (q=0) or mem (q=1) issue queue
  C cyc rob_idx       ROB entry no longer busy (result written back)
  R cyc rob_idx       committed
  X cyc rob_idx       ROB entry freed without commit (squashed)
"""
import re, sys
src, dst, width = sys.argv[1], sys.argv[2], int(sys.argv[3])
s = open(src).read()
U = "TestHarness.chiptop0.system.uartClockDomainWrapper.uart_0"
ON, CY, FD = f"{U}.trace_on", f"{U}.tcyc", f"{U}.tfd"
def modspan(name):
    i = s.index("module %s(" % name); return i, s.index("\nendmodule", i)
def declared(body, sig):
    return re.search(r"^\s*(?:wire|reg|input|output)\s+(?:\[[^\]]+\]\s+)?" + re.escape(sig) + r"\b", body, re.M) is not None
def append(name, text):
    global s
    i, j = modspan(name); s = s[:j] + text + s[j:]

# --- UART: gate, cycle counter, file handle ---
m = re.search(r"else if \((\S+) == 8'h01\)", s)
if m:   # probe build already present
    raise SystemExit("apply to the non-probe SV")
m = re.search(r"if \((\S+) == 8'h04\) \$finish;\n      else \$write\(\"%c\", \S+\);", s); bits = m.group(1)
s = s.replace(m.group(0), f"if ({bits} == 8'h04) $finish;\n      else if ({bits} == 8'h01) trace_on <= 1'b1;\n      else if ({bits} == 8'h02) trace_on <= 1'b0;\n      else $write(\"%c\", {bits});")
k = s.index("  always @(posedge clock) begin\n    if (~reset & (")
s = s[:k] + "  reg trace_on; reg [63:0] tcyc; integer tfd;\n  initial begin trace_on = 0; tcyc = 0; tfd = $fopen(\"boomtrace.log\", \"w\"); end\n  always @(posedge clock) tcyc <= tcyc + 64'd1;\n" + s[k:]

# --- fetch buffer ---
append("FetchBuffer", f"\n  always @(posedge clock) if ({ON} && io_enq_valid && io_enq_ready) $fdisplay({FD}, \"F %0d %h\", {CY}, io_enq_bits_pc);")

# --- core: dispatch and issue ---
i, j = modspan("BoomCore"); body = s[i:j]; add = ""
lsb = 2 if width > 2 else (1 if width == 2 else 0)
for w in range(width):
    pc = f"_rename_stage_io_ren2_uops_{w}_debug_pc"
    rid = f"dis_uops_{w}_rob_idx" if declared(body, f"dis_uops_{w}_rob_idx") else None
    if rid is None:
        cands = [c for c in ("_rob_io_rob_tail_idx", "rob_io_rob_tail_idx") if declared(body, c)]
        rid = cands[0] if cands else None
    assert declared(body, f"dis_fire_{w}") and rid, (w, rid)
    add += f"\n  always @(posedge clock) if ({ON} && dis_fire_{w}) $fdisplay({FD}, \"D %0d %h %0d\", {CY}, {pc}, {rid});"
for q, unit in enumerate(("_int_issue_unit", "_mem_issue_unit")):
    for n in range(8):
        v, r = f"{unit}_io_iss_valids_{n}", f"{unit}_io_iss_uops_{n}_rob_idx"
        if declared(body, v) and declared(body, r):
            add += f"\n  always @(posedge clock) if ({ON} && {v}) $fdisplay({FD}, \"I %0d %0d {q}\", {CY}, {r});"
s = s[:j] + add + s[j:]

# --- ROB: per-entry state transitions and commit ---
i, j = modspan("Rob"); body = s[i:j]; add = ""; n = 0
for c in range(width):
    for r in range(64):
        val = f"rob_val_{r}" if c == 0 else f"rob_val_{c}_{r}"
        bsy = f"rob_bsy_{r}" if c == 0 else f"rob_bsy_{c}_{r}"
        if not declared(body, val): break
        idx = (r << lsb) | c; n += 1
        add += (f"\n  reg pv_{c}_{r}, pb_{c}_{r}; always @(posedge clock) begin pv_{c}_{r} <= {val}; pb_{c}_{r} <= {bsy};"
                f" if ({ON} && pv_{c}_{r} && {val} && pb_{c}_{r} && !{bsy}) $fdisplay({FD}, \"C %0d {idx}\", {CY});"
                f" if ({ON} && pv_{c}_{r} && !{val} && !(io_commit_valids_{c} && rob_head == {r})) $fdisplay({FD}, \"X %0d {idx}\", {CY}); end")
    add += f"\n  always @(posedge clock) if ({ON} && io_commit_valids_{c}) $fdisplay({FD}, \"R %0d %0d\", {CY}, (rob_head << {lsb}) | {c});"
s = s[:j] + add + s[j:]

# --- memory side: load/store unit, miss handlers, writeback unit, cache bus ---
T = "TestHarness.chiptop0.system.tile_prci_domain.element_reset_domain_boom_tile"
def opt(name, items):
    """items: (fmt, args, condition) where every identifier in condition/args must be declared"""
    global s
    i, j = modspan(name); body = s[i:j]; out = ""
    for fmt, args, cond in items:
        ids = set(re.findall(r"[A-Za-z_]\w*", cond + " " + args)) - {"io_id"}
        ids = {x for x in ids if not x[0].isdigit()}
        if all(declared(body, x) for x in ids if x not in ("d",)):
            a = (", " + args) if args else ""
            out += f"\n  always @(posedge clock) if ({ON} && ({cond})) $fdisplay({FD}, \"{fmt}\", {CY}{a});"
        else:
            print("  skip", name, fmt, [x for x in ids if not declared(body, x)])
    s = s[:j] + out + s[j:]
opt("LSU", [("LI %0d %0d %0d", "io_core_exe_0_req_bits_uop_ldq_idx, io_core_exe_0_req_bits_uop_rob_idx", "will_fire_load_incoming_0_will_fire"),
            ("LW %0d %0d", "ldq_wakeup_idx", "will_fire_load_wakeup_0_will_fire"),
            ("LS %0d", "", "will_fire_store_commit_0_will_fire"),
            ("LR %0d %0d", "io_dmem_resp_0_bits_uop_ldq_idx", "io_dmem_resp_0_valid")])
opt("BoomNonBlockingDCache", [("N %0d %0d%0d%0d", "s2_nack_victim_0, s2_nack_wb_0, s2_nack_hit_0", "s2_nack_0"),
                              ("A %0d", "", "auto_out_a_valid"),
                              ("G %0d", "", "auto_out_d_valid && auto_out_d_ready"),
                              ("K %0d", "", "auto_out_c_valid && auto_out_c_ready")])
i, j = modspan("BoomMSHR")
s = s[:j] + f"\n  reg [4:0] pst; always @(posedge clock) begin pst <= state; if ({ON} && pst != state) $fdisplay({FD}, \"M %0d %0d %0d\", {CY}, io_id, state); end" + s[j:]
i, j = modspan("BoomWritebackUnit")
s = s[:j] + f"\n  reg [3:0] pst; always @(posedge clock) begin pst <= state; if ({ON} && pst != state) $fdisplay({FD}, \"W %0d %0d\", {CY}, state); end" + s[j:]
open(dst, "w").write(s); print("trace probes added:", dst, "rob entries", n)
