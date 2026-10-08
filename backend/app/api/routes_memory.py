from __future__ import annotations

from uuid import uuid4
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.database.models import (
    AIActionAudit,
    Episode,
    MemoryEvidence,
    MemoryItem,
    MemoryProcessingJob,
    MemoryRetrievalAudit,
    UserProfile,
)
from app.database.session import get_db
from app.memory.consolidation import MemoryConsolidator
from app.memory.embeddings import EmbeddingService
from app.memory.retrieval import MemoryRetrievalService
from app.memory.schemas import (
    ConsolidationRead,
    EpisodeRead,
    MemoryCreate,
    MemoryDetail,
    MemoryDiagnosticsRead,
    LearningBridgeRead,
    MemoryProcessingJobRead,
    MemoryRead,
    MemorySearchResult,
    MemoryUpdate,
    RecommendationOutcomeCreate,
    RecommendationOutcomeRead,
)
from app.memory.service import MemoryService
from app.memory.learning_bridge import LearningBridgeService
from app.recommendations import service as recommendation_service


router = APIRouter(prefix="/memories", tags=["memories"])


def _services(settings: Settings):
    gateway = AIGateway(settings)
    embeddings = EmbeddingService(settings, gateway)
    return MemoryService(embeddings), MemoryRetrievalService(settings, embeddings), MemoryConsolidator(settings, embeddings)


