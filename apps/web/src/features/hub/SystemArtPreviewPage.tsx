import { Component, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, DepthOfField, EffectComposer } from "@react-three/postprocessing";
import { ArrowLeft, Home, MessageCircle, RotateCcw, Settings } from "lucide-react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import * as THREE from "three";
import { GLTFLoader, type GLTF } from "three/addons/loaders/GLTFLoader.js";
import { RectAreaLightUniformsLib } from "three/addons/lights/RectAreaLightUniformsLib.js";

import { SettingsGravityWell } from "../settings-gravity-well/SettingsGravityWell";
import { spatialDomains, type SpatialDomainId } from "./spatialNavigation";
import { artCameraPose, artworkObjectBounds, fallbackArtCamera, placeArtLabels, placeArtObject, portraitArtCamera, projectArtLabel, type ArtCameraPose } from "./systemArtMotion";
import "./system-art-preview.css";
import { restoreArtworkRim } from "./artRuntimeMaterials";
import { artworkCameraOptics, type ArtCameraOptics } from "./artCameraOptics";
import { artworkSceneryLayers, type ArtSceneryLayer } from "./artSceneryLayers";
import { artworkSourcePowerScale } from "./artSourcePower";
import { artworkSourceColor } from "./artSourceColor";
import { createSpatialAssetResource } from "./spatialAssetResource";
import { CameraJourney, domainCamera, domainMoonFrame, entranceCamera, parentSpatialView, retainDepartingMoons, spatialView, spatialViewParams, type MoonFrame, type SpatialView } from "./spatialJourney";
import { spatialMoonCatalog } from "./spatialMoonCatalog";
import { SelfCore } from "./three/SelfCore";
import { moonKey, SpatialMoons } from "./SpatialMoons";

RectAreaLightUniformsLib.init();

// Blender light RGB values are linear, not sRGB hexadecimal colors.
const ART_LIGHT_COLORS = {
  key: new THREE.Color().setRGB(0.72, 0.82, 1, THREE.LinearSRGBColorSpace),
  rim: new THREE.Color().setRGB(0.24, 0.48, 1, THREE.LinearSRGBColorSpace),
  home: new THREE.Color().setRGB(1, 0.65, 0.33, THREE.LinearSRGBColorSpace),
  machining: new THREE.Color().setRGB(0.75, 0.86, 1, THREE.LinearSRGBColorSpace),
};

const ART_URL = "/art/system/life-os-system-v37.glb";
const ROOT_NAMES = ["SelfCore", "Calendar", "Learning", "Home", "Life", "Fitness"] as const;
type ArtRoot = typeof ROOT_NAMES[number];
type TargetId = string;
type ArtAsset = {
  scene: THREE.Group;
  roots: Record<ArtRoot, THREE.Object3D>;
  bounds: Record<ArtRoot, THREE.Box3>;
  transforms: Record<ArtRoot, { position: THREE.Vector3; scale: THREE.Vector3 }>;
  camera: ArtCameraPose;
  optics: ArtCameraOptics | null;
  cameraWarning: string | null;
  scenery: THREE.Object3D | undefined;
  sceneryLayers: ArtSceneryLayer[];
  sceneryTransform: { position: THREE.Vector3; scale: THREE.Vector3 } | null;
  dispose: () => void;
};
type AssetState = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; asset: ArtAsset };
type Labels = RefObject<Partial<Record<TargetId, HTMLElement>>>;

function ownGltfResources(gltf: GLTF) {
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();
  const skeletons = new Set<THREE.Skeleton>();
  for (const scene of gltf.scenes) scene.traverse(object => {
    const mesh = object as THREE.Mesh;
    if (mesh.geometry) geometries.add(mesh.geometry);
    if (mesh.material) {
      for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
        materials.add(material);
        for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value);
      }
    }
    if (object instanceof THREE.SkinnedMesh) skeletons.add(object.skeleton);
  });
  let disposed = false;
  return () => {
    if (disposed) return;
    disposed = true;
    geometries.forEach(geometry => geometry.dispose());
    materials.forEach(material => material.dispose());
    skeletons.forEach(skeleton => skeleton.dispose());
    const bitmaps = new Set<ImageBitmap>();
    textures.forEach(texture => {
      const images: unknown[] = Array.isArray(texture.source.data) ? texture.source.data : [texture.source.data];
      for (const image of images) if (typeof ImageBitmap !== "undefined" && image instanceof ImageBitmap) bitmaps.add(image);
      texture.dispose();
    });
    bitmaps.forEach(bitmap => bitmap.close());
  };
}

