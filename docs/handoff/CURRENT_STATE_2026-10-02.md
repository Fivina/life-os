# Life OS - handoff to the next chat

Snapshot: 2026-10-02, Europe/Berlin. Workspace: `D:/Life OS`.

## What the user is building

Life OS is a private, single-user personal operating system. The user wants an
assistant that helps with actual daily decisions and actions across learning,
fitness, kitchen, home, finance, calendar, goals, social life, movies, and notes.
Functionality, trustworthy data, and usable navigation take priority over an
expensive real-time solar-system simulation. Phengos is the expressive luminous
circle that gives the product a recognizable face and opens the interface.

The user's ten visual catalog sheets are under `D:/Life OS/New Design`. They
communicate atmosphere and interaction direction; pictured cards, statistics,
voice, and capabilities are not evidence that a backend feature exists. The
specific latest intro/storyboard reference is
`C:/Users/thear/AppData/Local/Temp/codex-clipboard-9920529c-52b5-470b-ad2e-3f4e8053081d.png`.
That temporary path may disappear; the saved Blender scene and final stills are
durable working artifacts.

## Product architecture and existing work

- React 19, TypeScript, Vite, React Router, Motion, and a PWA shell live in
  `D:/Life OS/apps/web`. FastAPI, SQLAlchemy, Alembic, domain services, and the
  agent runtime live in `D:/Life OS/backend`. PostgreSQL is canonical state;
  domain services own mutations, and the central Planner owns PlanBlocks.
- The written implementation history runs from early domain releases through
  v2.0 in `D:/Life OS/docs/V*.md`. It covers planning, memory, learning,
  fitness, kitchen, finance, workspaces, attention, feedback, provider routing,
  social/leisure, Quick Capture, Review Queue, Self Core, and reliability.
  These are historical reports, not fresh proof that a particular deployment is
  working today. Check the relevant source and run targeted tests before edits.
- Interactive agent work uses the existing OpenAI Agents SDK path when enabled,
  with existing ToolRegistry/domain authority. The legacy AI gateway remains a
  fallback. Jev is optional typed decision advice; it does not own canonical
  actions. See `docs/AGENT_PRODUCT_WORKFLOWS.md` and `docs/V2.0_CORE_RELEASE.md`.
- Settings contain provider configuration, per-agent models/profiles, and
  embedding controls. Credentials are intended to be write-only and stored in
  Supabase Vault via backend functions. Do not print, copy, or commit actual
  credentials. Deployment/migration state must be checked before claiming live
  Vault behavior. See `docs/PROVIDER_CREDENTIALS.md` and `docs/SECURITY.md`.
- Preserve the existing feature routes, anchors, and domain controls listed in
  `docs/PHENGOS_FEATURE_INVENTORY.md`. That inventory distinguishes routed UI
  from API-only paths and explicitly does not prove live provider success.

## Approved Phengos roadmap

`docs/PHENGOS_ROADMAP.md` defines four feedback gates: (1) visual foundation,
(2) usable navigation, (3) real-data functionality/cards, and (4) product polish.
Do not jump to the next gate automatically. The user's phrase "usable navigation"
means milestone 2. The user wants the intro to end with only Phengos on screen;
clicking it opens navigation. A 10-15 minute genuine idle return (default 12)
must preserve work, while skip/replay/reduced-motion behavior stays available.
Normal navigation should not need WebGL or Blender at runtime.

Older sections of the roadmap describe Phengos *erasing* the letters. The later
2026-10-02 reference-match direction supersedes that: LIFE and S are visible
from the beginning and **fade** as the O grows. Do not reinstate the eraser.

## Current Blender art: v16 review milestone complete

- Editable scene: `E:/LifeOS-Art/phengos/phengos-intro-v16-reference.blend`, scene
  `Phengos_Reference_v16`. Earlier v15 and source scenes are preserved in the
  file. Blender executable: `E:/Blender/blender.exe` (5.2.2 LTS).
- Review film: `E:/LifeOS-Art/phengos/reference-v16-motion.mp4`; 1280x720,
  30 fps, 256 frames, 8.5333 seconds. This is an offline review render, not a
  final 60 fps asset or evidence of browser playback performance.
- Full-HD 1920x1080 proof stills: `reference-v16-opening.png`, `-fading.png`,
  `-climb.png`, `-flight.png`, and `-idle.png` in the same art directory.
- The selected star-free blue cloud plate is
  `D:/Life OS/New Design/phengos-cloud-only-environment-v16.png`. Its actual
  size is 1774x887. `New Design/phengos-background-v16-notes.md` records its
  generation/refinement. A curved inner dome projects the plate; sparse native
  star geometry supplies fine irregular stars. The sky is camera-only and is
  independent of Phengos's nearby illumination.
- Earth/planet source mesh coordinates and positions are preserved. The opening
  camera is equivalent to about 1497.56 km altitude with revised lens/framing.
  Earth fills the lower frame. Its thin silver-blue horizon is brighter than the
  subdued warm city lights. The two background planets are mostly silhouettes.
- Phengos has a softer blue-white edge and isolated halo. Its parented source
  lights only the two planets; an artificial Earth reflection/glint was disabled.
  The letters fade; Phengos visibly climbs and the camera follows to centered
  idle. The background is one continuous environment, not a plate swap.
