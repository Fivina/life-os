import { describe, expect, it } from "vitest";
import { artworkCameraOptics } from "./artCameraOptics";

const authored = { art_camera_optics_version: 1, art_depth_focus_range: 10, art_depth_bokeh_scale: 1.5 };

describe("authored static artwork optics", () => {
  it("preserves bounded world-space focus range and bokeh strength", () => {
    expect(artworkCameraOptics(authored)).toEqual({ focusRange: 10, bokehScale: 1.5 });
    expect(authored.art_depth_focus_range).toBe(10);
  });

  it.each([
    {}, { ...authored, art_camera_optics_version: 2 },
    { ...authored, art_camera_optics_version: "1" },
    { ...authored, art_depth_focus_range: NaN },
    { ...authored, art_depth_focus_range: Infinity },
    { ...authored, art_depth_focus_range: "10" },
    { ...authored, art_depth_focus_range: 0 },
    { ...authored, art_depth_focus_range: 21 },
    { ...authored, art_depth_bokeh_scale: NaN },
    { ...authored, art_depth_bokeh_scale: Infinity },
    { ...authored, art_depth_bokeh_scale: 0 },
    { ...authored, art_depth_bokeh_scale: 2.1 },
  ])("disables optics for missing or invalid metadata %j", metadata => {
    expect(artworkCameraOptics(metadata)).toBeNull();
  });
});
