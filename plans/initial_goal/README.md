# Initial goal

Build a small web-based FPS inspired by America's Army 2.5 (aa25assist).

## Stack

- **Client:** TypeScript + Babylon.js (WebGL2/WebGPU) + Vite — `client/`
- **Server:** Colyseus over WebSocket + TypeScript — `server/`
- UI done with Babylon GUI (in-canvas), no React.
- Original AA2.5 assets downloaded/extracted under `plans/aa25assist_download/` and `plans/aa25assist_extract/` — potential source for maps/models later.

## Milestones

1. **Client only, one map, one player** ✅
   - Simple walled arena map with crates (placeholder geometry).
   - First-person controller: WASD + mouse look (pointer lock), gravity, collisions.
2. **Real map: Pipeline SF converted from AA2.5 assets** ✅
   (BSP + terrain + 2.9k static meshes + doors + hitscan fire —
   see `plans/pipeline_sf_convert/README.md`)
3. Crosshair/HUD polish, visible weapon or player model.
4. Wire client to Colyseus `GameRoom`: sync player positions, see a second player move.
5. Shooting damage, health, respawn.
6. Asset optimization (single GLB + KTX2) for distribution.

## Run

See root `README.md` — `npm run dev` in `client/` (http://localhost:5173) and `server/` (ws://localhost:2567).
