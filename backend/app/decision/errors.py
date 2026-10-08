class DecisionError(Exception):
    """Base class for typed decision infrastructure failures."""

    code = "decision_error"

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.retryable = retryable


class DecisionInfrastructureDisabled(DecisionError):
    code = "decision_infrastructure_disabled"


class DecisionProviderError(DecisionError):
    code = "decision_provider_error"


class DecisionProviderUnavailable(DecisionProviderError):
    code = "decision_provider_unavailable"


class DecisionProviderTimeout(DecisionProviderError):
    code = "decision_provider_timeout"


class DecisionValidationError(DecisionError):
    code = "decision_validation_error"


class UnsupportedDecisionQuestion(DecisionProviderError):
    code = "unsupported_decision_question"
