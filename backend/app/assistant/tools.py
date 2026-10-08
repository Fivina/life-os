from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Literal

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.schemas import ActionCreate, ActionRead
from app.actions.service import create_action, list_actions
from app.assistant.schemas import AssistantExplanation, AssistantMutationResult, AssistantRole
from app.commitments.schemas import CommitmentCreate, CommitmentRead
from app.commitments.service import create_commitment, list_commitments
from app.database.models import Exam, Plan, PlanBlock, UserProfile
from app.ai.gateway import AIGateway
from app.core.config import get_settings
from app.domains.fitness import service as fitness_service
from app.domains.fitness.schemas import BodyMeasurementCreate, WorkoutCompleteRequest, WorkoutSetCreate, WorkoutStartRequest
from app.domains.finance import service as finance_service
from app.domains.finance.schemas import BudgetCreate, ImportRowUpdate
from app.domains.kitchen import service as kitchen_service
from app.domains.kitchen import receipts as receipt_service
from app.domains.kitchen.schemas import MealCompleteRequest, MealManualCreate, MealPlanCompleteRequest, MealSelectionCreate, RecommendationRequest, ShoppingPurchaseCreate
from app.domains.learning import service as learning_service
from app.domains.learning.schemas import CourseCreate, ExamCreate, ExamUpdate, StudySessionCreate
from app.domains.home import service as home_service
from app.domains.home.schemas import HouseholdTaskCreate
from app.domains.goals import service as goals_service
from app.personal_model import service as personal_model_service
from app.memory.embeddings import EmbeddingService
from app.memory.retrieval import MemoryRetrievalService
from app.memory.schemas import MemoryCreate, MemoryUpdate
from app.memory.service import MemoryService
from app.planning.control_loop import evaluate_day, manual_replan
from app.planning.service import get_current_plan, plan_to_read
from app.planning.rolling import RollingPlanner
from app.state.schemas import StateObservationCreate
from app.state.service import create_observations, latest_check_in, latest_state
from app.strategy.schemas import ProposalModificationRequest
from app.strategy.service import PlanProposalService

ToolKind = Literal["READ_ONLY", "MUTATION"]
ConfirmationPolicy = Literal["never", "always", "conditional"]


