import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

const DESIGN = {
  pathScale: 0.00708,
  pathSamplesPerCurve: 30,
  orbitSegments: 640,
  glowRadius: 0.009,
  coreRadius: 0.225,
  innerEnergyRadius: 0.27,
  coronaRadius: 0.335,
  outerCoronaRadius: 0.43,
  particleCount: 8,
  particlePixelSize: 2.2
} as const;

export const SELF_CORE_VISUALS = DESIGN;

export type SelfCoreProps = {
  scale?: number;
  showParticles?: boolean;
  quality?: "hero" | "navigation";
  reducedMotion?: boolean;
  orbitSpread?: number;
  highlighted?: boolean;
};

const QUALITY = {
  hero: { pathSamples: DESIGN.pathSamplesPerCurve, orbitSegments: DESIGN.orbitSegments, tubeSides: 5, coreSegments: [80, 64], shellSegments: [48, 36], particles: DESIGN.particleCount, packets: 5, trailLength: 4 },
  navigation: { pathSamples: 12, orbitSegments: 160, tubeSides: 3, coreSegments: [32, 24], shellSegments: [24, 18], particles: 4, packets: 2, trailLength: 2 }
} as const;

type VisualProps = {
  quality: "hero" | "navigation";
  time: { value: number };
};

type CurveSegment = {
  control1: readonly [number, number];
  control2: readonly [number, number];
  end: readonly [number, number];
};

type DashWindow = readonly [number, number];

type OrbitSpec = {
  id: string;
  path: string;
  width: number;
  opacity: number;
  period: number;
  windows: readonly DashWindow[];
  z: number;
  tilt: readonly [number, number];
  radialScale?: number;
  tint: string;
  glow?: boolean;
  foreground?: boolean;
};

const ORBITS: OrbitSpec[] = [
  { id: "A", path: "M28 132 C48 91 96 72 151 78 C207 84 239 110 231 141 C221 177 173 193 117 184 C64 176 17 157 28 132 Z", width: 1.22, opacity: 0.52, period: 0.87, windows: [[0, 0.30], [0.35, 0.42], [0.53, 0.78]], z: 0.008, tilt: [0.10, -0.08], radialScale: 1.08, tint: "#36aaff", glow: true, foreground: true },
  { id: "B", path: "M72 34 C112 52 162 102 187 157 C208 203 193 228 164 218 C124 204 75 153 53 99 C36 58 45 23 72 34 Z", width: 0.82, opacity: 0.29, period: 1, windows: [[0, 0.17], [0.25, 0.59], [0.64, 0.75]], z: -0.022, tilt: [-0.13, 0.09], radialScale: 1.16, tint: "#35c8b8" },
  { id: "C", path: "M194 42 C214 65 195 116 153 164 C113 210 69 232 52 207 C34 181 57 130 97 85 C136 42 176 21 194 42 Z", width: 1.18, opacity: 0.48, period: 1, windows: [[0, 0.44], [0.53, 0.57], [0.69, 0.88]], z: 0.002, tilt: [0.08, 0.14], radialScale: 1.1, tint: "#79baff", glow: true, foreground: true },
  { id: "D", path: "M20 91 C57 47 121 25 185 49 C241 70 257 118 229 169 C201 220 135 244 73 219 C18 197 -12 145 20 91 Z", width: 0.86, opacity: 0.34, period: 1, windows: [[0, 0.11], [0.18, 0.66], [0.82, 0.86]], z: -0.038, tilt: [-0.06, -0.12], radialScale: 1.31, tint: "#c59a64" },
  { id: "E", path: "M58 145 C68 111 104 92 143 96 C183 100 210 124 202 151 C193 181 156 196 117 189 C78 182 49 169 58 145 Z", width: 0.76, opacity: 0.16, period: 1, windows: [[0, 0.28], [0.34, 0.42], [0.52, 0.86]], z: 0.044, tilt: [0.14, 0.06], tint: "#62b8df" },
  { id: "F", path: "M39 172 C75 199 141 203 192 171 C231 146 237 108 211 87 C177 59 111 62 65 91 C25 116 13 151 39 172 Z", width: 0.78, opacity: 0.19, period: 0.91, windows: [[0, 0.15], [0.28, 0.48], [0.66, 0.84]], z: 0.018, tilt: [-0.16, 0.12], tint: "#a28ce3" },
  { id: "G", path: "M116 18 C148 31 178 72 187 121 C197 174 180 223 147 239 C118 253 92 223 83 176 C73 126 83 72 103 34 C108 25 112 20 116 18 Z", width: 1.12, opacity: 0.43, period: 0.91, windows: [[0, 0.099], [0.187, 0.604], [0.747, 0.791]], z: 0.028, tilt: [0.10, -0.15], radialScale: 1.2, tint: "#4bc9ed", glow: true, foreground: true },
  { id: "H", path: "M35 71 C72 46 130 45 178 67 C224 88 246 126 226 158 C205 192 153 205 103 190 C55 176 21 143 23 105 C24 91 28 79 35 71 Z", width: 0.9, opacity: 0.3, period: 1, windows: [[0, 0.235], [0.343, 0.814]], z: -0.05, tilt: [0.05, 0.16], radialScale: 1.25, tint: "#61c6ba" },
  { id: "I", path: "M83 111 C101 89 137 83 164 101 C190 118 188 148 164 165 C139 183 101 176 84 153 C73 138 73 123 83 111 Z", width: 0.72, opacity: 0.14, period: 0.96, windows: [[0, 0.042], [0.125, 0.344], [0.406, 0.812]], z: 0.066, tilt: [-0.08, -0.04], tint: "#639bdc" },
  { id: "J", path: "M109 70 C135 82 155 108 158 137 C161 166 145 192 123 194 C102 195 91 168 96 139 C100 112 101 82 109 70 Z", width: 0.74, opacity: 0.15, period: 0.51, windows: [[0, 0.549], [0.706, 0.784]], z: -0.068, tilt: [0.12, 0.10], tint: "#9f94e3" }
];

