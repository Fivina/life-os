from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.types import AICapability, AIMessage, AIProviderError, AIRequest
from app.capture.schemas import (
    CaptureDomain,
    CapturedIntent,
    CaptureIntentType,
    CapturePolicyOutcome,
    CaptureStatus,
    ConsequenceLevel,
    QuickCaptureCreate,
    QuickCaptureRead,
)
from app.commitments.schemas import CommitmentCreate
from app.commitments.service import create_commitment
from app.core.config import Settings
from app.core.logging import get_logger
from app.database.models import Course, Exam, QuickCapture, UserProfile
from app.decision.traces import DecisionTraceService
from app.domains.finance.schemas import ManualTransactionCreate
from app.domains.finance.service import create_manual_transaction
from app.domains.kitchen.schemas import ManualShoppingNeedCreate
from app.domains.kitchen.service import create_manual_shopping_need
from app.domains.learning.schemas import ExamUpdate
from app.domains.learning.service import list_exams, update_exam
from app.events.service import append_event
from app.review.schemas import ReviewCreate, ReviewType
from app.review.service import ReviewQueueService


logger = get_logger(__name__)
WEEKDAYS = {name: index for index, name in enumerate(("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"))}
KNOWN_FINANCE_CATEGORIES = {
    "rewe": "Groceries", "aldi": "Groceries", "lidl": "Groceries", "edeka": "Groceries",
    "kaufland": "Groceries", "pharmacy": "Health", "apotheke": "Health",
    "netflix": "Subscriptions", "spotify": "Subscriptions", "lieferando": "Dining",
}


def _read(row: QuickCapture) -> QuickCaptureRead:
    return QuickCaptureRead(
        id=row.id, schema_version=row.schema_version, raw_text=row.raw_text, status=row.status,
        interpreted_domain=row.interpreted_domain, intent_type=row.intent_type,
        target_entity_type=row.target_entity_type, target_entity_id=row.target_entity_id,
        structured_payload=row.structured_payload_json or {}, confidence=row.confidence,
        ambiguity_flags=row.ambiguity_flags_json or [], consequence_level=row.consequence_level,
        confirmation_required=row.confirmation_required, review_required=row.review_required,
        policy_outcome=row.policy_outcome, reason_codes=row.reason_codes_json or [],
        interpreter_provider=row.interpreter_provider, interpreter_model=row.interpreter_model,
        review_item_id=row.review_item_id, canonical_entity_type=row.canonical_entity_type,
        canonical_entity_id=row.canonical_entity_id, expected_world_revision=row.expected_world_revision,
        created_at=row.created_at, applied_at=row.applied_at, version=row.version,
    )


