# Phengos Feature Inventory

Purpose: preserve current Life OS functionality while the Phengos visual redesign changes the home surface. This is a code inventory, not a runtime verification report. “Implemented UI” means a routed page currently wires controls to `api.ts`; “API-only” means a service method exists without a corresponding routed feature page identified here. Provider calls, backend availability, and live success are unverified.

## Routes and anchors

| Route | Current surface |
| --- | --- |
| `/` | Protected home entry; milestone 1 replaces the old WebGL scene with `PhengosHome`. Existing feature pages remain unchanged. |
| `/space` | Protected redirect to the spatial home flow. |
| `/self`, `/assistant` | Redirect to `/self/assistant`. |
| `/self/assistant` | Assistant, morning context, workspaces, planning/review controls, and conversation UI. |
| `/calendar` | Calendar, commitments, actions, plans, and plan-block controls. |
| `/life` | Life/household overview and related home data. |
| `/fitness` | Fitness tracking and workout UI. |
| `/learning` | Learning/courses/topics/progress UI. |
| `/kitchen` | Kitchen and Chef UI. |
| `/finance` | Finance overview, budgets, imports, recurring expenses, and transactions. |
| `/settings` | Intelligence/provider/model settings plus general settings controls. |
| `/settings/personal-model`, `/personal-model` | Personal-model summary, versions, patterns, refresh, and correction UI. |
| `/notebook` | Notebook entries, search, review/archive, and promotion UI. |
| `/movies` | Movie library, recommendations, watchlist, history, and Letterboxd import UI. |
| `/social` | Social trajectory, activities, opportunities, recommendations, and dismiss/outcome controls. |
| `/login` | Authentication UI. |

The updated Phengos launcher reads existing Kitchen shopping/meal-plan, Fitness,
Calendar, standing-fixture, and assistant-proposal data for contextual cards.
Purchase, workout-start, and explicit proposal approval/cancellation call the
existing domain endpoints and invalidate their shared query caches. A pending
proposal links to its saved conversation for review. The launcher does not create
a new source of truth, and the original routed domain controls remain available.

Development/preview routes are separate from the production navigation: `/_dev/system-art`, `/_dev/self-core`, `/_dev/neural-bloom`, `/_dev/dark-hole`, `/_dev/life-core-earth`, `/_dev/home-supply-core`, and `/_preview/fitness-orbit`. Several are DEV-gated or lazy-loaded previews, so they are not product feature guarantees. Existing section links: Kitchen `#nutrition`, `#shopping`; Fitness `#training`; Calendar `#daily-list`; Learning `#study-log`, `#study-candidates`, `#exams`; Life `#goals`. Milestone 1 adds `#household` to Life's already implemented household controls, making them accessible under Home without moving canonical ownership.

## Assistant, capture, review, and planning

### Implemented UI: `/self/assistant`

- Sends assistant messages, with a selected role and optional existing thread, through normal or streamed assistant responses.
- Lists, opens, creates, and archives assistant threads.
- Displays streamed agent work activity, including model/thinking, tool use, delegation, and routing events; the page also exposes assistant work-log data when returned.
- Loads the morning briefing and foreground workspace; can resume an active workspace.
- Shows assistant proposals and can confirm or cancel them.
- Shows pending review items from quick capture/review flows. Review actions include accept, edit-and-accept, reject, or dismiss; quick captures can be applied or rejected.
- Shows planning proposals and can accept or reject them. `api.ts` also supports present and modify operations; preserve those controls where rendered by the current assistant/planning UI.
- Feedback sessions support clarification, question responses, completion, and cancellation when a session is present.

### Implemented UI elsewhere

- `/calendar` exposes plan generation/replanning, plan-block start/complete/partial-complete/skip/cancel, day evaluation, action completion, and commitment completion/update flows through the calendar page.
- `/notebook` exposes entry creation, search, review, archive, and promotion to manual development review.

### API-only or not independently verified as routed UI

`api.ts` contains explicit endpoints for `quickCapture`, `applyQuickCapture`, `rejectQuickCapture`, pending `/review` items, strategy proposal present/modify/accept/reject, feedback sessions, workspace resume, and assistant proposal confirmation/cancellation. Their service contracts are present; this inventory does not claim every endpoint has a currently reachable button or that a live request succeeds.