function prepareAsset(gltf: GLTF, dispose: () => void): ArtAsset {
  gltf.scene.updateMatrixWorld(true);
  const roots = {} as ArtAsset["roots"];
  const bounds = {} as ArtAsset["bounds"];
  const transforms = {} as ArtAsset["transforms"];
  for (const name of ROOT_NAMES) {
    const matches: THREE.Object3D[] = [];
    gltf.scene.traverse(object => { if (object.name === name) matches.push(object); });
    if (matches.length !== 1) throw new Error(`Expected one ${name} root; found ${matches.length}.`);
    roots[name] = matches[0];
    transforms[name] = { position: matches[0].position.clone(), scale: matches[0].scale.clone() };
    bounds[name] = artworkObjectBounds(matches[0]);
    if (bounds[name].isEmpty() || ![...bounds[name].min.toArray(), ...bounds[name].max.toArray()].every(Number.isFinite)) {
      throw new Error(`${name} has no usable geometry bounds.`);
    }
  }
  for (const root of Object.values(roots)) {
    for (let parent = root.parent; parent; parent = parent.parent) {
      if (Object.values(roots).includes(parent)) throw new Error("System roots must not be nested inside one another.");
    }
  }
  const cameraNode = gltf.scene.getObjectByName("System_Composition_Camera");
  let authoredCamera: THREE.PerspectiveCamera | undefined;
  cameraNode?.traverse(object => { if (object instanceof THREE.PerspectiveCamera) authoredCamera ??= object; });
  const camera = authoredCamera ? {
    position: authoredCamera.getWorldPosition(new THREE.Vector3()),
    quaternion: authoredCamera.getWorldQuaternion(new THREE.Quaternion()),
    fov: authoredCamera.fov,
  } : fallbackArtCamera();
  const scenery = gltf.scene.getObjectByName("Scenery");
  const artMaterials = new Set<THREE.MeshStandardMaterial>();
  // Keep glTF's Y-up transforms and explicitly authored foreground scenery.
  gltf.scene.traverse(object => {
    if (!(object instanceof THREE.Mesh || object instanceof THREE.Line || object instanceof THREE.Points)) return;
    let namedAncestor = false;
    for (let ancestor: THREE.Object3D | null = object; ancestor; ancestor = ancestor.parent) {
      if (Object.values(roots).includes(ancestor) || ancestor === scenery) { namedAncestor = true; break; }
    }
    if (!namedAncestor) object.visible = false;
    if (object instanceof THREE.Mesh) {
      for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
        if (material instanceof THREE.MeshStandardMaterial) artMaterials.add(material);
      }
    }
  });
  artMaterials.forEach(restoreArtworkRim);
  return {
    scene: gltf.scene, roots, bounds, transforms, camera, scenery, dispose,
    optics: artworkCameraOptics(cameraNode?.userData ?? {}),
    sceneryLayers: artworkSceneryLayers(scenery),
    sceneryTransform: scenery ? { position: scenery.position.clone(), scale: scenery.scale.clone() } : null,
    cameraWarning: authoredCamera ? null : "System_Composition_Camera missing; using fallback framing.",
  };
}

const systemAssetResource = createSpatialAssetResource(async () => {
  const response = await fetch(ART_URL, { cache: "force-cache" });
  if (!response.ok) throw new Error(`Art asset unavailable (HTTP ${response.status}).`);
  const buffer = await response.arrayBuffer();
  if (buffer.byteLength < 12 || new DataView(buffer).getUint32(0, true) !== 0x46546c67) {
    throw new Error(`No valid GLB at ${ART_URL}.`);
  }
  const gltf = await new GLTFLoader().parseAsync(buffer, new URL("/art/system/", window.location.origin).href);
  const dispose = ownGltfResources(gltf);
  try { return { value: prepareAsset(gltf, dispose), dispose }; }
  catch (error) { dispose(); throw error; }
});

