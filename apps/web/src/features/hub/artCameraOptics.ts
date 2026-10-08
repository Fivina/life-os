export type ArtCameraOptics = { focusRange: number; bokehScale: number };

// Renderer-specific optics, not a claim that Blender's aperture maps numerically to bokeh.
export function artworkCameraOptics(metadata: Record<string, unknown>): ArtCameraOptics | null {
  const range = metadata.art_depth_focus_range;
  const scale = metadata.art_depth_bokeh_scale;
  if (metadata.art_camera_optics_version !== 1 ||
      typeof range !== "number" || !Number.isFinite(range) || range < 4 || range > 20 ||
      typeof scale !== "number" || !Number.isFinite(scale) || scale <= 0 || scale > 2) return null;
  return { focusRange: range, bokehScale: scale };
}
