from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import CognitiveTrace, FeedbackResponse, FeedbackSession, UserProfile
from app.feedback.schemas import (
    FeedbackDimension,
    FeedbackSessionStatus,
    IntelligenceQualitySummary,
    QualityDimensionSummary,
    QualityFilter,
)


class IntelligenceQualityService:
    """Computed descriptive aggregates. These statistics never become policy by themselves."""

    minimum_stable_sample = 5

    def summarize(
        self,
        db: Session,
        user: UserProfile,
        *,
        filters: QualityFilter | None = None,
        now: datetime | None = None,
    ) -> IntelligenceQualitySummary:
        query_filter = filters or QualityFilter()
        cutoff = (now or datetime.now(UTC)) - timedelta(days=query_filter.days) if query_filter.days else None
        statement = (
            select(FeedbackSession, CognitiveTrace)
            .join(CognitiveTrace, CognitiveTrace.id == FeedbackSession.target_cognitive_trace_id)
            .where(FeedbackSession.user_id == user.id)
        )
        if cutoff is not None:
            statement = statement.where(FeedbackSession.created_at >= cutoff)
        if query_filter.provider:
            statement = statement.where(CognitiveTrace.provider == query_filter.provider)
        if query_filter.model_version:
            statement = statement.where(CognitiveTrace.model_version == query_filter.model_version)
        if query_filter.policy_version:
            statement = statement.where(CognitiveTrace.policy_version == query_filter.policy_version)
        if query_filter.decision_family:
            statement = statement.where(CognitiveTrace.question_family == query_filter.decision_family)
        session_pairs = list(db.execute(statement).all())
        session_ids = [session.id for session, _ in session_pairs]
        responses = list(db.scalars(
            select(FeedbackResponse).where(FeedbackResponse.feedback_session_id.in_(session_ids))
        )) if session_ids else []

        grouped: dict[str, list[FeedbackResponse]] = defaultdict(list)
        for response in responses:
            grouped[response.dimension].append(response)
        dimensions = tuple(
            self._dimension_summary(FeedbackDimension(dimension), items)
            for dimension, items in sorted(grouped.items())
        )
        completed_count = sum(session.status == FeedbackSessionStatus.completed.value for session, _ in session_pairs)
        session_count = len(session_pairs)
        numeric_count = sum(response.score is not None and not response.is_skipped for response in responses)
        skipped_count = sum(response.is_skipped for response in responses)

        def count(values) -> dict[str, int]:
            return dict(sorted(Counter(value or "UNKNOWN" for value in values).items()))

        return IntelligenceQualitySummary(
            window_days=query_filter.days,
            session_count=session_count,
            completed_session_count=completed_count,
            completion_rate=round(completed_count / session_count, 6) if session_count else 0,
            clarification_rate=round(
                sum(session.clarification_used for session, _ in session_pairs) / session_count, 6
            ) if session_count else 0,
            average_questions_answered=round(
                sum(session.questions_answered_count for session, _ in session_pairs) / session_count, 6
            ) if session_count else 0,
            response_count=len(responses),
            numeric_response_count=numeric_count,
            skipped_response_count=skipped_count,
            dimensions=dimensions,
            scope_distribution=count(response.feedback_scope for response in responses),
            workspace_distribution=count(session.parent_workspace_type for session, _ in session_pairs),
            decision_family_distribution=count(trace.question_family for _, trace in session_pairs),
            provider_distribution=count(trace.provider for _, trace in session_pairs),
            model_distribution=count(trace.model_version for _, trace in session_pairs),
            policy_distribution=count(trace.policy_version for _, trace in session_pairs),
            routing_policy_distribution=count(
                ((trace.metadata_json or {}).get("provider_route") or {}).get("policy_version")
                for _, trace in session_pairs
            ),
            attention_action_distribution=count(
                ((session.frozen_context_json.get("attention_item") or {}).get("action")
                 or (session.frozen_context_json.get("trace") or {}).get("selected_answer"))
                for session, _ in session_pairs
            ),
        )

    def _dimension_summary(
        self,
        dimension: FeedbackDimension,
        responses: list[FeedbackResponse],
    ) -> QualityDimensionSummary:
        numeric = [response.score for response in responses if response.score is not None and not response.is_skipped]
        skipped = sum(response.is_skipped for response in responses)
        distribution = {str(score): numeric.count(score) for score in range(6)}
        return QualityDimensionSummary(
            dimension=dimension,
            response_count=len(responses),
            numeric_sample_count=len(numeric),
            skipped_count=skipped,
            average_score=round(sum(numeric) / len(numeric), 6) if numeric else None,
            score_distribution=distribution,
            skip_rate=round(skipped / len(responses), 6) if responses else 0,
            low_score_rate=round(sum(score <= 1 for score in numeric) / len(numeric), 6) if numeric else None,
            high_score_rate=round(sum(score >= 4 for score in numeric) / len(numeric), 6) if numeric else None,
            low_sample_warning=len(numeric) < self.minimum_stable_sample,
        )
