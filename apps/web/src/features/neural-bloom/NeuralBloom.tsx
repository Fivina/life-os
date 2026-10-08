import { useMemo } from "react";
import {
  AdditiveBlending,
  BufferGeometry,
  CatmullRomCurve3,
  Color,
  Float32BufferAttribute,
  TubeGeometry,
  Vector3
} from "three";

export type NeuralBloomMode = "hero" | "miniature";
export type NeuralBloomComplexity = "minimal" | "balanced" | "full";

export type NeuralBloomProps = {
  mode?: NeuralBloomMode;
  shellOpacity?: number;
  shellRoughness?: number;
  branchEmission?: number;
  branchThickness?: number;
  coreEmission?: number;
  nodeSize?: number;
  nodeEmission?: number;
  branchComplexity?: NeuralBloomComplexity;
  attention?: boolean;
};

type Point = [number, number, number];
type BranchSegment = {
  id: string;
  points: Vector3[];
  kind: "major" | "secondary" | "filament";
  terminalId?: string;
};
type MajorBranch = { id: string; segments: BranchSegment[] };
type BloomNode = { id: string; position: Vector3; kind: "terminal" | "junction" };

const origin = new Vector3(-0.2, -0.19, 0.025);

const branchProfiles: Array<{ id: string; direction: Point }> = [
  { id: "A", direction: [-0.96, 0.16, 0.2] },
  { id: "B", direction: [-0.63, 0.68, -0.3] },
  { id: "C", direction: [-0.12, 0.94, 0.31] },
  { id: "D", direction: [0.67, 0.69, -0.27] },
  { id: "E", direction: [0.97, 0.18, 0.38] },
  { id: "F", direction: [0.58, -0.67, 0.47] },
  { id: "G", direction: [-0.37, -0.87, -0.25] }
];

const fromPoint = (point: Point) => new Vector3(...point);

function radialPoint(direction: Point, radius = 0.91) {
  return fromPoint(direction).normalize().multiplyScalar(Math.min(radius, 1.34));
}

function makeCurve(points: Vector3[]): CatmullRomCurve3 {
  return new CatmullRomCurve3(points, false, "centripetal", 0.45);
}

function pointFromVector(vector: Vector3): Point {
  return [vector.x, vector.y, vector.z];
}

function growPath(start: Vector3, goal: Vector3, phase: number, curl: number, stepSize: number, maxRadius = 1.12) {
  const chord = goal.clone().sub(start);
  const planarLength = Math.hypot(chord.x, chord.y);
  const startAngle = Math.atan2(chord.y, chord.x);
  const steps = Math.max(16, Math.ceil(chord.length() / stepSize));
  const points: Vector3[] = [];

  for (let step = 0; step <= steps; step += 1) {
    const t = step / steps;
    const envelope = Math.sin(Math.PI * t);
    const angle = startAngle + curl * 0.72 * envelope
      + Math.sin(t * Math.PI * 2 + phase) * 0.045 * envelope;
    const radius = planarLength * t;
    const depthRipple = Math.sin(Math.PI * 2 * t + phase) * envelope * 0.065;
    const point = new Vector3(
      start.x + Math.cos(angle) * radius,
      start.y + Math.sin(angle) * radius,
      start.z + chord.z * t + depthRipple
    );
    if (point.length() > maxRadius) point.setLength(maxRadius);
    points.push(point);
  }

  return points;
}

function taperedTube(curve: CatmullRomCurve3, segments: number, radius: number, radialSegments: number, tipScale: number) {
  const geometry = new TubeGeometry(curve, segments, radius, radialSegments, false);
  const positions = geometry.getAttribute("position");
  const ringSize = radialSegments + 1;
  const offset = new Vector3();
  const center = new Vector3();

  for (let ring = 0; ring <= segments; ring += 1) {
    const t = ring / segments;
    curve.getPointAt(t, center);
    const taper = tipScale + (1 - tipScale) * Math.pow(1 - t, 0.72);

    for (let side = 0; side <= radialSegments; side += 1) {
      const vertex = ring * ringSize + side;
      offset.fromBufferAttribute(positions, vertex).sub(center).multiplyScalar(taper).add(center);
      positions.setXYZ(vertex, offset.x, offset.y, offset.z);
    }
  }

  positions.needsUpdate = true;
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
  return geometry;
}

