# Phengos: Persistent Redesign Roadmap

Agreed with the user on 2026-10-01. This file is durable project context, not a claim
of assistant memory outside this repository. Read it before continuing the redesign.

## Direction

Life OS exists to help the user's life. Functionality takes priority over rendering
a hyper-realistic solar system. Phengos is the curious, expressive luminous circle
that becomes the interface, remains recognizable, and accompanies real work.

Current visual reference: the six files in `New Design/Design`. The older sheets in
`New Design` are historical context. They are a visual catalog, not permission
to implement every pictured domain or invent data, scores, payment flows, or voice.
Existing backend/domain services remain canonical. Existing routes, credentials,
agent settings, conversations, review flows and domain controls must be preserved.
Use `PHENGOS_FEATURE_INVENTORY.md` as the preservation checklist.

## Four Milestones and Call Names

| Order | User call name | Scope | Feedback gate |
| --- | --- | --- | --- |
| 1 | Visual foundation | Layered high-quality artwork; Phengos; film-opening choreography; upward camera-follow illusion; idle descent; responsive/reduced-motion foundation | Show the actual locally running opening and motion. User reviews atmosphere before expansion. |
| 2 | Usable navigation | Persistent Phengos across domains/subcomponents; stable sidebar/mobile navigation; Back/breadcrumbs/history; keyboard access; same visual language | User navigates all existing features and gives feedback. |
| 3 | Real functionality | Real-data cards and contextual actions connected to existing services; validate shopping, training, calendar and conversation journeys; loading/empty/error states | User tests everyday workflows, not fictional showcase data. |
| 4 | Product polish | Consistency, responsiveness, accessibility, failure recovery, measured performance and refinements from daily use | Final product review; no automatic scope expansion. |

Within each milestone, implement/test/iterate independently. Pause for user feedback
at its boundary, or for a material ambiguity/blocker. Do not require a new prompt for
each small correction. "Usable navigation" later explicitly refers to milestone 2.
Do not start the next milestone merely because a previous one has been implemented.

## Corrected Motion Contract

- Opening: the Life OS wordmark appears over a starfield, Earth horizon and planets.
- Revision after visual feedback: author the introduction in Blender, not by layering
  a busy space wallpaper. Five seconds for approach/title separation, then 3.5 seconds
  for the camera-follow rise. Smooth blue-black negative space; blue-white circle.
- Its luminous O is Phengos. During camera retreat the near-horizon wordmark grows
  and rises toward center. Letters are visible from frame one; Phengos wipes S,
  then LIFE, then returns to center. No appearance or disappearance alpha fades.
- Phengos visibly climbs first, then the viewpoint follows and settles it near
  center. Earth/planets leave through camera framing, not a large vertical camera
  slide mistaken for flight. They do NOT fade away or get deleted.
- The workspace is revealed above the planetary scene, against more starfield.
- The end of the opening shows ONLY the circle, not a greeting, dashboard, shortcuts,
  header or footer. Clicking Phengos opens the feature menu; during intro it skips.
- After 10-15 MINUTES of genuine inactivity, Phengos and the viewpoint gently descend
  toward the original horizon. NOT eight seconds. Default: 12 minutes.
- Do not auto-collapse a focused form, open dialog, or active work. Idle return on
  the home surface must preserve drafts, scroll state and route identity.
- The circle feels soft/elastic through anticipation, squash/stretch, subtle recoil,
  breathing and settling. It is NOT a pointer-following toy or mandatory mouse drag.
- Expressive during transitions, calm during work; no endlessly hyperactive screen.
- Skip/replay/manual horizon return must be available for testing and repeat use.
- Respect reduced motion, keyboard navigation, background tabs and narrow screens.
- No fake "thinking": operational states must reflect real agent/request events.

## Implementation Constraints

Use React and Motion for React, an established MIT-licensed animation library.
The normal home must not require WebGL/GLB downloads. The opening is a pre-rendered
Blender film; matching Blender plates and transform-based parallax handle the live
home/idle fallback. Preserve existing 3D artwork as DEV/archive work, not as a
dependency for reaching functionality. Do not destructively delete the old feature
pages: migrate intentionally after replacement behavior is verified.

Milestone 1 may include a small functional feature launcher and assistant entry to
keep routes accessible. These are not the completed milestone-2 navigation or the
milestone-3 dashboard. No invented statistics or model/provider success claims.

Cost policy: primary session owns integration; delegate only independent bounded
work (max two). Use focused tests; broader checks at milestone boundaries. Freeze
approved visuals instead of repeatedly re-auditing or rebuilding the whole app.

## Current Status

Milestone 1: implemented locally; awaiting user visual feedback, not yet visually accepted.
Milestone 2: routed navigation is implemented and has focused tests; user visual
acceptance remains open. See `PHENGOS_NAVIGATION_BRIEF.md`. Milestone 3 has an
in-progress desktop card and domain workspace iteration; milestone 4 is not started.
Live browser visual inspection was completed for this iteration on 2026-10-03;
the prior browser-tool limitation no longer applies. Never claim 60 FPS without
actual frame measurements.

### 2026-10-03 continuation

The user directed work toward the PC workspace and its card/action flow while the
visual design is still under review. The v17 smooth-sky Blender film is locally
served. The desktop menu now projects canonical plan, commitments, Fitness,
shopping, meals, fixtures and saved assistant proposals into asymmetric cards.
Proposal cards show arguments and link to their exact saved conversation;
confirmation/cancellation uses the existing guarded service. This is a working
iteration for feedback, not visual acceptance or a claim that voice is implemented.
See `PHENGOS_DESKTOP_FLOW_RESEARCH.md` for the focused upstream comparison.

