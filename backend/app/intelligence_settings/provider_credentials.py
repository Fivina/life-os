from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models import UserProfile


PROVIDERS = {"openai", "gemini", "jev"}
SAFE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]{20,512}$")
VAULT_FUNCTIONS_READY = text(
    "SELECT to_regprocedure('private.has_lifeos_provider_secret(text,text)') IS NOT NULL"
)
JEV_VAULT_PROVIDER_READY = text("""
    SELECT CASE
        WHEN to_regprocedure('private.set_lifeos_provider_secret(text,text,text)') IS NULL THEN false
        ELSE position('jev' IN pg_get_functiondef(
            to_regprocedure('private.set_lifeos_provider_secret(text,text,text)')
        )) > 0
    END
""")


class ProviderSecretStore:
    """Backend-only access to per-user secrets held by Supabase Vault."""

    @staticmethod
    def _set_user_context(db: Session, user: UserProfile) -> None:
        db.execute(
            text("SELECT set_config('app.user_id', :user_id, true)"),
            {"user_id": user.id},
        )

    @staticmethod
    def available(db: Session) -> bool:
        if db.bind is None or db.bind.dialect.name != "postgresql":
            return False
        return bool(db.scalar(VAULT_FUNCTIONS_READY))

    def configured(self, db: Session, user: UserProfile, provider: str) -> bool:
        self._validate_provider(provider)
        if not self.provider_available(db, provider):
            return False
        try:
            self._set_user_context(db, user)
            return bool(db.scalar(
                text("SELECT private.has_lifeos_provider_secret(:user_id, :provider)"),
                {"user_id": user.id, "provider": provider},
            ))
        except SQLAlchemyError as exc:
            raise self._vault_error(exc) from None

    def get(self, db: Session, user: UserProfile, provider: str) -> str:
        self._validate_provider(provider)
        if not self.provider_available(db, provider):
            raise HTTPException(status_code=503, detail="Hosted secret storage is not ready. Complete the Supabase security setup first.")
        try:
            self._set_user_context(db, user)
            secret = db.scalar(
                text("SELECT private.get_lifeos_provider_secret(:user_id, :provider)"),
                {"user_id": user.id, "provider": provider},
            )
        except SQLAlchemyError as exc:
            raise self._vault_error(exc) from None
        if not secret:
            provider_name = {"openai": "OpenAI", "gemini": "Google Gemini", "jev": "Jev"}[provider]
            usage = "Jev decisions" if provider == "jev" else "this agent"
            raise HTTPException(status_code=409, detail=f"Add a {provider_name} API key in Settings before using {usage}.")
        return str(secret)

    def save(self, db: Session, user: UserProfile, provider: str, api_key: str) -> None:
        self._validate_provider(provider)
        if not SAFE_KEY_PATTERN.fullmatch(api_key):
            raise HTTPException(status_code=422, detail="The API key format is invalid.")
        if not self.provider_available(db, provider):
            raise HTTPException(status_code=503, detail="Hosted secret storage is not ready. Complete the Supabase security setup first.")
        try:
            self._set_user_context(db, user)
            db.execute(
                text("SELECT private.set_lifeos_provider_secret(:user_id, :provider, :secret)"),
                {"user_id": user.id, "provider": provider, "secret": api_key},
            )
        except SQLAlchemyError as exc:
            raise self._vault_error(exc) from None

    def delete(self, db: Session, user: UserProfile, provider: str) -> None:
        self._validate_provider(provider)
        if not self.provider_available(db, provider):
            raise HTTPException(status_code=503, detail="Hosted secret storage is not ready. Complete the Supabase security setup first.")
        try:
            self._set_user_context(db, user)
            db.execute(
                text("SELECT private.delete_lifeos_provider_secret(:user_id, :provider)"),
                {"user_id": user.id, "provider": provider},
            )
        except SQLAlchemyError as exc:
            raise self._vault_error(exc) from None

    @staticmethod
    def _validate_provider(provider: str) -> None:
        if provider not in PROVIDERS:
            raise HTTPException(status_code=404, detail="Unsupported provider.")

    def provider_available(self, db: Session, provider: str) -> bool:
        self._validate_provider(provider)
        if not self.available(db):
            return False
        if provider == "jev":
            try:
                return bool(db.scalar(JEV_VAULT_PROVIDER_READY))
            except SQLAlchemyError:
                return False
        return True

    @staticmethod
    def _vault_error(exc: SQLAlchemyError) -> HTTPException:
        code = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if code in {"42501", "42883", "3F000"}:
            return HTTPException(
                status_code=503,
                detail="Hosted secret storage is not ready. Complete the Supabase security setup first.",
            )
        return HTTPException(status_code=503, detail="Provider secret storage is temporarily unavailable.")
