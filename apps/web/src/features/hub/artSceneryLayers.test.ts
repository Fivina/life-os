import { Group, Vector3 } from "three";
import { describe, expect, it } from "vitest";
import { artworkSceneryLayers } from "./artSceneryLayers";
import { placeArtObject } from "./systemArtMotion";

describe("independently staged artwork scenery", () => {
  it("keeps missing and legacy scenery unchanged", () => {
    const legacy = new Group();
    legacy.add(new Group());
    expect(artworkSceneryLayers(undefined)).toEqual([]);
    expect(artworkSceneryLayers(legacy)).toEqual([]);
  });

  it("selects only directly tagged layers and does not infer tags", () => {
    const scenery = new Group();
    const tagged = new Group(); tagged.userData.art_scenery_layer = true;
    const nested = new Group(); nested.userData.art_scenery_layer = true;
    const untagged = new Group(); untagged.add(nested);
    const malformed = new Group(); malformed.userData.art_scenery_layer = "true";
    scenery.add(tagged, untagged, malformed);
    expect(artworkSceneryLayers(scenery).map(layer => layer.root)).toEqual([tagged]);
  });

  it("captures independent baselines and restores them after repeat portrait placement", () => {
    const scenery = new Group();
    const near = new Group(); near.userData = {
      art_scenery_layer: true, art_portrait_position: [0.5, -0.45, 2.0], art_portrait_scale: 0.4,
    };
    const belt = new Group(); belt.userData = {
      art_scenery_layer: true, art_portrait_position: [0.7, -1.3, -0.6], art_portrait_scale: 0.48,
    };
    near.position.set(1, 2, 3); belt.scale.set(1, 2, 1);
    scenery.add(near, belt);
    const layers = artworkSceneryLayers(scenery);
    for (let repeat = 0; repeat < 2; repeat++) {
      layers.forEach(layer => placeArtObject(layer.root, layer.authored, true));
    }
    expect(near.position).toEqual(new Vector3(0.5, -0.45, 2.0));
    expect(belt.position).toEqual(new Vector3(0.7, -1.3, -0.6));
    expect(near.scale).toEqual(new Vector3(0.4, 0.4, 0.4));
    expect(belt.scale).toEqual(new Vector3(0.48, 0.96, 0.48));
    layers.forEach(layer => placeArtObject(layer.root, layer.authored, false));
    expect(near.position).toEqual(new Vector3(1, 2, 3));
    expect(belt.scale).toEqual(new Vector3(1, 2, 1));
    expect(layers[0].authored.position).not.toBe(near.position);
  });
});
