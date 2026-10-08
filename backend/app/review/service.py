from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import MemoryItem, QuickCapture, ReceiptLine, ReviewItem, UserProfile
from app.events.service import append_event
from app.review.schemas import ReviewAction, ReviewCreate, ReviewItemRead, ReviewResolutionRead, ReviewStatus


def _read(row: ReviewItem) -> ReviewItemRead:
    return ReviewItemRead(
        id=row.id, review_type=row.review_type, status=row.status, priority=row.priority,
        source=row.source, source_ref=row.source_ref, summary=row.summary, question=row.question,
        candidate_values=row.candidate_values_json or {}, evidence=row.evidence_json or {},
        confidence=row.confidence, ambiguity_reasons=row.ambiguity_reasons_json or [],
        affected_domain=row.affected_domain, target_entity_type=row.target_entity_type,
        target_entity_id=row.target_entity_id, resolution=row.resolution_json or {},
        expires_at=row.expires_at, correlation_id=row.correlation_id,
        expected_world_revision=row.expected_world_revision, expected_target_version=row.expected_target_version,
        created_at=row.created_at, updated_at=row.updated_at, resolved_at=row.resolved_at, version=row.version,
    )


def _fingerprint(payload: ReviewCreate) -> str:
    material = {
        "review_type": payload.review_type.value,
        "source": payload.source,
        "source_ref": payload.source_ref,
        "target_entity_type": payload.target_entity_type,
        "target_entity_id": payload.target_entity_id,
        "candidate_values": payload.candidate_values,
        "ambiguity_reasons": sorted(payload.ambiguity_reasons),
        "expected_target_version": payload.expected_target_version,
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class ReviewQueueService:
    def enqueue(self, db: Session, user: UserProfile, payload: ReviewCreate) -> tuple[ReviewItemRead, bool]:
        fingerprint = _fingerprint(payload)
        existing = db.scalar(select(ReviewItem).where(
            ReviewItem.user_id == user.id,
            ReviewItem.fingerprint == fingerprint,
            ReviewItem.status == ReviewStatus.pending.value,
        ))
        if existing is not None:
            return _read(existing), False
        row = ReviewItem(
            user_id=user.id, review_type=payload.review_type.value, status=ReviewStatus.pending.value,
            priority=payload.priority, source=payload.source, source_ref=payload.source_ref,
            summary=payload.summary, question=payload.question,
            candidate_values_json=payload.candidate_values, evidence_json=payload.evidence,
            confidence=payload.confidence, ambiguity_reasons_json=payload.ambiguity_reasons,
            affected_domain=payload.affected_domain, target_entity_type=payload.target_entity_type,
            target_entity_id=payload.target_entity_id, resolution_json={}, expires_at=payload.expires_at,
            correlation_id=payload.correlation_id, expected_world_revision=payload.expected_world_revision,
            expected_target_version=payload.expected_target_version, fingerprint=fingerprint,
            metadata_json=payload.metadata,
        )
        db.add(row)
        db.flush()
        append_event(
            db, user, event_type="review_item.created", aggregate_type="review_item", aggregate_id=row.id,
            payload={"review_item_id": row.id, "review_type": row.review_type, "correlation_id": row.correlation_id},
            outbox=True,
        )
        return _read(row), True

    def list(self, db: Session, user: UserProfile, *, status_filter: str = "PENDING", limit: int = 100) -> list[ReviewItemRead]:
        self.expire_due(db, user)
        query = select(ReviewItem).where(ReviewItem.user_id == user.id)
        if status_filter:
            query = query.where(ReviewItem.status == status_filter)
        rows = list(db.scalars(query.order_by(ReviewItem.priority.desc(), ReviewItem.created_at.asc()).limit(min(limit, 200))).all())
        return [_read(row) for row in rows]

    def get_model(self, db: Session, user: UserProfile, item_id: str) -> ReviewItem:
        row = db.scalar(select(ReviewItem).where(ReviewItem.id == item_id, ReviewItem.user_id == user.id))
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found.")
        return row

    def get(self, db: Session, user: UserProfile, item_id: str) -> ReviewItemRead:
        return _read(self.get_model(db, user, item_id))

    def expire_due(self, db: Session, user: UserProfile) -> None:
        now = datetime.now(UTC)
        rows = db.scalars(select(ReviewItem).where(
            ReviewItem.user_id == user.id, ReviewItem.status == ReviewStatus.pending.value,
            ReviewItem.expires_at.is_not(None), ReviewItem.expires_at < now,
        )).all()
        for row in rows:
            row.status = ReviewStatus.expired.value
            row.resolved_at = now
            row.version += 1

    def resolve(
        self,
        db: Session,
        user: UserProfile,
        item_id: str,
        *,
        action: ReviewAction,
        edited_values: dict,
        expected_version: int | None,
    ) -> ReviewResolutionRead:
        row = self.get_model(db, user, item_id)
        if expected_version is not None and row.version != expected_version:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Review item changed after it was loaded.")
        if row.status != ReviewStatus.pending.value:
            return ReviewResolutionRead(item=_read(row), world_revision=user.world_revision)
        if row.expires_at and row.expires_at < datetime.now(UTC):
            row.status, row.resolved_at, row.version = ReviewStatus.expired.value, datetime.now(UTC), row.version + 1
            append_event(
                db, user, event_type="review_item.expired", aggregate_type="review_item", aggregate_id=row.id,
                payload={"review_item_id": row.id, "correlation_id": row.correlation_id}, outbox=True,
            )
            return ReviewResolutionRead(item=_read(row), world_revision=user.world_revision)
        if action in {ReviewAction.reject, ReviewAction.dismiss}:
            return self._close(db, user, row, action, edited_values)
        if not self._revalidate_target(db, row):
            return self._superseded(db, user, row)
        try:
            entity_type, entity_id = self._apply(db, user, row, edited_values)
        except HTTPException:
            capture = db.scalar(select(QuickCapture).where(
                QuickCapture.id == row.source_ref,
                QuickCapture.user_id == user.id,
            )) if row.review_type in {"QUICK_CAPTURE", "FINANCE_CLASSIFICATION"} else None
            if capture is not None and capture.status == "SUPERSEDED":
                return self._superseded(db, user, row)
            raise
        row.status = ReviewStatus.resolved.value
        row.resolution_json = {"action": action.value, "edited_values": edited_values, "canonical_entity_type": entity_type, "canonical_entity_id": entity_id}
        row.resolved_at = datetime.now(UTC)
        row.resolved_by = "user"
        row.version += 1
        append_event(
            db, user, event_type="review_item.resolved", aggregate_type="review_item", aggregate_id=row.id,
            payload={"review_item_id": row.id, "action": action.value, "correlation_id": row.correlation_id}, outbox=True,
        )
        return ReviewResolutionRead(item=_read(row), canonical_entity_type=entity_type, canonical_entity_id=entity_id, world_revision=user.world_revision)

    def _close(self, db: Session, user: UserProfile, row: ReviewItem, action: ReviewAction, edited_values: dict) -> ReviewResolutionRead:
        if row.review_type in {"QUICK_CAPTURE", "FINANCE_CLASSIFICATION"} and action == ReviewAction.reject:
            from app.capture.service import QuickCaptureService
            from app.core.config import get_settings
            QuickCaptureService(get_settings(), review_queue=self).reject(db, user, row.source_ref)
        if row.review_type == "MEMORY_CANDIDATE" and action == ReviewAction.reject:
            from app.ai.gateway import AIGateway
            from app.core.config import get_settings
            from app.memory.embeddings import EmbeddingService
            from app.memory.service import MemoryService
            memory_id = row.target_entity_id or row.source_ref
            if db.scalar(select(MemoryItem).where(MemoryItem.id == memory_id, MemoryItem.user_id == user.id)) is not None:
                settings = get_settings()
                MemoryService(EmbeddingService(settings, AIGateway(settings))).forget(db, user, memory_id)
        row.status = ReviewStatus.dismissed.value
        row.resolution_json = {"action": action.value, "edited_values": edited_values}
        row.resolved_at = datetime.now(UTC)
        row.resolved_by = "user"
        row.version += 1
        append_event(
            db, user, event_type="review_item.dismissed", aggregate_type="review_item", aggregate_id=row.id,
            payload={"review_item_id": row.id, "action": action.value, "correlation_id": row.correlation_id}, outbox=True,
        )
        return ReviewResolutionRead(item=_read(row), world_revision=user.world_revision)

    def _revalidate_target(self, db: Session, row: ReviewItem) -> bool:
        if row.expected_target_version is None or not row.target_entity_id:
            return True
        if row.review_type == "RECEIPT_ITEM":
            target = db.get(ReceiptLine, row.target_entity_id)
        elif row.review_type == "MEMORY_CANDIDATE":
            target = db.get(MemoryItem, row.target_entity_id)
        elif row.review_type == "QUICK_CAPTURE":
            return True
        else:
            target = None
        if target is None or target.version != row.expected_target_version:
            return False
        return True

    def _superseded(self, db: Session, user: UserProfile, row: ReviewItem) -> ReviewResolutionRead:
        row.status = ReviewStatus.superseded.value
        row.resolution_json = {"reason": "target_changed"}
        row.resolved_at = datetime.now(UTC)
        row.resolved_by = "system"
        row.version += 1
        append_event(
            db, user, event_type="review_item.superseded", aggregate_type="review_item", aggregate_id=row.id,
            payload={"review_item_id": row.id, "correlation_id": row.correlation_id}, outbox=True,
        )
        return ReviewResolutionRead(item=_read(row), world_revision=user.world_revision)

    def _apply(self, db: Session, user: UserProfile, row: ReviewItem, edited_values: dict) -> tuple[str | None, str | None]:
        if row.review_type in {"QUICK_CAPTURE", "FINANCE_CLASSIFICATION"}:
            from app.capture.service import QuickCaptureService
            from app.core.config import get_settings
            result = QuickCaptureService(get_settings(), review_queue=self).apply(
                db, user, row.source_ref, edited_payload=edited_values, from_review=True
            )
            return result.canonical_entity_type, result.canonical_entity_id
        if row.review_type == "RECEIPT_ITEM":
            from app.domains.kitchen.receipt_schemas import ReceiptLineUpdate, ReceiptReviewUpdate
            from app.domains.kitchen.receipts import update_review
            receipt_id = str(row.metadata_json.get("receipt_id") or "")
            values = {**row.candidate_values_json, **edited_values, "review_required": False}
            update_review(db, user, receipt_id, ReceiptReviewUpdate(lines={row.target_entity_id: ReceiptLineUpdate.model_validate(values)}))
            return "receipt_line", row.target_entity_id
        if row.review_type == "MEMORY_CANDIDATE":
            from app.ai.gateway import AIGateway
            from app.core.config import get_settings
            from app.memory.embeddings import EmbeddingService
            from app.memory.service import MemoryService
            memory_id = row.target_entity_id or row.source_ref
            settings = get_settings()
            result = MemoryService(EmbeddingService(settings, AIGateway(settings))).confirm(db, user, memory_id)
            return "memory", result.id
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This review type has no authorized apply path.")

    def sync_receipt_uncertainty(self, db: Session, user: UserProfile, receipt_id: str) -> list[ReviewItemRead]:
        lines = list(db.scalars(select(ReceiptLine).where(
            ReceiptLine.user_id == user.id, ReceiptLine.receipt_import_id == receipt_id,
            ReceiptLine.review_required.is_(True),
        )).all())
        results: list[ReviewItemRead] = []
        for line in lines:
            item, _ = self.enqueue(db, user, ReviewCreate(
                review_type="RECEIPT_ITEM", priority=65, source="receipt", source_ref=line.id,
                summary=f"Check receipt line {line.line_number}: {line.raw_text}",
                question="What product, quantity, unit, and category should this receipt line use?",
                candidate_values={"normalized_name": line.normalized_name, "quantity": line.quantity, "unit": line.unit, "category": line.category},
                evidence={"raw_text": line.raw_text, "line_number": line.line_number},
                confidence=min(line.confidence_name, line.confidence_quantity, line.confidence_price),
                ambiguity_reasons=["receipt_line_uncertain"], affected_domain="KITCHEN",
                target_entity_type="receipt_line", target_entity_id=line.id,
                expected_target_version=line.version, metadata={"receipt_id": receipt_id},
            ))
            results.append(item)
        return results

    def enqueue_memory_candidate(self, db: Session, user: UserProfile, memory_id: str) -> ReviewItemRead:
        memory = db.scalar(select(MemoryItem).where(MemoryItem.id == memory_id, MemoryItem.user_id == user.id))
        if memory is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory candidate not found.")
        item, _ = self.enqueue(db, user, ReviewCreate(
            review_type="MEMORY_CANDIDATE", priority=35, source="memory", source_ref=memory.id,
            summary="Check a possible memory", question="Should Life OS keep this as a memory?",
            candidate_values={"content": memory.content, "domain": memory.domain, "memory_type": memory.memory_type},
            evidence={"source_kind": memory.source_kind}, confidence=memory.confidence,
            ambiguity_reasons=["memory_confidence_below_auto_store"], affected_domain="MEMORY",
            target_entity_type="memory", target_entity_id=memory.id, expected_target_version=memory.version,
        ))
        return item
