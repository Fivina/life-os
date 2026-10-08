import { Box3, Quaternion, Vector3 } from "three";
import { describe, expect, it } from "vitest";
import { CameraJourney, domainCamera, domainMoonFrame, entranceCamera, moonPosition, parentSpatialView, retainDepartingMoons, spatialReturnPath, spatialView, spatialViewParams, TRAVEL_SECONDS } from "./spatialJourney";

describe("continuous spatial journey", () => {
  it("retains departing moons through rapid retargets and clears them for reduced motion", () => {
    const first = retainDepartingMoons([], "calendar", "life", false);
    const second = retainDepartingMoons(first, "life", "fitness", false);
    expect(second).toEqual(["calendar", "life"]);
    expect(retainDepartingMoons(second, "life", "home", false)).toEqual(second);
    expect(retainDepartingMoons(second, "fitness", null, true)).toEqual([]);
  });
  it("keeps workspace returns internal and discards unsupported URL state", () => {
    expect(spatialReturnPath("/")).toBe("/");
    expect(spatialReturnPath("/?depth=domain&domain=home&arbitrary=1")).toBe("/?depth=domain&domain=home");
    expect(spatialReturnPath("/space?depth=domain&domain=home&arbitrary=1")).toBe("/space?depth=domain&domain=home");
    expect(spatialReturnPath("/_dev/system-art?depth=system")).toBe("/_dev/system-art?depth=system");
    for (const path of ["https://evil.example/space", "//evil.example", "/space/unknown", "/kitchen", "/?depth=system#ignored", {}, null]) expect(spatialReturnPath(path)).toBeNull();
  });
  it("round-trips the three URL-backed layers and rejects unknown destinations", () => {
    for (const view of [{ depth: "core" }, { depth: "system" }, { depth: "domain", domain: "fitness" }] as const) {
      expect(spatialView(spatialViewParams(view))).toEqual(view);
    }
    expect(spatialView(new URLSearchParams("depth=domain&domain=unknown"))).toEqual({ depth: "core" });
    expect(parentSpatialView({ depth: "domain", domain: "life" })).toEqual({ depth: "system" });
    expect(parentSpatialView({ depth: "system" })).toEqual({ depth: "core" });
  });
  it("arrives exactly and retargets without jumping or mutating caller poses", () => {
    const start = { position: new Vector3(), quaternion: new Quaternion(), fov: 42 };
    const target = { ...start, position: new Vector3(10, 0, 0), fov: 48 };
    const journey = new CameraJourney(start);
    journey.travelTo(target);
    expect(journey.sample(TRAVEL_SECONDS / 2).position.x).toBeCloseTo(5);
    journey.travelTo(start);
    expect(journey.pose.position.x).toBeCloseTo(5);
    expect(journey.sample(TRAVEL_SECONDS).position).toEqual(start.position);
    expect(journey.moving).toBe(false);
    expect(target.position.x).toBe(10);
    expect(start.position.x).toBe(0);
  });
  it("reduced motion arrives immediately and invalid deltas never corrupt the camera", () => {
    const pose = entranceCamera({ width: 390, height: 844 });
    const journey = new CameraJourney(pose);
    const next = { ...pose, position: new Vector3(2, 3, 4) };
    journey.travelTo(next, true);
    expect(journey.pose.position).toEqual(next.position);
    expect(journey.moving).toBe(false);
    journey.sample(NaN);
    expect(journey.pose.position.toArray().every(Number.isFinite)).toBe(true);
  });
  it("does not replay travel or unlock visibility for an unchanged destination", () => {
    const pose = entranceCamera({ width: 1440, height: 900 });
    const journey = new CameraJourney(pose);
    journey.travelTo(pose);
    expect(journey.moving).toBe(false);
    expect(journey.progress).toBe(1);
  });
  it("approaches a planet from outside the system and keeps slow moon motion bounded", () => {
    const box = new Box3(new Vector3(4, -1, 2), new Vector3(6, 1, 4));
    const frame = domainMoonFrame(box, new Vector3());
    const camera = domainCamera(frame, { width: 1440, height: 900 });
    expect(camera.position.clone().sub(frame.center).dot(frame.center)).toBeGreaterThan(0);
    expect(frame.right.dot(frame.up)).toBeCloseTo(0);
    const before = moonPosition(frame, 0, 5);
    expect(before.distanceTo(moonPosition(frame, 0, 5, 1))).toBeLessThan(frame.radius * 0.025);
    expect(camera.position.toArray().every(Number.isFinite)).toBe(true);
  });
});