## Providers, models, and embeddings

### Implemented UI: `/settings`

- Reads and updates intelligence settings.
- Stores or deletes OpenAI, Gemini, and Jev provider credentials; displays provider configuration state.
- Loads provider model lists and assigns provider plus economy, fast, and reasoning models per agent.
- Saves agent profiles, including continuity and the self-core ambiguous-routing/“Use Jev” setting.
- Provides OpenAI chat and Jev decision capability-test buttons when configured.
- Reads and updates embedding provider/model settings and provides an embedding-provider test control when rendered by the settings page.
- Links agent settings to `/settings/personal-model` for the agent memory domain.

These are configuration and request paths only. No provider key validity, model availability, embedding success, latency, or live execution is asserted.

## Domain inventory

### Fitness: `/fitness`

Implemented UI and API wiring cover body measurements/latest measurement, fitness status and body trends, goals, programs, exercises, workout templates and template exercises, active workout sessions, exercise sets, session completion/abandonment, recovery observations, readiness summary, candidates/action sync, and progression.

### Kitchen: `/kitchen`

Implemented UI covers Chef natural-language intent and recommendations, no-shopping mode, select/reject meal options, planned meals, cooking mode with ingredients/steps/servings, satisfaction and feedback on completion, recipe creation, fridge inventory add/consume/adjust/staple configuration, nutrition targets, external meal logging, receipt upload/read/retry/review/confirmation, shopping needs/actions, and kitchen status. `#nutrition` is an existing anchor.

### Learning: `/learning`

The page is routed and uses learning status/courses/topics/progress-related operations. `api.ts` also exposes learning candidates and candidate-action synchronization, plus course and topic creation/update operations. Preserve the current course/topic/progress controls; do not infer successful syncing from the service definitions.

The section links expose Study Log, Study Candidates and Exams. These must remain
reachable even when newer home cards show only a brief overview.

### Life and household: `/life`

The routed life page covers the current life/home overview surface. `api.ts` exposes household overview (`/home/overview`) and related home data, plus shared commitments, actions, calendar projection, and planning operations. Development-only home/core-earth previews are visual previews, not additional production routes.

Actual controls include goal creation and trajectory display, recurring household
task creation, due/upcoming chores and version-checked task completion. This is
existing functionality, not a nonexistent Cleaning service to reinvent.

### Finance: `/finance`

Implemented UI covers recorded-data safe-to-spend breakdown, monthly/protected budgets, CSV bank-import staging, row review/accept/dismiss, import confirmation, recurring-expense refresh/detection, and recent transactions. The page links users to the assistant for finance questions. It explicitly presents the data as recorded/imported and does not move money or invent balances.

### Notebook: `/notebook`

Implemented UI/API support general and implementation-idea entries, filtering by type/status, notebook search, create, review, archive, and promote-to-manual-development-review.

### Social: `/social`

Implemented UI/API support social trajectory settings, social activity listing/creation, opportunity listing/filtering, recommendation refresh, source links, dismissing opportunities, recording recommendation outcomes, opportunity-source settings, and source discovery.

### Movies: `/movies`

Implemented UI covers movie search/library creation, weekly leisure trajectory min/max, recommendation inputs for time/mood/genres, choose/watch/reject outcomes, watchlist add/remove, watch history, and Letterboxd CSV preview/import with row matching and confirmation.

## Shared API-only capabilities to preserve

The service layer also exposes standing calendar rules and fixture overrides, push subscriptions and test notifications, data export, leisure/social opportunity source maintenance, finance import row confirmation, and several typed domain read/write contracts used by pages. These are current API capabilities, not claims of independently reachable UI. The redesign should keep route ownership and existing API contracts stable until each surface is intentionally migrated.

## Verification boundary

This inventory was derived from `apps/web/src/app/App.tsx`, routed feature pages, and `apps/web/src/services/api.ts`. No tests were run, no backend was changed, and no live provider or runtime behavior was verified.
