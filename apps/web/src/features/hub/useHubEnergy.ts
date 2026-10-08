import { useEffect, useRef, useState } from "react";

import type { HubModuleId } from "./hubModules";

export type EnergyTarget = HubModuleId | "self";
export type EnergyMode = "IDLE" | "HOVER_MODULE" | "SELECT_MODULE" | "RETURN";
export type EnergyPhase = "baseline" | "dwell" | "charge" | "orbit" | "travel" | "active" | "decay";

export type HubEnergyState = {
  mode: EnergyMode;
  phase: EnergyPhase;
  target: EnergyTarget | null;
  signal: number;
};

export const hoverTravelTimes: Record<EnergyTarget, number> = {
  calendar: 460,
  learning: 450,
  life: 490,
  fitness: 500,
  kitchen: 480,
  settings: 0,
  self: 0
};

export const clickTravelTimes: Record<EnergyTarget, number> = {
  calendar: 340,
  learning: 330,
  life: 370,
  fitness: 380,
  kitchen: 360,
  settings: 0,
  self: 0
};

const idleState: HubEnergyState = { mode: "IDLE", phase: "baseline", target: null, signal: 0 };

export function useHubEnergy() {
  const [state, setState] = useState<HubEnergyState>(idleState);
  const stateRef = useRef<HubEnergyState>(idleState);
  const timers = useRef<number[]>([]);
  const signal = useRef(0);

  function clearTimers() {
    timers.current.forEach((timer) => window.clearTimeout(timer));
    timers.current = [];
  }

  function schedule(callback: () => void, delay: number) {
    timers.current.push(window.setTimeout(callback, delay));
  }

  function commit(nextState: HubEnergyState) {
    stateRef.current = nextState;
    setState(nextState);
  }

  function hover(target: Exclude<EnergyTarget, "settings">) {
    if (stateRef.current.mode === "SELECT_MODULE") return;
    clearTimers();
    signal.current += 1;
    const nextSignal = signal.current;
    if (target === "self") {
      commit({ mode: "HOVER_MODULE", phase: "charge", target, signal: nextSignal });
      schedule(() => commit({ mode: "HOVER_MODULE", phase: "active", target, signal: nextSignal }), 120);
      return;
    }
    commit({ mode: "HOVER_MODULE", phase: "dwell", target, signal: nextSignal });
    schedule(() => commit({ mode: "HOVER_MODULE", phase: "charge", target, signal: nextSignal }), 160);
    schedule(() => commit({ mode: "HOVER_MODULE", phase: "orbit", target, signal: nextSignal }), 215);
    schedule(() => commit({ mode: "HOVER_MODULE", phase: "travel", target, signal: nextSignal }), 270);
    schedule(() => commit({ mode: "HOVER_MODULE", phase: "active", target, signal: nextSignal }), 270 + hoverTravelTimes[target]);
  }

  function leave(target: Exclude<EnergyTarget, "settings">) {
    const current = stateRef.current;
    if (current.mode === "SELECT_MODULE" || current.target !== target) return;
    clearTimers();
    commit({ mode: "HOVER_MODULE", phase: "decay", target, signal: current.signal });
    schedule(() => commit(idleState), current.phase === "dwell" ? 280 : 760);
  }

  function select(target: EnergyTarget) {
    clearTimers();
    signal.current += 1;
    const nextSignal = signal.current;
    commit({ mode: "SELECT_MODULE", phase: target === "settings" ? "active" : "charge", target, signal: nextSignal });
    if (target !== "settings" && target !== "self") {
      schedule(() => commit({ mode: "SELECT_MODULE", phase: "orbit", target, signal: nextSignal }), 70);
      schedule(() => commit({ mode: "SELECT_MODULE", phase: "travel", target, signal: nextSignal }), 130);
      schedule(() => commit({ mode: "SELECT_MODULE", phase: "active", target, signal: nextSignal }), 130 + clickTravelTimes[target]);
    } else if (target === "self") {
      schedule(() => commit({ mode: "SELECT_MODULE", phase: "active", target, signal: nextSignal }), 120);
    }
    return 130 + clickTravelTimes[target];
  }

  function setReturn(target: EnergyTarget | null) {
    clearTimers();
    signal.current += 1;
    commit({ mode: "RETURN", phase: "active", target, signal: signal.current });
    schedule(() => commit(idleState), 900);
  }

  useEffect(() => () => clearTimers(), []);

  return { state, hover, leave, select, setReturn };
}
