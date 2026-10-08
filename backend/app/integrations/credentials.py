from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models import UserProfile
from app.intelligence_settings.provider_credentials import ProviderSecretStore, SAFE_KEY_PATTERN
from app.integrations.registry import SECRET_PROVIDERS


def installation_admin(settings, user: UserProfile) -> bool:
    configured = getattr(settings, "integration_installation_admin_subjects", "")
    subjects = {value.strip() for value in configured.split(",") if value.strip()}
    return bool(user.auth_subject and user.auth_subject in subjects)


def authorize_scope(settings, user: UserProfile, scope: str) -> None:
    if scope not in {"tenant", "installation"}:
        raise HTTPException(422, "Invalid credential scope.")
    if scope == "installation" and not installation_admin(settings, user):
        raise HTTPException(403, "Installation credential management requires an authorized installation administrator.")


class IntegrationSecretStore(ProviderSecretStore):
    """Extends the existing Vault functions; tenant OpenAI has one existing key.

    Connection methods are backend-only primitives. The banking service must prove
    connection ownership before calling them; no generic settings route exposes them.
    """
    def __init__(self, settings):
        self.settings = settings

    @staticmethod
    def _validate_provider(provider: str) -> None:
        if provider not in SECRET_PROVIDERS:
            raise HTTPException(404, "Unsupported integration provider.")

    def available(self, db: Session) -> bool:
        if db.bind is None or db.bind.dialect.name != "postgresql":
            return False
        try:
            return bool(db.scalar(text("""
                SELECT to_regprocedure('private.lifeos_integration_secret_name(text,text,text,text)') IS NOT NULL
                  AND to_regprocedure('private.set_lifeos_scoped_provider_secret(text,text,text,text,text)') IS NOT NULL
                  AND to_regprocedure('private.get_lifeos_scoped_provider_secret(text,text,text,text)') IS NOT NULL
                  AND to_regprocedure('private.has_lifeos_scoped_provider_secret(text,text,text,text)') IS NOT NULL
                  AND to_regprocedure('private.delete_lifeos_scoped_provider_secret(text,text,text,text)') IS NOT NULL
            """)))
        except SQLAlchemyError as exc:
            raise self._vault_error(exc) from None

    def provider_available(self, db: Session, provider: str) -> bool:
        self._validate_provider(provider)
        # Old OpenAI remains readable before the additive integration migration.
        if provider == "openai":
            return ProviderSecretStore.available(db)
        return self.available(db)

    def _scoped(self, db: Session, user: UserProfile, provider: str, scope: str,
                operation: str, secret: str | None = None, connection_id: str | None = None):
        self._validate_provider(provider)
        if operation not in {"get", "set", "has", "delete"}:
            raise HTTPException(422, "Invalid credential operation.")
        if scope == "connection":
            if provider != "plaid":
                raise HTTPException(422, "Unsupported connection credential provider.")
            try:
                if str(UUID(str(connection_id))) != connection_id or str(UUID(user.id)) != user.id:
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise HTTPException(422, "Invalid connection credential identity.") from None
        else:
            authorize_scope(self.settings, user, scope)
            if connection_id is not None:
                raise HTTPException(422, "Invalid credential identity.")
        if operation == "set" and (secret is None or not SAFE_KEY_PATTERN.fullmatch(secret)):
            raise HTTPException(422, "Invalid credential format.")
        if not self.available(db):
            raise HTTPException(503, "Hosted secret storage is unavailable.")
        try:
            self._set_user_context(db, user)
            # Always reset the local flag to avoid privileges carrying into later calls.
            db.execute(text("SELECT set_config('app.integration_installation_admin', :value, true)"),
                       {"value": "true" if scope == "installation" and installation_admin(self.settings, user) else "false"})
            params = {"user_id": user.id, "scope": scope, "provider": provider, "connection_id": connection_id}
            args = ":user_id, :scope, :provider, :connection_id"
            if operation == "set":
                params["secret"] = secret
                args += ", :secret"
            return db.scalar(text(f"SELECT private.{operation}_lifeos_scoped_provider_secret({args})"), params)
        except SQLAlchemyError as exc:
            raise self._vault_error(exc) from None

    def configured_scoped(self, db, user, provider, scope="tenant") -> bool:
        authorize_scope(self.settings, user, scope)
        if scope == "tenant":
            return self.configured(db, user, provider)
        if not self.available(db):
            return False
        return bool(self._scoped(db, user, provider, scope, "has"))

    def get_scoped(self, db, user, provider, scope="tenant") -> str:
        authorize_scope(self.settings, user, scope)
        secret = self.get(db, user, provider) if scope == "tenant" else self._scoped(db, user, provider, scope, "get")
        if not secret:
            raise HTTPException(409, "Configure this integration credential first.")
        return str(secret)

    def save_scoped(self, db, user, provider, secret, scope="tenant") -> None:
        authorize_scope(self.settings, user, scope)
        if scope == "tenant":
            self.save(db, user, provider, secret)
        else:
            self._scoped(db, user, provider, scope, "set", secret)

    def delete_scoped(self, db, user, provider, scope="tenant") -> None:
        authorize_scope(self.settings, user, scope)
        if scope == "tenant":
            self.delete(db, user, provider)
        else:
            self._scoped(db, user, provider, scope, "delete")

    def save_connection_token(self, db, user, connection_id: str, token: str) -> None:
        self._scoped(db, user, "plaid", "connection", "set", token, connection_id)

    def get_connection_token(self, db, user, connection_id: str) -> str:
        secret = self._scoped(db, user, "plaid", "connection", "get", connection_id=connection_id)
        if not secret:
            raise HTTPException(409, "Connection credential is unavailable.")
        return str(secret)

    def delete_connection_token(self, db, user, connection_id: str) -> None:
        self._scoped(db, user, "plaid", "connection", "delete", connection_id=connection_id)

    def fixture_runtime_key(self, db: Session, user: UserProfile, scope: str) -> str | None:
        """Read the selected sports source only; never grant credential management.

        Installation lookup has a separate fixed-provider, backend-only SQL function.
        Ordinary users do not gain installation admin rights through this read path.
        Subsequent provider calls use the selected Vault source exclusively.
        """
        if scope == "tenant":
            return self.get_scoped(db, user, "api-football") if self.configured_scoped(db, user, "api-football") else None
        if scope != "installation":
            raise HTTPException(422, "Invalid fixture credential scope.")
        if db.bind is None or db.bind.dialect.name != "postgresql":
            return None
        try:
            ready = db.scalar(text("SELECT to_regprocedure('private.get_lifeos_fixture_installation_secret()') IS NOT NULL"))
            if not ready:
                raise HTTPException(503, "Hosted fixture secret storage is not ready.")
            secret = db.scalar(text("SELECT private.get_lifeos_fixture_installation_secret()"))
            return str(secret) if secret else None
        except SQLAlchemyError as exc:
            raise self._vault_error(exc) from None
