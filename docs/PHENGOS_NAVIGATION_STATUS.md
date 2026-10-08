# Phengos Navigation Milestone 2 Handoff

Date: 2026-10-02. The domain navigation slice is implemented in the shared
workspace. Home-return integration was completed later the same day; local
browser checks at desktop, 900px, and 320px are recorded below. The original
navigation slice did not add milestone 3 or 4 functionality.

## Changed Paths

- `apps/web/src/layouts/AppShell.tsx`
- `apps/web/src/features/phengos/navigation/navigationModel.ts`
- `apps/web/src/features/phengos/navigation/useWorkspaceBack.ts`
- `apps/web/src/features/phengos/navigation/PhengosNavigation.tsx`
- `apps/web/src/features/phengos/navigation/navigation.css`
- `apps/web/src/features/phengos/navigation/navigation.test.tsx`
- `docs/PHENGOS_NAVIGATION_STATUS.md`

Only these owned paths were edited. The home, journey contracts/hooks/tests,
feature directory, router, global styles, domain pages, backend, configuration,
dependencies, credentials, art and Blender files were not edited by this task.

## Catalog Inspection and Design

All ten original PNGs in `New Design` were opened with `view_image`, not merely
listed. Exact inspected filenames:

1. `ChatGPT Image Oct 1, 2026, 10_06_19 PM-1.png`
2. `ChatGPT Image Oct 1, 2026, 10_06_20 PM-2.png`
3. `ChatGPT Image Oct 1, 2026, 10_06_21 PM-3.png`
4. `ChatGPT Image Oct 1, 2026, 10_06_22 PM-4.png`
5. `ChatGPT Image Oct 1, 2026, 10_06_23 PM-5.png`
6. `ChatGPT Image Oct 1, 2026, 10_06_24 PM-6.png`
7. `ChatGPT Image Oct 1, 2026, 10_06_25 PM-7.png`
8. `ChatGPT Image Oct 1, 2026, 10_06_26 PM-8.png`
9. `ChatGPT Image Oct 1, 2026, 10_06_28 PM-9.png`
10. `ChatGPT Image Oct 1, 2026, 10_06_29 PM-10.png`

The implementation adopts the persistent white luminous circle, compact labeled
sidebar, clear group/subsection depth, dark neutral work surface, thin borders,
distinct existing domain icon colors and visible keyboard focus from sheets
3/4/8/9. The panel has one brief transform/opacity entrance and restrained circle
press feedback; reduced motion disables transitions. Working pages have no
entrance animation or pathname key. Catalog dashboards, statistics, payment,
voice, thinking and future-domain concepts were not implemented.

The domain shell uses an unframed content area. Desktop navigation scrolls
vertically in its own rail. At 900px and below the rail is replaced by the
persistent circle launcher; its modal contains every entry. Touch controls are
at least 44px. No WebGL, artwork downloads or new library is required.

## Hierarchy and Live Anchors

The unchanged `phengosFeatures` remains the only feature directory. Presentation
order is Self, Home, Fitness, Life, Calendar, Learning, System. All 21 entries are
rendered in both desktop and launcher navigation.

| Group | Existing entries |
| --- | --- |
| Self | Assistant `/self/assistant` |
| Home | Kitchen `/kitchen`; Shopping `/kitchen#shopping`; Household `/life#household` |
| Fitness | Fitness overview `/fitness`; Training `/fitness#training`; Nutrition `/kitchen#nutrition` |
| Life | Life overview `/life`; Goals `/life#goals`; Finance `/finance`; Social `/social`; Movies `/movies`; Notebook `/notebook` |
| Calendar | Calendar `/calendar`; Daily list `/calendar#daily-list` |
| Learning | Learning `/learning`; Study log `/learning#study-log`; Study candidates `/learning#study-candidates`; Exams `/learning#exams` |
| System | Settings `/settings`; Personal model `/settings/personal-model` |

All nine section IDs were verified on actual page headings, each with
`tabIndex={-1}`: Kitchen nutrition/shopping, Life goals/household, Fitness
training, Calendar daily-list, and Learning study-log/study-candidates/exams.
`RouteSectionFocus` remains mounted and unchanged.

## Route, History and Focus Behavior

- Active group and breadcrumbs resolve pathname plus decoded hash, so Nutrition
  belongs to Fitness and Household belongs to Home. Unknown/malformed hashes
  use the route overview; no section is invented.
- Same-page links retain the existing query string and route state. Links to
  another route do not copy page-specific query/state into an unrelated page.
- Back uses `navigate(-1)` only when the shell has observed the preceding entry.
  PUSH, REPLACE, POP and a new branch after Back are tracked using router keys.
  This is an in-memory navigation trail, not a domain data cache.
- A first/direct entry falls back to its group overview, or `/` if already on
  that overview. Examples: Nutrition -> `/fitness`, Household -> `/kitchen`,
  Personal model -> `/settings`, Settings -> `/`. Unobserved browser entries are
  never used by the shell Back button. Native browser Back/Forward still work.
  The observed trail resets when the shell unmounts or the app reloads.