function useArtAsset(attempt: number): AssetState {
  const [state, setState] = useState<{ attempt: number; result: AssetState }>({ attempt, result: { status: "loading" } });
  useEffect(() => {
    let active = true;
    setState({ attempt, result: { status: "loading" } });
    const lease = systemAssetResource.acquire();
    void lease.promise.then(asset => {
      if (active) setState({ attempt, result: { status: "ready", asset } });
    }, error => {
      if (active) setState({ attempt, result: { status: "error", message: error instanceof Error ? error.message : "Could not load the system art." } });
    });
    return () => { active = false; lease.release(); };
  }, [attempt]);
  return state.attempt === attempt ? state.result : { status: "loading" };
}

class ArtSceneBoundary extends Component<{ children: ReactNode; onFailure: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onFailure(); }
  render() {
    return this.state.failed ? <div className="system-art-render-fallback" role="status">3D preview unavailable.</div> : this.props.children;
  }
}

function RendererUnavailable({ onFailure }: { onFailure: () => void }) {
  useEffect(onFailure, [onFailure]);
  return <div className="system-art-render-fallback" role="status">WebGL unavailable.</div>;
}

function FrameSnapshots() {
  const { gl } = useThree();
  const sample = useRef({ frames: 0, since: 0, calls: 0, triangles: 0 });
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    const previous = gl.info.autoReset;
    gl.info.autoReset = false;
    sample.current.since = performance.now();
    const timer = window.setInterval(() => {
      const now = performance.now();
      const stats = sample.current;
      gl.domElement.dataset.fps = (stats.frames * 1000 / Math.max(1, now - stats.since)).toFixed(1);
      stats.frames = 0;
      stats.since = now;
    }, 2000);
    return () => { window.clearInterval(timer); gl.info.autoReset = previous; };
  }, [gl]);
  useFrame(() => { if (import.meta.env.DEV) gl.info.reset(); }, -1);
  // Composer renders at priority 1. Read all passes afterward, without React updates.
  useFrame(() => {
    if (!import.meta.env.DEV) return;
    const stats = sample.current;
    stats.frames++;
    stats.calls = gl.info.render.calls;
    stats.triangles = gl.info.render.triangles;
    gl.domElement.dataset.fps ??= "0.0";
    gl.domElement.dataset.drawCalls = String(stats.calls);
    gl.domElement.dataset.triangles = String(stats.triangles);
  }, 2);
  return null;
}

