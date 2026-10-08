# Spatial UI: Entry and Primary System

## Implemented Boundary

This milestone implements Depth 0 (Self Core and gravity well) and Depth 1
(the five primary domain objects). It is not the completed spatial redesign.
Planet-centered moon systems, the second warp, and the new card mechanic remain
for the next separately specified UI milestone. Planet selection currently opens
the existing functional domain page. Home opens Kitchen because there is no
separate canonical Home route in this repository.

## Structure

- `HubPage` coordinates URL-backed depth, accessible targets, reduced motion,
  transition input locking, and renderer-failure navigation.
- `SpatialHubScene` owns one Canvas, one camera, shared lighting, bloom, stars,
  orbit motion, and the existing authored objects. No duplicate model framework.
- DOM targets are projected from object coordinates each frame. Frame updates
  do not trigger React state updates; completion and interaction changes do.
- `spatialNavigation` contains domain identity, existing destinations, the
  bounded arrival curve, and slow orbital positions.
- Leaving a domain through the shell returns to `/?depth=system` rather than
  forcing the initial entry sequence again.

## Motion and Visual Policy

The 1.15-second transition uses quintic arrival easing, a bounded camera surge,
star streaks, and restrained blur. Hover/focus enlargement and halo brightness
are damped. Orbital motion decelerates during target interaction, then resumes.
Reduced motion disables decorative motion and uses on-demand rendering.

Self Core and gravity well retain their standalone hero defaults. The shared
scene uses smaller navigation geometry/particle budgets. Self Core's optional
outer orbit spread also moves its associated particles along the same curves.
The gravity well rotates its accretion flow/disk, not its black void.

Attention is red (`#ff4d57`). Selection and hover retain native object colors.
Only explicit canonical planner `overloaded` or `impossible_before_deadline`
currently activates Calendar's red segments/beacon and a textual indicator.
No overload is inferred for the other planets from task counts or unknown data.
Existing object attention contracts remain available for future authoritative
domain signals. No canonical state is written by this scene.

## Verification

- Full frontend milestone suite: 109 tests passed in 20 files.
- Following the final hover refinement: 20 focused tests passed in 3 files
  (hub navigation, navigation-object geometry/motion, shell transitions).
- Final TypeScript check passed.
- Production bundling passed; the existing large-main-chunk warning remains.
- Browser checks: entry, forward/reverse travel, mobile Fitness navigation,
  and return to the primary system. No runtime errors in the inspected QA tab.
- Desktop and mobile captures: 1280x720, 390x844, and 320x568.
- Screenshot canvas-region check: 42,099 bright desktop pixels and 22,465
  bright mobile pixels. Animated Self Core/gravity ROI: 3,665 changed pixels
  between two captures. These verify visible rendering/motion, not fidelity.
- Development frame samples on this desktop browser ranged approximately
  146-165 FPS. These are frame-cadence samples, not a benchmark or a promise
  of 60 FPS on real mobile hardware. The primary system measured approximately
  386 draw calls and 242k triangles including postprocessing; entry about
  147 calls and 47k triangles.

Captures are local, non-source output in `backend/var/spatial-ui-checks`.
Viewport overrides are temporary. Development servers remain running.
Backend/auth/provider-vault changes and backend test reruns were not needed.

## Remaining Work

1. Reference fidelity: finer neural-tree branching, more physical Fitness
   lighting/materials, and richer Self Core/gravity-flow detail. Current
   screenshots are a usable first integrated pass, not a pixel-identical match.
2. Depth 2: planet focus, second warp, moon identity/navigation, and cards after
   their interaction contract is supplied. Do not invent domain ownership.
3. Real-device performance profiling and further draw-call/asset-load reduction.
4. Domain-specific attention signals only when authoritative APIs supply them.
