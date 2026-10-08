import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { idleMinutes, PHENGOS_IDLE_KEY, PHENGOS_INTRO_CUES, PHENGOS_INTRO_KEY, protectsHomeWork, type PhengosPhase } from "./phengosJourney";

function stored(storage: Storage, key: string): string | null {
  try { return storage.getItem(key); } catch { return null; }
}

export function usePhengosJourney(ready: boolean, reducedMotion: boolean, host: RefObject<HTMLElement | null>, cinematicClock = false, returningHome = false) {
  const [phase, setPhase] = useState<PhengosPhase>(() => returningHome || reducedMotion || stored(window.sessionStorage, PHENGOS_INTRO_KEY)
    ? "workspace" : "wordmark");
  const current = useRef(phase);
  const [cycle, setCycle] = useState(0);
  const [minutes, setMinutes] = useState(() => idleMinutes(stored(window.localStorage, PHENGOS_IDLE_KEY)));
  const change = useCallback((next: PhengosPhase) => {
    current.current = next;
    setPhase(next);
    if (next === "workspace") {
      try { window.sessionStorage.setItem(PHENGOS_INTRO_KEY, "seen"); } catch { /* Storage is optional. */ }
    }
  }, []);
  const open = useCallback(() => { change("workspace"); setCycle(value => value + 1); }, [change]);
  const rest = useCallback(() => { change("rest"); setCycle(value => value + 1); }, [change]);
  const replay = useCallback(() => { change(reducedMotion ? "workspace" : "wordmark"); setCycle(value => value + 1); }, [change, reducedMotion]);
  const setIdleMinutes = (value: string) => {
    const next = idleMinutes(value);
    setMinutes(next);
    try { window.localStorage.setItem(PHENGOS_IDLE_KEY, String(next)); } catch { /* Storage is optional. */ }
  };

  useEffect(() => {
    if (reducedMotion) {
      if (["wordmark", "center", "ascent"].includes(current.current)) change("workspace");
      return;
    }
    if (cinematicClock || !ready || current.current !== "wordmark") return;
    const timers = PHENGOS_INTRO_CUES.map(cue => window.setTimeout(() => change(cue.phase), cue.after));
    return () => timers.forEach(window.clearTimeout);
  }, [ready, reducedMotion, cycle, change, cinematicClock]);

  const advanceIntro = useCallback((seconds: number) => {
    if (!["wordmark", "center", "ascent"].includes(current.current)) return;
    const next = seconds >= 5 ? "ascent" : seconds >= 3.8 ? "center" : "wordmark";
    if (next !== current.current) change(next);
  }, [change]);

  useEffect(() => {
    if (phase !== "workspace") return;
    const duration = minutes * 60_000;
    let lastActivity = Date.now();
    let timer = 0;
    const check = () => {
      const elapsed = Date.now() - lastActivity;
      if (!document.hidden && elapsed >= duration && !protectsHomeWork(host.current, document.activeElement)) { rest(); return; }
      timer = window.setTimeout(check, elapsed < duration ? duration - elapsed : 30_000);
    };
    const activity = () => {
      if (Date.now() - lastActivity < 1000) return;
      lastActivity = Date.now();
      window.clearTimeout(timer);
      timer = window.setTimeout(check, duration);
    };
    const visibility = () => { window.clearTimeout(timer); if (!document.hidden) check(); };
    timer = window.setTimeout(check, duration);
    const events = ["pointermove", "pointerdown", "keydown", "wheel", "focusin"] as const;
    events.forEach(name => window.addEventListener(name, activity, { passive: true }));
    document.addEventListener("visibilitychange", visibility);
    return () => {
      window.clearTimeout(timer);
      events.forEach(name => window.removeEventListener(name, activity));
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [phase, minutes, host, rest]);

  return { phase, open, rest, replay, minutes, setIdleMinutes, advanceIntro };
}
