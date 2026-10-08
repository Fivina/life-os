# Spatial Redesign Milestones

## Current Authorized Milestone

The user has frozen V37 art and authorized the continuous Layer 0 -> Layer 1 ->
Layer 2 journey before final material polishing. There is no Layer 3. Latest
implemented state and verification: `SPATIAL_JOURNEY_CHECKPOINT.md`.
`/space` is a protected, lazy-loaded foundation; the previous hub remains available.
The V34 handoff below is preserved historical evidence, not current acceptance.

## Goal And Boundaries

First priority: `docs/SPATIAL_ART_DIRECTION_PLAN.md` splits cinematic artwork into
six concrete chunks and visual gates. Navigation/motion and production integration
are later goals, not prerequisites for judging the artwork.

Create a cinematic, functional Life OS spatial experience inspired by the supplied
references, not a screenshot used as a replacement for interactive 3D. Preserve
canonical routes, authentication and backend behavior. Red is an attention fallback;
matching accents and modest object redesign are permitted by the latest direction.
Blender authors assets; the existing Three.js/R3F stack renders the application.
Figma can capture composition and interface decisions when its connection works;
it is not a prerequisite for continuing the artwork.

Each checkpoint records verified results and unfinished work. A successful render
alone is not evidence of browser fidelity or 60 FPS. Do not start speculative card
mechanics, unrelated backend work, or another frontend framework migration.

## 1. Art Direction And Composition - In Progress

- Compare the complete frame with the reference, including focal hierarchy and
  negative space, rather than judging each planet independently.
- Refine Self Core, Calendar/Chrono Ring, Learning/Neural Bloom, Home/Supply Core,
  Fitness/Orbit Barbell, and Life/Core Earth as distinct recognizable objects.
- Use shared directional lighting, selective atmospheric edges, restrained bloom,
  foreground parallax and a faint distant backdrop.
- Save editable Blender sources and rendered comparisons. Keep native domain
  colors; attention is visually distinct from decoration and hover.
- Gate: inspect the complete composition at reference-like framing and explicitly
  record remaining fidelity differences. Artwork remains editable.

## 2. Browser-Ready Asset Pipeline - Export Verified, Fidelity Pending

- Bake supported material channels; procedural Blender shaders do not magically
  export to glTF. Keep original procedural sources intact.
- Export stable named roots, geometry, UVs, textures and framing references.
- Bound texture sizes and mesh complexity, consolidate unnecessary draw calls,
  and record the package footprint.
- Gate: inspect the GLB's structure and load it in the browser without missing
  materials, malformed surfaces, or unwanted duplicate assets.

## 3. Isolated Browser Scene - Artwork Integrated, Browser Gate Pending

- First ship a development-only preview, leaving the existing hub intact.
- Render actual interactive objects full-bleed; add crisp projected labels,
  icon controls, loading/error states and keyboard/touch access.
- Inspect desktop and mobile screenshots and canvas pixels. Compare browser
  lighting/materials with the authored frame and fix observed differences.
- Gate: all main objects visible/reachable, no incoherent overlap, assets loaded,
  and no new runtime errors. Save evidence and the runnable preview URL.

## 4. Navigation And Motion - Planned

- Use URL-backed core/system/domain depth and stable camera destinations.
- Start with Self Core and the Settings gravity well beneath it. Reveal the system
  through a continuous bounded camera journey; zoom into the selected planet.
- Use gentle acceleration/arrival, slow orbiting, hover/focus stabilization, and
  brief warp effects. Keep labels sharp and reduced-motion views usable.
- Gate: forward/back transitions and keyboard/touch actions work; no lost focus,
  runaway loops, abrupt scene replacement, or control lock after cancellation.
- Subdomain moons may reference existing sections; do not invent functional cards
  or data. Final card mechanics require the user's separate specification.

## 5. Performance And Resilience - Planned

- Measure frame timing, slow-frame distribution, draw calls and triangles in the
  actual browser. Do not equate a static screenshot with performance evidence.
- Tune pixel ratio, geometry, texture sizes and postprocessing against the 60 FPS
  target. Document hardware/browser constraints and lower-quality fallbacks.
