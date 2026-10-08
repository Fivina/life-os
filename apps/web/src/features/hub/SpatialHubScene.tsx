import { Suspense, useEffect, useMemo, useRef, type RefObject } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { Bloom, EffectComposer } from "@react-three/postprocessing";

import { ChronoRing } from "../calendar/ChronoRing";
import { OrbitBarbell } from "../fitness/OrbitBarbell";
import { SupplyCore } from "../home/SupplyCore";
import { CoreEarth } from "../life/CoreEarth";
import { NeuralBloom } from "../neural-bloom/NeuralBloom";
import { SettingsGravityWell } from "../settings-gravity-well/SettingsGravityWell";
import { SelfCore } from "./three/SelfCore";
import { domainPosition, smoothTravel, spatialDomains, WARP_SECONDS, type SpatialDepth, type SpatialDomainId } from "./spatialNavigation";

export type SpatialTarget = SpatialDomainId | "self" | "settings";
type SceneProps = {
  depth: SpatialDepth;
  reducedMotion: boolean;
  hovered: SpatialTarget | null;
  calendarAttention: boolean;
  labels: RefObject<Partial<Record<SpatialTarget, HTMLButtonElement>>>;
  onArrive: () => void;
};

function Stars({ reducedMotion, travel }: { reducedMotion: boolean; travel: RefObject<number> }) {
  const root = useRef<THREE.Points>(null);
  const streaks = useRef<THREE.LineSegments>(null);
  const geometry = useMemo(() => {
    const positions = new Float32Array(750 * 3);
    let seed = 702;
    const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
    for (let i = 0; i < positions.length; i += 3) {
      positions[i] = (random() - 0.5) * 65;
      positions[i + 1] = (random() - 0.5) * 45;
      positions[i + 2] = -4 - random() * 35;
    }
    const result = new THREE.BufferGeometry();
    result.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return result;
  }, []);
  const streakGeometry = useMemo(() => {
    const points = geometry.getAttribute("position");
    const positions = new Float32Array(points.count * 6);
    for (let i = 0; i < points.count; i++) {
      const x = points.getX(i), y = points.getY(i), z = points.getZ(i);
      positions.set([x, y, z, x * 1.09, y * 1.09, z + 2.5], i * 6);
    }
    return new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(positions, 3));
  }, [geometry]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  useEffect(() => () => streakGeometry.dispose(), [streakGeometry]);
  useFrame((_, delta) => {
    if (!root.current) return;
    if (reducedMotion) {
      root.current.scale.z = 1;
      if (streaks.current) streaks.current.visible = false;
      return;
    }
    root.current.rotation.z += delta * 0.0009;
    root.current.scale.z = 1 - Math.sin(travel.current * Math.PI) * 0.35;
    if (streaks.current) {
      const strength = Math.sin(travel.current * Math.PI) ** 2;
      streaks.current.visible = strength > 0.01;
      (streaks.current.material as THREE.LineBasicMaterial).opacity = strength * 0.36;
    }
  });
  return <>
    <points ref={root} geometry={geometry}><pointsMaterial color="#b8d8ec" size={1.2} sizeAttenuation={false} transparent opacity={0.4} depthWrite={false} /></points>
    <lineSegments ref={streaks} geometry={streakGeometry} visible={false}><lineBasicMaterial color="#90c9ee" transparent opacity={0} depthWrite={false} /></lineSegments>
  </>;
}

function DomainObject({ id, attention }: { id: SpatialDomainId; attention: boolean }) {
  switch (id) {
    case "calendar": return <ChronoRing variant="miniature" attentionSegments={attention ? [0, 1, 2] : []} attentionNow={attention} />;
    case "learning": return <NeuralBloom mode="miniature" branchComplexity="minimal" branchEmission={0.95} nodeEmission={1.15} />;
    case "home": return <SupplyCore plateLayout={HOME_LAYOUT} showDetails={false} showIcons={false} emission={0.35} />;
    case "fitness": return <OrbitBarbell variant="miniature" view="three-quarter" cyanIntensity={0.85} />;
    case "life": return <CoreEarth presentation="miniature" cloudOpacity={0.45} lifeLightDensity={0.15} />;
  }
}
const HOME_LAYOUT = { plateCount: 28, seed: 328, jitter: 0.13, cornerRadius: 0.25 };

