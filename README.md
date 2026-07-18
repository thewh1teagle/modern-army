# modern-army

Web-based multiplayer FPS inspired by America's Army 2.5.

- `client/` — TypeScript + Babylon.js + Vite
- `server/` — Colyseus (WebSocket) game server

## Development

```sh
# client
cd client
npm install
npm run dev   # http://localhost:5173

# server
cd server
npm install
npm run dev   # ws://localhost:2567
```

## Controls

Click the canvas to lock the mouse. WASD move, mouse look, Shift sprint,
Space jump, E open/close doors, left-click fire, Esc releases the mouse.

The client loads the converted AA2.5 **Pipeline SF** map. Conversion pipeline
and docs: `plans/pipeline_sf_convert/README.md` (requires the extracted assets
in `plans/aa25assist_extract/`, not committed).
