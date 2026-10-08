import { useEffect, useState, type ReactNode } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import * as THREE from "three";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const runtime = vi.hoisted(() => ({
  mounts: 0, unmounts: 0, three: null as unknown,
  frames: new Set<{ callback: (state: unknown, delta: number) => void; priority: number }>(),
}));
vi.mock("@react-three/fiber", () => ({
  Canvas: ({ children }: { children: ReactNode }) => {
    useState(() => { runtime.mounts++; return 0; });
    useEffect(() => () => { runtime.unmounts++; }, []);
    return <div data-testid="canvas-host">{children}</div>;
  },
  useThree: () => runtime.three,
  // Explicitly stepped callbacks exercise scene logic, not rendering or GPU performance.
  useFrame: (callback: (state: unknown, delta: number) => void, priority = 0) => {
    useEffect(() => {
      const frame = { callback, priority };
      runtime.frames.add(frame);
      return () => { runtime.frames.delete(frame); };
    }, [callback, priority]);
  },
}));
vi.mock("@react-three/postprocessing", () => ({
  EffectComposer: ({ children }: { children: ReactNode }) => <>{children}</>, Bloom: () => null, DepthOfField: () => null,
}));
vi.mock("./three/SelfCore", () => ({ SelfCore: () => null }));
vi.mock("../settings-gravity-well/SettingsGravityWell", () => ({ SettingsGravityWell: () => null }));
vi.mock("./SpatialMoons", () => ({ SpatialMoons: () => null, moonKey: (domain: string, id: string) => `moon:${domain}:${id}` }));
vi.mock("three/addons/loaders/GLTFLoader.js", () => ({
  GLTFLoader: class {
    async parseAsync() {
      const scene = new THREE.Group();
      ["SelfCore", "Calendar", "Learning", "Home", "Life", "Fitness"].forEach((name, index) => {
        const root = new THREE.Group(); root.name = name;
        root.position.set(index * 2, index % 2, index);
        root.add(new THREE.Mesh(new THREE.SphereGeometry(0.5, 8, 6), new THREE.MeshStandardMaterial()));
        scene.add(root);
      });
      const camera = new THREE.PerspectiveCamera(42); camera.name = "System_Composition_Camera";
      camera.position.set(0, 12.5, 19.5); camera.lookAt(0, 0, 0); scene.add(camera);
      return { scene, scenes: [scene] };
    }
  },
}));

import { SystemArtPreviewPage } from "./SystemArtPreviewPage";
import { spatialMoonCatalog } from "./spatialMoonCatalog";
import { spatialDomains } from "./spatialNavigation";

function Location() {
  const location = useLocation();
  return <output data-testid="route" data-return={location.state?.spatialReturn}>{location.pathname}{location.search}{location.hash}</output>;
}

function stepFrames(count = 1) {
  // DOM-backed R3F groups need the one Three.js field used by the well billboard.
  document.querySelectorAll("group").forEach(group => {
    if (!("quaternion" in group)) Object.assign(group, { quaternion: new THREE.Quaternion() });
  });
  act(() => {
    for (let index = 0; index < count; index++) {
      [...runtime.frames].sort((a, b) => a.priority - b.priority)
        .forEach(frame => frame.callback(runtime.three, 1 / 60));
    }
  });
}