@router.get("", response_model=list[MemoryRead])
def list_memories(
    include_inactive: bool = False,
    domain: str | None = Query(default=None, max_length=60),
    memory_type: str | None = Query(default=None, max_length=60),
    status_filter: str | None = Query(default=None, alias="status", max_length=40),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    service, _, _ = _services(settings)
    return service.list(
        db,
        user,
        include_inactive=include_inactive,
        domain=domain,
        memory_type=memory_type,
        status_filter=status_filter,
    )


@router.post("", response_model=MemoryRead)
def create_memory(
    payload: MemoryCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    service, _, _ = _services(settings)
    result = service.create_explicit(db, user, payload, request_id=idempotency_key or str(uuid4()))
    db.commit()
    return result


@router.get("/search", response_model=list[MemorySearchResult])
def search_memories(
    q: str = Query(min_length=1, max_length=1000),
    domain: str | None = Query(default=None, max_length=60),
    limit: int | None = Query(default=None, ge=1, le=20),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _, retrieval, _ = _services(settings)
    result = retrieval.search_memories(db, user, q, domain=domain, limit=limit, request_id=str(uuid4()))
    db.commit()
    return result


@router.get("/episodes", response_model=list[EpisodeRead])
def list_episodes(
    domain: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    query = select(Episode).where(Episode.user_id == user.id, Episode.status == "active")
    if domain:
        query = query.where(Episode.domain == domain)
    rows = list(db.scalars(query.order_by(Episode.end_at.desc()).limit(limit)).all())
    return [EpisodeRead.model_validate(row) for row in rows]


@router.post("/consolidate", response_model=ConsolidationRead)
def consolidate_memories(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    _, _, consolidator = _services(settings)
    result = consolidator.consolidate_user(db, user)
    db.commit()
    return result


@router.get("/outcomes", response_model=list[RecommendationOutcomeRead])
def list_outcomes(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    return recommendation_service.list_outcomes(db, user, limit=limit)


@router.post("/outcomes", response_model=RecommendationOutcomeRead)
def record_outcome(payload: RecommendationOutcomeCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    result = recommendation_service.record_outcome(db, user, payload)
    db.commit()
    return result


@router.get("/jobs", response_model=list[MemoryProcessingJobRead])
def list_memory_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    rows = list(
        db.scalars(
            select(MemoryProcessingJob)
            .where(MemoryProcessingJob.user_id == user.id)
            .order_by(MemoryProcessingJob.created_at.desc())
            .limit(limit)
        ).all()
    )
    return [MemoryProcessingJobRead.model_validate(row) for row in rows]


@router.get("/diagnostics", response_model=MemoryDiagnosticsRead)
def memory_diagnostics(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    memory_counts = dict(
        db.execute(
            select(MemoryItem.status, func.count(MemoryItem.id))
            .where(MemoryItem.user_id == user.id)
            .group_by(MemoryItem.status)
        ).all()
    )
    job_counts = dict(
        db.execute(
            select(MemoryProcessingJob.status, func.count(MemoryProcessingJob.id))
            .where(MemoryProcessingJob.user_id == user.id)
            .group_by(MemoryProcessingJob.status)
        ).all()
    )
    retrieval_count, average_ms = db.execute(
        select(
            func.count(MemoryRetrievalAudit.id),
            func.coalesce(func.avg(MemoryRetrievalAudit.duration_ms), 0),
        ).where(MemoryRetrievalAudit.user_id == user.id)
    ).one()
    degraded = db.scalar(
        select(func.count(MemoryRetrievalAudit.id)).where(
            MemoryRetrievalAudit.user_id == user.id,
            MemoryRetrievalAudit.degraded.is_(True),
        )
    )
    embedding_calls = int(
        db.scalar(select(func.count(AIActionAudit.id)).where(AIActionAudit.user_id == user.id, AIActionAudit.capability == "EMBEDDING")) or 0
    )
    curator_calls = int(
        db.scalar(select(func.count(AIActionAudit.id)).where(AIActionAudit.user_id == user.id, AIActionAudit.skill_name == "memory-curator", AIActionAudit.capability != "EMBEDDING")) or 0
    )
    estimated_cost = float(
        db.scalar(select(func.coalesce(func.sum(AIActionAudit.estimated_cost), 0)).where(AIActionAudit.user_id == user.id, AIActionAudit.skill_name == "memory-curator")) or 0
    )
    return MemoryDiagnosticsRead(
        active_memories=int(memory_counts.get("active", 0)),
        candidate_memories=int(memory_counts.get("candidate", 0) + memory_counts.get("uncertain", 0)),
        contradicted_memories=int(memory_counts.get("contradicted", 0)),
        forgotten_memories=int(memory_counts.get("forgotten", 0)),
        evidence_records=int(db.scalar(select(func.count(MemoryEvidence.id)).where(MemoryEvidence.user_id == user.id)) or 0),
        episodes=int(db.scalar(select(func.count(Episode.id)).where(Episode.user_id == user.id)) or 0),
        pending_jobs=int(job_counts.get("pending", 0) + job_counts.get("running", 0)),
        failed_jobs=int(job_counts.get("failed", 0)),
        retrieval_count=int(retrieval_count or 0),
        average_retrieval_ms=round(float(average_ms or 0), 2),
        degraded_retrievals=int(degraded or 0),
        embedding_calls=embedding_calls,
        curator_calls=curator_calls,
        estimated_ai_cost=round(estimated_cost, 6),
    )


@router.post("/learning-bridge/refresh", response_model=LearningBridgeRead)
def refresh_learning_bridge(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = LearningBridgeService().refresh(db, user)
    db.commit()
    return result


@router.get("/{memory_id}", response_model=MemoryDetail)
def get_memory(memory_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    service, _, _ = _services(settings)
    return service.detail(db, user, memory_id)


@router.patch("/{memory_id}", response_model=MemoryRead)
def update_memory(memory_id: str, payload: MemoryUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    service, _, _ = _services(settings)
    result = service.update(db, user, memory_id, payload, request_id=str(uuid4()))
    db.commit()
    return result


@router.post("/{memory_id}/pin", response_model=MemoryRead)
def pin_memory(memory_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    service, _, _ = _services(settings)
    result = service.pin(db, user, memory_id, True)
    db.commit()
    return result


@router.post("/{memory_id}/unpin", response_model=MemoryRead)
def unpin_memory(memory_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    service, _, _ = _services(settings)
    result = service.pin(db, user, memory_id, False)
    db.commit()
    return result


@router.post("/{memory_id}/confirm", response_model=MemoryRead)
def confirm_memory(memory_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    service, _, _ = _services(settings)
    result = service.confirm(db, user, memory_id)
    db.commit()
    return result


@router.post("/{memory_id}/forget", response_model=MemoryRead)
def forget_memory(memory_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    service, _, _ = _services(settings)
    result = service.forget(db, user, memory_id)
    db.commit()
    return result
