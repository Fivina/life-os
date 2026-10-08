import { describe, expect, it } from "vitest";
import { MeshPhysicalMaterial, MeshStandardMaterial } from "three";
import { artworkRim, restoreArtworkRim } from "./artRuntimeMaterials";

describe("authored atmosphere contract", () => {
  it("accepts bounded authored color and strength", () => {
    expect(artworkRim({ art_rim_color: [0.1, 0.3, 0.8], art_rim_strength: 3 }))
      .toEqual({ color: [0.1, 0.3, 0.8], strength: 3 });
  });
  it.each([{}, { art_rim_color: [1, 2, 3], art_rim_strength: 3 },
    { art_rim_color: [0, 0, 1], art_rim_strength: Infinity },
    { art_rim_color: [0, 0], art_rim_strength: 3 }])("rejects malformed extras %j", extras => {
    expect(artworkRim(extras)).toBeNull();
  });
  it("preserves exported physical material properties", () => {
    const material = new MeshStandardMaterial({ roughness: 0.4, metalness: 0.7 });
    material.userData = { art_rim_color: [0.1, 0.3, 0.8], art_rim_strength: 3 };
    restoreArtworkRim(material);
    expect(material.roughness).toBe(0.4);
    expect(material.metalness).toBe(0.7);
    expect(material.customProgramCacheKey()).toBe("lifeos-authored-rim-v1");
  });

  it("accepts source-facing direction and a bounded dim-side floor", () => {
    expect(artworkRim({ art_rim_color: [0.32, 0.13, 0.8], art_rim_strength: 2.5,
      art_rim_direction: [0, -0.15, 0.99], art_rim_floor: 0.08 }))
      .toEqual({ color: [0.32, 0.13, 0.8], strength: 2.5, direction: [0, -0.15, 0.99], floor: 0.08 });
  });

  it.each([
    { art_rim_direction: [0, 0, 0], art_rim_floor: 0.08 },
    { art_rim_direction: [0, NaN, 1], art_rim_floor: 0.08 },
    { art_rim_direction: [0, 1], art_rim_floor: 0.08 },
    { art_rim_direction: [0, 0, 2], art_rim_floor: 0.08 },
    { art_rim_direction: [0, 0, 1], art_rim_floor: -0.1 },
    { art_rim_direction: [0, 0, 1], art_rim_floor: Infinity },
    { art_rim_direction: [0, 0, 1] }, { art_rim_floor: 0.08 },
  ])("rejects malformed directional contracts %j", extras => {
    expect(artworkRim({ art_rim_color: [0.32, 0.13, 0.8], art_rim_strength: 2.5, ...extras })).toBeNull();
  });

  it("adds a directional limb without replacing glass channels or the existing shader body", () => {
    const material = new MeshPhysicalMaterial({ roughness: 0.24, transmission: 0.86, ior: 1.04 });
    material.userData = { art_rim_color: [0.32, 0.13, 0.8], art_rim_strength: 2.5,
      art_rim_direction: [0, -0.15, 0.99], art_rim_floor: 0.08 };
    restoreArtworkRim(material);
    const shader = { uniforms: {}, fragmentShader: "#include <emissivemap_fragment>\nKEEP_EXISTING_PHYSICAL_SHADER" };
    material.onBeforeCompile(shader as Parameters<typeof material.onBeforeCompile>[0],
      {} as Parameters<typeof material.onBeforeCompile>[1]);
    expect(shader.uniforms).toMatchObject({ artRimDirection: { value: [0, -0.15, 0.99] }, artRimFloor: { value: 0.08 } });
    expect(shader.fragmentShader).toContain("viewMatrix * vec4(artRimDirection, 0.0)");
    expect(shader.fragmentShader).toContain("KEEP_EXISTING_PHYSICAL_SHADER");
    expect(material.transmission).toBe(0.86);
    expect(material.ior).toBe(1.04);
    expect(material.roughness).toBe(0.24);
    expect(material.customProgramCacheKey()).toBe("lifeos-authored-rim-v2-directional");
    material.dispose();
  });
});
