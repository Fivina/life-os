import { phengosFeatures } from "../phengosFeatures";

export type PhengosFeature = (typeof phengosFeatures)[number];
export type PhengosGroup = PhengosFeature["group"];

export const navigationGroups: readonly PhengosGroup[] = [
  "Home", "Calendar", "Self", "Learning", "Fitness", "Life", "System",
];

export const primaryNavigation = [
  { label: "Home", href: "/", group: "Home", color: "var(--life-domain-overview)" },
  { label: "Calendar", href: "/calendar", group: "Calendar", color: "var(--life-domain-calendar)" },
  { label: "Chat", href: "/chat", group: "Self", color: "var(--life-domain-chat)" },
  { label: "Learning", href: "/learning", group: "Learning", color: "var(--life-domain-learning)" },
  { label: "Fitness", href: "/fitness", group: "Fitness", color: "var(--life-domain-fitness)" },
  { label: "Life", href: "/life", group: "Life", color: "var(--life-domain-life)" },
  { label: "Kitchen", href: "/kitchen", group: "Home", color: "var(--life-domain-home)" },
] as const satisfies ReadonlyArray<{ label: string; href: string; group: PhengosGroup; color: string }>;

export function visibleGroup(group: PhengosGroup): string {
  return group === "Self" ? "Chat" : group === "System" ? "Settings" : group;
}

export function activeFeature(pathname: string, hash: string): PhengosFeature | undefined {
  let section = hash;
  try { section = decodeURIComponent(hash); } catch { /* Unknown hashes use the route overview. */ }
  return phengosFeatures.find(feature => feature.href === pathname + section)
    ?? phengosFeatures.find(feature => feature.href === pathname)
    ?? (pathname === "/settings/integrations" || pathname.startsWith("/settings/integrations/")
      ? phengosFeatures.find(feature => feature.href === "/settings")
      : undefined);
}

export function groupOverview(group: PhengosGroup): PhengosFeature {
  return phengosFeatures.find(feature => feature.group === group && !feature.href.includes("#"))!;
}

export function backFallback(feature: PhengosFeature | undefined): string {
  if (!feature) return "/";
  if (feature.href === "/chat") return "/";
  const overview = groupOverview(feature.group).href;
  return feature.href === overview ? "/" : overview;
}

export const phengosHomeState = { phengosReturn: true, phengosOpen: true };
