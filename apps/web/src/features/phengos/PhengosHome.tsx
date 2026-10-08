import { ArrowUp, ArrowUpRight, BookOpen, CalendarDays, CircleDot, Dumbbell, House, Moon, RotateCcw, Search, Settings, Utensils, X } from "lucide-react";
import { motion, MotionConfig, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { PHENGOS_IDLE_MINUTES } from "./phengosJourney";
import { phengosFeatures } from "./phengosFeatures";
import { phengosHomeState, primaryNavigation, visibleGroup } from "./navigation/navigationModel";
import { usePhengosJourney } from "./usePhengosJourney";
import { PhengosContextCards } from "./PhengosContextCards";
import "./phengosTheme.css";
import "./phengos.css";

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning." : hour < 18 ? "Good afternoon." : "Good evening.";
}
const groupStyles = {
  Self: { icon: CircleDot, color: "var(--ph-self)", description: "Ask, plan, and think with PHENGOS." },
  Home: { icon: House, color: "var(--ph-home)", description: "Your living space and everyday essentials." },
  Fitness: { icon: Dumbbell, color: "var(--ph-fitness)", description: "Training, recovery, and nutrition." },
  Life: { icon: CircleDot, color: "var(--ph-life)", description: "Goals, money, people, and ideas." },
  Calendar: { icon: CalendarDays, color: "var(--ph-calendar)", description: "Time, plans, and commitments." },
  Learning: { icon: BookOpen, color: "var(--ph-learning)", description: "Courses, notes, and progress." },
  System: { icon: Settings, color: "var(--ph-system)", description: "Preferences and your personal model." },
} as const;
export default function PhengosHome() {
  const navigate = useNavigate();
  const routeState = useLocation().state;
  const returningHome = routeState?.phengosReturn === true;
  const returnedLayer = routeState?.phengosOpen === true ? "overview" : null;
  const host = useRef<HTMLElement>(null);
  const actor = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const film = useRef<HTMLVideoElement>(null);
  const reduced = !!useReducedMotion();
  const [images, setImages] = useState({ idle: "loading", opening: "loading", rest: "loading" });
  const [loadTimedOut, setLoadTimedOut] = useState(false);
  const [draft, setDraft] = useState(() => { try { return window.sessionStorage.getItem("life-os:phengos-draft") ?? ""; } catch { return ""; } });
  const [menuOpen, setMenuOpen] = useState(returnedLayer !== null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filmEnabled, setFilmEnabled] = useState(true);
  const [filmPlaying, setFilmPlaying] = useState(false);
  const [filmReplay, setFilmReplay] = useState(0);
  const [pageVisible, setPageVisible] = useState(() => !document.hidden);
  const ready = loadTimedOut || images.idle !== "loading" && images.opening !== "loading";
  const { phase, open, rest, replay, minutes, setIdleMinutes, advanceIntro } = usePhengosJourney(ready, reduced, host, filmEnabled && !reduced, returningHome);
  const intro = ["wordmark", "center", "ascent"].includes(phase);
  const movieVisible = intro && filmEnabled && !reduced;
  const working = phase === "workspace";
  const searchResults = phengosFeatures.filter(feature => `${feature.label} ${feature.detail} ${visibleGroup(feature.group)}`.toLowerCase().includes(searchQuery.trim().toLowerCase()));

  useEffect(() => {
    if (!intro || !filmEnabled || reduced || filmPlaying || !pageVisible) return;
    const timer = window.setTimeout(() => { setFilmEnabled(false); open(); }, 6000);
    return () => window.clearTimeout(timer);
  }, [intro, filmEnabled, reduced, filmPlaying, pageVisible, open]);

  useEffect(() => {
    const timer = window.setTimeout(() => setLoadTimedOut(true), 6000);
    return () => window.clearTimeout(timer);
  }, []);
  useEffect(() => {
    const changed = () => setPageVisible(!document.hidden);
    document.addEventListener("visibilitychange", changed);
    return () => document.removeEventListener("visibilitychange", changed);
  }, []);
  useEffect(() => {
    if (!movieVisible || !film.current) return;
    if (pageVisible) {
      const playback = film.current.play();
      if (playback && typeof playback.catch === "function") void playback.catch(() => { setFilmEnabled(false); open(); });
    }
    else film.current.pause();
  }, [movieVisible, pageVisible, open]);
  const closeMenu = () => { setMenuOpen(false); actor.current?.focus(); };
  const enterWorkspace = () => { setSearchOpen(false); setMenuOpen(true); };
  useEffect(() => {
    if (!menuOpen) return;
    menu.current?.querySelector<HTMLInputElement>("input")?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); setMenuOpen(false); actor.current?.focus(); return; }
      if (event.key !== "Tab") return;
      const controls = menu.current?.querySelectorAll<HTMLElement>("a[href], button, input, select");
      if (!controls?.length) return;
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, [menuOpen]);

  const assetResult = (id: "idle" | "opening" | "rest", status: "ready" | "error") => setImages(current => ({ ...current, [id]: status }));
  const circleLabel = working ? "Open Phengos menu" : phase === "rest" ? "Rise with Phengos" : "Skip opening";
  const skipOpening = () => { film.current?.pause(); setFilmPlaying(false); open(); };

  return <MotionConfig reducedMotion="user"><main ref={host} className="phengos-home" data-phase={phase} data-menu-open={menuOpen} aria-label="Life OS Phengos home">
    <div className="phengos-scenery" aria-hidden="true">
      <img className="phengos-idle-plate" src="/art/phengos/idle-environment-v17.png" alt="" draggable={false}
        onLoad={() => assetResult("idle", "ready")} onError={() => assetResult("idle", "error")} hidden={images.idle === "error"} />
      <img className="phengos-workspace-plate" src="/art/phengos/workspace-environment-v17.png" alt="" draggable={false} />
      <img className="phengos-opening-plate" src="/art/phengos/opening-v17.png" alt="" draggable={false}
        onLoad={() => assetResult("opening", "ready")} onError={() => assetResult("opening", "error")} hidden={images.opening === "error"} />
      <img className="phengos-rest-plate" src="/art/phengos/rest-environment-v17.png" alt="" draggable={false}
        onLoad={() => assetResult("rest", "ready")} onError={() => assetResult("rest", "error")} hidden={images.rest === "error"} />
      {movieVisible && <video ref={film} key={filmReplay} className="phengos-film" src="/art/phengos/environment-v17-60.mp4" poster="/art/phengos/opening-v17.png"
        autoPlay muted playsInline preload="auto" onPlaying={() => setFilmPlaying(true)}
        onTimeUpdate={event => advanceIntro(event.currentTarget.currentTime)}
        onWaiting={() => setFilmPlaying(false)} onStalled={() => setFilmPlaying(false)}
        onEnded={() => { setFilmPlaying(false); open(); }}
        onError={() => { setFilmPlaying(false); setFilmEnabled(false); open(); }} />}
    </div>

    <div className="phengos-actor-position">
    <motion.button ref={actor} className="phengos-actor" data-rendered={movieVisible} type="button" aria-label={circleLabel} title={circleLabel} aria-hidden={menuOpen}
      aria-haspopup={working ? "dialog" : undefined} aria-expanded={working ? menuOpen : undefined} aria-controls={working ? "phengos-menu" : undefined}
      tabIndex={menuOpen ? -1 : 0}
      initial={false}
      whileHover={reduced || !working ? undefined : { scale: 1.08, rotate: -7 }}
      whileTap={reduced ? undefined : { scaleX: 1.14, scaleY: 0.86, rotate: 5 }}
      transition={{ type: "spring", stiffness: 330, damping: 16 }}
      onClick={() => working ? enterWorkspace() : skipOpening()}>
      <motion.span className="phengos-surface" initial={false} aria-hidden="true"
        animate={reduced || !pageVisible || !working ? { scaleX: 1, scaleY: 1 } : { scaleX: [1, 1.022, 1], scaleY: [1, 0.982, 1] }}
        transition={reduced || !pageVisible || !working ? { duration: 0 } : { duration: 5.8, repeat: Infinity, ease: "easeInOut" }} />
    </motion.button>
    </div>
    {movieVisible && <button className="phengos-skip" type="button" onClick={skipOpening}>Skip intro</button>}

    {menuOpen && <div className="phengos-menu-scrim" onClick={event => { if (event.target === event.currentTarget) closeMenu(); }}>
      <motion.div ref={menu} id="phengos-menu" className="phengos-menu" role="dialog" aria-modal="true" aria-labelledby="phengos-menu-title"
        style={{ "--life-context-accent": "#60a5fa" } as CSSProperties}
        initial={{ opacity: 0, y: 22, scale: 0.985 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 240, damping: 27 }}>
        <div className="phengos-menu-chrome"><span>LIFE OS <i /> PHENGOS</span><span>YOUR WORLD, IN CONTEXT</span>
          <button type="button" className="phengos-icon" aria-label="Close Phengos menu" title="Close menu" onClick={closeMenu}><X size={18} /></button></div>
        <div className="phengos-menu-layout">
          <nav className="phengos-domain-rail" aria-label="Life OS domains">
            <div className="phengos-rail-identity"><span>LIFE OS</span>
              <span className="phengos-rail-orb" aria-hidden="true" /></div>
            <div className="phengos-rail-capsule">
            <span className="phengos-rail-caption">YOUR DOMAINS</span>
            {primaryNavigation.map(item => { const Icon = item.label === "Kitchen" ? Utensils : groupStyles[item.group].icon; return <Link key={item.label}
              className={`phengos-rail-route${item.label === "Chat" ? " phengos-chat-route" : ""}`} to={item.href}
              state={item.href === "/" ? phengosHomeState : undefined} aria-current={item.href === "/" && !searchOpen ? "page" : undefined}
              style={{ "--phengos-role": item.color } as CSSProperties} onClick={() => setSearchOpen(false)}>
              {item.label === "Chat" ? <span className="pn-circle pn-chat-orb" aria-hidden="true" /> : <Icon size={20} aria-hidden="true" />}<span>{item.label}</span></Link>; })}
            <div className="phengos-rail-utilities">
              <button type="button" aria-pressed={searchOpen} onClick={() => { setSearchQuery(""); setSearchOpen(true); }} style={{ "--phengos-role": "var(--life-domain-overview)" } as CSSProperties}><Search size={20} aria-hidden="true" /><span>Search</span></button>
              <Link className="phengos-rail-route" to="/settings" style={{ "--phengos-role": groupStyles.System.color } as CSSProperties}><Settings size={20} aria-hidden="true" /><span>Settings</span></Link>
            </div>
            </div>
          </nav>
          <div className="phengos-menu-main">
            <div className="phengos-domain-heading"><span>YOUR WORLD</span><span className="phengos-layer-path">{searchOpen ? "SEARCH" : "GENERAL SURFACE"}</span></div>
            <div className="phengos-welcome phengos-welcome--overview">
              <span className="phengos-welcome-kicker">{searchOpen ? "LIFE OS / DESTINATIONS" : "LIFE OS / TODAY"}</span>
              <h2 id="phengos-menu-title">{searchOpen ? "Find your way." : greeting()}</h2>
              <p>{searchOpen ? "Search the places and tools already in your Life OS." : "What matters today, and everything one circle away."}</p></div>
            {searchOpen ? <div className="phengos-search-field"><label htmlFor="phengos-feature-search">Search LIFE OS</label><input id="phengos-feature-search" type="search" autoFocus value={searchQuery} onChange={event => setSearchQuery(event.target.value)} placeholder="Calendar, shopping, training…" /></div> : <form className="phengos-prompt" onSubmit={event => { event.preventDefault(); navigate(`/chat${draft.trim() ? `?q=${encodeURIComponent(draft.trim())}` : ""}`, { state: { phengosOriginLayer: "overview" } }); }}>
              <label className="phengos-sr-only" htmlFor="phengos-request">Message for your assistant</label>
              <input id="phengos-request" value={draft} onChange={event => { setDraft(event.target.value); try { window.sessionStorage.setItem("life-os:phengos-draft", event.target.value); } catch { /* Draft remains in this view. */ } }} placeholder="Ask anything, plan, create, or take action…" autoComplete="off" />
              <button type="submit" className="phengos-icon" aria-label="Open assistant with message" title="Open assistant with message"><ArrowUp size={19} /></button>
            </form>}
            {searchOpen ? <nav className="phengos-search-results" aria-label="Search results">{searchResults.map(feature => { const Icon = feature.icon; return <Link key={feature.href} to={feature.href} state={{ phengosOriginLayer: "overview" }} style={{ "--phengos-role": feature.color } as CSSProperties}><Icon size={20} aria-hidden="true" /><span><strong>{feature.label}</strong><small>{feature.detail}</small></span><ArrowUpRight size={16} aria-hidden="true" /></Link>; })}{searchResults.length === 0 && <p>No matching destination.</p>}</nav> : <PhengosContextCards />}
          </div>
        </div>
        <div className="phengos-menu-tools">
          <button className="phengos-icon" type="button" title="Replay opening" aria-label="Replay opening" onClick={() => { closeMenu(); setFilmPlaying(false); setFilmEnabled(true); setFilmReplay(value => value + 1); replay(); }}><RotateCcw size={17} /></button>
          <button className="phengos-icon" type="button" title="Return to horizon" aria-label="Return to horizon" onClick={() => { closeMenu(); rest(); }}><Moon size={17} /></button>
          <label className="phengos-idle-setting"><span>Idle return</span>
            <select aria-label="Idle return" value={minutes} onChange={event => setIdleMinutes(event.target.value)}>
              {PHENGOS_IDLE_MINUTES.map(value => <option key={value} value={value}>{value} min</option>)}
            </select>
          </label>
        </div>
      </motion.div>
    </div>}
    {!ready && <span className="phengos-asset-status" role="status">Preparing backdrop</span>}
    {Object.values(images).includes("error") && <span className="phengos-asset-status" role="status">Backdrop unavailable. Open Phengos to reach your features.</span>}
  </main></MotionConfig>;
}