function ArtScene({ asset, view, labels, reducedMotion, host, onPrepared, onFailure, onSelect, onMoon }: {
  asset: ArtAsset | null; view: SpatialView; labels: Labels; reducedMotion: boolean;
  host: RefObject<HTMLElement | null>; onPrepared: (ready: boolean) => void; onFailure: () => void;
  onSelect: (view: SpatialView) => void;
  onMoon: (href: string) => void;
}) {
  const { camera, size, gl, scene, invalidate } = useThree();
  const well = useRef<THREE.Group>(null);
  const provisional = useRef<THREE.Group>(null);
  const system = view.depth !== "core";
  const portrait = size.width / size.height < 0.8;
  const motion = useRef<CameraJourney | null>(null);
  const labelElapsed = useRef(1);
  const idleTime = useRef(0);
  const orbitPositions = useRef<Partial<Record<ArtRoot, THREE.Vector3>>>({});
  const orbitTimes = useRef<Partial<Record<ArtRoot, number>>>({});
  const [prepared, setPrepared] = useState(false);
  const [departingDomains, setDepartingDomains] = useState<SpatialDomainId[]>([]);
  const lastDomain = useRef<SpatialDomainId | null>(view.depth === "domain" ? view.domain : null);
  const sourcePowerScale = asset?.roots.SelfCore.userData.art_portrait_source_power_scale;
  const portraitSourceScale = typeof sourcePowerScale === "number" && Number.isFinite(sourcePowerScale)
    && sourcePowerScale > 0 && sourcePowerScale <= 1 ? sourcePowerScale : 1;
  const [placedBounds, setPlacedBounds] = useState<ArtAsset["bounds"] | null>(null);
  useLayoutEffect(() => {
    if (!asset) { setPlacedBounds(null); return; }
    const bounds = {} as ArtAsset["bounds"];
    for (const name of ROOT_NAMES) {
      const root = asset.roots[name];
      placeArtObject(root, asset.transforms[name], portrait);
      orbitPositions.current[name] = root.position.clone();
      orbitTimes.current[name] = 0;
      bounds[name] = artworkObjectBounds(root);
    }
    if (asset.scenery && asset.sceneryTransform) {
      placeArtObject(asset.scenery, asset.sceneryTransform, portrait);
    }
    asset.sceneryLayers.forEach(layer => placeArtObject(layer.root, layer.authored, portrait));
    asset.scene.updateMatrixWorld(true);
    setPlacedBounds(bounds);
    invalidate();
  }, [asset, portrait, invalidate]);
  const composition = useMemo(() => {
    const objectBounds = placedBounds ?? asset?.bounds;
    const coreBox = objectBounds?.SelfCore ?? new THREE.Box3(new THREE.Vector3(-1, -1, -1), new THREE.Vector3(1, 1, 1));
    const coreCenter = coreBox.getCenter(new THREE.Vector3());
    const scale = 0.45;
    const position = new THREE.Vector3(0, -2.05, -0.6);
    const wellBox = new THREE.Box3().setFromCenterAndSize(position, new THREE.Vector3().setScalar(scale * 7.2));
    const bounds = system ? coreBox.clone() : coreBox.clone().union(wellBox);
    if (objectBounds && system) ROOT_NAMES.forEach(name => bounds.union(objectBounds[name]));
    const authoredPose = portrait ? portraitArtCamera() : asset?.camera ?? fallbackArtCamera();
    const frames: Partial<Record<SpatialDomainId, MoonFrame>> = {};
    if (objectBounds) spatialDomains.forEach(domain => {
      const box = asset ? artworkObjectBounds(asset.roots[domain.label as ArtRoot]) : objectBounds[domain.label as ArtRoot];
      frames[domain.id] = domainMoonFrame(box, coreCenter);
    });
    const frame = view.depth === "domain" ? frames[view.domain] : undefined;
    const pose = !system || !asset ? entranceCamera(size) : frame ? domainCamera(frame, size)
      : artCameraPose(bounds, authoredPose, size, true);
    const targets: { id: TargetId; box: THREE.Box3 }[] = view.depth === "domain" ? [] : [
      { id: "SelfCore", box: asset ? coreBox : new THREE.Box3(new THREE.Vector3(-0.7, -0.3, -0.7), new THREE.Vector3(0.7, 1, 0.7)) },
      ...(!system ? [{ id: "Settings", box: wellBox }] : []),
    ];
    if (objectBounds && view.depth === "system") ROOT_NAMES.slice(1).forEach(id => targets.push({ id, box: objectBounds[id] }));
    return { position, scale, pose, bounds, targets, coreCenter, frames };
  }, [asset, placedBounds, portrait, system, view.depth, view.depth === "domain" ? view.domain : null, size.width, size.height]);

  useEffect(() => {
    let active = true;
    let frameId = 0;
    setPrepared(false);
    onPrepared(false);
    if (!asset) return;
    const textures = new Set<THREE.Texture>();
    asset.scene.traverse(object => {
      if (!(object instanceof THREE.Mesh)) return;
      for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
        for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value);
      }
    });
    const pending = [...textures];
    const warm = () => {
      if (!active) return;
      try {
        const texture = pending.shift();
        if (texture) { gl.initTexture(texture); frameId = requestAnimationFrame(warm); return; }
        void gl.compileAsync(scene, camera).then(() => {
          if (active) { setPrepared(true); onPrepared(true); invalidate(); }
        }, () => { if (active) onFailure(); });
      } catch { onFailure(); }
    };
    // Warm one texture per frame behind the entrance instead of uploading all on entry.
    frameId = requestAnimationFrame(warm);
    return () => { active = false; cancelAnimationFrame(frameId); };
  }, [asset, camera, gl, scene, onPrepared, onFailure, invalidate]);

  useLayoutEffect(() => {
    const destination = prepared || !system ? composition.pose : entranceCamera(size);
    if (!motion.current) motion.current = new CameraJourney(destination);
    else motion.current.travelTo(destination, reducedMotion);
    labelElapsed.current = 1;
    invalidate();
  }, [composition, prepared, system, reducedMotion, invalidate]);

  useLayoutEffect(() => {
    const next = view.depth === "domain" ? view.domain : null;
    const previous = lastDomain.current;
    if (reducedMotion || previous && previous !== next) {
      setDepartingDomains(current => retainDepartingMoons(current, previous, next, reducedMotion));
    }
    lastDomain.current = next;
  }, [view.depth, view.depth === "domain" ? view.domain : null, reducedMotion]);

  useEffect(() => { invalidate(); }, [composition, invalidate]);
  useEffect(() => {
    if (!host.current) return;
    host.current.dataset.assetPrepared = String(prepared);
  }, [host, prepared]);
  useEffect(() => {
    const lost = (event: Event) => { event.preventDefault(); onFailure(); };
    gl.domElement.addEventListener("webglcontextlost", lost);
    return () => gl.domElement.removeEventListener("webglcontextlost", lost);
  }, [gl, onFailure]);
  useFrame((_, delta) => {
    if (!(camera instanceof THREE.PerspectiveCamera)) return;
    const journey = motion.current;
    const pose = journey?.sample(Math.min(delta, 0.15)) ?? composition.pose;
    if (!journey?.moving && departingDomains.length) setDepartingDomains([]);
    camera.position.copy(pose.position);
    camera.quaternion.copy(pose.quaternion);
    camera.fov = pose.fov;
    camera.aspect = size.width / size.height;
    camera.near = 0.05;
    camera.far = Math.max(100, camera.position.distanceTo(composition.bounds.getCenter(new THREE.Vector3())) + composition.bounds.getSize(new THREE.Vector3()).length() * 2);
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld(true);
    const showSystem = prepared && (system || !!journey?.moving);
    if (asset) ROOT_NAMES.forEach(name => { asset.roots[name].visible = prepared && (name === "SelfCore" || showSystem); });
    if (asset?.scenery) asset.scenery.visible = showSystem;
    if (provisional.current) provisional.current.visible = !prepared;
    if (!reducedMotion) idleTime.current += Math.min(delta, 0.05);
    if (asset && prepared) {
      const baseline = asset.transforms.SelfCore.scale;
      const tall = portrait ? asset.roots.SelfCore.userData.art_portrait_scale : 1;
      const portraitScale = typeof tall === "number" && Number.isFinite(tall) ? tall : 1;
      asset.roots.SelfCore.scale.copy(baseline).multiplyScalar(portraitScale * (reducedMotion ? 1 : 1 + Math.sin(idleTime.current * 0.35) * 0.012));
      if (!reducedMotion && !journey?.moving) spatialDomains.forEach(domain => {
        if (view.depth === "domain" && view.domain === domain.id) return;
        const name = domain.label as ArtRoot;
        const base = orbitPositions.current[name];
        if (!base) return;
        const time = (orbitTimes.current[name] ?? 0) + Math.min(delta, 0.05);
        orbitTimes.current[name] = time;
        const angle = time * 0.00008;
        const dx = base.x - composition.coreCenter.x;
        const dz = base.z - composition.coreCenter.z;
        asset.roots[name].position.set(composition.coreCenter.x + dx * Math.cos(angle) - dz * Math.sin(angle), base.y,
          composition.coreCenter.z + dx * Math.sin(angle) + dz * Math.cos(angle));
      });
    }
    if (well.current) well.current.quaternion.copy(camera.quaternion);
    if (well.current) well.current.visible = !system || !!journey?.moving && journey.progress < 0.55;
    if (host.current) {
      host.current.dataset.moving = String(!!journey?.moving);
      host.current.style.setProperty("--travel", String(journey?.moving && !reducedMotion ? Math.sin(journey.progress * Math.PI) : 0));
    }
    labelElapsed.current += delta;
    if (journey?.moving) {
      for (const element of Object.values(labels.current)) {
        if (element?.dataset.projected) delete element.dataset.projected;
      }
      return;
    }
    if (labelElapsed.current < 0.08) return;
    labelElapsed.current = 0;
    const targets = composition.targets.filter(target => target.id === "Settings" || prepared || target.id === "SelfCore")
      .map(target => asset && ROOT_NAMES.includes(target.id as ArtRoot)
        ? { ...target, box: artworkObjectBounds(asset.roots[target.id as ArtRoot]) } : target);
    if (view.depth === "domain" && prepared) {
      const frame = composition.frames[view.domain];
      if (frame) for (const moon of spatialMoonCatalog[view.domain]) {
        const object = scene.getObjectByName(moonKey(view.domain, moon.id));
        if (!object) continue;
        const center = object.getWorldPosition(new THREE.Vector3());
        targets.push({ id: moonKey(view.domain, moon.id), box: new THREE.Box3().setFromCenterAndSize(center, new THREE.Vector3().setScalar(frame.radius * 0.5)) });
      }
    }
    const anchors = targets.map(target => projectArtLabel(target.id, target.box, camera, size));
    for (const anchor of placeArtLabels(anchors, size)) {
      const element = labels.current[anchor.id as TargetId];
      if (!element) continue;
      element.style.transform = `translate(${Math.round(anchor.x)}px, ${Math.round(anchor.y)}px) translate(-50%, -50%)`;
      element.dataset.projected = "true";
    }
  }, -2);

  return <>
    <ambientLight intensity={0.06} />
    <rectAreaLight position={[-6, 5.5, 4]} intensity={6} color={ART_LIGHT_COLORS.key} width={4} height={4}
      onUpdate={light => light.lookAt(0, 0, 0)} />
    <rectAreaLight position={[2, 3, -7]} intensity={4.31} color={ART_LIGHT_COLORS.rim} width={3} height={3}
      onUpdate={light => light.lookAt(0, 0, 0)} />
    <rectAreaLight position={[8.5, 3, -3.5]} intensity={9.09} color={ART_LIGHT_COLORS.home} width={3} height={3}
      onUpdate={light => light.lookAt(0, 0, 0)} />
    <rectAreaLight position={[7.5, 1.7, 6.5]} intensity={2.3} color={ART_LIGHT_COLORS.machining} width={1.8} height={0.5}
      onUpdate={light => light.lookAt(4.9, -0.25, 3.55)} />
    <pointLight position={[0, 0.5, 0]} intensity={206.73 * artworkSourcePowerScale(asset?.roots.SelfCore.userData ?? {})
      * (portrait ? portraitSourceScale : 1)} color={new THREE.Color().setRGB(
        ...artworkSourceColor(asset?.roots.SelfCore.userData ?? {}), THREE.LinearSRGBColorSpace)} decay={2} />
    {asset && <primitive object={asset.scene} dispose={null} onClick={(event: { object: THREE.Object3D; stopPropagation: () => void }) => {
      if (motion.current?.moving || !prepared) return;
      for (let object: THREE.Object3D | null = event.object; object; object = object.parent) {
        if (object.name === "SelfCore") { event.stopPropagation(); onSelect({ depth: "system" }); return; }
        const domain = spatialDomains.find(item => item.label === object?.name);
        if (domain) { event.stopPropagation(); onSelect({ depth: "domain", domain: domain.id }); return; }
      }
    }} />}
    <group ref={provisional} position={[0, 0.35, 0]} onClick={() => onSelect({ depth: "system" })}>
      <SelfCore quality="navigation" scale={2.1} orbitSpread={0.75} reducedMotion={reducedMotion} showParticles={false} />
    </group>
    <SpatialMoons frames={composition.frames} activeDomains={prepared ? [
      ...(view.depth === "domain" ? [view.domain] : []), ...departingDomains,
    ] : []} reducedMotion={reducedMotion}
      selectableDomain={view.depth === "domain" && prepared ? view.domain : null}
      onSelect={href => { if (!motion.current?.moving) onMoon(href); }} />
    <group ref={well} position={composition.position} scale={composition.scale} visible={!system}>
      <SettingsGravityWell quality="navigation" reducedMotion={reducedMotion} flowDensity={28} haloIntensity={0.6} />
    </group>
    <EffectComposer multisampling={0} enableNormalPass={false}>
      {view.depth === "system" && asset?.optics && <DepthOfField target={composition.coreCenter}
        focusRange={asset.optics.focusRange} bokehScale={asset.optics.bokehScale * (portrait ? 0.55 : 1)}
        resolutionScale={0.5} />}
      <Bloom intensity={0.8} luminanceThreshold={0.6} luminanceSmoothing={0.25} resolutionScale={0.5} resolutionX={512} resolutionY={512} mipmapBlur />
    </EffectComposer>
    <FrameSnapshots />
  </>;
}

