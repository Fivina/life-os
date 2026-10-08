import { Box3, MathUtils, PerspectiveCamera, Quaternion, Vector3 } from "three";
import { spatialDomains, smoothTravel, type SpatialDomainId } from "./spatialNavigation";
import { fitArtCamera, type ArtCameraPose, type ArtViewport } from "./systemArtMotion";

export type SpatialView = { depth: "core" } | { depth: "system" } | { depth: "domain"; domain: SpatialDomainId };
export const TRAVEL_SECONDS = 1.15;

export function spatialView(params: URLSearchParams): SpatialView {
  const domain = params.get("domain");
  if (params.get("depth") === "domain" && spatialDomains.some(item => item.id === domain)) {
    return { depth: "domain", domain: domain as SpatialDomainId };
  }
  return params.get("depth") === "system" ? { depth: "system" } : { depth: "core" };
}

export function spatialViewParams(view: SpatialView) {
  return new URLSearchParams(view.depth === "core" ? {} : view.depth === "system"
    ? { depth: "system" } : { depth: "domain", domain: view.domain });
}

export function parentSpatialView(view: SpatialView): SpatialView {
  return { depth: view.depth === "domain" ? "system" : "core" };
}

export function spatialReturnPath(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const match = value.match(/^(\/|\/space|\/_dev\/system-art)(?:\?([^#]*))?$/);
  if (!match) return null;
  const params = spatialViewParams(spatialView(new URLSearchParams(match[2] ?? "")));
  return match[1] + (params.size ? `?${params}` : "");
}

export function retainDepartingMoons(current: readonly SpatialDomainId[], previous: SpatialDomainId | null, next: SpatialDomainId | null, immediate: boolean): SpatialDomainId[] {
  if (immediate) return [];
  return previous && previous !== next ? [...new Set([...current, previous])] : [...current];
}

export function clonePose(pose: ArtCameraPose): ArtCameraPose {
  return { position: pose.position.clone(), quaternion: pose.quaternion.clone(), fov: pose.fov };
}

export function entranceCamera(viewport: ArtViewport): ArtCameraPose {
  const camera = new PerspectiveCamera(42);
  camera.position.set(0, 1.5, 8);
  camera.lookAt(0, -0.7, 0);
  const bounds = new Box3(new Vector3(-1.65, -3.4, -0.8), new Vector3(1.65, 1.55, 0.8));
  return fitArtCamera(bounds, { position: camera.position.clone(), quaternion: camera.quaternion.clone(), fov: 42 }, viewport);
}

export type MoonFrame = { center: Vector3; right: Vector3; up: Vector3; backward: Vector3; radius: number };

export function domainMoonFrame(box: Box3, core: Vector3): MoonFrame {
  const center = box.getCenter(new Vector3());
  const size = box.getSize(new Vector3());
  const radius = Math.max(0.65, Math.max(size.x, size.y, size.z) * 0.62);
  // Approach from outside the system: Core and the other planets stay behind the destination.
  const backward = center.clone().sub(core);
  backward.y = Math.max(radius * 0.45, backward.length() * 0.32);
  if (backward.lengthSq() < 0.001) backward.set(0, 0.4, 1);
  backward.normalize();
  const right = new Vector3().crossVectors(new Vector3(0, 1, 0), backward).normalize();
  const up = new Vector3().crossVectors(backward, right).normalize();
  return { center, radius, right, up, backward };
}

export function moonPosition(frame: MoonFrame, index: number, count: number, time = 0): Vector3 {
  const angle = Math.PI * 0.25 + index / Math.max(1, count) * Math.PI * 2 + time * 0.008;
  return frame.center.clone().addScaledVector(frame.right, Math.cos(angle) * frame.radius * 2.05)
    .addScaledVector(frame.up, Math.sin(angle) * frame.radius * 1.3)
    .addScaledVector(frame.backward, Math.sin(angle) * frame.radius * 0.28);
}

export function domainCamera(frame: MoonFrame, viewport: ArtViewport): ArtCameraPose {
  const box = new Box3();
  for (let index = 0; index < 8; index++) {
    const point = moonPosition(frame, index, 8);
    const half = new Vector3().setScalar(frame.radius * 0.27);
    box.union(new Box3(point.clone().sub(half), point.clone().add(half)));
  }
  const camera = new PerspectiveCamera(48);
  camera.position.copy(frame.center).addScaledVector(frame.backward, frame.radius * 7);
  camera.lookAt(frame.center);
  return fitArtCamera(box, { position: camera.position.clone(), quaternion: camera.quaternion.clone(), fov: 48 }, viewport);
}

/** Retargeting starts at the sampled pose, including during back/resize; no input lock. */
export class CameraJourney {
  readonly pose: ArtCameraPose;
  private from: ArtCameraPose;
  private target: ArtCameraPose;
  private elapsed = TRAVEL_SECONDS;

  constructor(pose: ArtCameraPose) {
    this.pose = clonePose(pose);
    this.from = clonePose(pose);
    this.target = clonePose(pose);
  }

  travelTo(target: ArtCameraPose, immediate = false) {
    this.from = clonePose(this.pose);
    this.target = clonePose(target);
    const unchanged = this.pose.position.distanceToSquared(target.position) < 1e-12
      && this.pose.quaternion.angleTo(target.quaternion) < 1e-6 && Math.abs(this.pose.fov - target.fov) < 1e-6;
    this.elapsed = immediate || unchanged ? TRAVEL_SECONDS : 0;
    this.sample(0);
  }

  get moving() { return this.elapsed < TRAVEL_SECONDS; }
  get progress() { return MathUtils.clamp(this.elapsed / TRAVEL_SECONDS, 0, 1); }

  sample(delta: number): ArtCameraPose {
    this.elapsed = Math.min(TRAVEL_SECONDS, this.elapsed + Math.max(0, Number.isFinite(delta) ? delta : 0));
    const eased = smoothTravel(this.progress);
    this.pose.position.lerpVectors(this.from.position, this.target.position, eased);
    this.pose.quaternion.slerpQuaternions(this.from.quaternion, this.target.quaternion, eased);
    this.pose.fov = MathUtils.lerp(this.from.fov, this.target.fov, eased);
    return this.pose;
  }
}
