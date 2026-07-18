#!/usr/bin/env python3
"""Cut holes in terrain where indoor floors already cover the ground.

AA2.5 (like UT2004) terrains carry a native QuadVisibilityBitmap that marks
quads not to render (used to cut holes for buildings built into terrain).
That field isn't a tagged UProperty -- it's serialized manually by the
engine's C++ TerrainInfo::Serialize alongside other native-only data, so
extract_terrain.py (which only reads tagged properties + the heightmap
texture) has no way to recover it without fully reverse-engineering that
native layout.

This script derives an equivalent hole mask heuristically from data we
*can* parse reliably: the BSP polygons. For every terrain quad, if any
BSP polygon's footprint (floor, wall, or ceiling) covers the quad and its
Z extent brackets the terrain surface height there, terrain would either
z-fight with a floor or poke through a wall/ceiling into an interior space
-- so we mark the quad hidden. Walls contribute a tall Z range (covering
whatever the terrain height is at that spot, if it's routing through the
building), floors/ceilings a thin one gated by HEIGHT_MARGIN.

Usage: python3 terrain_holes.py <bsp.json> <terrain.json>  (edits terrain.json in place)
"""

from __future__ import annotations

import base64
import json
import struct
import sys

HEIGHT_MARGIN = 600.0  # UU; only cut where indoor floor is close to terrain height


def point_in_poly(x: float, y: float, verts: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(verts)
    x1, y1 = verts[-1]
    for x2, y2 in verts:
        if (y1 > y) != (y2 > y):
            xin = x1 + (x2 - x1) * (y - y1) / (y2 - y1)
            if x < xin:
                inside = not inside
        x1, y1 = x2, y2
    return inside


def main() -> None:
    bsp_path, terrain_path = sys.argv[1], sys.argv[2]
    bsp = json.load(open(bsp_path))
    terrain = json.load(open(terrain_path))

    PAD = 4.0  # UU; absorbs float-precision gaps between adjacent structure tiles
    structure = []  # (minx, maxx, miny, maxy, minz, maxz, [(x,y),...])
    for p in bsp["polys"]:
        verts = p["verts"]
        if len(verts) < 3:
            continue
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        zs = [v[2] for v in verts]
        structure.append(
            (min(xs) - PAD, max(xs) + PAD, min(ys) - PAD, max(ys) + PAD, min(zs), max(zs), [(v[0], v[1]) for v in verts])
        )

    print(f"{len(structure)} BSP polys")

    for ter in terrain["terrains"]:
        lx, ly, lz = ter["location"]
        sx, sy, sz = ter["scale"]
        us, vs = ter["uSize"], ter["vSize"]
        heights = base64.b64decode(ter["heightsB64"])

        n_quads_x, n_quads_y = us - 1, vs - 1
        hidden = bytearray((n_quads_x * n_quads_y + 7) // 8)
        cut = 0
        for j in range(n_quads_y):
            for i in range(n_quads_x):
                # sample the quad's 4 corners (+ center); majority vote absorbs
                # misses at floor-tile seams that a single center sample would catch
                h00 = struct.unpack_from("<H", heights, (j * us + i) * 2)[0]
                h10 = struct.unpack_from("<H", heights, (j * us + i + 1) * 2)[0]
                h01 = struct.unpack_from("<H", heights, ((j + 1) * us + i) * 2)[0]
                h11 = struct.unpack_from("<H", heights, ((j + 1) * us + i + 1) * 2)[0]
                havg = (h00 + h10 + h01 + h11) / 4
                tz = lz + (havg - 32768) * sz / 256

                samples = [
                    (lx + (i - us / 2) * sx, ly + (j - vs / 2) * sy),
                    (lx + (i + 1 - us / 2) * sx, ly + (j - vs / 2) * sy),
                    (lx + (i - us / 2) * sx, ly + (j + 1 - vs / 2) * sy),
                    (lx + (i + 1 - us / 2) * sx, ly + (j + 1 - vs / 2) * sy),
                    (lx + (i + 0.5 - us / 2) * sx, ly + (j + 0.5 - vs / 2) * sy),
                ]
                votes = 0
                for cx, cy in samples:
                    for minx, maxx, miny, maxy, minz, maxz, poly in structure:
                        if not (minx <= cx <= maxx and miny <= cy <= maxy):
                            continue
                        if not (minz - HEIGHT_MARGIN <= tz <= maxz + HEIGHT_MARGIN):
                            continue
                        if point_in_poly(cx, cy, poly):
                            votes += 1
                            break
                if votes >= 3:
                    idx = j * n_quads_x + i
                    hidden[idx // 8] |= 1 << (idx % 8)
                    cut += 1
        print(f"{ter['name']}: {cut}/{n_quads_x * n_quads_y} quads hidden")
        ter["hiddenQuadsB64"] = base64.b64encode(bytes(hidden)).decode()

    json.dump(terrain, open(terrain_path, "w"))
    print(f"wrote {terrain_path}")


if __name__ == "__main__":
    main()
