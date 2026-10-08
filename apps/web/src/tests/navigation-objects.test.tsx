import { isValidElement, type ReactNode } from "react";
import * as THREE from "three";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SelfCore } from "../features/hub/three/SelfCore";
import { SettingsGravityWell } from "../features/settings-gravity-well/SettingsGravityWell";

const { frames } = vi.hoisted(() => ({ frames: [] as ((state: unknown, delta: number) => void)[] }));
vi.mock("@react-three/fiber", () => ({ useFrame: (callback: typeof frames[number]) => frames.push(callback) }));
vi.mock("react", async (original) => ({
  ...await original<typeof import("react")>(),
  useMemo: (factory: () => unknown) => factory(),
  useRef: (current: unknown) => ({ current }),
  useEffect: () => undefined
}));

type HostProps = {
  name?: string;
  children?: ReactNode;
  args?: readonly unknown[];
  ref?: { current: THREE.Object3D | null };
  geometry?: THREE.BufferGeometry;
  object?: THREE.ShaderMaterial;
  uniforms?: Record<string, { value: unknown }>;
  scale?: number;
};
type Host = { type: string; props: HostProps };

// Evaluate only these object components and attach real Three refs without a Canvas.
function objectTree(node: ReactNode, hosts: Host[] = []): Host[] {
  if (Array.isArray(node)) {
    node.forEach((child) => objectTree(child, hosts));
  } else if (isValidElement<HostProps>(node)) {
    if (typeof node.type === "function") {
      objectTree((node.type as (props: HostProps) => ReactNode)(node.props), hosts);
    } else if (typeof node.type === "string") {
      hosts.push({ type: node.type, props: node.props });
      if (node.props.ref) {
        node.props.ref.current = node.type === "sprite" ? new THREE.Sprite(new THREE.SpriteMaterial()) : node.type === "instancedMesh"
          ? new THREE.InstancedMesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial(), Number(node.props.args?.[2]))
          : new THREE.Group();
      }
      objectTree(node.props.children, hosts);
    }
  }
  return hosts;
}

function advance(seconds: number, hz = 60) {
  for (let index = 0; index < seconds * hz; index += 1) frames.forEach((frame) => frame({}, 1 / hz));
}

function timeUniforms(hosts: Host[]) {
  return hosts.flatMap(({ props }) => {
    const time = (props.uniforms ?? props.object?.uniforms)?.uTime;
    return time ? [time] : [];
  });
}

function budget(hosts: Host[]) {
  let triangles = 0;
  let points = 0;
  for (const { type, props } of hosts) {
    const args = props.args ?? [];
    if (type === "tubeGeometry") triangles += Number(args[1]) * Number(args[3]) * 2;
    if (type === "sphereGeometry") triangles += Number(args[1]) * (Number(args[2]) - 1) * 2;
    if (type === "mesh" && props.geometry) triangles += (props.geometry.index?.count ?? 0) / 3;
    if (type === "bufferAttribute") points += (args[0] as Float32Array).length / 3;
    if (type === "points" && props.geometry) points += props.geometry.getAttribute("position").count;
  }
  return { triangles, points };
}

