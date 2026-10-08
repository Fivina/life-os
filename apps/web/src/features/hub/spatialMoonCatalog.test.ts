import { describe, expect, it } from "vitest";

import { spatialDomains } from "./spatialNavigation";
import { spatialMoonCatalog } from "./spatialMoonCatalog";

const canonicalRoutes = new Set(["/calendar", "/learning", "/kitchen", "/fitness", "/life", "/finance", "/social", "/movies", "/notebook"]);
const supportedAnchors = new Set([
  "/kitchen#nutrition",
  "/kitchen#shopping",
  "/fitness#training",
  "/learning#study-log",
  "/learning#study-candidates",
  "/learning#exams",
  "/life#goals",
  "/calendar#daily-list",
]);

describe("spatialMoonCatalog", () => {
  it("matches the authoritative taxonomy and keeps ids unique", () => {
    const labels = Object.fromEntries(Object.entries(spatialMoonCatalog).map(([domain, moons]) => [domain, moons.map(({ label }) => label)]));
    const ids = Object.values(spatialMoonCatalog).flat().map((moon) => moon.id);

    expect(Object.keys(spatialMoonCatalog).sort()).toEqual(spatialDomains.map(({ id }) => id).sort());
    expect(labels).toEqual({
      calendar: ["Calendar", "Daily list"],
      learning: ["Study Log", "Study Candidates", "Exams"],
      home: ["Cleaning", "Kitchen", "Shopping"],
      fitness: ["Nutrition", "Training"],
      life: ["Finance", "Goals", "Social life", "Film", "Notebook"],
    });
    expect(spatialMoonCatalog.fitness[0]).toMatchObject({ id: "nutrition", href: "/kitchen#nutrition", availability: "ready" });
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("uses safe existing routes and marks the missing route as planned", () => {
    for (const moon of Object.values(spatialMoonCatalog).flat()) {
      if (moon.href === null) {
        expect(moon.availability).toBe("planned");
        continue;
      }

      expect(moon.availability).toBe("ready");
      expect(canonicalRoutes.has(moon.href) || supportedAnchors.has(moon.href)).toBe(true);
      expect(moon.href).not.toContain("?");
    }
  });
});
