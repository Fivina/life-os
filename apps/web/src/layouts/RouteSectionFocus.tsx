import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/** Restore section identity when a moon opens an existing, possibly lazy, workspace. */
export function RouteSectionFocus() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash) return;
    let id: string;
    try { id = decodeURIComponent(hash.slice(1)); } catch { return; }
    let observer: MutationObserver | undefined;
    let frame = 0;
    let finished = false;
    const locate = () => {
      const target = document.getElementById(id);
      if (!target || finished) return;
      finished = true;
      observer?.disconnect();
      frame = requestAnimationFrame(() => {
        target.scrollIntoView?.({ block: "start", behavior: "instant" });
        target.focus({ preventScroll: true });
      });
    };
    observer = new MutationObserver(locate);
    observer.observe(document.body, { childList: true, subtree: true });
    locate();
    const timeout = window.setTimeout(() => observer?.disconnect(), 3000);
    return () => { finished = true; observer?.disconnect(); cancelAnimationFrame(frame); window.clearTimeout(timeout); };
  }, [pathname, hash]);
  return null;
}
