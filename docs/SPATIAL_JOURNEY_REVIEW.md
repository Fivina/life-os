# Spatial Journey Integration Review

Read-only code review of the current integration, 2026-10-01 15:18 CEST. The primary is still adding tests/docs; this is a source snapshot, not acceptance of the finished integration. No tests/build were run, no browser was accessed, and no visual rendering or measured frame-cost claims are made. Catalogue contents were not audited.

Line references below are within `apps/web/src/features/hub/`. Snapshot SHA-256 prefixes: `SystemArtPreviewPage.tsx` B6285240E672, `spatialJourney.ts` D70D36D70AA5, `SpatialMoons.tsx` F31F6E15DC0A.

## Prioritized Findings

1. **P1: Demand rendering can leave navigation labels hidden or stale.** `SystemArtPreviewPage.tsx:370-372` skips projection until 80 ms have accumulated, but `:477` uses demand rendering for reduced motion. View/ready/resize updates can request only one frame within that interval; nothing schedules the remaining label update. Newly mounted labels default to hidden (`system-art-preview.css:75`), while `SystemArtPreviewPage.tsx:518` removes fallback links once ready. This can leave ready domain moons without usable controls. Force projection on view/readiness/resize changes, or schedule a bounded follow-up frame rather than depending on continuous animation.

2. **P2: An unchanged camera destination still starts travel and changes scene visibility.** `SystemArtPreviewPage.tsx:311-316` always calls `travelTo`; `spatialJourney.ts:86-90` resets the journey even when destination equals the current pose. Completing preparation at core depth targets the same entrance camera, but `SystemArtPreviewPage.tsx:340-343` then exposes all system roots/scenery for that artificial journey and `:367` hides labels through the moving selector. Visibility restoration can also start this no-op journey. Skip travel when the sampled pose already matches the destination, while preserving retargeting of actual in-flight journeys.

3. **P2: Outgoing moons disappear before the return camera journey finishes.** `SystemArtPreviewPage.tsx:418` passes no active domain as soon as the URL becomes system/core or another domain; `SpatialMoons.tsx:53,72` immediately hides the outgoing group. The camera still travels for 1.15 seconds (`spatialJourney.ts:6,86-90`). Keep the departing moon system visible through that transition, then retire its visibility on arrival. The planets remain mounted; this finding concerns moon continuity specifically.

4. **P2: Actionable moon bodies have no activation handler.** `SpatialMoons.tsx:58-62` renders named groups/meshes with no click callback, and `SystemArtPreviewPage.tsx:418` supplies no selection callback. The GLTF click handler at `:407-414` belongs to a separate primitive, so it cannot activate these sibling moon objects. Available workspaces can be reached only through their HTML labels (`:509-511`); selecting their 3D bodies does nothing. Wire available moon routes through the existing navigation path and leave planned moons non-actionable. No drag/zoom requirement is inferred.

## Bounded Risks

- **P2, first-render cost remains outside the warm-ready contract.** `SystemArtPreviewPage.tsx:299-302` initializes textures and compiles scene materials, then marks prepared. This does not initialize GLTF vertex/index buffers or effect passes introduced when entering system depth (`:423-425`). The installed Three renderer's `compile` prepares materials (`node_modules/three/src/renderers/WebGLRenderer.js:1449` onward), rather than rendering geometry. A first visible system/domain frame can still incur those costs. Treat prepared as texture/shader readiness; actual hitch severity remains unmeasured.

- **P3, warmup rejection is not cancelled with its effect.** `SystemArtPreviewPage.tsx:301-308` guards successful completion with `active`, but passes `onFailure` directly as the rejection callback. A late rejection from an obsolete warmup could latch failure on the page after retry. Guard the rejection callback with the same active flag. The installed Three implementation currently uses resolve-only asynchronous polling and throws compilation errors synchronously, so this is a conditional cancellation risk, not a demonstrated current rejection failure.

## Contracts Checked

The Canvas stays mounted across core/system/domain URL changes; its boundary is keyed only by retry (`SystemArtPreviewPage.tsx:476-485`). The module-scoped resource, active callback guard, lease release, and preparation-error disposal are present (`:141-169`). `CameraJourney` retargets from the sampled pose, clones caller poses, and supports immediate reduced-motion arrival (`spatialJourney.ts:80-102`). Moon frame updates run before label projection through priorities -3 and -2. These source checks support the ownership/travel design but do not establish renderer behavior under StrictMode, context loss, or demand rendering. The observed journey tests exercise the pure helpers, not these integration paths; ongoing primary test work may change that coverage.

## Fix Recheck: 2026-10-01

Bounded source recheck of the named fixes and their route/anchor/return integration, approximately 15:25 CEST. Primary tests are still being added. Earlier findings above describe the original snapshot; the statuses below supersede them. Current hash prefixes: preview A9417E4832FA, journey 71906DBC6D1B, moons D04F18F4B16B, section focus 5AA01C1A5B6F. No tests/build/browser execution or visual validation was performed.

