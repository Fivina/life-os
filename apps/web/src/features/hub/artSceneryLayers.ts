import { Object3D, Vector3 } from "three";

export type ArtSceneryLayer = {
  root: Object3D;
  authored: { position: Vector3; scale: Vector3 };
};

export function artworkSceneryLayers(scenery: Object3D | undefined): ArtSceneryLayer[] {
  // Only direct tagged layers can change pose; legacy assets stay a single root.
  return (scenery?.children ?? []).filter(child => child.userData.art_scenery_layer === true)
    .map(root => ({ root, authored: { position: root.position.clone(), scale: root.scale.clone() } }));
}
