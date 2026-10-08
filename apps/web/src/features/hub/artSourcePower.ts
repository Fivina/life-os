// Preserve the existing renderer conversion; authored scale is not photometric parity.
export function artworkSourcePowerScale(metadata: Record<string, unknown>): number {
  const scale = metadata.art_source_power_scale;
  return metadata.art_source_power_version === 1 && typeof scale === "number"
    && Number.isFinite(scale) && scale >= 0.1 && scale <= 4 ? scale : 1;
}
