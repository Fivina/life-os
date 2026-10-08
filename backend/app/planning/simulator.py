from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.planning.engine import CorePlannerV03
from app.planning.types import CandidateAction, PlanningContext


class SimCommitment:
    def __init__(self, id: str, title: str, starts_at: datetime, ends_at: datetime, level: str = "hard") -> None:
        self.id = id
        self.title = title
        self.starts_at = starts_at
        self.ends_at = ends_at
        self.level = level


def _context(
    *,
    energy: int = 75,
    mental_state: int = 75,
    actions: list[CandidateAction] | None = None,
    commitments: list[SimCommitment] | None = None,
) -> PlanningContext:
    planning_day = date(2026, 9, 14)
    start = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    end = datetime(2026, 9, 14, 22, 0, tzinfo=UTC)
    return PlanningContext(
        user_id="simulation-user",
        planning_date=planning_day,
        timezone="UTC",
        generated_at=datetime(2026, 9, 14, 7, 30, tzinfo=UTC),
        generated_from_world_revision=103,
        horizon_start=start,
        horizon_end=end,
        energy=energy,
        mental_state=mental_state,
        hard_commitments=commitments
        if commitments is not None
        else [SimCommitment("commitment-university", "University", start + timedelta(hours=3), start + timedelta(hours=8))],
        candidate_actions=actions if actions is not None else normal_actions(),
    )


def normal_actions() -> list[CandidateAction]:
    return [
        CandidateAction(
            source_action_id="study-macro",
            domain="learning",
            title="Macroeconomics study",
            commitment_level="goal_critical",
            estimated_minutes=120,
            minimum_minutes=25,
            maximum_minutes=120,
            deadline=datetime(2026, 9, 17, 18, 0, tzinfo=UTC),
            cognitive_load=72,
            trajectory_value=55,
            neglect_cost=22,
            activation_difficulty=48,
        ),
        CandidateAction(
            source_action_id="groceries",
            domain="kitchen",
            title="Groceries",
            commitment_level="maintenance",
            estimated_minutes=30,
            minimum_minutes=20,
            maximum_minutes=30,
            maintenance_value=32,
            neglect_cost=30,
        ),
        CandidateAction(
            source_action_id="optional-reading",
            domain="learning",
            title="Optional reading",
            commitment_level="optional",
            estimated_minutes=60,
            minimum_minutes=25,
            maximum_minutes=60,
        ),
    ]


def scenario_contexts() -> dict[str, PlanningContext]:
    overloaded = normal_actions() + [
        CandidateAction(
            source_action_id=f"extra-{index}",
            domain="admin",
            title=f"Extra admin {index}",
            commitment_level="optional",
            estimated_minutes=90,
            minimum_minutes=30,
            maximum_minutes=90,
        )
        for index in range(6)
    ]
    maintenance = normal_actions() + [
        CandidateAction(
            source_action_id="deep-optional",
            domain="learning",
            title="Deep optional article",
            commitment_level="optional",
            estimated_minutes=90,
            minimum_minutes=30,
            maximum_minutes=90,
            trajectory_value=5,
        )
    ]
    return {
        "normal_day": _context(),
        "low_state": _context(energy=30, mental_state=35),
        "deadline_pressure": _context(
            energy=60,
            mental_state=65,
            actions=[
                CandidateAction(
                    source_action_id="exam-study",
                    domain="learning",
                    title="Exam study",
                    commitment_level="goal_critical",
                    estimated_minutes=120,
                    minimum_minutes=25,
                    maximum_minutes=120,
                    deadline=datetime(2026, 9, 14, 23, 0, tzinfo=UTC),
                    trajectory_value=55,
                    neglect_cost=25,
                ),
                *normal_actions()[1:],
            ],
        ),
        "maintenance_neglect": _context(actions=maintenance),
        "overloaded_day": _context(actions=overloaded),
        "no_flexible_work": _context(actions=[]),
        "determinism": _context(),
    }


def run_simulation(context: PlanningContext | None = None) -> dict[str, Any]:
    result = CorePlannerV03().run(context or _context())
    return asdict(result)


def run_all_scenarios() -> dict[str, Any]:
    planner = CorePlannerV03()
    return {name: asdict(planner.run(context)) for name, context in scenario_contexts().items()}
