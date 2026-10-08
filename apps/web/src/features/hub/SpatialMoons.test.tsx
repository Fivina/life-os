import { fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Box3, Vector3 } from "three";
import { SpatialMoons, moonKey } from "./SpatialMoons";
import { domainMoonFrame } from "./spatialJourney";
import { spatialMoonCatalog } from "./spatialMoonCatalog";
import { spatialDomains } from "./spatialNavigation";

vi.mock("@react-three/fiber", () => ({ useFrame: () => {} }));
const frame = domainMoonFrame(new Box3(new Vector3(4, -1, 2), new Vector3(6, 1, 4)), new Vector3());
const frames = Object.fromEntries(spatialDomains.map(domain => [domain.id, frame]));

beforeEach(() => { vi.spyOn(console, "error").mockImplementation(() => {}); });
afterEach(() => { vi.restoreAllMocks(); });

it.each(spatialDomains)("activates every ready $label moon mesh using its actual component route", domain => {
  const onSelect = vi.fn();
  const { container } = render(<SpatialMoons frames={frames} activeDomains={[domain.id]} selectableDomain={domain.id} reducedMotion onSelect={onSelect} />);
  for (const moon of spatialMoonCatalog[domain.id]) {
    onSelect.mockClear();
    fireEvent.click(container.querySelector(`[name="${moonKey(domain.id, moon.id)}"]`)!);
    if (moon.href) expect(onSelect).toHaveBeenCalledExactlyOnceWith(moon.href);
    else expect(onSelect).not.toHaveBeenCalled();
  }
});

it("does not activate retained departing or hidden moon systems", () => {
  const onSelect = vi.fn();
  const { container } = render(<SpatialMoons frames={frames} activeDomains={["home", "life"]} selectableDomain="life" reducedMotion onSelect={onSelect} />);
  fireEvent.click(container.querySelector(`[name="${moonKey("home", "shopping")}"]`)!);
  fireEvent.click(container.querySelector(`[name="${moonKey("fitness", "training")}"]`)!);
  expect(onSelect).not.toHaveBeenCalled();
  fireEvent.click(container.querySelector(`[name="${moonKey("life", "finance")}"]`)!);
  expect(onSelect).toHaveBeenCalledExactlyOnceWith("/finance");
});
