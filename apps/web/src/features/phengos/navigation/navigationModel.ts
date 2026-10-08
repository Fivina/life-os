import { phengosFeatures } from "../phengosFeatures";

export type PhengosFeature = (typeof phengosFeatures)[number];
export type PhengosGroup = PhengosFeature["group"];

export const navigationGroups: readonly PhengosGroup[] = [
  "Home", "Calendar", "Self", "Learning", "Fitness", "Life", "System",
];

export function activeFeature(pathname: string, hash: string): PhengosFeature | undefined {
  let section = hash;
  try { section = decodeURIComponent(hash); } catch { /* Unknown hashes use the route overview. */ }
  return phengosFeatures.find(feature => feature.href === pathname + section)
    ?? phengosFeatures.find(feature => feature.href === pathname);
}

export function groupOverview(group: PhengosGroup): PhengosFeature {
  return phengosFeatures.find(feature => feature.group === group && !feature.href.includes("#"))!;
}

export function backFallback(feature: PhengosFeature | undefined): string {
  if (!feature) return "/";
  const overview = groupOverview(feature.group).href;
  return feature.href === overview ? "/" : overview;
}

export const phengosHomeState = { phengosReturn: true, phengosOpen: true };
