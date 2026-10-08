import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";

export type SupplyCorePlateState = "normal" | "healthy" | "scheduled" | "warning" | "attention";

export type SupplyCorePlateLayout = {
  plateCount: number;
  seed?: number;
  jitter?: number;
  cornerRadius?: number;
};

export type SupplyCoreColors = {
  plate: string;
  core: string;
  orbit: string;
};

export type SupplyCoreProps = {
  radius?: number;
  plateLayout?: SupplyCorePlateLayout;
  plateGap?: number;
  plateExtrusion?: number;
  defaultColors?: Partial<SupplyCoreColors>;
  plateStates?: Record<string, SupplyCorePlateState>;
  emission?: number;
  roughness?: number;
  showOrbit?: boolean;
  showDetails?: boolean;
  showIcons?: boolean;
};

export const DEFAULT_SUPPLY_CORE_LAYOUT: SupplyCorePlateLayout = {
  plateCount: 54,
  seed: 328,
  jitter: 0.13,
  cornerRadius: 0.25
};

const DEFAULT_COLORS: SupplyCoreColors = {
  plate: "#ad8457",
  core: "#24170d",
  orbit: "#ffc66e"
};

const STATE_COLORS: Record<Exclude<SupplyCorePlateState, "normal">, string> = {
  healthy: "#688951",
  scheduled: "#66869b",
  warning: "#d49b42",
  attention: "#ff4d57"
};

const plateToneOffsets = [0.035, -0.015, 0.012, -0.055, 0.048, -0.03, 0.022];
type PanelIcon = "home" | "leaf" | "cart" | "check" | "bars";

const iconStrokes: Record<PanelIcon, number[][][]> = {
  home: [
    [[-0.9, 0.05], [0, 0.9], [0.9, 0.05]],
    [[-0.63, 0.12], [-0.63, -0.77], [0.63, -0.77], [0.63, 0.12]],
    [[-0.17, -0.77], [-0.17, -0.24], [0.18, -0.24], [0.18, -0.77]]
  ],
  leaf: [
    [[0, -0.12], [-0.08, 0.36], [-0.48, 0.73], [-0.76, 0.67], [-0.69, 0.29], [-0.35, -0.01], [0, -0.12]],
    [[0, 0.08], [0.21, 0.49], [0.62, 0.72], [0.78, 0.65], [0.68, 0.29], [0.3, 0.06], [0, 0.08]],
    [[-0.58, -0.2], [-0.2, 0.18], [0.13, 0.48], [0.43, 0.72]]
  ],
  cart: [
    [[-0.82, 0.64], [-0.48, 0.64], [-0.22, -0.28], [0.78, -0.28], [0.53, 0.35], [-0.2, 0.35]],
    [[-0.14, 0.12], [0.62, 0.12]],
    [[-0.08, -0.45], [-0.23, -0.28]],
    [[-0.12, 0.69], [-0.08, 0.73], [-0.04, 0.69], [-0.08, 0.65], [-0.12, 0.69]],
    [[0.48, 0.69], [0.52, 0.73], [0.56, 0.69], [0.52, 0.65], [0.48, 0.69]]
  ],
  check: [
    [[-0.7, -0.62], [0.7, -0.62], [0.7, 0.62], [-0.7, 0.62], [-0.7, -0.62]],
    [[-0.42, -0.02], [-0.12, 0.32], [0.48, -0.38]]
  ],
  bars: [
    [[-0.38, -0.68], [-0.38, 0.68]],
    [[0.38, -0.68], [0.38, 0.68]],
    [[-0.53, -0.68], [-0.23, -0.68]],
    [[0.23, 0.68], [0.53, 0.68]]
  ],
};

function slerpDirection(start: THREE.Vector3, end: THREE.Vector3, amount: number) {
  const angle = start.angleTo(end);
  if (angle < 1e-6) return start.clone();
  const denominator = Math.sin(angle);
  return start.clone().multiplyScalar(Math.sin((1 - amount) * angle) / denominator)
    .addScaledVector(end, Math.sin(amount * angle) / denominator)
    .normalize();
}

function seededRandom(seed: number) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

type SupplyCell = {
  site: THREE.Vector3;
  vertices: THREE.Vector3[];
  cornerRatio: number;
  icon?: PanelIcon;
  iconColor?: string;
  accentColor?: string;
};