### 2026-10-03 universal language and domain workspace iteration

The user supplied `New Design/Design/{1,2,3,4,5,download}.png` and the pasted
PHÉNGOS v0.1 language. `PHENGOS_UNIVERSAL_DESIGN_CONTRACT.md` preserves it with
dated amendments. The 2026-10-03 desktop shell used a dark full-height rail with
a subdued blue frame, current-domain contours, a direct Kitchen entry, and
Search/Settings utilities. The Home launcher uses the same rail language. All
21 canonical destinations remain reachable through domain panels and Search.
A Home overview link returns directly to the open dashboard. Calendar and Kitchen
have full-viewport, data-grounded workspaces above their preserved controls, with
the v17 intro environment visible around dark cards and lit, source-colored edges.
Calendar's input aligns with its main column; Kitchen's cards clear it at wide and
laptop desktop sizes. No circle visual redesign, food image generation, voice
state, or new card backend was part of this iteration. Focused tests, typecheck,
build, and live desktop browser review passed. Visual acceptance and measured
frame cadence remain open.

### 2026-10-04 sidebar and glass correction

User review rejected the full-height rail. Current desktop Home and routed shells use a narrower floating navigation capsule, with the LIFE OS identifier and orb above it and open sky at the left and bottom. Continuous top and bottom chrome bars have been removed; required controls remain as individual controls or the floating assistant dock. Home, Calendar, Kitchen, and preserved legacy content bands now use high-opacity dark glass with lit contours. This is a visual iteration pending user acceptance; no circle redesign, food imagery, voice work, or route removal was introduced.

## Original Milestone 1 Delivery Checkpoint (Superseded Intro)

- Normal authenticated home: `http://127.0.0.1:5173/`, now `PhengosHome`.
- Opening cues: wordmark -> center (0.9s) -> ascent (1.8s) -> workspace (4.2s).
  Artwork loading can defer the sequence; skip and the feature directory work immediately.
- Foreground Earth/planets move out of frame, never fade; starfield moves more slowly.
- 12-minute idle default; 10/12/15-minute setting persists locally. Focused editors,
  open dialogs and the open feature directory prevent automatic rest.
- Manual horizon return, enter, replay, reduced motion, hidden-tab breathing pause,
  image-failure fallback, assistant-draft handoff and 21 existing route/section links.
- All prior domain pages, backend APIs and provider/credential configuration preserved.
  Household anchor added to existing Life controls; no duplicate cleaning backend.
- Focused tests: 20 passed across Phengos logic, routing, login and workspace return;
  Life/section-focus regressions: 3 passed; real Motion DOM smoke test: 1 passed.
  These are separate runs (24 distinct passing tests across seven files), not a full suite.
- Final production build including TypeScript: PASS, 2267 modules, Vite 23.62s.
  Existing large-main-chunk warning remains for the product-polish milestone.
- Local root and live Phengos source returned HTTP 200; new foreground returned 200;
  backend health returned ok. Browser-panel open request was queued, not visually inspected.
- Built-in generated foreground saved in repo; sampled alpha proves the upper center
  is transparent. Actual output is 1672x941, not 4K. See `PHENGOS_ASSETS.md` for provenance.
- Still requires user's desktop/mobile appearance and motion feedback. No browser
  screenshot, smoothness, reference-fidelity or 60 FPS verification is claimed.

## Blender Intro Revision v1 (Superseded)

- Latest direction: smooth cinematic space, low texture, coherent camera/planet lighting.
- Editable scene: `E:/LifeOS-Art/phengos/phengos-intro-v1.blend`.
- Source authoring and render scripts: `scripts/blender/phengos_intro.py` and
  `scripts/blender/render_phengos_intro.py`. Blender 5.2.2 LTS, Eevee, AgX.
- Camera is animated in world space; Earth rotates; title dissolves; Phengos rises;
  final frame excludes Earth/moons. No planet-opacity animation.
- 255 rendered frames, 30 fps, 1920x1080, silent H.264 MP4. This is an initial motion
  draft for feedback, not a claim of final reference fidelity or measured 60 FPS.
- Home plays the film and uses its playback time for phases; click circle to skip.
  Film failures/timeouts fall back to live Phengos and the existing accessible menu.
- Idle view uses the matching Blender plate and live circle. The 10/12/15-minute
  return currently uses transform-based plates, not a separately rendered descent.
- Only the circle is visible at rest. Menu carries all 21 existing links, draft entry,
  replay, manual horizon return and idle setting. Escape/focus containment supported.
- Preview renders were inspected directly. Live browser visual inspection still blocked;
  responsive visual handoff and playback require user review.
- Verification for this revision: 20 focused tests across three files passed. Tests
  cover the cinematic playback clock (buffering does not advance phases), video-end
  handoff, fallback/skip, focus containment, all existing feature links and draft
  preservation. Local root/MP4/WebP endpoints returned HTTP 200.

## Continuous Opening v2 Checkpoint

- Current normal home: `http://127.0.0.1:5173/`. Menu -> Replay opening shows
  the new sequence even if this browser session has already seen an opening.
