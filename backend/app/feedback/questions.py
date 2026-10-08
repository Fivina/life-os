from __future__ import annotations

from dataclasses import dataclass

from app.database.models import CognitiveTrace
from app.feedback.schemas import FeedbackClarification, FeedbackDimension, FeedbackQuestion


QUESTION_PROMPTS: dict[FeedbackDimension, tuple[str, str, str]] = {
    FeedbackDimension.timing: ("feedback.timing", "How was the timing?", "Completely wrong", "Exactly right"),
    FeedbackDimension.content_usefulness: ("feedback.content_usefulness", "How useful was the content itself?", "Not useful", "Exactly useful"),
    FeedbackDimension.context_selection: ("feedback.context_selection", "How well did this fit the current context?", "Wrong context", "Perfect context"),
    FeedbackDimension.frequency: ("feedback.frequency", "Was this surfaced at an appropriate frequency?", "Far too often", "Exactly right"),
    FeedbackDimension.tone: ("feedback.tone", "How appropriate was the tone?", "Completely wrong", "Exactly right"),
    FeedbackDimension.priority: ("feedback.priority", "Was this important enough to surface now?", "Not important", "Exactly right"),
    FeedbackDimension.question_usefulness: ("feedback.question_usefulness", "Was asking this question useful?", "Pointless", "Very useful"),
    FeedbackDimension.plan_realism: ("feedback.plan_realism", "How realistic was the planning judgment?", "Unrealistic", "Fully realistic"),
    FeedbackDimension.memory_correctness: ("feedback.memory_correctness", "Was the recalled information correct?", "Completely wrong", "Exactly correct"),
    FeedbackDimension.action_correctness: ("feedback.action_correctness", "Was the suggested action appropriate?", "Wrong action", "Exactly right"),
    FeedbackDimension.factual_accuracy: ("feedback.factual_accuracy", "How factually accurate was it?", "Incorrect", "Fully accurate"),
    FeedbackDimension.ui_state_mismatch: ("feedback.ui_state_mismatch", "Did the interface reflect the actual state?", "Completely mismatched", "Exactly matched"),
    FeedbackDimension.voice_transcription: ("feedback.voice_transcription", "Was the transcription accurate?", "Incorrect", "Fully accurate"),
    FeedbackDimension.latency: ("feedback.latency", "Was the response time acceptable?", "Unacceptably slow", "Exactly right"),
}


@dataclass(frozen=True)
class FeedbackQuestionPlan:
    questions: tuple[FeedbackQuestion, ...]
    clarification: FeedbackClarification | None = None


class FeedbackQuestionSelector:
    version = "feedback-question-selector-v1"

    def __init__(self, *, max_questions: int = 4):
        self.max_questions = max(1, min(max_questions, 4))

    def select(self, trace: CognitiveTrace, *, inline_explanation: str | None = None) -> FeedbackQuestionPlan:
        selected_answer = str((trace.output_json or {}).get("selected_answer", ""))
        family = trace.question_family.lower()
        question_id = trace.question_id.lower()
        explanation = (inline_explanation or "").lower()

        if family == "memory" or question_id.startswith("memory."):
            dimensions = [
                FeedbackDimension.memory_correctness,
                FeedbackDimension.context_selection,
                FeedbackDimension.factual_accuracy,
            ]
        elif family == "planning" or question_id.startswith("planning.") or trace.planner_ref:
            dimensions = [
                FeedbackDimension.plan_realism,
                FeedbackDimension.action_correctness,
                FeedbackDimension.priority,
                FeedbackDimension.timing,
            ]
        elif selected_answer == "ASK":
            dimensions = [
                FeedbackDimension.question_usefulness,
                FeedbackDimension.timing,
                FeedbackDimension.priority,
            ]
        elif family == "attention":
            dimensions = [
                FeedbackDimension.timing,
                FeedbackDimension.content_usefulness,
                FeedbackDimension.context_selection,
            ]
        else:
            dimensions = [
                FeedbackDimension.content_usefulness,
                FeedbackDimension.context_selection,
                FeedbackDimension.action_correctness,
            ]

        refinements: list[FeedbackDimension] = []
        if any(term in explanation for term in ("timing", "too early", "too late", "not now")):
            refinements.append(FeedbackDimension.timing)
        if any(term in explanation for term in ("remember", "memory", "preference")):
            refinements.append(FeedbackDimension.memory_correctness)
        if any(term in explanation for term in ("fact", "incorrect", "not true")):
            refinements.append(FeedbackDimension.factual_accuracy)
        if any(term in explanation for term in ("slow", "latency", "took too long")):
            refinements.append(FeedbackDimension.latency)
        if any(term in explanation for term in ("tone", "rude", "wording")):
            refinements.append(FeedbackDimension.tone)

        ordered = []
        for dimension in (*refinements, *dimensions):
            if dimension not in ordered:
                ordered.append(dimension)
        questions = tuple(self._question(dimension) for dimension in ordered[: self.max_questions])

        ambiguous = bool(explanation) and any(term in explanation.strip(" .!") for term in ("bad", "wrong", "not good")) and not refinements
        return FeedbackQuestionPlan(
            questions=questions,
            clarification=FeedbackClarification() if ambiguous else None,
        )

    @staticmethod
    def _question(dimension: FeedbackDimension) -> FeedbackQuestion:
        question_id, prompt, low_label, high_label = QUESTION_PROMPTS[dimension]
        return FeedbackQuestion(
            question_id=question_id,
            question_version=1,
            dimension=dimension,
            prompt=prompt,
            low_label=low_label,
            high_label=high_label,
        )
