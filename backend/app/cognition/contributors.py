from __future__ import annotations

from typing import Mapping

from app.decision.contributors import ContributorDescriptor
from app.decision.questions import ATTENTION_ACTION_V1
from app.decision.schemas import CognitiveEvent, DecisionQuestionRequest


def _attention_request(event: CognitiveEvent, *, default_reason: str) -> DecisionQuestionRequest:
    payload = event.input_payload
    return DecisionQuestionRequest(
        question=ATTENTION_ACTION_V1,
        metadata={
            "reason_code": payload.get("reason_code", default_reason),
            "subject": payload.get("subject", event.event_type),
            "priority": payload.get("priority", 30),
            "urgency": payload.get("urgency", 0.3),
            "evidence_quality": payload.get("evidence_quality", 0.3),
            "reversible": payload.get("reversible", True),
            "requires_canonical_mutation": payload.get("requires_canonical_mutation", False),
            "supported_in_version": payload.get("supported_in_version", True),
            "active_task_interruption_cost": payload.get("active_task_interruption_cost", 0.2),
            "not_before": payload.get("not_before"),
            "expires_at": payload.get("expires_at"),
            "open_thread_id": payload.get("open_thread_id"),
            "prospective_thread_id": payload.get("prospective_thread_id"),
            "curiosity": payload.get("curiosity"),
            "deduplication_key": payload.get("deduplication_key"),
            "host_authorized_actions": event.metadata.get("host_authorized_actions", []),
        },
    )


class WorkspaceDecisionContributor:
    name = "workspace-attention"
    descriptor = ContributorDescriptor(
        contributor_id="workspace-attention",
        version="1",
        supported_event_prefixes=("workspace.",),
        question_families=frozenset({"attention"}),
        priority=70,
    )

    def contribute(self, *, event: CognitiveEvent, state: Mapping[str, object]) -> tuple[DecisionQuestionRequest, ...]:
        del state
        return (_attention_request(event, default_reason="workspace_event"),)


class AttentionDecisionContributor:
    name = "attention-candidate"
    descriptor = ContributorDescriptor(
        contributor_id="attention-candidate",
        version="1",
        supported_event_types=frozenset({"attention.candidate"}),
        question_families=frozenset({"attention"}),
        priority=80,
    )

    def contribute(self, *, event: CognitiveEvent, state: Mapping[str, object]) -> tuple[DecisionQuestionRequest, ...]:
        del state
        return (_attention_request(event, default_reason="attention_candidate"),)


class ProspectiveThreadDecisionContributor:
    name = "prospective-thread-attention"
    descriptor = ContributorDescriptor(
        contributor_id="prospective-thread-attention",
        version="1",
        supported_event_types=frozenset({"prospective.eligible"}),
        question_families=frozenset({"attention"}),
        priority=75,
    )

    def contribute(self, *, event: CognitiveEvent, state: Mapping[str, object]) -> tuple[DecisionQuestionRequest, ...]:
        del state
        return (_attention_request(event, default_reason="prospective_thread_eligible"),)


DEFAULT_COGNITIVE_CONTRIBUTORS = (
    AttentionDecisionContributor(),
    ProspectiveThreadDecisionContributor(),
    WorkspaceDecisionContributor(),
)
