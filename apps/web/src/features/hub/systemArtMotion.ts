import { Box3, MathUtils, Mesh, Object3D, PerspectiveCamera, Quaternion, Vector3 } from "three";

// Authored framing helpers; spatialJourney coordinates continuous camera travel separately.
export type ArtCameraPose = { position: Vector3; quaternion: Quaternion; fov: number };
export type ArtViewport = { width: number; height: number };
export type LabelAnchor = { id: string; x: number; y: number };
export const ART_LABEL_WIDTH = 108;
export const ART_LABEL_HEIGHT = 44;

export function portraitArtCamera(): ArtCameraPose {
  const camera = new PerspectiveCamera(MathUtils.radToDeg(2 * Math.atan(18 / 43)));
  camera.position.set(0, 8.3, 13);
  camera.lookAt(0, 0, -0.45);
  return { position: camera.position.clone(), quaternion: camera.quaternion.clone(), fov: camera.fov };
}

export function portraitArtTransform(metadata: Record<string, unknown>) {
  const position = metadata.art_portrait_position;
  const scale = metadata.art_portrait_scale;
  if (!Array.isArray(position) || position.length !== 3 ||
      !position.every(value => typeof value === "number" && Number.isFinite(value) && Math.abs(value) <= 20) ||
      typeof scale !== "number" || !Number.isFinite(scale) || scale < 0.2 || scale > 1.5) return null;
  return { position: new Vector3(position[0], position[1], position[2]), scale };
}

export function placeArtObject(root: Object3D, authored: { position: Vector3; scale: Vector3 }, portrait: boolean) {
  const tall = portrait ? portraitArtTransform(root.userData) : null;
  root.position.copy(tall?.position ?? authored.position);
  root.scale.copy(authored.scale).multiplyScalar(tall?.scale ?? 1);
}

export function artworkObjectBounds(root: Object3D): Box3 {
  root.updateWorldMatrix(true, true);
  const bounds = new Box3();
  root.traverse(object => {
    if (!(object instanceof Mesh)) return;
    // Optical scattering extends beyond the body, but must not displace its
    // label or shrink the entire composition to fit an almost invisible edge.
    for (let ancestor: Object3D | null = object; ancestor; ancestor = ancestor.parent) {
      if (ancestor.userData.art_bounds_exclude === true) return;
      if (ancestor === root) break;
    }
    if (!object.geometry.boundingBox) object.geometry.computeBoundingBox();
    if (object.geometry.boundingBox) bounds.union(object.geometry.boundingBox.clone().applyMatrix4(object.matrixWorld));
  });
  return bounds;
}

export function fallbackArtCamera(): ArtCameraPose {
  const camera = new PerspectiveCamera(42);
  camera.position.set(0, 12.5, 19.5);
  camera.lookAt(0, 0, -0.1);
  return { position: camera.position.clone(), quaternion: camera.quaternion.clone(), fov: camera.fov };
}

export function artBoxCorners(box: Box3): Vector3[] {
  return [box.min.x, box.max.x].flatMap(x =>
    [box.min.y, box.max.y].flatMap(y => [box.min.z, box.max.z].map(z => new Vector3(x, y, z)))
  );
}

export function artSafeArea({ width, height }: ArtViewport) {
  return {
    left: 16,
    right: Math.max(16, width - 16),
    top: Math.min(84, height * 0.2),
    bottom: Math.max(height * 0.65, height - 80),
  };
}

