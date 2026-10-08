# W1 navigation and Chat review

2026-10-08. Separate read-only `navigation_review`, gpt-5.6-sol/medium,
bounded frontend review against33fceb3. No edits, broad audit or test reruns by
reviewer. Primary owns final integration. User visual acceptance remains open.

Navigation: one P2 dark-centered Chat orb violated frozen white identity. Author
corrected canonical white fill and white glow; reviewer inspected correction.
No other scoped navigation finding.73 author targeted tests/typecheck passed.

Chat/overlay findings, corrected and re-reviewed:
- P1: deferred confirmation/cancellation could append into a different active
  conversation after switching. Require captured thread/generation or pending locks.
- P2: unsupported raw initial role could be sent while picker displayed fallback.
  Require normalization to a registered option before send, preserve message history.
- P2: new-thread completion could erase text typed while creation was pending.
  Require preservation or disabled composer and a post-resolution regression.

Primary browser corrections: explicit Chat grid rows prevent optional error-state
absence stretching the composer; portal native dialog outside header avoids banner
stacking/header style inheritance. Reviewer inspected both corrections.

Primary runtime: disposable SQLite8001/frontend5174, AI disabled. Real synthetic
thread persisted; changing conversation and returning restored its unsent draft.
Calendar embedded send left URL on /calendar; close/minimize/reopen retained draft,
same conversation.390px mobile modal removed underlying workspace from accessibility
tree; breakpoint transition retained draft and close restored launcher focus.
Mobile proof: ignored artifacts/unified-contract/baseline/calendar-chat-mobile.jpg.
No live provider success, paid calls, or user visual acceptance claimed.

After correction:37 related assistant/stream/redirect/launcher tests passed;67
navigation/Home/runtime/redirect tests passed; web typecheck passed. The separate
reviewer completed a final bounded pass with no remaining scoped findings and a
clean diff check. Primary browser verified Kitchen's registered Chef normalization,
desktop Calendar/Kitchen overlays, full Chat persistence, and the390px Calendar
modal. Selected date/entity context remains unsupported because the actual request
schema has no context fields; no payload support is claimed or invented. User visual
acceptance remains open.

Milestone boundary verification after the final review: the full web suite passes,
43 files /377 tests, and TypeScript passes. The first full run exposed a legacy
`matchMedia` listener compatibility failure in an existing shell transition test;
the launcher now supports modern and legacy listener APIs. The affected transition
and overlay tests passed before the successful full rerun. Expected jsdom canvas and
Three.js deprecation warnings remain non-failing.
