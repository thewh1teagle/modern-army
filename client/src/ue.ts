import { Vector3, Quaternion } from "@babylonjs/core/Maths/math.vector";

/** UE2 → Babylon conversion.
 *
 * UE2: left-handed, Z-up, 1m ≈ 52.5 UU. Babylon: left-handed, Y-up.
 * Map (x, y, z)ue → (x, z, y)babylon, scaled to meters.
 * Rotators are 16-bit angle units (65536 = 360°), order roll(X) pitch(Y) yaw(Z).
 */
export const UU = 1 / 52.5;

export function pos(v: [number, number, number] | number[]): Vector3 {
  // negate X: a plain (x,z,y) swap mirrors the world (UE is LH about Z-up);
  // negating one axis restores the original handedness/layout
  return new Vector3(-v[0] * UU, v[2] * UU, v[1] * UU);
}

const R2 = (2 * Math.PI) / 65536;

/** Rotator [pitch, yaw, roll] in UE units → Babylon quaternion. */
export function rot(r: [number, number, number] | number[]): Quaternion {
  const [pitch, yaw, roll] = r;
  // with X negated, yaw/roll flip sign relative to the previous mapping
  return Quaternion.RotationYawPitchRoll(yaw * R2, -pitch * R2, -roll * R2);
}

export const YAW = (yawUnits: number): number => yawUnits * R2;
