import { ArrowLeft, BookOpen, CalendarDays, ChevronRight, CircleDot, Dumbbell, House, MessageCircle, Search, Settings, Utensils } from "lucide-react";
import { useEffect, useState, type CSSProperties, type RefObject } from "react";
import { Link, useLocation } from "react-router-dom";
import { phengosFeatures } from "../phengosFeatures";
import { activeFeature, navigationGroups, phengosHomeState, type PhengosGroup } from "./navigationModel";
import { useWorkspaceBack } from "./useWorkspaceBack";

export function NavigationLinks({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation();
  const active = activeFeature(location.pathname, location.hash);
  const [expanded, setExpanded] = useState<PhengosGroup | "Search" | null>(null);
  const [query, setQuery] = useState("");
  useEffect(() => setExpanded(null), [location.pathname, location.hash]);
  const groupIcons = { Home: House, Calendar: CalendarDays, Self: MessageCircle, Learning: BookOpen,
    Fitness: Dumbbell, Life: CircleDot, System: Settings } as const;
  const selectedFeatures = expanded === "Search"
    ? phengosFeatures.filter(feature => `${feature.label} ${feature.detail} ${feature.group}`.toLowerCase().includes(query.trim().toLowerCase()))
    : phengosFeatures.filter(feature => feature.group === expanded);

  const domainButton = (group: PhengosGroup) => {
    const Icon = groupIcons[group];
    const representative = phengosFeatures.find(feature => feature.group === group)!;
    const selected = active?.group === group && !(group === "Home" && location.pathname === "/kitchen");
    return <button key={group} type="button" className="pn-domain-button" data-active={selected}
      data-expanded={expanded === group} style={{ "--pn-accent": active?.group === group ? active.color : representative.color } as CSSProperties}
      aria-label={group === "System" ? "Settings" : group}
      aria-pressed={selected} aria-expanded={expanded === group}
      aria-controls={expanded === group ? "pn-feature-panel" : undefined}
      onClick={() => setExpanded(current => current === group ? null : group)}>
      <Icon size={21} aria-hidden="true" /><span>{group === "System" ? "Settings" : group}</span>
    </button>;
  };

  return <div className="pn-navigation-inner">
    <div className="pn-domain-list" role="group" aria-label="Life OS domains">
      {navigationGroups.filter(group => group !== "System").map(domainButton)}
      <Link className="pn-domain-button pn-kitchen-link" to="/kitchen" aria-current={location.pathname === "/kitchen" && !location.hash ? "page" : undefined}
        data-active={location.pathname === "/kitchen"} style={{ "--pn-accent": location.pathname === "/kitchen" ? active?.color ?? "var(--life-domain-home)" : "var(--life-domain-home)" } as CSSProperties}
        onClick={() => onNavigate?.()}><Utensils size={21} aria-hidden="true" /><span>Kitchen</span></Link>
    </div>
    <div className="pn-utility-list" role="group" aria-label="Life OS utilities">
      <button type="button" className="pn-search-button" data-expanded={expanded === "Search"}
        style={{ "--pn-accent": "var(--life-domain-overview)" } as CSSProperties}
        aria-expanded={expanded === "Search"} aria-controls={expanded === "Search" ? "pn-feature-panel" : undefined}
        onClick={() => { setQuery(""); setExpanded(current => current === "Search" ? null : "Search"); }}>
        <Search size={21} aria-hidden="true" /><span>Search</span>
      </button>
      {domainButton("System")}
    </div>
    {expanded && <div id="pn-feature-panel" className="pn-feature-panel" role="group" aria-label={`${expanded} features`}>
      <div className="pn-feature-panel-heading"><span>YOUR WORLD / {expanded.toUpperCase()}</span>
        <button type="button" aria-label="Close feature panel" onClick={() => setExpanded(null)}>×</button></div>
      <h2>{expanded === "System" ? "Settings" : expanded}</h2>
      {expanded === "Search" && <label className="pn-feature-search-label">Find a destination
        <input autoFocus type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search LIFE OS…" />
      </label>}
      <p>{selectedFeatures.length + (expanded === "Home" ? 1 : 0)} destinations</p>
      <ul>{expanded === "Home" && <li><Link to="/" state={phengosHomeState}
        style={{ "--pn-accent": "var(--life-domain-overview)" } as CSSProperties}
        onClick={event => {
          if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
            setExpanded(null); onNavigate?.();
          }
        }}>
        <House size={18} aria-hidden="true" /><span>Overview</span>
      </Link></li>}{selectedFeatures.map(feature => {
      const [pathname, section] = feature.href.split("#");
      const samePage = pathname === location.pathname;
      const Icon = feature.icon;
      return <li key={feature.href}><Link
        to={{ pathname, hash: section ? `#${section}` : "", search: samePage ? location.search : "" }}
        state={samePage ? location.state : undefined}
        aria-current={feature === active ? "page" : undefined}
        style={{ "--pn-accent": feature.color } as CSSProperties}
        onClick={event => {
          if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
            setExpanded(null);
            onNavigate?.();
          }
        }}>
        <Icon size={18} aria-hidden="true" /><span>{feature.label}</span>
      </Link></li>;
    })}</ul>
    </div>}
  </div>;
}

export function PhengosNavigation({ open, onToggle, launcher }: {
  open: boolean; onToggle: () => void; launcher: RefObject<HTMLButtonElement | null>;
}) {
  const location = useLocation();
  const active = activeFeature(location.pathname, location.hash);
  const back = useWorkspaceBack();

  return <div className="pn-navigation-heading" style={{ "--pn-orb-accent": active?.color ?? "#78adff" } as CSSProperties}>
    <button ref={launcher} className="pn-launcher" type="button" aria-label={open ? "Close Phengos navigation" : "Open Phengos navigation"}
      title={open ? "Hide navigation" : "Show navigation"} aria-expanded={open} aria-controls="pn-sidebar" onClick={onToggle}>
      <span className="pn-circle" aria-hidden="true" />
    </button>
    <button className="pn-icon" type="button" aria-label="Back" title="Back" onClick={back}><ArrowLeft size={20} aria-hidden="true" /></button>
    <nav className="pn-breadcrumbs" aria-label="Breadcrumb">
      <ol>
        <li><Link to="/" state={phengosHomeState} aria-label="Life OS hub" title="Return to Phengos"><House size={18} aria-hidden="true" /></Link></li>
        {active && <><li><ChevronRight size={14} aria-hidden="true" /><span>{active.group}</span></li>
          <li aria-current="page"><ChevronRight size={14} aria-hidden="true" /><span>{active.label === active.group ? "Overview" : active.label}</span></li></>}
      </ol>
    </nav>
  </div>;
}