function sortCellVertices(site: THREE.Vector3, vertices: THREE.Vector3[]) {
  const reference = Math.abs(site.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
  const east = reference.clone().cross(site).normalize();
  const north = site.clone().cross(east).normalize();
  return vertices.sort((a, b) =>
    Math.atan2(a.dot(north), a.dot(east)) - Math.atan2(b.dot(north), b.dot(east))
  );
}

function createPlateCells(layout: SupplyCorePlateLayout) {
  const requestedCount = Math.max(24, Math.min(96, Math.floor(layout.plateCount)));
  const random = seededRandom(layout.seed ?? DEFAULT_SUPPLY_CORE_LAYOUT.seed!);
  const jitter = layout.jitter ?? DEFAULT_SUPPLY_CORE_LAYOUT.jitter!;
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const sites: THREE.Vector3[] = [];
  const tangentReference = new THREE.Vector3();
  const tangentA = new THREE.Vector3();
  const tangentB = new THREE.Vector3();

  for (let index = 0; index < requestedCount; index += 1) {
    const y = 1 - (2 * (index + 0.5)) / requestedCount;
    const ringRadius = Math.sqrt(1 - y * y);
    const angle = goldenAngle * index + (random() - 0.5) * 0.18;
    const site = new THREE.Vector3(Math.cos(angle) * ringRadius, y, Math.sin(angle) * ringRadius);
    tangentReference.set(Math.abs(site.y) < 0.9 ? 0 : 1, Math.abs(site.y) < 0.9 ? 1 : 0, 0);
    tangentA.crossVectors(tangentReference, site).normalize();
    tangentB.crossVectors(site, tangentA).normalize();
    site.addScaledVector(tangentA, (random() - 0.5) * jitter * 0.9)
      .addScaledVector(tangentB, (random() - 0.5) * jitter * 0.9)
      .normalize();
    sites.push(site);
  }

  const frontSiteIndex = sites.reduce((best, site, index) => site.z > sites[best].z ? index : best, 0);
  const alignToFront = new THREE.Quaternion().setFromUnitVectors(sites[frontSiteIndex], new THREE.Vector3(0, 0, 1));
  const frontRoll = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), (random() - 0.5) * 0.22);
  const orientLayout = frontRoll.multiply(alignToFront);
  sites.forEach((site) => site.applyQuaternion(orientLayout).normalize());

  const cells: SupplyCell[] = sites.map((site) => {
    const neighbors = sites
      .filter((candidate) => candidate !== site)
      .map((candidate) => ({ candidate, proximity: site.dot(candidate) }))
      .sort((a, b) => b.proximity - a.proximity)
      .slice(0, Math.min(18, requestedCount - 1));
    const vertices: THREE.Vector3[] = [];

    for (let first = 0; first < neighbors.length; first += 1) {
      const firstPlane = site.clone().sub(neighbors[first].candidate);
      for (let second = first + 1; second < neighbors.length; second += 1) {
        const secondPlane = site.clone().sub(neighbors[second].candidate);
        const intersection = firstPlane.clone().cross(secondPlane);
        if (intersection.lengthSq() < 1e-10) continue;
        intersection.normalize();

        for (const candidateVertex of [intersection, intersection.clone().negate()]) {
          const siteProximity = site.dot(candidateVertex);
          if (sites.some((other) => siteProximity + 1e-6 < other.dot(candidateVertex))) continue;
          if (vertices.some((vertex) => vertex.angleTo(candidateVertex) < 1e-4)) continue;
          vertices.push(candidateVertex.clone());
        }
      }
    }

    const orderedVertices = sortCellVertices(site, vertices);
    const cornerRatio = THREE.MathUtils.clamp(
      (layout.cornerRadius ?? DEFAULT_SUPPLY_CORE_LAYOUT.cornerRadius!) + (random() - 0.5) * 0.34,
      0.12,
      0.4
    );
    return { site, vertices: orderedVertices, cornerRatio };
  });

  const iconPlacements: { icon: PanelIcon; color: string; accent?: string; target: THREE.Vector3 }[] = [
    { icon: "home", color: "#f5d89d", target: new THREE.Vector3(0, 0, 1) },
    { icon: "leaf", color: "#d7e5a1", accent: "#747a43", target: new THREE.Vector3(0, 0.54, 0.84).normalize() },
    { icon: "cart", color: "#c4e2ee", accent: "#687c88", target: new THREE.Vector3(0.54, 0, 0.84).normalize() },
    { icon: "check", color: "#ecd7ad", target: new THREE.Vector3(0.38, -0.42, 0.82).normalize() },
    { icon: "bars", color: "#e9c883", target: new THREE.Vector3(-0.04, -0.55, 0.82).normalize() }
  ];
  const assigned = new Set<SupplyCell>();
  for (const placement of iconPlacements) {
    const cell = cells
      .filter((candidate) => !assigned.has(candidate) && candidate.site.z > 0.12)
      .reduce<SupplyCell | undefined>((best, candidate) =>
        !best || candidate.site.dot(placement.target) > best.site.dot(placement.target) ? candidate : best,
      undefined);
    if (!cell) continue;
    cell.icon = placement.icon;
    cell.iconColor = placement.color;
    cell.accentColor = placement.accent;
    assigned.add(cell);
  }

  return cells.sort((a, b) => b.site.z - a.site.z);
}