- Rendered from `E:/LifeOS-Art/phengos/phengos-intro-v2-user-framing.blend`,
  preserving the user's live Blender planet positions and dimensions. Original
  camera starting transform/lens verified unchanged; no user scene was cleared.
- Full-width Earth horizon, distinct cobalt/banded planets, quieter blue space,
  quintic camera motion. Camera and Phengos share their vertical track exactly;
  no relative bob. Planet placement was captured in the authoring source too.
- Environment-only film: 1920x1080, 511 frames, 60fps, 1,127,760 bytes. Matching
  WebP plates: 65,300 / 54,642 / 15,676 bytes. Original v1 remains preserved.
- One live circle and live letters throughout. Decoded-frame projection updates
  CSS, not React state every frame. End keeps the same video node/final frame and
  circle. Skip cancels playback; subsequent home visits bypass the intro.
- Protected drafts/dialogs, all 21 feature links, 10/12/15-minute idle return,
  manual return/replay, reduced motion and media-error/stall fallback preserved.
- Final focused verification: 22 tests passed across Home, real-Motion runtime,
  and projection files. The seven routing tests passed in the preceding combined
  run; unchanged thereafter. Two earlier projection failures were repaired and
  passed on rerun. Final production build including TypeScript passed (2268
  modules, Vite 24.94s); existing large-main-chunk warning remains.
- Local root, environment MP4 and idle WebP endpoints: HTTP 200. Opening/final
  rendered plates inspected directly; final frame contains no planets/lettering.
- Live browser screenshot/playback/FPS verification remains unverified after the
  earlier browser tool-policy block. 60fps is film output, not measured app FPS.
- Audio signature discussed, not implemented in this checkpoint: quiet rise hum,
  soft original arrival tone, optional sound and browser user-gesture restrictions.
- Stop here for feedback. Usable navigation remains the next separate milestone.

## User-Arranged Warm Scene Preview (2026-10-02)

- Latest scene: `E:/LifeOS-Art/phengos/phengos-intro-v4-user-warm.blend`, scene
  `Phengos_User_Warm_v4`. This is a still-preview checkpoint, NOT a shipped film.
- Untouched user setup saved separately as
  `E:/LifeOS-Art/phengos/phengos-user-setup-before-warm.blend`. Original scene,
  objects, camera data, material graphs and animation actions remain separate.
- User's opening camera/lens and apparent planet composition retained. Small
  world is moved 3x farther from opening camera and scaled 3x; large world is
  moved/scaled 6x. These are physical distance changes, not 2D resizing.
- Both worlds use original procedural matte geology, not Jupiter/Neptune maps:
  small dark red, large dark orange. No bright emissive planetary outline.
- Earth retains its night-side texture and orientation; warm city-light tint,
  whitish atmospheric horizon and distant sun. Pure-white Phengos is primary.
  "Like Los Angeles lighting" is treated as warm visual direction, not permission
  to claim the currently shown European night map is Los Angeles.
- Camera and circle rise together by 200 scene units to clear the distant worlds.
  Distant planets show slower parallax; the final environment still has no planets.
- Sky/star geometry moved behind the distant objects; no opacity-based exit.
- Four actual 1920x1080 stills inspected: `warm-v4-title.png`,
  `warm-v4-opening.png`, `warm-v4-horizon.png`, `warm-v4-idle.png` on E:.
- Fixed preview/export hazards: cloned scene explicitly retained on disk;
  render operation selects the exact scene; copied compositor Render Layers
  explicitly targets the new scene instead of the prior source revision.
- Full warm movie not rendered or installed in the app yet. Localhost continues
  to use v2. Its cover-crop issue on narrow browser panels still needs integration
  work; a Blender still is not evidence that browser playback is fixed.
- Navigation agent remains paused at the user's prior pause checkpoint; no tests
  or final navigation integration claimed. No card or backend changes in this pass.

## Finite-Sun Scattering Study v5 (2026-10-02)

- Editable file: `E:/LifeOS-Art/phengos/phengos-intro-v5-sunrise.blend`, retained
  scene `Phengos_Sunrise_v5`. Isolated copies of v4 objects, materials, world,
  compositor and animation actions; v4 remains unchanged and available.
- Source: `scripts/blender/refine_phengos_sunrise.py`; still verification:
  `scripts/blender/preview_phengos_sunrise.py`. Exact scene selection and copied
  Render Layers scene references retained. No scene is cleared or replaced.
- Removed the Earth surface's emissive Fresnel rim. Its emission is now city
  lights only; bounded altitude-dependent Rayleigh/aerosol volume supplies the
  horizon scattering. Clamp altitude before exponentiation to avoid overflow
  inside Earth. No luminous glass shell or full-scene fog.
- Finite-distance white point source/disc produces distinct crescent directions
  on the distant worlds. Legacy SUN disabled to avoid duplicate illumination.
  Sun is offset from Phengos; restrained aerosol scattering and emitter strength
  preserve the circle as primary. Artistic scale, not scientific astronomy.
- Fictional red/orange worlds moved another 2x farther from opening camera and
  scaled 1.6x, reducing angular size to 80% of v4. Photographed CC0 rock height
  and roughness packed into the file; no real planet photos on fictional worlds.
- Shared camera/circle rise is now 350 scene units. All 511 integer frames tested:
  maximum vertical-track difference = 0. Compositor target, packed rock maps and
  volume-only atmosphere connections asserted. Original v4 camera ends at 200.
