export type PhengosPhase = "wordmark" | "center" | "ascent" | "workspace" | "rest";
export const PHENGOS_INTRO_KEY = "life-os:phengos-blender-opening-v17";
export const PHENGOS_IDLE_KEY = "life-os:phengos-idle-minutes";
export const PHENGOS_IDLE_MINUTES = [10, 12, 15] as const;
export const PHENGOS_INTRO_CUES = [
  { after: 3800, phase: "center" },
  { after: 5000, phase: "ascent" },
  { after: 8500, phase: "workspace" },
] as const;

export function idleMinutes(value: unknown): 10 | 12 | 15 {
  const number = Number(value);
  return PHENGOS_IDLE_MINUTES.includes(number as 10 | 12 | 15) ? number as 10 | 12 | 15 : 12;
}

export function protectsHomeWork(root: HTMLElement | null, focused: Element | null): boolean {
  return !!root && (!!focused && root.contains(focused) && focused.matches("input, textarea, select, [contenteditable=true]")
    || !!root.querySelector("dialog[open], [role=dialog], details[open]"));
}