function roundedCellBoundary(site: THREE.Vector3, vertices: THREE.Vector3[], cornerRatio: number) {
  const startPoints = vertices.map((vertex, index) => slerpDirection(vertex, vertices[(index + vertices.length - 1) % vertices.length], cornerRatio));
  const endPoints = vertices.map((vertex, index) => slerpDirection(vertex, vertices[(index + 1) % vertices.length], cornerRatio));
  const boundary: THREE.Vector3[] = [];
  const cornerSteps = 5;
  const edgeSteps = 3;

  for (let index = 0; index < vertices.length; index += 1) {
    const start = startPoints[index];
    const end = endPoints[index];
    const control = vertices[index].clone().lerp(site, 0.09).normalize();
    for (let step = 0; step <= cornerSteps; step += 1) {
      const t = step / cornerSteps;
      const point = start.clone().multiplyScalar((1 - t) * (1 - t))
        .addScaledVector(control, 2 * (1 - t) * t)
        .addScaledVector(end, t * t)
        .normalize();
      boundary.push(point);
    }

    const nextStart = startPoints[(index + 1) % vertices.length];
    for (let step = 1; step < edgeSteps; step += 1) {
      boundary.push(slerpDirection(end, nextStart, step / edgeSteps));
    }
  }

  return boundary.map((point) => {
    const angularDistance = site.angleTo(point);
    return { point, angularDistance };
  });
}

