from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.core.auth import AuthTokenError, verify_supabase_jwt
from app.core.config import Settings, get_settings
from app.database.models import UserProfile
from app.database.session import get_db


DEVELOPMENT_USER_EMAIL = "user@life-os.local"
DEVELOPMENT_AUTH_SUBJECT = "development:user@life-os.local"


def set_request_db_context(db: Session, *, auth_subject: str | None = None, email: str | None = None, user_id: str | None = None, worker: bool = False) -> None:
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    if auth_subject:
        db.execute(text("select set_config('app.auth_subject', :value, true)"), {"value": auth_subject})
    if email:
        db.execute(text("select set_config('app.user_email', :value, true)"), {"value": email})
    if user_id:
        db.execute(text("select set_config('app.user_id', :value, true)"), {"value": user_id})
    if worker:
        db.execute(text("select set_config('app.worker', 'true', true)"))


def get_or_create_user(db: Session, email: str = DEVELOPMENT_USER_EMAIL, auth_subject: str | None = DEVELOPMENT_AUTH_SUBJECT) -> UserProfile:
    if auth_subject:
        set_request_db_context(db, auth_subject=auth_subject, email=email)
    user = db.query(UserProfile).filter(or_(UserProfile.auth_subject == auth_subject, UserProfile.email == email)).one_or_none()
    if user is not None:
        if auth_subject and user.auth_subject is None:
            user.auth_subject = auth_subject
            db.commit()
            db.refresh(user)
        set_request_db_context(db, auth_subject=user.auth_subject or auth_subject, email=user.email, user_id=user.id)
        return user

    user = UserProfile(email=email, auth_subject=auth_subject, display_name="Life OS User")
    db.add(user)
    db.commit()
    db.refresh(user)
    set_request_db_context(db, auth_subject=user.auth_subject, email=user.email, user_id=user.id)
    return user


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserProfile:
    token = _bearer_token(authorization)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    if settings.development_auth_enabled:
        if token != settings.development_auth_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid development token.")
        return get_or_create_user(db)

    if settings.supabase_jwt_secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase JWT validation is not configured.",
        )

    try:
        verified = verify_supabase_jwt(
            token,
            secret=settings.supabase_jwt_secret,
            expected_issuer=settings.expected_supabase_issuer,
            expected_audience=settings.supabase_jwt_audience,
        )
    except AuthTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token.") from None

    allowed = settings.authorized_subject_set
    if allowed and verified.subject not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This Life OS instance is private.")

    email = verified.email or f"{verified.subject}@supabase.local"
    set_request_db_context(db, auth_subject=verified.subject, email=email)
    user = (
        db.query(UserProfile)
        .filter(or_(UserProfile.auth_subject == verified.subject, UserProfile.email == email))
        .one_or_none()
    )
    if user is None:
        user = UserProfile(email=email, auth_subject=verified.subject, display_name="Life OS User")
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.auth_subject is None:
        user.auth_subject = verified.subject
        db.commit()
        db.refresh(user)
    set_request_db_context(db, auth_subject=verified.subject, email=user.email, user_id=user.id)
    return user
