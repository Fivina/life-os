import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import PhengosHome from "./PhengosHome";

beforeEach(() => {
  window.localStorage.clear(); window.sessionStorage.clear();
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn(), addListener: vi.fn(), removeListener: vi.fn() })));
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(async () => {});
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("mounts the real Motion components and opens the workspace without any Canvas or provider request", async () => {
  const request = vi.fn();
  vi.stubGlobal("fetch", request);
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><PhengosHome /></MemoryRouter></QueryClientProvider>);
  expect(screen.getByRole("main")).toHaveAttribute("data-phase", "wordmark");
  fireEvent.click(screen.getByRole("button", { name: "Skip opening" }));
  expect(screen.getByRole("main")).toHaveAttribute("data-phase", "workspace");
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Open Phengos menu" }));
  await waitFor(() => expect(screen.getByRole("textbox", { name: "Message for your assistant" })).toBeVisible(), { timeout: 2000 });
  const domains = within(screen.getByRole("navigation", { name: "Life OS domains" }));
  expect(domains.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
  expect(domains.getByRole("link", { name: "Kitchen" })).toHaveAttribute("href", "/kitchen");
  expect(screen.queryByText("Choose where to work")).not.toBeInTheDocument();
  expect(document.querySelector("canvas")).toBeNull();
  await waitFor(() => expect(request).toHaveBeenCalledTimes(6));
});
