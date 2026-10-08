# Spatial Motion Storyboard

> Proposed timing for review. This documents future motion only; it is not
> existing behavior and does not authorize implementation in this milestone.

## Motion Intent

Use a cinematic, smooth spaceship warp: one readable acceleration, a quiet
arrival, and enough continuity that the user never loses orientation. Keep the
scene sparse and functional. Avoid theatrical clutter, camera spins, flashes,
or decorative effects that compete with the selected object.

## Camera Beats

| Beat | Time | Camera and scene intent |
| --- | ---: | --- |
| Ready | 0.00 s | Preserve the current view. Keep the source object, destination identity, and shell stable. |
| Commit | 0.00-0.10 s | Lock the transition input; confirm the selected target with a restrained focus lift. |
| Launch | 0.10-0.30 s | Ease camera toward the target and slightly compress the source orbit. No snap or roll. |
| Warp | 0.30-0.82 s | Use the bounded forward surge and sparse directional streaks. Keep the destination on a predictable screen-side trajectory. |
| Arrival | 0.82-1.05 s | Decelerate into the destination framing; settle scale, depth, lighting, and orbit motion together. |
| Label settle | 1.05-1.15 s | Reveal/settle the destination label and interaction targets; release the input lock at completion. |

The existing primary-system travel reference is 1.15 seconds with quintic
arrival easing. Future `core -> system` and `system -> domain` transitions
should preserve that ceiling unless a reviewed interaction contract changes it.
The future `domain -> system -> core` return should use the same beats in
reverse order, with no forced replay of the initial entry sequence.

## Continuity Rules

- Maintain a stable world-up and a consistent camera handedness; never rotate
  the user through a full scene spin.
- Carry the selected object's color, relative position, and motion direction
  through the warp. The destination should feel like the same object becoming
  a closer place, not a replacement screen.
- Keep the source silhouette visible through Launch and the destination
  silhouette readable before Arrival ends. Do not cross-fade both to empty
  space.
- Pause or damp orbital motion while the pointer/focus target is being
  committed; resume it only after the arrival settles.
- Preserve URL-backed depth and route identity. A failed renderer or invalid
  destination must resolve through the existing navigation boundary.

## Pointer, Focus, and Touch

- Pointer hover may apply a small scale and halo lift, damped into the warp;
  it must not move the camera by itself.
- Keyboard focus and pointer focus use the same target framing and label
  state. Focus must remain visible throughout the transition.
- Commit on an explicit activation, not on hover. Escape or equivalent cancel
  input should be honored before Commit completes where the host interaction
  contract permits it.
- Keep every projected navigation target at least 44 x 44 CSS px on touch
  layouts, with a visible larger hit area than the rendered object where
  needed. Avoid relying on precise drag gestures.
- Touch activation should use the same 1.15-second timing and destination
  continuity as pointer activation; do not add a separate flourish.

## Labels and Attention

- Labels appear only when the destination is discoverable or focused, remain
  legible during Arrival, and settle before input unlock.
- Use the canonical labels and identities: Calendar / Chrono Ring, Learning /
  Neural Bloom, Home / Supply Core, Fitness / Orbit Barbell, and Life / Core
  Earth. Home continues to resolve to the existing `/kitchen` destination.
- Red is reserved for explicit attention states only, using `#ff4d57`. It must
  not be used for generic selection, hover, warp streaks, or camera accents.
  Selection and hover retain each object's native color.

## Reduced Motion

When reduced motion is requested, skip the surge, streaks, blur, camera zoom,
and decorative orbital motion. Use an immediate or short (maximum 0.15-second)
focus/route change with stable framing, persistent focus visibility, and the
same labels, hit targets, URL state, and error handling. Do not rely on motion
to communicate selection or depth.

## 60 FPS Budget

- Design for a 16.67 ms frame budget on the target device; avoid introducing
  per-frame React state updates during travel.
- Keep the warp effects bounded to the existing shared scene and small,
  deterministic allocations. No effect should require a second canvas or a
  full-screen particle layer.
- Treat 60 FPS as the acceptance target, not a promise across real devices.
  Profile desktop and representative mobile hardware, including touch and
  reduced-motion paths, before approving the timings.
- If a frame misses budget, reduce streak count, blur quality, and secondary
  orbit detail before changing the camera beat or making labels harder to
  read.
