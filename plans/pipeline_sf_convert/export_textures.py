#!/usr/bin/env python3
"""Export UE2 textures to PNG in pure Python (replaces umodel texture export,
whose bundled nvtt DXT decoder produces garbage on arm64).

Supports P8 (palette), DXT1/3/5, RGBA8, L8/G16 (grayscale). Writes mip 0 to
<out>/<PackageName>/Texture/<name>.png (same layout umodel used).

Usage: python3 export_textures.py <package.utx|.aao> [...] --out <dir>
"""

from __future__ import annotations

import os
import struct
import sys
import zlib
from multiprocessing import Pool

from extract_map import Reader, load_package, parse_properties


def write_png(path: str, w: int, h: int, rgba: bytes) -> None:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        c = tag + payload
        return struct.pack(">I", len(payload)) + c + struct.pack(">I", zlib.crc32(c))

    raw = b"".join(b"\x00" + rgba[y * w * 4 : (y + 1) * w * 4] for y in range(h))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)


def c565(v: int) -> tuple[int, int, int]:
    return ((v >> 11 & 31) * 255 // 31, (v >> 5 & 63) * 255 // 63, (v & 31) * 255 // 31)


def decode_dxt1(data: bytes, w: int, h: int) -> bytearray:
    out = bytearray(w * h * 4)
    bi = 0
    for by in range(max(1, h // 4)):
        for bx in range(max(1, w // 4)):
            c0, c1, idx = struct.unpack_from("<HHI", data, bi)
            bi += 8
            p0, p1 = c565(c0), c565(c1)
            if c0 > c1:
                pal = (
                    p0 + (255,), p1 + (255,),
                    tuple((2 * a + b) // 3 for a, b in zip(p0, p1)) + (255,),
                    tuple((a + 2 * b) // 3 for a, b in zip(p0, p1)) + (255,),
                )
            else:
                pal = (
                    p0 + (255,), p1 + (255,),
                    tuple((a + b) // 2 for a, b in zip(p0, p1)) + (255,),
                    (0, 0, 0, 0),
                )
            for py in range(4):
                for px in range(4):
                    r, g, b, a = pal[(idx >> 2 * (py * 4 + px)) & 3]
                    o = ((by * 4 + py) * w + bx * 4 + px) * 4
                    out[o : o + 4] = bytes((r, g, b, a))
    return out


def decode_dxt45_alpha(block: bytes) -> list[int]:
    a0, a1 = block[0], block[1]
    if a0 > a1:
        pal = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    else:
        pal = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
    bits = int.from_bytes(block[2:8], "little")
    return [pal[(bits >> (3 * i)) & 7] for i in range(16)]


def decode_dxt35(data: bytes, w: int, h: int, dxt5: bool) -> bytearray:
    out = bytearray(w * h * 4)
    bi = 0
    for by in range(max(1, h // 4)):
        for bx in range(max(1, w // 4)):
            ablock = data[bi : bi + 8]
            c0, c1, idx = struct.unpack_from("<HHI", data, bi + 8)
            bi += 16
            p0, p1 = c565(c0), c565(c1)
            pal = (
                p0, p1,
                tuple((2 * a + b) // 3 for a, b in zip(p0, p1)),
                tuple((a + 2 * b) // 3 for a, b in zip(p0, p1)),
            )
            alphas = (
                decode_dxt45_alpha(ablock)
                if dxt5
                else [(ablock[i // 2] >> (4 * (i % 2)) & 15) * 17 for i in range(16)]
            )
            for py in range(4):
                for px in range(4):
                    i16 = py * 4 + px
                    r, g, b = pal[(idx >> 2 * i16) & 3]
                    o = ((by * 4 + py) * w + bx * 4 + px) * 4
                    out[o : o + 4] = bytes((r, g, b, alphas[i16]))
    return out


def read_mip0(pkg, data: bytes, e) -> tuple[dict, bytes] | None:
    r = Reader(data, e.serial_offset)
    p = parse_properties(pkg, r)
    if "Format" not in p and "USize" not in p:
        return None
    r.u32()
    nmips = r.u8()
    if nmips < 1:
        return None
    r.u32()
    count = r.cindex()
    return p, r.read(count)


def load_palette(pkg, data: bytes, name: str) -> bytes | None:
    pe = next((x for x in pkg.exports if x.name == name and x.class_name == "Palette"), None)
    if not pe:
        return None
    r = Reader(data, pe.serial_offset)
    parse_properties(pkg, r)
    n = r.cindex()
    return r.read(n * 4)


def export_package(args: tuple[str, str]) -> str:
    path, out_root = args
    pkg, data = load_package(path)
    pkg_name = os.path.basename(path).rsplit(".", 1)[0]
    out_dir = os.path.join(out_root, pkg_name, "Texture")
    n_ok = n_skip = 0
    for e in pkg.exports:
        if e.class_name != "Texture":
            continue
        try:
            got = read_mip0(pkg, data, e)
            if not got:
                n_skip += 1
                continue
            p, mip = got
            w, h, fmt = p.get("USize", 0), p.get("VSize", 0), p.get("Format", 0)
            if not w or not h:
                n_skip += 1
                continue
            if fmt == 3 and len(mip) >= w * h // 2:
                rgba = decode_dxt1(mip, w, h)
            elif fmt in (7, 8) and len(mip) >= w * h:
                rgba = decode_dxt35(mip, w, h, fmt == 8)
            elif fmt == 0 and len(mip) >= w * h:  # P8
                palname = p.get("Palette", "")
                pal = load_palette(pkg, data, palname.split(".")[-1]) if palname else None
                if not pal:
                    n_skip += 1
                    continue
                rgba = bytearray(w * h * 4)
                for i in range(w * h):
                    o = mip[i] * 4
                    rgba[i * 4 : i * 4 + 4] = pal[o : o + 3] + b"\xff"
            elif fmt == 5 and len(mip) >= w * h * 4:  # RGBA8 (stored BGRA)
                rgba = bytearray(w * h * 4)
                for i in range(0, w * h * 4, 4):
                    rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3] = mip[i + 2], mip[i + 1], mip[i], mip[i + 3]
            elif fmt in (9, 10):  # L8 / G16 grayscale
                step = 1 if fmt == 9 else 2
                rgba = bytearray(w * h * 4)
                for i in range(w * h):
                    v = mip[i * step + step - 1]
                    rgba[i * 4 : i * 4 + 4] = bytes((v, v, v, 255))
            else:
                n_skip += 1
                continue
            os.makedirs(out_dir, exist_ok=True)
            write_png(os.path.join(out_dir, f"{e.name}.png"), w, h, bytes(rgba))
            n_ok += 1
        except Exception:
            n_skip += 1
    return f"{pkg_name}: {n_ok} ok, {n_skip} skipped"


def main() -> None:
    args = sys.argv[1:]
    out = args[args.index("--out") + 1]
    paths = [os.path.realpath(a) for a in args if not a.startswith("--") and a != out]
    with Pool() as pool:
        for line in pool.imap_unordered(export_package, [(p, out) for p in paths]):
            print(line)


if __name__ == "__main__":
    main()
