import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import PhengosHome from "./PhengosHome";
import { PHENGOS_IDLE_KEY, PHENGOS_INTRO_KEY } from "./phengosJourney";
import { phengosFeatures } from "./phengosFeatures";

const preference = vi.hoisted(() => ({ reduced: false }));
const shoppingApi = vi.hoisted(() => ({ shoppingList: vi.fn(), markShoppingPurchased: vi.fn(), calendarProjection: vi.fn(), fitnessStatus: vi.fn(), startWorkout: vi.fn(), mealPlans: vi.fn(), standingCalendarRules: vi.fn(), standingRuleFixtures: vi.fn(), pendingAssistantProposals: vi.fn(), confirmAssistantProposal: vi.fn(), cancelAssistantProposal: vi.fn() }));
vi.mock("../../services/api", () => ({ api: shoppingApi }));
vi.mock("motion/react", async () => {
  const { createElement, forwardRef } = await import("react");
  return {
    useReducedMotion: () => preference.reduced,
    MotionConfig: ({ children }: { children: unknown }) => children,
    AnimatePresence: ({ children }: { children: unknown }) => children,
    motion: Object.fromEntries(["div", "button", "span", "article", "nav"].map(tag => [tag, forwardRef((props: Record<string, unknown>, ref) => {
      const { animate, initial: _initial, exit: _exit, transition: _transition, layout: _layout, whileTap: _whileTap, whileHover: _whileHover, ...rest } = props;
      return createElement(tag, { ...rest, ref, "data-animation": JSON.stringify(animate) });
    })])),
  };
});