function createBranchNetwork(complexity: NeuralBloomComplexity) {
  const branches: MajorBranch[] = [];
  const nodes: BloomNode[] = [];

  branchProfiles.forEach((profile, index) => {
    const rootAngle = index * 2.399;
    const root = origin.clone().add(fromPoint([Math.cos(rootAngle) * 0.024, Math.sin(rootAngle) * 0.024, Math.sin(rootAngle * 1.7) * 0.018]));
    const mainDirection = fromPoint(profile.direction).normalize();
    const lateral = new Vector3(-mainDirection.y, mainDirection.x, 0).normalize();
    if (lateral.lengthSq() < 0.01) lateral.set(1, 0, 0);
    const depth = new Vector3(0, 0, 1);
    const phase = index * 1.731 + 0.4;
    const curlByBranch = [0.98, 0.82, 1.05, 0.76, 0.9, 1.0, 0.78];
    const curl = curlByBranch[index] ?? 0.4;
    const primaryReach = [1.27, 1.18, 1.32, 1.15, 1.26, 1.19, 1.22][index];
    const destination = radialPoint(profile.direction, primaryReach);
    const primaryPoints = growPath(root, destination, phase, curl, 0.056, 1.34);
    const primaryCurve = makeCurve(primaryPoints);
    const segments: BranchSegment[] = [
      { id: `${profile.id}_trunk`, points: primaryPoints, kind: "major", terminalId: `Tip_${profile.id}` }
    ];
    nodes.push({ id: `Tip_${profile.id}`, position: destination, kind: "terminal" });

    if (complexity === "full") {
      const bloomSites: Record<number, number> = { 1: 0.72, 2: 0.68, 4: 0.74, 5: 0.7 };
      const bloomT = bloomSites[index];
      if (bloomT !== undefined) {
        const center = primaryCurve.getPoint(bloomT);
        const tangent = primaryCurve.getTangent(bloomT).normalize();
        const outward = center.clone().normalize();
        const side = new Vector3().crossVectors(outward, tangent).normalize();
        if (side.lengthSq() < 0.01) side.copy(lateral);
        const bloomDepth = new Vector3().crossVectors(tangent, side).normalize();
        nodes.push({ id: `BloomHead_${profile.id}`, position: center, kind: "junction" });

        [-1.5, -0.42, 0.52, 1.55].forEach((spread, rayIndex) => {
          const rayDirection = tangent.clone()
            .addScaledVector(side, spread)
            .addScaledVector(outward, 0.42)
            .addScaledVector(bloomDepth, (rayIndex - 1) * 0.14)
            .normalize();
          const rayEnd = center.clone().addScaledVector(rayDirection, 0.3 + (rayIndex % 2) * 0.07);
          if (rayEnd.length() < 1.1) rayEnd.setLength(1.1);
          const rayPoints = growPath(center, rayEnd, phase + rayIndex * 0.83, curl * 0.22, 0.032, 1.16);
          segments.push({ id: `BloomHead_${profile.id}_ray_${rayIndex + 1}`, points: rayPoints, kind: "secondary", terminalId: `BloomHead_${profile.id}_tip_${rayIndex + 1}` });
          nodes.push({ id: `BloomHead_${profile.id}_tip_${rayIndex + 1}`, position: rayEnd, kind: "terminal" });
        });
      }
    }

    if (complexity !== "minimal") {
      const forkCount = complexity === "balanced" ? 1 : [3, 4, 2, 4, 2, 3, 2][index];
      const twigCount = [2, 3, 1, 3, 1, 2, 1][index];
      for (let forkIndex = 0; forkIndex < forkCount; forkIndex += 1) {
        const sign = (index + forkIndex) % 2 === 0 ? -1 : 1;
        const t = 0.3 + forkIndex * 0.2 + (index % 2) * 0.04;
        const start = primaryCurve.getPoint(t);
        const parentTangent = primaryCurve.getTangent(t).normalize();
        const branchSide = new Vector3(-parentTangent.y, parentTangent.x, 0).normalize();
        if (branchSide.lengthSq() < 0.01) branchSide.copy(lateral);
        const outward = start.clone().sub(origin).normalize();
        const forkDirection = parentTangent.clone()
          .addScaledVector(branchSide, sign * (0.5 + forkIndex * 0.08))
          .addScaledVector(outward, 0.24)
          .addScaledVector(depth, ((index + forkIndex) % 3 - 1) * 0.22)
          .normalize();
        const secondaryReach = forkIndex % 2 === 0 ? 1.09 : 0.96;
        const end = radialPoint(pointFromVector(forkDirection), secondaryReach);
        const points = growPath(start, end, phase + (forkIndex + 1) * 1.19, curl * (0.3 + forkIndex * 0.08), 0.052, 1.18);
        const forkCurve = makeCurve(points);
        const terminalId = `Tip_${profile.id}_${forkIndex + 1}`;
        segments.push({ id: `${profile.id}_fork_${forkIndex + 1}`, points, kind: "secondary", terminalId });
        nodes.push({ id: terminalId, position: end, kind: "terminal" });

        if (complexity === "full" && forkIndex < twigCount) {
          const twigT = forkIndex === 0 ? 0.58 : 0.66;
          const twigStart = forkCurve.getPoint(twigT);
          const twigTangent = forkCurve.getTangent(twigT).normalize();
          const twigSide = new Vector3(-twigTangent.y, twigTangent.x, 0).normalize();
          if (twigSide.lengthSq() < 0.01) twigSide.copy(branchSide);
          const twigDirection = twigTangent.clone()
            .addScaledVector(twigSide, sign * (forkIndex === 0 ? 0.48 : -0.42))
            .addScaledVector(twigStart.clone().sub(origin).normalize(), 0.3)
            .addScaledVector(depth, index % 2 === 0 ? -0.25 : 0.3)
            .normalize();
          const twigEnd = radialPoint(pointFromVector(twigDirection), 0.89);
          const twigPoints = growPath(twigStart, twigEnd, phase - 1.4 + forkIndex * 0.9, curl * 0.24, 0.047, 1.0);
          const twigId = `Tip_${profile.id}_twig_${forkIndex + 1}`;
          segments.push({ id: `${profile.id}_twig_${forkIndex + 1}`, points: twigPoints, kind: "filament", terminalId: twigId });
          nodes.push({ id: twigId, position: twigEnd, kind: "terminal" });
        }

        if (complexity === "full" && forkIndex < 2) {
          nodes.push({ id: `Junction_${profile.id}_${forkIndex + 1}`, position: start, kind: "junction" });
        }
      }

      if (complexity === "full") {
        [0, 1].forEach((filamentIndex) => {
          const t = filamentIndex === 0 ? 0.31 : 0.56;
          const start = primaryCurve.getPoint(t);
          const sign = (index + filamentIndex) % 2 === 0 ? 1 : -1;
          const tangent = primaryCurve.getTangent(t).normalize();
          const side = new Vector3(-tangent.y, tangent.x, 0).normalize();
          if (side.lengthSq() < 0.01) side.copy(lateral);
          const direction = tangent.clone()
            .addScaledVector(side, sign * (0.62 + filamentIndex * 0.08))
            .addScaledVector(start.clone().sub(origin).normalize(), 0.28)
            .addScaledVector(depth, sign * (filamentIndex === 0 ? 0.28 : -0.34))
            .normalize();
          const end = radialPoint(pointFromVector(direction), filamentIndex === 0 ? 0.76 : 0.88);
          const points = growPath(start, end, phase + filamentIndex * 2.7, curl * 0.32 * sign, 0.045, 0.92);
          const nodeId = `Inner_${profile.id}_${filamentIndex + 1}`;
          segments.push({ id: `${profile.id}_filament_${filamentIndex + 1}`, points, kind: "filament", terminalId: nodeId });
          nodes.push({ id: nodeId, position: end, kind: "terminal" });
        });

      }
    }

    branches.push({ id: profile.id, segments });
  });

  if (complexity === "full" && branches[0]) {
    const innerReach = [0.34, 0.57, 0.68, 0.42, 0.75, 0.47, 0.36, 0.62, 0.33, 0.72, 0.51];
    const innerAngles = [-0.36, 0.12, 0.42, 1.34, 1.78, 2.56, 3.12, 3.68, 4.55, 5.08, 5.72];
    innerAngles.forEach((angle, index) => {
      const depth = Math.sin(index * 1.61) * 0.22;
      const end = new Vector3(
        origin.x + Math.cos(angle) * innerReach[index],
        origin.y + Math.sin(angle) * innerReach[index],
        origin.z + depth
      );
      const start = origin.clone().add(new Vector3(Math.cos(angle) * 0.016, Math.sin(angle) * 0.016, 0));
      const points = growPath(start, end, index * 0.91 + 0.4, 0.92 + (index % 4) * 0.14, 0.032, 0.82);
      branches[0].segments.push({ id: `BloomCore_Ray_${index + 1}`, points, kind: "secondary" });
      if (index % 2 === 0) nodes.push({ id: `BloomCore_Tip_${index + 1}`, position: end, kind: "terminal" });
    });
  }

  return { branches, nodes };
}

