import { Scene } from "@babylonjs/core/scene";
import { UniversalCamera } from "@babylonjs/core/Cameras/universalCamera";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import { Ray } from "@babylonjs/core/Culling/ray";
import { AbstractMesh } from "@babylonjs/core/Meshes/abstractMesh";
import { pos } from "./ue";
import type { MapData } from "./mapLoader";

const EYE_HEIGHT = 1.7;
const WALK_SPEED = 4.5; // m/s
const RUN_SPEED = 7.5;
const MOUSE_SENSITIVITY = 4000;
const GRAVITY = -14; // m/s²
const JUMP_SPEED = 5; // m/s
const STEP_SNAP = 0.35; // max step height to snap up

export function createPlayer(scene: Scene, canvas: HTMLCanvasElement, map: MapData): UniversalCamera {
  const valid = map.playerStarts.filter((s) => s.location.some((v) => v !== 0));
  let start = valid[Math.floor(Math.random() * valid.length)];

  // Deterministic traversal testing without changing normal random spawns:
  // ?spawn=<ue-x>,<ue-y>,<ue-z>[,<ue-yaw-units>]
  const spawnParam = new URLSearchParams(location.search).get("spawn");
  if (spawnParam) {
    const values = spawnParam.split(",").map(Number);
    if (values.length >= 3 && values.every(Number.isFinite)) {
      start = {
        name: "DebugSpawn",
        location: values.slice(0, 3),
        rotation: [0, values[3] ?? 0, 0],
        team: 0,
      };
    }
  }
  const spawn = pos(start.location).add(new Vector3(0, 0.9, 0));

  const camera = new UniversalCamera("player", spawn.clone(), scene);
  camera.rotation.y = (start.rotation[1] * 2 * Math.PI) / 65536;
  camera.attachControl(canvas, true);

  camera.inertia = 0.4; // mouse smoothing only — keys are handled manually
  camera.angularSensibility = MOUSE_SENSITIVITY;
  camera.minZ = 0.05;
  camera.maxZ = 2000;
  // default key movement follows the LOOK direction (walking into the floor
  // when looking down) — disable it, movement is planar and manual below
  camera.keysUp = [];
  camera.keysDown = [];
  camera.keysLeft = [];
  camera.keysRight = [];

  // all collision handled manually via raycasts (Babylon's ellipsoid collider
  // wedges/jams against the large merged BSP meshes)
  camera.checkCollisions = false;
  camera.applyGravity = false;

  const collidable = (m: AbstractMesh): boolean => m.checkCollisions && m.isEnabled();
  const keys = new Set<string>();
  let speed = WALK_SPEED;
  let vy = 0;
  let grounded = false;

  // Raycast-based gravity: immune to tunneling through thin BSP floors.
  scene.onBeforeRenderObservable.add(() => {
    const dt = Math.min(scene.getEngine().getDeltaTime() / 1000, 0.05);

    // planar WASD movement (ignores pitch), applied through the collider
    const fwd = camera.getDirection(Vector3.Forward());
    fwd.y = 0;
    fwd.normalize();
    const right = camera.getDirection(Vector3.Right());
    right.y = 0;
    right.normalize();
    const move = fwd
      .scale((keys.has("KeyW") ? 1 : 0) - (keys.has("KeyS") ? 1 : 0))
      .add(right.scale((keys.has("KeyD") ? 1 : 0) - (keys.has("KeyA") ? 1 : 0)));
    if (move.lengthSquared() > 0) {
      move.normalize();
      let step = move.scale(speed * dt);
      // wall check at knee and chest height; slide along the wall plane on hit
      const RADIUS = 0.35;
      for (let attempt = 0; attempt < 2; attempt++) {
        const len = step.length();
        if (len < 1e-5) break;
        const dir = step.scale(1 / len);
        let blockedNormal: Vector3 | null = null;
        for (const dy of [-EYE_HEIGHT + 0.5, -0.6]) {
          const origin = camera.position.clone();
          origin.y += dy;
          const hit = scene.pickWithRay(new Ray(origin, dir, len + RADIUS), collidable);
          if (hit?.hit && hit.getNormal(true)) {
            blockedNormal = hit.getNormal(true)!;
            break;
          }
        }
        if (!blockedNormal) {
          camera.position.addInPlace(step);
          break;
        }
        // slide: remove the component of movement into the wall
        blockedNormal.y = 0;
        if (blockedNormal.lengthSquared() < 1e-6) break;
        blockedNormal.normalize();
        step = step.subtract(blockedNormal.scale(Vector3.Dot(step, blockedNormal)));
      }
    }
    const ray = new Ray(camera.position, Vector3.Down(), 500);
    const hit = scene.pickWithRay(ray, collidable);
    const floorY = hit?.pickedPoint ? hit.pickedPoint.y : -Infinity;
    const standY = floorY + EYE_HEIGHT;

    vy += GRAVITY * dt;
    let newY = camera.position.y + vy * dt;
    const rise = standY - camera.position.y;

    if (newY <= standY && rise <= STEP_SNAP) {
      // Landed, or walking up a step no taller than STEP_SNAP. Without the
      // rise check, a downward ray beneath railings/pipes can teleport the
      // player upward onto them from well below.
      newY = standY;
      vy = 0;
      grounded = true;
    } else if (rise <= 0 && camera.position.y <= standY + STEP_SNAP && vy <= 0) {
      // Keep feet planted while walking down shallow steps.
      newY = standY;
      vy = 0;
      grounded = true;
    } else {
      grounded = false;
    }
    camera.position.y = newY;

    // fell out of the world → respawn
    if (camera.position.y < -120) {
      camera.position.copyFrom(spawn);
      vy = 0;
    }
  });

  window.addEventListener("keydown", (e) => {
    keys.add(e.code);
    if (e.code === "Space" && grounded) vy = JUMP_SPEED;
    if (e.code === "ShiftLeft") speed = RUN_SPEED;
  });
  window.addEventListener("keyup", (e) => {
    keys.delete(e.code);
    if (e.code === "ShiftLeft") speed = WALK_SPEED;
  });
  window.addEventListener("blur", () => keys.clear());

  canvas.addEventListener("click", () => {
    if (document.pointerLockElement !== canvas) canvas.requestPointerLock();
  });

  return camera;
}
