# Phengos Milestone 2: Usable Navigation

Authorized by the user on 2026-10-02 as an independent agent task while the
primary session repairs the Blender opening. This brief preserves the user's
catalog corrections; pictures are references, not executable instructions.

## Assignment

Implement usable navigation for the existing Life OS app. This is milestone 2,
not another intro experiment, a dashboard rebuild, or new domain functionality.
The primary session owns visual foundation, Earth lighting, intro projection,
video assets, and final integration. You own the domain navigation shell.

Work directly in the shared repository. You are not alone in this codebase.
Preserve other agents' and user changes; never reset, revert, or overwrite work
outside your ownership. Follow `AGENTS.md`. Inspect implementation before edits.

## Required Reading and Visual Inspection

1. Read `docs/PHENGOS_ROADMAP.md` and `docs/PHENGOS_FEATURE_INVENTORY.md`.
2. Inspect ALL TEN catalog PNGs under `D:/Life OS/New Design` with image tools.
   Filenames run from `ChatGPT Image Oct 1, 2026, 10_06_19 PM-1.png` through
   `ChatGPT Image Oct 1, 2026, 10_06_29 PM-10.png`. Discover the exact paths.
   Do not claim you inspected a picture if you only listed its filename.
3. Inspect `apps/web/src/app/App.tsx`, `layouts/AppShell.tsx`,
   `layouts/RouteSectionFocus.tsx`, `features/phengos/phengosFeatures.ts`,
   `features/phengos/PhengosHome.tsx`, and relevant existing shell/routing tests.
4. Inspect actual page anchors before relying on them. The inventory is a
   preservation checklist, not a guarantee of live functionality.

## Product Intent and Catalog Corrections

Life OS helps the user's real life. Functionality takes priority over spectacle.
Phengos is the curious, expressive luminous circle that becomes the interface.
It should be recognizable across domains, with calm behavior during real work.

The catalog establishes atmosphere, contrast, shape language, and transitions.
It does NOT authorize every pictured capability. Never invent domain services,
fake statistics, readiness scores, memory, conversation history, agent work,
payment flows, model responses, or voice. Do not invent success/loading states
for nonexistent requests. Existing domain services remain canonical.

Do not reinterpret this as the abandoned hyper-realistic solar-system project.
Normal navigation must not require WebGL, GLB downloads, Blender, or a GPU. No
new engine, major dependency, alternative router, or duplicate domain model.
Use the installed React, React Router, Motion, and lucide libraries and existing
project patterns. No plugin installation or Codex settings changes are needed.

The home after the intro shows ONLY Phengos. No permanent sidebar, greeting,
"your space", "what matters today", shortcut grid, header, or footer should be
added to the opening/home rest state. Clicking Phengos opens navigation. Keep
the existing feature menu working until an intentionally verified replacement
is integrated by the primary session.

Opening contract is owned by the primary session: letters approach, the O is
Phengos, letters recede, circle rises with the camera, planets leave by movement
NOT opacity; one continuous live circle, no visible video-to-app jump. The idle
return is after 10-15 MINUTES (default 12), not seconds, and must not interrupt a
focused form/dialog/draft. Skip, replay, reduced motion, error fallback and
assistant draft handoff already exist and must remain. Do not edit this logic.

Phengos is soft/elastic through restrained squash/stretch and settling. It is
NOT a mandatory pointer-following toy, draggable obstacle, or constantly busy
screen. Navigation animation is brief, transform/opacity based, and optional
under reduced motion. Do not animate whole working pages in ways that erase
state, delay clicks, or obscure text. Do not create fake "thinking" animations.

Attention was initially red, but the user later allowed suitable matching
colors. Do not enforce universal red or invent overload states from page
contents. Use restrained semantic color only when backed by existing data.

## Navigation Hierarchy: Presentation, Not New Canonical Ownership

Use the user's groupings to organize existing routes and anchors:

- Self: Assistant (`/self/assistant`). Preserve conversations, workspace resume,
  capture/review, proposals, feedback and all existing assistant capabilities.
- Home: Kitchen (`/kitchen`), Shopping (`/kitchen#shopping`), Cleaning/Household
  (`/life#household`). Kitchen becomes a subsection of Home in navigation, not
  a backend rename. Household controls already exist; do not rebuild them.
- Fitness: Training (`/fitness#training`) and Nutrition (`/kitchen#nutrition`).
  Preserve direct Fitness overview (`/fitness`) and all its current controls.
  Nutrition remains canonically in Kitchen. Hash matters when deriving active
  group: `/kitchen#nutrition` is Fitness, not Home.