- Earlier draft stills revealed weak atmospheric lighting, then excessive sun
  haze competing with Phengos. Both corrected before the final review renders.
- Final review rendering: title/ascent/idle at 960x540, 48 samples; horizon at
  1920x1080, 72 samples. All four final renders inspected. Final frame contains
  circle and quiet space only. Mid-rise retains the distant worlds as intended.
- Python compile check passed for the two final scripts; no backend/frontend
  suite run for this art-only change.
- Full v5 movie NOT exported/installed. Localhost still uses v2; responsive
  cover-crop and camera projection remain integration work, not fixed by this
  Blender study. Continuous motion/FPS not claimed from stills. Navigation remains
  paused; no card, backend, API key, or unrelated UI changes.

## Hidden Horizon Lighting Experiment v6 (2026-10-02)

- User-authorized experiment: invisible sources distributed behind the horizon,
  with angled side/back lighting to reveal the distant planets. No visible sun.
- Saved `E:/LifeOS-Art/phengos/phengos-intro-v6-hidden-horizon.blend`, scene
  `Phengos_Hidden_Horizon_v6`; isolated from v5, which remains intact.
- Five rectangular area lights illuminate the atmospheric volume only. Six
  additional area lights (three per planet, nominal camera-relative phase angles
  100/120/130 degrees) are linked only to their respective fictional world.
- Actual render comparison revealed surface washout and an outward-facing large
  planet crescent. Removed Earth from horizon receivers and turned the planet
  lights inward. Lights never directly illuminate Earth or Phengos.
- Controlled frame-301 comparisons: 1.0x restrained and 2.4x strong, same camera,
  geometry, material and exposure. Selected 1.6x as the working middle strength.
  Light base energies remain stored per object for reproducible comparisons.
- Sun disc hidden, previous point/SUN sources disabled, not deleted. Earth still
  has warm city emission; thin atmospheric scattering supplies the horizon glow.
  This is an intentionally staged cinematic rig, not multiple astronomical suns.
- Eleven receiver assignments, correct compositor target, preserved 16-object
  v5 source and hidden sun assertions passed. Final scripts compile passed.
- Final selected frame, title, ascent and idle rendered. Selected and idle
  images inspected; v6 then superseded for the user's curved-source experiment.
  Preview uses the installed renderer's `--cycles-device CUDA` command-line
  override; no Blender preference or security-setting change.
- Movie/browser not replaced. This lighting-only study does not claim animation
  playback, 60 FPS, browser crop repair, navigation, or backend verification.

## Curved Hidden Source v7 (2026-10-02)

- User clarification: **curved source behind the horizon**, not a fan of rays.
- Saved `E:/LifeOS-Art/phengos/phengos-intro-v7-curved-source.blend`, retained
  scene `Phengos_Curved_Source_v7`. Source v6 remains unchanged at 1.6 strength.
- One continuous emissive upper hemisphere, radius 190, center `(0,-176,-390)`;
  its nearest extent is z=-200, behind Earth's far extent z=-160. This provides
  low-angle grazing illumination without putting a visible sun in the shot.
- Camera/glossy/transmission ray visibility disabled on emitter. It illuminates
  the atmospheric volume only. The previous horizon lamp row is disabled; the
  six planet-detail lights remain. No foreground emissive shell, glass fake-rim,
  full-scene fog or new visible celestial body is added.
- Explicitly remapped copied light-link receiver collections to v7 objects.
  Sharing v6 collections would incorrectly target the previous scene's planets.
  Correct receiver membership, disabled prior sources, camera-hidden emitter,
  compositor target and preserved v6 assertions passed.
- Initial strengths 8/20 were underexposed after Earth occlusion. Compared
  strengths 160/400 with the same geometry, camera and exposure; selected 400
  for the working preview. These are shader radiance settings, not lamp watts.
- Earlier v6 selected/title/ascent/idle images are on E:; no v6 film installed.
- v7 final review renders completed and inspected: 1920x1080/96 samples for
  selected horizon, 960x540/48 samples for title, rise and idle. No emitter/sun
  visible in any inspected frame; idle contains circle and quiet space only.
  Both final scripts compile passed. Six camera/circle track samples remain
  aligned, no motion edits here. Still-image checks are not a motion acceptance.
- No frontend/backend changes, full test suite, film export, browser handoff or
  FPS acceptance claim. Localhost remains v2 until separate movie integration.

## Independent Planet Lighting and Shared Scale v8/v9 (2026-10-02)

- v8 clones v7 into `Phengos_Planet_Depth_v8`, saved as
  `E:/LifeOS-Art/phengos/phengos-intro-v8-planet-depth.blend`. Four individually
  linked area lights replace the six active mirrored detail lights: broad left
  key for orange, narrower right key for red, very weak fills. Planet material
  emission is zero. Same-frame 1.0/1.7 lighting studies rendered; the 1.7 study
  inspected before the subsequent common-scale geometry pass.
- Latest user request supersedes the earlier Earth-sized large-world suggestion:
  use real Mars/Mercury/Earth size proportions on a common reduced scale.
- v9 clones v8 into `Phengos_Scale_Study_v9`, saved as
  `E:/LifeOS-Art/phengos/phengos-intro-v9-shared-scale.blend`.
  Earth=10, orange Mars-size=5.3202, red Mercury-size=3.8289 normalized radii.
  Existing mesh/texture assets retained, uneven object stretching corrected.
