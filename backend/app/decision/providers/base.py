from typing import Protocol

from app.decision.provider_schemas import ProviderCapabilities, ProviderHealth, ProviderSupport
from app.decision.schemas import DecisionContext, DecisionProviderResult, DecisionQuestion


class DecisionProvider(Protocol):
    name: str
    provider_version: str
    model_version: str | None

    def capabilities(self) -> ProviderCapabilities: ...

    def supports(self, *, question: DecisionQuestion, context: DecisionContext) -> ProviderSupport: ...

    def health(self) -> ProviderHealth: ...

    def evaluate(self, *, question: DecisionQuestion, context: DecisionContext) -> DecisionProviderResult:
        """Evaluate a bounded decision without accessing canonical application state."""
        ...

    def evaluate_batch(
        self,
        *,
        questions: tuple[DecisionQuestion, ...],
        contexts: tuple[DecisionContext, ...],
    ) -> dict[str, DecisionProviderResult]:
        """Evaluate compatible questions against one shared bounded state when supported."""
        ...
