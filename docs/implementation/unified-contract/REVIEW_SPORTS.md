# Life OS independent review

Reviewed `0d1a12b06d3b27eb7144623eeef2b6d12a18207b` against `f3ef64d`, bounded to the GH-4 next-match/Vault/Calendar paths and CONTRACT_SOURCE PDF pages 55–56.

## Actionable findings

1. **P2 — the next-match card is not guaranteed to be projected and is not compact.**  
   **File/line:** `apps/web/src/features/phengos/phengosCardProjection.ts:161-169`  
   **Reproduction:** Supply two pending proposals, an agenda, a planned workout, two upcoming commitments, shopping, a meal, and one valid future fixture. The fixture has priority 52 outside 48 hours; the final global `.slice(0, 8)` drops it. `PhengosContextCards` later removes the agenda, so the dashboard can still have room while showing no match. When emitted, the fixture is also declared `size: "wide"`.  
   **Criterion:** PDF p.56 requires always projecting the nearest scheduled/confirmed future fixture as one compact card. Reserve the selected fixture across the card cap (or cap other categories separately) and use the compact fixture presentation; add a crowded-dashboard regression test.

2. **P2 — a same-record query refresh can overwrite Calendar navigation.**  
   **File/line:** `apps/web/src/features/calendar/CalendarWorkspace.tsx:150-158`  
   **Reproduction:** Open `/calendar?commitment=<id>`, navigate to Month or another date, then let the canonical commitment query refresh with any changed field/version. Because the effect depends on the whole `requestedCommitment` object, it reselects the record and forces Day view/date again even though the URL target did not change.  
   **Criterion:** GH-4 requires linked-record query changes not to reset user navigation/drafts unnecessarily. Apply the initial deep-link positioning once per requested ID (while still updating displayed canonical details), and test a refreshed same-ID response after manual navigation.

No scoped backend defect was found in the reviewed source/tests: `next=1`, daily upgrade/retry, authoritative empty/failure pointer, TBD kickoff, idempotent reschedule, bounded/no-redirect transport, sanitized failures, nested rollback, selected Vault-only lookup, fixed-provider getter/search path, and tenant-isolated nullable canonical reads are covered by the inspected implementation and targeted mocks.

## Checks performed

- Verified exact detached HEAD: `0d1a12b06d3b27eb7144623eeef2b6d12a18207b`; diff base `f3ef64d`; clean tree; `git diff --check` clean.
- Read the handoff/ledger and only CONTRACT_SOURCE PDF pages 55–56.
- Ran the three permitted suites with the prescribed interpreter/options: **26 passed** in 4.70s (2 unrelated Pydantic deprecation warnings).
- Inspected scoped frontend source/tests only; dependencies are absent, so frontend tests/typecheck were not rerun.

## Explicit gaps / not accepted here

- Shared installation fetch-once remains incomplete.
- Hosted PostgreSQL migrations 0031–0033 and the 0033 Vault function/grants were not executed.
- No live Vault, API-Football/provider, hosted rollback, or browser/frontend runtime verification was performed.
- This review does not mark the wider contract complete; primary owns fixes and acceptance.

Primary correction checkpoint:331e917 (published). Both P2 findings are corrected:
reserved compact fixture card plus crowded-dashboard regression; initial positioning
once per requested ID plus same-ID refresh/new-ID regression.21 focused frontend
tests and typecheck passed. This note records correction evidence, not a second
independent review. See HANDOFF/LEDGER for remaining shared-cache/hosted gates.
