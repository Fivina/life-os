from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from app.decision.schemas import (
    CognitiveEvent,
    ContextFact,
    DecisionContext,
    DecisionQuestion,
    ProvenanceReference,
)


class DecisionContextBuilder:
    """Build small structured decision context from explicitly supplied relevant facts."""

    def __init__(self, *, max_facts: int = 24, max_serialized_bytes: int = 16_384):
        self.max_facts = max_facts
        self.max_serialized_bytes = max_serialized_bytes

    def build(
        self,
        *,
        event: CognitiveEvent,
        question: DecisionQuestion,
        facts: Mapping[str, Any] | None = None,
        provenance: Mapping[str, Sequence[ProvenanceReference]] | None = None,
        memory_refs: Sequence[str] = (),
        pattern_refs: Sequence[str] = (),
        recent_intervention_refs: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> DecisionContext:
        fact_values = facts or {}
        fact_provenance = provenance or {}
        if len(fact_values) > self.max_facts:
            raise ValueError(f"Decision context exceeds the {self.max_facts}-fact bound.")

        context_facts = tuple(
            ContextFact(
                key=key,
                value=value,
                provenance=tuple(fact_provenance.get(key) or (ProvenanceReference(source_type="caller"),)),
            )
            for key, value in sorted(fact_values.items())
        )
        context = DecisionContext(
            event_id=event.event_id,
            question_id=question.question_id,
            question_version=question.question_version,
            workspace_ref=event.workspace_ref,
            facts=context_facts,
            entity_refs=event.entity_refs,
            memory_refs=tuple(memory_refs),
            pattern_refs=tuple(pattern_refs),
            recent_intervention_refs=tuple(recent_intervention_refs),
            metadata=dict(metadata or {}),
        )
        encoded = json.dumps(context.model_dump(mode="json"), separators=(",", ":"), sort_keys=True).encode("utf-8")
        if len(encoded) > self.max_serialized_bytes:
            raise ValueError(f"Decision context exceeds the {self.max_serialized_bytes}-byte bound.")
        return context
