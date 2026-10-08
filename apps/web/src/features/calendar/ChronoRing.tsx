import { useEffect, useMemo } from "react";
import * as THREE from "three";

export type ChronoRingConfig = {
  planetRadius: number;
  ringRadius: number;
  ringThickness: number;
  segmentCount: number;
  /** Angular space between neighboring ring segments, in radians. */
  segmentGap: number;
  ringEmission: number;
  nowMarkerSize: number;
  nowMarkerEmission: number;
};

export const DEFAULT_CHRONO_RING_CONFIG: Readonly<ChronoRingConfig> = {
  planetRadius: 1,
  ringRadius: 1.55,
  ringThickness: 0.14,
  segmentCount: 24,
  segmentGap: 0.025,
  ringEmission: 0.18,
  nowMarkerSize: 0.09,
  nowMarkerEmission: 1.15
};

export type ChronoRingProps = {
  config?: Partial<ChronoRingConfig>;
  variant?: "hero" | "miniature";
  scale?: number;
  /** Segment indexes that should carry an attention tint. The default is empty. */
  attentionSegments?: readonly number[];
  attentionNow?: boolean;
};

const RING_DEPTH = 0.042;
const NOW_ANGLE = 1.0;
const ATTENTION_RED = "#ff4d57";
const RING_PALETTE = ["#7654f4", "#4d36cf", "#7654f4", "#999cff", "#563bcf", "#704de8"];

function hashGridCell(x: number, y: number) {
  let value = Math.imul(x + 1, 374761393) + Math.imul(y + 1, 668265263);
  value = Math.imul(value ^ (value >>> 13), 1274126177);
  return ((value ^ (value >>> 16)) >>> 0) / 0xffffffff;
}

function periodicValueNoise(u: number, v: number, columns: number, rows: number) {
  const x = u * columns;
  const y = v * rows;
  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const tx = x - x0;
  const ty = y - y0;
  const smoothX = tx * tx * (3 - 2 * tx);
  const smoothY = ty * ty * (3 - 2 * ty);
  const wrapX = (cell: number) => ((cell % columns) + columns) % columns;
  const wrapY = (cell: number) => ((cell % rows) + rows) % rows;
  const top = THREE.MathUtils.lerp(
    hashGridCell(wrapX(x0), wrapY(y0)),
    hashGridCell(wrapX(x0 + 1), wrapY(y0)),
    smoothX
  );
  const bottom = THREE.MathUtils.lerp(
    hashGridCell(wrapX(x0), wrapY(y0 + 1)),
    hashGridCell(wrapX(x0 + 1), wrapY(y0 + 1)),
    smoothX
  );
  return THREE.MathUtils.lerp(top, bottom, smoothY) * 2 - 1;
}