| Earlier Finding | Status | Current Source Evidence |
| --- | --- | --- |
| Demand-mode label timer | Closed at source level | `SystemArtPreviewPage.tsx:314-320` forces `labelElapsed = 1` and invalidates for composition/destination, readiness, resize, and reduced-motion changes. |
| No-op camera travel | Closed | `spatialJourney.ts:94-100` compares position, quaternion, and FOV with tolerances and immediately settles equal poses. A focused unchanged-destination regression test exists at `spatialJourney.test.ts:42`; it was read, not run. |
| Departing moons disappear | Partially closed | `SystemArtPreviewPage.tsx:322-327,343,430-433` retains a departing domain through sampled-camera arrival and passes incoming/outgoing domains together. Normal single-destination returns are covered by this logic; interrupted retargeting remains open below. |
| Missing moon activation | Closed | `SpatialMoons.tsx:58-60` activates only available hrefs. `SystemArtPreviewPage.tsx:433,488,527-528` gates mesh activation during travel and supplies return state for both mesh and label navigation. |
| Stale warmup rejection | Closed | `SystemArtPreviewPage.tsx:304-311` now guards rejection as well as success with the effect's active flag. |
| First geometry/effect cost | Open, unmeasured | Texture/shader readiness still does not establish first geometry/effect render cost. The previously documented limitation remains; no offscreen GPU workaround is needed for this source recheck. |

### Remaining Continuity Finding

**P2: Rapid URL retargeting can replace the actual departure before arrival.** At `SystemArtPreviewPage.tsx:325-326`, A -> B records departing A and last-requested B. A further B -> C URL change before the camera arrives replaces departing A with B. `:430-432` then shows only B and C even if the sampled camera is still near A; A's moons disappear before the journey stops. Browser history can change the URL during travel, so the click lock does not exclude this sequence. Preserve an already retained departure until the journey settles, rather than replacing it with every requested domain.

The same retention is installed in a passive effect (`:322`), after the first changed-view commit can hide the old group. That leaves a possible inter-commit visibility gap on an ordinary exit. Commit retained visibility with the view/pose transition before a frame can observe the new destination; this timing risk has not been visually reproduced.

### Named Route And Anchor Checks

`app/App.tsx:103-106` places `/space` under `ProtectedRoute` while preserving the existing hub index. `HubPage.tsx:92` links its Orbit control to `/space`. `layouts/AppShell.tsx:46-50` consumes return state through the exact-path allowlist and canonical spatial view parameters in `spatialJourney.ts:25-30`; no external return URL is accepted. Direct moon-to-workspace-to-spatial return wiring has no additional source finding.

`layouts/RouteSectionFocus.tsx:7-29` decodes the hash, waits for a target when necessary, scrolls/focuses it, and cancels its observer/frame/timer on cleanup. The named section headings have IDs and `tabIndex={-1}` in their existing pages: Calendar daily-list, Learning study-log/study-candidates/exams, Fitness training, Kitchen nutrition/shopping, and Life goals. This confirms the supplied anchor mechanism without repeating the catalogue audit.

The newly observed `spatialJourneyUi.test.tsx` checks URL navigation, one mocked Canvas mount/load, and workspace links. It explicitly stubs frame callbacks and moon rendering, so it cannot resolve the remaining retarget/visibility timing finding or establish rendered demand-mode labels. Test execution and broader integration acceptance remain with the primary.

## Final Retention Recheck: 2026-10-01

Last-fix-only source review, approximately 15:31 CEST. Snapshot prefixes: preview 8BAA44A6394A, journey A5042004D7C3, journey tests A00C340F7D6C. Primary integration verification remains separate. No tests/build were rerun and no browser was accessed.

**Remaining continuity finding: closed at source level.** `spatialJourney.ts:33-36` unions prior departures with the previous domain instead of replacing them. Starting from the component's empty array and validated five-domain identities, Set deduplication bounds retained identities to five despite repeated retargeting. Reduced motion returns an empty array. `SystemArtPreviewPage.tsx:432-435` keeps those departures visible alongside the incoming domain; `:344-345` clears them only after sampling establishes camera arrival.

The visibility timing risk is also closed at source level: retention now runs in `useLayoutEffect` (`SystemArtPreviewPage.tsx:322-329`) before paint. The updater capture is correct: `previous` is copied from `lastDomain.current` at `:324`, captured by the pure functional updater at `:326`, and the ref advances only afterward at `:328`. A deferred or replayed updater therefore cannot accidentally read the new destination as the old domain.

`spatialJourney.test.ts:6-12` contains assertions for rapid A -> B -> C retention, a repeated identity, and reduced-motion clearing. These tests were inspected, not executed. No further correctness finding remains within this last-fix scope. The previously documented geometry/effect cost remains open and unmeasured; rendered behavior is not claimed.
