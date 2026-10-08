import { Bell, LogOut, RefreshCw, WifiOff } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { NavigationLinks, PhengosNavigation } from "../features/phengos/navigation/PhengosNavigation";
import { PhengosAssistantBar } from "../features/phengos/navigation/PhengosAssistantBar";
import { activeFeature } from "../features/phengos/navigation/navigationModel";
import "../features/phengos/phengosTheme.css";
import "../features/phengos/navigation/navigation.css";
import { signOut } from "../lib/auth";
import { enablePushNotifications, type PushSetupResult } from "../lib/push";
import { useRealtimeConnectionState } from "../app/RealtimeProvider";
import type { RealtimeConnectionState } from "../services/realtime";
import { RouteSectionFocus } from "./RouteSectionFocus";

export function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const active = activeFeature(location.pathname, location.hash);
  const [pushState, setPushState] = useState<PushSetupResult | "idle" | "working">("idle");
  const [navigationOpen, setNavigationOpen] = useState(() => typeof window.matchMedia !== "function" || !window.matchMedia("(max-width: 900px)").matches);
  const navigationLauncher = useRef<HTMLButtonElement>(null);
  const realtimeState = useRealtimeConnectionState();

  useEffect(() => {
    if (!navigationOpen) return;
    const onEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      const sidebar = document.getElementById("pn-sidebar");
      const fromNavigation = document.activeElement === navigationLauncher.current || sidebar?.contains(document.activeElement);
      if (!fromNavigation && !window.matchMedia?.("(max-width: 900px)")?.matches) return;
      setNavigationOpen(false);
      navigationLauncher.current?.focus();
    };
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [navigationOpen]);

  async function handleLogout() {
    await signOut();
    navigate("/login", { replace: true });
  }

  async function handleEnablePush() {
    setPushState("working");
    setPushState(await enablePushNotifications());
  }

  return (
    <div className="os-shell workspace-mode phengos-workspace" data-domain={active?.group ?? "Overview"}
      style={{ "--life-context-accent": active?.color ?? "#60a5fa" } as CSSProperties}>
      <RouteSectionFocus />
      <a className="pn-skip" href="#phengos-workspace-content" onClick={event => {
        event.preventDefault();
        const content = document.getElementById("phengos-workspace-content");
        content?.focus({ preventScroll: true });
        content?.scrollIntoView?.({ block: "start", behavior: "instant" });
      }}>Skip to content</a>
      <header className="os-header pn-header">
        <PhengosNavigation open={navigationOpen} onToggle={() => setNavigationOpen(open => !open)} launcher={navigationLauncher} />
        <div className="pn-actions">
          <button className="pn-icon" type="button" aria-label="Enable reminders" title="Enable reminders" onClick={handleEnablePush} disabled={pushState === "working"}>
            <Bell size={18} />
          </button>
          <button className="pn-icon" type="button" aria-label="Log out" title="Log out" onClick={handleLogout}>
            <LogOut size={18} />
          </button>
        </div>
      </header>
      {pushState !== "idle" && pushState !== "working" ? <p role="status" className={`pn-push-status status-text ${pushState === "enabled" ? "success" : "error"}`}>{pushMessage(pushState)}</p> : null}
      <ConnectionStatusBanner state={realtimeState} />

      {navigationOpen && <button className="pn-nav-backdrop" type="button" aria-label="Close navigation backdrop" onClick={() => { setNavigationOpen(false); navigationLauncher.current?.focus(); }} />}
      <div className="workspace-frame pn-frame" data-nav-open={navigationOpen}>
        <nav id="pn-sidebar" className="pn-sidebar" aria-label="Life OS navigation" hidden={!navigationOpen}>
          <div className="pn-sidebar-brand"><strong>LIFE OS</strong><i className="pn-sidebar-orb" aria-hidden="true" /><span>PHÉNGOS · ONE SYSTEM</span></div>
          <NavigationLinks onNavigate={() => { if (window.matchMedia?.("(max-width: 900px)")?.matches) setNavigationOpen(false); }} />
          <div className="pn-sidebar-end" aria-hidden="true"><span>PHÉNGOS</span><i /></div>
        </nav>
        <main className="module-surface pn-surface" id="phengos-workspace-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
      <PhengosAssistantBar />
    </div>
  );
}

export function ConnectionStatusBanner({ state }: { state: RealtimeConnectionState }) {
  if (state !== "OFFLINE" && state !== "RECONNECTING") return null;
  return (
    <div className="connection-status-banner" role="status" aria-live="polite">
      <WifiOff size={17} aria-hidden="true" />
      <span>{state === "OFFLINE" ? "Life OS is offline. Changes are not being sent." : "Live updates paused. Showing the last confirmed state while reconnecting."}</span>
      <button className="icon-button" type="button" aria-label="Refresh connection" title="Refresh connection" onClick={() => window.location.reload()}>
        <RefreshCw size={16} />
      </button>
    </div>
  );
}

function pushMessage(state: PushSetupResult) {
  if (state === "enabled") return "Reminders enabled.";
  if (state === "denied") return "Notifications are blocked.";
  if (state === "unsupported") return "Notifications are not supported here.";
  if (state === "missing_config") return "Push is not configured for this environment.";
  return "Could not enable reminders.";
}
