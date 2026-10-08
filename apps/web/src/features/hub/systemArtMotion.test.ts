import { Box3, BoxGeometry, Group, Mesh, MeshBasicMaterial, PerspectiveCamera, Vector3 } from "three";
import { describe, expect, it } from "vitest";
import { ART_LABEL_HEIGHT, ART_LABEL_WIDTH, artBoxCorners, artCameraPose, artworkObjectBounds, artSafeArea, fallbackArtCamera, fitArtCamera, placeArtLabels, placeArtObject, portraitArtCamera, portraitArtTransform } from "./systemArtMotion";

const bounds = new Box3(new Vector3(-9, -5, -4), new Vector3(8, 4, 5));

describe("static system art framing", () => {
  it("uses a separately authored portrait view rather than the desktop camera", () => {
    const portrait = portraitArtCamera();
    expect(portrait.position.equals(fallbackArtCamera().position)).toBe(false);
    expect(portrait.fov).toBeGreaterThan(40);
    expect(portraitArtTransform({ art_portrait_position: [-1.28, 0.35, -0.7], art_portrait_scale: 0.7 }))
      .toEqual({ position: new Vector3(-1.28, 0.35, -0.7), scale: 0.7 });
  });

  it.each([
    {}, { art_portrait_position: [0, 0], art_portrait_scale: 1 },
    { art_portrait_position: [0, NaN, 0], art_portrait_scale: 1 },
    { art_portrait_position: [0, 0, 0], art_portrait_scale: -1 },
    { art_portrait_position: [0, 0, 30], art_portrait_scale: 1 },
  ])("rejects unusable portrait metadata %j", metadata => {
    expect(portraitArtTransform(metadata)).toBeNull();
  });

  it("places portrait foreground without accumulating scale and restores desktop staging", () => {
    const scenery = new Group();
    const authored = { position: new Vector3(0, 0, 0), scale: new Vector3(1, 2, 1) };
    scenery.userData = { art_portrait_position: [-0.6, -1.4, 5.5], art_portrait_scale: 0.38 };
    placeArtObject(scenery, authored, true);
    placeArtObject(scenery, authored, true);
    expect(scenery.position).toEqual(new Vector3(-0.6, -1.4, 5.5));
    expect(scenery.scale).toEqual(new Vector3(0.38, 0.76, 0.38));
    placeArtObject(scenery, authored, false);
    expect(scenery.position).toEqual(authored.position);
    expect(scenery.scale).toEqual(authored.scale);
    expect(authored.scale).toEqual(new Vector3(1, 2, 1));
  });

  it("uses the authored object pose for malformed portrait metadata", () => {
    const object = new Group();
    const authored = { position: new Vector3(2, 1, 0), scale: new Vector3(0.67, 0.67, 0.67) };
    object.userData = { art_portrait_position: [0, NaN, 1], art_portrait_scale: 0.7 };
    placeArtObject(object, authored, true);
    expect(object.position).toEqual(authored.position);
    expect(object.scale).toEqual(authored.scale);
  });

  it("excludes the faint optical envelope from body labels and framing bounds", () => {
    const root = new Group();
    const material = new MeshBasicMaterial();
    const body = new Mesh(new BoxGeometry(2, 2, 2), material);
    const halo = new Mesh(new BoxGeometry(10, 10, 0.01), material);
    halo.userData.art_bounds_exclude = true;
    root.position.set(3, 4, 5);
    root.add(body, halo);
    expect(artworkObjectBounds(root)).toEqual(new Box3(new Vector3(2, 3, 4), new Vector3(4, 5, 6)));
    body.geometry.dispose(); halo.geometry.dispose(); material.dispose();
  });
  it("preserves the authored wide system camera exactly", () => {
    const authored = fallbackArtCamera();
    const pose = artCameraPose(bounds, authored, { width: 1920, height: 1080 }, true);
    expect(pose.position.equals(authored.position)).toBe(true);
    expect(pose.quaternion.equals(authored.quaternion)).toBe(true);
    expect(pose.fov).toBe(authored.fov);
  });

  it.each([{ width: 320, height: 568 }, { width: 390, height: 844 }, { width: 844, height: 390 }])(
    "fits every exported bound with control/label clearance at $width x $height", viewport => {
      const pose = fitArtCamera(bounds, fallbackArtCamera(), viewport);
      const camera = new PerspectiveCamera(pose.fov, viewport.width / viewport.height, 0.05, 1000);
      camera.position.copy(pose.position);
      camera.quaternion.copy(pose.quaternion);
      camera.updateMatrixWorld(true);
      const safe = artSafeArea(viewport);
      for (const corner of artBoxCorners(bounds)) {
        const point = corner.project(camera);
        const x = (point.x / 2 + 0.5) * viewport.width;
        const y = (-point.y / 2 + 0.5) * viewport.height;
        expect(x).toBeGreaterThan(safe.left + ART_LABEL_WIDTH / 2);
        expect(x).toBeLessThan(safe.right - ART_LABEL_WIDTH / 2);
        expect(y).toBeGreaterThan(safe.top);
        expect(y).toBeLessThan(safe.bottom);
        expect(point.z).toBeGreaterThan(-1);
        expect(point.z).toBeLessThan(1);
      }
    }
  );

  it.each([{ width: 320, height: 568 }, { width: 390, height: 844 }, { width: 844, height: 390 }])(
    "keeps all seven coincident labels stable, reachable and unclipped at $width x $height", viewport => {
      const anchors = ["SelfCore", "Settings", "Calendar", "Learning", "Home", "Life", "Fitness"].map(id => ({ id, x: -100, y: viewport.height * 2 }));
      const placed = placeArtLabels(anchors, viewport);
      expect(placeArtLabels(anchors, viewport)).toEqual(placed);
      const safe = artSafeArea(viewport);
      for (const [index, label] of placed.entries()) {
        expect(label.x - ART_LABEL_WIDTH / 2).toBeGreaterThanOrEqual(safe.left);
        expect(label.x + ART_LABEL_WIDTH / 2).toBeLessThanOrEqual(safe.right);
        expect(label.y - ART_LABEL_HEIGHT / 2).toBeGreaterThanOrEqual(safe.top);
        expect(label.y + ART_LABEL_HEIGHT / 2).toBeLessThanOrEqual(safe.bottom);
        for (const other of placed.slice(index + 1)) {
          expect(Math.abs(label.x - other.x) >= ART_LABEL_WIDTH + 8 || Math.abs(label.y - other.y) >= ART_LABEL_HEIGHT + 8).toBe(true);
        }
      }
    }
  );
});
