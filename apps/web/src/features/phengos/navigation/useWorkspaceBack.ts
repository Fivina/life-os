import { useLayoutEffect, useRef } from "react";
import { useLocation, useNavigate, useNavigationType } from "react-router-dom";
import { activeFeature, backFallback, phengosHomeState } from "./navigationModel";

export function useWorkspaceBack() {
  const location = useLocation();
  const action = useNavigationType();
  const navigate = useNavigate();
  const history = useRef({ keys: [location.key], index: 0 });

  useLayoutEffect(() => {
    const trail = history.current;
    if (trail.keys[trail.index] === location.key) return;
    if (action === "PUSH") {
      trail.keys = [...trail.keys.slice(0, trail.index + 1), location.key];
      trail.index += 1;
    } else if (action === "REPLACE") {
      trail.keys[trail.index] = location.key;
    } else {
      const index = trail.keys.indexOf(location.key);
      // An unobserved POP may have come from outside this shell. Never assume its predecessor is safe.
      if (index < 0) { trail.keys = [location.key]; trail.index = 0; }
      else trail.index = index;
    }
  }, [action, location.key]);

  return () => {
    if (history.current.index > 0) { navigate(-1); return; }
    if (location.state?.phengosOriginLayer === "overview" || location.state?.phengosOriginLayer === "domain") {
      navigate("/", { replace: true, state: phengosHomeState });
      return;
    }
    const fallback = backFallback(activeFeature(location.pathname, location.hash));
    navigate(fallback, { replace: true, state: fallback === "/" ? phengosHomeState : undefined });
  };
}