class AssistantToolError(Exception):
    def __init__(self, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class EmptyArgs(BaseModel):
    pass


class PlanExplanationArgs(BaseModel):
    query: str | None = None
    plan_id: str | None = None
    block_id: str | None = None


class ReplanArgs(BaseModel):
    reason: str = "ASSISTANT_REQUESTED"
    now: datetime | None = None


class MemorySearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    domain: str | None = Field(default=None, max_length=60)
    memory_type: str | None = Field(default=None, max_length=60)
    limit: int = Field(default=6, ge=1, le=20)


class RememberArgs(BaseModel):
    content: str = Field(min_length=2, max_length=1200)
    memory_type: str = "preference"
    domain: str = Field(default="general", min_length=1, max_length=60)
    polarity: int = Field(default=0, ge=-1, le=1)
    importance: float = Field(default=0.65, ge=0, le=1)
    pinned: bool = False


class MemoryIdArgs(BaseModel):
    memory_id: str


class CorrectMemoryArgs(MemoryIdArgs):
    content: str = Field(min_length=2, max_length=1200)
    memory_type: str | None = None
    domain: str | None = Field(default=None, max_length=60)
    polarity: int | None = Field(default=None, ge=-1, le=1)
    importance: float | None = Field(default=None, ge=0, le=1)


class LearningStatusArgs(BaseModel):
    exam_hint: str | None = None


class ExamStatusArgs(BaseModel):
    exam_id: str | None = None
    exam_hint: str | None = None


class StudyLogArgs(BaseModel):
    exam_id: str | None = None
    exam_hint: str | None = None
    topic_id: str | None = None
    duration_minutes: int = Field(gt=0)
    quality_rating: int | None = Field(default=None, ge=1, le=5)
    occurred_at: datetime | None = None
    notes: str | None = None


class KitchenRecommendationArgs(RecommendationRequest):
    pass


class FinanceImportStatusArgs(BaseModel):
    batch_id: str


class FinanceCategorizeArgs(BaseModel):
    row_id: str
    category: str = Field(min_length=1, max_length=120)


class ReceiptIdArgs(BaseModel):
    receipt_id: str


class MealPlanCompleteAssistantArgs(MealPlanCompleteRequest):
    plan_id: str


class ShoppingPurchaseAssistantArgs(ShoppingPurchaseCreate):
    item_id: str


class HouseholdTaskIdArgs(BaseModel):
    task_id: str


class PlanProposalIdArgs(BaseModel):
    proposal_id: str


class PlanProposalModifyArgs(ProposalModificationRequest):
    proposal_id: str


def _home_status(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    return ToolResult(message="Household state loaded.", result=_json_model(home_service.overview(db, user)), entity_type="household_overview")


def _goals_status(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    return ToolResult(message="Goals and trajectories loaded.", result=_json_model(goals_service.overview(db, user)), entity_type="goals_overview")


def _create_household_task(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    task = home_service.create_task(db, user, HouseholdTaskCreate.model_validate(args.model_dump()))
    home_service.refresh_actions(db, user, horizon_start=datetime.now(UTC).date(), horizon_end=datetime.now(UTC).date())
    return ToolResult(message=f"Created recurring household task: {task.title}.", result=_json_model(task), entity_type="household_task", entity_id=task.id)


def _complete_household_task(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    task = home_service.complete_task(db, user, args.task_id)
    return ToolResult(message=f"Completed {task.title}; the next due date was calculated.", result=_json_model(task), entity_type="household_task", entity_id=task.id)


def _active_plan_proposals(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    service = PlanProposalService(get_settings())
    proposals = [service.to_read(row).model_dump(mode="json") for row in service.list_active(db, user, limit=5)]
    return ToolResult(message=f"Loaded {len(proposals)} active plan proposal(s).", result={"proposals": proposals})


def _accept_plan_proposal(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    service = PlanProposalService(get_settings())
    try:
        row = service.accept(db, user, args.proposal_id)
    except (LookupError, ValueError) as exc:
        raise AssistantToolError("proposal_rejected", str(exc)) from exc
    return ToolResult(
        message="The proposal was applied through the Planner.",
        result=service.to_read(row).model_dump(mode="json"),
        entity_type="plan_proposal",
        entity_id=row.id,
    )


def _modify_plan_proposal(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    service = PlanProposalService(get_settings())
    request = ProposalModificationRequest.model_validate(args.model_dump(exclude={"proposal_id"}))
    try:
        row = service.modify(db, user, args.proposal_id, request)
    except (LookupError, ValueError) as exc:
        raise AssistantToolError("proposal_rejected", str(exc)) from exc
    return ToolResult(
        message="The requested change was re-simulated as a new proposal.",
        result=service.to_read(row).model_dump(mode="json"),
        entity_type="plan_proposal",
        entity_id=row.id,
    )


def _reject_plan_proposal(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    service = PlanProposalService(get_settings())
    try:
        row = service.reject(db, user, args.proposal_id)
    except (LookupError, ValueError) as exc:
        raise AssistantToolError("proposal_rejected", str(exc)) from exc
    return ToolResult(
        message="The proposal was rejected. Your current plan was not changed.",
        result=service.to_read(row).model_dump(mode="json"),
        entity_type="plan_proposal",
        entity_id=row.id,
    )


class ToolResult(BaseModel):
    message: str
    result: dict[str, Any] = Field(default_factory=dict)
    entity_type: str | None = None
    entity_id: str | None = None
    explanation: AssistantExplanation | None = None


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    args_schema: type[BaseModel]
    kind: ToolKind
    allowed_roles: set[AssistantRole]
    confirmation_policy: ConfirmationPolicy
    handler: Callable[[Session, UserProfile, BaseModel, str | None], ToolResult]

    def validate_args(self, raw: dict[str, Any]) -> BaseModel:
        return self.args_schema.model_validate(raw or {})


def _json_model(value: Any) -> dict[str, Any]:
    return jsonable_encoder(value)


def _current_state(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    values = latest_state(db, user)
    check_in = latest_check_in(values)
    return ToolResult(
        message="Current state loaded.",
        result={"check_in": check_in.model_dump(mode="json") if check_in else None, "world_revision": user.world_revision},
    )


def _today_summary(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    state = _current_state(db, user, args, idempotency_key).result
    plan = get_current_plan(db, user)
    actions = list_actions(db, user, planning_pool=True)
    return ToolResult(
        message="Here is the current Life OS summary.",
        result={
            "state": state,
            "current_plan": plan_to_read(plan, user.world_revision).model_dump(mode="json") if plan else None,
            "planning_pool_count": len(actions),
        },
    )


def _current_plan(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    plan = get_current_plan(db, user)
    return ToolResult(
        message="Current plan loaded." if plan else "No current plan exists for today.",
        result={"plan": plan_to_read(plan, user.world_revision).model_dump(mode="json") if plan else None},
        entity_type="plan" if plan else None,
        entity_id=plan.id if plan else None,
    )


def _planner_overload(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    plan = get_current_plan(db, user)
    payload = {
        "status": plan.overload_status if plan else "no_plan",
        "shortfall_minutes": plan.shortfall_minutes if plan else 0,
        "details": plan.overload_json if plan else {},
    }
    return ToolResult(message=f"Planner load status: {payload['status']}.", result=payload, entity_type="plan" if plan else None, entity_id=plan.id if plan else None)


def _planner_horizon(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    planner = RollingPlanner()
    status_row = planner.refresh(db, user)
    rows = planner.allocations(db, user, start_day=status_row.horizon_start, end_day=status_row.horizon_end)
    return ToolResult(
        message=f"Rolling allocation is {status_row.status} with {status_row.shortfall_minutes} minutes shortfall.",
        result={
            "status": status_row.status,
            "required_minutes": status_row.required_minutes,
            "available_minutes": status_row.available_minutes,
            "shortfall_minutes": status_row.shortfall_minutes,
            "allocations": [{"date": row.planning_date.isoformat(), "domain": row.domain, "action_group_id": row.action_group_id, "allocated_minutes": row.allocated_minutes, "risk_status": row.risk_status} for row in rows],
        },
    )


def _commitments(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    rows = list_commitments(db, user, status_filter="active")
    return ToolResult(message="Commitments loaded.", result={"commitments": [CommitmentRead.model_validate(row).model_dump(mode="json") for row in rows[:20]]})


def _planning_pool(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    actions = list_actions(db, user, planning_pool=True)
    return ToolResult(message="Planning pool loaded.", result={"actions": [ActionRead.model_validate(item).model_dump(mode="json") for item in actions[:20]]})


def _fitness_status(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    status_read = fitness_service.status_summary(db, user)
    next_name = status_read.next_workout.name if status_read.next_workout else "No next workout configured"
    return ToolResult(message=f"Fitness status loaded. Next workout: {next_name}.", result=status_read.model_dump(mode="json"))


def _learning_status(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    status_read = learning_service.status_summary(db, user)
    active = status_read.active_exam
    if active and active.trajectory:
        message = (
            f"{active.title}: readiness {active.trajectory.readiness_score}, "
            f"risk {active.trajectory.risk}, remaining {active.trajectory.remaining_quality_adjusted_minutes} quality-adjusted minutes."
        )
    else:
        message = "Learning status loaded. No active exam is currently configured."
    return ToolResult(message=message, result=status_read.model_dump(mode="json"), entity_type="exam" if active else None, entity_id=active.id if active else None)


def _kitchen_status(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    status_read = kitchen_service.status_summary(db, user)
    top = status_read.top_recommendation.recipe.name if status_read.top_recommendation else "No inventory-only recommendation yet"
    return ToolResult(message=f"Kitchen status loaded. Top no-shopping option: {top}.", result=status_read.model_dump(mode="json"))


def _kitchen_recommendations(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    data = args if isinstance(args, RecommendationRequest) else RecommendationRequest.model_validate(args.model_dump(exclude_none=True))
    recs = kitchen_service.recommendations(db, user, data)
    if recs:
        message = f"Top Kitchen recommendation: {recs[0].recipe.name} ({recs[0].score})."
    elif data.no_shopping:
        message = "No no-shopping meal fits current inventory yet."
    else:
        message = "No meal recommendations are available yet."
    return ToolResult(message=message, result={"recommendations": [item.model_dump(mode="json") for item in recs]})


def _shopping_needs(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    needs = kitchen_service.list_shopping_needs(db, user)
    return ToolResult(message=f"{len(needs)} active Kitchen shopping need(s) loaded.", result={"shopping_needs": [item.model_dump(mode="json") for item in needs]})


def _finance_overview(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    value = finance_service.overview(db, user)
    return ToolResult(message="Finance overview loaded from recorded data.", result=value.model_dump(mode="json"), entity_type="finance_overview")


def _finance_safe_to_spend(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    value = finance_service.safe_to_spend(db, user)
    return ToolResult(message="Safe-to-spend estimate loaded with its assumptions.", result=value.model_dump(mode="json"), entity_type="safe_to_spend")


def _finance_import_status(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    value = finance_service.get_import(db, user, args.batch_id)
    return ToolResult(message=f"Import status: {value.status}.", result=value.model_dump(mode="json"), entity_type="finance_import_batch", entity_id=value.id)


def _finance_budget(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    value = finance_service.create_budget(db, user, BudgetCreate.model_validate(args.model_dump()))
    return ToolResult(message=f"Budget saved: {value.name}.", result=value.model_dump(mode="json"), entity_type="finance_budget", entity_id=value.id)


def _finance_categorize(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    value = finance_service.update_import_row(db, user, args.row_id, ImportRowUpdate(category=args.category, accept=True))
    return ToolResult(message=f"Import row categorized as {args.category}.", result=value.model_dump(mode="json"), entity_type="finance_import_batch", entity_id=value.id)


def _select_meal(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    value = kitchen_service.select_meal(db, user, MealSelectionCreate.model_validate(args.model_dump()))
    return ToolResult(message=f"Meal selected: {value.recipe.name}.", result=value.model_dump(mode="json"), entity_type="meal_plan", entity_id=value.id)


def _complete_meal_plan(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    payload = MealPlanCompleteRequest.model_validate(args.model_dump(exclude={"plan_id"}))
    value = kitchen_service.complete_meal_plan(db, user, args.plan_id, payload)
    return ToolResult(message=f"Meal completed: {value.recipe.name}.", result=value.model_dump(mode="json"), entity_type="meal_plan", entity_id=value.id)


def _purchase_shopping_item(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    payload = ShoppingPurchaseCreate.model_validate(args.model_dump(exclude={"item_id"}))
    value = kitchen_service.mark_shopping_item_purchased(db, user, args.item_id, payload)
    return ToolResult(message=f"Marked {value.ingredient_name} purchased.", result=value.model_dump(mode="json"), entity_type="shopping_need_item", entity_id=value.id)


def _receipt_review(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    value = receipt_service.get_import(db, user, args.receipt_id)
    return ToolResult(message=f"Receipt status: {value.status}; {value.review_count} item(s) need review.", result=value.model_dump(mode="json"), entity_type="receipt_import", entity_id=value.id)


def _receipt_confirm(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    value = receipt_service.confirm_import(db, user, args.receipt_id)
    return ToolResult(message="Receipt confirmed and reconciled with Kitchen and Finance.", result=value.model_dump(mode="json"), entity_type="receipt_import", entity_id=value.id)


def _personal_model_summary(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    summary = personal_model_service.summary(db, user)
    return ToolResult(
        message=f"Personal learning status: {summary.status}; evidence {summary.evidence_n}; active models {summary.active_model_count}.",
        result=summary.model_dump(mode="json"),
    )


def _memory_services() -> tuple[MemoryService, MemoryRetrievalService]:
    settings = get_settings()
    embeddings = EmbeddingService(settings, AIGateway(settings))
    return MemoryService(embeddings), MemoryRetrievalService(settings, embeddings)


def _memory_search(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    data = args if isinstance(args, MemorySearchArgs) else MemorySearchArgs.model_validate(args.model_dump())
    _, retrieval = _memory_services()
    results = retrieval.search_memories(
        db,
        user,
        data.query,
        domain=data.domain,
        memory_types=[data.memory_type] if data.memory_type else None,
        limit=data.limit,
        request_id=idempotency_key,
    )
    return ToolResult(
        message=f"{len(results)} relevant memory item(s) loaded.",
        result={"memories": [item.model_dump(mode="json") for item in results]},
    )


def _remember(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    data = args if isinstance(args, RememberArgs) else RememberArgs.model_validate(args.model_dump())
    memories, _ = _memory_services()
    memory = memories.create_explicit(db, user, MemoryCreate.model_validate(data.model_dump()), request_id=idempotency_key)
    return ToolResult(
        message="Memory saved as user-confirmed personal memory.",
        result=memory.model_dump(mode="json"),
        entity_type="memory",
        entity_id=memory.id,
    )


def _correct_memory(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    data = args if isinstance(args, CorrectMemoryArgs) else CorrectMemoryArgs.model_validate(args.model_dump())
    memories, _ = _memory_services()
    current = memories.get_model(db, user, data.memory_id)
    payload = MemoryUpdate.model_validate(data.model_dump(exclude={"memory_id"}) | {"expected_version": current.version})
    memory = memories.update(db, user, data.memory_id, payload, request_id=idempotency_key)
    return ToolResult(
        message="Memory corrected; the previous version remains auditable.",
        result=memory.model_dump(mode="json"),
        entity_type="memory",
        entity_id=memory.id,
    )


def _pin_memory(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    data = args if isinstance(args, MemoryIdArgs) else MemoryIdArgs.model_validate(args.model_dump())
    memories, _ = _memory_services()
    memory = memories.pin(db, user, data.memory_id, True)
    return ToolResult(message="Memory pinned.", result=memory.model_dump(mode="json"), entity_type="memory", entity_id=memory.id)


def _unpin_memory(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    data = args if isinstance(args, MemoryIdArgs) else MemoryIdArgs.model_validate(args.model_dump())
    memories, _ = _memory_services()
    memory = memories.pin(db, user, data.memory_id, False)
    return ToolResult(message="Memory unpinned.", result=memory.model_dump(mode="json"), entity_type="memory", entity_id=memory.id)


def _forget_memory(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    data = args if isinstance(args, MemoryIdArgs) else MemoryIdArgs.model_validate(args.model_dump())
    memories, _ = _memory_services()
    memory = memories.forget(db, user, data.memory_id)
    return ToolResult(message="Memory forgotten and its existing sources suppressed.", result=memory.model_dump(mode="json"), entity_type="memory", entity_id=memory.id)


def _explain_memory(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    data = args if isinstance(args, MemoryIdArgs) else MemoryIdArgs.model_validate(args.model_dump())
    memories, _ = _memory_services()
    detail = memories.detail(db, user, data.memory_id)
    evidence = [
        {
            "source_type": item.source_type,
            "evidence_kind": item.evidence_kind,
            "direction": item.direction,
            "observed_at": item.observed_at.isoformat(),
            "excerpt": item.excerpt,
        }
        for item in detail.evidence
    ]
    summary = f"Life OS holds this as {detail.status} {detail.memory_type} memory with {len(evidence)} evidence record(s)."
    return ToolResult(
        message=summary,
        result={"memory": detail.model_dump(mode="json"), "why": evidence},
        entity_type="memory",
        entity_id=detail.id,
        explanation=AssistantExplanation(title=detail.content, factors=evidence, summary=summary),
    )


def _latest_current_plan(db: Session, user: UserProfile) -> Plan | None:
    return db.scalar(
        select(Plan)
        .where(Plan.user_id == user.id, Plan.status == "current")
        .order_by(Plan.generated_at.desc(), Plan.created_at.desc())
        .limit(1)
    )


def _find_exam(db: Session, user: UserProfile, *, exam_id: str | None = None, hint: str | None = None) -> Exam:
    query = select(Exam).where(Exam.user_id == user.id)
    if exam_id:
        query = query.where(Exam.id == exam_id)
    exams = list(db.scalars(query.order_by(Exam.exam_at.asc().nulls_last(), Exam.exam_date.asc().nulls_last())).all())
    if exam_id and exams:
        return exams[0]
    if hint:
        hint_lower = hint.lower()
        for exam in exams:
            if hint_lower in exam.title.lower():
                return exam
    if len(exams) == 1:
        return exams[0]
    raise AssistantToolError("exam_required", "I need to know which exam this refers to before I can use the Learning service.")


def _exam_status(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    data = args if isinstance(args, ExamStatusArgs) else ExamStatusArgs()
    exam = _find_exam(db, user, exam_id=data.exam_id, hint=data.exam_hint)
    read = learning_service.exam_to_read(db, user, exam)
    return ToolResult(message=f"Exam status loaded for {exam.title}.", result=read.model_dump(mode="json"), entity_type="exam", entity_id=exam.id)


def _report_state(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    payload = StateObservationCreate.model_validate(args.model_dump(exclude_none=True))
    observations = create_observations(db, user, payload)
    if not observations:
        raise AssistantToolError("state_values_required", "State report needs at least one numeric value.")
    control = evaluate_day(db, user, now=payload.observed_at, trigger_reason="assistant_state_report")
    return ToolResult(
        message=f"State recorded. Control loop status: {control['control_status']}.",
        result={"observation_ids": [item.id for item in observations], "control": _json_model(control), "world_revision": user.world_revision},
        entity_type="state_observation_batch",
        entity_id=observations[0].id,
    )


def _create_commitment(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    payload = CommitmentCreate.model_validate(args.model_dump(exclude_none=True))
    commitment = create_commitment(db, user, payload)
    return ToolResult(
        message=f"Commitment created: {commitment.title}.",
        result=CommitmentRead.model_validate(commitment).model_dump(mode="json") | {"world_revision": user.world_revision},
        entity_type="commitment",
        entity_id=commitment.id,
    )


def _add_intention(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    payload = ActionCreate.model_validate(args.model_dump(exclude_none=True))
    action = create_action(db, user, payload)
    return ToolResult(
        message=f"Intention added to the planning pool: {action.title}.",
        result=ActionRead.model_validate(action).model_dump(mode="json") | {"world_revision": user.world_revision},
        entity_type="action",
        entity_id=action.id,
    )


def _request_replan(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    data = args if isinstance(args, ReplanArgs) else ReplanArgs()
    result = manual_replan(db, user, reason=data.reason, now=data.now)
    return ToolResult(
        message=f"Replan result: {result['control_status']}.",
        result=_json_model(result) | {"world_revision": user.world_revision},
        entity_type="plan" if result.get("plan") else None,
        entity_id=result["plan"].id if result.get("plan") and hasattr(result["plan"], "id") else None,
    )


def _study_session(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    data = args if isinstance(args, StudyLogArgs) else StudyLogArgs.model_validate(args.model_dump())
    exam = _find_exam(db, user, exam_id=data.exam_id, hint=data.exam_hint)
    payload = StudySessionCreate(
        exam_id=exam.id,
        topic_id=data.topic_id,
        occurred_at=data.occurred_at,
        duration_minutes=data.duration_minutes,
        quality_rating=data.quality_rating,
        source="assistant_confirmed",
        notes=data.notes,
    )
    session = learning_service.log_study_session(db, user, payload, idempotency_key=idempotency_key)
    return ToolResult(
        message=f"Study session logged for {exam.title}.",
        result={"study_session": session.id, "duration_minutes": session.duration_minutes, "quality_adjusted_minutes": session.quality_adjusted_minutes, "world_revision": user.world_revision},
        entity_type="study_session",
        entity_id=session.id,
    )


def _log_manual_meal(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    meal = kitchen_service.log_manual_meal(db, user, MealManualCreate.model_validate(args.model_dump(exclude_none=True)))
    return ToolResult(
        message=f"Meal logged: {meal.name_snapshot}.",
        result=meal.model_dump(mode="json") | {"world_revision": user.world_revision},
        entity_type="meal_history",
        entity_id=meal.id,
    )


def _create_course(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    course = learning_service.create_course(db, user, CourseCreate.model_validate(args.model_dump(exclude_none=True)))
    return ToolResult(message=f"Course created: {course.name}.", result={"course_id": course.id, "world_revision": user.world_revision}, entity_type="course", entity_id=course.id)


def _create_exam(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    exam = learning_service.create_exam(db, user, ExamCreate.model_validate(args.model_dump(exclude_none=True)))
    return ToolResult(message=f"Exam created: {exam.title}.", result={"exam_id": exam.id, "world_revision": user.world_revision}, entity_type="exam", entity_id=exam.id)


def _update_exam(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    raw = args.model_dump(exclude_none=True)
    exam_id = raw.pop("exam_id", None)
    if not exam_id:
        raise AssistantToolError("exam_required", "Exam update requires an exam id.")
    exam = learning_service.update_exam(db, user, exam_id, ExamUpdate.model_validate(raw))
    return ToolResult(message=f"Exam updated: {exam.title}.", result={"exam_id": exam.id, "world_revision": user.world_revision}, entity_type="exam", entity_id=exam.id)


def _start_workout(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    session = fitness_service.start_workout(db, user, WorkoutStartRequest.model_validate(args.model_dump(exclude_none=True)))
    return ToolResult(message="Workout started.", result={"session_id": session.id, "world_revision": user.world_revision}, entity_type="workout_session", entity_id=session.id)


def _record_workout_set(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    raw = args.model_dump(exclude_none=True)
    session_id = raw.pop("session_id", None)
    if not session_id:
        raise AssistantToolError("workout_session_required", "Workout set logging requires an active session id.")
    item = fitness_service.log_set(db, user, session_id, WorkoutSetCreate.model_validate(raw), idempotency_key=idempotency_key)
    return ToolResult(message="Workout set recorded.", result={"set_id": item.id, "world_revision": user.world_revision}, entity_type="exercise_set", entity_id=item.id)


def _complete_workout(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    raw = args.model_dump(exclude_none=True)
    session_id = raw.pop("session_id", None)
    if not session_id:
        raise AssistantToolError("workout_session_required", "Workout completion requires a session id.")
    session = fitness_service.complete_workout(db, user, session_id, WorkoutCompleteRequest.model_validate(raw))
    return ToolResult(message="Workout completed.", result={"session_id": session.id, "world_revision": user.world_revision}, entity_type="workout_session", entity_id=session.id)


def _complete_recipe_meal(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    raw = args.model_dump(exclude_none=True)
    recipe_id = raw.pop("recipe_id", None)
    if not recipe_id:
        raise AssistantToolError("recipe_required", "Recipe completion requires a recipe id.")
    meal = kitchen_service.complete_recipe_meal(db, user, recipe_id, MealCompleteRequest.model_validate(raw))
    return ToolResult(
        message=f"Recipe meal completed: {meal.name_snapshot}.",
        result=meal.model_dump(mode="json") | {"world_revision": user.world_revision},
        entity_type="meal_history",
        entity_id=meal.id,
    )


def _body_measurement(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    measurement = fitness_service.add_body_measurement(db, user, BodyMeasurementCreate.model_validate(args.model_dump(exclude_none=True)))
    return ToolResult(message="Body measurement recorded.", result={"measurement_id": measurement.id, "world_revision": user.world_revision}, entity_type="body_measurement", entity_id=measurement.id)


def _plan_explanation(db: Session, user: UserProfile, args: BaseModel, idempotency_key: str | None) -> ToolResult:
    data = args if isinstance(args, PlanExplanationArgs) else PlanExplanationArgs()
    plan = db.get(Plan, data.plan_id) if data.plan_id else (get_current_plan(db, user) or _latest_current_plan(db, user))
    if plan is None or plan.user_id != user.id:
        raise AssistantToolError("plan_not_found", "No current plan is available to explain.", status.HTTP_404_NOT_FOUND)
    block = None
    if data.block_id:
        block = db.get(PlanBlock, data.block_id)
        if block is not None and (block.user_id != user.id or block.plan_id != plan.id):
            block = None
    if block is None and data.query:
        terms = [term for term in data.query.lower().replace("?", " ").split() if len(term) >= 4]
        blocks = sorted(plan.blocks, key=lambda item: item.starts_at)
        block = next((item for item in blocks if any(term in item.title.lower() for term in terms)), None)
    if block is None and plan.blocks:
        block = sorted(plan.blocks, key=lambda item: item.starts_at)[0]
    factors = []
    if block is not None and isinstance(block.decision_factors, dict):
        factors = block.decision_factors.get("items", [])[:6]
    if not factors and isinstance(plan.decision_factors, dict):
        factors = plan.decision_factors.get("items", [])[:6]
    title = block.title if block is not None else "Current plan"
    when = f" at {block.starts_at.strftime('%H:%M')}" if block is not None else ""
    notes = [item.get("notes") for item in factors if isinstance(item, dict) and item.get("notes")]
    summary = f"{title}{when} was selected by the planner from stored decision factors."
    if notes:
        summary += f" Key factor: {notes[0]}"
    explanation = AssistantExplanation(title=title, factors=factors, summary=summary)
    return ToolResult(message=summary, result={"plan_id": plan.id, "block_id": block.id if block else None}, entity_type="plan_block" if block else "plan", entity_id=block.id if block else plan.id, explanation=explanation)


class WorkoutSetAssistantArgs(WorkoutSetCreate):
    session_id: str


class WorkoutCompleteAssistantArgs(WorkoutCompleteRequest):
    session_id: str


class ExamUpdateAssistantArgs(ExamUpdate):
    exam_id: str


class RecipeMealCompleteAssistantArgs(MealCompleteRequest):
    recipe_id: str


class ToolRegistry:
    def __init__(self) -> None:
        roles_all: set[AssistantRole] = {"GENERAL_ASSISTANT", "FITNESS_COACH", "LEARNING_COACH", "HOME_MANAGER", "CHEF", "FINANCE_ADVISOR"}
        roles_general: set[AssistantRole] = {"GENERAL_ASSISTANT"}
        roles_fitness: set[AssistantRole] = {"GENERAL_ASSISTANT", "FITNESS_COACH"}
        roles_learning: set[AssistantRole] = {"GENERAL_ASSISTANT", "LEARNING_COACH"}
        roles_kitchen: set[AssistantRole] = {"GENERAL_ASSISTANT", "CHEF"}
        roles_home: set[AssistantRole] = {"GENERAL_ASSISTANT", "HOME_MANAGER"}
        roles_finance: set[AssistantRole] = {"FINANCE_ADVISOR"}
        self.tools: dict[str, ToolDefinition] = {}
        self._register("get_today_summary", "Read bounded current Life OS summary.", EmptyArgs, "READ_ONLY", roles_general, "never", _today_summary)
        self._register("get_current_state", "Read latest state values.", EmptyArgs, "READ_ONLY", roles_all, "never", _current_state)
        self._register("get_current_plan", "Read current plan.", EmptyArgs, "READ_ONLY", roles_all, "never", _current_plan)
        self._register("get_planner_overload", "Read deterministic overload and shortfall state.", EmptyArgs, "READ_ONLY", roles_general, "never", _planner_overload)
        self._register("get_horizon_allocations", "Read deterministic rolling allocations.", EmptyArgs, "READ_ONLY", roles_general, "never", _planner_horizon)
        self._register("get_plan_block_explanation", "Explain a plan block using stored DecisionFactors.", PlanExplanationArgs, "READ_ONLY", roles_all, "never", _plan_explanation)
        self._register("get_active_plan_proposals", "Read active PlanProposals and their stored effects and trade-offs.", EmptyArgs, "READ_ONLY", roles_general, "never", _active_plan_proposals)
        self._register("accept_plan_proposal", "Apply one existing PlanProposal through the Planner authority path.", PlanProposalIdArgs, "MUTATION", roles_general, "always", _accept_plan_proposal)
        self._register("modify_plan_proposal", "Re-simulate one existing PlanProposal with explicit user constraints.", PlanProposalModifyArgs, "MUTATION", roles_general, "always", _modify_plan_proposal)
        self._register("reject_plan_proposal", "Reject one existing PlanProposal without changing the current plan.", PlanProposalIdArgs, "MUTATION", roles_general, "always", _reject_plan_proposal)
        self._register("get_commitments", "Read active commitments.", EmptyArgs, "READ_ONLY", roles_general, "never", _commitments)
        self._register("get_planning_pool_summary", "Read planning pool actions.", EmptyArgs, "READ_ONLY", roles_general, "never", _planning_pool)
        self._register("get_fitness_status", "Read V0.5 fitness status.", EmptyArgs, "READ_ONLY", roles_fitness, "never", _fitness_status)
        self._register("get_learning_status", "Read V0.6 learning status.", LearningStatusArgs, "READ_ONLY", roles_learning, "never", _learning_status)
        self._register("get_home_status", "Read due, upcoming, and recently completed household tasks.", EmptyArgs, "READ_ONLY", roles_home, "never", _home_status)
        self._register("get_goals_status", "Read active goals, derived trajectories, milestones, and weekly focus.", EmptyArgs, "READ_ONLY", roles_general, "never", _goals_status)
        self._register("get_exam_status", "Read one exam and trajectory.", ExamStatusArgs, "READ_ONLY", roles_learning, "never", _exam_status)
        self._register("get_kitchen_status", "Read V0.8 kitchen status.", EmptyArgs, "READ_ONLY", roles_kitchen, "never", _kitchen_status)
        self._register("get_kitchen_recommendations", "Read deterministic Kitchen meal recommendations.", KitchenRecommendationArgs, "READ_ONLY", roles_kitchen, "never", _kitchen_recommendations)
        self._register("get_shopping_needs", "Read active Kitchen shopping needs.", EmptyArgs, "READ_ONLY", roles_kitchen, "never", _shopping_needs)
        self._register("select_meal", "Select a recommendation and create a canonical meal plan with dependent shopping and cooking actions.", MealSelectionCreate, "MUTATION", roles_kitchen, "always", _select_meal)
        self._register("complete_meal_plan", "Complete a selected meal and record inventory use, feedback, and cooking competency evidence.", MealPlanCompleteAssistantArgs, "MUTATION", roles_kitchen, "always", _complete_meal_plan)
        self._register("mark_shopping_purchased", "Mark one canonical shopping item purchased and optionally add it to inventory.", ShoppingPurchaseAssistantArgs, "MUTATION", roles_kitchen, "always", _purchase_shopping_item)
        self._register("receipt_get_review", "Read one receipt import and its bounded review state.", ReceiptIdArgs, "READ_ONLY", roles_kitchen, "never", _receipt_review)
        self._register("receipt_confirm", "Confirm a fully reviewed receipt and reconcile Kitchen, shopping, and Finance.", ReceiptIdArgs, "MUTATION", roles_kitchen, "always", _receipt_confirm)
        self._register("finance_get_overview", "Read bounded monthly totals, budgets, recurring expenses, recent transactions, and savings goals.", EmptyArgs, "READ_ONLY", roles_finance, "never", _finance_overview)
        self._register("finance_get_safe_to_spend", "Read a deterministic safe-to-spend estimate and its assumptions.", EmptyArgs, "READ_ONLY", roles_finance, "never", _finance_safe_to_spend)
        self._register("finance_import_status", "Read the review and confirmation status of one CSV import.", FinanceImportStatusArgs, "READ_ONLY", roles_finance, "never", _finance_import_status)
        self._register("finance_save_budget", "Create or update a monthly budget.", BudgetCreate, "MUTATION", roles_finance, "always", _finance_budget)
        self._register("finance_categorize_import_row", "Categorize and accept one ambiguous CSV import row.", FinanceCategorizeArgs, "MUTATION", roles_finance, "always", _finance_categorize)
        self._register("get_personal_model_summary", "Read Personal Learning diagnostic summary.", EmptyArgs, "READ_ONLY", roles_general, "never", _personal_model_summary)
        self._register("memory_search", "Search bounded relevant semantic memory.", MemorySearchArgs, "READ_ONLY", roles_general, "never", _memory_search)
        self._register("memory_explain", "Explain a memory using stored provenance.", MemoryIdArgs, "READ_ONLY", roles_general, "never", _explain_memory)
        self._register("memory_remember", "Store an explicit user-confirmed semantic memory.", RememberArgs, "MUTATION", roles_general, "always", _remember)
        self._register("memory_correct", "Correct and supersede a semantic memory.", CorrectMemoryArgs, "MUTATION", roles_general, "always", _correct_memory)
        self._register("memory_pin", "Pin a semantic memory as a durable user rule.", MemoryIdArgs, "MUTATION", roles_general, "always", _pin_memory)
        self._register("memory_unpin", "Unpin a semantic memory.", MemoryIdArgs, "MUTATION", roles_general, "always", _unpin_memory)
        self._register("memory_forget", "Forget a semantic memory and suppress stale sources.", MemoryIdArgs, "MUTATION", roles_general, "always", _forget_memory)
        self._register("report_state", "Record explicit state observations.", StateObservationCreate, "MUTATION", roles_all, "conditional", _report_state)
        self._register("create_commitment", "Propose a fixed-time calendar appointment or obligation. Requires timezone-aware start and end times; host confirmation applies it.", CommitmentCreate, "MUTATION", roles_general, "always", _create_commitment)
        self._register("add_intention", "Propose flexible work for the planner to place within an availability window. Not for fixed-time appointments; use create_commitment for those.", ActionCreate, "MUTATION", roles_general, "conditional", _add_intention)
        self._register("request_replan", "Request deterministic Planner V2 replanning.", ReplanArgs, "MUTATION", roles_general, "conditional", _request_replan)
        self._register("start_workout", "Start a workout through Fitness service.", WorkoutStartRequest, "MUTATION", roles_fitness, "always", _start_workout)
        self._register("record_workout_set", "Record a workout set through Fitness service.", WorkoutSetAssistantArgs, "MUTATION", roles_fitness, "always", _record_workout_set)
        self._register("complete_workout", "Complete a workout through Fitness service.", WorkoutCompleteAssistantArgs, "MUTATION", roles_fitness, "always", _complete_workout)
        self._register("add_body_measurement", "Record a body measurement through Fitness service.", BodyMeasurementCreate, "MUTATION", roles_fitness, "conditional", _body_measurement)
        self._register("log_study_session", "Log a study session through Learning service.", StudyLogArgs, "MUTATION", roles_learning, "always", _study_session)
        self._register("create_course", "Create a course through Learning service.", CourseCreate, "MUTATION", roles_learning, "always", _create_course)
        self._register("create_exam", "Create an exam through Learning service.", ExamCreate, "MUTATION", roles_learning, "always", _create_exam)
        self._register("update_exam", "Update an exam through Learning service.", ExamUpdateAssistantArgs, "MUTATION", roles_learning, "always", _update_exam)
        self._register("create_household_task", "Create one canonical recurring household task.", HouseholdTaskCreate, "MUTATION", roles_home, "always", _create_household_task)
        self._register("complete_household_task", "Complete a household task and calculate its next due date.", HouseholdTaskIdArgs, "MUTATION", roles_home, "always", _complete_household_task)
        self._register("log_manual_meal", "Log an external meal through Kitchen service.", MealManualCreate, "MUTATION", roles_kitchen, "always", _log_manual_meal)
        self._register("complete_recipe_meal", "Complete a recipe meal and consume Kitchen inventory.", RecipeMealCompleteAssistantArgs, "MUTATION", roles_kitchen, "always", _complete_recipe_meal)

    def _register(
        self,
        name: str,
        description: str,
        args_schema: type[BaseModel],
        kind: ToolKind,
        allowed_roles: set[AssistantRole],
        confirmation_policy: ConfirmationPolicy,
        handler: Callable[[Session, UserProfile, BaseModel, str | None], ToolResult],
    ) -> None:
        self.tools[name] = ToolDefinition(name, description, args_schema, kind, allowed_roles, confirmation_policy, handler)

    def get(self, name: str | None) -> ToolDefinition:
        if not name or name not in self.tools:
            raise AssistantToolError("unknown_tool", "The requested tool is not registered.")
        return self.tools[name]

    def authorize(self, tool: ToolDefinition, role: AssistantRole) -> None:
        if role not in tool.allowed_roles:
            raise AssistantToolError("unauthorized_tool", "This assistant role is not allowed to use that tool.", status.HTTP_403_FORBIDDEN)

    def execute(self, db: Session, user: UserProfile, tool: ToolDefinition, args: BaseModel, *, idempotency_key: str | None = None) -> ToolResult:
        return tool.handler(db, user, args, idempotency_key)

    def requires_confirmation(self, tool: ToolDefinition, model_requested: bool) -> bool:
        if tool.kind == "READ_ONLY":
            return False
        if tool.confirmation_policy == "always":
            return True
        return bool(model_requested)


def semantic_error_response(exc: HTTPException) -> AssistantToolError:
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("code") or "The canonical service rejected that action."
    else:
        message = str(detail)
    return AssistantToolError("semantic_failure", message, exc.status_code)
