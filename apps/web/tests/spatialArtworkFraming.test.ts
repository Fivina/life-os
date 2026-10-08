// @vitest-environment node
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import { Box3, BufferGeometry, Mesh, Object3D, PerspectiveCamera, Vector3 } from "three";
import { describe, expect, it } from "vitest";
import { domainCamera, domainMoonFrame, entranceCamera, moonPosition } from "../src/features/hub/spatialJourney";
import { spatialDomains } from "../src/features/hub/spatialNavigation";
import { spatialMoonCatalog } from "../src/features/hub/spatialMoonCatalog";
import { artBoxCorners, artworkObjectBounds, placeArtObject, type ArtCameraPose } from "../src/features/hub/systemArtMotion";

type ExportNode = {
  name?: string; children?: number[]; mesh?: number; extras?: Record<string, unknown>;
  translation?: [number, number, number]; rotation?: [number, number, number, number]; scale?: [number, number, number]; matrix?: number[];
};
type ExportDocument = {
  nodes: ExportNode[]; scenes: { nodes: number[] }[]; scene?: number;
  meshes: { primitives: { attributes: { POSITION: number } }[] }[];
  accessors: { min?: [number, number, number]; max?: [number, number, number] }[];
};
const binary = readFileSync(new URL("../public/art/system/life-os-system-v37.glb", import.meta.url));
const exported = JSON.parse(binary.subarray(20, 20 + binary.readUInt32LE(12)).toString()) as ExportDocument;
const viewports = [{ width: 1440, height: 900 }, { width: 390, height: 844 }];
const stylesheet = readFileSync(new URL("../src/features/hub/system-art-preview.css", import.meta.url), "utf8");

describe("projected label stylesheet states (DOM model, not browser rendering)", () => {
  it.each([
    { projected: false, moving: false, visibility: "hidden" },
    { projected: true, moving: false, visibility: "visible" },
    { projected: true, moving: true, visibility: "hidden" },
  ])("uses $visibility for projected=$projected moving=$moving", ({ projected, moving, visibility }) => {
    const dom = new JSDOM(`<style>${stylesheet}</style><main class="system-art-preview" data-moving="${moving}">
      <button class="system-art-label" ${projected ? 'data-projected="true"' : ""}>Self Core</button></main>`);
    try {
      expect(dom.window.getComputedStyle(dom.window.document.querySelector("button")!).visibility).toBe(visibility);
    } finally { dom.window.close(); }
  });
});

// Read authored transforms and POSITION bounds only: no textures, renderer, or browser.
function boundsFor(viewport: { width: number; height: number }) {
  const objects = exported.nodes.map(node => {
    const object = new Object3D();
    object.name = node.name ?? "";
    object.userData = node.extras ?? {};
    if (node.matrix) object.matrix.fromArray(node.matrix).decompose(object.position, object.quaternion, object.scale);
    else {
      if (node.translation) object.position.fromArray(node.translation);
      if (node.rotation) object.quaternion.fromArray(node.rotation);
      if (node.scale) object.scale.fromArray(node.scale);
    }
    for (const primitive of node.mesh === undefined ? [] : exported.meshes[node.mesh].primitives) {
      const accessor = exported.accessors[primitive.attributes.POSITION];
      expect(accessor.min).toBeDefined(); expect(accessor.max).toBeDefined();
      const geometry = new BufferGeometry();
      geometry.boundingBox = new Box3(new Vector3(...accessor.min!), new Vector3(...accessor.max!));
      object.add(new Mesh(geometry));
    }
    return object;
  });
  exported.nodes.forEach((node, index) => node.children?.forEach(child => objects[index].add(objects[child])));
  const scene = new Object3D();
  exported.scenes[exported.scene ?? 0].nodes.forEach(index => scene.add(objects[index]));
  const bounds: Record<string, Box3> = {};
  for (const name of ["SelfCore", ...spatialDomains.map(domain => domain.label)]) {
    const root = scene.getObjectByName(name)!;
    expect(root, name).toBeDefined();
    placeArtObject(root, { position: root.position.clone(), scale: root.scale.clone() }, viewport.width / viewport.height < 0.8);
    bounds[name] = artworkObjectBounds(root);
  }
  scene.traverse(object => { if (object instanceof Mesh) { object.geometry.dispose(); } });
  return bounds;
}

function cameraFor(pose: ArtCameraPose, viewport: { width: number; height: number }) {
  const camera = new PerspectiveCamera(pose.fov, viewport.width / viewport.height, 0.05, 200);
  camera.position.copy(pose.position); camera.quaternion.copy(pose.quaternion);
  camera.updateMatrixWorld(true);
  return camera;
}

function inside(point: Vector3, camera: PerspectiveCamera) {
  const projected = point.clone().project(camera);
  return Math.abs(projected.x) < 1 && Math.abs(projected.y) < 1 && projected.z > -1 && projected.z < 1;
}

describe.each(viewports)("actual V37 geometric framing at $width x $height", viewport => {
  it("contains the authored Core at the entrance destination", () => {
    const bounds = boundsFor(viewport);
    const camera = cameraFor(entranceCamera(viewport), viewport);
    expect(artBoxCorners(bounds.SelfCore).every(point => inside(point, camera))).toBe(true);
  });

  it.each(spatialDomains)("frames $label and its entire moon orbit with distant system context", domain => {
    const bounds = boundsFor(viewport);
    const frame = domainMoonFrame(bounds[domain.label], bounds.SelfCore.getCenter(new Vector3()));
    const camera = cameraFor(domainCamera(frame, viewport), viewport);
    expect(artBoxCorners(bounds[domain.label]).every(point => inside(point, camera))).toBe(true);
    // Sample a complete slow orbit, not only the initially mounted moon positions.
    for (let sample = 0; sample < 96; sample++) {
      const center = moonPosition(frame, sample, 96);
      const radius = new Vector3().setScalar(frame.radius * 0.235);
      expect(artBoxCorners(new Box3(center.clone().sub(radius), center.clone().add(radius)))
        .every(point => inside(point, camera)), `orbit sample ${sample}`).toBe(true);
    }
    const distant = ["SelfCore", ...spatialDomains.filter(item => item.id !== domain.id).map(item => item.label)]
      .filter(name => inside(bounds[name].getCenter(new Vector3()), camera));
    expect(distant.length, "at least two wider-system centers inside the camera frustum; not occlusion proof").toBeGreaterThanOrEqual(2);
    expect(spatialMoonCatalog[domain.id].length).toBeGreaterThan(0);
  });
});
