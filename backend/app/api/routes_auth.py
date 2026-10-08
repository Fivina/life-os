from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.database.models import UserProfile

router = APIRouter(tags=["auth"])


@router.get("/me")
def me(user: UserProfile = Depends(get_current_user)) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "world_revision": user.world_revision,
        "version": user.version,
    }
