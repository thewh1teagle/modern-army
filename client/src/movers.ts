import { Scene } from "@babylonjs/core/scene";
import { TransformNode } from "@babylonjs/core/Meshes/transformNode";
import { Vector3, Quaternion } from "@babylonjs/core/Maths/math.vector";
import { Animation } from "@babylonjs/core/Animations/animation";
import "@babylonjs/core/Animations/animatable";
import { UniversalCamera } from "@babylonjs/core/Cameras/universalCamera";
import { pos, rot } from "./ue";
import type { MapData, MapLoader } from "./mapLoader";

interface Door {
  node: TransformNode;
  closedPos: Vector3;
  openPos: Vector3;
  closedRot: Quaternion;
  openRot: Quaternion;
  open: boolean;
}

/** Movers: doors/lifts. Base keyframe = closed, key 1 = open. Toggle with E. */
export class Movers {
  private doors: Door[] = [];

  constructor(private scene: Scene) {}

  async load(map: MapData, loader: MapLoader): Promise<void> {
    for (const mv of map.movers) {
      if (!mv.mesh) continue;
      const parts = mv.mesh.split(".");
      const key = `${parts[0]}.${parts[parts.length - 1]}`.toLowerCase();
      const path = loader.index.meshes[key];
      if (!path) continue;
      // reuse loader's instantiate path via a fake single-actor list
      await loader["instantiate"](path, [
        { name: mv.name, mesh: mv.mesh, location: mv.location, rotation: mv.rotation, scale: mv.scale, scale3d: mv.scale3d },
      ]);
      const node = this.scene.getTransformNodeByName(mv.name);
      if (!node) continue;
      node.getChildMeshes().forEach((m) => (m.checkCollisions = true));

      const basePos = mv.keys["BasePos"] ?? mv.location;
      const baseRot = mv.keys["BaseRot"] ?? mv.rotation;
      const openPosUE = mv.keys["KeyPos[1]"];
      const openRotUE = mv.keys["KeyRot[1]"];
      const closedPos = pos(basePos);
      const closedRot = rot(baseRot);
      // KeyPos/KeyRot are deltas from base in UE2 movers
      const openPos = openPosUE
        ? pos([basePos[0] + openPosUE[0], basePos[1] + openPosUE[1], basePos[2] + openPosUE[2]])
        : closedPos.clone();
      const openRot = openRotUE
        ? rot([baseRot[0] + openRotUE[0], baseRot[1] + openRotUE[1], baseRot[2] + openRotUE[2]])
        : closedRot.clone();
      node.position = closedPos;
      node.rotationQuaternion = closedRot;
      this.doors.push({ node, closedPos, openPos, closedRot, openRot, open: false });
    }

    window.addEventListener("keydown", (e) => {
      if (e.code === "KeyE") this.toggleNearest();
    });
    console.log(`${this.doors.length} movers ready`);
  }

  private toggleNearest(): void {
    const cam = this.scene.activeCamera as UniversalCamera | null;
    if (!cam) return;
    let best: Door | null = null;
    let bestD = 4; // meters
    for (const d of this.doors) {
      const dist = d.node.position.subtract(cam.position).length();
      if (dist < bestD) {
        bestD = dist;
        best = d;
      }
    }
    if (!best) return;
    best.open = !best.open;
    const fps = 30;
    const frames = 25;
    Animation.CreateAndStartAnimation("doorPos", best.node, "position", fps, frames,
      best.node.position.clone(), best.open ? best.openPos : best.closedPos, Animation.ANIMATIONLOOPMODE_CONSTANT);
    Animation.CreateAndStartAnimation("doorRot", best.node, "rotationQuaternion", fps, frames,
      best.node.rotationQuaternion!.clone(), best.open ? best.openRot : best.closedRot, Animation.ANIMATIONLOOPMODE_CONSTANT);
  }
}
