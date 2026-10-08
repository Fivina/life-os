import { fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { AppShell } from "../layouts/AppShell";

vi.mock("../app/RealtimeProvider", () => ({ useRealtimeConnectionState: () => "CONNECTED" }));
vi.mock("../features/hub/GravitySettingsNode", () => ({ GravitySettingsNode: () => null }));
vi.mock("../features/hub/ModuleGlyph", () => ({ ModuleGlyph: () => null }));
vi.mock("../features/hub/SelfCore", () => ({ SelfCoreMark: () => null }));

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

it("returns a moon workspace to its originating planetary view without replaying the old hub exit", () => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false })));
  render(<MemoryRouter initialEntries={[{ pathname: "/kitchen", state: { spatialReturn: "/?depth=domain&domain=home" } }]}><Routes>
    <Route element={<AppShell />}><Route path="kitchen" element={<h2>Kitchen controls</h2>} /></Route>
    <Route path="/" element={<h2>Home planetary view</h2>} />
  </Routes></MemoryRouter>);
  fireEvent.click(screen.getByRole("link", { name: "Life OS hub" }));
  expect(screen.getByRole("heading", { name: "Home planetary view" })).toBeInTheDocument();
});

it("returns immediately to the new system and leaves no old fading exit state on re-entry", () => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false })));
  render(<MemoryRouter initialEntries={["/settings"]}><Routes>
    <Route element={<AppShell />}>
      <Route path="settings" element={<h2>Settings controls</h2>} />
    </Route>
    <Route path="/" element={<Link to="/settings">Enter settings</Link>} />
  </Routes></MemoryRouter>);
  fireEvent.click(screen.getByRole("link", { name: "Life OS hub" }));
  fireEvent.click(screen.getByRole("link", { name: "Enter settings" }));
  expect(screen.getByRole("heading", { name: "Settings controls" })).toBeInTheDocument();
  expect(document.querySelector(".workspace-frame")).not.toHaveClass("workspace-exiting");
});
