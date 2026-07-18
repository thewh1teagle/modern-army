#!/usr/bin/env python3
"""Extract TerrainInfo heightmaps (G16) from a repacked UE2 .aao map.

G16 mip layout after tagged properties: int32 unk, u8 mip_count, then per mip:
int32 skip_offset, compact byte count, raw data (u16 LE heights).

World height: z = Location.z + (h - 32768) * TerrainScale.z / 256
Quad spacing: TerrainScale.x/y per heightmap cell, centered on Location.

Usage: python3 extract_terrain.py <map.aao> <out.json>
"""

from __future__ import annotations

import base64
import json
import sys

from extract_map import Reader, load_package, parse_properties, actor_props


def main() -> None:
    map_path, out_path = sys.argv[1], sys.argv[2]
    pkg, data = load_package(map_path)

    terrains = []
    for ti in (e for e in pkg.exports if e.class_name == "TerrainInfo"):
        p = actor_props(pkg, data, ti)
        tex_name = p.get("TerrainMap")
        te = next(e for e in pkg.exports if e.name == tex_name)
        r = Reader(data, te.serial_offset)
        tp = parse_properties(pkg, r)
        assert tp.get("Format") == 10, f"{tex_name}: not G16"
        r.u32()  # unknown
        nmips = r.u8()
        assert nmips >= 1
        r.u32()  # skip offset
        count = r.cindex()
        usize, vsize = tp["USize"], tp["VSize"]
        assert count == usize * vsize * 2, "mip size mismatch"
        heights = r.read(count)
        terrains.append(
            {
                "name": ti.name,
                "location": p.get("Location", [0, 0, 0]),
                "scale": p.get("TerrainScale", [64, 64, 64]),
                "uSize": usize,
                "vSize": vsize,
                "heightsB64": base64.b64encode(heights).decode(),
            }
        )
        print(f"{ti.name}: {tex_name} {usize}x{vsize} scale {p.get('TerrainScale')}")

    json.dump({"terrains": terrains}, open(out_path, "w"))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
