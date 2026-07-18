import { Engine } from "@babylonjs/core/Engines/engine";
import { Scene } from "@babylonjs/core/scene";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import { HemisphericLight } from "@babylonjs/core/Lights/hemisphericLight";
import { DirectionalLight } from "@babylonjs/core/Lights/directionalLight";
import { Color3, Color4 } from "@babylonjs/core/Maths/math.color";
import "@babylonjs/core/Collisions/collisionCoordinator";
import "@babylonjs/core/Culling/ray";
import { ASSET_BASE, MapLoader, loadMap } from "./mapLoader";
import { createPlayer } from "./player";
import { Movers } from "./movers";
import { setupFire, addCrosshair } from "./fire";
import { addDebugHud } from "./debugHud";
import { addGameplayHud } from "./gameplayHud";

const canvas = document.getElementById("app") as HTMLCanvasElement;
// Render at the browser's actual device-pixel ratio. The map's fine texture
// detail otherwise looks soft, especially when the browser is zoomed.
const engine = new Engine(canvas, true, undefined, true);

async function start(): Promise<void> {
  const scene = new Scene(engine);
  scene.clearColor = new Color4(0.55, 0.65, 0.75, 1); // arctic sky
  scene.collisionsEnabled = true;
  scene.gravity = new Vector3(0, -0.12, 0); // per-frame; too high grinds against floors
  Engine.CollisionsEpsilon = 0.01; // default 0.001 makes the collider stick/sink
  scene.fogMode = Scene.FOGMODE_LINEAR;
  scene.fogStart = 150;
  scene.fogEnd = 600;
  scene.fogColor = new Color3(0.55, 0.65, 0.75);
  // A restrained contrast lift preserves the original cool sky palette.
  // ACES tone mapping is intentionally avoided here: these legacy diffuse
  // textures are already display-referred and ACES turns the sky muddy tan.
  scene.imageProcessingConfiguration.contrast = 1.08;

  const amb = new HemisphericLight("ambient", new Vector3(0, 1, 0), scene);
  amb.intensity = 0.78;
  amb.groundColor = new Color3(0.32, 0.35, 0.42);
  const sun = new DirectionalLight("sun", new Vector3(-0.4, -1, -0.3), scene);
  sun.intensity = 0.7;

  const map = await loadMap(scene);
  const camera = createPlayer(scene, canvas, map);

  const movers = new Movers(scene);
  const loader = new MapLoader(scene);
  loader.index = await (await fetch(`${ASSET_BASE}/map/assets_index.json`)).json();
  await movers.load(map, loader);

  setupFire(scene, camera, canvas);
  addCrosshair();
  addGameplayHud(canvas);
  addDebugHud(scene, camera);

  (window as any).__scene = scene; // debug/screenshot hook
  engine.runRenderLoop(() => scene.render());

  const loading = document.getElementById("loading");
  loading?.classList.add("ready");
  loading?.addEventListener("transitionend", () => loading.remove(), { once: true });
}

start().catch((e) => {
  console.error("failed to start", e);
  document.body.innerHTML = `<pre style="color:red;padding:1em">${e}</pre>`;
});

window.addEventListener("resize", () => engine.resize());