function Tube({
  segment,
  thickness,
  emission
}: {
  segment: BranchSegment;
  thickness: number;
  emission: number;
}) {
  const curve = useMemo(() => makeCurve(segment.points), [segment.points]);
  const tipScale = segment.kind === "major" ? 0.2 : segment.kind === "secondary" ? 0.11 : 0.08;
  const geometry = useMemo(
    () => taperedTube(curve, segment.kind === "major" ? 48 : segment.kind === "secondary" ? 32 : 24, thickness, segment.kind === "major" ? 7 : 5, tipScale),
    [curve, segment.kind, thickness, tipScale]
  );
  const glowGeometry = useMemo(
    () => taperedTube(curve, segment.kind === "major" ? 48 : segment.kind === "secondary" ? 32 : 24, thickness * 2.8, segment.kind === "major" ? 7 : 5, tipScale),
    [curve, segment.kind, thickness, tipScale]
  );
  const isMajor = segment.kind === "major";
  const isFilament = segment.kind === "filament";
  const averageDepth = useMemo(
    () => segment.points.reduce((sum, point) => sum + point.z, 0) / segment.points.length,
    [segment.points]
  );
  const depthCue = 0.56 + Math.max(0, Math.min(1, (averageDepth + 1) * 0.5)) * 0.44;
  const color = isMajor ? "#ead7ff" : isFilament ? "#b28aff" : "#cfadff";
  const glowColor = isMajor ? "#a778ff" : isFilament ? "#8053de" : "#9468f4";
  const coreOpacity = Math.min(1, (isMajor ? 0.92 : isFilament ? 0.48 : 0.57) * emission * depthCue);

  return (
    <group name={segment.id}>
      <mesh geometry={glowGeometry} renderOrder={1}>
        <meshBasicMaterial
          color={glowColor}
          transparent
          opacity={Math.min(0.24, (isMajor ? 0.2 : isFilament ? 0.075 : 0.11) * emission * depthCue)}
          blending={AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
      <mesh geometry={geometry} renderOrder={2}>
        <meshBasicMaterial
          color={color}
          transparent
          opacity={coreOpacity}
          blending={AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}

function BloomNodeMesh({
  node,
  mode,
  nodeSize,
  emission,
  attention
}: {
  node: BloomNode;
  mode: NeuralBloomMode;
  nodeSize: number;
  emission: number;
  attention: boolean;
}) {
  if (mode === "miniature" && node.kind === "junction") return null;

  const isAttentionNode = attention && (node.id === "Tip_B" || node.id === "Tip_F");
  const isInnerNode = node.id.startsWith("Inner_");
  const isBloom = node.id.startsWith("BloomHead_");
  const isJunction = node.kind === "junction";
  const radius = isBloom ? nodeSize * 1.08 : isJunction ? nodeSize * 0.82 : isInnerNode ? nodeSize * 0.42 : nodeSize;
  const color = isAttentionNode ? "#ff4d57" : isBloom ? "#f1e2ff" : node.kind === "junction" ? "#d8bdff" : "#f3e6ff";
  const haloColor = isAttentionNode ? "#ff4d57" : isBloom ? "#b27aff" : "#b27aff";
  const depthCue = 0.56 + Math.max(0, Math.min(1, (node.position.z + 1) * 0.5)) * 0.44;

  return (
    <group name={node.id} position={node.position}>
      <mesh scale={isBloom ? 1.45 : isJunction ? 1.5 : 1.4} renderOrder={3}>
        <sphereGeometry args={[radius, 12, 10]} />
        <meshBasicMaterial
          color={haloColor}
          transparent
          opacity={Math.min(0.24, (isAttentionNode ? 0.2 : isBloom ? 0.12 : isJunction ? 0.17 : 0.11) * emission * depthCue)}
          blending={AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
      <mesh renderOrder={4}>
        <sphereGeometry args={[radius, 16, 12]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={Math.min(1, 0.94 * emission * depthCue)}
          blending={AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}

function BloomCore({ size, emission }: { size: number; emission: number }) {
  return (
    <group name="BloomCore" position={origin}>
      <mesh scale={3.8} renderOrder={3}>
        <sphereGeometry args={[size, 24, 18]} />
        <meshBasicMaterial
          color="#8f50f4"
          transparent
          opacity={Math.min(0.12, 0.085 * emission)}
          blending={AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
      <mesh scale={1.48} renderOrder={4}>
        <sphereGeometry args={[size, 24, 18]} />
        <meshBasicMaterial
          color="#e9d5ff"
          transparent
          opacity={Math.min(0.3, 0.26 * emission)}
          blending={AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
      <mesh renderOrder={5}>
        <sphereGeometry args={[size * 0.58, 20, 16]} />
        <meshBasicMaterial color="#fff8ff" toneMapped={false} />
      </mesh>
    </group>
  );
}

function createSparkGeometry(count: number, branches: MajorBranch[]) {
  const geometry = new BufferGeometry();
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const opacities = new Float32Array(count);
  const low = new Color("#7852c7");
  const mid = new Color("#b98eff");
  const high = new Color("#f0dfff");
  const networkCurves = branches.flatMap((branch) => branch.segments.map((segment) => makeCurve(segment.points)));
  let seed = 581_031;
  const random = () => {
    seed = (seed * 1_664_525 + 1_013_904_223) >>> 0;
    return seed / 4_294_967_296;
  };

  for (let index = 0; index < count; index += 1) {
    const offset = index * 3;
    let position: Vector3;
    if (networkCurves.length > 0 && random() < 0.34) {
      position = networkCurves[Math.floor(random() * networkCurves.length)].getPoint(0.12 + random() * 0.88);
      position.add(new Vector3((random() - 0.5) * 0.12, (random() - 0.5) * 0.12, (random() - 0.5) * 0.12));
      if (position.length() > 0.96) position.setLength(0.96);
    } else {
      const z = random() * 2 - 1;
      const angle = random() * Math.PI * 2;
      const planar = Math.sqrt(1 - z * z);
      const radius = 0.1 + Math.pow(random(), 1.25) * 0.82;
      position = new Vector3(
        origin.x + Math.cos(angle) * planar * radius,
        origin.y + Math.sin(angle) * planar * radius,
        z * radius
      );
      if (position.length() > 0.97) position.setLength(0.97);
    }
    positions[offset] = position.x;
    positions[offset + 1] = position.y;
    positions[offset + 2] = position.z;

    const tint = random();
    const color = tint < 0.7
      ? low.clone().lerp(mid, tint / 0.7)
      : mid.clone().lerp(high, (tint - 0.7) / 0.3);
    colors[offset] = color.r;
    colors[offset + 1] = color.g;
    colors[offset + 2] = color.b;
    sizes[index] = 0.026 + random() * 0.036;
    opacities[index] = 0.22 + random() * 0.46;
  }

  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.setAttribute("aColor", new Float32BufferAttribute(colors, 3));
  geometry.setAttribute("aSize", new Float32BufferAttribute(sizes, 1));
  geometry.setAttribute("aOpacity", new Float32BufferAttribute(opacities, 1));
  geometry.computeBoundingSphere();
  return geometry;
}

function SparkField({ mode, emission, branches }: { mode: NeuralBloomMode; emission: number; branches: MajorBranch[] }) {
  const geometry = useMemo(
    () => createSparkGeometry(mode === "miniature" ? 92 : 2300, branches),
    [mode, branches]
  );

  return (
    <points name="BloomInternalSparks" geometry={geometry} frustumCulled={false} renderOrder={0}>
      <shaderMaterial
        vertexShader={sparkVertexShader}
        fragmentShader={sparkFragmentShader}
        transparent
        blending={AdditiveBlending}
        depthWrite={false}
        toneMapped={false}
        uniforms={{ uEmission: { value: emission } }}
      />
    </points>
  );
}

const sparkVertexShader = `
  attribute vec3 aColor;
  attribute float aSize;
  attribute float aOpacity;
  uniform float uEmission;
  varying vec3 vColor;
  varying float vOpacity;
  void main() {
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mvPosition;
    gl_PointSize = clamp(aSize * (240.0 / max(1.0, -mvPosition.z)), 0.68, 4.2);
    vColor = aColor;
    vOpacity = aOpacity * uEmission;
  }
`;

const sparkFragmentShader = `
  varying vec3 vColor;
  varying float vOpacity;
  void main() {
    float distanceFromCenter = length(gl_PointCoord - vec2(0.5)) * 2.0;
    float softCore = exp(-distanceFromCenter * distanceFromCenter * 5.0);
    float edge = 1.0 - smoothstep(0.52, 1.0, distanceFromCenter);
    gl_FragColor = vec4(vColor, vOpacity * softCore * edge);
    #include <colorspace_fragment>
  }
`;

function BloomScattering({ emission }: { emission: number }) {
  return (
    <mesh name="BloomScattering" renderOrder={0}>
      <sphereGeometry args={[0.968, 48, 36]} />
      <shaderMaterial
        vertexShader={scatterVertexShader}
        fragmentShader={scatterFragmentShader}
        transparent
        blending={AdditiveBlending}
        depthWrite={false}
        toneMapped={false}
        uniforms={{
          uEmission: { value: emission },
          uOrigin: { value: new Vector3(origin.x, origin.y, 0) }
        }}
      />
    </mesh>
  );
}

const scatterVertexShader = `
  varying vec3 vLocalPosition;
  void main() {
    vLocalPosition = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const scatterFragmentShader = `
  uniform float uEmission;
  uniform vec3 uOrigin;
  varying vec3 vLocalPosition;
  void main() {
    float sourceDistance = length(vLocalPosition.xy - uOrigin.xy);
    float sourceGlow = exp(-sourceDistance * sourceDistance * 15.0);
    float innerHaze = exp(-sourceDistance * sourceDistance * 4.1);
    vec3 hazeColor = mix(vec3(0.2, 0.09, 0.48), vec3(0.72, 0.48, 1.0), sourceGlow * 0.74 + innerHaze * 0.26);
    float hazeOpacity = (0.02 + innerHaze * 0.055 + sourceGlow * 0.14) * uEmission;
    gl_FragColor = vec4(hazeColor, hazeOpacity);
    #include <colorspace_fragment>
  }
`;

function OuterShell({ opacity, roughness }: { opacity: number; roughness: number }) {
  const uniforms = useMemo(
    () => ({
      uOpacity: { value: opacity },
      uRoughness: { value: roughness },
      uBaseColor: { value: new Color("#170d2b") },
      uEdgeColor: { value: new Color("#c19aff") }
    }),
    [opacity, roughness]
  );

  return (
    <mesh name="OuterShell" renderOrder={6}>
      <sphereGeometry args={[1, 64, 48]} />
      <shaderMaterial
        uniforms={uniforms}
        vertexShader={shellVertexShader}
        fragmentShader={shellFragmentShader}
        transparent
        depthWrite={false}
        toneMapped={false}
      />
    </mesh>
  );
}

const shellVertexShader = `
  varying vec3 vNormal;
  varying vec3 vViewPosition;
  varying vec3 vLocalPosition;
  void main() {
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vViewPosition = normalize(-mvPosition.xyz);
    vLocalPosition = position;
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const shellFragmentShader = `
  uniform float uOpacity;
  uniform float uRoughness;
  uniform vec3 uBaseColor;
  uniform vec3 uEdgeColor;
  varying vec3 vNormal;
  varying vec3 vViewPosition;
  varying vec3 vLocalPosition;
  void main() {
    float facing = max(dot(normalize(vNormal), normalize(vViewPosition)), 0.0);
    float exponent = mix(4.2, 1.7, clamp(uRoughness, 0.0, 1.0));
    float rim = pow(1.0 - facing, exponent);
    float glassGlint = pow(1.0 - facing, 12.0);
    float striation = sin(vLocalPosition.x * 12.0 + sin(vLocalPosition.z * 8.0)) * sin(vLocalPosition.y * 11.0 + vLocalPosition.z * 5.0);
    float grain = fract(sin(dot(floor(vLocalPosition * 190.0), vec3(12.9898, 78.233, 37.719))) * 43758.5453);
    float glint = smoothstep(0.978, 0.999, grain) * (1.0 - rim);
    float mineralShade = 0.035 + 0.065 * (1.0 - abs(normalize(vNormal).y)) + striation * 0.035;
    vec3 shellColor = mix(uBaseColor, uEdgeColor, clamp(rim * 1.5 + mineralShade, 0.0, 1.0));
    shellColor += uEdgeColor * glint * 0.22;
    shellColor += uEdgeColor * glassGlint * 0.62;
    float alpha = clamp(uOpacity * (0.08 + rim * 0.85) + glassGlint * 0.18 + glint * 0.014, 0.0, 0.46);
    gl_FragColor = vec4(shellColor, alpha);
  }
`;

export function NeuralBloom({
  mode = "hero",
  shellOpacity = 0.22,
  shellRoughness = 0.36,
  branchEmission = 1,
  branchThickness,
  coreEmission = 1,
  nodeSize,
  nodeEmission = 1,
  branchComplexity,
  attention = false
}: NeuralBloomProps) {
  const complexity = branchComplexity ?? (mode === "miniature" ? "balanced" : "full");
  const resolvedThickness = branchThickness ?? (mode === "miniature" ? 0.014 : 0.0115);
  const resolvedNodeSize = nodeSize ?? (mode === "miniature" ? 0.026 : 0.019);
  const coreSize = mode === "miniature" ? 0.061 : 0.074;
  const { branches, nodes } = useMemo(() => createBranchNetwork(complexity), [complexity]);

  return (
    <group name="LearningRoot">
      {branches.map((branch) => (
        <group key={branch.id} name={`MajorBranch_${branch.id}`}>
          {branch.segments.map((segment) => (
            <Tube
              key={segment.id}
              segment={segment}
              thickness={resolvedThickness * (segment.kind === "secondary" ? 0.64 : segment.kind === "filament" ? 0.55 : 1)}
              emission={branchEmission * (segment.kind === "secondary" ? 0.76 : segment.kind === "filament" ? 0.8 : 1)}
            />
          ))}
        </group>
      ))}
      <BloomScattering emission={coreEmission} />
      <SparkField mode={mode} emission={coreEmission} branches={branches} />
      <BloomCore size={coreSize} emission={coreEmission} />
      <group name="TerminalNodes">
        {nodes.map((node) => (
          <BloomNodeMesh
            key={node.id}
            node={node}
            mode={mode}
            nodeSize={resolvedNodeSize}
            emission={nodeEmission}
            attention={attention}
          />
        ))}
      </group>
      <OuterShell opacity={shellOpacity} roughness={shellRoughness} />
    </group>
  );
}

