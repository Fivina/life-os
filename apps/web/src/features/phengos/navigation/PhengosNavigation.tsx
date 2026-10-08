import { ArrowLeft, BookOpen, CalendarDays, ChevronRight, CircleDot, Dumbbell, House, Search, Settings, Utensils } from "lucide-react";
import { useEffect, useState, type CSSProperties, type RefObject } from "react";
import { Link, useLocation } from "react-router-dom";
import { phengosFeatures } from "../phengosFeatures";
import { activeFeature, phengosHomeState, primaryNavigation, visibleGroup } from "./navigationModel";
import { useWorkspaceBack } from "./useWorkspaceBack";

const navigationIcons = {
  Home: House,
  Calendar: CalendarDays,
  Chat: CircleDot,
  Learning: BookOpen,
  Fitness: Dumbbell,
  Life: CircleDot,
  Kitchen: Utensils,
} as const;

function isPrimaryActive(pathname: string, label: (typeof primaryNavigation)[number]["label"]) {
  if (label === "Home") return pathname === "/";
  if (label === "Kitchen") return pathname === "/kitchen";
  if (label === "Chat") return pathname === "/chat" || pathname === "/self" || pathname === "/assistant" || pathname === "/self/assistant";
  if (label === "Life") return ["/life", "/finance", "/social", "/movies", "/notebook"].some(path => pathname === path || pathname.startsWith(`${path}/`));
  return pathname === primaryNavigation.find(item => item.label === label)?.href;
}

export function NavigationLinks({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation();
  const active = activeFeature(location.pathname, location.hash);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  useEffect(() => setSearchOpen(false), [location.pathname, location.hash]);
  const searchResults = phengosFeatures.filter(feature =>
    `${feature.label} ${feature.detail} ${visibleGroup(feature.group)}`.toLowerCase().includes(query.trim().toLowerCase()),
  );

  return <div className="pn-navigation-inner">
    <div className="pn-domain-list" role="group" aria-label="Life OS domains">
      {primaryNavigation.map(item => {
        const Icon = navigationIcons[item.label];
        const selected = isPrimaryActive(location.pathname, item.label);
        return <Link key={item.label} className={`pn-domain-button${item.label === "Chat" ? " pn-chat-link" : ""}`}
          to={item.href} state={item.href === "/" ? phengosHomeState : undefined}
          data-active={selected} aria-current={selected ? "page" : undefined}
          style={{ "--pn-accent": item.color } as CSSProperties} onClick={() => onNavigate?.()}>
          {item.label === "Chat" ? <span className="pn-circle pn-chat-orb" aria-hidden="true" /> : <Icon size={21} aria-hidden="true" />}
          <span>{item.label}</span>
        </Link>;
      })}
    </div>
    <div className="pn-utility-list" role="group" aria-label="Life OS utilities">
      <button type="button" className="pn-search-button" data-expanded={searchOpen}
        style={{ "--pn-accent": "var(--life-domain-overview)" } as CSSProperties}
        aria-expanded={searchOpen} aria-controls={searchOpen ? "pn-search-panel" : undefined}
        onClick={() => { setQuery(""); setSearchOpen(current => !current); }}>
        <Search size={21} aria-hidden="true" /><span>Search</span>
      </button>
      <Link className="pn-domain-button" to="/settings" data-active={location.pathname === "/settings" || location.pathname.startsWith("/settings/")}
        aria-current={location.pathname === "/settings" || location.pathname.startsWith("/settings/") ? "page" : undefined}
        style={{ "--pn-accent": "var(--life-domain-system)" } as CSSProperties} onClick={() => onNavigate?.()}>
        <Settings size={21} aria-hidden="true" /><span>Settings</span>
      </Link>
    </div>
    {searchOpen && <div id="pn-search-panel" className="pn-feature-panel pn-search-panel" role="search" aria-label="Search destinations">
      <div className="pn-feature-panel-heading"><span>YOUR WORLD / SEARCH</span>
        <button type="button" aria-label="Close search" onClick={() => setSearchOpen(false)}>×</button></div>
      <h2>Search</h2>
      <label className="pn-feature-search-label">Find a destination
        <input autoFocus type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search LIFE OS…" />
      </label>
      <p>{searchResults.length} destinations</p>
      <ul>{searchResults.map(feature => {
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
              setSearchOpen(false);
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
        {active && <><li><ChevronRight size={14} aria-hidden="true" /><span>{visibleGroup(active.group)}</span></li>
          <li aria-current="page"><ChevronRight size={14} aria-hidden="true" /><span>{active.label === visibleGroup(active.group) ? "Overview" : active.label}</span></li></>}
      </ol>
    </nav>
  </div>;
}