- Earth radius 240 gives a broader, flatter horizon and frame-301 camera altitude
  equivalent to approximately 258 km. Atmospheric density and the hidden curved
  emitter adjust with Earth scale. Planet lights follow resized/moved worlds,
  with size and power scaled to preserve irradiance; working strength 1.3.
- Opening planet angular diameters 8/3.5 degrees give camera distances of
  7.6268/12.5380 Earth radii. These are cinematic, NOT real orbital distances.
  Both worlds fit in frame; sparse stars and smooth sky now sit behind them.
- Shared camera/circle travel extended to 1850 without replacing authored easing;
  six alignment samples pass. Final frame clears both planets naturally.
- v9 draft plus title/ascent/idle rendered at 960x540/48 samples and selected
  horizon at 1920x1080/96 samples. All four final checkpoints visually inspected.
  Surface city-light detail remains soft at this closer view: no finished texture
  quality or cinematic motion claim based on stills.
- Persisted-file verification passed for size ratios, spherical dimensions,
  angular diameters, unchanged source Earth and mesh count, four receiver rigs,
  hidden atmosphere-only emitter, compositor target, six track samples, idle
  clearance and star depth. Python compile passed for the changed art scripts.
- Calculations recorded in `docs/PHENGOS_SCALE_STUDY.md`. No movie export,
  localhost replacement, sound, card/navigation work or backend/frontend tests
  in this art-only scope. Localhost still uses v2, not these Blender studies.

## Natural Horizon v10 (2026-10-02)

- Re-read catalog pages 1/2/3 under `New Design`; the relevant horizon uses fine
  warm settlement lights, dark terrain/cloud shapes and a narrow cool limb, not
  enlarged amber blobs or a uniformly thick fog stripe. Prior user constraints
  still override catalog timings/fades: 5-second intro, camera rise, no planet
  opacity disappearance. No new navigation implementation.
- Isolated scene `Phengos_Natural_Horizon_v10` saved to
  `E:/LifeOS-Art/phengos/phengos-intro-v10-natural-horizon.blend`.
  v9 and user source scenes remain intact. Earth radius 240 -> 480; both distant
  worlds, their distances, light sizes/powers and background depth scale together.
  Real relative radii and opening angular sizes are retained.
- Camera-to-Earth center is calculated from a 450 km equivalent altitude at
  frame 301 and a horizon 5 degrees below the optical axis. Center is approximately
  `(0,-494.1724,-121.0338)`. The opening viewpoint is approximately 469 km;
  the ascent subsequently leaves this altitude, as intended.
- Earth replaced with a 512-segment/256-ring UV sphere (130562 vertices);
  atmosphere with 256 segments/256 rings (65282 vertices). Fine spherical
  boundaries reduce geometric faceting. Existing animation orientation/UV
  convention/material ownership retained. Cloud bump disconnected from Earth
  normals to avoid exaggerated relief on the limb.
- NASA's 500 m VIIRS C1 grayscale tile supplies city radiance through a bounded
  geographic crop, 8192x5821, with cubic sampling and global fallback outside it.
  Preparation, geographic bounds, credits and SHA256 hashes are recorded in
  `SPATIAL_ASSET_SOURCES.md`. No made-up settlement texture or NASA wallpaper.
- Exponential atmospheric scale height 8 km, bounded outer shell 80 km,
  Rayleigh density 0.006, hidden curved-source radiance 500. Unbiased volume
  rendering retained; glare reduced 0.35 -> 0.18, threshold 0.8 -> 1.0.
  Very dim Earth-only cool fill reveals land/cloud albedo, not daylight.
- Curved-source and directional-SUN trial images compared at fixed framing.
  Directional trial was underexposed; not selected or saved as the working rig.
  The catalog's concentrated central sunrise glint is still not matched.
- Final selected horizon rendered at 1920x1080/256 samples, title/ascent/idle
  at 960x540/96 samples, all inspected. City detail and atmospheric edge improved,
  but this remains a composition review, not finished cinematic lighting.
- Persisted-file verification passed (`verify_phengos_scale.py --natural`):
  source preservation, shared radius ratios/angular sizes, receiver isolation,
  camera altitude, packed regional tile, cloud-fill ownership, unbiased volume,
  six track samples, background depth and final planet clearance. Dense UV
  primitive radius assertion uses 20 ppm relative tolerance for float accumulation.
- Python compile passed for authoring, asset preparation, preview and verification
  scripts. No unrelated backend/frontend tests. No movie/browser replacement,
  sound or measured motion/FPS claim; localhost still uses v2.

## Silver Horizon v11 (2026-10-02)

- Requested 600 km equivalent viewpoint at frame 301; measured 600.00014 km.
  Earth radius remains 480, center `(0,-496.751,-150.516)` approximately.
  Real relative planet radii and authored cinematic opening distances are retained.
- Saved isolated `Phengos_Silver_Horizon_v11` to
  `E:/LifeOS-Art/phengos/phengos-intro-v11-silver-horizon.blend`.
  v10 geometry, lights, materials and animation remain unchanged.
- Compared volume and analytical optical limb at identical 600 km framing.
  Initial optical test spread too much blue over Earth; narrowed to a silver
  grazing-angle shell (power 80, base radiance 6) with restrained blue falloff
  (power 70, radiance 0.7). No textured rim or stochastic volume in selected mode.
  This is an explicit camera-only artistic layer, not a physical scattering claim.
  Previous atmosphere/emitter are retained but volume is hidden in silver mode.
