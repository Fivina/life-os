from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


Scope = Literal["tenant", "installation"]
Environment = Literal["sandbox", "production"]
ErrorCode = Literal["not_configured", "client_id_required", "test_unavailable", "authentication_failed",
                    "rate_limited", "provider_unavailable", "provider_rejected", "invalid_response", "timeout", "network_error"]


class CredentialWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr = Field(min_length=20, max_length=512)
    scope: Scope = "tenant"
    environment: Environment = "sandbox"
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    region: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    client_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{24}$")

    @field_validator("api_key")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        from app.intelligence_settings.provider_credentials import SAFE_KEY_PATTERN
        if not SAFE_KEY_PATTERN.fullmatch(value.get_secret_value()):
            raise ValueError("Invalid credential format.")
        return value


class IntegrationStatus(BaseModel):
    id: str
    name: str
    kind: Literal["api", "public", "import"]
    configured: bool
    credential_management_available: bool
    scope: Scope
    environment: Environment
    capabilities: list[str]
    last_success_at: datetime | None = None
    last_attempt_at: datetime | None = None
    error_code: ErrorCode | None = None
    language: str | None = None
    region: str | None = None
    client_id: str | None = None
    attribution: str | None = None


class IntegrationList(BaseModel):
    providers: list[IntegrationStatus]
    credential_management_available: bool


class CredentialResult(BaseModel):
    provider: str
    configured: bool
    scope: Scope


class ConnectionTestResult(CredentialResult):
    success: bool
    error_code: ErrorCode | None = None
    last_attempt_at: datetime
    last_success_at: datetime | None = None
