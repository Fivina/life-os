import { useLayoutEffect, useMemo, useRef } from "react";
import { useLoader } from "@react-three/fiber";
import { AdditiveBlending, Color, ShaderMaterial, TextureLoader, Vector3, type Texture } from "three";

export type CoreEarthSurfacePalette = {
  deepOcean: string;
  ocean: string;
  shadedLand: string;
  livingLand: string;
  atmosphere: string;
  clouds: string;
  lifeLights: string;
};

export const CORE_EARTH_PALETTE: CoreEarthSurfacePalette = {
  deepOcean: "#0b2a4d",
  ocean: "#1d6fa5",
  shadedLand: "#28583f",
  livingLand: "#4faf6c",
  atmosphere: "#71d5ff",
  clouds: "#eaf3ff",
  lifeLights: "#e6b45a"
};

export type CoreEarthProps = {
  radius?: number;
  surfacePalette?: Partial<CoreEarthSurfacePalette>;
  atmosphereIntensity?: number;
  cloudOpacity?: number;
  lifeLightDensity?: number;
  roughness?: number;
  emission?: number;
  attentionSignal?: boolean;
  presentation?: "hero" | "miniature";
  view?: CoreEarthView;
};

export type CoreEarthView = "front" | "three-quarter" | "side";

const VIEW_ROTATIONS: Record<CoreEarthView, [number, number, number]> = {
  front: [0.12, 0.02, -0.04],
  "three-quarter": [0.2, -0.54, -0.08],
  side: [0.16, -1.2, -0.08]
};

const SURFACE_VERTEX_SHADER = /* glsl */ `
  varying vec3 vObjectPosition;
  varying vec3 vNormal;
  varying vec3 vViewPosition;

  void main() {
    vObjectPosition = normalize(position);
    vNormal = normalize(normalMatrix * normal);
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    vViewPosition = -mvPosition.xyz;
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const PROCEDURAL_NOISE = /* glsl */ `
  float hash(vec3 p) {
    return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453123);
  }

  vec3 gradient(vec3 cell) {
    float index = floor(hash(cell) * 12.0);
    float firstSign = mod(index, 2.0) * 2.0 - 1.0;
    float secondSign = mod(floor(index / 2.0), 2.0) * 2.0 - 1.0;
    if (index < 4.0) return vec3(firstSign, secondSign, 0.0) * 0.70710678;
    if (index < 8.0) return vec3(firstSign, 0.0, secondSign) * 0.70710678;
    return vec3(0.0, firstSign, secondSign) * 0.70710678;
  }

  float noise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    vec3 u = f * f * (3.0 - 2.0 * f);
    float n000 = dot(gradient(i), f);
    float n100 = dot(gradient(i + vec3(1.0, 0.0, 0.0)), f - vec3(1.0, 0.0, 0.0));
    float n010 = dot(gradient(i + vec3(0.0, 1.0, 0.0)), f - vec3(0.0, 1.0, 0.0));
    float n110 = dot(gradient(i + vec3(1.0, 1.0, 0.0)), f - vec3(1.0, 1.0, 0.0));
    float n001 = dot(gradient(i + vec3(0.0, 0.0, 1.0)), f - vec3(0.0, 0.0, 1.0));
    float n101 = dot(gradient(i + vec3(1.0, 0.0, 1.0)), f - vec3(1.0, 0.0, 1.0));
    float n011 = dot(gradient(i + vec3(0.0, 1.0, 1.0)), f - vec3(0.0, 1.0, 1.0));
    float n111 = dot(gradient(i + vec3(1.0, 1.0, 1.0)), f - vec3(1.0, 1.0, 1.0));
    float z0 = mix(mix(n000, n100, u.x), mix(n010, n110, u.x), u.y);
    float z1 = mix(mix(n001, n101, u.x), mix(n011, n111, u.x), u.y);
    return clamp(0.5 + mix(z0, z1, u.z) * 0.72, 0.0, 1.0);
  }

  float fbm(vec3 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int octave = 0; octave < 5; octave++) {
      value += noise(p) * amplitude;
      p *= 2.03;
      amplitude *= 0.5;
    }
    return value;
  }

  float fbmSoft(vec3 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int octave = 0; octave < 4; octave++) {
      value += noise(p) * amplitude;
      p *= 2.0;
      amplitude *= 0.5;
    }
    return value;
  }

  float fbmMacro(vec3 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int octave = 0; octave < 2; octave++) {
      value += noise(p) * amplitude;
      p *= 2.0;
      amplitude *= 0.5;
    }
    return value / 0.75;
  }
