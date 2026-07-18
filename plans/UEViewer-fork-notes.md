# UEViewer (umodel) fork notes

`plans/UEViewer/` is a patched clone of https://github.com/gildor2/UEViewer
(shallow, master @ July 2026), built as a native arm64 macOS CLI exporter
(`plans/UEViewer/umodel`). Rendering/viewer is disabled upstream on macOS —
export-only, which is all we need.

Build: `cd plans/UEViewer && ./build.sh` (needs Xcode CLT + Homebrew `libpng`).

## Patches for arm64 macOS build

1. **`common.project`** — `-msse2` is x86-only; skipped on osx platform.
2. **`Core/MathSSE.h`** — on arm64, include vendored `Core/sse2neon.h`
   (github.com/DLTcollab/sse2neon) instead of `<xmmintrin.h>`; maps SSE
   intrinsics (`__m128`) to NEON.
3. **`libs/nvtt/nvcore/poshlib/posh.h`** — added ARM64 CPU detection
   (`POSH_CPU_AARCH64`) and put it in the little-endian list (otherwise nvtt
   errors "cannot determine target CPU", then defaults to big-endian).
4. **`libs/nvtt/nvcore/nvcore.h`** — map `POSH_CPU_AARCH64` → `NV_CPU_X86_64`
   (only gates debug asm; safe).
5. **`common.project`** — compile `libs/nvtt/nvcore/poshlib/posh.c` (never built
   upstream; `DDSHeader::swapBytes()` references `POSH_SwapU32` → link error).
6. **`Unreal/FileSystem/GameFileSystem.cpp`** — `stat64` doesn't exist on modern
   macOS; use `stat` (already 64-bit) under `__APPLE__`.
7. **`common.project`** — add Homebrew libpng include/lib paths
   (`/opt/homebrew/opt/libpng`) on osx.

## Patches for AA2.5 Assist packages

Key discovery: the AA2.5 Assist archives ship **repacked/decrypted** packages —
standard UE2 package structure (plain name/import/export tables), while stock
umodel's `-game=aa2` expects the retail encrypted/scrambled layout. Generic UE2
mode (`Game: 200000`) reads the tables but fails on AA-specific object data
(e.g. `UTexture::Serialize` → bad alloc). So: use `-game=aa2` with the
structure-level AA2 branches neutralized:

8. **`Unreal/UnrealPackage/UnPackage2.cpp`** (`AA2_FName`) — name table: if
   serialized length is positive, read as plain ANSI string (repacked format)
   instead of asserting + ROR16-decrypting UTF-16.
9. **`Unreal/UnrealPackage/UnPackage.cpp`** (`FObjectImport::Serialize`) — AA2
   custom import layout branch disabled (`if (0 && ...)`); standard layout used.
10. **`Unreal/UnrealPackage/UnPackage2.cpp`** (`FObjectExport` serialize) — same
    for the AA2 custom export layout branch.

## Usage / verified

Flat dir of symlinks to all `.aao/.usx/.utx/.u/.ukx` under
`plans/aa25assist_extract/files/Data/AAFiles/` (umodel needs one search path;
pass the map by full path — `.aao` isn't auto-scanned):

```sh
./umodel -game=aa2 -path=$GAME -list $GAME/Pipeline_SF.aao          # full load OK
./umodel -game=aa2 -path=$GAME -out=$OUT -export -gltf $GAME/M-Pipeline.usx  # 51/51 meshes
```

- `Pipeline_SF.aao` loads completely: 2864 StaticMeshActor, 1468 BSP models,
  80 TerrainSector, 273 Light, 16 AGP_PlayerStart.
- Exporting the map itself yields 0 objects — umodel does not export level
  actors/BSP/terrain; that needs our own parser or T3D route
  (see `plans/pipeline_sf_convert/README.md`).
