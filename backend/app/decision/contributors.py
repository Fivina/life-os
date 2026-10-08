from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from app.decision.schemas import CognitiveEvent, DecisionQuestion, DecisionQuestionRequest


class DecisionContributor(Protocol):
    name: str
    descriptor: "ContributorDescriptor"

    def contribute(
        self,
        *,
        event: CognitiveEvent,
        state: Mapping[str, object],
    ) -> tuple[DecisionQuestionRequest, ...]:
        """Return zero or a bounded set of explicit questions relevant to this event."""
        ...


@dataclass(frozen=True)
class ContributorDescriptor:
    contributor_id: str
    version: str
    supported_event_types: frozenset[str] = frozenset()
    supported_event_prefixes: tuple[str, ...] = ()
    supported_domains: frozenset[str] = frozenset()
    supported_entity_types: frozenset[str] = frozenset()
    question_families: frozenset[str] = frozenset()
    priority: int = 50

    def matches(self, event: CognitiveEvent) -> bool:
        event_type_match = (
            not self.supported_event_types and not self.supported_event_prefixes
        ) or event.event_type in self.supported_event_types or any(
            event.event_type.startswith(prefix) for prefix in self.supported_event_prefixes
        )
        domain_match = not self.supported_domains or bool(self.supported_domains.intersection(event.domains))
        event_entity_types = {reference.entity_type for reference in event.entity_refs}
        entity_match = not self.supported_entity_types or bool(self.supported_entity_types.intersection(event_entity_types))
        return event_type_match and domain_match and entity_match


@dataclass(frozen=True)
class ContributorActivation:
    contributors: tuple[DecisionContributor, ...]
    truncated_contributor_ids: tuple[str, ...] = ()


class DecisionContributorRegistry:
    def __init__(self, contributors: Sequence[DecisionContributor] = ()):
        self._contributors: dict[str, DecisionContributor] = {}
        for contributor in contributors:
            self.register(contributor)

    def register(self, contributor: DecisionContributor) -> None:
        contributor_id = contributor.descriptor.contributor_id
        if contributor_id in self._contributors:
            raise ValueError(f"Duplicate decision contributor {contributor_id}.")
        self._contributors[contributor_id] = contributor

    def activate(self, event: CognitiveEvent, *, max_contributors: int = 4) -> ContributorActivation:
        if max_contributors < 1:
            raise ValueError("At least one contributor slot is required.")
        matching = sorted(
            (contributor for contributor in self._contributors.values() if contributor.descriptor.matches(event)),
            key=lambda item: (-item.descriptor.priority, item.descriptor.contributor_id),
        )
        return ContributorActivation(
            contributors=tuple(matching[:max_contributors]),
            truncated_contributor_ids=tuple(
                contributor.descriptor.contributor_id for contributor in matching[max_contributors:]
            ),
        )


class StaticDecisionContributor:
    """Explicit test/integration contributor; it performs no dynamic system-wide activation."""

    def __init__(
        self,
        *,
        name: str,
        event_types: Sequence[str],
        questions: Sequence[DecisionQuestion],
        max_questions: int = 4,
    ):
        if len(questions) > max_questions:
            raise ValueError(f"Contributor exceeds the {max_questions}-question bound.")
        self.name = name
        self.event_types = frozenset(event_types)
        self.questions = tuple(questions)
        self.descriptor = ContributorDescriptor(
            contributor_id=name,
            version="1",
            supported_event_types=self.event_types,
            question_families=frozenset(question.family for question in questions),
        )

    def contribute(
        self,
        *,
        event: CognitiveEvent,
        state: Mapping[str, object],
    ) -> tuple[DecisionQuestionRequest, ...]:
        del state
        if event.event_type not in self.event_types:
            return ()
        return tuple(DecisionQuestionRequest(question=question) for question in self.questions)
