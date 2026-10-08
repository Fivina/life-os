# Life OS handoff — 2026-10-04

Workspace: `D:/Life OS`. This is the current entry point for continuing the desktop PHÉNGOS redesign. The October 2 and 3 handoffs are historical snapshots; their old art, navigation, and server-state claims must not be treated as current without checking the live repository.

## Direction and source of truth

- The latest visual references are the six images in `New Design/Design/`: `1.png`, `2.png`, `3.png`, `4.png`, `5.png`, and `download.png`. `2.png` is the strongest full desktop Calendar reference; `3.png` and `4.png` isolate the sidebar and contour; `5.png` is the Kitchen composition. Earlier images in `New Design` and the three supplied PDFs are context, not authority to replace newer working behavior.
- Read `AGENTS.md`, `docs/PHENGOS_ROADMAP.md`, `docs/PHENGOS_FEATURE_INVENTORY.md`, and `docs/PHENGOS_UNIVERSAL_DESIGN_CONTRACT.md` before making a redesign change. The contract preserves the user-supplied palette and dated visual corrections. `docs/PHENGOS_VISUAL_LANGUAGE.md` describes the current code-level material and interaction rules.
- Keep all existing routes, anchors, controls, data states, and backend ownership. The live repository is implementation truth. No circle redesign, voice mode, generated food photography, or new card backend is in this visual pass. The user handles card backends in another session.
- The user is reviewing the **desktop/PC** result against the catalog. This design is not yet accepted. Do not call the milestone finished or claim a pixel-exact match.

## Current desktop implementation

- The v17 Blender introduction is served locally with native video/still assets in `apps/web/public/art/phengos/`. The routed workspace uses `workspace-environment-v17.png` from the same scene. The background is the primary visual surface; no page-wide dark overlay should hide it. The introduction and normal home do not require a live WebGL scene.
- Home combines real-data contextual cards and domain navigation. The routed shell has a narrow floating navigation capsule with the identifier and orb separated above it, an angular contour, domain-aware active state, Back and breadcrumbs, and a floating assistant entry. There is no continuous top or bottom chrome bar. The 21 existing destinations remain accessible through the domain panels and Search.
- The approved glass hierarchy is **dark blue translucent glass for a major workspace frame**, then **deeper near-black translucent glass for ordinary information cards and repeated items**. Use a thin bright upper reflection and a controlled illuminated contour; the scene should remain perceptible through the fill. Source-domain colors belong mainly to edges, icons and selections. Needs Attention is red glass; PHÉNGOS suggestions are blue glass. Repeated rows avoid individual backdrop blur for rendering cost.
- Calendar uses this treatment across its main day/week/month scene, scheduled event blocks, Today, Week Allocation, Commitment Calendar, date card and insight panels. The lower preserved tools also use glass: Standing Calendar Rules, Calendar Projection, its timeline, Needs Attention, Week Map, Add Commitment, Add Intention, proposals when present, and Planning Pool. `CalendarPage.tsx` now scopes those tools under `.calendar-page`; `.calendar-needs-attention` carries the red semantic material. CSS is in `apps/web/src/features/calendar/calendar-workspace.css`.
- Kitchen uses the same hierarchy across its overview, PHÉNGOS suggestion, meal recommendation, fridge, nutrition, quick actions, weekly meals, shopping connection, and all lower preserved tools and forms. Its material is in `apps/web/src/features/kitchen/kitchen.css`. Meal photography remains deferred until the approved backend utility supplies it; the code-native plate motif remains.
- Shared tokens and other routed glass rules are in `apps/web/src/features/phengos/phengosTheme.css` and `apps/web/src/features/phengos/navigation/navigation.css`. Avoid creating a second palette or alternate navigation system.

## Most recent correction and verification

The user rejected an earlier first pass because the Calendar grid and its right-side information cards looked matte, and Kitchen's lower tools still looked like older flat cards. The latest pass added the structural blue/dark glass contrast, upper-edge reflections, scene transparency, and scoped treatment for the complete lower Calendar and Kitchen pages. It did not remove features or alter API behavior.

- Full-page desktop captures from the running local browser: `docs/handoff/PHENGOS_CALENDAR_FULL_GLASS_2026-10-04.png` and `docs/handoff/PHENGOS_KITCHEN_FULL_GLASS_2026-10-04.png`. Both cover the overview **and** lower utilities. Earlier `*_ALL_GLASS_*`, `*_REWORK_*`, and `*_BEFORE_REWORK_*` files are intermediate comparison captures, not the final view of this correction.
- The local preview was inspected at `http://127.0.0.1:5173/calendar` and `/kitchen` with a temporary 1800×900 browser viewport. The viewport override was reset after capture, and the Kitchen preview was left open. A later chat should verify whether the server is still running instead of assuming it is.
- `pnpm --filter @life-os/web build` passed after the Calendar and Kitchen edits: TypeScript build and Vite production build, 2279 modules. The existing large main-chunk warning remains. No backend tests were needed for this CSS/markup-scoping pass. Browser frame cadence was **not measured**; neither the 60 fps encoded intro nor a passing build proves 60 fps UI rendering.
- The screenshots and build verify the implementation, not user visual acceptance. Review at wide desktop and laptop sizes again if the user provides further visual feedback.

## Next work and guardrails

1. Ask for no new scope by default: respond to the user's next visual comparison against the latest `New Design/Design` images. Inspect the relevant current component and browser view before changing it.
2. Preserve the existing lower Calendar and Kitchen utilities while refining their composition. Do not hide or delete them merely to make the first viewport look like a catalog sheet.
3. Keep ordinary cards dark; use red glass only for actual attention and blue glass for PHÉNGOS suggestions. Keep the introduction background visible through localized glass, with enough contrast for labels and controls.
4. Verify visual changes in the live browser and run a targeted build or test at the next meaningful milestone. Measure actual frame cadence before making a 60 fps claim. Product polish and user acceptance remain open.

The repository had no reproducible committed baseline in the earlier handoffs; verify `git status` before attempting Git operations. Do not reset or clean the user's working tree.
