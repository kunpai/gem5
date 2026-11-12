import sys, struct
d = open(sys.argv[1], "rb").read()
d += b"\0" * (-len(d) % 8)
with open(sys.argv[2], "w") as f:
    for i in range(0, len(d), 8):
        f.write("%016x\n" % struct.unpack("<Q", d[i:i+8])[0])