function makePlateGeometry({
  site,
  roundedBoundary,
  radius,
  plateGap,
  plateExtrusion,
  layered
}: {
  site: THREE.Vector3;
  roundedBoundary: ReturnType<typeof roundedCellBoundary>;
  radius: number;
  plateGap: number;
  plateExtrusion: number;
  layered: boolean;
}) {
  const boundary = roundedBoundary.map(({ point, angularDistance }) => {
    const scale = Math.max(0.82, 1 - plateGap / (2 * radius * angularDistance));
    return slerpDirection(site, point, scale);
  });
  const ringScales = [1, 0.992, 0.978, 0.952, 0.912, 0.86, 0.79, 0.7, 0.59, 0.46, 0.32, 0.18, 0.08];
  const ringHeights = [0.003, plateExtrusion * 0.14, plateExtrusion * 0.38, plateExtrusion * 0.66, plateExtrusion * 0.9, plateExtrusion * 1.04, plateExtrusion * 1.08, plateExtrusion * 1.08, plateExtrusion * 1.06, plateExtrusion * 1.03, plateExtrusion, plateExtrusion * 0.985, plateExtrusion * 0.975];
  const positions: number[] = [];
  const indices: number[] = [];
  const pointsPerRing = boundary.length;

  ringScales.forEach((scale, ringIndex) => {
    const ringRadius = radius + (ringHeights[ringIndex] ?? plateExtrusion * 0.975);
    boundary.forEach((edgePoint) => {
      const direction = slerpDirection(site, edgePoint, scale);
      const point = direction.clone().multiplyScalar(ringRadius);
      positions.push(point.x, point.y, point.z);
    });
  });

  for (let ring = 0; ring < ringScales.length - 1; ring += 1) {
    const outerOffset = ring * pointsPerRing;
    const innerOffset = (ring + 1) * pointsPerRing;
    for (let index = 0; index < pointsPerRing; index += 1) {
      const next = (index + 1) % pointsPerRing;
      indices.push(
        outerOffset + index, outerOffset + next, innerOffset + next,
        outerOffset + index, innerOffset + next, innerOffset + index
      );
    }
  }

  const centerIndex = positions.length / 3;
  const centerPoint = site.clone().multiplyScalar(radius + plateExtrusion * 0.975);
  positions.push(centerPoint.x, centerPoint.y, centerPoint.z);
  const finalRingOffset = (ringScales.length - 1) * pointsPerRing;
  for (let index = 0; index < pointsPerRing; index += 1) {
    indices.push(finalRingOffset + index, finalRingOffset + ((index + 1) % pointsPerRing), centerIndex);
  }

  const trimStart = indices.length;
  const trimScales = [0.78, 0.754];
  const trimOffset = positions.length / 3;
  trimScales.forEach((scale) => {
    boundary.forEach((edgePoint) => {
      const direction = slerpDirection(site, edgePoint, scale);
      const point = direction.multiplyScalar(radius + plateExtrusion * 0.99 + 0.0015);
      positions.push(point.x, point.y, point.z);
    });
  });
  for (let index = 0; index < pointsPerRing; index += 1) {
    const next = (index + 1) % pointsPerRing;
    indices.push(
      trimOffset + index, trimOffset + next, trimOffset + pointsPerRing + next,
      trimOffset + index, trimOffset + pointsPerRing + next, trimOffset + pointsPerRing + index
    );
  }

  const luminousRimStart = indices.length;
  const luminousRimOffset = positions.length / 3;
  [0.955, 0.935].forEach((scale) => {
    boundary.forEach((edgePoint) => {
      const direction = slerpDirection(site, edgePoint, scale);
      const point = direction.multiplyScalar(radius + plateExtrusion * 1.04 + 0.0022);
      positions.push(point.x, point.y, point.z);
    });
  });
  for (let index = 0; index < pointsPerRing; index += 1) {
    const next = (index + 1) % pointsPerRing;
    indices.push(
      luminousRimOffset + index, luminousRimOffset + next, luminousRimOffset + pointsPerRing + next,
      luminousRimOffset + index, luminousRimOffset + pointsPerRing + next, luminousRimOffset + pointsPerRing + index
    );
  }

  const layeredLipStart = indices.length;
  if (layered) {
    const lipOffset = positions.length / 3;
    [0.935, 0.915, 0.89].forEach((scale, ringIndex) => {
      boundary.forEach((edgePoint) => {
        const direction = slerpDirection(site, edgePoint, scale);
        const point = direction.multiplyScalar(radius + plateExtrusion * (ringIndex === 0 ? 1.075 : 1.11) + 0.001);
        positions.push(point.x, point.y, point.z);
      });
    });
    for (let ring = 0; ring < 2; ring += 1) {
      const outerOffset = lipOffset + ring * pointsPerRing;
      const innerOffset = outerOffset + pointsPerRing;
      for (let index = 0; index < pointsPerRing; index += 1) {
        const next = (index + 1) % pointsPerRing;
        indices.push(
          outerOffset + index, outerOffset + next, innerOffset + next,
          outerOffset + index, innerOffset + next, innerOffset + index
        );
      }
    }
  }

  const gasketStart = indices.length;
  let insetFaceStart = indices.length;
  if (layered) {
    const gasketOffset = positions.length / 3;
    [0.87, 0.82].forEach((scale) => {
      boundary.forEach((edgePoint) => {
        const direction = slerpDirection(site, edgePoint, scale);
        const point = direction.multiplyScalar(radius + plateExtrusion * 1.105);
        positions.push(point.x, point.y, point.z);
      });
    });
    for (let index = 0; index < pointsPerRing; index += 1) {
      const next = (index + 1) % pointsPerRing;
      indices.push(
        gasketOffset + index, gasketOffset + next, gasketOffset + pointsPerRing + next,
        gasketOffset + index, gasketOffset + pointsPerRing + next, gasketOffset + pointsPerRing + index
      );
    }

    insetFaceStart = indices.length;
    const insetOffset = positions.length / 3;
    const insetScales = [0.82, 0.785, 0.68, 0.5, 0.28, 0.08];
    insetScales.forEach((scale, ringIndex) => {
      boundary.forEach((edgePoint) => {
        const direction = slerpDirection(site, edgePoint, scale);
        const point = direction.multiplyScalar(radius + plateExtrusion * (ringIndex === 0 ? 1.12 : 1.145));
        positions.push(point.x, point.y, point.z);
      });
    });
    for (let ring = 0; ring < insetScales.length - 1; ring += 1) {
      const outerOffset = insetOffset + ring * pointsPerRing;
      const innerOffset = outerOffset + pointsPerRing;
      for (let index = 0; index < pointsPerRing; index += 1) {
        const next = (index + 1) % pointsPerRing;
        indices.push(
          outerOffset + index, outerOffset + next, innerOffset + next,
          outerOffset + index, innerOffset + next, innerOffset + index
        );
      }
    }
    const centerIndex = positions.length / 3;
    const centerPoint = site.clone().multiplyScalar(radius + plateExtrusion * 1.145);
    positions.push(centerPoint.x, centerPoint.y, centerPoint.z);
    const finalRingOffset = insetOffset + (insetScales.length - 1) * pointsPerRing;
    for (let index = 0; index < pointsPerRing; index += 1) {
      indices.push(finalRingOffset + index, finalRingOffset + ((index + 1) % pointsPerRing), centerIndex);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  const bevelIndexCount = pointsPerRing * 6 * 4;
  geometry.addGroup(0, bevelIndexCount, 0);
  geometry.addGroup(bevelIndexCount, trimStart - bevelIndexCount, 1);
  geometry.addGroup(trimStart, luminousRimStart - trimStart, 2);
  geometry.addGroup(luminousRimStart, layeredLipStart - luminousRimStart, 3);
  if (layered) {
    geometry.addGroup(layeredLipStart, gasketStart - layeredLipStart, 4);
    geometry.addGroup(gasketStart, insetFaceStart - gasketStart, 5);
    geometry.addGroup(insetFaceStart, indices.length - insetFaceStart, 6);
  }
  return geometry;
}

function createPlateSpecs(layout: SupplyCorePlateLayout, radius: number, plateGap: number, plateExtrusion: number) {
  const cells = createPlateCells(layout);

  return cells.map(({ site, vertices, cornerRatio, icon, iconColor, accentColor }, index) => {
    const roundedBoundary = roundedCellBoundary(site, vertices, cornerRatio);
    const isMedallion = index === 0;
    const engraved = !icon && site.z > 0.24 && index % 4 === 2;
    const surfaceExtrusion = plateExtrusion + (isMedallion ? 0.008 : 0);
    const geometryBoundary = isMedallion
      ? roundedBoundary.map(({ point, angularDistance }) => ({
        point: slerpDirection(site, point, 1.02),
        angularDistance: angularDistance * 1.02
      }))
      : roundedBoundary;
    return {
      id: `plate-${String(index + 1).padStart(2, "0")}`,
      geometry: makePlateGeometry({ site, roundedBoundary: geometryBoundary, radius, plateGap, plateExtrusion: surfaceExtrusion, layered: isMedallion || Boolean(icon) }),
      site,
      angularRadius: roundedBoundary.reduce((sum, { angularDistance }) => sum + angularDistance, 0) / roundedBoundary.length,
      seed: index,
      plateExtrusion: surfaceExtrusion,
      icon,
      iconColor,
      accentColor,
      engraved
    };
  });
}

function createPanelIconGeometry(site: THREE.Vector3, radius: number, plateExtrusion: number, icon: PanelIcon) {
  const reference = Math.abs(site.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
  const tangentX = reference.clone().cross(site).normalize();
  const tangentY = site.clone().cross(tangentX).normalize();
  const size = radius * 0.1;
  const halfWidth = radius * 0.0035;
  const lift = radius + plateExtrusion * 1.145 + radius * 0.002;
  const positions: number[] = [];
  const normals: number[] = [];
  const indices: number[] = [];
  const toWorld = (x: number, y: number) => site.clone()
    .addScaledVector(tangentX, x * size / radius)
    .addScaledVector(tangentY, y * size / radius)
    .normalize()
    .multiplyScalar(lift);

  for (const stroke of iconStrokes[icon]) {
    for (let index = 0; index < stroke.length - 1; index += 1) {
      const start = toWorld(stroke[index][0], stroke[index][1]);
      const end = toWorld(stroke[index + 1][0], stroke[index + 1][1]);
      const tangent = end.clone().sub(start).normalize();
      const side = site.clone().cross(tangent).normalize().multiplyScalar(halfWidth);
      const first = start.clone().add(side);
      const second = start.clone().sub(side);
      const third = end.clone().add(side);
      const fourth = end.clone().sub(side);
      const baseIndex = positions.length / 3;
      for (const point of [first, second, third, fourth]) {
        positions.push(point.x, point.y, point.z);
        normals.push(site.x, site.y, site.z);
      }
      indices.push(baseIndex, baseIndex + 1, baseIndex + 2, baseIndex + 2, baseIndex + 1, baseIndex + 3);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  geometry.setIndex(indices);
  return geometry;
}

function PanelIconMesh({
  site,
  radius,
  plateExtrusion,
  icon,
  color
}: {
  site: THREE.Vector3;
  radius: number;
  plateExtrusion: number;
  icon: PanelIcon;
  color: string;
}) {
  const geometry = useMemo(() => createPanelIconGeometry(site, radius, plateExtrusion, icon), [site, radius, plateExtrusion, icon]);
  useEffect(() => () => geometry.dispose(), [geometry]);

  return (
    <mesh geometry={geometry} frustumCulled={false} renderOrder={4}>
      <meshBasicMaterial color={color} toneMapped={false} />
    </mesh>
  );
}

function createPanelEtchGeometry(site: THREE.Vector3, radius: number, plateExtrusion: number, seed: number) {
  const reference = Math.abs(site.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
  const tangentX = reference.clone().cross(site).normalize();
  const tangentY = site.clone().cross(tangentX).normalize();
  const angle = ((seed % 5) - 2) * 0.16;
  const cosine = Math.cos(angle);
  const sine = Math.sin(angle);
  const size = radius * 0.15;
  const halfWidth = radius * 0.0011;
  const lift = radius + plateExtrusion * 1.085 + radius * 0.0015;
  const strokes = seed % 2 === 0
    ? [[[-0.72, 0.52], [-0.18, 0.52]], [[-0.72, 0.52], [-0.72, 0.18]], [[0.28, -0.48], [0.72, -0.48]]]
    : [[[-0.68, -0.5], [-0.2, -0.5]], [[0.52, 0.16], [0.52, 0.55]], [[0.2, 0.55], [0.52, 0.55]]];
  const positions: number[] = [];
  const indices: number[] = [];
  const toWorld = (x: number, y: number) => {
    const rotatedX = x * cosine - y * sine;
    const rotatedY = x * sine + y * cosine;
    return site.clone()
      .addScaledVector(tangentX, rotatedX * size / radius)
      .addScaledVector(tangentY, rotatedY * size / radius)
      .normalize()
      .multiplyScalar(lift);
  };

  for (const stroke of strokes) {
    const start = toWorld(stroke[0][0], stroke[0][1]);
    const end = toWorld(stroke[1][0], stroke[1][1]);
    const side = site.clone().cross(end.clone().sub(start).normalize()).normalize().multiplyScalar(halfWidth);
    const baseIndex = positions.length / 3;
    for (const point of [start.clone().add(side), start.clone().sub(side), end.clone().add(side), end.clone().sub(side)]) {
      positions.push(point.x, point.y, point.z);
    }
    indices.push(baseIndex, baseIndex + 1, baseIndex + 2, baseIndex + 2, baseIndex + 1, baseIndex + 3);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  return geometry;
}

function PanelEtchMesh({ site, radius, plateExtrusion, seed }: { site: THREE.Vector3; radius: number; plateExtrusion: number; seed: number }) {
  const geometry = useMemo(() => createPanelEtchGeometry(site, radius, plateExtrusion, seed), [site, radius, plateExtrusion, seed]);
  useEffect(() => () => geometry.dispose(), [geometry]);

  return (
    <mesh geometry={geometry} frustumCulled={false} renderOrder={4}>
      <meshBasicMaterial color="#493722" transparent opacity={0.76} depthWrite={false} toneMapped={false} />
    </mesh>
  );
}

function createFastenerMatrices(
  plates: ReturnType<typeof createPlateSpecs>,
  radius: number,
  plateExtrusion: number
) {
  const transforms: THREE.Matrix4[] = [];
  const marker = new THREE.Object3D();
  const normal = new THREE.Vector3();
  const reference = new THREE.Vector3();
  const tangentA = new THREE.Vector3();
  const tangentB = new THREE.Vector3();
  const markerNormal = new THREE.Vector3(0, 1, 0);

  for (const { site, angularRadius, plateExtrusion: plateHeight, icon, engraved } of plates) {
    reference.set(Math.abs(site.y) < 0.9 ? 0 : 1, Math.abs(site.y) < 0.9 ? 1 : 0, 0);
    tangentA.crossVectors(reference, site).normalize();
    tangentB.crossVectors(site, tangentA).normalize();
    const tangents = engraved && !icon
      ? [tangentA, tangentB, tangentA.clone().negate(), tangentB.clone().negate()]
      : [tangentA, tangentB];
    for (const tangent of tangents) {
      const markerAngle = angularRadius * (icon ? 0.88 : engraved ? 0.72 : 0.58);
      normal.copy(site).multiplyScalar(Math.cos(markerAngle))
        .addScaledVector(tangent, Math.sin(markerAngle)).normalize();
      marker.position.copy(normal).multiplyScalar(radius + (plateHeight ?? plateExtrusion) * (icon ? 1.11 : engraved ? 1.085 : 1) + radius * 0.0014);
      marker.quaternion.setFromUnitVectors(markerNormal, normal);
      marker.scale.setScalar(radius * (engraved && !icon ? 0.008 : 0.0095));
      marker.updateMatrix();
      transforms.push(marker.matrix.clone());
    }
  }

  return transforms;
}

function resolvePlateColor(baseColor: string, state: SupplyCorePlateState | undefined, seed: number, accent?: string) {
  const color = new THREE.Color(state && state !== "normal" ? STATE_COLORS[state] : accent ?? baseColor);
  if (!state || state === "normal") {
    color.offsetHSL(0, 0, accent ? 0 : plateToneOffsets[seed % plateToneOffsets.length] + (seed === 0 ? 0.04 : 0));
  }
  return color;
}

/** Procedural, state-addressable modular Home planet. Plate IDs are stable for a given layout seed. */
export function SupplyCore({
  radius = 1.1,
  plateLayout = DEFAULT_SUPPLY_CORE_LAYOUT,
  plateGap = 0.026,
  plateExtrusion = 0.045,
  defaultColors,
  plateStates = {},
  emission = 0.28,
  roughness = 0.42,
  showOrbit = true,
  showDetails = true,
  showIcons = true
}: SupplyCoreProps) {
  const colors = { ...DEFAULT_COLORS, ...defaultColors };
  const plates = useMemo(
    () => createPlateSpecs(plateLayout, radius, plateGap, plateExtrusion),
    [plateLayout, radius, plateGap, plateExtrusion]
  );
  const fastenerGeometry = useMemo(() => new THREE.SphereGeometry(1, 12, 8), []);
  const fastenerRef = useRef<THREE.InstancedMesh>(null);
  const fastenerMatrices = useMemo(
    () => showDetails ? createFastenerMatrices(plates, radius, plateExtrusion) : [],
    [plates, radius, plateExtrusion, showDetails]
  );
  const orbitRotation = useMemo(() => {
    const majorAxis = new THREE.Vector3(1, -0.27, 0).normalize();
    const normal = new THREE.Vector3(0.27, 1, 0).normalize().multiplyScalar(Math.sqrt(1 - 0.32 ** 2));
    normal.z = 0.32;
    normal.normalize();
    const minorAxis = new THREE.Vector3().crossVectors(normal, majorAxis).normalize();
    const basis = new THREE.Matrix4().makeBasis(majorAxis, minorAxis, normal);
    return new THREE.Euler().setFromRotationMatrix(basis, "XYZ");
  }, []);

  useLayoutEffect(() => {
    const instance = fastenerRef.current;
    if (!instance) return;
    fastenerMatrices.forEach((matrix, index) => instance.setMatrixAt(index, matrix));
    instance.instanceMatrix.needsUpdate = true;
  }, [fastenerMatrices]);

  return (
    <group name="HomeRoot">
      <mesh name="CoreSphere">
        <sphereGeometry args={[radius - plateGap * 0.52, 64, 48]} />
        <meshStandardMaterial color={colors.core} roughness={0.42} metalness={0.48} />
      </mesh>

      <group name="PlateGroups">
        {plates.map(({ id, geometry, seed, site, plateExtrusion: plateHeight, icon: iconType, iconColor, accentColor, engraved }) => {
          const state = plateStates[id];
          const isAlert = state === "warning" || state === "attention";
          const color = resolvePlateColor(colors.plate, state, seed, accentColor);
          const icon = showIcons && iconType && iconColor ? { icon: iconType, color: iconColor } : undefined;
          return (
            <group key={id}>
              <mesh name={`Plate-${id}`} geometry={geometry} castShadow receiveShadow>
                <meshStandardMaterial
                  attach="material-0"
                  color={color.clone().multiplyScalar(0.69)}
                  metalness={0.68}
                  roughness={Math.min(0.76, roughness + 0.06)}
                />
                <meshPhysicalMaterial
                  attach="material-1"
                  color={color}
                  emissive={state && state !== "normal" ? STATE_COLORS[state] : seed === 0 ? "#7b3d11" : "#2b1809"}
                  emissiveIntensity={state && state !== "normal" ? emission * (isAlert ? 0.62 : 0.34) : seed === 0 ? 0.035 : 0.012}
                  metalness={0.72}
                  roughness={THREE.MathUtils.clamp(roughness + (seed % 5) * 0.035, 0.48, 0.68)}
                  clearcoat={0.12}
                  clearcoatRoughness={0.58}
                />
                <meshStandardMaterial
                  attach="material-2"
                  color={color.clone().lerp(new THREE.Color("#f0ca8b"), 0.1)}
                  metalness={0.72}
                  roughness={0.42}
                />
                <meshStandardMaterial
                  attach="material-3"
                  color={color.clone().lerp(new THREE.Color(colors.orbit), 0.2)}
                  emissive={color.clone().lerp(new THREE.Color(colors.orbit), 0.48)}
                  emissiveIntensity={state && state !== "normal" ? emission * 0.24 : seed === 0 ? 0.48 : iconType ? 0.18 : 0.035}
                  metalness={0.58}
                  roughness={0.24}
                  toneMapped={false}
                />
                <meshStandardMaterial
                  attach="material-4"
                  color={color.clone().lerp(new THREE.Color("#f8dbad"), 0.38)}
                  emissive={color.clone().lerp(new THREE.Color(colors.orbit), 0.24)}
                  emissiveIntensity={seed === 0 ? 0.28 : 0.055}
                  metalness={0.76}
                  roughness={0.3}
                  toneMapped={false}
                />
                <meshStandardMaterial
                  attach="material-5"
                  color={color.clone().multiplyScalar(0.42)}
                  metalness={0.64}
                  roughness={0.5}
                />
                <meshPhysicalMaterial
                  attach="material-6"
                  color={color.clone().lerp(new THREE.Color("#e2c79f"), 0.16)}
                  emissive={color.clone().lerp(new THREE.Color(colors.orbit), 0.22)}
                  emissiveIntensity={seed === 0 ? 0.09 : 0.025}
                  metalness={0.74}
                  roughness={0.38}
                  clearcoat={0.18}
                  clearcoatRoughness={0.46}
                  toneMapped={false}
                />
              </mesh>
              {icon && <PanelIconMesh site={site} radius={radius} plateExtrusion={plateHeight} {...icon} />}
              {showDetails && engraved && <PanelEtchMesh site={site} radius={radius} plateExtrusion={plateHeight} seed={seed} />}
            </group>
          );
        })}
      </group>

      {showDetails && fastenerMatrices.length > 0 && (
        <instancedMesh ref={fastenerRef} name="PlateFasteners" args={[fastenerGeometry, undefined, fastenerMatrices.length]} castShadow>
          <meshStandardMaterial color="#ffe1a7" emissive="#e7a34b" emissiveIntensity={0.16} metalness={0.56} roughness={0.3} />
        </instancedMesh>
      )}

      <group name="AtmosphereRim">
        <mesh name="GoldInnerRim" scale={1.026} renderOrder={3}>
          <sphereGeometry args={[radius, 64, 48]} />
          <meshBasicMaterial color={colors.orbit} side={THREE.BackSide} transparent opacity={0.12} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>
        <mesh name="GoldOuterRim" scale={1.064} renderOrder={3}>
          <sphereGeometry args={[radius, 48, 36]} />
          <meshBasicMaterial color="#cb762c" side={THREE.BackSide} transparent opacity={0.065} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>
      </group>

      {showOrbit && <group name="OrbitRing" position={[0, -radius * 0.04, 0]} rotation={orbitRotation}>
        <mesh name="SupplyOrbitGlow" renderOrder={1}>
          <torusGeometry args={[radius * 1.24, 0.012, 8, 180]} />
          <meshBasicMaterial color={colors.orbit} transparent opacity={0.06} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>
        <mesh name="SupplyOrbit" renderOrder={2}>
          <torusGeometry args={[radius * 1.24, 0.0028, 6, 180]} />
          <meshBasicMaterial color="#e2a34f" toneMapped={false} />
        </mesh>
        <mesh name="OrbitMarkerOne" position={[radius * 1.24, 0, 0]}>
          <sphereGeometry args={[0.025, 16, 12]} />
          <meshBasicMaterial color="#fff2cf" toneMapped={false} />
        </mesh>
        <mesh name="OrbitMarkerTwo" position={[-radius * 1.24, 0, 0]}>
          <sphereGeometry args={[0.019, 14, 10]} />
          <meshBasicMaterial color="#ffe1a0" toneMapped={false} />
        </mesh>
      </group>}
    </group>
  );
}
