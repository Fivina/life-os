# Phengos Shared Scale Study v9

Source: NASA/JPL mean radii, https://ssd.jpl.nasa.gov/planets/phys_par.html.
These references control size only; the distant worlds retain their fictional
orange/red terrain and are not literal depictions of Mars or Mercury.

## One Common Scale

| Reference | Mean radius (km) | Earth = 10 | Scene radius |
| --- | ---: | ---: | ---: |
| Earth | 6371.0084 | 10.0000 | 240.0000 |
| Mars | 3389.50 | 5.3202 | 127.6847 |
| Mercury | 2439.4 | 3.8289 | 91.8938 |

The scene uses 26.5458683 reference kilometres per Blender unit. Earth=10 is
the normalized comparison, not a different scale for each object. Uniform
scaling replaces the prior nonuniform stretches. Geometry density and packed
texture assets are unchanged: a larger radius does not add mesh complexity.

## Distance and Apparent Size

For a spherical radius R at camera-to-center distance d:

```text
angular diameter = 2 * asin(R / d)
d = R / sin(angular diameter / 2)
```

| Fictional world | Target opening angle | Opening distance | Distance / Earth radius |
| --- | ---: | ---: | ---: |
| Large orange, Mars-size | 8 degrees | 1830.4345 units | 7.6268 |
| Small red, Mercury-size | 3.5 degrees | 3009.1109 units | 12.5380 |

These are deliberately compressed **cinematic distances**, not actual solar
system orbital separations. True orbital distances would make both worlds
tiny in this wide shot. Camera-relative sightlines `(0.48,0.16,-1)` and
`(-0.50,0.20,-1)` keep both complete silhouettes within the frame. The red
world is smaller and farther away. Distance is calculated from frame 1's
camera, not from an arbitrary current animation frame.

## Earth Perspective and Lighting

- Earth radius doubles from 120 to 240, with center `(0,-242.4,-40)`.
  Its near horizon remains low in the frame, with less visible curvature.
- At frame 301 the camera is approximately 257.9 reference kilometres above
  the surface, calculated as `(distance to center - radius) * km per unit`.
  This is a low-orbit artistic view, not a physically simulated Earth orbit.
- The atmospheric shell and hidden hemisphere emitter scale with Earth.
  Exponential atmosphere altitude/density parameters adjust with this scale.
- Each planet retains its isolated reflected-light rig: left-side key for the
  large orange world, right-side key for the small red one. Area sizes scale
  linearly and light powers quadratically to preserve incident intensity.
- Planet surface emission stays zero. Horizon lighting targets atmosphere
  only; it does not wash out Earth's dark face or light Phengos directly.
- Star geometry and the smooth sky move behind the distant worlds, with
  camera clipping adjusted accordingly. No new wallpaper or solar texture.
- The existing eased camera/circle rise is retained, with shared travel
  extended from 350 to 1850 units so the farther worlds leave the frame.
  This is not a frame-rate or motion-playback acceptance result.

## Files and Scope

- Blender: `E:/LifeOS-Art/phengos/phengos-intro-v9-shared-scale.blend`
- Authoring: `scripts/blender/refine_phengos_scale.py`
- Preview: `scripts/blender/preview_phengos_scale.py`
- Scene: `Phengos_Scale_Study_v9`, cloned without changing v8/v7/user sources.
- This is a still-image scale/framing study. Full movie export, browser handoff,
  responsive film cropping, sound and navigation remain separate work.
