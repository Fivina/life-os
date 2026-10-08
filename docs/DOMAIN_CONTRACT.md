# Domain Planning Contract

Domains own canonical state, deterministic calculations, requirements, constraints, execution interpretation, and narrow AI context. Planner alone owns `Plan` and `PlanBlock` placement; Calendar is the compiled execution surface.

The future conceptual interface is:

```python
class DomainPlanningContract(Protocol):
    name: str
    def get_current_state(db, user) -> dict: ...
    def get_requirements(db, user, horizon_start, horizon_end) -> list[PlanningRequirement]: ...
    def refresh_actions(db, user, horizon_start, horizon_end) -> DomainRefreshResult: ...
    def get_constraints(db, user, horizon_start, horizon_end) -> list[dict]: ...
    def apply_execution_outcome(db, user, block, outcome, actual_minutes, occurred_at): ...
    def get_summary_for_context(db, user) -> dict: ...
    def get_risk_state(db, user) -> dict: ...
```

## Scheduling Boundary

Domains may not directly create, edit, move, or delete `PlanBlock` records. They reconcile shared `Action` variants with stable requirement keys. Core Planner V2 owns scheduling authority.

## Reconciliation

Generated Actions carry domain, requirement key, source entity, generated reason, generation version, optional Goal/Trajectory links, and planning priority. Repeated refresh updates the current variants and archives obsolete requirements without deleting execution history.

## Execution

Calendar outcomes route by `PlanBlock.domain` and Action provenance. Learning writes `StudySession`, Fitness writes `WorkoutSession`, and Home advances `HouseholdTask` recurrence. Partial completion records actual time and Planner debt; skip leaves the domain requirement active.

## Active Domains

- Fitness: programs, workout requirements, actual sets, progression, recovery, and nutrition target contract.
- Learning: courses, exams, deterministic workload/risk, study requirements, and quality-adjusted sessions.
- Home: recurring household state, due requirements, and completion recurrence.
- Goals: derived Trajectories, Milestones, Weekly Focus, and priority signals; it does not own Calendar.
- Kitchen: ingredients, inventory, meals, nutrition logs, preferences, and shopping lists.
