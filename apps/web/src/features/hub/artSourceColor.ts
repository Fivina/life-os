const LEGACY_SOURCE_COLOR = [0.22, 0.62, 1] as const;

// Authored values are linear RGB, not sRGB display colors.
export function artworkSourceColor(metadata: Record<string, unknown>): [number, number, number] {
  const color = metadata.art_source_color_linear;
  if (metadata.art_source_color_version === 1 && Array.isArray(color) && color.length === 3
    && Array.from(color).every(channel => typeof channel === "number" && Number.isFinite(channel)
      && channel >= 0 && channel <= 1) && color.some(channel => channel > 0)) {
    return [color[0], color[1], color[2]];
  }
  return [...LEGACY_SOURCE_COLOR];
}
