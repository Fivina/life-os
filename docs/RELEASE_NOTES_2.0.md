# Life OS 2.0 Release Notes

Life OS 2.0 is the completion release for the non-voice core. It does not introduce a new lifestyle domain. It proves that the systems delivered through v1.9B work together as one restart-safe, text-first daily-use product.

## What 2.0 Proves

- Self Core can orchestrate canonical Planning, Learning, Fitness, Kitchen, Finance, Home, Life, Calendar, workspace, attention, and conversation state without becoming a second database.
- Named daily-use regression scenarios cover morning start, study recovery, cooking and inventory, workout execution, Finance capture, uncertainty review, Notebook parking, prospective movies, social filtering, proposal acceptance, restart continuity, two-client convergence, and AI outage.
- Quick Capture proposes typed domain mutations; uncertainty enters the Review Queue; accepted changes still pass through domain services.
- Active Workspaces, conversations, plans, threads, feedback state, and canonical domain records survive fresh sessions and process restart.
- Events and WorldRevision drive transport-neutral realtime invalidation and gap recovery.
- Gemini, Laya, Jev, and external discovery/metadata providers may all be absent without preventing core startup or deterministic daily workflows.
- Empty-database migration, previous-revision upgrade, downgrade/re-upgrade, PostgreSQL integration, backup/restore, and deterministic source packaging are automated release checks.

## Daily-Use Improvements

- Application and package versions now report 2.0 consistently.
- The shell stays visually quiet while live state is connected and shows a clear retryable banner while offline or reconnecting.
- Release checks are organized around one manifest and one command instead of duplicating scenario logic.

## Known Limitations

- Real Gemini, Laya, Jev, TMDB, API-Football, Ticketmaster, Web Push, and hosted deployment behavior require their own credentials/runtime and are optional.
- Laya performance depends on local hardware and model availability; no personalized model training is part of 2.0.
- External opportunity and movie/showtime coverage depends on configured adapters; no purchase, reservation, or booking is performed.
- The product remains a private single-user modular monolith. Production deployment and managed snapshot retention are operator responsibilities.
- Voice, STT, TTS, VAD, barge-in, microphone streaming, wake word, and a native hands-free companion are deliberately deferred to separately authorized v2.1+ work.