export function fitArtCamera(box: Box3, authored: ArtCameraPose, viewport: ArtViewport): ArtCameraPose {
  const center = box.getCenter(new Vector3());
  const inverse = authored.quaternion.clone().invert();
  const { width, height } = viewport;
  const safe = artSafeArea(viewport);
  // Symmetric fitting leaves space for controls and label placement at either edge.
  const verticalSpace = Math.max(0.15, Math.min(1 - 2 * safe.top / height, 2 * safe.bottom / height - 1) - 0.16);
  const horizontalSpace = Math.max(0.15, (width - 2 * (safe.left + ART_LABEL_WIDTH / 2)) / width);
  const tanY = Math.tan(MathUtils.degToRad(authored.fov / 2));
  const tanX = tanY * width / height;
  let distance = 0.1;
  for (const corner of artBoxCorners(box)) {
    corner.sub(center).applyQuaternion(inverse);
    distance = Math.max(distance, corner.z + Math.abs(corner.x) / (tanX * horizontalSpace),
      corner.z + Math.abs(corner.y) / (tanY * verticalSpace));
  }
  const backward = new Vector3(0, 0, 1).applyQuaternion(authored.quaternion);
  return {
    position: center.addScaledVector(backward, distance * 1.04),
    quaternion: authored.quaternion.clone(),
    fov: authored.fov,
  };
}

export function artCameraPose(box: Box3, authored: ArtCameraPose, viewport: ArtViewport, system: boolean) {
  // The wide system composition belongs to Blender; narrow/core views fit the actual exported bounds.
  return system && viewport.width >= 900 && viewport.width / viewport.height >= 1.35
    ? { position: authored.position.clone(), quaternion: authored.quaternion.clone(), fov: authored.fov }
    : fitArtCamera(box, authored, viewport);
}

export function projectArtLabel(id: string, box: Box3, camera: PerspectiveCamera, viewport: ArtViewport): LabelAnchor {
  const center = box.getCenter(new Vector3()).project(camera);
  let bottom = -Infinity;
  for (const corner of artBoxCorners(box)) {
    const projected = corner.project(camera);
    bottom = Math.max(bottom, (-projected.y * 0.5 + 0.5) * viewport.height);
  }
  return {
    id,
    x: (center.x * 0.5 + 0.5) * viewport.width,
    y: bottom + 8 + ART_LABEL_HEIGHT / 2,
  };
}

export function placeArtLabels(anchors: readonly LabelAnchor[], viewport: ArtViewport): LabelAnchor[] {
  const safe = artSafeArea(viewport);
  const halfWidth = ART_LABEL_WIDTH / 2;
  const halfHeight = ART_LABEL_HEIGHT / 2;
  const minX = safe.left + halfWidth;
  const maxX = Math.max(minX, safe.right - halfWidth);
  const minY = safe.top + halfHeight;
  const maxY = Math.max(minY, safe.bottom - halfHeight);
  const placed: LabelAnchor[] = [];
  const overlaps = (a: LabelAnchor, b: LabelAnchor) =>
    Math.abs(a.x - b.x) < ART_LABEL_WIDTH + 8 && Math.abs(a.y - b.y) < ART_LABEL_HEIGHT + 8;

  for (const anchor of anchors) {
    const preferred = { ...anchor, x: MathUtils.clamp(anchor.x, minX, maxX), y: MathUtils.clamp(anchor.y, minY, maxY) };
    const candidates = [preferred];
    // Deterministic nearby positions keep coincident projections individually reachable.
    for (let row = -anchors.length; row <= anchors.length; row++) {
      for (let column = -2; column <= 2; column++) {
        candidates.push({
          id: anchor.id,
          x: MathUtils.clamp(preferred.x + column * (ART_LABEL_WIDTH + 8), minX, maxX),
          y: MathUtils.clamp(preferred.y + row * (ART_LABEL_HEIGHT + 8), minY, maxY),
        });
      }
    }
    // Include viewport-aligned positions when projections cluster at the same edge.
    for (let y = minY; y <= maxY; y += ART_LABEL_HEIGHT + 8) {
      for (let x = minX; x <= maxX; x += ART_LABEL_WIDTH + 8) candidates.push({ id: anchor.id, x, y });
    }
    candidates.sort((a, b) =>
      ((a.x - preferred.x) ** 2 + (a.y - preferred.y) ** 2) - ((b.x - preferred.x) ** 2 + (b.y - preferred.y) ** 2)
    );
    placed.push(candidates.find(candidate => placed.every(other => !overlaps(candidate, other))) ?? preferred);
  }
  return placed;
}