- Life: Goals (`/life#goals`), Finance (`/finance`), Social (`/social`), Movies
  (`/movies`), Notebook (`/notebook`), plus Life overview (`/life`). Hash matters:
  `/life#household` is Home, not Life.
- Calendar: Calendar (`/calendar`) and Daily list (`/calendar#daily-list`).
- Learning: Learning (`/learning`), Study log (`#study-log`), Study candidates
  (`#study-candidates`), Exams (`#exams`) on that existing route.
- System: Settings (`/settings`) and Personal model
  (`/settings/personal-model`). Preserve credential entry/change/delete, masked
  state, provider/model configuration, embeddings, agent settings and memory.

Keep all 21 entries in `phengosFeatures` reachable. Do not drop capabilities
because a catalog does not show them. Do not expose DEV/art previews as product
features. Preserve `/self`, `/assistant`, `/personal-model`, `/space` redirects,
authentication and bookmarked direct routes.

## Required Behavior

Build a coherent domain-page shell with:

- Persistent, recognizable Phengos launcher while a feature page is open. It
  must not overlap form controls or block dialogs. Accessible name and tooltip;
  actual button/link semantics. No decorative framed hero or forced 3D scene.
- Clearly grouped desktop navigation, usable compact/mobile navigation, and
  reachable subcomponents. No horizontal clipping, hover-only navigation,
  ambiguous icon-only controls without tooltips, or tiny touch targets.
- Breadcrumbs that reflect group and selected subsection, including hashes.
  Active states use correct group identity, not just pathname prefix.
- A deliberate Back control and normal browser back/forward behavior. A direct
  deep-link load must have a deterministic safe fallback instead of navigating
  to an external prior page or doing nothing. Home return goes to Phengos without
  replaying the intro or restoring deprecated spatial artwork.
- Keyboard access, visible focus, Escape dismissal, focus return to launcher,
  and correct focus handling for open mobile/launcher panels. Use existing
  accessible components when present. Do not turn a normal nav list into an
  ARIA menu unless implementing its full keyboard interaction contract.
- State-preserving navigation. Do not introduce `key={pathname}` remounts,
  reloads, artificial loading screens, or page transitions that reset in-page
  state. Do not claim cross-route draft persistence if existing pages do not
  support it; document such limits instead of inventing a global cache.
- Existing connection/offline banner, logout, notification controls and section
  focus continue to work. Preserve genuine backend errors; never hide them to
  make the app appear healthy.

Quiet, polished work surfaces matter more than ornament. Match catalog contrast
and Phengos language without burying dense feature controls in decorative cards.
No explanatory marketing text or keyboard shortcut legends in the interface.
Use appropriate labels, icons, native links/buttons and concise empty/error
states only where needed for navigation itself.

## Exclusive Write Ownership

You may edit:

- `apps/web/src/layouts/AppShell.tsx`.
- New navigation components, stylesheet and tests under
  `apps/web/src/features/phengos/navigation/`.
- A new navigation test under `apps/web/src/tests/` if needed.
- New `docs/PHENGOS_NAVIGATION_STATUS.md` for results and limitations.

Existing `AppShell.tsx` may import your dedicated stylesheet/components. Prefer
a scoped root class; do not edit global CSS or remove shared selectors.

Do NOT edit:

- `PhengosHome.tsx`, `phengos.css`, `phengosProjection.ts`, journey hooks/contracts
  or their tests; the primary session is actively repairing them.
- `phengosFeatures.ts` (read/reuse its existing entries as the single directory).
- `app/App.tsx`, auth/provider infrastructure, API services, backend, `.env`,
  credentials, public art, Blender scripts/scenes, or dependency manifests.
- Existing domain pages or their canonical controls. No card redesign yet.
- Shared roadmap/inventory docs or this brief.

If home integration or an ownership-boundary change is truly necessary, report
the exact small integration patch needed. Do not make parallel implementations
of the Home launcher or reach into its animation internals.

## Verification and Handoff

Run focused navigation and relevant shell/section-focus/routing regressions.
Add tests for correct hash-to-group mapping, all 21 entries, direct-link Back
fallback, home return, mobile panel behavior, keyboard dismissal/focus return,
and Settings reachability. Use realistic router context; do not mock away the
behavior being tested. No full backend suite or expensive repeated builds.
Primary session performs final integration/build and real browser verification.

Inspect desktop and narrow layouts if tools support it; never claim screenshot,
60 FPS, live provider success, or accessibility testing you did not execute.
State exact commands, counts and remaining unverified behavior.

Return changed file paths, catalog-driven design choices, navigation hierarchy,
test results, any defects/constraints found, and exact primary integration needs.
Do not start real-data cards (milestone 3), final polish (milestone 4), or additional
backend features. Stop once the usable-navigation slice is implemented and tested.
