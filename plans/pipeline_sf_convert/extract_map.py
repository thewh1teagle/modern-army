#!/usr/bin/env python3
"""Extract actor placements from a repacked (standard-layout) UE2 .aao map.

Outputs map.json with:
  - staticMeshActors: mesh ref (package.name), location, rotation, scale
  - movers (doors/lifts): base + key positions/rotations
  - playerStarts: location, rotation
UE units/axes are kept as-is; the client does the coordinate conversion.

Usage: python3 extract_map.py <map.aao> <out.json>
"""

from __future__ import annotations

import json
import struct
import sys
from dataclasses import dataclass, field


class Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    def u8(self) -> int:
        v = self.data[self.pos]
        self.pos += 1
        return v

    def s(self, fmt: str) -> int:
        v = struct.unpack_from(fmt, self.data, self.pos)[0]
        self.pos += struct.calcsize(fmt)
        return v

    def u16(self) -> int:
        return self.s("<H")

    def u32(self) -> int:
        return self.s("<I")

    def i32(self) -> int:
        return self.s("<i")

    def f32(self) -> float:
        return self.s("<f")

    def read(self, n: int) -> bytes:
        v = self.data[self.pos : self.pos + n]
        self.pos += n
        return v

    def cindex(self) -> int:
        """UE1/2 FCompactIndex: variable-length signed int."""
        b = self.u8()
        neg = b & 0x80
        v = b & 0x3F
        if b & 0x40:
            shift = 6
            while True:
                b = self.u8()
                v |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
        return -v if neg else v

    def fstring(self) -> str:
        n = self.cindex()
        if n == 0:
            return ""
        if n > 0:  # ANSI, includes null
            return self.read(n)[:-1].decode("latin-1")
        raw = self.read(-n * 2)  # UTF-16
        return raw.decode("utf-16-le")[:-1]


@dataclass
class Export:
    class_index: int
    super_index: int
    package_index: int
    name: str
    flags: int
    serial_size: int
    serial_offset: int
    class_name: str = "?"


@dataclass
class Package:
    names: list[str] = field(default_factory=list)
    imports: list[tuple[str, str, int, str]] = field(default_factory=list)  # clspkg, cls, pkg, name
    exports: list[Export] = field(default_factory=list)

    def obj_name(self, ref: int) -> str:
        """Resolve an object reference to a qualified name."""
        if ref == 0:
            return ""
        if ref > 0:
            return self.exports[ref - 1].name
        imp = self.imports[-ref - 1]
        # qualify with outer package chain
        outer = imp[2]
        parts = [imp[3]]
        while outer != 0:
            o = self.imports[-outer - 1]
            parts.append(o[3])
            outer = o[2]
        return ".".join(reversed(parts))


RF_HAS_STACK = 0x02000000


def load_package(path: str) -> tuple[Package, bytes]:
    data = open(path, "rb").read()
    r = Reader(data)
    assert r.u32() == 0x9E2A83C1, "not a UE package"
    ver = r.u16()
    _lic = r.u16()
    _flags = r.u32()
    name_count, name_off = r.u32(), r.u32()
    export_count, export_off = r.u32(), r.u32()
    import_count, import_off = r.u32(), r.u32()
    assert ver >= 68, f"old package version {ver} not supported"

    pkg = Package()
    r.pos = name_off
    for _ in range(name_count):
        nm = r.fstring()
        r.u32()  # name flags
        pkg.names.append(nm)

    r.pos = import_off
    for _ in range(import_count):
        clspkg = pkg.names[r.cindex()]
        cls = pkg.names[r.cindex()]
        outer = r.i32()
        nm = pkg.names[r.cindex()]
        pkg.imports.append((clspkg, cls, outer, nm))

    r.pos = export_off
    for _ in range(export_count):
        ci = r.cindex()
        si = r.cindex()
        pi = r.i32()
        nm = pkg.names[r.cindex()]
        fl = r.u32()
        sz = r.cindex()
        off = r.cindex() if sz > 0 else 0
        pkg.exports.append(Export(ci, si, pi, nm, fl, sz, off))

    # resolve class names (class ref: >0 export, <0 import, 0 = UClass itself)
    for e in pkg.exports:
        if e.class_index == 0:
            e.class_name = "Class"
        elif e.class_index > 0:
            e.class_name = pkg.exports[e.class_index - 1].name
        else:
            e.class_name = pkg.imports[-e.class_index - 1][3]
    return pkg, data


# ---- tagged property parsing ----

