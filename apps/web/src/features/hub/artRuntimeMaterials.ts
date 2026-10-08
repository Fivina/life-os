import { MeshStandardMaterial } from "three";

type ArtworkRim = { color: [number, number, number]; strength: number; direction?: [number, number, number]; floor?: number };

export function artworkRim(extras: Record<string, unknown>) {
  const color = extras.art_rim_color;
  const strength = extras.art_rim_strength;
  if (!Array.isArray(color) || color.length !== 3 ||
      !color.every(value => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1) ||
      typeof strength !== "number" || !Number.isFinite(strength) || strength < 0 || strength > 10) return null;
  const rim: ArtworkRim = { color: color as [number, number, number], strength };
  if (extras.art_rim_direction !== undefined || extras.art_rim_floor !== undefined) {
    const direction = extras.art_rim_direction;
    const floor = extras.art_rim_floor;
    if (!Array.isArray(direction) || direction.length !== 3 ||
        !direction.every(value => typeof value === "number" && Number.isFinite(value) && Math.abs(value) <= 1) ||
        direction.reduce((sum, value) => sum + value * value, 0) < 1e-12 ||
        typeof floor !== "number" || !Number.isFinite(floor) || floor < 0 || floor > 1) return null;
    rim.direction = direction as [number, number, number];
    rim.floor = floor;
  }
  return rim;
}

// View-dependent atmosphere cannot be baked into portable glTF textures.
export function restoreArtworkRim(material: MeshStandardMaterial) {
  const rim = artworkRim(material.userData);
  if (!rim) return;
  material.onBeforeCompile = shader => {
    shader.uniforms.artRimColor = { value: rim.color };
    shader.uniforms.artRimStrength = { value: rim.strength };
    let directionUniforms = "";
    let directionMask = "float artRimMask = 1.0;";
    if (rim.direction) {
      shader.uniforms.artRimDirection = { value: rim.direction };
      shader.uniforms.artRimFloor = { value: rim.floor };
      directionUniforms = "uniform vec3 artRimDirection; uniform float artRimFloor;";
      directionMask = `vec3 artDirectionView = normalize((viewMatrix * vec4(artRimDirection, 0.0)).xyz);
        float artRimMask = mix(artRimFloor, 1.0, pow(max(dot(normalize(normal), artDirectionView), 0.0), 0.75));`;
    }
    shader.fragmentShader = `uniform vec3 artRimColor; uniform float artRimStrength; ${directionUniforms}\n${shader.fragmentShader}`
      .replace("#include <emissivemap_fragment>", `#include <emissivemap_fragment>
        float artFacing = clamp(dot(normalize(normal), normalize(vViewPosition)), 0.0, 1.0);
        float artFresnel = 0.004867 + 0.995133 * pow(1.0 - artFacing, 5.0);
        ${directionMask}
        totalEmissiveRadiance += artRimColor * artRimStrength * pow(artFresnel, 1.8) * artRimMask;
      `);
  };
  material.customProgramCacheKey = () => rim.direction ? "lifeos-authored-rim-v2-directional" : "lifeos-authored-rim-v1";
  material.needsUpdate = true;
}
