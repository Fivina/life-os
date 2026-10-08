from __future__ import annotations

import re

from app.feedback.schemas import ReservedFeedbackCommand


_LOG_FEEDBACK = re.compile(
    r"^\s*log\s+feedback(?:\s*[.!?:]\s*(?P<explanation>.*?))?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)


def match_log_feedback(message: str) -> ReservedFeedbackCommand:
    """Recognize only the reserved command and punctuation-delimited inline evidence."""
    match = _LOG_FEEDBACK.fullmatch(message)
    if match is None:
        return ReservedFeedbackCommand(matched=False)
    explanation = (match.group("explanation") or "").strip()
    return ReservedFeedbackCommand(
        matched=True,
        canonical_command="Log feedback",
        inline_explanation=explanation or None,
    )
