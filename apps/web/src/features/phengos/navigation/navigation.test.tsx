import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useEffect, useState } from "react";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "../../../layouts/AppShell";
import { phengosFeatures } from "../phengosFeatures";
import { activeFeature, backFallback, navigationGroups } from "./navigationModel";

const mocks = vi.hoisted(() => ({
  connection: "LIVE",
  signOut: vi.fn().mockResolvedValue(undefined),
  push: vi.fn().mockResolvedValue("denied"),
  mounted: vi.fn(),
}));
vi.mock("../../../app/RealtimeProvider", () => ({ useRealtimeConnectionState: () => mocks.connection }));
vi.mock("../../../lib/auth", () => ({ signOut: mocks.signOut }));
vi.mock("../../../lib/push", () => ({ enablePushNotifications: mocks.push }));

beforeEach(() => { mocks.connection = "LIVE"; mocks.mounted.mockClear(); mocks.signOut.mockClear(); mocks.push.mockClear(); });

function FixturePage() {
  const [draft, setDraft] = useState("");
  useEffect(() => { mocks.mounted(); }, []);
  return <>
    <label>Page draft<input value={draft} onChange={event => setDraft(event.target.value)} /></label>
    {["nutrition", "shopping", "household", "training", "goals", "daily-list", "study-log", "study-candidates", "exams"].map(id =>
      <h2 id={id} key={id} tabIndex={-1}>{id} controls</h2>)}
  </>;
}

function RouterControls() {
  const location = useLocation();
  const navigate = useNavigate();
  return <>
    <output data-testid="location">{location.pathname + location.search + location.hash}</output>
    <output data-testid="location-state">{JSON.stringify(location.state)}</output>
    <button onClick={() => navigate(-1)}>Browser back</button>
    <button onClick={() => navigate(1)}>Browser forward</button>
    <button onClick={() => navigate("/learning", { replace: true })}>Replace with Learning</button>
  </>;
}

const paths = [...new Set(phengosFeatures.map(feature => feature.href.split("#")[0]))];
function renderWorkspace(entry: string | { pathname: string; search?: string; hash?: string; state?: unknown } = "/kitchen", prior?: string) {
  return render(<MemoryRouter initialEntries={prior ? [prior, entry] : [entry]} initialIndex={prior ? 1 : 0}>
    <RouterControls />
    <Routes>
      <Route element={<AppShell />}>{paths.map(path => <Route key={path} path={path} element={<FixturePage />} />)}</Route>
      <Route path="/" element={<h1>Phengos home</h1>} />
      <Route path="/login" element={<h1>Login</h1>} />
      <Route path="/outside" element={<h1>Unobserved prior page</h1>} />
    </Routes>
  </MemoryRouter>);
}