function SystemScene({ depth, reducedMotion, hovered, calendarAttention, labels, onArrive }: SceneProps) {
  const { camera, size, gl } = useThree();
  const compact = size.width / size.height < 0.9;
  const core = useRef<THREE.Group>(null);
  const gravity = useRef<THREE.Group>(null);
  const domains = useRef<Partial<Record<SpatialDomainId, THREE.Group>>>({});
  const progress = useRef(depth === "system" ? 1 : 0);
  const travel = useRef(0);
  const orbitTime = useRef(0);
  const transition = useRef({ from: progress.current, to: progress.current, elapsed: WARP_SECONDS, reported: true });
  const scratch = useMemo(() => new THREE.Vector3(), []);
  const frameStats = useRef({ elapsed: 0, frames: 0, slow: 0 });
  const hoverScale = useRef(1);
  const orbitSpeed = useRef(1);

  useEffect(() => {
    const previous = gl.info.autoReset;
    gl.info.autoReset = false;
    return () => { gl.info.autoReset = previous; };
  }, [gl]);

  useEffect(() => {
    const to = depth === "system" ? 1 : 0;
    transition.current = { from: progress.current, to, elapsed: progress.current === to ? WARP_SECONDS : 0, reported: false };
  }, [depth]);

  useFrame((_, dt) => {
    const delta = Math.min(dt, 0.05);
    const state = transition.current;
    state.elapsed += dt;
    const phase = reducedMotion ? 1 : Math.min(1, state.elapsed / WARP_SECONDS);
    progress.current = THREE.MathUtils.lerp(state.from, state.to, smoothTravel(phase));
    travel.current = phase < 1 ? phase : 0;
    if (phase === 1 && !state.reported) { state.reported = true; onArrive(); }
    orbitSpeed.current = THREE.MathUtils.damp(orbitSpeed.current, hovered ? 0 : 1, 5, delta);
    if (!reducedMotion) orbitTime.current += delta * orbitSpeed.current;
    const p = progress.current;
    const surge = reducedMotion || phase === 1 ? 0 : Math.sin(phase * Math.PI) ** 2 * 4;
    const systemDistance = compact ? 18.8 : Math.max(15.4, 8.1 / (Math.tan(THREE.MathUtils.degToRad(21)) * size.width / size.height));
    camera.position.set(0, THREE.MathUtils.lerp(0.15, compact ? 0.05 : 0.3, p), THREE.MathUtils.lerp(24, systemDistance, p) - surge);
    camera.lookAt(0, 0.15, 0);
    camera.updateMatrixWorld();

    if (core.current) {
      core.current.position.y = THREE.MathUtils.lerp(1.7, 0.55, p);
      hoverScale.current = reducedMotion ? (hovered === "self" ? 1.1 : 1) : THREE.MathUtils.damp(hoverScale.current, hovered === "self" ? 1.1 : 1, 7, delta);
      core.current.scale.setScalar(THREE.MathUtils.lerp(1.75, 1.05, p) * hoverScale.current);
    }
    if (gravity.current) {
      gravity.current.position.y = THREE.MathUtils.lerp(-3.6, compact ? -5.3 : -3.55, p);
      gravity.current.scale.setScalar(THREE.MathUtils.lerp(0.88, 0.46, p));
    }
    for (const domain of spatialDomains) {
      const object = domains.current[domain.id];
      if (!object) continue;
      const position = domainPosition(domain.angle, compact, orbitTime.current);
      object.position.set(...position);
      object.visible = p > 0.06;
      object.scale.setScalar((compact ? 0.47 : 0.7) * smoothTravel(p));
      object.rotation.y = reducedMotion ? 0 : Math.sin(orbitTime.current * 0.035 + domain.angle) * 0.12;
      positionLabel(domain.id, object);
    }
    if (core.current) positionLabel("self", core.current);
    if (gravity.current) positionLabel("settings", gravity.current);

    // Development-only frame samples contain no personal state.
    if (import.meta.env.DEV) {
      const stats = frameStats.current;
      stats.elapsed += dt; stats.frames += 1; if (dt > 0.025) stats.slow += 1;
      if (stats.elapsed >= 2) {
        const host = gl.domElement;
        const fps = stats.frames / stats.elapsed;
        host.dataset.fps = fps.toFixed(1);
        host.dataset.drawCalls = String(gl.info.render.calls);
        host.dataset.triangles = String(gl.info.render.triangles);
        host.dataset.slowFrames = String(stats.slow);
        frameStats.current = { elapsed: 0, frames: 0, slow: 0 };
      }
    }
    gl.info.reset();
  });

  function positionLabel(id: SpatialTarget, object: THREE.Group) {
    const element = labels.current[id];
    if (!element) return;
    object.getWorldPosition(scratch);
    scratch.project(camera);
    element.style.left = `${(scratch.x * 0.5 + 0.5) * size.width}px`;
    element.style.top = `${(-scratch.y * 0.5 + 0.5) * size.height}px`;
  }

  const tracks = useMemo(() => spatialDomains.map((domain, i) => {
    const geometry = new THREE.BufferGeometry();
    const points = Array.from({ length: 129 }, (_, n) => {
      const angle = n / 128 * Math.PI * 2;
      return new THREE.Vector3(Math.cos(angle) * (compact ? 2.05 : 5.8) * (1 + i * 0.06), Math.sin(angle) * (compact ? 3.85 : 2.8) * (1 - i * 0.035) + 0.45, Math.sin(angle + i * 0.5) * 0.8 - 0.3 - i * 0.08);
    });
    geometry.setFromPoints(points);
    return new THREE.LineLoop(geometry, new THREE.LineBasicMaterial({ color: domain.color, transparent: true, opacity: 0.035 }));
  }), [compact]);
  useEffect(() => () => tracks.forEach(track => { track.geometry.dispose(); (track.material as THREE.Material).dispose(); }), [tracks]);

  return <>
    <color attach="background" args={["#000208"]} />
    <ambientLight intensity={0.8} />
    <hemisphereLight args={["#d7efff", "#030610", 0.85]} />
    <directionalLight position={[-3, 5, 7]} intensity={2.7} color="#d7e8ff" />
    <directionalLight position={[6, -2, -4]} intensity={1.8} color="#67b7e9" />
    <pointLight position={[0, 0.6, 2]} intensity={12} distance={18} color="#a6ddff" />
    <Stars reducedMotion={reducedMotion} travel={travel} />
    <group ref={core} position={[0, 0.55, 0]}><SelfCore quality="navigation" highlighted={hovered === "self"} orbitSpread={depth === "core" ? (compact ? 2.1 : 3.5) : 1.4} reducedMotion={reducedMotion} /></group>
    <group ref={gravity} position={[0, -3.1, -0.6]}><SettingsGravityWell quality="navigation" reducedMotion={reducedMotion} flowDensity={compact ? 36 : 48} flowRadius={3.5} haloIntensity={0.7} /></group>
    <group visible={depth === "system"}>{tracks.map((track, i) => <primitive object={track} key={i} />)}</group>
    {spatialDomains.map(domain => <group key={domain.id} ref={(object) => { if (object) domains.current[domain.id] = object; }} visible={depth === "system"}>
      <Suspense fallback={null}><DomainObject id={domain.id} attention={domain.id === "calendar" && calendarAttention} /></Suspense>
    </group>)}
    <EffectComposer multisampling={0} resolutionScale={0.5}>
      <Bloom intensity={0.32} luminanceThreshold={1.15} luminanceSmoothing={0.35} mipmapBlur />
    </EffectComposer>
  </>;
}

export function SpatialHubScene(props: SceneProps) {
  return <Canvas frameloop={props.reducedMotion ? "demand" : "always"} camera={{ position: [0, 0.15, 24], fov: 42, near: 0.1, far: 100 }} dpr={[1, 1.4]} gl={{ antialias: true, powerPreference: "high-performance" }} aria-label="Life OS spatial system">
    <SystemScene {...props} />
  </Canvas>;
}