function createPlanetSurfaceTextures() {
  const width = 512;
  const height = 256;
  const colorPixels = new Uint8Array(width * height * 4);
  const reliefPixels = new Uint8Array(width * height * 4);
  const roughnessPixels = new Uint8Array(width * height * 4);
  const byte = (value: number) => Math.max(0, Math.min(255, Math.round(value)));
  let seed = 90723;
  const random = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 0xffffffff;
  };
  const craterCount = 128;
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const craters = Array.from({ length: craterCount }, (_, index) => {
    const vertical = THREE.MathUtils.clamp(
      1 - (2 * (index + 0.5)) / craterCount + (random() - 0.5) * 0.12,
      -0.985,
      0.985
    );
    return {
      longitude: index * goldenAngle + (random() - 0.5) * 0.36,
      latitude: Math.asin(vertical),
      radius:
        index % 32 === 0
          ? 0.075 + random() * 0.05
          : 0.01 + Math.pow(random(), 1.7) * 0.04,
      aspect: 0.78 + random() * 0.5,
      rotation: random() * Math.PI,
      rimWarp: 0.04 + random() * 0.09,
      phase: random() * Math.PI * 2,
      strength: 0.55 + random() * 0.45
    };
  });

  for (let y = 0; y < height; y += 1) {
    const latitude = (y / (height - 1) - 0.5) * Math.PI;
    for (let x = 0; x < width; x += 1) {
      const longitude = (x / width) * Math.PI * 2;
      const warp =
        0.22 * Math.sin(longitude * 2.1 + latitude * 4.2) +
        0.08 * Math.sin(longitude * 4.4 - latitude * 3.3);
      const contour = Math.sin((latitude * 3.4 + warp) * Math.PI * 2);
      const fineRidge = Math.pow(Math.max(0, 1 - Math.abs(contour)), 10);
      const flow =
        0.58 * Math.sin(longitude * 1.6 + Math.sin(latitude * 4.7 + longitude * 1.3) * 0.9) +
        0.28 * Math.cos(longitude * 3.8 - latitude * 5.2) +
        0.14 * Math.sin(longitude * 8.1 + latitude * 6.7);
      const u = x / width;
      const v = y / height;
      const cloudNoise = periodicValueNoise(u, v, 12, 6);
      const mineralNoise = periodicValueNoise(u, v, 32, 16);
      const grainNoise = periodicValueNoise(u, v, 96, 48);
      const microNoise = periodicValueNoise(u, v, 192, 96);
      const mineralGrain =
        0.45 * Math.sin(longitude * 19 + latitude * 13) +
        0.24 * Math.cos(longitude * 29 - latitude * 21);
      const surface =
        flow * 0.3 +
        fineRidge * 0.16 +
        cloudNoise * 0.32 +
        mineralNoise * 0.4 +
        grainNoise * 0.22 +
        microNoise * 0.18 +
        mineralGrain * 0.12;
      let craterRelief = 0;
      for (const crater of craters) {
        const latitudeDelta = latitude - crater.latitude;
        if (Math.abs(latitudeDelta) > crater.radius * 1.8) continue;

        const longitudeDelta = Math.atan2(
          Math.sin(longitude - crater.longitude),
          Math.cos(longitude - crater.longitude)
        );
        const longitudeDistance = longitudeDelta * Math.cos((latitude + crater.latitude) / 2);
        const cosine = Math.cos(crater.rotation);
        const sine = Math.sin(crater.rotation);
        const localX =
          (longitudeDistance * cosine + latitudeDelta * sine) / crater.aspect;
        const localY =
          (-longitudeDistance * sine + latitudeDelta * cosine) * crater.aspect;
        const rimShape =
          1 +
          crater.rimWarp * Math.sin(Math.atan2(localY, localX) * 3 + crater.phase) +
          crater.rimWarp * 0.38 * Math.cos(Math.atan2(localY, localX) * 5 - crater.phase);
        const normalizedDistance = Math.hypot(localX, localY) / (crater.radius * rimShape);
        if (normalizedDistance > 1.8) continue;

        const bowl = Math.exp(-Math.pow((normalizedDistance - 0.18) / 0.6, 2));
        const rim = Math.exp(-Math.pow((normalizedDistance - 0.94) / 0.23, 2));
        craterRelief += crater.strength * (rim * 24 - bowl * 22);
      }
      const index = (y * width + x) * 4;
      const luminance = surface * 68 + fineRidge * 12 + craterRelief * 1.8;

      colorPixels[index] = byte(22 + luminance * 0.46);
      colorPixels[index + 1] = byte(28 + luminance * 0.82);
      colorPixels[index + 2] = byte(62 + luminance * 1.55);
      colorPixels[index + 3] = 255;

      const relief = byte(
        128 +
          flow * 30 +
          fineRidge * 28 +
          cloudNoise * 22 +
          mineralNoise * 38 +
          grainNoise * 34 +
          microNoise * 32 +
          craterRelief * 2.8
      );
      reliefPixels[index] = relief;
      reliefPixels[index + 1] = relief;
      reliefPixels[index + 2] = relief;
      reliefPixels[index + 3] = 255;

      const roughness = byte(
        178 + Math.abs(mineralNoise) * 30 + grainNoise * 12 + microNoise * 10 + fineRidge * 18
      );
      roughnessPixels[index] = roughness;
      roughnessPixels[index + 1] = roughness;
      roughnessPixels[index + 2] = roughness;
      roughnessPixels[index + 3] = 255;
    }
  }

  const makeTexture = (pixels: Uint8Array, colorSpace: THREE.ColorSpace) => {
    const texture = new THREE.DataTexture(pixels, width, height, THREE.RGBAFormat);
    texture.colorSpace = colorSpace;
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.ClampToEdgeWrapping;
    texture.magFilter = THREE.LinearFilter;
    texture.minFilter = THREE.LinearMipmapLinearFilter;
    texture.generateMipmaps = true;
    texture.needsUpdate = true;
    return texture;
  };

  return {
    color: makeTexture(colorPixels, THREE.SRGBColorSpace),
    relief: makeTexture(reliefPixels, THREE.NoColorSpace),
    roughness: makeTexture(roughnessPixels, THREE.NoColorSpace)
  };
}

