import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { GRAVITY_SETTINGS_NEAR_STREAM_PATHS } from "../hub/gravity-settings-flow-paths";

export type SettingsGravityWellProps = {
  voidRadius?: number;
  lensingRadius?: number;
  lensingIntensity?: number;
  distortionStrength?: number;
  flowDensity?: number;
  flowRadius?: number;
  haloIntensity?: number;
  showInnerTunnel?: boolean;
  quality?: "hero" | "navigation";
  reducedMotion?: boolean;
};

const QUALITY = {
  hero: { stars: 220, brightStars: 42, filaments: 2, distortions: 8, tubeSegments: 88, tubeSides: 4, diskRings: 36, diskSegments: 288, voidSegments: [128, 96], tunnelSegments: 64, tunnelRingSegments: 72 },
  navigation: { stars: 70, brightStars: 14, filaments: 1, distortions: 4, tubeSegments: 40, tubeSides: 3, diskRings: 12, diskSegments: 96, voidSegments: [40, 30], tunnelSegments: 32, tunnelRingSegments: 40 }
} as const;

type Quality = NonNullable<SettingsGravityWellProps["quality"]>;
type MotionTime = { value: number };

const lensVertexShader = /* glsl */ `
  varying vec2 vPosition;

  void main() {
    vPosition = position.xy;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const lensFragmentShader = /* glsl */ `
  uniform float uVoidRadius;
  uniform float uLensingRadius;
  uniform float uLensingIntensity;
  uniform float uHaloIntensity;
  uniform float uDistortionStrength;
  uniform float uTime;
  varying vec2 vPosition;

  void main() {
    float radius = length(vPosition);
    if (radius < uVoidRadius * 1.015) discard;
    float angle = atan(vPosition.y, vPosition.x);
    float flowAngle = angle - uTime * 0.004;
    float lensRadius = max(uLensingRadius, uVoidRadius + 0.025);
    float rimWidth = max(0.016, uVoidRadius * 0.03);
    float rimDistance = radius - lensRadius;

    float narrowRim = exp(-pow(rimDistance / rimWidth, 2.0));
    float softRim = exp(-pow(rimDistance / (rimWidth * 2.7), 2.0));
    float halo = exp(-pow(rimDistance / (uVoidRadius * 0.34), 2.0));

    float upperLobe = pow(max(0.0, sin(flowAngle - 0.32)), 5.0);
    float lowerLobe = pow(max(0.0, -sin(flowAngle - 0.42)), 5.0);
    // Periodic angular distance keeps each crescent continuous across the seam.
    float hotCrescent = 0.9 * exp(-pow(atan(sin(flowAngle - 2.45), cos(flowAngle - 2.45)) / 0.58, 2.0))
      + 0.52 * exp(-pow(atan(sin(flowAngle - 4.82), cos(flowAngle - 4.82)) / 0.68, 2.0));
    float asymmetry = 0.08 + 0.43 * upperLobe + 0.14 * lowerLobe + hotCrescent;
    float warped = 1.0 + uDistortionStrength * 0.13 * sin(flowAngle * 3.0 + radius * 8.0);

    vec3 blueWhite = vec3(0.48, 0.78, 0.96);
    vec3 ice = vec3(0.86, 0.96, 1.0);
    vec3 rimColor = mix(blueWhite, ice, clamp(upperLobe * 0.35 + hotCrescent * 0.74, 0.0, 0.92));
    vec3 color = rimColor * (narrowRim * 1.76 + softRim * 0.45);
    color += vec3(0.14, 0.39, 0.59) * halo * uHaloIntensity * 0.36;

    float alpha = (narrowRim * 1.12 + softRim * 0.2 + halo * uHaloIntensity * 0.18)
      * asymmetry * warped * uLensingIntensity;
    gl_FragColor = vec4(color, clamp(alpha, 0.0, 0.94));
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

const flowVertexShader = /* glsl */ `
  varying vec2 vFlowUv;
  void main() {
    vFlowUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const flowFragmentShader = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  uniform float uTime;
  varying vec2 vFlowUv;
  void main() {
    float current = pow(0.5 + 0.5 * cos(vFlowUv.x * 25.132741 - uTime * 0.16), 6.0);
    float crossSection = 0.7 + 0.3 * sin(vFlowUv.y * 3.141593);
    gl_FragColor = vec4(uColor * (0.92 + current * 0.3), uOpacity * crossSection * (0.82 + current * 0.18));
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

function seededRandom(seed: number) {
  let value = seed >>> 0;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 4294967296;
  };
}

function makeStarPositions(count: number, voidRadius: number, seed = 37041) {
  const random = seededRandom(seed);
  const positions = new Float32Array(count * 3);
  let written = 0;

  while (written < count) {
    const angle = random() * Math.PI * 2;
    const radius = 1.2 + random() * 3.3;
    if (radius < voidRadius * 1.55) continue;

    positions[written * 3] = Math.cos(angle) * radius;
    positions[written * 3 + 1] = Math.sin(angle) * radius * 0.78;
    positions[written * 3 + 2] = (random() - 0.5) * 1.2;
    written += 1;
  }

  return positions;
}

function makeFlowCurves(flowDensity: number, flowRadius: number, voidRadius: number) {
  const count = Math.max(4, Math.round(flowDensity));
  const curves: THREE.CurvePath<THREE.Vector3>[] = [];
  const layerCount = Math.ceil(count / GRAVITY_SETTINGS_NEAR_STREAM_PATHS.length);
  const pathScale = (voidRadius / 31) * THREE.MathUtils.clamp(flowRadius / 2.8, 0.72, 1.48);

  for (let index = 0; index < count; index += 1) {
    const sourcePath = GRAVITY_SETTINGS_NEAR_STREAM_PATHS[index % GRAVITY_SETTINGS_NEAR_STREAM_PATHS.length];
    const layer = Math.floor(index / GRAVITY_SETTINGS_NEAR_STREAM_PATHS.length);
    const lane = index % GRAVITY_SETTINGS_NEAR_STREAM_PATHS.length;
    const layerOffset = layer - (layerCount - 1) / 2;
    const radialScale = 1 + layerOffset * 0.035;
    const depth = (lane % 5 - 2) * 0.014 + layer * 0.008;
    const tokens = sourcePath.match(/[A-Za-z]|-?\d*\.?\d+/g) ?? [];
    const curve = new THREE.CurvePath<THREE.Vector3>();
    let cursor = 0;
    let current: readonly [number, number] = [0, 0];

    const toWorld = ([x, y]: readonly [number, number]) => new THREE.Vector3(
      (x - 66) * pathScale * radialScale,
      (60 - y) * pathScale * radialScale,
      depth
    );

    while (cursor < tokens.length) {
      const command = tokens[cursor++];
      if (command === "M") {
        current = [Number(tokens[cursor++]), Number(tokens[cursor++])];
        continue;
      }
      if (command !== "C") continue;

      const control1: readonly [number, number] = [Number(tokens[cursor++]), Number(tokens[cursor++])];
      const control2: readonly [number, number] = [Number(tokens[cursor++]), Number(tokens[cursor++])];
      const end: readonly [number, number] = [Number(tokens[cursor++]), Number(tokens[cursor++])];
      curve.add(new THREE.CubicBezierCurve3(toWorld(current), toWorld(control1), toWorld(control2), toWorld(end)));
      current = end;
    }

    curves.push(curve);
  }

  return curves;
}

function makeFlowFilaments(flowCurves: THREE.Curve<THREE.Vector3>[], variants: number) {
  const scales = [0.92, 1.12].slice(0, variants);
  const filaments: THREE.CatmullRomCurve3[] = [];

  flowCurves.forEach((source, sourceIndex) => {
    scales.forEach((baseScale, variantIndex) => {
      const random = seededRandom(9301 + sourceIndex * 97 + variantIndex * 997);
      const scaleX = baseScale * (0.93 + random() * 0.14);
      const scaleY = baseScale * (0.88 + random() * 0.24);
      const rotation = (random() - 0.5) * 0.14;
      const phase = random() * Math.PI * 2;
      const zOffset = [-0.11, -0.025][variantIndex];
      const points: THREE.Vector3[] = [];
      const samples = 92;

      for (let sample = 0; sample < samples; sample += 1) {
        const t = sample / (samples - 1);
        const point = source.getPointAt(t);
        const x = point.x * scaleX;
        const y = point.y * scaleY;
        const bend = Math.sin(Math.PI * t) * Math.sin(phase + t * Math.PI * 2) * 0.014;
        point.x = x * Math.cos(rotation) - y * Math.sin(rotation) + bend;
        point.y = x * Math.sin(rotation) + y * Math.cos(rotation) + bend * 0.35;
        point.z += zOffset + Math.sin(phase + t * Math.PI * 2) * 0.01;
        points.push(point);
      }

      filaments.push(new THREE.CatmullRomCurve3(points, false, "centripetal"));
    });
  });

  return filaments;
}

function makeAccretionDiskGeometry(voidRadius: number, flowRadius: number, distortionStrength: number, quality: Quality) {
  const radialSegments = QUALITY[quality].diskRings;
  const angularSegments = QUALITY[quality].diskSegments;
  const verticesPerRing = angularSegments + 1;
  const innerRadius = voidRadius * 1.035;
  const outerRadius = flowRadius * 0.84;
  const positions: number[] = [];
  const colors: number[] = [];
  const indices: number[] = [];
  const cool = new THREE.Color("#145078");
  const blue = new THREE.Color("#4c9cc6");
  const ice = new THREE.Color("#d8f4ff");

  for (let ring = 0; ring <= radialSegments; ring += 1) {
    const progress = ring / radialSegments;
    for (let spoke = 0; spoke <= angularSegments; spoke += 1) {
      const angle = Math.PI * 2 * spoke / angularSegments;
      const hotspot = Math.pow(Math.max(0, Math.cos(angle - 2.35)), 5)
        * 0.86 + Math.pow(Math.max(0, Math.cos(angle - 4.9)), 3) * 0.26;
      const innerBand = Math.exp(-Math.pow(progress / 0.18, 2));
      const outerFade = Math.pow(1 - progress, 0.72);
      const streakWave = Math.sin(angle * 38 + progress * 22 + Math.sin(angle * 7) * 1.8);
      const streak = 0.73 + 0.27 * (0.5 + 0.5 * streakWave);
      const irregularity = Math.sin(angle * 3 + progress * 5.5) * 0.018
        + Math.sin(angle * 11 - progress * 10) * 0.006;
      const radius = innerRadius + progress * (outerRadius - innerRadius)
        + irregularity * (0.35 + distortionStrength);
      const flattening = 0.74 - progress * 0.28;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius * flattening;
      const z = -0.19 + Math.sin(angle * 2 + progress * 5) * (0.025 + distortionStrength * 0.025);
      positions.push(x, y, z);

      const colorMix = THREE.MathUtils.clamp(innerBand * 0.42 + hotspot * 0.68, 0, 1);
      const color = cool.clone().lerp(blue, 0.38 + innerBand * 0.3).lerp(ice, colorMix * 0.72);
      const alpha = outerFade * streak * (0.12 + innerBand * 0.68) * (0.24 + hotspot * 0.76);
      color.multiplyScalar(alpha);
      colors.push(color.r, color.g, color.b);
    }
  }

  for (let ring = 0; ring < radialSegments; ring += 1) {
    for (let spoke = 0; spoke < angularSegments; spoke += 1) {
      const a = ring * verticesPerRing + spoke;
      const b = (ring + 1) * verticesPerRing + spoke;
      const c = b + 1;
      const d = a + 1;
      indices.push(a, b, d, b, c, d);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.setIndex(indices);
  return geometry;
}

function makeDistortionCurves(flowRadius: number, voidRadius: number, distortionStrength: number, count: number) {
  const curves: THREE.CatmullRomCurve3[] = [];
  const maxRadius = Math.min(flowRadius + 0.2, 3.65);

  for (let index = 0; index < count; index += 1) {
    const radius = voidRadius * 1.42 + index * ((maxRadius - voidRadius * 1.42) / (count - 1));
    const start = -1.3 + index * 0.19;
    const end = start + 3.5 + (index % 3) * 0.18;
    const points: THREE.Vector3[] = [];
    const samples = 40;

    for (let sample = 0; sample <= samples; sample += 1) {
      const angle = start + (end - start) * sample / samples;
      const bend = Math.sin(angle * 2.0 + index * 0.72) * distortionStrength * 0.095;
      const x = Math.cos(angle) * (radius + bend);
      const y = Math.sin(angle) * (radius * (0.66 + (index % 3) * 0.025) + bend);
      const z = -0.28 - index * 0.009;
      points.push(new THREE.Vector3(x, y, z));
    }

    curves.push(new THREE.CatmullRomCurve3(points, false, "centripetal"));
  }

  return curves;
}

function makeParticlePositions(curves: THREE.Curve<THREE.Vector3>[], flowDensity: number) {
  const particleCount = Math.max(18, Math.round(flowDensity * 2.4));
  const positions = new Float32Array(particleCount * 3);
  const random = seededRandom(8147);

  for (let index = 0; index < particleCount; index += 1) {
    const curve = curves[Math.floor(random() * curves.length)];
    const point = curve.getPointAt(0.04 + random() * 0.92);
    positions[index * 3] = point.x;
    positions[index * 3 + 1] = point.y;
    positions[index * 3 + 2] = point.z + (random() - 0.5) * 0.025;
  }

  return positions;
}

function StarPoints({
  positions,
  size = 0.018,
  opacity = 0.38,
  color = "#9bdcff"
}: { positions: Float32Array; size?: number; opacity?: number; color?: string }) {
  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color={color}
        size={size}
        sizeAttenuation
        transparent
        opacity={opacity}
        depthWrite={false}
        toneMapped={false}
      />
    </points>
  );
}

function AccretionDisk({
  voidRadius,
  flowRadius,
  distortionStrength,
  quality
}: { voidRadius: number; flowRadius: number; distortionStrength: number; quality: Quality }) {
  const geometry = useMemo(
    () => makeAccretionDiskGeometry(voidRadius, flowRadius, distortionStrength, quality),
    [voidRadius, flowRadius, distortionStrength, quality]
  );

  useEffect(() => () => geometry.dispose(), [geometry]);

  return (
    <mesh geometry={geometry} renderOrder={1}>
      <meshBasicMaterial
        vertexColors
        transparent
        opacity={0.48}
        depthWrite={false}
        side={THREE.DoubleSide}
        blending={THREE.AdditiveBlending}
        toneMapped={false}
      />
    </mesh>
  );
}

function CurveStrands({
  curves,
  color,
  opacity,
  width,
  quality,
  time,
  blending = THREE.NormalBlending,
  renderOrder = 0
}: {
  curves: THREE.Curve<THREE.Vector3>[];
  color: string;
  opacity: number;
  width: number;
  quality: Quality;
  time?: MotionTime;
  blending?: THREE.Blending;
  renderOrder?: number;
}) {
  const uniforms = useMemo(() => ({
    uColor: { value: new THREE.Color(color) },
    uOpacity: { value: opacity },
    uTime: time ?? { value: 0 }
  }), [color, opacity, time]);
  const detail = QUALITY[quality];
  return (
    <group>
      {curves.map((curve, index) => (
        <mesh key={index} renderOrder={renderOrder}>
          <tubeGeometry args={[curve, detail.tubeSegments, width * (index % 4 === 0 ? 1.2 : 1), detail.tubeSides, false]} />
          {time ? <shaderMaterial
            vertexShader={flowVertexShader}
            fragmentShader={flowFragmentShader}
            uniforms={{ ...uniforms, uOpacity: { value: opacity * (index % 5 === 0 ? 1.5 : 1) } }}
            transparent
            depthWrite={false}
            toneMapped={false}
            blending={blending}
          /> : <meshBasicMaterial
            color={color}
            transparent
            opacity={opacity * (index % 5 === 0 ? 1.5 : 1)}
            depthWrite={false}
            toneMapped={false}
            blending={blending}
          />}
        </mesh>
      ))}
    </group>
  );
}

export function SettingsGravityWell({
  voidRadius = 0.68,
  lensingRadius = 0.735,
  lensingIntensity = 0.96,
  distortionStrength = 0.42,
  flowDensity = 24,
  flowRadius = 2.8,
  haloIntensity = 0.52,
  showInnerTunnel = false,
  quality = "hero",
  reducedMotion = false
}: SettingsGravityWellProps) {
  const detail = QUALITY[quality];
  const time = useMemo(() => ({ value: 0 }), []);
  const flow = useRef<THREE.Group>(null);
  const disk = useRef<THREE.Group>(null);
  const density = quality === "navigation" ? Math.max(4, Math.round(flowDensity * 0.5)) : flowDensity;
  useFrame((_, delta) => {
    if (reducedMotion) return;
    time.value += Math.min(delta, 0.1);
    if (flow.current) flow.current.rotation.z = -time.value * 0.006;
    if (disk.current) disk.current.rotation.z = -time.value * 0.003;
  });
  const lensMaterial = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      uVoidRadius: { value: voidRadius },
      uLensingRadius: { value: lensingRadius },
      uLensingIntensity: { value: lensingIntensity },
      uHaloIntensity: { value: haloIntensity },
      uDistortionStrength: { value: distortionStrength },
      uTime: time
    },
    vertexShader: lensVertexShader,
    fragmentShader: lensFragmentShader,
    transparent: true,
    depthWrite: false,
    depthTest: true,
    blending: THREE.AdditiveBlending,
    toneMapped: false
  }), [voidRadius, lensingRadius, lensingIntensity, haloIntensity, distortionStrength, time]);

  useEffect(() => () => lensMaterial.dispose(), [lensMaterial]);

  const starPositions = useMemo(() => makeStarPositions(detail.stars, voidRadius), [detail.stars, voidRadius]);
  const brighterStarPositions = useMemo(() => makeStarPositions(detail.brightStars, voidRadius, 92013), [detail.brightStars, voidRadius]);
  const flowCurves = useMemo(
    () => makeFlowCurves(density, flowRadius, voidRadius),
    [density, flowRadius, voidRadius]
  );
  const flowFilaments = useMemo(
    () => makeFlowFilaments(flowCurves, detail.filaments),
    [flowCurves, detail.filaments]
  );
  const distortionCurves = useMemo(
    () => makeDistortionCurves(flowRadius, voidRadius, distortionStrength, detail.distortions),
    [flowRadius, voidRadius, distortionStrength, detail.distortions]
  );
  const particlePositions = useMemo(
    () => makeParticlePositions([...flowCurves, ...flowFilaments], density),
    [flowCurves, flowFilaments, density]
  );

  return (
    <group name="GravityWellRoot">
      <group name="WarpedStarField">
        <StarPoints positions={starPositions} size={0.03} opacity={0.54} />
        <StarPoints positions={brighterStarPositions} size={0.046} opacity={0.78} color="#c6edff" />
      </group>

      <group name="OuterDistortionField">
        <CurveStrands curves={distortionCurves} color="#438eb1" opacity={0.042} width={0.0028} quality={quality} />
      </group>

      <group ref={disk} name="AccretionDiskLayer">
        <AccretionDisk voidRadius={voidRadius} flowRadius={flowRadius} distortionStrength={distortionStrength} quality={quality} />
      </group>

      <group ref={flow} name="AccretionFlow">
        <group name="FlowFilaments">
          <CurveStrands curves={flowFilaments} color="#438eb1" opacity={0.03} width={0.0065} blending={THREE.AdditiveBlending} quality={quality} time={time} />
          <CurveStrands curves={flowFilaments} color="#79bfdf" opacity={0.075} width={0.0023} quality={quality} time={time} />
        </group>

        <group name="FlowField">
          <CurveStrands curves={flowCurves} color="#2f86ad" opacity={0.13} width={0.0075} blending={THREE.AdditiveBlending} quality={quality} time={time} />
          <CurveStrands curves={flowCurves} color="#9adcf5" opacity={0.31} width={0.0026} quality={quality} time={time} />
        </group>

        <group name="FlowParticles">
          <StarPoints positions={particlePositions} size={0.042} opacity={0.86} color="#c9f0ff" />
        </group>
      </group>

      <group name="LensingRing" position={[0, 0, -0.11]}>
        <mesh renderOrder={2}>
          <planeGeometry args={[7.2, 7.2]} />
          <primitive object={lensMaterial} attach="material" />
        </mesh>
      </group>

      <group name="VoidCore" visible={!showInnerTunnel}>
        <mesh renderOrder={3}>
          <sphereGeometry args={[voidRadius, ...detail.voidSegments]} />
          <meshBasicMaterial color="#000105" toneMapped={false} />
        </mesh>
      </group>

      <group name="InnerTunnel" visible={showInnerTunnel} position={[0, 0, 0.02]}>
        {[0, 1, 2, 3].map((layer) => {
          const radius = voidRadius * (0.86 - layer * 0.17);
          const depth = -layer * 0.18;
          return (
            <group key={layer} position={[0, 0, depth]}>
              <mesh>
                <circleGeometry args={[radius, detail.tunnelSegments]} />
                <meshBasicMaterial color={layer === 0 ? "#020811" : "#000206"} side={THREE.DoubleSide} />
              </mesh>
              <mesh>
                <torusGeometry args={[radius, Math.max(0.008, voidRadius * 0.014), 6, detail.tunnelRingSegments]} />
                <meshBasicMaterial color="#72bce1" transparent opacity={0.22 - layer * 0.04} toneMapped={false} />
              </mesh>
            </group>
          );
        })}
      </group>
    </group>
  );
}