function mount(initialEntries: Array<string | { pathname: string; state?: unknown }> = ["/"]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={initialEntries}>
    <Routes><Route path="/" element={<PhengosHome />} /><Route path="*" element={<h2>Existing feature</h2>} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  preference.reduced = false;
  window.localStorage.clear();
  window.sessionStorage.clear();
  shoppingApi.shoppingList.mockReset().mockResolvedValue([]);
  shoppingApi.markShoppingPurchased.mockReset().mockResolvedValue({});
  shoppingApi.calendarProjection.mockReset().mockResolvedValue({ commitments: [], planning_pool: [], world_revision: 0 });
  shoppingApi.fitnessStatus.mockReset().mockResolvedValue({ active_session: null, next_workout: null });
  shoppingApi.startWorkout.mockReset().mockResolvedValue({});
  shoppingApi.mealPlans.mockReset().mockResolvedValue([]);
  shoppingApi.standingCalendarRules.mockReset().mockResolvedValue([]);
  shoppingApi.standingRuleFixtures.mockReset().mockResolvedValue([]);
  shoppingApi.pendingAssistantProposals.mockReset().mockResolvedValue([]);
  shoppingApi.confirmAssistantProposal.mockReset().mockResolvedValue({ response_type: "MUTATION_RESULT", message: "Saved" });
  shoppingApi.cancelAssistantProposal.mockReset().mockResolvedValue({ response_type: "NO_ACTION", message: "Cancelled" });
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(async () => {});
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("plays the Blender scene and hands its last frame to one live clickable circle", () => {
  mount();
  const video = document.querySelector("video")!;
  expect(video.getAttribute("src")).toContain("environment-v17-60.mp4");
  expect(screen.getByRole("main")).toHaveAttribute("data-phase", "wordmark");
  expect(screen.getByRole("button", { name: "Skip opening" })).toHaveAttribute("data-rendered", "true");
  fireEvent.ended(video);
  expect(screen.getByRole("main")).toHaveAttribute("data-phase", "workspace");
  expect(document.querySelector("video")).toBeNull();
  expect(screen.getByRole("button", { name: "Open Phengos menu" })).toHaveAttribute("data-rendered", "false");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("lets the user skip and preserves all existing destinations in the launcher", async () => {
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Skip opening" }));
  expect(screen.getByRole("main")).toHaveAttribute("data-phase", "workspace");
  fireEvent.click(screen.getByRole("button", { name: "Open Phengos menu" }));
  const rail = within(screen.getByRole("navigation", { name: "Life OS domains" }));
  for (const group of [...new Set(phengosFeatures.map(feature => feature.group))]) {
    fireEvent.click(rail.getByRole("button", { name: group === "System" ? "Settings" : group }));
    const domain = within(screen.getByRole("navigation", { name: `${group} features` }));
    for (const feature of phengosFeatures.filter(feature => feature.group === group)) {
      expect(domain.getByRole("link", { name: feature.label })).toHaveAttribute("href", feature.href);
    }
  }
  await waitFor(() => expect(shoppingApi.shoppingList).toHaveBeenCalled());
  fireEvent.click(screen.getByRole("button", { name: "Return to horizon" }));
  expect(screen.getByRole("main")).toHaveAttribute("data-phase", "rest");
  expect(document.querySelector(".phengos-rest-plate")).toHaveAttribute("src", "/art/phengos/rest-environment-v17.png");
  expect(screen.getByRole("button", { name: "Rise with Phengos" })).toHaveAttribute("data-rendered", "false");
  fireEvent.click(screen.getByRole("button", { name: "Rise with Phengos" }));
  expect(screen.getByRole("main")).toHaveAttribute("data-phase", "workspace");
});

it("finds canonical destinations from the Home rail search", () => {
  window.sessionStorage.setItem(PHENGOS_INTRO_KEY, "seen");
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Open Phengos menu" }));
  const rail = within(screen.getByRole("navigation", { name: "Life OS domains" }));
  fireEvent.click(rail.getByRole("button", { name: "Search" }));
  fireEvent.change(screen.getByRole("searchbox", { name: "Search LIFE OS" }), { target: { value: "shopping" } });
  expect(within(screen.getByRole("navigation", { name: "Search results" })).getByRole("link", { name: /Shopping/ })).toHaveAttribute("href", "/kitchen#shopping");
});

it("moves from the overview into a domain and returns without losing the assistant draft", () => {
  window.sessionStorage.setItem(PHENGOS_INTRO_KEY, "seen");
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Open Phengos menu" }));
  const rail = within(screen.getByRole("navigation", { name: "Life OS domains" }));
  expect(rail.getByRole("button", { name: "Overview" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.change(screen.getByRole("textbox", { name: "Message for your assistant" }), { target: { value: "Plan tomorrow" } });
  fireEvent.click(rail.getByRole("button", { name: "Home" }));
  expect(rail.getByRole("button", { name: "Home" })).toHaveAttribute("aria-pressed", "true");
  expect(within(screen.getByRole("navigation", { name: "Home features" })).getByRole("link", { name: "Shopping" })).toHaveAttribute("href", "/kitchen#shopping");
  fireEvent.click(screen.getByRole("button", { name: "Back to overview" }));
  expect(rail.getByRole("button", { name: "Overview" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("textbox", { name: "Message for your assistant" })).toHaveValue("Plan tomorrow");
});

it("restores the originating domain and saved prompt on a working-view return", () => {
  mount([{ pathname: "/", state: { phengosReturn: true, phengosOpen: true, phengosGroup: "Home" } }]);
  expect(screen.getByRole("dialog", { name: "Home" })).toBeInTheDocument();
  expect(within(screen.getByRole("navigation", { name: "Home features" })).getByRole("link", { name: "Shopping" })).toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox", { name: "Message for your assistant" }), { target: { value: "Plan dinner" } });
  fireEvent.click(screen.getByRole("button", { name: "Close Phengos menu" }));
  fireEvent.click(screen.getByRole("button", { name: "Open Phengos menu" }));
  expect(screen.getByRole("textbox", { name: "Message for your assistant" })).toHaveValue("Plan dinner");
});

it("does not replay after an explicit Home return, but still supports replay", () => {
  mount([{ pathname: "/", state: { phengosReturn: true } }]);
  expect(screen.getByRole("main")).toHaveAttribute("data-phase", "workspace");
  expect(document.querySelector("video")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Open Phengos menu" }));
  fireEvent.click(screen.getByRole("button", { name: "Replay opening" }));
  expect(screen.getByRole("main")).toHaveAttribute("data-phase", "wordmark");
  expect(document.querySelector("video")).not.toBeNull();
});

it("shows real Kitchen shopping items and uses the existing purchase action", async () => {
  window.sessionStorage.setItem(PHENGOS_INTRO_KEY, "seen");
  shoppingApi.shoppingList.mockResolvedValue([{
    ingredient_name: "Milk", quantity: 2, unit: "l", priority_class: "required",
    reasons: [], estimated_cost: null, source_item_ids: ["shopping-1"], status: "open",
  }]);
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Open Phengos menu" }));
  expect(await screen.findByText("Milk")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Mark Milk purchased" }));
  await waitFor(() => expect(shoppingApi.markShoppingPurchased).toHaveBeenCalledWith("shopping-1", { add_to_inventory: true }));
  expect(screen.getByRole("link", { name: /Open shopping list/ })).toHaveAttribute("href", "/kitchen#shopping");
  fireEvent.click(screen.getByRole("button", { name: "Dismiss shopping card" }));
  expect(screen.queryByText("Milk")).not.toBeInTheDocument();
});

it("shows a near-term calendar card from canonical commitments", async () => {
  window.sessionStorage.setItem(PHENGOS_INTRO_KEY, "seen");
  shoppingApi.calendarProjection.mockResolvedValue({ commitments: [{
    canonical_id: "commitment-1", canonical_type: "commitment", title: "Project review",
    starts_at: new Date(Date.now() + 60 * 60_000).toISOString(), ends_at: new Date(Date.now() + 2 * 60 * 60_000).toISOString(),
    status: "scheduled", level: "hard", commitment_type: "work", source: "manual", version: 1,
  }], planning_pool: [], world_revision: 1 });
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Open Phengos menu" }));
  expect(await screen.findByRole("heading", { name: "Project review" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Open calendar/ })).toHaveAttribute("href", "/calendar");
});

it("shows a stable day and focus overview from the current plan", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 3, 10, 0, 0));
  window.sessionStorage.setItem(PHENGOS_INTRO_KEY, "seen");
  shoppingApi.calendarProjection.mockResolvedValue({ commitments: [], planning_pool: [], world_revision: 1, current_plan: {
    id: "plan-1", blocks: [{ id: "block-1", title: "Study session", domain: "learning", block_type: "generated_action",
      status: "planned", starts_at: new Date(Date.now() + 60 * 60_000).toISOString(),
      ends_at: new Date(Date.now() + 2 * 60 * 60_000).toISOString(), duration_minutes: 60 }],
  } });
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Open Phengos menu" }));
  expect(screen.getByRole("heading", { name: "Today at a glance" })).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "Study session" })).toBeInTheDocument();
  expect(screen.getByText("1 planned block")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open daily plan" })).toHaveAttribute("href", "/calendar#daily-list");
  expect(screen.getByRole("link", { name: /Plan\s*1/ })).toHaveAttribute("href", "/calendar");
});

it("requires explicit approval for a saved agent proposal card", async () => {
  window.sessionStorage.setItem(PHENGOS_INTRO_KEY, "seen");
  shoppingApi.pendingAssistantProposals.mockResolvedValue([{ id: "proposal-1", thread_id: "thread-1", summary: "Add a meeting with Deniz", tool_name: "create_commitment",
    arguments: { title: "Meet Deniz" }, status: "pending", expires_at: new Date(Date.now() + 600_000).toISOString(), version: 1 }]);
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Open Phengos menu" }));
  expect(await screen.findByRole("heading", { name: "Add a meeting with Deniz" })).toBeInTheDocument();
  expect(screen.getByText("Meet Deniz")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Review or adjust in chat/ })).toHaveAttribute("href", "/self/assistant?thread=thread-1");
  expect(shoppingApi.confirmAssistantProposal).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Approve and save" }));
  await waitFor(() => expect(shoppingApi.confirmAssistantProposal).toHaveBeenCalledWith("proposal-1"));
});

it("starts the next real Fitness workout from a contextual card", async () => {
  window.sessionStorage.setItem(PHENGOS_INTRO_KEY, "seen");
  shoppingApi.fitnessStatus.mockResolvedValue({ active_session: null, next_workout: { id: "workout-1", name: "Upper A", estimated_duration_minutes: 75 } });
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Open Phengos menu" }));
  expect(await screen.findByRole("heading", { name: "Upper A" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Start workout" }));
  await waitFor(() => expect(shoppingApi.startWorkout).toHaveBeenCalledWith({ workout_template_id: "workout-1" }));
  await waitFor(() => expect(screen.getByRole("heading", { name: "Existing feature" })).toBeInTheDocument());
});

it("uses the configured twelve-minute idle return and protects an open card menu", () => {
  vi.useFakeTimers();
  window.sessionStorage.setItem(PHENGOS_INTRO_KEY, "seen");
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Open Phengos menu" }));
  act(() => vi.advanceTimersByTime(12 * 60_000));
  expect(screen.getByRole("main")).toHaveAttribute("data-phase", "workspace");
  fireEvent.change(screen.getByRole("combobox", { name: "Idle return" }), { target: { value: "10" } });
  expect(window.localStorage.getItem(PHENGOS_IDLE_KEY)).toBe("10");
  fireEvent.click(screen.getByRole("button", { name: "Close Phengos menu" }));
});

it("skips film playback for reduced motion and falls back if video fails", () => {
  preference.reduced = true;
  const reduced = mount();
  expect(screen.getByRole("main")).toHaveAttribute("data-phase", "workspace");
  expect(document.querySelector("video")).toBeNull();
  reduced.unmount();
  preference.reduced = false;
  window.sessionStorage.clear();
  mount();
  fireEvent.error(document.querySelector("video")!);
  expect(screen.getByRole("main")).toHaveAttribute("data-phase", "workspace");
});

it("does not abandon the introduction while the tab is hidden", () => {
  vi.useFakeTimers();
  mount();
  Object.defineProperty(document, "hidden", { configurable: true, value: true });
  try {
    fireEvent(document, new Event("visibilitychange"));
    act(() => vi.advanceTimersByTime(7000));
    expect(screen.getByRole("main")).toHaveAttribute("data-phase", "wordmark");
  } finally {
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
  }
});
