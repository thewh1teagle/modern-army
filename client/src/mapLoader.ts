import { Scene } from "@babylonjs/core/scene";
import { Mesh } from "@babylonjs/core/Meshes/mesh";
import { VertexData } from "@babylonjs/core/Meshes/mesh.vertexData";
import { TransformNode } from "@babylonjs/core/Meshes/transformNode";
import { StandardMaterial } from "@babylonjs/core/Materials/standardMaterial";
import { Texture } from "@babylonjs/core/Materials/Textures/texture";
import { Color3 } from "@babylonjs/core/Maths/math.color";
import { Vector3, Quaternion } from "@babylonjs/core/Maths/math.vector";
import { SceneLoader } from "@babylonjs/core/Loading/sceneLoader";
import "@babylonjs/loaders/glTF/2.0";
import { pos, rot, UU } from "./ue";

// "assets" (dev, default): raw umodel export -- uncompressed PNGs + per-mesh
// .gltf/.bin, fast to regenerate while iterating on the pipeline scripts.
// "assets_optimized": WebP textures + draco-compressed .glb, fetched from a
// GitHub release and baked into the site by CI (see .github/workflows and
// plans/pipeline_sf_convert/README.md) -- opt-in via VITE_ASSET_DIR.
// VITE_ASSET_DIR may also be a full URL, to load assets from a different
// origin (e.g. a CDN) than the one serving the app itself.
// import.meta.env.BASE_URL is Vite's configured `base` (e.g. "/modern-army/"
// on GitHub Pages, "/" locally) -- same-origin asset paths must respect it.
const assetDir = import.meta.env.VITE_ASSET_DIR ?? "assets";
export const ASSET_BASE = /^https?:\/\//.test(assetDir)
  ? assetDir.replace(/\/$/, "")
  : `${import.meta.env.BASE_URL}${assetDir}`.replace(/\/\//g, "/");

// ---- data shapes (see plans/pipeline_sf_convert/*.py) ----
export interface MapData {
  staticMeshActors: {
    name: string;
    mesh: string;
    location: number[];
    rotation: number[];
    scale: number;
    scale3d: number[];
  }[];
  movers: {
    name: string;
    mesh: string;
    location: number[];
    rotation: number[];
    scale: number;
    scale3d: number[];
    keys: Record<string, number[]>;
    numKeys: number;
  }[];
  playerStarts: { name: string; location: number[]; rotation: number[]; team: number }[];
}
interface BspPoly {
  verts: number[][];
  uvs: number[][];
  texture: string;
  flags: number;
  twoSided: boolean;
}
interface AssetsIndex {
  meshes: Record<string, string>;
  textures: Record<string, { path: string; w: number; h: number }>;
}

async function json<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

export class MapLoader {
  private matCache = new Map<string, StandardMaterial>();
  index!: AssetsIndex;

  constructor(private scene: Scene) {}

  /** Material from a UE texture reference like "T-METAL.misc.met_misc_pipe03". */
  private material(texRef: string): StandardMaterial {
    const short = texRef.split(".").pop()!.toLowerCase();
    let mat = this.matCache.get(short);
    if (mat) return mat;
    mat = new StandardMaterial(`m_${short}`, this.scene);
    mat.specularColor = new Color3(0.05, 0.05, 0.05);
    const entry = this.index.textures[short];
    if (entry) {
      // invertY=false: UE and glTF UVs use a top-left origin
      const tex = new Texture(`${ASSET_BASE}/${entry.path}`, this.scene, false, false);
      tex.wrapU = tex.wrapV = Texture.WRAP_ADDRESSMODE;
      mat.diffuseTexture = tex;
      // alpha only for obviously-masked textures (fences, foliage, glass)
      const masked = /trans|alpha|fence|grate|leaf|foliage|branch|tree|glass|wire|rail|chain|_t$/.test(short);
      tex.hasAlpha = masked;
    } else {
      mat.diffuseColor = new Color3(0.5, 0.45, 0.4);
    }
    mat.backFaceCulling = true;
    this.matCache.set(short, mat);
    return mat;
  }

  /** Build the BSP world geometry, one mesh per texture. */
  async loadBsp(): Promise<void> {
    const bsp = await json<{ polys: BspPoly[] }>(`${ASSET_BASE}/map/bsp.json`);
    const byTex = new Map<string, BspPoly[]>();
    for (const p of bsp.polys) {
      const list = byTex.get(p.texture) ?? [];
      list.push(p);
      byTex.set(p.texture, list);
    }
    for (const [texRef, polys] of byTex) {
      const positions: number[] = [];
      const uvs: number[] = [];
      const indices: number[] = [];
      const short = texRef.split(".").pop()!.toLowerCase();
      const dims = this.index.textures[short] ?? { w: 256, h: 256 };
      for (const p of polys) {
        const base = positions.length / 3;
        for (let i = 0; i < p.verts.length; i++) {
          const v = p.verts[i];
          positions.push(-v[0] * UU, v[2] * UU, v[1] * UU);
          uvs.push(p.uvs[i][0] / dims.w, p.uvs[i][1] / dims.h);
        }
        // fan-triangulate; single winding — the material is double-sided
        for (let i = 2; i < p.verts.length; i++) {
          indices.push(base, base + i - 1, base + i);
        }
      }
      const mesh = new Mesh(`bsp_${short}`, this.scene);
      const vd = new VertexData();
      vd.positions = positions;
      vd.uvs = uvs;
      vd.indices = indices;
      const normals: number[] = [];
      VertexData.ComputeNormals(positions, indices, normals);
      vd.normals = normals;
      vd.applyToMesh(mesh);
      // some node polys wind the "wrong" way (coplanar BSP nodes) — render
      // world geometry double-sided so floors/walls never vanish
      const mat = this.material(texRef).clone(`bsp_${short}`)!;
      mat.backFaceCulling = false;
      mesh.material = mat;
      mesh.checkCollisions = true;
      mesh.freezeWorldMatrix();
    }
  }

  /** Heightmap terrains. */
  async loadTerrain(): Promise<void> {
    const t = await json<{
      terrains: {
        location: number[];
        scale: number[];
        uSize: number;
        vSize: number;
        heightsB64: string;
        hiddenQuadsB64?: string;
      }[];
    }>(`${ASSET_BASE}/map/terrain.json`);
    for (const ter of t.terrains) {
      const raw = atob(ter.heightsB64);
      const n = ter.uSize * ter.vSize;
      const heights = new Uint16Array(n);
      for (let i = 0; i < n; i++) heights[i] = raw.charCodeAt(2 * i) | (raw.charCodeAt(2 * i + 1) << 8);
      // Quads under indoor floors (see plans/pipeline_sf_convert/terrain_holes.py):
      // AA2.5's real QuadVisibilityBitmap isn't a tagged property umodel/extract_terrain.py
      // can read, so holes are approximated from BSP floor coverage instead.
      let hiddenQuads: Uint8Array | null = null;
      if (ter.hiddenQuadsB64) {
        const rawHidden = atob(ter.hiddenQuadsB64);
        hiddenQuads = new Uint8Array(rawHidden.length);
        for (let i = 0; i < rawHidden.length; i++) hiddenQuads[i] = rawHidden.charCodeAt(i);
      }

      const positions: number[] = [];
      const uvs: number[] = [];
      const indices: number[] = [];
      const [lx, ly, lz] = ter.location;
      const [sx, sy, sz] = ter.scale;
      for (let j = 0; j < ter.vSize; j++) {
        for (let i = 0; i < ter.uSize; i++) {
          const h = heights[j * ter.uSize + i];
          const x = lx + (i - ter.uSize / 2) * sx;
          const y = ly + (j - ter.vSize / 2) * sy;
          const z = lz + ((h - 32768) * sz) / 256;
          positions.push(-x * UU, z * UU, y * UU);
          uvs.push(i / 4, j / 4);
        }
      }
      const nQuadsX = ter.uSize - 1;
      for (let j = 0; j < ter.vSize - 1; j++) {
        for (let i = 0; i < nQuadsX; i++) {
          if (hiddenQuads) {
            const qIdx = j * nQuadsX + i;
            if ((hiddenQuads[qIdx >> 3] >> (qIdx & 7)) & 1) continue;
          }
          const a = j * ter.uSize + i;
          const b = a + 1;
          const c = a + ter.uSize;
          const d = c + 1;
          indices.push(a, c, b, b, c, d);
        }
      }
      const mesh = new Mesh("terrain", this.scene);
      const vd = new VertexData();
      vd.positions = positions;
      vd.uvs = uvs;
      vd.indices = indices;
      const normals: number[] = [];
      VertexData.ComputeNormals(positions, indices, normals);
      vd.normals = normals;
      vd.applyToMesh(mesh);
      const tmat = this.material("ter_snow_plain").clone("terrain_mat")!;
      tmat.backFaceCulling = false;
      mesh.material = tmat;
      mesh.checkCollisions = true;
      mesh.freezeWorldMatrix();
    }
  }

  /** Instantiate all static mesh actors (one glTF load per unique mesh). */
  async loadActors(map: MapData): Promise<void> {
    const byMesh = new Map<string, MapData["staticMeshActors"]>();
    for (const a of map.staticMeshActors) {
      const list = byMesh.get(a.mesh) ?? [];
      list.push(a);
      byMesh.set(a.mesh, list);
    }
    let missing = 0;
    const jobs: Promise<void>[] = [];
    for (const [meshRef, actors] of byMesh) {
      const parts = meshRef.split(".");
      const key = `${parts[0]}.${parts[parts.length - 1]}`.toLowerCase();
      const path = this.index.meshes[key];
      if (!path) {
        missing++;
        continue;
      }
      jobs.push(this.instantiate(path, actors));
    }
    await Promise.all(jobs);
    if (missing) console.warn(`${missing} meshes not found in export`);
  }

  private async instantiate(path: string, actors: MapData["staticMeshActors"]): Promise<void> {
    const dir = `${ASSET_BASE}/${path.substring(0, path.lastIndexOf("/") + 1)}`;
    const file = path.substring(path.lastIndexOf("/") + 1);
    const res = await SceneLoader.ImportMeshAsync(null, dir, file, this.scene);
    const root = res.meshes[0]; // gltf __root__
    // apply umodel material names → textures
    for (const m of res.meshes) {
      if (m.material) m.material = this.material(m.material.name);
    }
    root.setEnabled(false);
    for (const a of actors) {
      const inst = new TransformNode(a.name, this.scene);
      const clone = root.clone(a.name + "_m", inst)!;
      clone.setEnabled(true);
      inst.position = pos(a.location);
      inst.rotationQuaternion = rot(a.rotation);
      // umodel glTF exports at 1 unit = 100 UU; our world is 52.5 UU/m.
      // negative X mirrors the mesh to match the negated world X axis.
      const s = (a.scale ?? 1) * (100 / 52.5);
      inst.scaling = new Vector3(-s * a.scale3d[0], s * a.scale3d[2], s * a.scale3d[1]);

      // A significant part of Pipeline's floors and building shell is made
      // from placed static meshes rather than BSP.  Leaving these meshes
      // non-collidable lets the raycast character controller fall through a
      // room and walk into the snowy pipe/service space below it.
      for (const child of clone.getChildMeshes(false)) {
        child.checkCollisions = true;
        child.isPickable = true;
      }
    }
  }
}

export async function loadMap(scene: Scene): Promise<MapData> {
  const loader = new MapLoader(scene);
  loader.index = await json(`${ASSET_BASE}/map/assets_index.json`);
  const map = await json<MapData>(`${ASSET_BASE}/map/map.json`);
  await loader.loadBsp();
  await loader.loadTerrain();
  await loader.loadActors(map);
  return map;
}
