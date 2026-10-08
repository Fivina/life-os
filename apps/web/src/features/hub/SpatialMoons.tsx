import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { spatialDomains, type SpatialDomainId } from "./spatialNavigation";
import { spatialMoonCatalog } from "./spatialMoonCatalog";
import { moonPosition, type MoonFrame } from "./spatialJourney";

export function moonKey(domain: SpatialDomainId, id: string) { return `moon:${domain}:${id}`; }

function mineralMoon(seed: number, accent: string) {
  const geometry = new THREE.SphereGeometry(1, 40, 28);
  const positions = geometry.attributes.position;
  const colors = new Float32Array(positions.count * 3);
  const color = new THREE.Color(accent);
  const point = new THREE.Vector3();
  for (let index = 0; index < positions.count; index++) {
    point.fromBufferAttribute(positions, index).normalize();
    const strata = Math.sin(point.x * 13 + seed) * Math.cos(point.y * 19 - seed) * Math.sin(point.z * 17 + seed * 0.7);
    const fine = Math.sin(point.x * 43 + point.z * 31) * Math.cos(point.y * 37 + seed);
    point.multiplyScalar(1 + strata * 0.016 + fine * 0.004);
    positions.setXYZ(index, point.x, point.y, point.z);
    const value = 0.2 + (strata * 0.5 + 0.5) * 0.25;
    colors.set([color.r * value, color.g * value, color.b * value], index * 3);
  }
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  geometry.computeVertexNormals();
  return geometry;
}

function MoonSystem({ domain, frame, active, selectable, reducedMotion, onSelect }: {
  domain: SpatialDomainId; frame: MoonFrame; active: boolean; selectable: boolean; reducedMotion: boolean; onSelect: (href: string) => void;
}) {
  const groups = useRef<(THREE.Group | null)[]>([]);
  const time = useRef(0);
  const moons = spatialMoonCatalog[domain];
  const geometries = useMemo(() => moons.map((moon, index) => mineralMoon(index + domain.length, moon.accent)), [moons, domain]);
  const orbit = useMemo(() => {
    const points = Array.from({ length: 97 }, (_, index) => moonPosition(frame, index, 96));
    return new THREE.BufferGeometry().setFromPoints(points);
  }, [frame]);
  useEffect(() => () => { geometries.forEach(geometry => geometry.dispose()); }, [geometries]);
  useEffect(() => () => orbit.dispose(), [orbit]);
  useFrame((_, delta) => {
    if (!active) return;
    if (!reducedMotion) time.current += Math.min(delta, 0.05);
    moons.forEach((_, index) => {
      const group = groups.current[index];
      if (!group) return;
      group.position.copy(moonPosition(frame, index, moons.length, time.current));
      group.rotation.y = reducedMotion ? 0 : time.current * 0.035;
    });
  }, -3);
  return <group visible={active} name={`${domain}-moons`}>
    <lineLoop>
      <primitive object={orbit} attach="geometry" />
      <lineBasicMaterial color={spatialDomains.find(item => item.id === domain)?.color} transparent opacity={0.14} />
    </lineLoop>
    {moons.map((moon, index) => <group key={moon.id} name={moonKey(domain, moon.id)}
      ref={object => { groups.current[index] = object; }} position={moonPosition(frame, index, moons.length)}
      onClick={event => { event.stopPropagation(); if (active && selectable && moon.href) onSelect(moon.href); }}>
      <mesh geometry={geometries[index]} scale={frame.radius * (index % 2 ? 0.19 : 0.23)}>
        <meshStandardMaterial vertexColors roughness={0.86} metalness={0.12} />
      </mesh>
    </group>)}
  </group>;
}

export function SpatialMoons({ frames, activeDomains, selectableDomain, reducedMotion, onSelect }: {
  frames: Partial<Record<SpatialDomainId, MoonFrame>>; activeDomains: readonly SpatialDomainId[]; selectableDomain: SpatialDomainId | null; reducedMotion: boolean; onSelect: (href: string) => void;
}) {
  return <group name="SpatialSubcomponents">{spatialDomains.map(domain => {
    const frame = frames[domain.id];
    return frame ? <MoonSystem key={domain.id} domain={domain.id} frame={frame} active={activeDomains.includes(domain.id)} selectable={selectableDomain === domain.id} reducedMotion={reducedMotion} onSelect={onSelect} /> : null;
  })}</group>;
}
