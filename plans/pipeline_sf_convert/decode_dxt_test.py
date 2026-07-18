#!/usr/bin/env python3
"""Reference DXT1 decode of one texture to ground-truth umodel's PNG output."""
import struct, sys, zlib
from extract_map import load_package, Reader, parse_properties

def write_png(path, w, h, rgba):
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
    raw = b"".join(b"\x00" + rgba[y*w*4:(y+1)*w*4] for y in range(h))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    open(path, "wb").write(png)

def c565(v):
    r = (v >> 11) & 31; g = (v >> 5) & 63; b = v & 31
    return (r*255//31, g*255//63, b*255//31)

def decode_dxt1(data, w, h):
    out = bytearray(w*h*4)
    bi = 0
    for by in range(h//4):
        for bx in range(w//4):
            c0, c1, idx = struct.unpack_from("<HHI", data, bi); bi += 8
            p0, p1 = c565(c0), c565(c1)
            if c0 > c1:
                pal = [p0, p1, tuple((2*a+b)//3 for a,b in zip(p0,p1)), tuple((a+2*b)//3 for a,b in zip(p0,p1))]
            else:
                pal = [p0, p1, tuple((a+b)//2 for a,b in zip(p0,p1)), (0,0,0)]
            for py in range(4):
                for px in range(4):
                    r,g,b = pal[(idx >> 2*(py*4+px)) & 3]
                    o = ((by*4+py)*w + bx*4+px)*4
                    out[o:o+4] = bytes((r,g,b,255))
    return bytes(out)

import os
GAME = "/private/tmp/claude-501/-Users-yqbqwlny-Documents-modern-army/4fa7720e-d24a-4de5-a135-9e5befb87a65/scratchpad/aa2game"
pkg, data = load_package(os.path.realpath(GAME + "/T-CONCRETE.utx"))
e = [x for x in pkg.exports if x.name == "con_wall_wall03_b"][0]
r = Reader(data, e.serial_offset)
p = parse_properties(pkg, r)
r.u32(); nm = r.u8(); r.u32()
count = r.cindex()
mip = r.read(count)
print("format", p["Format"], "mip0 bytes", count, "expected", p["USize"]*p["VSize"]//2)
rgba = decode_dxt1(mip, p["USize"], p["VSize"])
write_png(sys.argv[1], p["USize"], p["VSize"], rgba)
print("wrote", sys.argv[1])
