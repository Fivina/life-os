# Phengos component audit — 2026-10-04

## Active route ownership

- `/` is routed by `apps/web/src/app/App.tsx` to `features/phengos/PhengosHome.tsx`.
- `/kitchen` is routed to `features/kitchen/KitchenPage.tsx`, whose overview delegates to `KitchenOverview.tsx`.
- `/calendar` is routed to `features/calendar/CalendarPage.tsx`, whose main surface delegates to `CalendarWorkspace.tsx`.
- The legacy `features/home/HomePage.tsx` is not imported by `App.tsx`; its `MetricSlider` and `ConsistencyHeatmap` imports are therefore archival candidates.
- `components/StatTile.tsx` remains active in Life, Fitness, Learning, Finance, and Personal Model pages and should be preserved.

## Intentional dual surfaces

`PhengosHome` is the current launcher and contextual overview. The routed Kitchen and Calendar pages remain canonical domain tools with their existing controls and API ownership. `SupplyCore` and `ChronoRing` are spatial hub/preview infrastructure, not duplicate routed domain pages.

## Duplicate findings and recommendations

The old HomePage component set and Phengos launcher are overlapping overview surfaces, but only Phengos is active at `/`. This pass detects these candidates and preserves them; archival should follow a reference and preview check. `MetricSlider` and `ConsistencyHeatmap` are imported only by the legacy HomePage in the source tree. `StatTile` has active routed consumers and is not a retirement candidate.

Kitchen has one routed page and one overview component. Its lower Chef, cooking, receipt, recommendation, planned-meal, nutrition, inventory, recipe, shopping, and competency surfaces are all rendered from `KitchenPage.tsx`; they are utilities inside the canonical page, not duplicate components. Calendar similarly has one routed workspace; ChronoRing is visual preview/spatial infrastructure.

The generic `StatTile` CSS has layered declarations in `global.css`, but this is cascade reuse rather than duplicate rendering. Cleanup should be handled separately with visual verification.
