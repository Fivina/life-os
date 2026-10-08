from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.database.models import UserProfile
from app.decision.gateway import DecisionGateway


router = APIRouter(prefix="/decision", tags=["decision"])


@router.get("/providers")
def provider_health(
    settings: Settings = Depends(get_settings),
    _user: UserProfile = Depends(get_current_user),
) -> dict:
    gateway = DecisionGateway(settings)
    return {
        "routing_mode": settings.decision_routing_mode,
        "routing_policy_version": settings.decision_routing_policy_version,
        "providers": gateway.provider_health(),
    }
