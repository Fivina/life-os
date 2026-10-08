from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.workspaces.schemas import ActiveWorkspaceRead, workspace_to_read
from app.workspaces.service import ActiveWorkspaceService


router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[ActiveWorkspaceRead])
def list_workspaces(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return [workspace_to_read(row) for row in ActiveWorkspaceService().list_active(db, user)]


@router.get("/foreground", response_model=ActiveWorkspaceRead | None)
def foreground_workspace(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    row = ActiveWorkspaceService().get_foreground_workspace(db, user)
    return workspace_to_read(row) if row else None


@router.get("/{workspace_id}", response_model=ActiveWorkspaceRead)
def get_workspace(workspace_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    row = ActiveWorkspaceService().get_workspace(db, user, workspace_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return workspace_to_read(row)


@router.post("/{workspace_id}/resume", response_model=ActiveWorkspaceRead)
def resume_workspace(workspace_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    try:
        row = ActiveWorkspaceService().resume_workspace(db, user, workspace_id, foreground=True)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    return workspace_to_read(row)
