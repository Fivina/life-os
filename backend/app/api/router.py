from fastapi import APIRouter

from app.api.routes_actions import router as actions_router
from app.api.routes_assistant import router as assistant_router
from app.api.routes_auth import router as auth_router
from app.api.routes_calendar import router as calendar_router
from app.api.routes_commitments import router as commitments_router
from app.api.routes_day import router as day_router
from app.api.routes_decision import router as decision_router
from app.api.routes_export import router as export_router
from app.api.routes_fitness import router as fitness_router
from app.api.routes_finance import router as finance_router
from app.api.routes_feedback import router as feedback_router
from app.api.routes_goals import router as goals_router
from app.api.routes_health import router as health_router
from app.api.routes_home import router as home_router
from app.api.routes_kitchen import router as kitchen_router
from app.api.routes_learning import router as learning_router
from app.api.routes_memory import router as memory_router
from app.api.routes_media import router as media_router
from app.api.routes_notifications import router as notifications_router
from app.api.routes_personal_model import router as personal_model_router
from app.api.routes_plans import router as plans_router
from app.api.routes_push import router as push_router
from app.api.routes_receipts import router as receipts_router
from app.api.routes_recommendations import router as recommendations_router
from app.api.routes_state import router as state_router
from app.api.routes_strategy import router as strategy_router
from app.api.routes_communication import router as communication_router
from app.api.routes_realtime import router as realtime_router
from app.api.routes_workspaces import router as workspaces_router
from app.api.routes_notebook import router as notebook_router
from app.api.routes_standing_calendar import router as standing_calendar_router
from app.api.routes_movies import router as movies_router
from app.api.routes_social import router as social_router
from app.api.routes_self_core import router as self_core_router
from app.api.routes_quick_capture import router as quick_capture_router
from app.api.routes_review import router as review_router
from app.api.routes_intelligence_settings import router as intelligence_settings_router
from app.api.routes_integrations import router as integrations_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(assistant_router)
api_router.include_router(state_router)
api_router.include_router(strategy_router)
api_router.include_router(communication_router)
api_router.include_router(realtime_router)
api_router.include_router(workspaces_router)
api_router.include_router(notebook_router)
api_router.include_router(standing_calendar_router)
api_router.include_router(movies_router)
api_router.include_router(social_router)
api_router.include_router(self_core_router)
api_router.include_router(quick_capture_router)
api_router.include_router(review_router)
api_router.include_router(intelligence_settings_router)
api_router.include_router(integrations_router)
api_router.include_router(commitments_router)
api_router.include_router(actions_router)
api_router.include_router(calendar_router)
api_router.include_router(plans_router)
api_router.include_router(day_router)
api_router.include_router(decision_router)
api_router.include_router(fitness_router)
api_router.include_router(finance_router)
api_router.include_router(feedback_router)
api_router.include_router(goals_router)
api_router.include_router(learning_router)
api_router.include_router(home_router)
api_router.include_router(kitchen_router)
api_router.include_router(personal_model_router)
api_router.include_router(memory_router)
api_router.include_router(media_router)
api_router.include_router(recommendations_router)
api_router.include_router(push_router)
api_router.include_router(receipts_router)
api_router.include_router(notifications_router)
api_router.include_router(export_router)