function createPlanetContour(radius: number, latitudeBase: number, phase: number) {
  const points = Array.from({ length: 192 }, (_, index) => {
    const longitude = (index / 192) * Math.PI * 2;
    const latitude =
      latitudeBase +
      0.19 * Math.sin(longitude * 1.6 + phase) +
      0.078 * Math.sin(longitude * 3.7 - phase * 1.4) +
      0.032 * Math.cos(longitude * 6.4 + phase);
    const curvedLongitude = longitude + 0.11 * Math.sin(longitude * 2.7 + phase * 0.7);
    const surfaceRadius = radius + 0.009;
    return new THREE.Vector3(
      surfaceRadius * Math.cos(latitude) * Math.cos(curvedLongitude),
      surfaceRadius * Math.sin(latitude),
      surfaceRadius * Math.cos(latitude) * Math.sin(curvedLongitude)
    );
  });

  return new THREE.CatmullRomCurve3(points, true, "centripetal");
}

function createPlanetGeometry(radius: number) {
  return new THREE.SphereGeometry(radius, 160, 112);
}

function createNowGlowTexture() {
  const size = 96;
  const pixels = new Uint8Array(size * size * 4);
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const dx = (x / (size - 1)) * 2 - 1;
      const dy = (y / (size - 1)) * 2 - 1;
      const radius = Math.hypot(dx, dy);
      const falloff = Math.pow(Math.max(0, 1 - radius), 2.5);
      const index = (y * size + x) * 4;
      pixels[index] = 224;
      pixels[index + 1] = 235;
      pixels[index + 2] = 255;
      pixels[index + 3] = Math.round(falloff * 220);
    }
  }

  const texture = new THREE.DataTexture(pixels, size, size, THREE.RGBAFormat);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.ClampToEdgeWrapping;
  texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearFilter;
  texture.needsUpdate = true;
  return texture;
}

function NowMarkerNode({
  position,
  size,
  emission,
  attentionNow
}: {
  position: [number, number, number];
  size: number;
  emission: number;
  attentionNow: boolean;
}) {
  const glowTexture = useMemo(createNowGlowTexture, []);

  useEffect(() => () => glowTexture.dispose(), [glowTexture]);

  return (
    <group name="NowMarker" position={position}>
      <mesh name="NowMarkerCore" castShadow>
        <sphereGeometry args={[size, 28, 28]} />
        <meshPhysicalMaterial
          color="#dce8ff"
          emissive={attentionNow ? ATTENTION_RED : "#dce8ff"}
          emissiveIntensity={emission}
          metalness={0.04}
          roughness={0.28}
          clearcoat={0.5}
          clearcoatRoughness={0.22}
        />
      </mesh>
      <sprite name="NowMarkerHalo" scale={[size * 11, size * 11, 1]} renderOrder={2}>
        <spriteMaterial
          map={glowTexture}
          color={attentionNow ? ATTENTION_RED : "#b9cbff"}
          transparent
          opacity={0.4}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </sprite>
      <pointLight
        color={attentionNow ? ATTENTION_RED : "#dce7ff"}
        intensity={0.62}
        distance={0.82}
        decay={2}
      />
    </group>
  );
}

