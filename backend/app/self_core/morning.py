from __future__ import annotations

from datetime import UTC, datetime, time
from hashlib import sha256
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.attention.schemas import AttentionAction, AttentionItemStatus
from app.communication.composer import ResponseComposer
from app.communication.schemas import CommunicativeIntent, ResponseModePreference, SpeechAct, StructuredFact
from app.database.models import (
    ActiveWorkspace,
    AttentionItem,
    Commitment,
    InventoryItem,
    InventoryLot,
    PlanProposal,
    Trajectory,
    UserProfile,
)
from app.domains.finance.contracts import grocery_budget_signal
from app.planning.automation import MorningPlanner
from app.self_core.schemas import MorningBriefingContext, MorningBriefingResponse, SelfCoreReference
from app.workspaces.schemas import WorkspaceStatus


POLICY_VERSION = "morning-briefing-v1"
VISIBLE_ATTENTION = {
    AttentionAction.show_passively.value,
    AttentionAction.mention_when_natural.value,
    AttentionAction.ask.value,
    AttentionAction.propose.value,
    AttentionAction.interrupt.value,
}


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class MorningBriefingBuilder:
    """Build a bounded projection from canonical services; it owns no life state."""

    def build(self, db: Session, user: UserProfile, *, timezone: str = "Europe/Berlin", now: datetime | None = None) -> MorningBriefingResponse:
        zone = ZoneInfo(timezone)
        local_now = now.astimezone(zone) if now and now.tzinfo else now.replace(tzinfo=zone) if now else datetime.now(zone)
        plan, plan_created = MorningPlanner().ensure(db, user, timezone_name=timezone, now=local_now)
        day_start = datetime.combine(local_now.date(), time.min, tzinfo=zone)
        day_end = datetime.combine(local_now.date(), time.max, tzinfo=zone)
        blocks = sorted(
            [block for block in plan.blocks if block.status not in {"completed", "cancelled", "skipped"} and _aware(block.ends_at) >= _aware(local_now)],
            key=lambda block: _aware(block.starts_at),
        )
        block_refs = tuple(
            SelfCoreReference(ref_type="plan_block", ref_id=block.id, title=block.title, status=block.status,
                              starts_at=block.starts_at, detail=block.domain)
            for block in blocks[:5]
        )
        commitments = list(db.scalars(
            select(Commitment).where(
                Commitment.user_id == user.id,
                Commitment.status == "active",
                Commitment.starts_at >= day_start,
                Commitment.starts_at <= day_end,
                Commitment.level.in_(("hard", "protected")),
            ).order_by(Commitment.starts_at).limit(4)
        ))
        trajectories = list(db.scalars(
            select(Trajectory).where(
                Trajectory.user_id == user.id,
                (Trajectory.on_track.is_(False)) | Trajectory.risk.in_(("high", "critical", "at_risk")),
            ).order_by(Trajectory.updated_at.desc()).limit(4)
        ))
        proposals = list(db.scalars(
            select(PlanProposal).where(
                PlanProposal.user_id == user.id,
                PlanProposal.status.in_(("DRAFT", "PRESENTED", "MODIFIED")),
                PlanProposal.expires_at >= local_now,
            ).order_by(PlanProposal.created_at.desc()).limit(3)
        ))
        attention = list(db.scalars(
            select(AttentionItem).where(
                AttentionItem.user_id == user.id,
                AttentionItem.status.in_((AttentionItemStatus.pending.value, AttentionItemStatus.eligible.value)),
                AttentionItem.action.in_(VISIBLE_ATTENTION),
                (AttentionItem.not_before.is_(None)) | (AttentionItem.not_before <= local_now),
                (AttentionItem.expires_at.is_(None)) | (AttentionItem.expires_at >= local_now),
            ).order_by(AttentionItem.priority.desc(), AttentionItem.created_at).limit(4)
        ))
        workspace = db.scalar(select(ActiveWorkspace).where(
            ActiveWorkspace.user_id == user.id,
            ActiveWorkspace.is_foreground.is_(True),
            ActiveWorkspace.status.in_((WorkspaceStatus.active.value, WorkspaceStatus.paused.value)),
        ))
        low_inventory = list(db.execute(
            select(InventoryItem, func.coalesce(func.sum(InventoryLot.quantity), 0.0).label("available"))
            .outerjoin(InventoryLot, (InventoryLot.inventory_item_id == InventoryItem.id) & (InventoryLot.status == "active") & ((InventoryLot.expires_at.is_(None)) | (InventoryLot.expires_at >= local_now)))
            .where(InventoryItem.user_id == user.id, InventoryItem.active.is_(True), InventoryItem.is_staple.is_(True), InventoryItem.restock_threshold.is_not(None))
            .group_by(InventoryItem.id)
            .having(func.coalesce(func.sum(InventoryLot.quantity), 0.0) <= InventoryItem.restock_threshold)
            .limit(3)
        ))
        budget = grocery_budget_signal(db, user)
        finance_signal = None
        if budget.status in {"LIMITED", "EXHAUSTED"}:
            finance_signal = {"status": budget.status, "remaining": budget.grocery_budget_remaining, "currency": budget.currency, "window": budget.budget_window}

        refs = [f"plan:{plan.id}:v{plan.version}"]
        refs += [f"attention:{row.id}" for row in attention]
        refs += [f"proposal:{row.id}" for row in proposals]
        if workspace:
            refs.append(f"workspace:{workspace.id}:r{workspace.state_revision}")
        fingerprint_material = f"{local_now.date()}|{plan.id}|{plan.version}|{user.world_revision}|{POLICY_VERSION}|{'|'.join(refs)}"
        fingerprint = sha256(fingerprint_material.encode()).hexdigest()[:32]
        context = MorningBriefingContext(
            date=local_now.date(), generated_at=local_now, fingerprint=fingerprint, plan_id=plan.id,
            plan_version=plan.version, world_revision=user.world_revision, first_block=block_refs[0] if block_refs else None,
            important_blocks=block_refs, protected_commitments=tuple(SelfCoreReference(
                ref_type="commitment", ref_id=row.id, title=row.title, status=row.status, starts_at=row.starts_at, detail=row.location
            ) for row in commitments), trajectory_changes=tuple(SelfCoreReference(
                ref_type="trajectory", ref_id=row.id, title=row.name, status=row.status, detail=row.risk
            ) for row in trajectories), active_proposals=tuple(SelfCoreReference(
                ref_type="plan_proposal", ref_id=row.id, title=row.reason_code.replace("_", " ").title(), status=row.status,
                detail=f"{len(row.changes_json or [])} proposed change(s)"
            ) for row in proposals), attention_items=tuple(SelfCoreReference(
                ref_type="attention_item", ref_id=row.id, title=row.subject, status=row.action, detail=row.reason_code
            ) for row in attention), active_workspace=(SelfCoreReference(
                ref_type="active_workspace", ref_id=workspace.id, title=workspace.workspace_type.title(), status=workspace.status,
                detail=workspace.current_step or workspace.current_phase
            ) if workspace else None), kitchen_signals=tuple(SelfCoreReference(
                ref_type="inventory_item", ref_id=item.id, title=item.ingredient_name, status="LOW", detail=f"{float(available):g} {item.canonical_unit} available"
            ) for item, available in low_inventory), finance_signal=finance_signal,
            omitted_categories=tuple(name for name, present in (("trajectories", trajectories), ("proposals", proposals), ("attention", attention), ("kitchen", low_inventory), ("finance", finance_signal)) if not present),
            source_refs=tuple(refs),
        )
        facts: list[StructuredFact] = []
        if context.first_block:
            facts.append(StructuredFact(key="first_block", value=f"{context.first_block.title} at {context.first_block.starts_at.astimezone(zone).strftime('%H:%M')}", source_ref=context.first_block.ref_id))
        if context.protected_commitments:
            item = context.protected_commitments[0]
            facts.append(StructuredFact(key="protected_commitment", value=f"{item.title} at {item.starts_at.astimezone(zone).strftime('%H:%M')}", source_ref=item.ref_id))
        if context.trajectory_changes:
            facts.append(StructuredFact(key="trajectory", value=f"{context.trajectory_changes[0].title} needs attention", source_ref=context.trajectory_changes[0].ref_id))
        if context.attention_items:
            facts.append(StructuredFact(key="attention", value=context.attention_items[0].title, source_ref=context.attention_items[0].ref_id))
        if context.kitchen_signals:
            facts.append(StructuredFact(key="kitchen", value=f"Low: {', '.join(item.title for item in context.kitchen_signals)}", source_ref=context.kitchen_signals[0].ref_id))
        if context.finance_signal:
            facts.append(StructuredFact(key="finance", value=f"Grocery budget is {context.finance_signal['status'].lower()}", source_ref=budget.source_ref))
        intent = CommunicativeIntent(
            purpose=SpeechAct.status, attention_action=AttentionAction.show_passively, reason_code="MORNING_BRIEFING",
            facts=tuple(facts), current_state_refs=context.source_refs, workspace_ref=workspace.id if workspace else None,
            response_mode_preference=ResponseModePreference.deterministic, fallback_template_key="morning_briefing",
            must_include=tuple(str(fact.value) for fact in facts),
        )
        message = ResponseComposer().deterministic_text(intent)
        return MorningBriefingResponse(context=context, message=message, reused=not plan_created, plan_created=plan_created)
