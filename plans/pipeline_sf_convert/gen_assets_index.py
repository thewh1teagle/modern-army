#!/usr/bin/env python3
"""Build assets_index.json for the client from the umodel export tree.

- meshes:   lowercase "package.meshname" -> mesh path (relative to /assets/)
- textures: lowercase "texturename" -> {path, w, h}  (names are globally
  unique enough for AA2.5; last one wins on collision)

Supports both the raw dev export (.gltf + .png) and the optimized tree
(draco .glb + .webp from optimize_assets.md) -- whichever is present.

Usage: python3 gen_assets_index.py <client/public/assets | assets_optimized>
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path


def png_size(path: Path) -> tuple[int, int]:
    with open(path, "rb") as f:
        head = f.read(26)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", path
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def webp_size(path: Path) -> tuple[int, int]:
    with open(path, "rb") as f:
        head = f.read(30)
    assert head[:4] == b"RIFF" and head[8:12] == b"WEBP", path
    fmt = head[12:16]
    if fmt == b"VP8 ":
        w, h = struct.unpack_from("<HH", head, 26)
        return w & 0x3FFF, h & 0x3FFF
    if fmt == b"VP8L":
        b0, b1, b2, b3 = head[21], head[22], head[23], head[24]
        w = 1 + (((b1 & 0x3F) << 8) | b0)
        h = 1 + (((b3 & 0xF) << 10) | (b2 << 2) | (b1 >> 6))
        return w, h
    if fmt == b"VP8X":
        # extended format container: flags(1) + reserved(3) + w-1(3 LE) + h-1(3 LE)
        w = 1 + (head[24] | (head[25] << 8) | (head[26] << 16))
        h = 1 + (head[27] | (head[28] << 8) | (head[29] << 16))
        return w, h
    raise ValueError(f"unsupported webp format {fmt!r}: {path}")


def main() -> None:
    assets = Path(sys.argv[1])
    root = assets / "umodel"
    meshes: dict[str, str] = {}
    textures: dict[str, dict] = {}

    mesh_ext = "glb" if any(root.rglob("*.glb")) else "gltf"
    for mesh in root.rglob(f"*.{mesh_ext}"):
        pkg = mesh.relative_to(root).parts[0]
        key = f"{pkg}.{mesh.stem}".lower()
        meshes[key] = str(mesh.relative_to(assets))

    tex_ext = "webp" if any(root.rglob("*.webp")) else "png"
    size_fn = webp_size if tex_ext == "webp" else png_size
    for tex in root.rglob(f"*.{tex_ext}"):
        w, h = size_fn(tex)
        textures[tex.stem.lower()] = {"path": str(tex.relative_to(assets)), "w": w, "h": h}

    out = assets / "map" / "assets_index.json"
    json.dump({"meshes": meshes, "textures": textures}, open(out, "w"))
    print(f"wrote {out}: {len(meshes)} meshes ({mesh_ext}), {len(textures)} textures ({tex_ext})")


if __name__ == "__main__":
    main()
