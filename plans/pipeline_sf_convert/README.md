# Pipeline SF → browser conversion (WORKING)

Converts the AA2.5 map `Pipeline_SF.aao` into data the Babylon.js client loads
directly. First playable version: walk/jump/fire around the full map with
textured BSP, terrain, ~2,900 placed static meshes, and 38 working doors.

## Pipeline (re-run in this order)

All scripts are stdlib-only Python 3 in this folder. `$GAME` = a flat dir of
symlinks to every `.aao/.usx/.utx/.u/.ukx` under
`plans/aa25assist_extract/files/Data/AAFiles/` (umodel/scripts need one search
path; recreate with `ln -sf`, see UEViewer-fork-notes.md). `$ASSETS` =
`client/public/assets`.

1. **Actors** — `extract_map.py <map.aao> $ASSETS/map/map.json`
   UE2 package parser (name/import/export tables + tagged properties).
   Emits staticMeshActors (mesh ref, location, rotation, scale), movers
   (base + key frames), playerStarts. Some AGP_PlayerStarts parse with
   Location (0,0,0) — client filters those out.
2. **BSP** — `extract_bsp.py <map.aao> $ASSETS/map/bsp.json`
   Parses the largest Model export (root level CSG). Reverse-engineered
   layouts documented in the script docstring; notable: AA2 adds an extra
   int32 after the UPrimitive sphere, FBspNode carries an extra 16-byte
   sphere + 20-byte tail. Emits textured polygons (texel-space UVs).
3. **Terrain** — `extract_terrain.py <map.aao> $ASSETS/map/terrain.json`
   Two TerrainInfos, G16 heightmaps decoded from the map package.
   Height formula (verified): z = Location.z + (h−32768)·TerrainScale.z/256.
4. **Meshes** — umodel (patched fork, `plans/UEViewer/umodel`):
   `./umodel -game=aa2 -path=$GAME -out=$ASSETS/umodel -export -gltf $GAME/<pkg>.usx`
   for the 20 packages referenced by map.json (list: see git history or
   regenerate from map.json mesh prefixes).
5. **Textures** — `export_textures.py $GAME/T*.utx $GAME/Pipeline_SF.aao --out $ASSETS/umodel`
   Pure-Python PNG export (P8/DXT1/DXT3/DXT5/RGBA8/L8/G16). Replaces
   umodel's texture export: its bundled nvtt DXT decoder emits garbage on
   arm64. glTF materials are named after the UE texture; the client matches
   them to PNGs by name.
6. **Index** — `gen_assets_index.py $ASSETS`
   Writes `map/assets_index.json`: lowercase mesh/texture name → path + PNG
   dimensions (used to normalize BSP texel UVs).

## Client (`client/src/`) — conventions that were hard-won, do not regress

- `ue.ts` — UE(x,y,z) → Babylon(**−x**, z, y), scale 1/52.5 UU/m.
  The X negation matters: a plain axis swap MIRRORS the whole map
  (discovered via mirrored sign text). Rotators: yaw `+`, pitch `−`,
  roll `−` under this mapping.
- **umodel glTF meshes are 1 unit = 100 UU** → instance scale factor
  100/52.5, with X negated to match the mirrored world axis.
- **All textures load with `invertY=false`** (UE and glTF UVs are
  top-left-origin; Babylon's default flip renders signs upside down).
- BSP: one mesh per texture, single winding + `backFaceCulling=false`
  (never emit both windings in one mesh — ComputeNormals cancels to
  black). Texel UVs normalized by PNG dims from assets_index.
- `player.ts` — **fully manual character controller.** Babylon's ellipsoid
  collider + applyGravity are unusable here: gravity tunnels through thin
  BSP floors, only applies while moving, and the collider wedges against
  the merged BSP meshes. Instead: planar WASD (pitch excluded), wall rays
  at knee/chest with slide-along-wall, raycast gravity + step-up snap,
  grounded-only jump, fall-out respawn. Movers/BSP/terrain are the only
  collidable meshes.
- `movers.ts` — doors: E toggles nearest mover (≤4m) between base and
  key-1 pose. `fire.ts` — hitscan + impact mark. `debugHud.ts` — position
  (Babylon + UE coords), yaw/pitch, fps; enable with `?debug` URL param or
  `VITE_DEBUG=1`.

## Map facts learned while debugging

- Tipped/stacked chairs and floor debris are DELIBERATE map decoration
  (abandoned facility) — not a rotation bug.
- The open blue pit near the pipes is the map's water channel: UE2 water
  here is an invisible zone portal, not geometry. Needs a water feature.
- Half the AGP_PlayerStarts are `bDeleteMe` with no Location — the client
  filters spawns with location (0,0,0).
- Low corridors are ~128 UU (2.44m); doors are real Movers that must be
  opened with E.

## Known gaps / next steps

- Terrain uses a single snow texture (real layer/alpha-map blending TODO).
- Foliage/masked textures approximate; some meshes' materials default gray.
- Static-mesh primitives participate in the raycast character collision system;
  this is required because parts of the building shell and floors are placed
  meshes rather than BSP.
- Assets are dev-quality (755MB PNGs, per-mesh glTF). For distribution:
  merge into one compressed GLB + KTX2 (gltf-transform), as originally planned.
- Mover sounds, lighting (currently generic ambient+sun, no lightmaps).

## Debug

Headless screenshots: `node <scratchpad>/shot.mjs out.png [x y z yawDeg]`
(Playwright; `window.__scene` is exposed by main.ts).