type OrbitPacketSpec = {
  orbitId: string;
  duration: number;
  initialElapsed: number;
};

const PACKETS: OrbitPacketSpec[] = [
  { orbitId: "E", duration: 9.5, initialElapsed: 0 },
  { orbitId: "A", duration: 14.6, initialElapsed: 4 },
  { orbitId: "C", duration: 19.8, initialElapsed: 9 },
  { orbitId: "D", duration: 24, initialElapsed: 13 },
  { orbitId: "B", duration: 17.2, initialElapsed: 7 }
];

const ATMOSPHERE_VERTEX_SHADER = /* glsl */ `
  varying vec3 vLocalPosition;
  varying vec3 vNormalView;
  varying vec3 vPositionView;
  void main() {
    vLocalPosition = position;
    vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
    vNormalView = normalize(normalMatrix * normal);
    vPositionView = viewPosition.xyz;
    gl_Position = projectionMatrix * viewPosition;
  }
`;

const ATMOSPHERE_FRAGMENT_SHADER = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  uniform float uPower;
  uniform float uTime;
  varying vec3 vLocalPosition;
  varying vec3 vNormalView;
  varying vec3 vPositionView;
  void main() {
    float facing = abs(dot(normalize(vNormalView), normalize(-vPositionView)));
    vec3 direction = normalize(vLocalPosition);
    float waveA = sin(direction.x * 37.0 + direction.y * 26.0 - direction.z * 19.0 + uTime * 0.42);
    float waveB = sin(direction.x * 21.0 - direction.y * 34.0 + direction.z * 29.0 - uTime * 0.31);
    float filaments = pow(max(0.0, 0.5 + 0.5 * waveA * waveB), 7.0);
    float warp = (waveA * 0.026 + waveB * 0.018) * (0.35 + filaments);
    float rim = pow(clamp(1.0 - facing + warp, 0.0, 1.0), uPower) * 0.76;
    float faceGlow = pow(1.0 - facing, 2.2) * 0.16;
    float plasmaGlow = filaments * pow(1.0 - facing, 1.12) * 0.16;
    vec3 plasmaColor = mix(uColor, vec3(0.62, 0.9, 1.0), filaments * 0.62);
    gl_FragColor = vec4(plasmaColor, (rim * (0.56 + filaments * 1.15) + faceGlow + plasmaGlow) * uOpacity);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

const CORE_VERTEX_SHADER = /* glsl */ `
  varying vec3 vLocalPosition;
  varying vec3 vNormalView;
  varying vec3 vPositionView;
  void main() {
    vLocalPosition = position;
    vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
    vNormalView = normalize(normalMatrix * normal);
    vPositionView = viewPosition.xyz;
    gl_Position = projectionMatrix * viewPosition;
  }
`;

const CORE_FRAGMENT_SHADER = /* glsl */ `
  uniform float uTime;
  varying vec3 vLocalPosition;
  varying vec3 vNormalView;
  varying vec3 vPositionView;
  float hash31(vec3 p) {
    p = fract(p * 0.1031);
    p += dot(p, p.yzx + 33.33);
    return fract((p.x + p.y) * p.z);
  }
  float valueNoise(vec3 p) {
    vec3 cell = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash31(cell + vec3(0.0, 0.0, 0.0));
    float b = hash31(cell + vec3(1.0, 0.0, 0.0));
    float c = hash31(cell + vec3(0.0, 1.0, 0.0));
    float d = hash31(cell + vec3(1.0, 1.0, 0.0));
    float e = hash31(cell + vec3(0.0, 0.0, 1.0));
    float f1 = hash31(cell + vec3(1.0, 0.0, 1.0));
    float g = hash31(cell + vec3(0.0, 1.0, 1.0));
    float h = hash31(cell + vec3(1.0, 1.0, 1.0));
    return mix(mix(mix(a, b, f.x), mix(c, d, f.x), f.y),
      mix(mix(e, f1, f.x), mix(g, h, f.x), f.y), f.z);
  }
  float fbm(vec3 p) {
    float sum = 0.0;
    float amplitude = 0.5;
    for (int octave = 0; octave < 4; octave++) {
      sum += valueNoise(p) * amplitude;
      p = p * 2.03 + vec3(7.1, 3.7, 5.3);
      amplitude *= 0.5;
    }
    return sum;
  }
  void main() {
    vec3 direction = normalize(vLocalPosition);
    vec3 drift = vec3(uTime * 0.11, -uTime * 0.075, uTime * 0.045);
    float broadFlow = fbm(direction * 6.6 + drift);
    float fineFlow = fbm(direction * 15.0 - drift * 1.35);
    float current = 0.5 + 0.5 * sin(direction.x * 10.0 + direction.y * 13.0 - direction.z * 9.0
      + fineFlow * 7.0 + uTime * 0.12);
    float filaments = pow(max(0.0, current), 5.2);
    float granulation = fbm(direction * 38.0 + drift * 2.0);
    float sparks = smoothstep(0.70, 0.91, granulation);
    float facing = max(dot(normalize(vNormalView), normalize(-vPositionView)), 0.0);
    float limb = smoothstep(0.0, 0.88, facing);
    vec3 deepBlue = vec3(0.008, 0.035, 0.12);
    vec3 cobalt = vec3(0.025, 0.30, 0.64);
    vec3 ionBlue = vec3(0.20, 0.70, 0.98);
    vec3 iceBlue = vec3(0.55, 0.86, 1.0);
    vec3 color = mix(deepBlue, cobalt, smoothstep(0.16, 0.77, broadFlow));
    color = mix(color, ionBlue, smoothstep(0.34, 0.79, fineFlow) * 0.78);
    color = mix(color, iceBlue, smoothstep(0.77, 0.96, granulation) * 0.45);
    color += vec3(0.12, 0.48, 0.82) * filaments * 0.62;
    color += vec3(0.6, 0.9, 1.0) * sparks * 0.34;

    // A broken, turbulent plasma band gives the photosphere a bright solar rim.
    float ringWarp = (fineFlow - 0.5) * 0.22
      + sin(direction.x * 21.0 + direction.y * 17.0 + direction.z * 13.0 + uTime * 0.18) * 0.055;
    float plasmaBand = exp(-pow((facing - 0.53 - ringWarp) * 20.0, 2.0));
    float magneticFlicker = 0.4 + 0.6 * pow(max(0.0, sin(direction.x * 31.0
      + direction.y * 27.0 - direction.z * 23.0 + fineFlow * 8.0 + uTime * 0.24)), 4.0);
    color += vec3(0.56, 0.83, 1.0) * plasmaBand * magneticFlicker * (1.1 + fineFlow * 0.8);
    color += vec3(0.86, 0.98, 1.0) * plasmaBand * sparks * 1.35;
    float outerArches = exp(-pow((facing - 0.72 - ringWarp * 0.68) * 18.0, 2.0));
    color += vec3(0.25, 0.63, 0.93) * outerArches * (0.4 + magneticFlicker * 0.8);

    float hotCenter = pow(facing, 62.0);
    color = mix(color, vec3(0.94, 0.99, 1.0), hotCenter * 0.96);
    color += vec3(0.3, 0.57, 0.78) * hotCenter * 0.36;
    color *= 0.24 + limb * 1.13;
    gl_FragColor = vec4(color, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

const ORBIT_VERTEX_SHADER = /* glsl */ `
  varying vec2 vPathUv;
  varying vec3 vNormalView;
  varying vec3 vPositionView;
  void main() {
    vPathUv = uv;
    vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
    vNormalView = normalize(normalMatrix * normal);
    vPositionView = viewPosition.xyz;
    gl_Position = projectionMatrix * viewPosition;
  }
`;

const ORBIT_FRAGMENT_SHADER = /* glsl */ `
  uniform vec3 uColorStart;
  uniform vec3 uColorMid;
  uniform vec3 uColorEnd;
  uniform float uOpacity;
  uniform float uDashPeriod;
  uniform vec2 uDashA;
  uniform vec2 uDashB;
  uniform vec2 uDashC;
  uniform float uEdgeSoftness;
  varying vec2 vPathUv;
  varying vec3 vNormalView;
  varying vec3 vPositionView;
  float dashWindow(float position, vec2 window) {
    return smoothstep(window.x, window.x + uEdgeSoftness, position)
      * (1.0 - smoothstep(window.y - uEdgeSoftness, window.y, position));
  }
  void main() {
    float phase = fract(vPathUv.x / uDashPeriod);
    float dash = max(dashWindow(phase, uDashA), max(dashWindow(phase, uDashB), dashWindow(phase, uDashC)));
    float along = smoothstep(0.0, 0.5, vPathUv.x);
    vec3 color = mix(uColorStart, uColorMid, smoothstep(0.0, 0.5, vPathUv.x));
    color = mix(color, uColorEnd, smoothstep(0.5, 1.0, vPathUv.x) * 0.58);
    float viewFacing = 0.76 + 0.24 * abs(dot(normalize(vNormalView), normalize(-vPositionView)));
    float alpha = dash * uOpacity * viewFacing;
    gl_FragColor = vec4(color * (0.88 + along * 0.12), alpha);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

function parseCubicPath(path: string) {
  const tokens = path.match(/[A-Za-z]|-?\d*\.?\d+/g) ?? [];
  const segments: CurveSegment[] = [];
  let cursor = 0;
  let command = "";
  let current: readonly [number, number] = [0, 0];
  let start: readonly [number, number] = [0, 0];

  while (cursor < tokens.length) {
    if (/^[A-Za-z]$/.test(tokens[cursor])) {
      command = tokens[cursor++];
      if (command === "Z" || command === "z") break;
      if (command === "M" || command === "m") {
        current = [Number(tokens[cursor++]), Number(tokens[cursor++])];
        start = current;
        command = command === "M" ? "C" : "c";
        continue;
      }
    }

    if (command !== "C") {
      throw new Error(`Unsupported Self Core path command: ${command}`);
    }

    const control1: readonly [number, number] = [Number(tokens[cursor++]), Number(tokens[cursor++])];
    const control2: readonly [number, number] = [Number(tokens[cursor++]), Number(tokens[cursor++])];
    const end: readonly [number, number] = [Number(tokens[cursor++]), Number(tokens[cursor++])];
    segments.push({ control1, control2, end });
    current = end;
  }

  if (current[0] !== start[0] || current[1] !== start[1]) {
    segments.push({ control1: current, control2: start, end: start });
  }

  return { start, segments };
}

function cubicPoint(
  start: readonly [number, number],
  segment: CurveSegment,
  amount: number
) {
  const inverse = 1 - amount;
  const a = inverse * inverse * inverse;
  const b = 3 * inverse * inverse * amount;
  const c = 3 * inverse * amount * amount;
  const d = amount * amount * amount;
  return [
    a * start[0] + b * segment.control1[0] + c * segment.control2[0] + d * segment.end[0],
    a * start[1] + b * segment.control1[1] + c * segment.control2[1] + d * segment.end[1]
  ] as const;
}

function makeOrbitCurve(orbit: OrbitSpec, samples: number = DESIGN.pathSamplesPerCurve, orbitSpread = 1) {
  const { start, segments } = parseCubicPath(orbit.path);
  const rotation = new THREE.Euler(orbit.tilt[0], orbit.tilt[1], 0);
  const radialScale = orbit.radialScale ?? 1;
  const spread = orbit.foreground ? 1 : THREE.MathUtils.clamp(orbitSpread, 1, 4);
  let segmentStart = start;
  const points: THREE.Vector3[] = [];

  segments.forEach((segment) => {
    for (let index = 0; index < samples; index += 1) {
      const [x, y] = cubicPoint(segmentStart, segment, index / samples);
      const point = new THREE.Vector3(
        (x - 130) * DESIGN.pathScale * radialScale * spread,
        (132 - y) * DESIGN.pathScale * radialScale * Math.sqrt(spread),
        0
      ).applyEuler(rotation);
      point.z += orbit.z;
      points.push(point);
    }
    segmentStart = segment.end;
  });

  return new THREE.CatmullRomCurve3(points, true, "centripetal");
}

function makeHaloTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const context = canvas.getContext("2d");
  if (!context) return new THREE.Texture();

  const gradient = context.createRadialGradient(128, 128, 0, 128, 128, 128);
  gradient.addColorStop(0, "rgba(240, 252, 255, 0.50)");
  gradient.addColorStop(0.12, "rgba(203, 245, 255, 0.38)");
  gradient.addColorStop(0.38, "rgba(58, 188, 255, 0.19)");
  gradient.addColorStop(1, "rgba(14, 90, 180, 0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, 256, 256);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function AtmosphereShell({
  name,
  radius,
  color,
  opacity,
  power,
  quality,
  time
}: {
  name: string;
  radius: number;
  color: string;
  opacity: number;
  power: number;
} & VisualProps) {
  const uniforms = useMemo(() => ({
    uColor: { value: new THREE.Color(color) },
    uOpacity: { value: opacity },
    uPower: { value: power },
    uTime: time
  }), [color, opacity, power, time]);

  return (
    <mesh name={name}>
      <sphereGeometry args={[radius, ...QUALITY[quality].shellSegments]} />
      <shaderMaterial
        vertexShader={ATMOSPHERE_VERTEX_SHADER}
        fragmentShader={ATMOSPHERE_FRAGMENT_SHADER}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        side={THREE.FrontSide}
        toneMapped={false}
      />
    </mesh>
  );
}

function Halo({ highlighted, reducedMotion }: { highlighted: boolean; reducedMotion: boolean }) {
  const texture = useMemo(makeHaloTexture, []);
  const sprite = useRef<THREE.Sprite>(null);
  const brightness = useRef(1);
  const color = useMemo(() => new THREE.Color("#82d9ff"), []);
  useEffect(() => () => texture.dispose(), [texture]);
  useFrame((_, delta) => {
    if (!sprite.current) return;
    const target = highlighted ? 1.55 : 1;
    brightness.current = reducedMotion ? target : THREE.MathUtils.damp(brightness.current, target, 7, Math.min(delta, 0.1));
    sprite.current.material.color.copy(color).multiplyScalar(brightness.current);
  });

  return (
    <group name="Halo">
      <sprite ref={sprite} name="HaloLight" scale={[1.4, 1.4, 1]} renderOrder={1}>
        <spriteMaterial
          map={texture}
          color="#82d9ff"
          opacity={1.02}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
      </sprite>
    </group>
  );
}

function CoreSphere({ quality, time }: VisualProps) {
  const uniforms = useMemo(() => ({ uTime: time }), [time]);
  const heartTexture = useMemo(makeHaloTexture, []);
  useEffect(() => () => heartTexture.dispose(), [heartTexture]);

  return (
    <group name="CoreSphere" renderOrder={5}>
      <mesh>
        <sphereGeometry args={[DESIGN.coreRadius, ...QUALITY[quality].coreSegments]} />
        <shaderMaterial
          vertexShader={CORE_VERTEX_SHADER}
          fragmentShader={CORE_FRAGMENT_SHADER}
          uniforms={uniforms}
          toneMapped={false}
        />
      </mesh>
      <sprite
        position={[0, 0, DESIGN.coreRadius * 1.03]}
        scale={[0.078, 0.078, 1]}
        renderOrder={6}
      >
        <spriteMaterial
          map={heartTexture}
          color="#effcff"
          opacity={0.94}
          transparent
          depthTest
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
      </sprite>
    </group>
  );
}

function InnerEnergyShell(props: VisualProps) {
  return (
    <group name="InnerEnergyShell" renderOrder={2}>
      <AtmosphereShell
        name="InnerEnergySurface"
        radius={DESIGN.innerEnergyRadius}
        color="#8adfff"
        opacity={0.075}
        power={1.65}
        {...props}
      />
    </group>
  );
}

function Corona(props: VisualProps) {
  return (
    <group name="Corona" renderOrder={2}>
      <AtmosphereShell
        name="CoronaRim"
        radius={DESIGN.coronaRadius}
        color="#67d3ff"
        opacity={0.2}
        power={2.1}
        {...props}
      />
      <AtmosphereShell
        name="OuterCoronaRim"
        radius={DESIGN.outerCoronaRadius}
        color="#399be0"
        opacity={0.065}
        power={2.7}
        {...props}
      />
    </group>
  );
}

function createOrbitMaterial(orbit: OrbitSpec, foreground = false) {
  const windows = foreground
    ? [[0.17, 0.29], [1, 1], [1, 1]] as const
    : ([...orbit.windows, [1, 1], [1, 1]].slice(0, 3) as readonly DashWindow[]);
  const period = foreground ? 1 : orbit.period;
  const routeColor = new THREE.Color(orbit.tint);
  const accentColor = new THREE.Color("#dffaff");
  return new THREE.ShaderMaterial({
    vertexShader: ORBIT_VERTEX_SHADER,
    fragmentShader: ORBIT_FRAGMENT_SHADER,
    uniforms: {
      uColorStart: { value: foreground ? new THREE.Color("#67caff") : routeColor.clone().multiplyScalar(0.22) },
      uColorMid: { value: foreground ? new THREE.Color("#bcecff") : routeColor.clone().lerp(new THREE.Color("#79dcff"), 0.24) },
      uColorEnd: { value: foreground ? new THREE.Color("#effcff") : routeColor.clone().lerp(accentColor, 0.52) },
      uOpacity: { value: foreground ? 0.46 : orbit.opacity },
      uDashPeriod: { value: period },
      uDashA: { value: new THREE.Vector2(...windows[0]) },
      uDashB: { value: new THREE.Vector2(...windows[1]) },
      uDashC: { value: new THREE.Vector2(...windows[2]) },
      uEdgeSoftness: { value: 0.009 }
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
    toneMapped: false
  });
}

function OrbitArc({ orbit, quality, orbitSpread }: { orbit: OrbitSpec; quality: VisualProps["quality"]; orbitSpread: number }) {
  const detail = QUALITY[quality];
  const curve = useMemo(() => makeOrbitCurve(orbit, detail.pathSamples, orbitSpread), [orbit, detail.pathSamples, orbitSpread]);
  const material = useMemo(() => createOrbitMaterial(orbit), [orbit]);
  const foregroundMaterial = useMemo(
    () => orbit.foreground && quality === "hero" ? createOrbitMaterial(orbit, true) : null,
    [orbit, quality]
  );
  useEffect(() => () => material.dispose(), [material]);
  useEffect(() => () => foregroundMaterial?.dispose(), [foregroundMaterial]);

  return (
    <group name={`OrbitArc_${orbit.id}`}>
      {orbit.glow && (
        <mesh renderOrder={1}>
          <tubeGeometry args={[curve, detail.orbitSegments, DESIGN.glowRadius, detail.tubeSides, true]} />
          <meshBasicMaterial color="#2ab8ff" transparent opacity={0.044} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>
      )}
      <mesh material={material} renderOrder={2}>
        <tubeGeometry args={[curve, detail.orbitSegments, Math.max(orbit.width * DESIGN.pathScale * 0.29, 0.0011), detail.tubeSides, true]} />
      </mesh>
      {foregroundMaterial && (
        <mesh material={foregroundMaterial} renderOrder={3}>
          <tubeGeometry args={[curve, detail.orbitSegments, Math.max(orbit.width * DESIGN.pathScale * 0.34, 0.0014), detail.tubeSides, true]} />
        </mesh>
      )}
    </group>
  );
}

function ParticleField({ quality, orbitSpread }: { quality: VisualProps["quality"]; orbitSpread: number }) {
  const count = QUALITY[quality].particles;
  const geometry = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const nodes: readonly { orbitId: string; progress: number; color: string }[] = [
      { orbitId: "A", progress: 0.08, color: "#e8faff" },
      { orbitId: "A", progress: 0.56, color: "#62caff" },
      { orbitId: "B", progress: 0.22, color: "#5dd8c9" },
      { orbitId: "C", progress: 0.16, color: "#b5cbff" },
      { orbitId: "C", progress: 0.72, color: "#7edcff" },
      { orbitId: "D", progress: 0.61, color: "#e2b06f" },
      { orbitId: "G", progress: 0.43, color: "#effcff" },
      { orbitId: "H", progress: 0.81, color: "#58d0bd" }
    ];
    const curves = new Map(ORBITS.map((orbit) => [orbit.id, makeOrbitCurve(orbit, QUALITY[quality].pathSamples, orbitSpread)]));

    nodes.filter((_, index) => quality === "hero" || index % 2 === 0).forEach((node, index) => {
      const position = curves.get(node.orbitId)?.getPointAt(node.progress);
      if (!position) return;
      positions[index * 3] = position.x;
      positions[index * 3 + 1] = position.y;
      positions[index * 3 + 2] = position.z + 0.002;
      const color = new THREE.Color(node.color);
      colors[index * 3] = color.r;
      colors[index * 3 + 1] = color.g;
      colors[index * 3 + 2] = color.b;
    });

    const result = new THREE.BufferGeometry();
    result.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    result.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    return result;
  }, [count, quality, orbitSpread]);
  useEffect(() => () => geometry.dispose(), [geometry]);

  return (
    <group name="ParticleField" renderOrder={4}>
      <points geometry={geometry}>
        <pointsMaterial
          vertexColors
          size={DESIGN.particlePixelSize * 3.2}
          sizeAttenuation={false}
          transparent
          opacity={0.15}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
      </points>
      <points geometry={geometry}>
        <pointsMaterial
          vertexColors
          size={DESIGN.particlePixelSize * 1.25}
          sizeAttenuation={false}
          transparent
          opacity={0.98}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
      </points>
    </group>
  );
}