- Large orange world's key is upper-left at 124 degrees; small red world's key
  is lower-right at 132 degrees. Nominal illuminated fractions 22.0% and 16.5%.
  Receiver-isolated keys/fills cannot brighten Earth or each other. Most of each
  planet remains dark; reduced coat/specular and key strength retain colored terrain.
  Separate sunlit-side optical shells avoid full glowing rings or surface emission.
- Fictional surfaces now use NASA SVS LROC color/LOLA elevation on original
  256-segment/128-ring spheres, with different UV offsets and original orange/red
  tints. Shader bump is bounded; silhouettes are not displaced. Sources, dimensions,
  hashes and attribution are in `SPATIAL_ASSET_SOURCES.md`.
- Persisted-file verification passed (`verify_phengos_scale.py --silver`):
  600 km altitude, archived 450 km source preservation, radius ratios/angular
  framing, packed maps, no planet emission, four isolated lights, camera-only
  optical gates, dawn fractions, six camera/circle samples and final planet clearance.
  Archived-scene animation validation explicitly activates its dependency graph.
- Changed art scripts compile. Preview checkpoint renders use CUDA, selected
  frame at 1920x1080/256 samples and title/ascent/idle at 960x540/96 samples.
  No backend/frontend work, new plugin, sound, navigation or movie export.
  Localhost still uses v2; these previews do not validate full-motion flicker/FPS.

## Luminous Horizon v12 (2026-10-02)

- User correction: opening camera moves BACKWARDS. Requested visual gear ratio
  is camera 5 : Earth 5 : letters 1, with synchronized light changes. Original
  five-second opening and subsequent 3.5-second upward camera-follow remain.
- Isolated scene `Phengos_Luminous_Horizon_v12`, saved to
  `E:/LifeOS-Art/phengos/phengos-intro-v12-luminous-horizon.blend`.
  v11 objects/materials/animation remain intact; animated material node trees
  have separate copied actions so source title fades cannot be overwritten.
- Shared quintic timing drives 40 units of camera retreat (Z 20 -> 60),
  0.75 degrees of Earth rotation and 8 units of wordmark depth relative to camera.
  Letters follow 32 of the 40 camera units. The 5:5:1 relationship is a visual
  normalized motion ratio, not an equality between kilometers/sec and degrees/sec.
  During rise, Earth rotates another 0.525 degrees with the same rise timing.
- Earth altitude is 900.00015 km equivalent at frame 301 after the retreat,
  not constant throughout the shot. Earth stays radius 480; planet positions and
  real relative radii are unchanged. Opening angular metadata is recalculated
  against the corrected camera origin. No false real orbital-distance claim.
- Silver limb is near-white with soft neutral falloff, not a saturated blue stripe.
  Horizon radiance declines to 45% during retreat; letters decline from 2 to 1.2
  while their existing fade ends; planet light factor declines 1.15 -> 0.75.
  Phengos emission grows 2 -> 8 only as the letters dissolve. This is optical
  art direction, not physically changing stars or surface light sources.
- Planet keys have zero elevation in the opening view basis: large world's left
  side and small world's right side, phases retained at 124/132 degrees.
  Small-world shadow fill increased 0.015 -> 0.055 flux; large world uses dark
  brown crater plains and muted orange highlands from its existing NASA terrain.
  No new external models or texture downloads. Receiver isolation remains.
- Wordmark O measured from the actual font: height 0.4699798 units, title-stage
  Phengos scale 0.5464864 versus previous unit scale. Baseline/cap-center aligned;
  circle grows to its existing full size only during letter separation.
  Pale-blue title colors coordinate with the blue starfield; circle stays white.
- Stable UV noise varies dark-orange/warm-ivory colors inside the existing city
  radiance mask only. No invented settlements, grain, temporal flicker or gameplay data.
- Persisted-file verification passes (`verify_phengos_scale.py --luminous`):
  source preservation, 900 km, planet ratios/depth, receiver ownership, neutral
  limb color, O height/baseline, lateral keys, six retreat/rotation/wordmark samples,
  camera/circle rise alignment, final planet clearance and packed assets.
- Only Blender art scripts and this continuity document changed. Localhost movie,
  app navigation, sound and backend behavior are not replaced in this preview pass.
  Full delivery-quality 60fps rendering and browser handoff remain unverified.
- Final title/horizon frames rendered at 1920x1080/256 samples, rise/idle at
  960x540/96 samples; all four visually inspected. Art scripts compile.
- Timing draft exported at 480x270/16 samples/12fps: 103 frames, 8.5833 seconds
  including the last frame's hold. This is not delivery-quality smoothness.
  `inspect_phengos_motion.py` decodes the actual MP4 through Blender's sequencer:
  FPS/duration/dimensions/nonblank checks passed, frames 1/19/37/61/73/103 visually
  inspected for wordmark sizing, light handoff, retreat, rise and empty-space ending.
  No new media plugin or runtime dependency. Blender 5.2 sequencer-duration APIs
  emit a future Blender-6 deprecation warning; verification still passes.

## Character-Led Flight v13 (2026-10-02)

- Latest user correction supersedes v12's shrinking title and 3700-unit camera
  slide. Explicit clarification: visible climb, then camera follows and centers.
