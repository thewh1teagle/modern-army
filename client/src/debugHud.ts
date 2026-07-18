import { Scene } from "@babylonjs/core/scene";
import { UniversalCamera } from "@babylonjs/core/Cameras/universalCamera";
import { UU } from "./ue";

/** On-screen debug overlay. Enabled with `VITE_DEBUG=1 npm run dev`
 *  (or `?debug` in the URL as a runtime override). */
export function isDebug(): boolean {
  return import.meta.env.VITE_DEBUG === "1" || new URLSearchParams(location.search).has("debug");
}

export function addDebugHud(scene: Scene, camera: UniversalCamera): void {
  if (!isDebug()) return;
  const el = document.createElement("div");
  el.style.cssText =
    "position:fixed;top:8px;left:8px;padding:6px 10px;background:rgba(0,0,0,.65);" +
    "color:#8f8;font:12px/1.5 monospace;white-space:pre;pointer-events:none;z-index:20";
  document.body.appendChild(el);

  const compass = (yawDeg: number): string => {
    const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    return dirs[Math.round(((yawDeg % 360) + 360) % 360 / 45) % 8];
  };

  scene.onAfterRenderObservable.add(() => {
    const p = camera.position;
    const yaw = (camera.rotation.y * 180) / Math.PI;
    const pitch = (camera.rotation.x * 180) / Math.PI;
    const fwd = camera.getForwardRay(1).direction;
    el.textContent =
      `pos  bab(${p.x.toFixed(1)}, ${p.y.toFixed(1)}, ${p.z.toFixed(1)})\n` +
      `     ue (${(-p.x / UU).toFixed(0)}, ${(p.z / UU).toFixed(0)}, ${(p.y / UU).toFixed(0)})\n` +
      `yaw  ${yaw.toFixed(0)}° (${compass(yaw)})  pitch ${pitch.toFixed(0)}°\n` +
      `fwd  (${fwd.x.toFixed(2)}, ${fwd.y.toFixed(2)}, ${fwd.z.toFixed(2)})\n` +
      `fps  ${scene.getEngine().getFps().toFixed(0)}`;
  });
}