- Check resizing, reduced motion, renderer failure and resource cleanup.
- Gate: report measured results and unresolved limits explicitly, not a universal
  60 FPS promise. Scene remains navigable on lower-capability devices.

## 6. Main Hub Integration - Planned

- Integrate the visually verified scene through existing app boundaries.
- Preserve canonical routes, current-plan attention and all non-visual behavior.
- Run focused navigation/accessibility tests, frontend typecheck and a production
  build at the integration milestone. Do not repeatedly rerun unrelated backend
  suites for art-only edits.
- Gate: existing navigation passes; the production asset bundle is valid; old hub
  code is retired only after replacement behavior is verified.

## Current Handoff (2026-10-01)

- Current authored source: `E:\LifeOS-Art\system\system-art-v2.blend`.
- Frozen current source: `E:\LifeOS-Art\system\system-art-v34.blend`.
- Current full-frame render: `E:\LifeOS-Art\system\v34\system.png`.
- Portrait/untextured evidence: `E:\LifeOS-Art\system\v34\portrait.png` and
  `E:\LifeOS-Art\system\v34\system-untextured.png`. Actual 400px/300px small
  renders and changed Home/Fitness closeups inspected. Other closeups remain V33.
- Earlier V1 sources and renders remain preserved, not replaced.
- Repeatable art scripts and setup: `scripts/blender`, `docs/BLENDER_WORKFLOW.md`.
- Proposed motion timing: `docs/SPATIAL_MOTION_STORYBOARD.md`.
- Scaffold/export and independent reviewers completed and closed. Reviews live
  in `docs/SPATIAL_VISUAL_REVIEW.md`, `docs/SPATIAL_VISUAL_REVIEW_V8.md`,
  `docs/SPATIAL_VISUAL_REVIEW_V14.md`, `docs/SPATIAL_VISUAL_REVIEW_V17.md` and
  `docs/SPATIAL_VISUAL_REVIEW_V22.md` and `docs/SPATIAL_VISUAL_REVIEW_V25.md`.
  V29 landscape and V30 portrait depth placement are independently accepted as
  progress; V29 portrait was rejected and not published. Complete Depth 1 remains
  NOT MET. V33-probe source volume/continuous fading are accepted as appearances;
  V34 warmer finishes and finer belt continuity are also accepted as improvements,
  not the whole-frame gate. Broad highlights and bead-like belt rhythm remain open.
- Latest scope clarification: finish the whole Depth 1 solar-system view like the
  reference, including scenery/depth, before domain zoom/moons/cards.
  Motion/navigation implementation is deferred until the visual gate passes.
- Static scaffold files: `SystemArtPreviewPage.tsx`, `system-art-preview.css`,
  `systemArtMotion.ts`, `systemArtMotion.test.ts` in `apps/web/src/features/hub`.
- Latest V34 build passed, including project TypeScript, with the existing large-
  chunk warning. V33's nine source-power tests passed previously and were not rerun.
  V30's 35 layer/framing/material
  tests and V28's 13 optics tests were not repeated for the unchanged contracts.
  Actual source assertions/render/export and compileall passed. No backend/full-suite
  rerun; temporary/cache stays on E:.
- Development-only route: `http://127.0.0.1:5173/_dev/system-art?depth=system`.
- GLB and generated distant environment are in `apps/web/public/art/system`.
  Current versioned V34 export: 281,614 triangles, 39 asset draw calls, 29 embedded
  images, 23.52 MiB. Estimated RGBA8 with mipmaps: 160 MiB, not measured GPU total.
  Procedural PBR maps baked at 1024px; portable source maps capped at
  2048px while editable originals remain intact. Transmission/IOR/alpha validated.
  These are asset counts, not measured runtime totals or performance claims.
- Preview preserves Scenery in the system view, uses authored camera and AgX,
  restores explicit atmosphere rim extras, and has unframed 44px-hit labels.
  Portrait staging uses exported per-root poses/scales, including a separate
  foreground transform; V30 independently places three tagged scenery layers and
  restores them without accumulated scale. Optical halo/field bounds do not displace
  labels or shrink framing. Middle-distance lighting still needs improvement.
