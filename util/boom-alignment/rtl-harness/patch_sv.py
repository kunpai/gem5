import re, sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()
# 1) program image load into main memory
a = "  reg [63:0] Memory[0:33554431];"
assert s.count(a) == 1
i = s.index(a); j = s.index("\n", i)
s = s[:j+1] + '''  string imgf;
  initial begin
    if ($value$plusargs("img=%s", imgf)) $readmemh(imgf, Memory);
  end
''' + s[j+1:]
# 2) UART tap: print each byte enqueued to the TX queue, 0x04 ends simulation
m = re.search(r"  Queue8_UInt8 txq \(.*?\n.*?\n.*?\n.*?\n\s*\.io_enq_valid \((.*?)\),.*?\n\s*\.io_enq_bits  \((.*?)\),", s)
assert m, "txq not found"
valid, bits = m.group(1), m.group(2)
tap = f'''  always @(posedge clock) begin
    if (~reset & ({valid}) & _txq_io_enq_ready) begin
      if ({bits} == 8'h04) $finish;
      else $write("%c", {bits});
    end
  end
'''
s = s[:m.start()] + tap + s[m.start():]
open(dst, "w").write(s)
print("patched", dst, "valid=", valid, "bits=", bits)
