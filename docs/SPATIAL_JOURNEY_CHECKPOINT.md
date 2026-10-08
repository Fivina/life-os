# Continuous Spatial Workspace - 2026-10-01

> Superseded normal-home direction: the user stopped the 3D expansion and approved
> the Phengos layered-artwork redesign. See `PHENGOS_ROADMAP.md`. The normal `/`
> route now uses Phengos without WebGL. This document records the preserved spatial
> artwork foundation, still available in the DEV preview, not the current home UI.

## User-Authorized Direction

The previous six-stage art goal was cancelled by the user, not completed. Freeze
V37 artwork; do not keep polishing materials at the expense of the application.
The new active goal is a continuous Layer 0 -> Layer 1 -> Layer 2 foundation.
There is no Layer 3. Card mechanics and new domain workflows follow separately.

| Layer | Scene | URL |
| --- | --- | --- |
| 0 | Self Core and Settings gravity well | `/` |
| 1 | Existing V37 solar-system artwork | `/?depth=system` |
| 2 | Selected planet and subcomponent moons; wider system retained | `/?depth=domain&domain=fitness` |

The user explicitly authorized replacing the old default hub on 2026-10-01.
The authenticated `/` route now mounts the spatial scene in both development and
production builds. `/space` redirects to `/`, preserving validated layer/domain
parameters. The DEV route `/_dev/system-art` remains for artwork diagnostics.
The old HubPage is no longer imported or mounted by the application router.

Every ready moon has both a real component link and a mesh click handler. Links
carry the originating planet so the workspace return action restores it. Only
the selected domain's moons can activate; departing systems remain visual only.
If rendering fails, the selected domain's moon links stay available. Layer 0 Back
is disabled (there is no old hub behind it); domain Back -> system -> Core works.
Existing component controls are unchanged. Their shell uses ordinary Lucide
navigation icons instead of the old decorative hub glyphs; no new menu redesign.

## Taxonomy

- Home: Cleaning, Kitchen, Shopping.
- Fitness: Nutrition, Training.
- Life: Finance, Goals, Social life, Film, Notebook.
- Calendar: Calendar, Daily list.
- Learning: existing Study Log, Study Candidates, Exams; not a newly approved redesign.

Cleaning is explicitly pending/non-actionable; no fake cleaning workflow exists.
Nutrition remains canonical in Kitchen and is linked by the Fitness moon to
`/kitchen#nutrition`. Shopping links to `/kitchen#shopping`. Training, Goals,
Learning sections and the Calendar plan/projection have real focusable anchors.
Daily list currently opens existing calendar plan execution, not a new task list.
No canonical ownership or backend data moved with this visual taxonomy.

## Implemented Foundation

- A single Canvas, parsed GLB and scene survive core/system/domain URL changes.
  Camera destinations use actual root bounds, with explicit portrait placement.
- The domain camera approaches from outside the system, looking inward. Other
  planets and scenery remain present instead of replacing the universe with a
  separate closeup scene. Actual visibility/composition still needs browser proof.
- Camera travel uses 1.15-second quintic interpolation. Back/Escape/history and
  resize retarget from the sampled pose. Identical destinations do not replay travel.
- Departing moons remain visible until arrival, including rapid retargets; retained
  identities are bounded to the five domains. Reduced motion skips travel/idle motion.
- Slow planetary motion, Core breathing and moon orbits are bounded; the selected
  planet holds position. Projected HTML labels use 44px targets and throttle at rest.
- Core uses an existing lightweight procedural object while the 24.32 MiB system
  loads. This is an intentional temporary visual substitution, not the authored Core.
- One texture is initialized per animation frame, then existing Three.js
  `compileAsync` prepares shaders. Prepared means texture/shader preparation, not
  proof that geometry buffers and all postprocessing passes cannot hitch.
- Versioned HTTP cache and a single-flight leased resource avoid repeat parsing.
  Assets remain while leased and for a 30-second release grace; expired/abandoned
  results dispose safely. No unlimited scene cache or extra loading framework.
- Object and label activation share real routes; workspace links carry validated
  spatial return state. AppShell's hub action can return to the originating planet.
- Domain pages are still ordinary routes and unmount the Canvas. Quick returns can
  reuse parsed assets, but must warm a new renderer. Future cards/panels have not
  yet been integrated over a permanently mounted workspace canvas.