- V22 uses directional Learning limb extras and validated physical glass channels,
  inward Calendar ticks with satin mineral response, authored portrait source-power
  compensation, and linear-RGB preview light colors. Intensity parity remains
  approximate and requires real browser evidence. Backend/production hub untouched.
- V28 preserves those earlier body/portrait gains, moves the existing key forward
  without raising its power and stages 18 near/58 receding rocks plus 90 dust flecks
  in real perspective depth. Scenery exports as three batches, not per-rock draws.
  Core's extended curves become asymmetric tapered fragments instead of long
  projected orbital contours. No professional complete-frame approval yet.
- DepthOfField uses the existing dependency and bounded version-1 camera metadata,
  focused on Core, with lower portrait bokeh. Distant bitmap remains outside optics.
  Blender aperture and runtime bokeh are approximate separate controls; no parity claim.
- V28 export validated but the first live-file replacement failed with WinError 5.
  Successful versioned retry preserved the old V23 asset without weakening ACLs or
  interrupting the server. Preview now selects `life-os-system-v34.glb`; public/dist
  hashes match after the successful build. Older assets are retained, not selected.
- V29/V30 retain three child layers through export consolidation: four batches for
  19 near meshes, 58 belt rocks, 90 dust flecks and 8 tracks. Exact boolean metadata,
  Y-up portrait poses and frozen-source hash were checked in the actual final GLB.
  Added material costs one draw and 16 MiB estimated decoded maps versus V28;
  source and asset hashes/results are in `SPATIAL_ART_CHECKPOINT.md`.
- V33 keeps that staging, replaces detached fragments with 16 continuous tapered
  outer strands, disables shadowing by the visual source proxy and raises existing
  Core power to 6,250 W (other lights/exposure unchanged). Versioned scale 2.5 is
  preserved in GLB and used by the preview; legacy/malformed metadata retains power.
  Curves add 3,864 triangles versus V30, no extra draw/maps. Reviewer accepts the
  lighting/fading probe appearance, not complete art or actual browser evidence.
- Current untextured control no longer hides geometry merely because label bounds
  exclude it; actual field remains, while clouds/scattering/bloom/optics are removed.
- V34 retains that rig and framing, warms Home's materials, restrains Fitness/near
  basalt and adds 168 shared-material small belt chips. Four batches remain, including
  226 receding rocks/chips. No extra draws/images, 3,360 additional triangles versus
  V33. Source assertions, exact exported layer poses and source hashes passed.
  Seven saved-source renders were inspected; no unchanged contract tests repeated.
  Export took 556.08 seconds; larger bake-object count is a cost, not an optimization.
- A separate unsaved less-blue Core probe is preserved under `v35-light-probe`.
  Primary sees warmer Home/less uniformly cyan debris, but this is not live lighting.
  Next: validate a source-color contract if adopted, and redistribute existing debris
  into an irregular band with dark gaps rather than continuing to add dots.
- Gravity concept is saved at `E:\LifeOS-Art\gravity-well-study` and primary-inspected,
  with a dark interior/continuous rim/dense flow. It is not integrated or runtime-
  validated; current priority remains Depth 1 rather than another isolated object pass.
- Browser attachment timed out, then was explicitly blocked by browser tool
  security policy. No workaround attempted. Browser screenshots, canvas pixels,
  runtime shader compilation, mobile fidelity and loading/failure QA remain
  UNVERIFIED. A valid GLB and passing TypeScript do not prove those gates.
- Close-ups are produced with `scripts/blender/render_art_view.py`, without
  saving over the authored source. Review actual output, not execution intent.
- Demand-render snapshots are not evidence of animated 60 FPS.
- No production hub replacement or browser fidelity/performance claim yet.
- Detailed gate audit and next actions: `docs/SPATIAL_ART_CHECKPOINT.md`.
  V7-V34 improvements were inspected by primary; reviewers accept selected depth/light
  corrections, not finished artwork or the unavailable browser screenshots.