- Home links always use `/`, ignore legacy `spatialReturn`, and send
  `{ phengosReturn: true }` for primary-session integration described below.
- The native modal dialog supplies background inertness and the browser top
  layer. Escape, cancel, close-button and backdrop dismissal restore launcher
  focus. Tab/Shift+Tab boundaries wrap. Selection closes the panel without an
  extra launcher-focus request that would override section focus. Body scrolling
  is restored on close/unmount. Lists retain ordinary link semantics.
- Skip to content focuses/scrolls the main without overwriting the subsection
  hash. Notification result messages, notification setup, logout and the genuine
  offline/reconnecting banner remain wired to the existing implementations.

The solution reuses React Router and native dialog instead of adding a router or
modal framework. Relevant references:
[React Router useNavigate](https://reactrouter.com/api/hooks/useNavigate) and
[native dialog behavior](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog).

## Verification

Final focused test command, run from `D:/Life OS/apps/web` using installed Node
directly after package-wrapper worker-start timeouts:

```powershell
& 'C:\Program Files\nodejs\node.exe' 'D:\Life OS\node_modules\.pnpm\vitest@4.1.11_jsdom@27.4.0_vite@7.3.6\node_modules\vitest\vitest.mjs' run src/features/phengos/navigation/navigation.test.tsx src/tests/app-shell-transition.test.tsx src/layouts/RouteSectionFocus.test.tsx src/tests/connection-status.test.tsx src/tests/app-spatial-routing.test.tsx src/tests/life.test.tsx src/tests/app.test.tsx --pool=forks --maxWorkers=1
```

Result: **PASS**, exit 0, **7 files / 62 tests**, duration 129.61s. Navigation has
47 tests; existing regressions have 15. These counts are distinct tests, not a
sum of repeated runs. The unchanged app regressions verify `/space` redirects,
Home entry, shell return/re-entry, section focus, connection state, existing Life
controls and private login. Existing Three CommonJS deprecation warnings remain.

Earlier verification: the first six-file run had 58 passes and two failures
(dialog boundary selector and an ambiguous test status query). Both were repaired.
A six-file rerun passed all 60 tests before the final skip-link/backdrop checks.
Two subsequent package-wrapper invocations encountered Vitest's fixed 60-second
worker-start timeout: one ran no tests, the other passed the login smoke test but
could not start navigation. Neither is counted as a navigation pass. The final
direct Node invocation above passed every selected test after all code changes.

TypeScript command, from the same working directory:

```powershell
& 'C:\Program Files\nodejs\node.exe' '.\node_modules\typescript\bin\tsc' --project tsconfig.app.json --noEmit --incremental false
```

Result: **PASS**, exit 0, with no diagnostics, after all final code changes.
The preceding equivalent
`pnpm --dir apps/web exec tsc --project tsconfig.app.json --noEmit --incremental false`
passed with exit 0; a prior run identified invalid `exact` options in the new
Testing Library role queries, which were removed. No production build or backend
suite was run by this task.

The navigation test uses a real MemoryRouter/Routes/Outlet and the real shell,
section-focus component, navigation links and Back hook. Domain controls are a
small stateful fixture; realtime, logout and notification service calls are
mocked. jsdom lacks native dialog showModal/close, so only those browser methods
are shimmed. Tests do not establish real-browser top-layer behavior, background
inertness, native Tab progression, screen-reader support or touch layout.

No live provider request, FPS measurement, screenshot or visual acceptance is
claimed. Browser discovery during this task reported `No browser is available`.
The primary session owns final build and real desktop/mobile browser inspection.

## Primary Home Integration (2026-10-02)

`PhengosHome.tsx` now consumes `location.state?.phengosReturn === true` and passes
it to `usePhengosJourney`. A direct Settings entry followed by Return to Phengos
opens the circle workspace without replaying the intro. Explicit replay still
starts the film. This was checked in focused component tests and in the local
browser at the 320px viewport. The existing Home feature menu remains reachable,
with all 21 routes/anchors preserved.

In the local browser, the Home circle and menu were inspected at the default
desktop viewport, 900×700, and 320×568. The 320px layout had no document-level
horizontal overflow; Settings opened from the Home menu, kept its existing
controls visible, and the breadcrumb returned Home without replay. Focused tests
verified every route/anchor link and the Home replay contract. This is not an
exhaustive live exercise of all 21 destinations, native dialog behavior in every
browser, or production provider functionality.

## State Preservation Limits and Acceptance

Same-page subsection navigation and opening/dismissing navigation preserve mounted
page state. Removing the shell pathname key also avoids forced remounts of shared
page component types. Different existing route components still unmount normally:
their component-local drafts are not guaranteed to persist across route changes
or Home return. No global draft cache or duplicate domain state was introduced.

For primary acceptance: inspect desktop, 900px compact and 320px mobile layouts;
keyboard/touch navigation to all entries; native modal focus/inertness and existing
Assistant dialogs; both cross-group hashes; direct Back fallbacks; real Settings
credentials/model controls; Home-return integration; and normal browser history.
The user feedback gate remains milestone 2; do not start cards or further polish
automatically.