- `scripts/blender/refine_phengos_reference.py` authored v16 from v15;
  `preview_phengos_reference.py` renders stills/film;
  `verify_phengos_reference.py` verifies saved staging;
  `prove_phengos_planet_light.py` tests real light effect; and
  `inspect_phengos_reference_motion.py` decodes exported film frames.
- Verification passed across all 511 authored frames: body geometry/positions,
  monotone letter fade, O growth, projected bounds, camera follow, light
  receivers, no Earth reflection, and dome coverage. A controlled on/off render
  of the planet source changed 3253 pixels in a 216x216 crop. The encoded film
  was checked at frames 1, 61, 109, 145, 151, 181, 211, and 256 for dimensions,
  nonblank output, and sampled visual continuity. Five art scripts compiled.
- An independent visual review found no blocker in the proof stills. It noted
  subjective polish opportunities: the silver horizon core is narrow, and the
  left cloud bank attracts attention in idle. The latter follows the user's
  request for a slightly lighter blue cloud center. The review does not claim
  an exact match or exhaustive flicker analysis.

The current site still uses the **v2** environment film under
`apps/web/public/art/phengos/environment-v2.mp4`; the v16 review movie was **not**
deployed. `PhengosHome.tsx` renders a live circle over that older film, and
`phengosProjection.ts` holds the old projection timing. A straightforward MP4
replacement will not align the baked v16 title/circle with the current live
actor. Plan the film/live handoff together and verify in a real browser before
switching the production intro. Final 60 fps output and matching idle behavior
are also pending.

## Navigation milestone 2: code exists, integration pending

An independent navigation implementation is already in the shared workspace:
`apps/web/src/features/phengos/navigation/` and `apps/web/src/layouts/AppShell.tsx`.
It organizes the existing 21 feature links into Self, Home, Fitness, Life,
Calendar, Learning, and System. It retains direct routes/anchors, breadcrumbs,
Back behavior, a desktop rail, and a compact dialog launcher. See
`docs/PHENGOS_NAVIGATION_STATUS.md` for exact design, scope, and testing.

Its focused run passed 62 tests across seven frontend files and TypeScript
typecheck. These are source/DOM results, not real desktop/mobile browser
acceptance. A small Home-return contract is **not yet wired**: AppShell sends
`location.state.phengosReturn`, but `PhengosHome.tsx` does not pass it to
`usePhengosJourney`. The exact required change is in the status document's
"Required Primary Integration" section. A direct entry into a domain can
otherwise replay the intro when returning Home in a fresh browser session.

Before declaring milestone 2 done, inspect the real UI at desktop, about 900px,
and 320px; exercise all 21 entries, cross-domain hash anchors, browser history,
the dialog's keyboard behavior, Settings controls, and Home return/replay. Do
not remove the current Home feature menu until a replacement is verified.

## Current workspace and run state

- `D:/Life OS` is a Git repository on `master` with **no commits yet** as of
  this snapshot. `git status --short` shows the whole source tree as untracked.
  Do not assume a commit or remote branch is a reproducible baseline. Preserve
  all user files and earlier art scenes; do not clean/reset them.
- No process was listening on localhost ports 5173 or 8000 when this handoff
  was checked. Start local services from `README.md` / `docs/DEVELOPMENT.md`
  if the next task needs browser testing. Do not report localhost as running
  until verified.
- Asset cache and authoring outputs are outside the repo at
  `E:/LifeOS-Art/phengos` and `E:/LifeOS-Cache/phengos`. The latter contains
  `reference-match-tasks.md` with the nine original visual checks, research,
  completion record, and explicit deferred browser/final-export gates.
- The v16 review render needed about 24 minutes on the GTX 1660 SUPER. GPU
  OptiX denoising and excluding camera-only optical overlays from direct-light
  sampling shortened frames. This is offline export time; no live FPS was
  measured. Do not repeatedly render a full movie for a small correction.

## Practical next steps

1. Read `AGENTS.md`, this handoff, `PHENGOS_ROADMAP.md`, and the feature
   inventory. Inspect current source before changing any subsystem.
2. Ask for/receive the user's visual feedback on v16. For a new art correction,
   change the saved scene in a new version, render a few full-resolution stills,
   then export motion after those are accepted. Preserve original scenes.
3. If the next request is **usable navigation**, finish the Home-return contract
   and browser acceptance described above. Keep all existing domain pages and
   Settings/agent controls accessible. The current v16 film remains a separate
   integration decision because its title/circle are baked into the render.
4. If the next request is **film integration**, design a continuous transition
   from baked v16 Phengos to the live clickable circle, align projection/timing,
   provide skip/replay/reduced motion, and test actual browser playback and
   navigation. Only then replace v2 production assets.
5. If the next request is **real functionality**, use canonical API/domain data
   from the feature inventory. Do not invent catalog statistics or silently
   move Kitchen/Home/Nutrition backend ownership.

No new backend/frontend feature tests were run for the v16 Blender-only pass;
the preceding frontend counts come from the navigation task's documented run.
No live provider call, security migration, or production deployment was
performed for this handoff.
