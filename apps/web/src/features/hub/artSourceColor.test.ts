import { describe, expect, it } from "vitest";
import { artworkSourceColor } from "./artSourceColor";

const authored = { art_source_color_version: 1, art_source_color_linear: [0.56, 0.76, 1] };

describe("versioned artwork source color", () => {
  it("preserves linear RGB and returns an independent tuple", () => {
    const result = artworkSourceColor(authored);
    expect(result).toEqual([0.56, 0.76, 1]);
    result[0] = 0;
    expect(authored.art_source_color_linear).toEqual([0.56, 0.76, 1]);
  });

  it("allows bounded zero-valued channels without converting color spaces", () => {
    expect(artworkSourceColor({ ...authored, art_source_color_linear: [0, 0.5, 1] }))
      .toEqual([0, 0.5, 1]);
  });

  it.each([
    {}, { ...authored, art_source_color_version: 2 },
    { ...authored, art_source_color_version: "1" },
    ...[[0, 0, 0], [0.56, 0.76], [0.56, 0.76, 1, 1], ["0.56", 0.76, 1],
      [NaN, 0.76, 1], [Infinity, 0.76, 1], [-0.1, 0.76, 1], [0.56, 0.76, 1.1],
      Object.assign(Array(3), { 0: 0.56, 2: 1 }),
      null, "#aaccff"].map(color => ({ ...authored, art_source_color_linear: color })),
  ])("retains legacy lighting for invalid or missing metadata %j", metadata => {
    expect(artworkSourceColor(metadata)).toEqual([0.22, 0.62, 1]);
  });
});
