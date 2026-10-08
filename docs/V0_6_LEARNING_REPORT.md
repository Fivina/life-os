# Life OS V0.6 — Learning

## 1. Release Purpose

V0.6 makes high-stakes exams operational trajectories instead of simple dated events. Learning now answers preparation target, completed work, remaining work, future sustainable capacity, required pace, readiness, risk, infeasibility, and useful study candidates.

## 2. Preconditions

V0.1 State, V0.2 Commitments/Actions, V0.3 Core Planner, V0.4 Daily Control Loop, and V0.5 Fitness are present and passing.

## 3. Repository Audit

The repository already had placeholder Learning models/routes/UI, generic Goal/Trajectory tables, Planner CandidateAction metadata, PlanBlock execution, event/outbox/world revision services, and the Fitness specialist-domain pattern. Learning placeholders were extended instead of duplicated.

## 4. Architecture Reused

Learning reuses domain services, Pydantic route contracts, canonical Actions for planning pool integration, Core Planner scoring, PlanBlock execution lifecycle, events/outbox/world revisions, and Home card patterns.

## 5. Deviations

`learning_study_requirements` is reused as the StudyUnit/Topic table to preserve existing data. User timezone is not yet stored on `UserProfile`; V0.6 uses the existing API/default timezone path, defaulting to `Europe/Berlin`.

## 6. Learning Domain Boundary

Learning owns courses, exams, topics, StudySessions, quality-adjusted preparation, trajectory calculations, candidate generation, summaries, and tool context. Learning does not write PlanBlocks or own scheduling.

## 7. Course Model

`learning_courses` stores user ownership, name, code, description, institution, status, timestamps, and version. The legacy `title` column is preserved for compatibility and mirrored from name.

## 8. Exam Model

`learning_exams` stores course link, title, `exam_at`, legacy `exam_date`, importance, status, target preparation minutes, optional minimum/quality-adjusted target, strategy version, attempts/final-attempt metadata, format, location, notes, timestamps, and version.

## 9. StudyUnit / Topic Model

`learning_study_requirements` now represents topics with exam link, title, order, importance weight, estimated required minutes, simple prerequisite topic, completed minutes, status, timestamps, and version.

## 10. StudySession Model

`learning_study_sessions` stores actual study: course/exam/topic links, optional source Action and PlanBlock, timestamps, raw duration, quality rating, quality multiplier, quality-adjusted minutes, source, notes, idempotency key, and version.

## 11. Academic Execution Truth

StudySession is academic execution truth. A planned Learning block is only a projection until completion creates a StudySession. Manual study can be logged without a PlanBlock.

## 12. Quality-Adjusted Progress

V1 formula: quality 1 = 0.50, 2 = 0.75, 3 or missing = 1.00, 4 = 1.10, 5 = 1.20. `quality_adjusted_minutes = duration_minutes * multiplier`, rounded and bounded to at most 1.2x raw duration. Raw duration remains visible separately.

## 13. Exam Trajectory Model

Trajectory is derived deterministically from Exam, StudySession, Topic, Commitment, and time data. It exposes target, raw completed, quality-adjusted completed, remaining, time remaining, capacity, pace, load ratio, risk, readiness, latest-safe-start, and infeasibility.

## 14. Remaining Work Calculation

`remaining_quality_adjusted_minutes = max(target_quality_adjusted_minutes_or_target_preparation_minutes - quality_adjusted_completed_minutes, 0)`.

## 15. Future Capacity Estimate

For each future day until the exam: weekday base 120 study minutes, weekend base 180. Hard commitment minutes discount capacity by 35%. A 15% sustainability buffer is then applied. Current/exam partial days are prorated. This is an estimate, not scheduling.

## 16. Required Pace

`required_daily_minutes = remaining_quality_adjusted_minutes / ceil(days_remaining)` with a minimum one-day divisor. `required_weekly_hours = required_daily_minutes * 7 / 60`.

## 17. Load Ratio

`load_ratio = remaining_quality_adjusted_minutes / estimated_future_study_capacity`. If capacity is zero and work remains, load ratio is null and the trajectory is infeasible.

## 18. Risk Bands

Risk thresholds: infeasible if remaining exceeds capacity; critical if load ratio >= 0.95; high >= 0.80; moderate >= 0.55; otherwise low. These are preparation-pressure bands, not grade probabilities.

## 19. Preparation Readiness

If topics exist: readiness = 70% preparation progress + 30% weighted topic coverage. If no topics exist: readiness = preparation progress. The result is clamped 0-100 and labeled as preparation readiness.

## 20. Latest-Safe-Start / Acceleration

The algorithm estimates average future daily capacity, computes required preparation days, adds a safety margin of 15% of remaining days bounded 1-7 days, and subtracts that from the exam deadline. If now is later than that point, `behind_safe_pace = true`.

## 21. Infeasibility

If remaining work exceeds estimated sustainable capacity, the response sets `feasible = false`, `risk = infeasible`, and exposes shortfall minutes/hours. The system does not lower the target or invent capacity.

## 22. Topic Coverage

Each topic coverage ratio is `min(1, completed_quality_adjusted_minutes / estimated_required_minutes)`, unless the topic status is explicitly covered/complete/done. Overall coverage is weighted by importance.

## 23. Prerequisites

Topics support one simple prerequisite topic. Self-prerequisites and direct cycles are rejected. Candidate generation picks the first incomplete prerequisite-satisfied topic before dependent topics.

## 24. CandidateAction Generation

