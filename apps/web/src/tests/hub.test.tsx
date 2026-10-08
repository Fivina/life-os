import { useEffect } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HubPage } from "../features/hub/HubPage";
import { domainPosition, smoothTravel, spatialDepth, spatialDomains } from "../features/hub/spatialNavigation";

const state = vi.hoisted(() => ({ overload: "feasible", failScene: false }));
vi.mock("../services/api", () => ({ api: { currentPlan: async () => ({ overload_status: state.overload }) } }));
vi.mock("../features/hub/SpatialHubScene", () => ({
  SpatialHubScene: ({ depth, onArrive, calendarAttention, reducedMotion }: { depth: string; onArrive: () => void; calendarAttention: boolean; reducedMotion: boolean }) => {
    useEffect(onArrive, [depth, onArrive]);
    if (state.failScene) throw new Error("WebGL unavailable");
    return <div data-testid="scene" data-attention={calendarAttention} data-reduced={reducedMotion} />;
  }
}));

function Location() { const location = useLocation(); return <output data-testid="location">{location.pathname}{location.search}</output>; }
function mount(path = "/", reduced = false) {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: reduced, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Location /><Routes>
    <Route path="/" element={<HubPage />} />
    <Route path="*" element={<h2>Domain workspace</h2>} />
  </Routes></MemoryRouter></QueryClientProvider>);
}

describe("spatial hub navigation", () => {
  beforeEach(() => { state.overload = "feasible"; state.failScene = false; });
  afterEach(() => vi.unstubAllGlobals());
  it("opens with Self Core and gravity well, without visible domain targets", async () => {
    mount();
    await screen.findByTestId("scene");
    expect(screen.getByRole("button", { name: "Explore Self Core system" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Open Settings" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Open Calendar" })).not.toBeInTheDocument();
  });
  it("travels to all five existing domains and returns with Escape", async () => {
    mount();
    await screen.findByTestId("scene");
    fireEvent.click(screen.getByRole("button", { name: "Explore Self Core system" }));
    expect(await screen.findByRole("button", { name: "Return to Self Core" })).toBeEnabled();
    expect(screen.getByTestId("location")).toHaveTextContent("/?depth=system");
    for (const domain of spatialDomains) expect(screen.getByRole("button", { name: `Open ${domain.label}` })).toBeEnabled();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("button", { name: "Open Calendar" })).not.toBeInTheDocument();
  });
  it.each(spatialDomains)("keeps $label connected to its real domain page", async (domain) => {
    mount("/?depth=system");
    await screen.findByTestId("scene");
    fireEvent.click(screen.getByRole("button", { name: `Open ${domain.label}` }));
    expect(screen.getByTestId("location")).toHaveTextContent(domain.path);
    expect(screen.getByRole("heading", { name: "Domain workspace" })).toBeInTheDocument();
  });
  it("respects reduced motion and supports a direct system URL", async () => {
    mount("/?depth=system", true);
    expect(await screen.findByTestId("scene")).toHaveAttribute("data-reduced", "true");
    fireEvent.click(screen.getByRole("button", { name: "Return to Self Core" }));
    expect(screen.getByLabelText("Life OS hub")).toHaveAttribute("data-moving", "false");
  });
  it("does not manufacture attention from a feasible plan", async () => {
    mount("/?depth=system");
    expect(await screen.findByTestId("scene")).toHaveAttribute("data-attention", "false");
    expect(screen.queryByText("Needs attention")).not.toBeInTheDocument();
  });
  it("marks only Calendar when canonical planner capacity is overloaded", async () => {
    state.overload = "overloaded";
    mount("/?depth=system");
    await screen.findByText("Needs attention");
    expect(screen.getByRole("button", { name: "Open Calendar" })).toHaveAttribute("data-attention", "true");
    expect(screen.getByRole("button", { name: "Open Fitness" })).toHaveAttribute("data-attention", "false");
  });
  it("retains usable domain links when the renderer fails", async () => {
    state.failScene = true;
    const log = vi.spyOn(console, "error").mockImplementation(() => undefined);
    try {
      mount();
      expect(await screen.findByRole("link", { name: "Calendar" })).toHaveAttribute("href", "/calendar");
      expect(screen.queryByRole("button", { name: "Explore Self Core system" })).not.toBeInTheDocument();
    } finally { log.mockRestore(); }
  });
});
describe("spatial motion contract", () => {
  it("clamps smooth arrival with zero-speed endpoints and monotonic travel", () => {
    expect(smoothTravel(-1)).toBe(0);
    expect(smoothTravel(2)).toBe(1);
    expect(smoothTravel(0.001)).toBeLessThan(0.000001);
    const samples = Array.from({ length: 101 }, (_, i) => smoothTravel(i / 100));
    expect(samples).toEqual([...samples].sort((a, b) => a - b));
  });
  it("moves orbit positions slowly and never invents unknown depths", () => {
    const start = domainPosition(0, false), later = domainPosition(0, false, 1);
    expect(Math.hypot(...later.map((value, i) => value - start[i]))).toBeLessThan(0.005);
    expect(spatialDepth("planet")).toBe("core");
    expect(spatialDepth("system")).toBe("system");
  });
});
