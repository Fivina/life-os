# Life OS handoff — 2026-10-03

Workspace: `D:/Life OS`. This follows, and does not replace, `CURRENT_STATE_2026-10-02.md`. The user is reviewing the Phengos redesign and has asked to focus on the desktop/PC workflow. They said the current visual result is still far from the catalog; do not describe it as accepted or finished. The ten sheets in `New Design` are design references. Read `docs/PHENGOS_ROADMAP.md`, `docs/PHENGOS_FEATURE_INVENTORY.md`, and `docs/PHENGOS_DESKTOP_FLOW_RESEARCH.md` before changing the flow.

## Delivered locally in this iteration

- Blender v17 smooth-sky scene: `E:/LifeOS-Art/phengos/phengos-intro-v17-smooth-sky.blend`. Original v16 remains. The scene corrects coarse blue clouds and exported a silent 1280x720 H.264 film, 511 frames at 60 fps. Web assets are in `apps/web/public/art/phengos/` (`environment-v17-60.mp4`, `opening-v17.png`, `idle-environment-v17.png`, `rest-environment-v17.png`). The home uses native video plus still plates and a live CSS/Motion circle; no normal-home WebGL or canvas loop.
- `PhengosHome` plays/skips/replays the film, opens the desktop workspace from the circle, preserves 21 route/section destinations, returns to the horizon after configured genuine inactivity, and respects reduced motion. Existing routed feature pages remain intact.
- `PhengosContextCards` projects canonical Calendar plans/commitments, Fitness status, Kitchen shopping/selected meals, standing fixtures and assistant proposals into asymmetric, ranked cards. It polls while the workspace is open. Pinning is browser-local and dismissal only affects the current view. Shopping purchase and next workout actions use existing endpoints. Planned fitness blocks only link to training because the next workout template may not match the block.
- The assistant now saves proposal IDs with conversation messages, restores current proposal status in saved chats, exposes an authenticated read-only pending-proposal feed, and provides the exact saved thread ID for each proposal card. Approval/cancellation still goes through existing authorization, version/revision, expiry, and idempotency checks. Home cards display arguments before offering approval; complex proposals require full chat review. A confirmed-then-declined race now reports the earlier save truthfully.
- Fixture normalization retains safe provider logo URLs for future synced fixtures. No match, score, meal photo or agent success is fabricated.

## Verification

- Focused frontend tests: 27 passed across Home, projection, runtime and Assistant.
- Focused backend tests: 26 passed across proposal restore/feed and fixture logo normalization.
- TypeScript typecheck and production Vite build passed. Existing large main bundle warning remains.
- In-app browser at `http://127.0.0.1:5173/` showed decoded intro playback advancing, video ending in the live circle, desktop cards populated from saved data, navigation from the daily card to `/calendar#daily-list`, and Home return without replay. Browser API did not expose dropped-frame counts; 60 fps refers to the encoded film, not a measured rendering guarantee.
- Local Vite dev server runs on port 5173; backend uvicorn on port 8000. There is no configured Git remote or public hosting target in this workspace. This is a local preview, not a public deployment.

## Remaining product work

- The desktop surface is an iteration for review; the original feature pages and chat are not yet fully transformed into the catalog's card language. Continue from the user's feedback instead of marking roadmap milestones accepted.
- Voice transport, listening/speaking states and agent-authored arbitrary card layouts are future work. The existing persisted proposal path is the safe action contract to reuse.
- Recipe records have no photo field. Fixture logos depend on a real provider sync; the current Beşiktaş rule in the local database had not synced at browser inspection.
- Measure real browser animation smoothness on the user's target device before claiming 60 FPS. Optimize the large existing main JS bundle during product polish.

## Later PC design continuation (2026-10-03)

- The user clarified that design includes motion, animation, display, dashboard composition, aesthetics and user-oriented utility, and that card backends are handled in another session. Voice is excluded for now. Read `docs/PHENGOS_PREMIUM_IMPLEMENTATION_TASKS.md`, `docs/PHENGOS_VISUAL_LANGUAGE.md` and `docs/PHENGOS_ARCHITECTURE_AND_IMPLEMENTATION_MAP.md` before delegating or building the next slice.
- `PhengosHome` now has an actual PC overview and domain layer. A full-viewport desktop frame, compact seven-domain rail, large persistent circle, contextual dashboard and asymmetrical domain component cards replace the former small menu layout. All 21 existing routes remain accessible through the directory. A feature-link return carries the originating layer; the assistant prompt draft is retained in session storage across route transitions.
- `AppShell` now has one routed navigation system: the persistent sidebar/drawer and centered small circle. The duplicate feature popup was removed. The circle toggles that one navigation surface, and the existing Back, breadcrumb, skip link, connection/reminder controls and routed work views remain.
- Shared visual tokens are in `apps/web/src/features/phengos/phengosTheme.css`; all 21 route descriptors now have truthful short utility copy. This is a live example and a design contract for future agents, not just a prose brief. The actual browser walkthrough showed overview → Home component cards → routed work, and the assistant work view with sidebar open/closed. The old domain page internals still require Task 4 migration.
- The read-only backend map found canonical sources for calendar, kitchen, fitness, fixtures, assistant proposals, review and strategy flows. Integration gaps are documented separately: persistent pin/dismiss, a near-term fixture feed, uniform freshness/provenance and assistant action-proposal adjustment. No new backend card service was implemented in this continuation.
- Focused Home/runtime/navigation tests: 57 passed across three files after the single-menu change. TypeScript and production Vite build passed; the existing ~1.45 MB main JS chunk warning remains. Browser FPS was not measured; the encoded film remains 60 fps, which is a separate claim.
