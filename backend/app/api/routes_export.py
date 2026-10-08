from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.database.models import (
    AIActionAudit,
    Action,
    AssistantActionProposal,
    BodyMeasurement,
    Commitment,
    Course,
    Event,
    Exercise,
    ExerciseSet,
    Exam,
    FitnessGoal,
    Ingredient,
    InventoryItem,
    InventoryLot,
    MealHistory,
    MemoryConsolidationRun,
    MemoryEvidence,
    MemoryItem,
    MemoryLearningBridgeRun,
    MemoryProcessingJob,
    MemoryRetrievalAudit,
    MemorySuppression,
    Episode,
    NotificationIntent,
    NutritionTarget,
    PatternEvidence,
    PersonalModelRefreshRun,
    PersonalModelVersion,
    Plan,
    PlanBlock,
    PreferenceEvidence,
    ProgressionState,
    PushDelivery,
    PushSubscription,
    Recipe,
    RecipeIngredient,
    RecoveryObservation,
    RecommendationOutcome,
    Recommendation,
    RecommendationOption,
    ShoppingNeed,
    ShoppingNeedItem,
    StateObservation,
    StudyRequirement,
    StudySession,
    TrainingExample,
    UserProfile,
    Workout,
    WorkoutProgram,
    WorkoutSession,
    WorkoutTemplate,
    WorkoutTemplateExercise,
    WorldRevision,
    QuickCapture,
    ReviewItem,
    UserIntelligenceSettings,
    NotebookEntry,
    ConversationThread,
    ConversationMessage,
    ConversationSummary,
)
from app.database.session import get_db

router = APIRouter(prefix="/export", tags=["export"])


EXPORT_MODELS = [
    StateObservation,
    Commitment,
    Action,
    Plan,
    PlanBlock,
    Event,
    WorldRevision,
    AssistantActionProposal,
    AIActionAudit,
    BodyMeasurement,
    WorkoutProgram,
    WorkoutTemplate,
    Workout,
    Exercise,
    WorkoutTemplateExercise,
    WorkoutSession,
    ExerciseSet,
    ProgressionState,
    RecoveryObservation,
    FitnessGoal,
    Course,
    Exam,
    StudyRequirement,
    StudySession,
    Ingredient,
    InventoryItem,
    InventoryLot,
    Recipe,
    RecipeIngredient,
    MealHistory,
    NutritionTarget,
    PreferenceEvidence,
    ShoppingNeed,
    ShoppingNeedItem,
    TrainingExample,
    PersonalModelVersion,
    PatternEvidence,
    PersonalModelRefreshRun,
    NotificationIntent,
    PushSubscription,
    PushDelivery,
    MemoryItem,
    MemoryEvidence,
    MemoryLearningBridgeRun,
    MemorySuppression,
    MemoryProcessingJob,
    MemoryRetrievalAudit,
    Episode,
    Recommendation,
    RecommendationOption,
    RecommendationOutcome,
    MemoryConsolidationRun,
    QuickCapture,
    ReviewItem,
    UserIntelligenceSettings,
    NotebookEntry,
    ConversationThread,
    ConversationMessage,
    ConversationSummary,
]


@router.get("")
def export_user_data(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)) -> dict[str, Any]:
    settings = get_settings()
    tables: dict[str, Any] = {}
    for model in EXPORT_MODELS:
        rows = db.scalars(select(model).where(model.user_id == user.id).order_by(model.created_at.asc())).all()
        if model is PushSubscription:
            tables[model.__tablename__] = [
                {
                    "id": row.id,
                    "device_label": row.device_label,
                    "status": row.status,
                    "last_success_at": row.last_success_at,
                    "last_failure_at": row.last_failure_at,
                    "failure_count": row.failure_count,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                    "version": row.version,
                }
                for row in rows
            ]
        elif model in {MemoryItem, Episode}:
            tables[model.__tablename__] = jsonable_encoder(
                [
                    {column.name: getattr(row, column.name) for column in model.__table__.columns if column.name != "embedding_vector"}
                    for row in rows
                ]
            )
        else:
            tables[model.__tablename__] = jsonable_encoder(rows)
    return {
        "manifest": {
            "export_schema_version": "life-os-export-v1",
            "exported_at": datetime.now(UTC).isoformat(),
            "app_version": settings.deployment_version,
            "environment": settings.app_env,
        },
        "user_profile": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "world_revision": user.world_revision,
            "version": user.version,
        },
        "tables": tables,
    }
