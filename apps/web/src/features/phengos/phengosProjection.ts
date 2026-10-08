export const PHENGOS_FILM_SECONDS = 8.5;

export function smoothCamera(value: number): number {
  const t = Math.min(1, Math.max(0, value));
  return t * t * t * (t * (6 * t - 15) + 10);
}

// Mirrors the lens, sensor, circle radius and camera track in phengos_intro.py.
// Cover framing is shared by the rendered environment and the interactive actor.
export function phengosProjection(seconds: number, width: number, height: number) {
  const time = Math.min(PHENGOS_FILM_SECONDS, Math.max(0, seconds));
  const approach = smoothCamera(time / 5);
  const center = smoothCamera((time - 3.8) / 1.2);
  const filmWidth = Math.max(width, height * 16 / 9);
  const unit = filmWidth / ((23 - 5 * approach) * 36 / 38);
  // Preserve the complete wordmark on portrait screens rather than crop its letters.
  const titleUnit = Math.min(unit, Math.max(1, width - 48) / 8.3);
  const finalSize = Math.max(64, filmWidth * 0.86 / (18 * 36 / 38));
  return {
    x: 1.2 * (1 - center) * titleUnit,
    // Character and camera share exactly the same vertical track: no relative bob.
    y: 0,
    scale: Math.max(64 * 18 / (23 - 5 * approach), unit * 0.86) / finalSize,
    size: finalSize,
    titleUnit,
    titleOpacity: smoothCamera(time / 1.2) * (1 - center),
  };
}
