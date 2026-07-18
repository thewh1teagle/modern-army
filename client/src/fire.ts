import { Scene } from "@babylonjs/core/scene";
import { UniversalCamera } from "@babylonjs/core/Cameras/universalCamera";
import { MeshBuilder } from "@babylonjs/core/Meshes/meshBuilder";
import { StandardMaterial } from "@babylonjs/core/Materials/standardMaterial";
import { Color3 } from "@babylonjs/core/Maths/math.color";

/** Hitscan fire: ray from screen center, leave a small impact mark. */
export function setupFire(scene: Scene, camera: UniversalCamera, canvas: HTMLCanvasElement): void {
  const impactMat = new StandardMaterial("impact", scene);
  impactMat.diffuseColor = new Color3(0.1, 0.1, 0.1);
  impactMat.emissiveColor = new Color3(0.2, 0.15, 0.1);

  canvas.addEventListener("mousedown", (e) => {
    if (e.button !== 0 || document.pointerLockElement !== canvas) return;
    const ray = camera.getForwardRay(300);
    const hit = scene.pickWithRay(ray, (m) => m.isPickable && m.isEnabled());
    if (hit?.pickedPoint) {
      const mark = MeshBuilder.CreateSphere("hit", { diameter: 0.06, segments: 4 }, scene);
      mark.position = hit.pickedPoint;
      mark.material = impactMat;
      mark.isPickable = false;
      setTimeout(() => mark.dispose(), 10_000);
    }
  });
}

/** Simple crosshair overlay. */
export function addCrosshair(): void {
  const el = document.createElement("div");
  el.style.cssText =
    "position:fixed;left:50%;top:50%;width:8px;height:8px;margin:-4px 0 0 -4px;" +
    "border:1.5px solid rgba(255,255,255,.85);border-radius:50%;pointer-events:none;z-index:10";
  document.body.appendChild(el);
}
