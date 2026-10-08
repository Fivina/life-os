# Phengos PC architecture and implementation map

Prepared 2026-10-03 after inspecting the current frontend routes, feature inventory and backend contracts. This document coordinates the five tasks in `PHENGOS_PREMIUM_IMPLEMENTATION_TASKS.md`. It is not permission to expand the backend in this chat. Card backend work belongs to the user's other session; this session owns display design, frontend utility and integration with contracts that already exist. Implement the visual grammar in `PHENGOS_VISUAL_LANGUAGE.md`, then judge it in the running PC UI against the catalog sheets.

## One route model, one data owner

`apps/web/src/app/App.tsx` places all production domain pages under `AppShell`; `/` hosts `PhengosHome`. `phengosFeatures.ts` lists all 21 route/anchor destinations. Keep React Router, the existing app shell, breadcrumbs, Back/history, keyboard access and route section focus. Do not create a second router or duplicate card service. Frontend view models may combine read data for display; canonical mutations stay with existing domain endpoints and Query invalidation.

The production dashboard should be composed from two frontend layers:

1. **Stable surface:** greeting, prompt, domain navigation, trustworthy day/area overview and entry points.
2. **Contextual surface:** ranked cards only when the corresponding source provides a relevant user event, plan, item or proposal. Pinned state affects visual order; empty and stale states are explicit.

Development scenario galleries may demonstrate dense match, gym, friend, shopping, chosen meal and agent-proposal states without placing invented content in production.

## Source and action map

| User experience | Existing backend source | Existing action / frontend destination | Frontend responsibility |
| --- | --- | --- | --- |
| Today, meetings, daily list | `GET /api/v1/calendar-projection`, current plan and commitments | `/calendar#daily-list`; version-guarded commitment and plan-block actions | Project near-term blocks, avoid duplicate highlights, retain source and date |
| Shopping | `/kitchen/status`, `/shopping-needs`, `/shopping-list` | `/shopping-items/{id}/purchase`; `/kitchen#shopping` | Show real aggregate items and status; keep list and purchase controls truthful |
| Selected meal | `/meal-plans`, Kitchen/Chef recommendations | Native meal-plan select, update and complete flows; `/kitchen` | Show a meal only when selected/saved; link to Kitchen work view |
| Training today | `/fitness/status` includes next workout, active session, readiness and plan window | Existing workout start/set/finish endpoints; `/fitness#training` | Distinguish planned template from active session; offer Start only for an actionable template |
| Near-term Beşiktaş fixture | `/standing-calendar-rules`, then each rule's `/fixtures`; normalized fixture may include crests and linked commitment | `/calendar` and standing-rule/fixture controls | Normalize only enabled rules; show opponent/date/logos when supplied; do not invent score |
| Assistant action proposal | `/assistant/proposals/pending`, saved `/threads/{id}` | `/assistant/proposals/{id}` confirm/cancel; `/self/assistant?thread=...` | Display exact arguments/consequence, explicit approval, stale/error state and thread link |
| Review / strategy proposal | `/review`, `/strategy/proposals/{id}` | Review resolution, strategy present/modify/accept/reject in native assistant | Keep these types distinct from assistant action proposals; only show Adjust where a real path exists |

Other routed domains already have backend owners: Life/home/household/goals, Learning, Finance, Social, Movies, Notebook, Personal Model, Settings/providers and workspaces. Their existing pages are the working views. The new shell and domain overview should lead into those pages; migration must keep their full controls.

## Real contract gaps to coordinate with backend session

- Persistent pin/dismiss preferences have no shared backend contract; local UI state is provisional.
- Fixtures require a standing-rule list and per-rule fetch, with normalized JSON parsing. A focused near-term feed would simplify the frontend, but the current route is usable.
- Freshness/provenance varies by domain model. The frontend can label known sources and avoid claiming uniform sync state.
- Assistant action proposals support confirm/cancel and thread follow-up; they have no general modify endpoint. Strategy proposals separately support modify. An Adjust button for an assistant action should open its saved conversation or native flow until a typed edit contract exists.
- There is no cross-domain card feed. The existing Query client can project canonical responses now; a future backend feed must not become a second source of truth.

## Implementation sequence and ownership

1. **Desktop shell and navigation (Task 1):** complete the real overview/domain/subcomponent/workspace flow, persistent circle and role colors. Preserve the 21 links and drafts. The PC surface and Home component example are implemented in `PhengosHome`; routed `AppShell` uses one toggleable 21-link sidebar/drawer controlled by the circle. The earlier separate navigation popup was removed so two main menus cannot overlap. Routed Back carries the opening home layer when a card or component link supplied that origin.
2. **Card presentation (Task 2):** typed view models, card anatomy, relevance and scenario gallery. Keep the existing `phengosCardProjection.ts` adapter; extend it by source, not by a second store.
3. **Conversation and card actions (Task 3):** complete visual approval/review flow and exact-thread navigation. Respect each proposal type's real mutation contract; voice transport stays out.
4. **Domain migration (Task 4):** Kitchen Shopping/Meal, Fitness Training, Calendar Daily List and Assistant Review first; then Life/Learning; Finance/Settings; Social/Movies/Notebook/Personal Model. Extract common domain overview, section header and action row only after two real migrations prove the shape. Retain forms/tables/history in the deepest work view.
5. **Measured visual quality (Task 5):** reference comparison, motion, accessibility and target-PC cadence/bundle profiling. Apply these standards in every task, with the final pass checking continuity across all routes.

## Preservation and review

Use `PHENGOS_FEATURE_INVENTORY.md` for behavior checks. Review each major visual slice as both a still and an interaction recording at wide and laptop PC sizes: idle circle → dashboard → domain → working view → Back/Home. Verify real data/empty/error labeling, focus, reduced motion, route anchors, drafts and canonical actions. The existing tests verify route and selected card behavior; they do not establish catalog fidelity or 60 FPS browser rendering.