export function SystemArtPreviewPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const view = spatialView(params);
  const host = useRef<HTMLElement>(null);
  const backButton = useRef<HTMLButtonElement>(null);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [visible, setVisible] = useState(() => !document.hidden);
  const [attempt, setAttempt] = useState(0);
  const state = useArtAsset(attempt);
  const [sceneFailed, setSceneFailed] = useState(false);
  const [prepared, setPrepared] = useState(false);
  const labels = useRef<Partial<Record<TargetId, HTMLElement>>>({});
  const onFailure = useCallback(() => { setPrepared(false); setSceneFailed(true); }, []);
  const onPrepared = useCallback((ready: boolean) => setPrepared(ready), []);
  const ready = state.status === "ready" && prepared && !sceneFailed;
  const changeView = useCallback((next: SpatialView) => { setParams(spatialViewParams(next)); backButton.current?.focus(); }, [setParams]);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const changed = () => setReducedMotion(media.matches);
    const visibility = () => setVisible(!document.hidden);
    media.addEventListener("change", changed);
    document.addEventListener("visibilitychange", visibility);
    return () => { media.removeEventListener("change", changed); document.removeEventListener("visibilitychange", visibility); };
  }, []);
  useEffect(() => {
    const back = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || view.depth === "core") return;
      if ((event.target as HTMLElement)?.matches?.("input, textarea, select, [contenteditable=true]")) return;
      event.preventDefault();
      changeView(parentSpatialView(view));
    };
    window.addEventListener("keydown", back);
    return () => window.removeEventListener("keydown", back);
  }, [view.depth, view.depth === "domain" ? view.domain : null, changeView]);
  const retry = () => { setPrepared(false); setSceneFailed(false); setAttempt(value => value + 1); };
  const message = sceneFailed ? "3D preview unavailable on this device."
    : state.status === "loading" ? "Preparing system"
    : state.status === "error" ? state.message : !prepared ? "Preparing system" : state.asset.cameraWarning;
  const selected = view.depth === "domain" ? spatialDomains.find(domain => domain.id === view.domain) : null;
  const openMoon = (href: string) => navigate(href, { state: { spatialReturn: location.pathname + `?${spatialViewParams(view)}` } });

  return <main ref={host} className="system-art-preview" aria-label="Life OS spatial workspace" data-depth={view.depth} data-ready={ready}>
    <img key={attempt} className="system-art-background" src="/art/system/deep-space-v1.png" alt="" onError={event => { event.currentTarget.hidden = true; }} />
    <div className="system-art-stage">
      <ArtSceneBoundary key={attempt} onFailure={onFailure}>
        {!sceneFailed && <Canvas frameloop={reducedMotion || !visible ? "demand" : "always"} dpr={[1, 1.4]} camera={{ fov: 42, position: [0, 1.5, 8], near: 0.05, far: 200 }}
          onCreated={({ gl }) => { gl.toneMapping = THREE.AgXToneMapping; }}
          gl={{ alpha: true, antialias: false, powerPreference: "high-performance" }}
          fallback={<RendererUnavailable onFailure={onFailure} />}
          aria-label="Life OS system art canvas">
          <ArtScene asset={state.status === "ready" ? state.asset : null} view={view} labels={labels}
            reducedMotion={reducedMotion || !visible} host={host} onPrepared={onPrepared} onFailure={onFailure} onSelect={changeView} onMoon={openMoon} />
        </Canvas>}
      </ArtSceneBoundary>
    </div>
    <header className="system-art-header">
      <nav aria-label="Spatial navigation">
        <button ref={backButton} className="system-art-icon" type="button" aria-label="Back" title="Back" disabled={view.depth === "core"} onClick={() => {
          if (view.depth !== "core") changeView(parentSpatialView(view));
        }}><ArrowLeft size={18} /></button>
        <Link className="system-art-icon" to="/" aria-label="Life OS home" title="Life OS home"><Home size={18} /></Link>
      </nav>
      <h1>{selected?.label ?? "Life OS"}</h1>
      <nav aria-label="Quick access">
        <Link className="system-art-icon" to="/self" aria-label="Talk to Self Core" title="Talk to Self Core"><MessageCircle size={18} /></Link>
        <Link className="system-art-icon" to="/settings" aria-label="Settings" title="Settings"><Settings size={18} /></Link>
      </nav>
    </header>
    <nav className="system-art-labels" aria-label="System objects" hidden={sceneFailed}>
      {view.depth !== "domain" && <button ref={element => { labels.current.SelfCore = element ?? undefined; }} className="system-art-label" type="button"
        aria-label="Explore solar system" onClick={() => changeView({ depth: "system" })}>Self Core</button>}
      {view.depth === "core" && <Link ref={element => { labels.current.Settings = element ?? undefined; }} className="system-art-label" to="/settings">Settings</Link>}
      {view.depth === "system" && ready && spatialDomains.map(domain => <button key={domain.id} type="button"
        ref={element => { labels.current[domain.label as ArtRoot] = element ?? undefined; }}
        className="system-art-label" aria-label={`Explore ${domain.label}`} onClick={() => changeView({ depth: "domain", domain: domain.id })}>{domain.label}</button>)}
      {view.depth === "domain" && ready && spatialMoonCatalog[view.domain].map(moon => moon.href
        ? <Link key={moon.id} ref={element => { labels.current[moonKey(view.domain, moon.id)] = element ?? undefined; }} className="system-art-label" to={moon.href}
          state={{ spatialReturn: location.pathname + `?${spatialViewParams(view)}` }}>{moon.label}</Link>
        : <button key={moon.id} ref={element => { labels.current[moonKey(view.domain, moon.id)] = element ?? undefined; }} className="system-art-label" type="button" aria-disabled="true" title={`${moon.label} workspace is not built yet`}>{moon.label}<span className="system-art-planned">Pending</span></button>)}
    </nav>
    <footer className="system-art-footer">
      {message && <div className="system-art-status" role={state.status === "error" || sceneFailed ? "alert" : "status"}>
        <span>{message}</span>
        {(state.status === "error" || sceneFailed) && <button className="system-art-icon" type="button" onClick={retry} aria-label="Retry art preview" title="Retry art preview"><RotateCcw size={18} /></button>}
      </div>}
      {!ready && <>
        <nav className="system-art-fallback-links" aria-label="Domain pages">
          {spatialDomains.map(domain => <Link key={domain.id} to={domain.path}
            state={{ spatialReturn: location.pathname + `?${spatialViewParams(view)}` }}>{domain.label}</Link>)}
        </nav>
        {view.depth === "domain" && <nav className="system-art-fallback-links" aria-label="Moon pages">
          {spatialMoonCatalog[view.domain].map(moon => moon.href
            ? <Link key={moon.id} to={moon.href} state={{ spatialReturn: location.pathname + `?${spatialViewParams(view)}` }}>{moon.label}</Link>
            : <span key={moon.id}>{moon.label} (planned)</span>)}
        </nav>}
      </>}
      {!message && <span className="system-art-depth">{selected?.identity ?? (view.depth === "system" ? "Primary system" : "Self Core")}</span>}
    </footer>
  </main>;
}

export default SystemArtPreviewPage;