class QuickCaptureService:
    policy_version = "quick-capture-policy-v1"

    def __init__(self, settings: Settings, *, review_queue: ReviewQueueService | None = None, gateway: AIGateway | None = None):
        self.settings = settings
        self.review_queue = review_queue or ReviewQueueService()
        self.gateway = gateway or AIGateway(settings)

    @staticmethod
    def is_likely_capture(text: str) -> bool:
        patterns = (
            r"(?i)\bexam\b.+\b(?:moved|changed|rescheduled)\b",
            r"(?i)^\s*(?:i\s+)?(?:paid|spent)\b",
            r"(?i)^\s*(?:i\s+)?(?:(?:need|have)\s+to\s+buy|buy|get|need\s+(?!to\b))\s*",
            r"(?i)^\s*.+?\s+(?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+\d",
        )
        return any(re.search(pattern, text.strip()) for pattern in patterns)

    def capture(
        self,
        db: Session,
        user: UserProfile,
        payload: QuickCaptureCreate,
        *,
        idempotency_key: str | None = None,
    ) -> QuickCaptureRead:
        key = idempotency_key or self._default_key(payload)
        existing = db.scalar(select(QuickCapture).where(
            QuickCapture.user_id == user.id, QuickCapture.idempotency_key == key,
        ))
        if existing is not None:
            return _read(existing)
        when = payload.now or datetime.now(UTC)
        intent = self._interpret(db, user, payload.text.strip(), now=when, timezone=payload.timezone)
        outcome = self._policy(intent)
        review_required = outcome == CapturePolicyOutcome.send_to_review
        capture_status = CaptureStatus.pending_review if review_required else (
            CaptureStatus.invalid if outcome == CapturePolicyOutcome.reject_invalid else CaptureStatus.proposed
        )
        row = QuickCapture(
            user_id=user.id, raw_text=payload.text.strip(), status=capture_status.value,
            source_conversation_id=payload.conversation_thread_id, source_message_id=payload.source_message_id,
            source_workspace_id=payload.workspace_id, interpreted_domain=intent.interpreted_domain.value,
            intent_type=intent.intent_type.value, target_entity_type=intent.target_entity_type,
            target_entity_id=intent.target_entity_id, structured_payload_json=intent.structured_payload,
            confidence=intent.confidence, ambiguity_flags_json=intent.ambiguity_flags,
            consequence_level=intent.consequence_level.value,
            confirmation_required=outcome == CapturePolicyOutcome.request_confirmation,
            review_required=review_required, policy_outcome=outcome.value,
            reason_codes_json=intent.reason_codes, interpreter_provider=intent.interpreter_provider,
            interpreter_model=intent.interpreter_model, idempotency_key=key,
            expected_world_revision=user.world_revision,
            trace_json={"policy_version": self.policy_version, "hidden_reasoning_stored": False},
        )
        db.add(row)
        db.flush()
        review_item_id: str | None = None
        if review_required:
            review_type = ReviewType.finance_classification if intent.interpreted_domain == CaptureDomain.finance else ReviewType.quick_capture
            review, _ = self.review_queue.enqueue(db, user, ReviewCreate(
                review_type=review_type,
                priority=75 if intent.consequence_level == ConsequenceLevel.high else 55,
                source="quick_capture", source_ref=row.id,
                summary=self._summary(intent), question=self._question(intent),
                candidate_values=intent.structured_payload,
                evidence={"raw_text": payload.text.strip()}, confidence=intent.confidence,
                ambiguity_reasons=intent.ambiguity_flags or intent.reason_codes,
                affected_domain=intent.interpreted_domain.value,
                target_entity_type=intent.target_entity_type, target_entity_id=intent.target_entity_id,
                correlation_id=row.id, expected_world_revision=row.expected_world_revision,
                expected_target_version=intent.structured_payload.get("expected_version"),
                metadata={"capture_intent_type": intent.intent_type.value},
            ))
            row.review_item_id = review.id
            review_item_id = review.id
        append_event(
            db, user, event_type="quick_capture.interpreted", aggregate_type="quick_capture", aggregate_id=row.id,
            payload={
                "capture_id": row.id, "domain": row.interpreted_domain, "intent_type": row.intent_type,
                "policy_outcome": row.policy_outcome, "review_item_id": review_item_id,
            },
            outbox=True,
        )
        trace = DecisionTraceService().record_quick_capture(
            db, user, capture_id=row.id, conversation_thread_id=row.source_conversation_id,
            workspace_ref=row.source_workspace_id,
            interpretation={**intent.model_dump(mode="json"), "entity_candidates": intent.structured_payload.get("entity_candidates", [])},
            policy_outcome=outcome.value, review_item_id=review_item_id,
        )
        row.trace_json = {**row.trace_json, "cognitive_trace_id": trace.id}
        db.flush()
        logger.info("quick_capture_interpreted", extra={"capture_id": row.id, "outcome": outcome.value, "domain": row.interpreted_domain})
        return _read(row)

    def get(self, db: Session, user: UserProfile, capture_id: str) -> QuickCaptureRead:
        return _read(self._get_model(db, user, capture_id))

    def list(self, db: Session, user: UserProfile, *, limit: int = 50) -> list[QuickCaptureRead]:
        rows = db.scalars(select(QuickCapture).where(QuickCapture.user_id == user.id).order_by(QuickCapture.created_at.desc()).limit(min(limit, 100))).all()
        return [_read(row) for row in rows]

    def apply(
        self,
        db: Session,
        user: UserProfile,
        capture_id: str,
        *,
        edited_payload: dict | None = None,
        expected_version: int | None = None,
        from_review: bool = False,
    ) -> QuickCaptureRead:
        row = self._get_model(db, user, capture_id)
        if expected_version is not None and row.version != expected_version:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Capture changed after it was loaded.")
        if row.status == CaptureStatus.applied.value:
            return _read(row)
        if row.status in {CaptureStatus.invalid.value, CaptureStatus.rejected.value, CaptureStatus.superseded.value}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Capture cannot be applied in its current state.")
        if row.review_required and not from_review:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This capture must be resolved through the Review Queue.")
        values = {**(row.structured_payload_json or {}), **(edited_payload or {})}
        entity_type: str
        entity_id: str
        if row.intent_type == CaptureIntentType.update_exam_date.value:
            exam = db.scalar(select(Exam).where(Exam.id == row.target_entity_id, Exam.user_id == user.id))
            expected = int(values.get("expected_version") or 0)
            if exam is None or exam.version != expected:
                row.status, row.version = CaptureStatus.superseded.value, row.version + 1
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The exam changed after this proposal was created.")
            new_date = date.fromisoformat(str(values["new_date"]))
            new_exam_at = exam.exam_at.replace(year=new_date.year, month=new_date.month, day=new_date.day) if exam.exam_at else None
            updated = update_exam(db, user, exam.id, ExamUpdate(expected_version=exam.version, exam_date=new_date, exam_at=new_exam_at))
            entity_type, entity_id = "exam", updated.id
        elif row.intent_type == CaptureIntentType.create_transaction.value:
            if not values.get("category"):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A category is required before applying this transaction.")
            transaction = create_manual_transaction(db, user, ManualTransactionCreate(
                occurred_on=date.fromisoformat(str(values["occurred_on"])), amount=Decimal(str(values["amount"])),
                currency=str(values.get("currency") or "EUR"), merchant=values.get("merchant"),
                category=str(values["category"]), description=values.get("description"),
                idempotency_key=f"quick-capture:{row.id}",
            ))
            entity_type, entity_id = "finance_transaction", transaction.id
        elif row.intent_type == CaptureIntentType.create_shopping_need.value:
            item = create_manual_shopping_need(db, user, ManualShoppingNeedCreate(
                item_name=str(values["item_name"]), quantity=float(values.get("quantity") or 1),
                unit=str(values.get("unit") or "count"), priority_class=str(values.get("priority_class") or "optional"),
                idempotency_key=f"quick-capture:{row.id}",
            ))
            entity_type, entity_id = "shopping_need_item", item.id
        elif row.intent_type == CaptureIntentType.create_commitment.value:
            commitment = create_commitment(db, user, CommitmentCreate(
                title=str(values["title"]), description=values.get("description"), level="hard", commitment_type="hard",
                starts_at=datetime.fromisoformat(str(values["starts_at"])), ends_at=datetime.fromisoformat(str(values["ends_at"])),
                timezone=str(values.get("timezone") or "Europe/Berlin"), all_day=False,
                location=values.get("location"), recurrence={}, source="quick_capture", notes=values.get("notes"),
            ))
            entity_type, entity_id = "commitment", commitment.id
        else:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Capture has no supported canonical mutation.")
        row.structured_payload_json = values
        row.status = CaptureStatus.applied.value
        row.canonical_entity_type, row.canonical_entity_id = entity_type, entity_id
        row.applied_at = datetime.now(UTC)
        row.review_required = False
        row.version += 1
        append_event(
            db, user, event_type="quick_capture.applied", aggregate_type="quick_capture", aggregate_id=row.id,
            payload={"capture_id": row.id, "canonical_entity_type": entity_type, "canonical_entity_id": entity_id}, outbox=True,
        )
        row.trace_json = {**(row.trace_json or {}), "final_outcome": "APPLIED", "canonical_ref": f"{entity_type}:{entity_id}"}
        logger.info("quick_capture_applied", extra={"capture_id": row.id, "entity_type": entity_type})
        return _read(row)

    def reject(self, db: Session, user: UserProfile, capture_id: str) -> QuickCaptureRead:
        row = self._get_model(db, user, capture_id)
        if row.status == CaptureStatus.applied.value:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An applied capture cannot be rejected.")
        row.status, row.rejected_at, row.version = CaptureStatus.rejected.value, datetime.now(UTC), row.version + 1
        append_event(db, user, event_type="quick_capture.rejected", aggregate_type="quick_capture", aggregate_id=row.id, payload={"capture_id": row.id}, outbox=True)
        return _read(row)

    def _get_model(self, db: Session, user: UserProfile, capture_id: str) -> QuickCapture:
        row = db.scalar(select(QuickCapture).where(QuickCapture.id == capture_id, QuickCapture.user_id == user.id))
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quick capture not found.")
        return row

    def _interpret(self, db: Session, user: UserProfile, text: str, *, now: datetime, timezone: str) -> CapturedIntent:
        exam = self._exam_intent(db, user, text, now=now, timezone=timezone)
        if exam:
            return exam
        finance = self._finance_intent(text, now=now)
        if finance:
            return finance
        shopping = re.match(
            r"(?i)^\s*(?:i\s+)?(?:(?:need|have)\s+to\s+buy|buy|get|need\s+(?!to\b))\s*(?:some\s+)?(.+?)[.!]?\s*$",
            text,
        )
        if shopping:
            item = shopping.group(1).strip()
            return CapturedIntent(
                interpreted_domain=CaptureDomain.kitchen, intent_type=CaptureIntentType.create_shopping_need,
                target_entity_type="shopping_need_item", structured_payload={"item_name": item, "quantity": 1, "unit": "count", "priority_class": "optional"},
                confidence=0.96, consequence_level=ConsequenceLevel.low, confirmation_required=True,
                reason_codes=["explicit_shopping_need"],
            )
        commitment = self._commitment_intent(text, now=now, timezone=timezone)
        if commitment:
            return commitment
        return self._ai_interpret(db, user, text, now=now, timezone=timezone)

    def _exam_intent(self, db: Session, user: UserProfile, text: str, *, now: datetime, timezone: str) -> CapturedIntent | None:
        match = re.search(r"(?i)(?:my\s+)?(.+?)\s+exam\s+(?:was\s+)?(?:moved|changed|rescheduled)\s+to\s+(.+?)[.!]?$", text)
        generic = re.search(r"(?i)(?:move|change|reschedule)\s+(?:my\s+|the\s+)?exam\s+to\s+(.+?)[.!]?$", text)
        if not match and not generic:
            return None
        subject = match.group(1).strip() if match else ""
        date_phrase = match.group(2).strip() if match else generic.group(1).strip()
        new_date = self._parse_date(date_phrase, now, timezone)
        exams = list(list_exams(db, user))
        candidates: list[Exam] = []
        subject_key = re.sub(r"\s+", " ", subject.lower()).strip()
        title_matches = [exam for exam in exams if subject_key and subject_key in exam.title.lower()]
        if len(title_matches) == 1:
            candidates = title_matches
        else:
            for exam in exams:
                course = db.get(Course, exam.course_id) if exam.course_id else None
                haystack = " ".join(filter(None, [exam.title, course.name if course else None])).lower()
                if not subject or subject_key in haystack or any(token in haystack for token in subject_key.split() if len(token) > 3):
                    candidates.append(exam)
        if new_date is None or len(candidates) != 1:
            flags = []
            if new_date is None:
                flags.append("date_unresolved")
            if len(candidates) == 0:
                flags.append("target_not_found")
            elif len(candidates) > 1:
                flags.append("target_ambiguous")
            return CapturedIntent(
                interpreted_domain=CaptureDomain.learning, intent_type=CaptureIntentType.update_exam_date,
                target_entity_type="exam", structured_payload={
                    "requested_subject": subject or None, "date_phrase": date_phrase,
                    "new_date": new_date.isoformat() if new_date else None,
                    "entity_candidates": [{"id": item.id, "title": item.title, "version": item.version} for item in candidates[:6]],
                }, confidence=0.35 if candidates else 0.2, ambiguity_flags=flags,
                consequence_level=ConsequenceLevel.high, confirmation_required=True,
                reason_codes=["exam_update_requires_resolved_target"],
            )
        target = candidates[0]
        return CapturedIntent(
            interpreted_domain=CaptureDomain.learning, intent_type=CaptureIntentType.update_exam_date,
            target_entity_type="exam", target_entity_id=target.id,
            structured_payload={
                "exam_title": target.title, "old_date": (target.exam_at.date() if target.exam_at else target.exam_date).isoformat() if (target.exam_at or target.exam_date) else None,
                "new_date": new_date.isoformat(), "expected_version": target.version,
            }, confidence=0.98, consequence_level=ConsequenceLevel.high, confirmation_required=True,
            reason_codes=["canonical_exam_resolved", "consequential_date_change"],
        )

    def _finance_intent(self, text: str, *, now: datetime) -> CapturedIntent | None:
        match = re.search(r"(?i)\b(?:i\s+)?(?:paid|spent)\s*(?:€|eur\s*)?([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:euros?|eur|€)?(?:\s+(?:at|to)\s+(.+?))?[.!]?\s*$", text)
        if not match:
            return None
        amount = match.group(1).replace(",", ".")
        merchant = (match.group(2) or "").strip() or None
        category = next((value for key, value in KNOWN_FINANCE_CATEGORIES.items() if merchant and key in merchant.lower()), None)
        flags = [] if category else ["category_uncertain"]
        return CapturedIntent(
            interpreted_domain=CaptureDomain.finance, intent_type=CaptureIntentType.create_transaction,
            target_entity_type="finance_transaction",
            structured_payload={"occurred_on": now.date().isoformat(), "amount": amount, "currency": "EUR", "merchant": merchant, "category": category, "description": None},
            confidence=0.95 if merchant else 0.82, ambiguity_flags=flags,
            consequence_level=ConsequenceLevel.medium, confirmation_required=True,
            reason_codes=["explicit_payment_fact"] + (["classification_requires_review"] if not category else ["merchant_category_rule"]),
        )

    def _commitment_intent(self, text: str, *, now: datetime, timezone: str) -> CapturedIntent | None:
        match = re.match(r"(?i)^\s*(.+?)\s+(next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+([0-2]?\d)(?::([0-5]\d))?\s*$", text.strip(" ."))
        if not match:
            return None
        title = match.group(1).strip().title()
        day = self._next_weekday(now, WEEKDAYS[match.group(3).lower()], force_next=bool(match.group(2)))
        try:
            zone = ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("UTC")
        starts = datetime.combine(day, time(int(match.group(4)), int(match.group(5) or 0)), tzinfo=zone)
        ends = starts + timedelta(hours=1)
        return CapturedIntent(
            interpreted_domain=CaptureDomain.calendar, intent_type=CaptureIntentType.create_commitment,
            target_entity_type="commitment",
            structured_payload={"title": title, "starts_at": starts.isoformat(), "ends_at": ends.isoformat(), "timezone": timezone, "duration_assumption_minutes": 60},
            confidence=0.88, ambiguity_flags=["duration_assumed"], consequence_level=ConsequenceLevel.high,
            confirmation_required=True, reason_codes=["explicit_calendar_time", "consequential_commitment_creation"],
        )

    def _ai_interpret(self, db: Session, user: UserProfile, text: str, *, now: datetime, timezone: str) -> CapturedIntent:
        fallback = CapturedIntent(
            interpreted_domain=CaptureDomain.unknown, intent_type=CaptureIntentType.unknown,
            structured_payload={}, confidence=0, ambiguity_flags=["interpretation_unavailable"],
            consequence_level=ConsequenceLevel.medium, confirmation_required=True,
            reason_codes=["deterministic_parser_no_match"],
        )
        try:
            response = self.gateway.complete(
                db, user, request_id=f"quick-capture:{hashlib.sha256(text.encode()).hexdigest()[:16]}",
                assistant_role="GENERAL_ASSISTANT", skill_name="quick-capture", skill_version="1.9.1",
                capability=AICapability.fast,
                request=AIRequest(
                    system_instruction=(
                        "Interpret a possible Life OS canonical capture. Never authorize a mutation. Use only the supported intents "
                        "UPDATE_EXAM_DATE, CREATE_TRANSACTION, CREATE_SHOPPING_NEED, CREATE_COMMITMENT, or UNKNOWN. "
                        "Return UNKNOWN when required facts or identity are unavailable."
                    ),
                    messages=[AIMessage(role="user", content=text)], response_schema=CapturedIntent.model_json_schema(),
                    temperature=0, metadata={"current_time": now.isoformat(), "timezone": timezone},
                ), optional=True,
            )
            interpreted = CapturedIntent.model_validate_json(response.text or "{}")
            return interpreted.model_copy(update={
                "confirmation_required": True,
                "ambiguity_flags": list(dict.fromkeys([*interpreted.ambiguity_flags, "semantic_interpretation_requires_review"])),
                "interpreter_provider": response.provider,
                "interpreter_model": response.model,
            })
        except (AIProviderError, ValidationError, ValueError, TypeError):
            return fallback

    @staticmethod
    def _policy(intent: CapturedIntent) -> CapturePolicyOutcome:
        if intent.intent_type == CaptureIntentType.unknown:
            return CapturePolicyOutcome.send_to_review
        if intent.ambiguity_flags and any(flag in {"target_not_found", "target_ambiguous", "date_unresolved", "category_uncertain", "semantic_interpretation_requires_review"} for flag in intent.ambiguity_flags):
            return CapturePolicyOutcome.send_to_review
        if intent.consequence_level in {ConsequenceLevel.medium, ConsequenceLevel.high} or intent.confirmation_required:
            return CapturePolicyOutcome.request_confirmation
        return CapturePolicyOutcome.apply

    @staticmethod
    def _parse_date(value: str, now: datetime, timezone: str) -> date | None:
        cleaned = value.lower().strip().rstrip(".")
        try:
            return date.fromisoformat(cleaned)
        except ValueError:
            pass
        match = re.fullmatch(r"(?:(next)\s+)?(" + "|".join(WEEKDAYS) + r")", cleaned)
        if match:
            return QuickCaptureService._next_weekday(now, WEEKDAYS[match.group(2)], force_next=bool(match.group(1)))
        for fmt in ("%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _next_weekday(now: datetime, weekday: int, *, force_next: bool) -> date:
        delta = (weekday - now.date().weekday()) % 7
        if delta == 0 or (force_next and delta < 7):
            delta += 7
        return now.date() + timedelta(days=delta)

    @staticmethod
    def _summary(intent: CapturedIntent) -> str:
        labels = {
            CaptureIntentType.update_exam_date: "Review exam date change",
            CaptureIntentType.create_transaction: "Review finance transaction",
            CaptureIntentType.create_shopping_need: "Review shopping need",
            CaptureIntentType.create_commitment: "Review calendar commitment",
            CaptureIntentType.unknown: "Clarify captured information",
        }
        return labels[intent.intent_type]

    @staticmethod
    def _question(intent: CapturedIntent) -> str:
        if "target_ambiguous" in intent.ambiguity_flags:
            return "Which canonical entity should this update?"
        if "category_uncertain" in intent.ambiguity_flags:
            return "Which finance category should this transaction use?"
        return "Please check or complete this proposed change before it is applied."

    @staticmethod
    def _default_key(payload: QuickCaptureCreate) -> str:
        material = "|".join((payload.text.strip().lower(), payload.conversation_thread_id or "", payload.source_message_id or "", payload.workspace_id or ""))
        return f"capture:{hashlib.sha256(material.encode('utf-8')).hexdigest()}"