function PlanetCore({ radius }: { radius: number }) {
  const surface = useMemo(createPlanetSurfaceTextures, []);
  const geometry = useMemo(() => createPlanetGeometry(radius), [radius]);
  const contours = useMemo(
    () =>
      [-0.45, 0.02, 0.46].map((latitude, index) =>
        createPlanetContour(radius, latitude, 0.45 + index * 1.93)
      ),
    [radius]
  );
  useEffect(
    () => () => {
      surface.color.dispose();
      surface.relief.dispose();
      surface.roughness.dispose();
      geometry.dispose();
    },
    [geometry, surface]
  );

  return (
    <group name="PlanetCore">
      <mesh name="PlanetBody" geometry={geometry} castShadow receiveShadow>
        <meshPhysicalMaterial
          color="#ffffff"
          map={surface.color}
          bumpMap={surface.relief}
          roughnessMap={surface.roughness}
          bumpScale={0.42}
          emissive="#122557"
          emissiveIntensity={0.09}
          metalness={0.12}
          roughness={0.94}
          clearcoat={0.02}
          clearcoatRoughness={0.78}
        />
      </mesh>
      <group name="PlanetSurfaceDetail">
        {contours.map((curve, index) => (
            <mesh key={index} name={`PlanetContour_${String(index + 1).padStart(2, "0")}`}>
            <tubeGeometry args={[curve, 192, 0.002, 5, true]} />
            <meshBasicMaterial
              color={index % 2 === 0 ? "#455aa8" : "#5266b6"}
              transparent
              opacity={0.18}
              depthWrite={false}
            />
          </mesh>
        ))}
      </group>
    </group>
  );
}

function OrbitTrace({
  radius,
  startAngle,
  endAngle,
  phase,
  rotation,
  satelliteFractions
}: {
  radius: number;
  startAngle: number;
  endAngle: number;
  phase: number;
  rotation: [number, number, number];
  satelliteFractions: number[];
}) {
  const curve = useMemo(() => {
    const points = Array.from({ length: 128 }, (_, index) => {
      const progress = index / 127;
      const angle = startAngle + (endAngle - startAngle) * progress;
      const orbitRadius = radius + 0.035 * Math.sin(angle * 2 + phase);
      const latitude = 0.12 * Math.sin(angle * 1.7 + phase);
      return new THREE.Vector3(
        orbitRadius * Math.cos(latitude) * Math.cos(angle),
        orbitRadius * Math.sin(latitude),
        orbitRadius * Math.cos(latitude) * Math.sin(angle)
      );
    });
    return new THREE.CatmullRomCurve3(points, false, "centripetal");
  }, [endAngle, phase, radius, startAngle]);
  const satellites = useMemo(
    () => satelliteFractions.map((fraction) => curve.getPointAt(fraction)),
    [curve, satelliteFractions]
  );

  return (
    <group rotation={rotation}>
      <mesh name="OrbitTrace">
        <tubeGeometry args={[curve, 160, 0.0022, 5, false]} />
        <meshBasicMaterial color="#34477f" transparent opacity={0.42} depthWrite={false} />
      </mesh>
      {satellites.map((position, index) => (
        <mesh key={index} name={`OrbitMoon_${String(index + 1).padStart(2, "0")}`} position={position}>
          <sphereGeometry args={[index === 0 ? 0.052 : 0.034, 20, 20]} />
          <meshStandardMaterial
            color="#334d87"
            emissive="#1a2f72"
            emissiveIntensity={0.38}
            metalness={0.56}
            roughness={0.3}
          />
          <pointLight color="#526fd1" intensity={0.16} distance={0.42} decay={2} />
        </mesh>
      ))}
    </group>
  );
}

function OrbitAccents() {
  return (
    <group name="OrbitalAccents" rotation={[-0.08, 0.12, -0.12]}>
      <OrbitTrace
        radius={1.77}
        startAngle={-2.35}
        endAngle={2.48}
        phase={0.2}
        rotation={[0.1, 0.08, -0.24]}
        satelliteFractions={[0.2, 0.7]}
      />
      <OrbitTrace
        radius={1.91}
        startAngle={0.72}
        endAngle={5.02}
        phase={1.15}
        rotation={[0.3, -0.16, 0.17]}
        satelliteFractions={[0.47, 0.77]}
      />
    </group>
  );
}