- Isolated scene `Phengos_Character_Flight_v13`, saved as
  `E:/LifeOS-Art/phengos/phengos-intro-v13-character-flight.blend`.
  Source v12 retains its 37 objects, camera track and separate animation actions;
  v13 has 41 objects. No live user Blender arrangement is overwritten.
- Five-second camera retreat Z20 -> 60 remains. Wordmark relative depth closes
  30 -> 18 and scale grows 0.9 -> 1.4 while rising from the horizon. The measured
  font-O sizing is preserved before the final-second handoff; letters then fade.
- Phengos actually travels Y0 -> 55, Z42 -> 6 over the subsequent 3.5 seconds.
  Camera translates only Y0 -> 12 and pans upward; character leads by up to
  13 degrees before settling at the screen center. Earth and planets never move
  downward or fade to fake departure. Earth rotation retains synchronized easing.
- Fixed finite sunrise is geometrically hidden by Earth during retreat (center
  becomes occluded at 1.7333s). Silver horizon radiance declines to 35%. New
  surrounding sky/star shells at radii 11000/10000 keep the upward view continuous;
  previous flat background is hidden only in the isolated v13 scene.
- A real point light parents to Phengos and illuminates only a restrained reflective
  optical layer over Earth. The localized linear rim sparkle is an explicitly
  art-directed shader glint, not a claim of physical atmospheric light simulation.
- Persisted-file verification covers all 511 frames: growing title projection,
  measured O sizing, source preservation, fixed body positions, character/camera
  separation, framing, finite sunrise occlusion, isolated moving light and centered
  ending. Handoff altitude remains approximately 900 km equivalent.
- Five 960x540/48-sample draft stills rendered and inspected: early, growing,
  handoff, flight and idle. These validate composition checkpoints, not final
  motion smoothness. Changed art scripts compile successfully.
- Timing draft exported at 480x270/16 samples/12fps: 103 frames, 8.5833 seconds
  including the endpoint hold. Decoded actual-MP4 frames 1/13/37/61/73/91/103
  inspected; FPS, duration, dimensions and nonblank checks passed. Low-resolution
  compression suppresses faint stars; this is not delivery-quality film or 60fps
  smoothness evidence. Full-quality rendering remains a separate feedback gate.
- Strict sunrise visibility verification initially exposed an inherited
  viewport-hidden flag causing a stale test transform. Source enabled in v13's
  viewport; entire-source geometry occlusion and all-frame checks then passed.
- Frontend, localhost film, backend, sound and paused navigation work are unchanged.
  Browser still uses v2; this is a Blender preview feedback gate, not deployment.

## Blue Eraser and Cinematic Hierarchy v14/v15 (2026-10-02)

- v14 responds to corrected title staging: wordmark visible from frame one,
  centered above Earth rather than on its atmospheric edge. Initial projected
  width 41.91% -> 51.65% at 2.8 seconds. Title is placed deeper in world space
  while preserving these projected proportions; camera still retreats.
- `E:/LifeOS-Art/phengos/phengos-intro-v14-blue-eraser.blend`, isolated scene
  `Phengos_Blue_Eraser_v14`. All v13/source scenes remain intact.
- Spatial shader clipping follows Phengos, not a uniform text-opacity fade:
  S erased rightward at 2.8-3.35s, LIFE erased leftward at 3.35-4.65s, circle
  returns to center by 5s. Then visible climb and camera-follow continue to 8.5s.
  Erased glyphs cannot reappear when the circle returns or flies upward.
- Two actual parented blue point sources use existing reflective optics and
  planet receivers. Ascent changes planet-source directions by approximately
  5.24/9.61 degrees and reduces their gain. These use cinematic receiver gains,
  not a claim of astronomical luminosity. Background remains an enclosing sky.
- v14 persisted-file checks passed over all 511 frames: initial title visibility,
  projection, measured O diameter, erasure order, fixed bodies, parented lights,
  rising character, darker sky, final centering and natural planetary clearance.
- Latest user direction locks composition/geometry. v15 is ONLY lighting and
  compositing: `E:/LifeOS-Art/phengos/phengos-intro-v15-cinematic-hierarchy.blend`,
  isolated scene `Phengos_Cinematic_Hierarchy_v15`. No mesh, location, camera,
  character-motion, erasure-frontier, planet-size or star-distribution edits.
- Object-index 101 isolates Phengos bloom before adding its soft blue halo to
  the original crisp render. Typography/cities/stars do not enter the glow path.
  Circle emission is 1.7x hotter; letters slightly brighter with no general bloom.
- Planets are darkened with cooler, greatly reduced keys/fills and weak optical
  crescents, especially the large right world. Cities retain warm tint with
  emission 1.1 -> 0.82. Sky radiance reduced to 12% of v14; sparse star radiance
  1.5 -> 0.65 with exactly the same mesh/distribution.
- Earth uses a clean thin cool optical edge with narrower smooth falloff and
  stronger final-selected rim than the first v15 trial. It still dims during
  retreat. Hot circle-mesh illumination excludes night-side terrain to avoid a
  daylight wash; restrained real optical reflection and planet lighting remain.
- Desired hierarchy: black space < dark planets < warm cities < cool Earth rim
  < crisp typography < blue-white Phengos. This is art direction, not a claim
  that every individual city/star pixel has strictly ordered radiance.
- Final persisted-file check passed: 42 objects retained, mesh coordinate buffers
  exactly equal to v14, all 511 object/camera transform samples identical (maximum
  delta 0), copied source preserved, eraser masks retained and character-only
  bloom graph verified. All six changed/new art scripts compile successfully.
