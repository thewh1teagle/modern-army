#!/usr/bin/env python3
"""Extract level BSP geometry from a repacked UE2/AA2.5 .aao map.

Parses the root UModel (largest Model export): Vectors, Points, Nodes, Surfs,
Verts — enough to emit textured world polygons. Reverse-engineered layout
(AA2.5 Assist repack, package ver 127/23):

  UModel: None-props(1) + FBox(25) + FSphere(16) + int32 (AA2 extra)
          + TArray<FVector> Vectors + TArray<FVector> Points
          + TArray<FBspNode> Nodes + TArray<FBspSurf> Surfs + TArray<FVert> Verts

  FBspNode: FPlane(16) + ZoneMask(8) + NodeFlags(1)
            + iVertPool(c) + iSurf(c) + iBack(c) + iFront(c) + iPlane(c)
            + iCollisionBound(c) + iRenderBound(c) + sphere(16) + iZone(2)
            + NumVertices(1) + 20 bytes tail (iLeaf[2] + 3 ints)

  FBspSurf: Texture(c objref) + PolyFlags(u32) + pBase(c) + vNormal(c)
            + vTextureU(c) + vTextureV(c) + iBrushPoly(c) + Actor(c)
            + FPlane(16) + LightMapScale(f32) + int32

  FVert: pVertex(c) + iSide(c)

  (c) = FCompactIndex. UVs are texel-space: u = (P - Points[pBase])·Vectors[vTexU].

Usage: python3 extract_bsp.py <map.aao> <out.json>
"""

from __future__ import annotations

import json
import math
import sys

from extract_map import Reader, load_package

PF_INVISIBLE = 0x00000001
PF_TWO_SIDED = 0x00000100
PF_FAKE_BACKDROP = 0x00000080
PF_PORTAL = 0x04000000
SKIP_FLAGS = PF_INVISIBLE | PF_FAKE_BACKDROP | PF_PORTAL


def vec(r: Reader) -> list[float]:
    return [r.f32(), r.f32(), r.f32()]


def parse_model(pkg, data: bytes, e) -> dict:
    r = Reader(data, e.serial_offset)
    end = e.serial_offset + e.serial_size
    assert pkg.names[r.cindex()] == "None", "expected empty property list"
    r.read(25)  # FBox
    r.read(16)  # FSphere
    r.read(4)   # AA2 licensee extra int32

    vectors = [vec(r) for _ in range(r.cindex())]
    points = [vec(r) for _ in range(r.cindex())]

    nodes = []
    for _ in range(r.cindex()):
        plane = [r.f32() for _ in range(4)]
        r.read(8)  # ZoneMask
        r.u8()     # NodeFlags
        ivert_pool = r.cindex()
        isurf = r.cindex()
        for _ in range(5):  # iBack iFront iPlane iCollisionBound iRenderBound
            r.cindex()
        r.read(16)  # node sphere
        r.read(2)   # iZone[2]
        nverts = r.u8()
        r.read(20)  # iLeaf[2] + 3 ints
        nodes.append((ivert_pool, isurf, nverts, plane))

    surfs = []
    for _ in range(r.cindex()):
        tex = r.cindex()
        flags = r.u32()
        pbase = r.cindex()
        r.cindex()  # vNormal
        vtu = r.cindex()
        vtv = r.cindex()
        r.cindex()  # iBrushPoly
        r.cindex()  # Actor
        r.read(16)  # plane
        r.f32()     # LightMapScale
        r.read(4)   # int32
        surfs.append((pkg.obj_name(tex), flags, pbase, vtu, vtv))

    verts = []
    for _ in range(r.cindex()):
        pv = r.cindex()
        r.cindex()  # iSide
        verts.append(pv)

    assert r.pos <= end, "overran model export"
    return {"vectors": vectors, "points": points, "nodes": nodes, "surfs": surfs, "verts": verts}


def build_polys(m: dict) -> list[dict]:
    polys = []
    for ivert_pool, isurf, nverts, _plane in m["nodes"]:
        if nverts < 3:
            continue
        tex, flags, pbase, vtu, vtv = m["surfs"][isurf]
        if flags & SKIP_FLAGS:
            continue
        pts = [m["points"][m["verts"][ivert_pool + i]] for i in range(nverts)]
        base = m["points"][pbase]
        tu, tv = m["vectors"][vtu], m["vectors"][vtv]
        uvs = [
            [
                sum((p[k] - base[k]) * tu[k] for k in range(3)),
                sum((p[k] - base[k]) * tv[k] for k in range(3)),
            ]
            for p in pts
        ]
        polys.append(
            {
                "verts": pts,
                "uvs": uvs,
                "texture": tex,
                "flags": flags,
                "twoSided": bool(flags & PF_TWO_SIDED),
            }
        )
    return polys


def main() -> None:
    map_path, out_path = sys.argv[1], sys.argv[2]
    pkg, data = load_package(map_path)

    models = [e for e in pkg.exports if e.class_name == "Model"]
    models.sort(key=lambda e: e.serial_size, reverse=True)
    root = models[0]
    print(f"root model '{root.name}' {root.serial_size} bytes")

    m = parse_model(pkg, data, root)
    print(
        f"vectors {len(m['vectors'])}, points {len(m['points'])}, "
        f"nodes {len(m['nodes'])}, surfs {len(m['surfs'])}, verts {len(m['verts'])}"
    )
    polys = build_polys(m)
    textures = {p["texture"] for p in polys}
    json.dump({"polys": polys}, open(out_path, "w"))
    print(f"wrote {out_path}: {len(polys)} visible polys, {len(textures)} textures")


if __name__ == "__main__":
    main()