function OrbitPackets({ quality, time, reducedMotion, orbitSpread }: VisualProps & { reducedMotion: boolean; orbitSpread: number }) {
  const detail = QUALITY[quality];
  const instances = useRef<THREE.InstancedMesh>(null);
  const initialized = useRef(false);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const axis = useMemo(() => new THREE.Vector3(1, 0, 0), []);
  const position = useMemo(() => new THREE.Vector3(), []);
  const tangent = useMemo(() => new THREE.Vector3(), []);
  const curves = useMemo(() => new Map(ORBITS.map((orbit) => [orbit.id, makeOrbitCurve(orbit, detail.pathSamples, orbitSpread)])), [detail.pathSamples, orbitSpread]);
  const markerColors = useMemo(() => [
    new THREE.Color("#effcff"),
    new THREE.Color("#a7e7ff"),
    new THREE.Color("#62bfe9"),
    new THREE.Color("#317da9")
  ], []);

  useFrame(() => {
    const mesh = instances.current;
    if (!mesh || (reducedMotion && initialized.current)) return;

    PACKETS.slice(0, detail.packets).forEach((packet, packetIndex) => {
      const curve = curves.get(packet.orbitId);
      if (!curve) return;
      const progress = THREE.MathUtils.euclideanModulo(
        (time.value + packet.initialElapsed) / packet.duration,
        1
      );
      for (let trailIndex = 0; trailIndex < detail.trailLength; trailIndex += 1) {
        const instanceIndex = packetIndex * detail.trailLength + trailIndex;
        const trailProgress = THREE.MathUtils.euclideanModulo(progress - trailIndex * 0.0045, 1);
        curve.getPointAt(trailProgress, position);
        curve.getTangentAt(trailProgress, tangent).normalize();
        dummy.position.copy(position);
        dummy.quaternion.setFromUnitVectors(axis, tangent);
        const head = trailIndex === 0;
        const width = head ? 0.036 : 0.019 - trailIndex * 0.003;
        const thickness = head ? 0.0044 : 0.0029 - trailIndex * 0.00035;
        dummy.scale.set(width, thickness, thickness);
        dummy.updateMatrix();
        mesh.setMatrixAt(instanceIndex, dummy.matrix);
        if (!initialized.current) mesh.setColorAt(instanceIndex, markerColors[trailIndex]);
      }
    });

    mesh.instanceMatrix.needsUpdate = true;
    if (!initialized.current && mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    // Packet positions span every orbit, rather than the unit source sphere.
    if (!initialized.current) mesh.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 2.5 * orbitSpread);
    initialized.current = true;
  });

  return (
    <instancedMesh ref={instances} name="OrbitPackets" args={[undefined, undefined, detail.packets * detail.trailLength]} renderOrder={5}>
      <sphereGeometry args={[1, quality === "hero" ? 12 : 6, quality === "hero" ? 8 : 4]} />
      <meshBasicMaterial
        color="#dffaff"
        toneMapped={false}
        transparent
        opacity={0.94}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </instancedMesh>
  );
}

export function SelfCore({ scale = 1, showParticles = true, quality = "hero", reducedMotion = false, orbitSpread = 1, highlighted = false }: SelfCoreProps) {
  const time = useMemo(() => ({ value: 0 }), []);
  useFrame((_, delta) => {
    if (!reducedMotion) time.value += Math.min(delta, 0.1);
  });
  return (
    <group name="SelfCoreRoot" scale={scale}>
      <Halo highlighted={highlighted} reducedMotion={reducedMotion} />
      <Corona quality={quality} time={time} />
      <InnerEnergyShell quality={quality} time={time} />
      {ORBITS.map((orbit) => <OrbitArc key={orbit.id} orbit={orbit} quality={quality} orbitSpread={orbitSpread} />)}
      {showParticles && <ParticleField quality={quality} orbitSpread={orbitSpread} />}
      <OrbitPackets key={`${quality}-${orbitSpread}`} quality={quality} time={time} reducedMotion={reducedMotion} orbitSpread={orbitSpread} />
      <CoreSphere quality={quality} time={time} />
    </group>
  );
}
