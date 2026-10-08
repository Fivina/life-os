import { Component, lazy, Suspense, useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { ArrowLeft, MessageCircle, Settings, Orbit } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../../services/api";
import { spatialDepth, spatialDomains } from "./spatialNavigation";
import type { SpatialTarget } from "./SpatialHubScene";
import "./spatial-hub.css";

const SpatialHubScene = lazy(async () => {
  const module = await import("./SpatialHubScene");
  return { default: module.SpatialHubScene };
});

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    media.addEventListener?.("change", update);
    return () => media.removeEventListener?.("change", update);
  }, []);
  return reduced;
}

class SceneBoundary extends Component<{ children: ReactNode; onFailure: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onFailure(); }
  render() {
    if (!this.state.failed) return this.props.children;
    return <div className="spatial-fallback"><h2>Life OS</h2><p>The 3D view is unavailable on this device.</p><nav>{spatialDomains.map(domain => <Link key={domain.id} to={domain.path}>{domain.label}</Link>)}<Link to="/self">Self Core</Link><Link to="/settings">Settings</Link></nav></div>;
  }
}

export function HubPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const depth = spatialDepth(params.get("depth"));
  const reducedMotion = useReducedMotion();
  const [moving, setMoving] = useState(false);
  const [sceneFailed, setSceneFailed] = useState(false);
  const [sceneReady, setSceneReady] = useState(false);
  const [hovered, setHovered] = useState<SpatialTarget | null>(null);
  const labels = useRef<Partial<Record<SpatialTarget, HTMLButtonElement>>>({});
  const plan = useQuery({ queryKey: ["current-plan"], queryFn: () => api.currentPlan(), staleTime: 60_000, retry: false });
  const calendarAttention = ["overloaded", "impossible_before_deadline"].includes(plan.data?.overload_status ?? "");
  const onArrive = useCallback(() => { setMoving(false); setSceneReady(true); }, []);
  const onFailure = useCallback(() => { setSceneFailed(true); setMoving(false); }, []);

  const changeDepth = useCallback((next: "core" | "system") => {
    setHovered(null);
    setMoving(!reducedMotion);
    setParams(next === "system" ? { depth: "system" } : {});
  }, [reducedMotion, setParams]);

  useEffect(() => {
    const back = (event: KeyboardEvent) => { if (event.key === "Escape" && depth === "system" && !moving) changeDepth("core"); };
    window.addEventListener("keydown", back);
    return () => window.removeEventListener("keydown", back);
  }, [depth, moving, changeDepth]);

  function interaction(id: SpatialTarget) {
    return {
      ref: (element: HTMLButtonElement | null) => { if (element) labels.current[id] = element; },
      onMouseEnter: () => setHovered(id), onMouseLeave: () => setHovered(null),
      onFocus: () => setHovered(id), onBlur: () => setHovered(null),
      disabled: moving,
    };
  }

  return <section className="spatial-hub" aria-label="Life OS hub" data-depth={depth} data-moving={moving}>
    <div className="spatial-stage"><SceneBoundary onFailure={onFailure}><Suspense fallback={null}>
      <SpatialHubScene depth={depth} reducedMotion={reducedMotion} hovered={hovered} calendarAttention={calendarAttention} labels={labels} onArrive={onArrive} />
    </Suspense></SceneBoundary></div>
    <div className="spatial-warp" aria-hidden="true" />
    <div className="spatial-label-layer" hidden={sceneFailed || !sceneReady}>
      <button {...interaction("self")} className="spatial-target is-core" type="button" aria-label={depth === "core" ? "Explore Self Core system" : "Open Self Core"} onClick={() => depth === "core" ? changeDepth("system") : navigate("/self")}>
        <span>Self Core</span>
      </button>
      <button {...interaction("settings")} className="spatial-target is-settings" type="button" aria-label="Open Settings" onClick={() => navigate("/settings")}><span>Settings</span></button>
      <div className="spatial-domain-targets" hidden={depth !== "system"}>
        {spatialDomains.map(domain => <button {...interaction(domain.id)} key={domain.id} className="spatial-target" type="button" aria-label={`Open ${domain.label}`} onClick={() => navigate(domain.path)} data-attention={domain.id === "calendar" && calendarAttention} title={domain.id === "calendar" && calendarAttention ? "Planner reports insufficient capacity" : domain.identity} style={{ "--object-color": domain.color } as CSSProperties}>
          <span>{domain.label}</span><small>{domain.id === "calendar" && calendarAttention ? "Needs attention" : domain.identity}</small>
        </button>)}
      </div>
    </div>
    <div className="spatial-controls">
      <div>{depth === "system" ? <button className="icon-button" type="button" title="Return to Self Core" aria-label="Return to Self Core" disabled={moving} onClick={() => changeDepth("core")}><ArrowLeft size={19} /></button> : null}</div>
      <span className="spatial-depth" aria-live="polite">{moving ? "In transit" : depth === "core" ? "Self Core" : "Primary system"}</span>
      <nav aria-label="Quick access"><Link className="icon-button" to="/space" title="Spatial workspace" aria-label="Spatial workspace"><Orbit size={18} /></Link><Link className="icon-button" to="/self" title="Talk to Self Core" aria-label="Talk to Self Core"><MessageCircle size={18} /></Link><Link className="icon-button" to="/settings" title="Settings" aria-label="Settings"><Settings size={18} /></Link></nav>
    </div>
  </section>;
}