function sidebar() { return within(screen.getByRole("navigation", { name: "Life OS navigation" })); }
function openGroup(group: string) {
  const existing = sidebar().queryByRole("group", { name: `${group} features` });
  if (!existing) fireEvent.click(sidebar().getByRole("button", { name: group === "System" ? "Settings" : group }));
  return within(sidebar().getByRole("group", { name: `${group} features` }));
}
function featureLink(label: string) {
  const feature = phengosFeatures.find(item => item.label === label)!;
  return openGroup(feature.group).getByRole("link", { name: label });
}
describe("navigation directory identity", () => {
  it.each(phengosFeatures)("resolves $href to $group / $label", feature => {
    const [pathname, section] = feature.href.split("#");
    expect(activeFeature(pathname, section ? `#${section}` : "")).toBe(feature);
  });

  it("retains all 21 canonical entries in the seven requested groups", () => {
    renderWorkspace();
    expect(phengosFeatures).toHaveLength(21);
    expect(sidebar().getAllByRole("button").filter(node => node.classList.contains("pn-domain-button"))).toHaveLength(7);
    for (const group of navigationGroups) {
      const panel = openGroup(group);
      for (const feature of phengosFeatures.filter(item => item.group === group)) {
        expect(panel.getByRole("link", { name: feature.label })).toHaveAttribute("href", feature.href);
      }
    }
  });

  it("offers the main dashboard from the Home domain panel", () => {
    renderWorkspace("/calendar");
    const overview = openGroup("Home").getByRole("link", { name: "Overview" });
    expect(overview).toHaveAttribute("href", "/");
    fireEvent.click(overview);
    expect(screen.getByRole("heading", { name: "Phengos home" })).toBeInTheDocument();
    expect(screen.getByTestId("location-state")).toHaveTextContent('"phengosOpen":true');
  });

  it("searches the canonical feature list from the sidebar utility", () => {
    renderWorkspace();
    fireEvent.click(sidebar().getByRole("button", { name: "Search" }));
    const panel = within(sidebar().getByRole("group", { name: "Search features" }));
    fireEvent.change(panel.getByRole("searchbox", { name: "Find a destination" }), { target: { value: "shop" } });
    expect(panel.getByRole("link", { name: "Shopping" })).toHaveAttribute("href", "/kitchen#shopping");
    expect(panel.queryByRole("link", { name: "Fitness" })).not.toBeInTheDocument();
  });

  it.each([
    ["/kitchen#nutrition", "Home", "Nutrition"],
    ["/life#household", "Home", "Household"],
    ["/settings/personal-model", "System", "Personal model"],
  ])("marks only the correct group and breadcrumb for %s", (path, group, label) => {
    renderWorkspace(path);
    const link = featureLink(label);
    expect(link).toHaveAttribute("aria-current", "page");
    expect(sidebar().getAllByRole("link").filter(node => node.hasAttribute("aria-current"))).toEqual([link]);
    const selectedDomain = path.startsWith("/kitchen")
      ? sidebar().getAllByRole("link", { name: "Kitchen" }).find(node => node.classList.contains("pn-kitchen-link"))
      : sidebar().getByRole("button", { name: group === "System" ? "Settings" : group });
    expect(selectedDomain).toHaveAttribute("data-active", "true");
    const breadcrumbs = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(breadcrumbs).toHaveTextContent(group);
    expect(breadcrumbs.querySelector("[aria-current=page]")).toHaveTextContent(label);
  });

  it("handles encoded, unknown and malformed hashes without inventing sections", () => {
    expect(activeFeature("/kitchen", "#%6eutrition")?.group).toBe("Home");
    expect(activeFeature("/kitchen", "#unknown")?.label).toBe("Kitchen");
    expect(activeFeature("/kitchen", "#%ZZ")?.label).toBe("Kitchen");
    expect(activeFeature("/unknown", "")).toBeUndefined();
    expect(backFallback(undefined)).toBe("/");
  });
});