describe("spatial page routing", () => {
  beforeEach(() => {
    runtime.mounts = 0; runtime.unmounts = 0; runtime.frames.clear();
    const canvas = document.createElement("canvas");
    runtime.three = {
      camera: new THREE.PerspectiveCamera(), scene: new THREE.Scene(), size: { width: 1440, height: 900 }, invalidate: vi.fn(),
      gl: { domElement: canvas, initTexture: vi.fn(), compileAsync: vi.fn(async () => {}), info: { autoReset: true, reset: vi.fn(), render: { calls: 0, triangles: 0 } } },
    };
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
    const glb = new ArrayBuffer(12); new DataView(glb).setUint32(0, 0x46546c67, true);
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, arrayBuffer: async () => glb })));
    vi.spyOn(console, "error").mockImplementation(() => {}); // DOM cannot interpret R3F intrinsic elements.
  });
  afterEach(() => {
    vi.restoreAllMocks(); vi.unstubAllGlobals();
  });

  it("keeps one Canvas/load through core-system-domain-back and opens genuine moon routes", async () => {
    render(<MemoryRouter initialEntries={["/space"]}><Location /><Routes>
      <Route path="/space" element={<SystemArtPreviewPage />} />
      <Route path="*" element={<h2>Existing workspace</h2>} />
    </Routes></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Explore solar system", hidden: true }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Explore Home", hidden: true })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Explore Home", hidden: true }));
    expect(screen.getByTestId("route")).toHaveTextContent("/space?depth=domain&domain=home");
    expect(screen.getByRole("button", { name: /Cleaning/, hidden: true })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("link", { name: "Shopping", hidden: true })).toHaveAttribute("href", "/kitchen#shopping");
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByTestId("route")).toHaveTextContent("/space?depth=system");
    fireEvent.click(screen.getByRole("button", { name: "Explore Fitness", hidden: true }));
    expect(runtime.mounts).toBe(1);
    expect(runtime.unmounts).toBe(0);
    expect(fetch).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("link", { name: "Training", hidden: true }));
    expect(screen.getByTestId("route")).toHaveTextContent("/fitness#training");
    expect(screen.getByRole("heading", { name: "Existing workspace" })).toBeInTheDocument();
    await act(async () => {});
  });

  it("projects entrance labels on one demand frame and settles reduced-motion navigation immediately", async () => {
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
    render(<MemoryRouter initialEntries={["/space"]}><SystemArtPreviewPage /></MemoryRouter>);
    const host = screen.getByRole("main");
    await waitFor(() => expect(host).toHaveAttribute("data-ready", "true"));
    stepFrames();
    const core = screen.getByRole("button", { name: "Explore solar system" });
    expect(core).toHaveAttribute("data-projected", "true");
    expect(core.style.visibility).toBe("");
    expect(core.style.transform).toMatch(/^translate\(-?\d+px, -?\d+px\)/);
    expect(host).toHaveAttribute("data-moving", "false");
    fireEvent.click(core);
    stepFrames();
    const fitness = screen.getByRole("button", { name: "Explore Fitness" });
    expect(fitness).toHaveAttribute("data-projected", "true");
    expect(fitness.style.visibility).toBe("");
    expect(host).toHaveAttribute("data-moving", "false");
    expect(runtime.mounts).toBe(1);
  });

  it("returns to the new root entrance without reopening an old hub", async () => {
    render(<MemoryRouter initialEntries={["/?depth=system"]}><Location /><Routes>
      <Route path="/" element={<SystemArtPreviewPage />} />
    </Routes></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("main")).toHaveAttribute("data-depth", "core");
    expect(screen.getByRole("button", { name: "Back" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("main")).toHaveAttribute("data-depth", "core");
    expect(screen.getByTestId("route")).toHaveTextContent("/");
    expect(runtime.mounts).toBe(1);
    await act(async () => {});
  });

  it.each(spatialDomains.flatMap(domain => spatialMoonCatalog[domain.id]
    .filter(moon => moon.href).map(moon => ({ domain: domain.id, label: moon.label, href: moon.href! }))))(
    "opens $domain / $label from the normal home route and retains its planet return", async ({ domain, label, href }) => {
      render(<MemoryRouter initialEntries={[`/?depth=domain&domain=${domain}`]}><Location /><Routes>
        <Route path="/" element={<SystemArtPreviewPage />} />
        <Route path="*" element={<h2>Existing workspace</h2>} />
      </Routes></MemoryRouter>);
      await waitFor(() => expect(screen.getByRole("main")).toHaveAttribute("data-ready", "true"));
      const link = screen.getByRole("link", { name: label, hidden: true });
      expect(link).toHaveAttribute("href", href);
      fireEvent.click(link);
      expect(screen.getByTestId("route").textContent).toBe(href);
      expect(screen.getByTestId("route")).toHaveAttribute("data-return", `/?depth=domain&domain=${domain}`);
      expect(screen.getByRole("heading", { name: "Existing workspace" })).toBeInTheDocument();
    },
  );

  it("keeps the selected moon destinations reachable when 3D preparation fails", async () => {
    const gl = (runtime.three as { gl: { compileAsync: ReturnType<typeof vi.fn> } }).gl;
    gl.compileAsync.mockRejectedValueOnce(new Error("Shader preparation failed"));
    render(<MemoryRouter initialEntries={["/?depth=domain&domain=life"]}><Location /><Routes>
      <Route path="/" element={<SystemArtPreviewPage />} />
      <Route path="*" element={<h2>Existing workspace</h2>} />
    </Routes></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("navigation", { name: "Moon pages" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "Notebook" }));
    expect(screen.getByTestId("route").textContent).toBe("/notebook");
    expect(screen.getByTestId("route")).toHaveAttribute("data-return", "/?depth=domain&domain=life");
  });

  it("retargets an interrupted journey and returns to an exact settled entrance", async () => {
    render(<MemoryRouter initialEntries={["/space"]}><SystemArtPreviewPage /></MemoryRouter>);
    const host = screen.getByRole("main");
    await waitFor(() => expect(host).toHaveAttribute("data-ready", "true"));
    stepFrames(72);
    const camera = (runtime.three as { camera: THREE.PerspectiveCamera }).camera;
    const entrancePosition = camera.position.clone();
    const core = screen.getByRole("button", { name: "Explore solar system" });
    fireEvent.click(core);
    stepFrames(20);
    expect(host).toHaveAttribute("data-moving", "true");
    expect(core.style.visibility).toBe("");
    expect(core).not.toHaveAttribute("data-projected");
    const interruptedPosition = camera.position.clone();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(camera.position).toEqual(interruptedPosition);
    stepFrames(72);
    expect(camera.position.distanceTo(entrancePosition)).toBeLessThan(1e-8);
    expect(host).toHaveAttribute("data-moving", "false");
    expect(screen.getByRole("button", { name: "Explore solar system" })).toHaveAttribute("data-projected", "true");
    expect(runtime.mounts).toBe(1);
  });

  it("retains canonical fallback links after context loss and prepares a fresh Canvas on retry", async () => {
    render(<MemoryRouter initialEntries={["/space"]}><SystemArtPreviewPage /></MemoryRouter>);
    const host = screen.getByRole("main");
    await waitFor(() => expect(host).toHaveAttribute("data-ready", "true"));
    const canvas = (runtime.three as { gl: { domElement: HTMLCanvasElement } }).gl.domElement;
    const lost = new Event("webglcontextlost", { cancelable: true });
    act(() => { canvas.dispatchEvent(lost); });
    expect(lost.defaultPrevented).toBe(true);
    expect(host).toHaveAttribute("data-ready", "false");
    expect(runtime.unmounts).toBe(1);
    expect(screen.queryByTestId("canvas-host")).not.toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Domain pages" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry art preview" }));
    await waitFor(() => expect(host).toHaveAttribute("data-ready", "true"));
    expect(runtime.mounts).toBe(2);
    expect(runtime.unmounts).toBe(1);
    const gl = (runtime.three as { gl: { compileAsync: () => Promise<void> } }).gl;
    expect(gl.compileAsync).toHaveBeenCalledTimes(2);
  });

  it("keeps preparation status and canonical routes until shader preparation finishes", async () => {
    let finish!: () => void;
    const preparation = new Promise<void>(resolve => { finish = resolve; });
    const gl = (runtime.three as { gl: { compileAsync: ReturnType<typeof vi.fn> } }).gl;
    gl.compileAsync.mockReturnValueOnce(preparation);
    render(<MemoryRouter initialEntries={["/space?depth=system"]}><SystemArtPreviewPage /></MemoryRouter>);
    const host = screen.getByRole("main");
    await waitFor(() => expect(gl.compileAsync).toHaveBeenCalledTimes(1));
    expect(host).toHaveAttribute("data-ready", "false");
    expect(screen.getByRole("status")).toHaveTextContent("Preparing system");
    expect(screen.getByRole("navigation", { name: "Domain pages" })).toBeInTheDocument();
    await act(async () => { finish(); await preparation; });
    await waitFor(() => expect(host).toHaveAttribute("data-ready", "true"));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(runtime.mounts).toBe(1);
  });

  it("stops a shader-failed renderer and retries without discarding canonical fallback navigation", async () => {
    const gl = (runtime.three as { gl: { compileAsync: ReturnType<typeof vi.fn> } }).gl;
    gl.compileAsync.mockRejectedValueOnce(new Error("Shader preparation failed"));
    render(<MemoryRouter initialEntries={["/space"]}><SystemArtPreviewPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("3D preview unavailable"));
    expect(runtime.unmounts).toBe(1);
    expect(runtime.frames.size).toBe(0);
    expect(screen.getByRole("navigation", { name: "Domain pages" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry art preview" }));
    await waitFor(() => expect(screen.getByRole("main")).toHaveAttribute("data-ready", "true"));
    expect(runtime.mounts).toBe(2);
    expect(gl.compileAsync).toHaveBeenCalledTimes(2);
  });

  it("ignores stale preparation failure after context loss and a successful retry", async () => {
    let rejectOld!: (error: Error) => void;
    let finishRetry!: () => void;
    const oldPreparation = new Promise<void>((_, reject) => { rejectOld = reject; });
    const retryPreparation = new Promise<void>(resolve => { finishRetry = resolve; });
    const gl = (runtime.three as { gl: { compileAsync: ReturnType<typeof vi.fn>; domElement: HTMLCanvasElement } }).gl;
    gl.compileAsync.mockReturnValueOnce(oldPreparation);
    gl.compileAsync.mockReturnValueOnce(retryPreparation);
    render(<MemoryRouter initialEntries={["/space"]}><SystemArtPreviewPage /></MemoryRouter>);
    await waitFor(() => expect(gl.compileAsync).toHaveBeenCalledTimes(1));
    act(() => { gl.domElement.dispatchEvent(new Event("webglcontextlost", { cancelable: true })); });
    fireEvent.click(screen.getByRole("button", { name: "Retry art preview" }));
    await waitFor(() => expect(gl.compileAsync).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("main")).toHaveAttribute("data-ready", "false");
    await act(async () => { finishRetry(); await retryPreparation; });
    await waitFor(() => expect(screen.getByRole("main")).toHaveAttribute("data-ready", "true"));
    await act(async () => { rejectOld(new Error("Old renderer failed late")); await Promise.resolve(); });
    expect(screen.getByRole("main")).toHaveAttribute("data-ready", "true");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(runtime.mounts).toBe(2);
  });
});