- Hidden tabs/reduced motion use demand rendering. Renderer failure/context loss
  retains ordinary domain links and explicit retry. Backend is untouched.

## Actual Verification

Default-route integration checkpoint (2026-10-01, supersedes the old-default
and Layer 0 exit behavior described in earlier checkpoints below):

- Focused routing, scene recovery, real moon-handler, return-path and login tests:
  **46 passed, six files**. Every ready moon's link and each domain's real mesh
  handlers are exercised. These DOM/scene-logic tests do not prove GPU visuals.
- After replacing the old shell glyphs, return-transition tests: **2 passed**.
- Production build including `tsc -b`: PASS, 1,858 modules, Vite 19.30 seconds.
  Existing large-main-chunk warning remains; spatial chunk is 432.07 kB uncompressed.
- Local `/` returned HTTP 200. Vite's served App source includes the new root
  scene and compatibility redirect, and no HubPage reference. Backend health: ok.
- Live browser visual/performance verification remains unexecuted following the
  previously recorded browser-security rejection. No screenshot/60 FPS claim.

Latest preparation/recovery/exit checkpoint (2026-10-01):

- Preparation status now lasts through texture/shader preparation, rather than
  disappearing when the download/parse finishes.
- Renderer failure clears readiness and unmounts Canvas. Canonical fallback links
  remain available; retry creates a fresh Canvas and waits for new preparation.
  Parsed assets remain owned by the existing resource lease, not discarded/reloaded.
- Late rejected preparation from an abandoned renderer cannot invalidate a
  successful retry. Controlled pending/rejected promises exercise this guard.
- Hierarchical Back at Layer 0 now exits to `/`, avoiding a history trap that could
  reopen the previous system layer. Browser Back/Forward retains normal route history.
- Final targeted run: **10/10 tests, two files**, 6.29 seconds: the eight-test
  `spatialJourneyUi.test.tsx` and two-test `app-shell-transition.test.tsx`.
- Current production build: PASS including `tsc -b`; 1,866 modules; Vite 10.51
  seconds. Spatial JS 315.82 kB before gzip; existing large-main-chunk warning remains.
  No full-suite/backend rerun or live GPU/recovery measurement is claimed.
- Public and built V37 GLB hashes still match the frozen hash below. No standalone
  small authored Core GLB exists in the inspected art directories; the procedural
  cold-entry substitution remains an explicit limitation. No second asset pipeline
  or material change was introduced just to avoid this acceptance limitation.

Previous label/framing continuation (2026-10-01):

- Fixed an actual travel-label defect: inline `visibility: visible` overrode the
  motion-hide stylesheet. Projection now uses `data-projected`; travel clears it
  and arrival restores it after reprojecting. No inline visibility defeats CSS.
- Focused current run: **26/26 tests, three files**, 8.53 seconds:
  `tests/spatialArtworkFraming.test.ts`, `spatialJourneyUi.test.tsx`,
  `spatialJourney.test.ts`. Counts below belong to the earlier foundation milestone,
  not an additional current full-suite result.
- Then-current `npm --prefix apps/web run typecheck`: PASS. The production build below
  is the earlier milestone result; no new build/full-suite claim is made here.
- Twelve framing tests read actual V37 GLB node transforms and POSITION accessor
  bounds. At 1440x900 and 390x844, the entrance contains Core, each domain camera
  contains its body/full sampled moon orbit, and at least two wider-system centers
  are inside its frustum. This does not prove occlusion, brightness or recognizability.
- Three fresh jsdom snapshots read the real stylesheet from disk and check hidden,
  projected and moving states. Vitest strips CSS imports in the app DOM harness;
  the separate Node tests avoid claiming that empty imported CSS proves the cascade.
- The DOM harness now manually steps registered frame callbacks in priority order.
  It checks one-frame reduced-motion projection, interrupted travel returning to
  the exact entrance, and context-loss fallback/retry with a new mocked Canvas.
  The renderer, GLTF fixture, moon objects and GPU remain mocked. No real context
  restoration, visibility, GPU or frame-rate acceptance is inferred.

- Final focused frontend run: **40/40 tests, seven files**, 21.90 seconds.
  Covers resource leases/retry/disposal, URL policy, camera retarget/no-op behavior,
  bounded moon retention, taxonomy, DOM navigation, section focus, old hub behavior
  and AppShell return regression. Do not add repeated earlier runs to this count.
