import { describe, expect, it } from "vitest";
import { artworkSourcePowerScale } from "./artSourcePower";

const authored = { art_source_power_version: 1, art_source_power_scale: 2.5 };

describe("versioned artwork source power", () => {
  it("retains the authored light ratio without mutating metadata", () => {
    expect(artworkSourcePowerScale(authored)).toBe(2.5);
    expect(authored.art_source_power_scale).toBe(2.5);
  });

  it.each([
    {}, { ...authored, art_source_power_version: 2 },
    { ...authored, art_source_power_version: "1" },
    { ...authored, art_source_power_scale: "2.5" },
    { ...authored, art_source_power_scale: NaN },
    { ...authored, art_source_power_scale: Infinity },
    { ...authored, art_source_power_scale: 0 },
    { ...authored, art_source_power_scale: 4.1 },
  ])("preserves baseline power for legacy or invalid metadata %j", metadata => {
    expect(artworkSourcePowerScale(metadata)).toBe(1);
  });
});
