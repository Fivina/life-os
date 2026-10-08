import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { Outlet } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "../app/App";

vi.mock("../app/providers", () => ({ AppProviders: ({ children }: { children: ReactNode }) => children }));
vi.mock("../features/auth/ProtectedRoute", () => ({ ProtectedRoute: () => <Outlet /> }));
vi.mock("../features/phengos/PhengosHome", () => ({ default: () => <h2>Phengos home</h2> }));

afterEach(() => { window.history.replaceState(null, "", "/"); });

it.each(["/", "/?depth=system", "/?depth=domain&domain=fitness"])(
  "mounts Phengos, not the old hub or WebGL scene, at %s", async path => {
    window.history.replaceState(null, "", path);
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Phengos home" })).toBeInTheDocument();
    expect(document.querySelector(".hub-screen")).toBeNull();
    expect(window.location.pathname + window.location.search).toBe(path);
  },
);

it.each([
  ["/space", "/"],
  ["/space?depth=system", "/?depth=system"],
  ["/space?depth=domain&domain=home&untrusted=1", "/?depth=domain&domain=home"],
  ["/space?depth=domain&domain=unknown", "/"],
])("redirects saved %s links to %s", async (path, expected) => {
  window.history.replaceState(null, "", path);
  render(<App />);
  await screen.findByRole("heading", { name: "Phengos home" });
  await waitFor(() => expect(window.location.pathname + window.location.search).toBe(expected));
});