function createRingSegmentGeometry(
  innerRadius: number,
  outerRadius: number,
  start: number,
  end: number
) {
  const shape = new THREE.Shape();
  shape.moveTo(outerRadius * Math.cos(start), outerRadius * Math.sin(start));
  shape.absarc(0, 0, outerRadius, start, end, false);
  shape.lineTo(innerRadius * Math.cos(end), innerRadius * Math.sin(end));
  shape.absarc(0, 0, innerRadius, end, start, true);
  shape.closePath();

  const geometry = new THREE.ExtrudeGeometry(shape, {
    bevelEnabled: true,
    bevelSegments: 2,
    bevelSize: 0.007,
    bevelThickness: 0.007,
    curveSegments: 8,
    depth: RING_DEPTH,
    steps: 1
  });
  geometry.translate(0, 0, -RING_DEPTH / 2);
  geometry.computeVertexNormals();
  return geometry;
}

function RingSegment({
  index,
  geometry,
  emission,
  attention
}: {
  index: number;
  geometry: THREE.ExtrudeGeometry;
  emission: number;
  attention: boolean;
}) {
  const baseColor = RING_PALETTE[index % RING_PALETTE.length];
  const color = attention ? ATTENTION_RED : baseColor;

  return (
    <mesh
      name={`RingSegment_${String(index + 1).padStart(2, "0")}`}
      geometry={geometry}
      castShadow={false}
      receiveShadow
    >
      <meshPhysicalMaterial
        color={color}
        emissive={color}
        emissiveIntensity={emission}
        metalness={0.4}
        roughness={0.32}
        clearcoat={0.16}
        clearcoatRoughness={0.38}
      />
    </mesh>
  );
}

/** Procedural Calendar domain object with separately addressable ring segments. */
export function ChronoRing({
  config,
  variant = "hero",
  scale = 1,
  attentionSegments = [],
  attentionNow = false
}: ChronoRingProps) {
  const resolved = { ...DEFAULT_CHRONO_RING_CONFIG, ...config };
  const segmentCount = Math.max(8, Math.floor(resolved.segmentCount));
  const step = (Math.PI * 2) / segmentCount;
  const gap = THREE.MathUtils.clamp(resolved.segmentGap, 0, step * 0.45);
  const innerRadius = Math.max(
    resolved.planetRadius + 0.08,
    resolved.ringRadius - resolved.ringThickness / 2
  );
  const outerRadius = Math.max(innerRadius + 0.06, resolved.ringRadius + resolved.ringThickness / 2);
  const variantScale = variant === "miniature" ? 0.82 : 1;
  const emphasized = useMemo(() => new Set(attentionSegments), [attentionSegments]);
  const nowMarkerRadius = Math.max(
    resolved.planetRadius + resolved.nowMarkerSize,
    resolved.ringRadius - resolved.nowMarkerSize * 1.4
  );

  const geometries = useMemo(
    () =>
      Array.from({ length: segmentCount }, (_, index) => {
        const center = index * step;
        return createRingSegmentGeometry(
          innerRadius,
          outerRadius,
          center + gap / 2,
          center + step - gap / 2
        );
      }),
    [gap, innerRadius, outerRadius, segmentCount, step]
  );

  return (
    <group name="CalendarRoot" scale={scale * variantScale}>
      <PlanetCore radius={resolved.planetRadius} />
      {variant === "hero" && <OrbitAccents />}

      <group name="ChronoRing" rotation={[1.605, 0.283, -0.673]}>
        {geometries.map((geometry, index) => (
          <RingSegment
            key={index}
            index={index}
            geometry={geometry}
            emission={resolved.ringEmission}
            attention={emphasized.has(index)}
          />
        ))}

        <NowMarkerNode
          position={[
            nowMarkerRadius * Math.cos(NOW_ANGLE),
            nowMarkerRadius * Math.sin(NOW_ANGLE),
            -RING_DEPTH / 2 - resolved.nowMarkerSize * 0.8
          ]}
          size={resolved.nowMarkerSize}
          emission={resolved.nowMarkerEmission}
          attentionNow={attentionNow}
        />
      </group>
    </group>
  );
}