- DOM integration asserts one mocked Canvas mount and one fetch through spatial
  navigation. At that milestone frame callbacks were not executed; the latest
  bounded continuation steps them explicitly. Neither harness renders WebGL.
- Final `npm --prefix apps/web run build`: PASS, including `tsc -b`; 1,866 modules,
  Vite phase 22.12 seconds. Spatial page is a real lazy production chunk, 315.78 kB
  before gzip. Existing approximately 1.47 MB main-chunk warning remains.
- Two workers had disjoint scopes: route catalogue and asset ownership. The latter
  then performed bounded independent source review. Findings were corrected and
  rechecked; see `SPATIAL_JOURNEY_REVIEW.md`. No duplicate full-suite/backend runs.
- Existing localhost server remained listening on 127.0.0.1:5173, PID 1416.

## Frozen Art Evidence

Source `E:/LifeOS-Art/system/system-art-v37.blend`; public
`apps/web/public/art/system/life-os-system-v37.glb` and adjacent report.
Source SHA256: `ebf47ade9dd5a56f31abadeede10efdd5b7aa89cb8ddca341aad03bba85a85c3`.
Asset SHA256: `619afbf0b22c49e6910e2328abce8faa77542fbecbd85aa3bf86a6ff49f5a4f2`.
Report: 281,614 triangles, 39 asset draws, 29 images, 25,503,516 bytes.
Estimated decoded RGBA8+mips 160 MiB, not measured GPU total.
V37 landscape/portrait/reduced/untextured renders were inspected previously;
shared-rig six-body closeups are V35 evidence, not relabeled V37 images.
Independent V37 clump correction accepted; complete-art gate was never met.

## Remaining Acceptance Work

GPT-6 Astra is the user-appointed visual reviewer/controller. Its first bounded
review inspected the main reference, Fitness reference and authored V37 still,
not the current web scene. See `SPATIAL_JOURNEY_VISUAL_BRIEF.md` for the six visual
criteria, taxonomy guardrails and required acceptance views. Primary retains
implementation, integration and verification ownership; reviews are milestone
batches rather than continuous full-project rereads.

Review priorities: destination composition and visible distant context; moon/label
separation, especially Life and portrait; entrance/travel continuity. Still-image
observations are not runtime defects or approval. No new material polishing or
additional scope is authorized by this review.

Browser tool access was explicitly SECURITY BLOCKED earlier. No retry, alternate
browser, headless/CDP, shell screenshot or other workaround was used. The new
journey therefore has no browser screenshots, canvas-pixel checks, GPU timings,
mobile visual acceptance, context-loss recovery execution or shader-runtime proof.
Pure helpers and DOM mocks cannot stand in for this evidence.

## Completion Audit

| Requirement | Current evidence | Unproven acceptance |
| --- | --- | --- |
| Entrance Core + gravity well | Scene source; demand-frame DOM checks; real Core bounds | Live entrance appearance/cold substitution |
| V37 system | Source/build hashes; authored renders; runtime integration | Actual web lighting/framing |
| Planet + named moons + distant system | Canonical catalogue; V37 frustum/orbit tests | Readability, occlusion, moon/label spacing |
| One scene across Layers 0-2 | Canvas mount/load regression through query changes | Actual GPU/context continuity |
| Staged/preloaded assets | Leases; texture staging; compile source and promise tests | First-draw buffer/effect cost, warm/cold timings |
| Cancellable travel + idle motion | Camera math; manually stepped reversal | Visible smoothness, idle composition, frame times |
| Keyboard/back/reduced motion | DOM routing/demand-frame checks; source | Live accessibility and viewport behavior |
| Loading/error recovery | Pending/failure/stale-promise/context-event tests | Real device loss/restoration behavior |
| Preservation/scope | Canonical route tests; frozen asset hashes; backend not edited | Card integration intentionally deferred |

Previous goal turn made concrete progress. Goal completion remains unproven:
the outstanding evidence requires legitimate browser access or user-supplied live
captures, not more repetitions of the same synthetic tests. An asynchronous request
for current entrance/Fitness desktop and narrow screenshots is already outstanding.

Next priorities: actual first-page/planetary screenshots and motion checks through
legitimate browser access; fix observed framing/lighting or first-entry hitches;
measure frame-time distributions/memory growth during repeated forward/back;
then the user's card/workplace specification. No universal zero-load or 60 FPS claim.
This is a working foundation checkpoint, not completion of the active goal.