describe("history and route state", () => {
  it.each([
    ["/kitchen#nutrition", "/kitchen"],
    ["/life#household", "/kitchen"],
    ["/calendar#daily-list", "/calendar"],
    ["/settings/personal-model", "/settings"],
    ["/finance", "/life"],
    ["/settings", "/"],
  ])("uses a deterministic safe Back fallback on direct %s", (path, expected) => {
    renderWorkspace(path, "/outside");
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByTestId("location")).toHaveTextContent(new RegExp(`^${expected}$`));
    expect(screen.queryByRole("heading", { name: "Unobserved prior page" })).not.toBeInTheDocument();
  });

  it("uses observed history and supports browser Back and Forward across groups", () => {
    renderWorkspace("/kitchen#shopping");
    fireEvent.click(featureLink("Nutrition"));
    expect(screen.getByTestId("location")).toHaveTextContent("/kitchen#nutrition");
    fireEvent.click(featureLink("Settings"));
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/kitchen#nutrition");
    fireEvent.click(screen.getByRole("button", { name: "Browser back" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/kitchen#shopping");
    fireEvent.click(screen.getByRole("button", { name: "Browser forward" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/kitchen#nutrition");
  });

  it("tracks replacement entries and discards an abandoned forward branch", () => {
    renderWorkspace();
    fireEvent.click(featureLink("Settings"));
    fireEvent.click(screen.getByRole("button", { name: "Replace with Learning" }));
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/kitchen$/);
    fireEvent.click(featureLink("Finance"));
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    fireEvent.click(screen.getByRole("button", { name: "Browser forward" }));
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/finance$/);
  });

  it("preserves a same-page draft, query, route state and section focus through hash navigation", async () => {
    renderWorkspace({ pathname: "/kitchen", search: "?view=recorded", state: { workspace: "existing", spatialReturn: "/?depth=domain&domain=home" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Page draft" }), { target: { value: "Unsaved meal" } });
    fireEvent.click(featureLink("Nutrition"));
    expect(screen.getByTestId("location")).toHaveTextContent("/kitchen?view=recorded#nutrition");
    expect(screen.getByTestId("location-state")).toHaveTextContent('"workspace":"existing"');
    expect(screen.getByRole("textbox", { name: "Page draft" })).toHaveValue("Unsaved meal");
    await waitFor(() => expect(screen.getByRole("heading", { name: "nutrition controls" })).toHaveFocus());
    fireEvent.click(featureLink("Shopping"));
    expect(screen.getByRole("textbox", { name: "Page draft" })).toHaveValue("Unsaved meal");
    expect(mocks.mounted).toHaveBeenCalledTimes(1);
  });

  it("skips to content without replacing the selected subsection hash", async () => {
    renderWorkspace("/kitchen#nutrition");
    await waitFor(() => expect(screen.getByRole("heading", { name: "nutrition controls" })).toHaveFocus());
    fireEvent.click(screen.getByRole("link", { name: "Skip to content" }));
    expect(screen.getByRole("main")).toHaveFocus();
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/kitchen#nutrition$/);
    expect(featureLink("Nutrition")).toHaveAttribute("aria-current", "page");
  });

  it("does not add a pathname remount or transfer page-specific query/state to another route", () => {
    renderWorkspace({ pathname: "/kitchen", search: "?view=recorded", state: { workspace: "kitchen-only" } });
    const surface = document.querySelector(".pn-surface");
    fireEvent.click(featureLink("Household"));
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/life#household$/);
    expect(screen.getByTestId("location-state")).toHaveTextContent("null");
    expect(document.querySelector(".pn-surface")).toBe(surface);
    expect(mocks.mounted).toHaveBeenCalledTimes(1);
  });

  it("returns to plain Phengos Home with return intent instead of restoring legacy spatial artwork", () => {
    renderWorkspace({ pathname: "/kitchen", state: { spatialReturn: "/?depth=domain&domain=home" } });
    fireEvent.click(screen.getByRole("link", { name: "Life OS hub" }));
    expect(screen.getByRole("heading", { name: "Phengos home" })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/$/);
    expect(screen.getByTestId("location-state")).toHaveTextContent('"phengosReturn":true');
  });

  it("returns a card-opened workspace to its Phengos domain layer", () => {
    renderWorkspace({ pathname: "/kitchen", hash: "#shopping", state: { phengosOriginLayer: "domain", phengosOriginGroup: "Home" } });
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/$/);
    expect(screen.getByTestId("location-state")).toHaveTextContent('"phengosOpen":true');
    expect(screen.getByTestId("location-state")).toHaveTextContent('"phengosGroup":"Home"');
  });
});

describe("single routed navigation", () => {
  it("uses the persistent sidebar as the only feature menu and toggles it with the circle", () => {
    renderWorkspace("/kitchen#nutrition");
    expect(sidebar().getAllByRole("button").filter(node => node.classList.contains("pn-domain-button"))).toHaveLength(7);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close Phengos navigation" }));
    expect(screen.queryByRole("navigation", { name: "Life OS navigation" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Phengos navigation" })).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(screen.getByRole("button", { name: "Open Phengos navigation" }));
    expect(featureLink("Nutrition")).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes the one sidebar with Escape without losing the working draft", () => {
    renderWorkspace();
    fireEvent.change(screen.getByRole("textbox", { name: "Page draft" }), { target: { value: "Draft" } });
    featureLink("Kitchen").focus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("navigation", { name: "Life OS navigation" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Phengos navigation" })).toHaveFocus();
    expect(screen.getByRole("textbox", { name: "Page draft" })).toHaveValue("Draft");
  });

  it("keeps all section links and browser history available through the same sidebar", async () => {
    renderWorkspace();
    fireEvent.click(featureLink("Shopping"));
    await waitFor(() => expect(screen.getByRole("heading", { name: "shopping controls" })).toHaveFocus());
    fireEvent.click(featureLink("Settings"));
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/settings$/);
    fireEvent.click(featureLink("Personal model"));
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/settings\/personal-model$/);
  });
});
describe("existing shell controls", () => {
  it("preserves genuine offline state and notification denial", async () => {
    mocks.connection = "OFFLINE";
    renderWorkspace();
    expect(screen.getByText("Life OS is offline. Changes are not being sent.").closest("[role=status]")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Enable reminders" }));
    expect(await screen.findByText("Notifications are blocked.")).toBeInTheDocument();
    expect(mocks.push).toHaveBeenCalledTimes(1);
  });

  it("preserves logout and the login replacement route", async () => {
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(await screen.findByRole("heading", { name: "Login" })).toBeInTheDocument();
    expect(mocks.signOut).toHaveBeenCalledTimes(1);
  });
});