- Seven final checkpoint stills rendered and visually inspected. Opening further
  rendered at 1920x1080/128 samples; other checkpoints at 960x540/64 samples.
  Circle reflection is reduced/softened to avoid a vertical beam dominating Earth.
- Final timing export completed: `E:/LifeOS-Art/phengos/cinematic-v15-motion-draft.mp4`,
  480x270/24 samples/12fps, 103 frames, 8.5833 seconds including endpoint hold.
  Actual exported frames 1/25/35/39/41/49/57/61/73/91/103 decoded and inspected.
  FPS, duration, dimensions and nonblank checks passed. Initial visible lettering,
  S/LIFE spatial erasure, centered handoff, lead/follow flight and planet-free ending
  remain intact. This is not final 60fps smoothness or browser-integration evidence.
- No frontend/backend, sound, navigation or localhost film changes. This remains
  a Blender preview feedback gate; live app still uses v2.

## Reference-Match Research and Task Gate (2026-10-02)

- Latest user direction supersedes v14/v15 erasure: LIFE/S fade while the O grows
  and becomes the character. No letter-wiping sweep. Remove artificial Earth
  reflection; moving Phengos light may reveal restrained parts of the two planets.
- Preserve Earth/planet geometry and positions. Camera altitude around 1500 km is
  a framing experiment, not a locked value or a promise that altitude alone makes
  Earth appear bigger. Lens, aim, cropping and camera path must be judged together.
- Nine requested checks are retained: composition, lighting/materials, background/
  depth, compositing/grade, Earth, planets, Phengos, typography and global grade.
  The reference requires richer irregular blue star clouds, quieter city networks,
  dark planetary silhouettes, a stronger atmospheric sunrise and softer circle.
- Persistent working tasks/research/acceptance checks:
  `E:/LifeOS-Cache/phengos/reference-match-tasks.md`.
- Research/planning only in this step, as requested. No scene, renderer, app,
  soundtrack, navigation or deployed film changes. Full-resolution still review
  comes before another full film render; native preview quality and actual browser
  publication remain separate gates. Existing milestones/features are preserved.

## Reference-Match Implementation v16 (2026-10-02)

- User authorized implementation, then refined the sky direction: clean curved
  inner background, sparse irregular stars, subtle lighter blue cloud centers.
  Distant sky radiance stays independent of Phengos's planet illumination.
- Isolated scene `Phengos_Reference_v16` saved in
  `E:/LifeOS-Art/phengos/phengos-intro-v16-reference.blend`.
  Original v15/source scenes are retained. Earth and planet mesh coordinates,
  positions and scales are preserved; camera opening altitude is 1497.56 km
  equivalent with 31 mm lens and revised framing.
- LIFE/S now fade in opacity and radiance around the growing O. Removed spatial
  eraser choreography. Character climbs first; camera follows and ends centered.
- Earth uses quieter settlement radiance, a thin bounded scattering volume and
  directional backlight, plus controlled optical rim and separate sunrise glow.
  Artificial Earth reflection, glint and its Phengos receiver light are disabled.
- Circle has a softer luminous edge, isolated inner/outer blue glow, and a parented
  source linked only to the two planets. Fixed a blocking shell-shadow interaction
  so the source can reach those receivers; cinematic source gain is intentional.
- Built-in image generation produced a cleaner cloud plate with lighter azure
  centers. Star-free plate is at
  `New Design/phengos-cloud-only-environment-v16.png` (1774 x 887, actual output).
  Native irregular star geometry provides fine highlights separately. Inner dome
  UV coverage is checked throughout the camera flight. Sky is camera-only.
- Independent Astra visual review prioritized softer atmosphere/O edges and
  optical type balance; incorporated in the final proof-frame pass.
- Five 1920x1080/128-sample checkpoints rendered: opening, fading, climb, flight,
  idle. All-frame verification passed: 511 frames, fixed bodies, monotone fade,
  growing O, visible lead/follow, final centering, isolated light receivers,
  no Earth reflection, no dome edge entering the view.
- Controlled same-seed planet light on/off render passed: 3253 changed pixels,
  mean RGB increase 0.00013437 in the 216x216 planetary crop at frame 361.
  This verifies a subtle actual illumination effect, not just a linked-light flag.
- Review film completed: `E:/LifeOS-Art/phengos/reference-v16-motion.mp4`,
  1280x720, 30 fps, 256 frames, 8.5333 seconds, 1,582,269 bytes. Export used
  24 samples with OptiX GPU denoising; view-dependent overlays were excluded from
  direct-light sampling. Saved scene and full-HD proofs retain their own settings.
- Actual encoded frames 1/61/109/145/151/181/211/256 decoded and visually checked.
  Dimensions, frame count, duration and nonblank checks passed. Sampled fade,
  visible climb, planet clearance and centered idle match the authored staging.
  These checks are not an exhaustive temporal-flicker evaluation or final 60 fps
  delivery. Five changed authoring/render/verification scripts compile successfully.
- Independent Astra review found no still-frame delivery blocker. Remaining
  subjective polish: narrow silver rim and a more noticeable left cloud bank in
  idle. The latter matches the request for lighter cloud centers. No additional
  redesign was made after this feedback gate.
- Blender review milestone is complete. No production frontend film replacement:
  the live app remains on v2, and interactive handoff/idle return, final encoding
  and browser verification are a separate integration gate.
