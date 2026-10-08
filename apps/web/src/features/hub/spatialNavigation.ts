export type SpatialDepth = "core" | "system";
export const ATTENTION_RED = "#ff4d57";
export const WARP_SECONDS = 1.15;

export const spatialDomains = [
  { id: "calendar", label: "Calendar", identity: "Chrono Ring", path: "/calendar", color: "#a59bff", angle: 2.55 },
  { id: "learning", label: "Learning", identity: "Neural Bloom", path: "/learning", color: "#d2a7ff", angle: 0.83 },
  { id: "home", label: "Home", identity: "Supply Core", path: "/kitchen", color: "#f2c07b", angle: 3.63 },
  { id: "fitness", label: "Fitness", identity: "Orbit Barbell", path: "/fitness", color: "#83dfff", angle: -0.1 },
  { id: "life", label: "Life", identity: "Core Earth", path: "/life", color: "#94e4c4", angle: -1.12 },
] as const;
export type SpatialDomainId = typeof spatialDomains[number]["id"];

export function spatialDepth(value: string | null): SpatialDepth {
  return value === "system" ? "system" : "core";
}

export function smoothTravel(value: number): number {
  const t = Math.min(1, Math.max(0, value));
  return t * t * t * (t * (t * 6 - 15) + 10);
}

export function domainPosition(angle: number, compact: boolean, time = 0): [number, number, number] {
  const theta = angle + time * 0.0005;
  return [Math.cos(theta) * (compact ? 2.05 : 5.8), Math.sin(theta) * (compact ? 3.85 : 2.8) + 0.45, Math.sin(theta) * 0.55];
}