`;

const SURFACE_FRAGMENT_SHADER = /* glsl */ `
  uniform vec3 uDeepOcean;
  uniform vec3 uOcean;
  uniform vec3 uShadedLand;
  uniform vec3 uLivingLand;
  uniform sampler2D uLandMask;
  uniform vec3 uLightDirection;
  uniform float uRoughness;
  uniform float uEmission;

  varying vec3 vObjectPosition;
  varying vec3 vNormal;
  varying vec3 vViewPosition;

  ${PROCEDURAL_NOISE}

  void main() {
    vec3 p = normalize(vObjectPosition);
    float longitude = atan(p.z, -p.x);
    float mapU = longitude / 6.28318530718;
    if (mapU < 0.0) mapU += 1.0;
    float mapV = asin(clamp(p.y, -1.0, 1.0)) / 3.14159265359 + 0.5;
    float landMask = smoothstep(0.32, 0.68, texture2D(uLandMask, vec2(mapU, mapV)).a);

    float seaDepth = fbmSoft(p * 2.8 + vec3(-3.0, 5.0, 1.0));
    float terrain = fbmSoft(p * 9.2 + vec3(1.7, 9.2, -4.0));
    float regionalTerrain = fbmSoft(p * 19.0 + vec3(-7.0, 5.0, 3.0));
    float mountainRidges = pow(1.0 - abs(noise(p * 25.0 + vec3(3.1, -7.4, 5.6)) * 2.0 - 1.0), 2.4);
    float microTexture = fbm(p * 34.0 + vec3(3.1, -7.4, 5.6));
    vec3 ocean = mix(uDeepOcean, uOcean, 0.24 + seaDepth * 0.52);
    float biome = smoothstep(0.31, 0.69, terrain * 0.76 + regionalTerrain * 0.24);
    vec3 land = mix(uShadedLand, uLivingLand, biome);
    float highlands = smoothstep(0.54, 0.74, terrain * 0.74 + regionalTerrain * 0.26 + mountainRidges * 0.12);
    vec3 uplandColor = mix(uLivingLand, vec3(0.54, 0.61, 0.49), 0.38);
    land = mix(land, uplandColor, highlands * 0.46);
    float highPeaks = smoothstep(0.78, 0.96, terrain + mountainRidges * 0.22);
    land = mix(land, vec3(0.67, 0.73, 0.66), highPeaks * 0.2);

    vec3 normal = normalize(vNormal);
    vec3 lightDirection = normalize(uLightDirection);
    vec3 viewDirection = normalize(vViewPosition);
    float daylight = max(dot(normal, lightDirection), 0.0);
    float wrapLight = clamp((dot(normal, lightDirection) + 0.22) / 1.22, 0.0, 1.0);
    float specularPower = mix(92.0, 13.0, clamp(uRoughness, 0.0, 1.0));
    float specular = pow(max(dot(reflect(-lightDirection, normal), viewDirection), 0.0), specularPower);
    float elevation = fbmSoft(p * 9.0 + vec3(4.0, -6.0, 2.0))
      + fbmSoft(p * 23.0 + vec3(-2.0, 12.0, 8.0)) * 0.18
      + mountainRidges * 0.08;
    vec2 reliefSlope = vec2(dFdx(elevation), dFdy(elevation));
    float reliefLight = clamp(1.0 + dot(reliefSlope, lightDirection.xy) * 12.0, 0.72, 1.28);
    land *= reliefLight;

    vec3 surface = mix(ocean, land, landMask);
    surface *= (0.08 + wrapLight * 1.08) * (0.91 + microTexture * 0.18);
    surface += uOcean * specular * (1.0 - uRoughness) * 0.42;
    surface += mix(uOcean, uLivingLand, landMask) * uEmission * 0.12;
    surface += mix(vec3(0.0), vec3(0.025, 0.055, 0.075), 1.0 - daylight) * 0.13;

    gl_FragColor = vec4(surface, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

const SHELL_VERTEX_SHADER = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vViewPosition;

  void main() {
    vNormal = normalize(normalMatrix * normal);
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    vViewPosition = -mvPosition.xyz;
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const ATMOSPHERE_FRAGMENT_SHADER = /* glsl */ `
  uniform vec3 uColor;
  uniform float uIntensity;
  varying vec3 vNormal;
  varying vec3 vViewPosition;

  void main() {
    float facing = max(dot(normalize(vNormal), normalize(vViewPosition)), 0.0);
    float rim = pow(1.0 - facing, 2.4);
    float haze = pow(1.0 - facing, 1.15);
    float alpha = clamp((rim * 0.7 + haze * 0.1) * uIntensity, 0.0, 0.72);
    vec3 color = uColor * (rim * 1.45 + haze * 0.16) * uIntensity;
    gl_FragColor = vec4(color, alpha);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

const CLOUD_FRAGMENT_SHADER = /* glsl */ `
  uniform vec3 uCloudColor;
  uniform vec3 uAtmosphereColor;
  uniform float uOpacity;
  varying vec3 vObjectPosition;
  varying vec3 vNormal;
  varying vec3 vViewPosition;

  ${PROCEDURAL_NOISE}

  void main() {
    vec3 p = normalize(vObjectPosition);
    vec3 cloudWarp = vec3(
      fbmMacro(p * 2.1 + vec3(4.0, 2.0, -6.0)),
      fbmMacro(p * 2.1 + vec3(-3.0, 7.0, 5.0)),
      fbmMacro(p * 2.1 + vec3(8.0, -4.0, 3.0))
    ) - 0.5;
    float cloudMass = fbmSoft(p * 3.8 + cloudWarp * 1.25 + vec3(-4.8, 2.1, 7.3));
    float cloudBanks = fbmSoft(p * 7.8 + cloudWarp * 0.48 + vec3(3.0, -5.0, 2.0));
    float wisps = fbm(p * 18.0 + vec3(3.0, 1.0, -5.0));
    float field = cloudMass * 0.76 + cloudBanks * 0.24 + (wisps - 0.5) * 0.07;
    float coverage = smoothstep(0.50, 0.585, field);
    float sunlit = max(dot(normalize(vNormal), normalize(vec3(0.42, 0.65, 0.38))), 0.0);
    float cloudShade = 0.82 + sunlit * 0.42;
    float alpha = coverage * uOpacity * (0.19 + sunlit * 0.86);
    vec3 color = mix(uCloudColor, uAtmosphereColor, 0.025) * cloudShade;
    gl_FragColor = vec4(color, alpha);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

function createLandMaskSampler(texture: Texture) {
  const image = texture.image as CanvasImageSource & { width?: number; height?: number; naturalWidth?: number; naturalHeight?: number };
  const width = image.naturalWidth || image.width || 0;
  const height = image.naturalHeight || image.height || 0;
  if (!width || !height || typeof document === "undefined") return () => false;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return () => false;
  context.drawImage(image, 0, 0, width, height);
  const alpha = context.getImageData(0, 0, width, height).data;
  return (x: number, y: number, z: number) => {
    let u = Math.atan2(z, -x) / (Math.PI * 2);
    if (u < 0) u += 1;
    const v = Math.asin(Math.max(-1, Math.min(1, y))) / Math.PI + 0.5;
    const px = Math.min(width - 1, Math.floor(u * width));
    const py = Math.min(height - 1, Math.floor((1 - v) * height));
    return alpha[(py * width + px) * 4 + 3] > 128;
  };
}

function makeLifeLightPositions(radius: number, density: number, miniature: boolean, isLand: (x: number, y: number, z: number) => boolean) {
  const lightCount = Math.round(Math.max(0, Math.min(1, density)) * (miniature ? 20 : 72));
  const positions: number[] = [];
  let seed = 982451653;
  const random = () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };

  for (let attempt = 0; attempt < 1800 && positions.length / 3 < lightCount; attempt += 1) {
    const y = random() * 2 - 1;
    const angle = random() * Math.PI * 2;
    const ring = Math.sqrt(1 - y * y);
    const x = ring * Math.cos(angle);
    const z = ring * Math.sin(angle);
    if (!isLand(x, y, z)) continue;
    positions.push(x * radius * 1.026, y * radius * 1.026, z * radius * 1.026);
  }

  return new Float32Array(positions);
}

function SurfaceMaterial({
  palette,
  roughness,
  emission,
  landMask
}: {
  palette: CoreEarthSurfacePalette;
  roughness: number;
  emission: number;
  landMask: Texture;
}) {
  const material = useRef<ShaderMaterial>(null);
  const uniforms = useMemo(() => ({
    uDeepOcean: { value: new Color(palette.deepOcean) },
    uOcean: { value: new Color(palette.ocean) },
    uShadedLand: { value: new Color(palette.shadedLand) },
    uLivingLand: { value: new Color(palette.livingLand) },
    uLandMask: { value: landMask },
    uLightDirection: { value: new Vector3(0.42, 0.65, 0.38).normalize() },
    uRoughness: { value: roughness },
    uEmission: { value: emission }
  }), [landMask]);

  useLayoutEffect(() => {
    const values = material.current?.uniforms;
    if (!values) return;
    values.uDeepOcean.value.set(palette.deepOcean);
    values.uOcean.value.set(palette.ocean);
    values.uShadedLand.value.set(palette.shadedLand);
    values.uLivingLand.value.set(palette.livingLand);
    values.uRoughness.value = Math.max(0, Math.min(1, roughness));
    values.uEmission.value = Math.max(0, emission);
  }, [palette, roughness, emission]);

  return (
    <shaderMaterial
      ref={material}
      name="LivingRegionMaterial"
      uniforms={uniforms}
      vertexShader={SURFACE_VERTEX_SHADER}
      fragmentShader={SURFACE_FRAGMENT_SHADER}
    />
  );
}

function Atmosphere({ radius, intensity, color, segments }: { radius: number; intensity: number; color: string; segments: number }) {
  const material = useRef<ShaderMaterial>(null);
  const uniforms = useMemo(() => ({
    uColor: { value: new Color(color) },
    uIntensity: { value: intensity }
  }), []);

  useLayoutEffect(() => {
    const values = material.current?.uniforms;
    if (!values) return;
    values.uColor.value.set(color);
    values.uIntensity.value = Math.max(0, intensity);
  }, [color, intensity]);

  return (
    <mesh name="Atmosphere" scale={1.075} renderOrder={4}>
      <sphereGeometry args={[radius, segments, segments]} />
      <shaderMaterial
        ref={material}
        uniforms={uniforms}
        vertexShader={SHELL_VERTEX_SHADER}
        fragmentShader={ATMOSPHERE_FRAGMENT_SHADER}
        transparent
        depthWrite={false}
        blending={AdditiveBlending}
        toneMapped={false}
      />
    </mesh>
  );
}

function CloudLayer({ radius, opacity, palette, segments }: {
  radius: number;
  opacity: number;
  palette: CoreEarthSurfacePalette;
  segments: number;
}) {
  const material = useRef<ShaderMaterial>(null);
  const uniforms = useMemo(() => ({
    uCloudColor: { value: new Color(palette.clouds) },
    uAtmosphereColor: { value: new Color(palette.atmosphere) },
    uOpacity: { value: opacity }
  }), []);

  useLayoutEffect(() => {
    const values = material.current?.uniforms;
    if (!values) return;
    values.uCloudColor.value.set(palette.clouds);
    values.uAtmosphereColor.value.set(palette.atmosphere);
    values.uOpacity.value = Math.max(0, Math.min(1, opacity));
  }, [palette, opacity]);

  return (
    <group name="CloudLayer">
      <mesh scale={1.018} renderOrder={2}>
        <sphereGeometry args={[radius, segments, segments]} />
        <shaderMaterial
          ref={material}
          uniforms={uniforms}
          vertexShader={SURFACE_VERTEX_SHADER}
          fragmentShader={CLOUD_FRAGMENT_SHADER}
          transparent
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}

function OrbitElements({ radius, attentionSignal, miniature }: {
  radius: number;
  attentionSignal: boolean;
  miniature: boolean;
}) {
  return (
    <group name="OrbitElements">
      <mesh rotation={[0.46, 0.1, -0.18]} renderOrder={5}>
        <torusGeometry args={[radius * 1.48, radius * (miniature ? 0.0032 : 0.0038), 4, 192]} />
        <meshBasicMaterial color="#8ce4ff" transparent opacity={miniature ? 0.32 : 0.5} depthWrite={false} toneMapped={false} />
      </mesh>
      {!miniature ? (
        <mesh rotation={[-0.34, 0.18, 0.54]} renderOrder={5}>
          <torusGeometry args={[radius * 1.65, radius * 0.0024, 4, 192]} />
          <meshBasicMaterial color="#55bce8" transparent opacity={0.27} depthWrite={false} toneMapped={false} />
        </mesh>
      ) : null}
      {attentionSignal ? (
        <mesh name="AttentionSignal" position={[radius * 1.48 * 0.76, radius * 1.48 * 0.5, radius * 1.48 * 0.41]} renderOrder={6}>
          <sphereGeometry args={[radius * 0.026, 14, 10]} />
          <meshBasicMaterial color="#ff4d57" toneMapped={false} />
        </mesh>
      ) : null}
    </group>
  );
}

export function CoreEarth({
  radius = 1,
  surfacePalette,
  atmosphereIntensity = 1.06,
  cloudOpacity = 0.9,
  lifeLightDensity = 0.46,
  roughness = 0.62,
  emission = 0.18,
  attentionSignal = false,
  presentation = "hero",
  view = "three-quarter"
}: CoreEarthProps) {
  const miniature = presentation === "miniature";
  const segments = miniature ? 44 : 88;
  const landMaskTexture = useLoader(TextureLoader, "/assets/core-earth-land.svg");
  const isLand = useMemo(() => createLandMaskSampler(landMaskTexture), [landMaskTexture]);
  const palette = useMemo(() => ({ ...CORE_EARTH_PALETTE, ...surfacePalette }), [
    surfacePalette?.deepOcean,
    surfacePalette?.ocean,
    surfacePalette?.shadedLand,
    surfacePalette?.livingLand,
    surfacePalette?.atmosphere,
    surfacePalette?.clouds,
    surfacePalette?.lifeLights
  ]);
  const lifeLightPositions = useMemo(
    () => makeLifeLightPositions(radius, lifeLightDensity, miniature, isLand),
    [radius, lifeLightDensity, miniature, isLand]
  );

  return (
    <group name="LifeRoot" rotation={VIEW_ROTATIONS[view]}>
      <mesh name="PlanetSurface" renderOrder={1}>
        <sphereGeometry args={[radius, segments, segments]} />
        <SurfaceMaterial palette={palette} roughness={roughness} emission={emission} landMask={landMaskTexture} />
      </mesh>
      <CloudLayer radius={radius} opacity={cloudOpacity} palette={palette} segments={segments} />
      <points name="LifeLights" renderOrder={3}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[lifeLightPositions, 3]} />
        </bufferGeometry>
        <pointsMaterial
          color={palette.lifeLights}
          size={radius * (miniature ? 0.056 : 0.046)}
          sizeAttenuation
          transparent
          opacity={0.9}
          depthWrite={false}
          blending={AdditiveBlending}
          toneMapped={false}
        />
      </points>
      <Atmosphere radius={radius} intensity={atmosphereIntensity} color={palette.atmosphere} segments={segments} />
      <OrbitElements radius={radius} attentionSignal={attentionSignal} miniature={miniature} />
    </group>
  );
}