def parse_properties(pkg: Package, r: Reader) -> dict:
    """Parse UE2 tagged properties until 'None'. Returns {name or name[idx]: value}."""
    props: dict = {}
    while True:
        name = pkg.names[r.cindex()]
        if name == "None":
            break
        info = r.u8()
        ptype = info & 0x0F
        size_type = (info >> 4) & 0x07
        is_array = bool(info & 0x80)

        struct_name = pkg.names[r.cindex()] if ptype == 10 else None

        size = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}.get(size_type)
        if size is None:
            size = r.u8() if size_type == 5 else (r.u16() if size_type == 6 else r.u32())

        array_index = 0
        if is_array and ptype != 3:  # for bool, bit 0x80 is the value
            b = r.u8()
            if b < 128:
                array_index = b
            elif b & 0xC0 == 0x80:
                array_index = ((b & 0x3F) << 8) | r.u8()
            else:
                array_index = ((b & 0x3F) << 24) | (r.u8() << 16) | (r.u8() << 8) | r.u8()

        end = r.pos + size
        key = name if array_index == 0 else f"{name}[{array_index}]"

        if ptype == 1:  # byte
            props[key] = r.u8()
        elif ptype == 2:  # int
            props[key] = r.i32()
        elif ptype == 3:  # bool
            props[key] = is_array
        elif ptype == 4:  # float
            props[key] = r.f32()
        elif ptype in (5, 6):  # object/name ref
            idx = r.cindex()
            props[key] = pkg.obj_name(idx) if ptype == 5 else pkg.names[idx]
        elif ptype == 10:  # struct
            if struct_name == "Vector":
                props[key] = [r.f32(), r.f32(), r.f32()]
            elif struct_name == "Rotator":
                props[key] = [r.i32(), r.i32(), r.i32()]
            else:
                props[key] = f"<struct {struct_name}>"
        # other types: skipped via `end`
        r.pos = end
    return props


def actor_props(pkg: Package, data: bytes, e: Export) -> dict:
    r = Reader(data, e.serial_offset)
    if e.flags & RF_HAS_STACK:
        # FStateFrame: Node, StateNode (compact), ProbeMask (u64), LatentAction (u32), Offset if node
        node = r.cindex()
        r.cindex()
        r.read(12)
        if node != 0:
            r.cindex()
    return parse_properties(pkg, r)


def main() -> None:
    map_path, out_path = sys.argv[1], sys.argv[2]
    pkg, data = load_package(map_path)

    out = {"staticMeshActors": [], "movers": [], "playerStarts": []}
    counts: dict[str, int] = {}
    for e in pkg.exports:
        cls = e.class_name
        if cls in ("StaticMeshActor", "DecoMesh") or cls == "Mover" or cls == "AGP_PlayerStart":
            try:
                p = actor_props(pkg, data, e)
            except Exception as ex:  # noqa: BLE001
                counts[f"ERROR {cls}"] = counts.get(f"ERROR {cls}", 0) + 1
                continue
            counts[cls] = counts.get(cls, 0) + 1
            base = {
                "name": e.name,
                "location": p.get("Location", [0, 0, 0]),
                "rotation": p.get("Rotation", [0, 0, 0]),
            }
            if cls in ("StaticMeshActor", "DecoMesh"):
                mesh = p.get("StaticMesh", "")
                if not mesh or p.get("bHidden"):
                    continue
                out["staticMeshActors"].append(
                    base
                    | {
                        "mesh": mesh,
                        "scale": p.get("DrawScale", 1.0),
                        "scale3d": p.get("DrawScale3D", [1, 1, 1]),
                    }
                )
            elif cls == "Mover":
                keys = {k: v for k, v in p.items() if k.startswith(("KeyPos", "KeyRot", "BasePos", "BaseRot"))}
                out["movers"].append(
                    base
                    | {
                        "mesh": p.get("StaticMesh", ""),
                        "scale": p.get("DrawScale", 1.0),
                        "scale3d": p.get("DrawScale3D", [1, 1, 1]),
                        "keys": keys,
                        "numKeys": p.get("NumKeys", 2),
                    }
                )
            else:
                out["playerStarts"].append(base | {"team": p.get("TeamNumber", 0)})

    json.dump(out, open(out_path, "w"), indent=1)
    print(f"parsed: {counts}")
    print(
        f"wrote {out_path}: {len(out['staticMeshActors'])} static meshes, "
        f"{len(out['movers'])} movers, {len(out['playerStarts'])} player starts"
    )


if __name__ == "__main__":
    main()