describe("persistent scene navigation objects", () => {
  beforeEach(() => { frames.length = 0; });

  it("keeps SelfCore's ten orbit silhouettes with a materially smaller navigation budget", () => {
    const hero = objectTree(<SelfCore />);
    const navigation = objectTree(<SelfCore quality="navigation" scale={0.7} showParticles={false} />);
    expect(navigation.filter(({ props }) => props.name?.startsWith("OrbitArc_"))).toHaveLength(10);
    expect(budget(navigation).triangles).toBeLessThan(budget(hero).triangles * 0.2);
    expect(navigation.find(({ props }) => props.name === "SelfCoreRoot")?.props.scale).toBe(0.7);
    expect(navigation.some(({ props }) => props.name === "ParticleField")).toBe(false);
    expect(hero.find(({ type }) => type === "instancedMesh")?.props.args?.[2]).toBe(20);
    expect(navigation.find(({ type }) => type === "instancedMesh")?.props.args?.[2]).toBe(4);
  });

  it("reduces gravity geometry and particle cost while preserving the void radius", () => {
    const hero = objectTree(<SettingsGravityWell />);
    const navigation = objectTree(<SettingsGravityWell quality="navigation" />);
    expect(budget(navigation).triangles).toBeLessThan(budget(hero).triangles * 0.2);
    expect(budget(navigation).points).toBeLessThan(budget(hero).points * 0.4);
    expect(navigation.find(({ type }) => type === "sphereGeometry")?.props.args?.[0]).toBe(0.68);
    expect(hero.filter(({ type }) => type === "tubeGeometry")).toHaveLength(152);
    expect(navigation.filter(({ type }) => type === "tubeGeometry")).toHaveLength(52);
  });

  it("freezes every SelfCore shader and packet after static initialization under reduced motion", () => {
    const tree = objectTree(<SelfCore reducedMotion />);
    advance(1);
    const packets = tree.find(({ type }) => type === "instancedMesh")?.props.ref?.current as THREE.InstancedMesh;
    const initial = Array.from(packets.instanceMatrix.array);
    const version = packets.instanceMatrix.version;
    expect(initial.some((value, index) => index % 16 === 12 && Math.abs(value) > 0.1)).toBe(true);
    advance(2);
    expect(Array.from(packets.instanceMatrix.array)).toEqual(initial);
    expect(packets.instanceMatrix.version).toBe(version);
    expect(timeUniforms(tree)).toHaveLength(4);
    expect(timeUniforms(tree).every(({ value }) => value === 0)).toBe(true);
  });

  it("runs gravity flow slowly without rotating the void, and freezes all gravity motion when reduced", () => {
    const moving = objectTree(<SettingsGravityWell />);
    const still = objectTree(<SettingsGravityWell reducedMotion />);
    advance(10);
    const rotation = (tree: Host[], name: string) => (tree.find(({ props }) => props.name === name)?.props.ref?.current as THREE.Group).rotation.z;
    expect(rotation(moving, "AccretionFlow")).toBeCloseTo(-0.06);
    expect(rotation(moving, "AccretionDiskLayer")).toBeCloseTo(-0.03);
    expect(rotation(still, "AccretionFlow")).toBe(0);
    expect(rotation(still, "AccretionDiskLayer")).toBe(0);
    expect(moving.find(({ props }) => props.name === "VoidCore")?.props.ref).toBeUndefined();
    expect(timeUniforms(still).every(({ value }) => value === 0)).toBe(true);
    expect(timeUniforms(moving).every(({ value }) => Math.abs(Number(value) - 10) < 1e-8)).toBe(true);
    expect(moving.find(({ type }) => type === "primitive")?.props.object?.depthTest).toBe(true);
  });

  it("keeps simultaneous instances' animation clocks independent and frame-rate independent", () => {
    const self = objectTree(<SelfCore quality="navigation" />);
    const gravity = objectTree(<SettingsGravityWell quality="navigation" />);
    advance(2, 30);
    expect(timeUniforms(self).every(({ value }) => Math.abs(Number(value) - 2) < 1e-8)).toBe(true);
    expect(timeUniforms(gravity).every(({ value }) => Math.abs(Number(value) - 2) < 1e-8)).toBe(true);
    expect(timeUniforms(self)[0]).not.toBe(timeUniforms(gravity)[0]);
  });

  it("brightens focus smoothly without changing identity to an attention color", () => {
    const tree = objectTree(<SelfCore highlighted quality="navigation" />);
    const halo = tree.find(({ props }) => props.name === "HaloLight")?.props.ref?.current as THREE.Sprite;
    advance(1);
    const native = new THREE.Color("#82d9ff");
    expect(halo.material.color.b).toBeGreaterThan(native.b * 1.5);
    expect(halo.material.color.b).toBeGreaterThan(halo.material.color.r);
  });
});