Learning generates candidates from active exam trajectories with stable IDs, exam/course/topic metadata, title, duration, commitment level, cognitive load, activation difficulty, trajectory value, urgency, neglect cost, deadline, prerequisite metadata, variant, and decision metadata.

## 25. Duration Variants

V0.6 variants: full 90m, standard 60m, reduced 45m, minimum 25m, activation 10m. Variants reference the same academic trajectory.

## 26. Activation Starters

Activation candidates are generated for non-low-risk trajectories to preserve minimum viable academic progress under friction or low state.

## 27. Cognitive Load / Activation Difficulty

Full/standard study uses higher cognitive load; reduced/minimum/activation variants lower cognitive load and activation difficulty. Unsatisfied prerequisites add activation friction.

## 28. Low-State Transformation

The Core Planner already shortens goal-critical blocks under low state. Learning supplies reduced/minimum/activation variants so low state changes study form before deleting critical academic progress.

## 29. Missed Study / Backlog Firewall

Skipped and missed Learning PlanBlocks do not create StudySessions and do not clone duplicate Actions. Remaining work and pressure change only through time and actual logged sessions.

## 30. Partial Study Semantics

Completing a Learning PlanBlock with actual duration records a StudySession using actual minutes. A 60m plan completed for 35m contributes 35 quality-adjusted minutes at default quality unless separately logged.

## 31. Fitness / Learning Planner Arbitration

Fitness and Learning both publish canonical Actions. The Core Planner alone scores and places blocks, respecting hard commitments, stress, slack, and state.

## 32. Events

Learning emits `learning.course.created`, `learning.course.updated`, `learning.exam.created`, `learning.exam.updated`, `learning.topic.created`, `learning.topic.updated`, and `learning.study_session.completed`.

## 33. Outbox

Learning semantic events use the shared transactional outbox.

## 34. WorldRevision

Learning mutations increment `UserProfile.world_revision` through the shared event service. Reads and failed/stale mutations do not intentionally advance world revision.

## 35. API Surface

Added `/learning/status`, `/context`, `/courses`, `/courses/{id}`, `/exams`, `/exams/{id}`, `/exams/{id}/trajectory`, `/exams/{id}/topics`, `/topics/{id}`, `/study-sessions`, `/candidates`, and `/candidates/sync-actions`.

## 36. Learning Dashboard

The Learning page now shows active exam, target, risk, readiness, remaining work, required pace, future capacity, explicit infeasibility, setup forms, study logging, candidates, and exam list.

## 37. Exam Detail UX

V0.6 uses compact exam cards rather than a separate route. Each card shows course, completed/target hours, readiness, and risk.

## 38. Study Logging UX

The UI logs raw minutes and a neutral 1-5 quality rating. It does not frame lower quality as wasted time.

## 39. Home Integration

Home now has a live Learning card with active exam, readiness, remaining work, required pace, and today’s Learning block presence.

## 40. Today / PlanBlock Integration

Today timeline remains the source for PlanBlocks. Completing a Learning PlanBlock creates one linked StudySession; skipped/missed blocks create none.

## 41. Learning Context / Tool Contracts

Learning exposes bounded context for active exams, trajectories, topic coverage, recent sessions, plan window, and candidates. Safe future tools: `get_learning_status`, `log_study_session`, `create_course`, `create_exam`, `update_exam`, `get_exam_status`.

## 42. Database Migration

Migration `0006_learning_domain` extends existing Learning tables and preserves data. It applies after `0005_fitness_domain`.

## 43. Simulation Scenarios

Automated tests cover healthy/high-pressure/infeasible trajectories, study completion, missed/skipped semantics, partial PlanBlock execution, low state, Fitness conflict, prerequisites, and idempotent session logging.

## 44. Automated Tests

Backend regression: 55 passed. Frontend regression: 31 passed. Typecheck passed. Production build passed.

## 45. Manual Acceptance

Manual scenario created Macroeconomics course/exam, three topics with prerequisites, 40h raw study with mixed quality, candidates, Planner action sync, Fitness conflict, Learning PlanBlock completion, skipped block, low-state plan, infeasible exam, refresh/reload reads, and event/action checks. Result: PASS.

## 46. Known Limitations

Capacity is conservative and approximate. User timezone is not yet a UserProfile field. Topic prerequisites are intentionally simple. There is no syllabus import, spaced repetition, or grade prediction.

## 47. Deliberate Deferrals

Deferred: lecture/PDF ingestion, flashcards, Anki-like scheduling, AI tutor, LMS integrations, learned quality multipliers, personalized study times, embeddings, notifications intelligence, and V0.7 Assistant.

## 48. User Friction Observed

Manual setup requires creating course, exam, topics, and target hours. Quality logging is deliberately low-friction but still a manual step.

## 49. Data Created for V0.7 and V0.9

Assistant may safely query bounded Learning status, exams, trajectories, candidates, topics, and sessions. Personal Learning may later use historical sessions, quality ratings, candidate metadata, topic coverage, and trajectory outcomes without treating AI as academic truth.

## 50. Acceptance Checklist

Course, Exam, target preparation, StudySession, quality-adjusted progress, remaining work, future capacity, required pace, load ratio, risk, readiness, latest safe start, infeasibility, shortfall, strategy version, topics, prerequisites, candidates, duration variants, activation starters, planner arbitration, low-state handling, partial study, missed-study firewall, Home card, semantic events, outbox, world revision, tests, migration, and manual acceptance are complete.

## 51. Release Decision

PASS

## 52. Readiness for V0.7

V0.7 Assistant may safely query Learning status and exam trajectories and may mutate only through bounded Learning tools. It must not write PlanBlocks, execute SQL, edit calendar projections, or become academic truth.
