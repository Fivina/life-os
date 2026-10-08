import { describe, expect, it } from "vitest";
import { PHENGOS_FILM_SECONDS, phengosProjection, smoothCamera } from "./phengosProjection";

describe("shared cinematic projection", () => {
  it("settles without velocity or acceleration discontinuities", () => {
    expect(smoothCamera(-1)).toBe(0);
    expect(smoothCamera(2)).toBe(1);
    expect(smoothCamera(0.5)).toBe(0.5);
    expect(smoothCamera(0.001)).toBeLessThan(0.00000002);
    expect(1 - smoothCamera(0.999)).toBeLessThan(0.00000002);
  });
  it.each([[1920, 1080], [1440, 900], [390, 844], [320, 568]])("keeps the wordmark and live actor within %i x %i", (width, height) => {
    for (let time = 0; time <= PHENGOS_FILM_SECONDS; time += 0.1) {
      const p = phengosProjection(time, width, height);
      expect(p.y).toBe(0);
      expect(width / 2 + p.x + p.size * p.scale / 2).toBeLessThan(width);
      expect(width / 2 + p.x - p.size * p.scale / 2).toBeGreaterThan(0);
      expect(width / 2 - 4.15 * p.titleUnit).toBeGreaterThan(0);
      expect(width / 2 + 2.95 * p.titleUnit).toBeLessThan(width);
    }
    const end = phengosProjection(PHENGOS_FILM_SECONDS, width, height);
    expect(end.x).toBe(0);
    expect(end.y).toBeCloseTo(0);
    expect(end.scale).toBe(1);
    expect(end.titleOpacity).toBe(0);
    expect(phengosProjection(100, width, height)).toEqual(end);
  });
});
