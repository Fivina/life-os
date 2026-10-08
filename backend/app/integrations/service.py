from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import text

from app.integrations.credentials import IntegrationSecretStore, authorize_scope, installation_admin
from app.integrations.models import IntegrationConfiguration
from app.integrations.provider_tests import IntegrationConnectionTester
from app.integrations.registry import PROVIDERS, provider_definition
from app.integrations.schemas import CredentialResult, ConnectionTestResult, IntegrationList, IntegrationStatus


class IntegrationService:
    def __init__(self, settings, *, store=None, tester=None):
        self.settings = settings
        self.store = store if store is not None else IntegrationSecretStore(settings)
        self.tester = tester if tester is not None else IntegrationConnectionTester()

    def _owner(self, db, user, scope):
        authorize_scope(self.settings, user, scope)
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            db.execute(text("SELECT set_config('app.user_id', :value, true)"), {"value": user.id})
            db.execute(text("SELECT set_config('app.integration_installation_admin', :value, true)"),
                       {"value": "true" if scope == "installation" and installation_admin(self.settings, user) else "false"})
        return user.id if scope == "tenant" else "installation"

    def _configuration(self, db, user, provider, scope, *, create=False):
        owner = self._owner(db, user, scope)
        row = db.get(IntegrationConfiguration, (scope, owner, provider))
        if row is None and create:
            row = IntegrationConfiguration(scope=scope, owner_id=owner, provider=provider, environment="sandbox")
            db.add(row)
        return row

    def list(self, db, user, scope="tenant"):
        self._owner(db, user, scope)
        available = self.store.available(db)
        providers = []
        for definition in PROVIDERS.values():
            row = self._configuration(db, user, definition.id, scope)
            managed = definition.kind == "api"
            # Imports never claim a live connection; public integrations need no key.
            configured = self.store.configured_scoped(db, user, definition.id, scope) if managed else False
            providers.append(IntegrationStatus(
                id=definition.id, name=definition.name, kind=definition.kind,
                configured=configured, credential_management_available=available and managed,
                scope=scope, environment=row.environment if row else "sandbox",
                capabilities=list(definition.capabilities), attribution=definition.attribution,
                language=row.language if row else None, region=row.region if row else None,
                client_id=row.client_id if row else None,
                last_success_at=row.last_success_at if row else None,
                last_attempt_at=row.last_attempt_at if row else None,
                error_code=row.error_code if row else None,
            ))
        return IntegrationList(providers=providers, credential_management_available=available)

    def save(self, db, user, provider, payload):
        provider_definition(provider, require_secret=True)
        if payload.client_id is not None and provider != "plaid":
            raise HTTPException(422, "Client ID is only supported for Plaid.")
        self._owner(db, user, payload.scope)
        self.store.save_scoped(db, user, provider, payload.api_key.get_secret_value(), payload.scope)
        row = self._configuration(db, user, provider, payload.scope, create=True)
        if "environment" in payload.model_fields_set:
            row.environment = payload.environment
        # Omitted preferences survive key replacement; explicit null clears them.
        for field in ("language", "region", "client_id"):
            if field in payload.model_fields_set:
                setattr(row, field, getattr(payload, field))
        row.last_success_at = None
        row.last_attempt_at = None
        row.error_code = None
        db.flush()
        return CredentialResult(provider=provider, configured=True, scope=payload.scope)

    def delete(self, db, user, provider, scope="tenant"):
        provider_definition(provider, require_secret=True)
        self._owner(db, user, scope)
        self.store.delete_scoped(db, user, provider, scope)
        row = self._configuration(db, user, provider, scope)
        if row:
            row.last_success_at = None
            row.last_attempt_at = None
            row.error_code = None
        db.flush()
        return CredentialResult(provider=provider, configured=False, scope=scope)

    def test(self, db, user, provider, scope="tenant"):
        provider_definition(provider, require_secret=True)
        self._owner(db, user, scope)
        configured = self.store.configured_scoped(db, user, provider, scope)
        row = self._configuration(db, user, provider, scope, create=True)
        row.last_attempt_at = datetime.now(UTC)
        error = "not_configured"
        if configured:
            secret = self.store.get_scoped(db, user, provider, scope)
            error = self.tester.test(provider, secret, environment=row.environment, client_id=row.client_id)
        row.error_code = error
        if error is None:
            row.last_success_at = row.last_attempt_at
        db.flush()
        return ConnectionTestResult(provider=provider, configured=configured, scope=scope,
                                    success=error is None, error_code=error,
                                    last_attempt_at=row.last_attempt_at, last_success_at=row.last_success_at)
