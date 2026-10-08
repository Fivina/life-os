from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class IntegrationConfiguration(Base):
    """Only non-secret preferences and sanitized connection-test state."""
    __tablename__ = "integration_configurations"

    scope: Mapped[str] = mapped_column(String(20), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), primary_key=True)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, default="sandbox")
    language: Mapped[str | None] = mapped_column(String(10))
    region: Mapped[str | None] = mapped_column(String(2))
    client_id: Mapped[str | None] = mapped_column(String(128))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(40))

    __table_args__ = (
        CheckConstraint("scope IN ('tenant', 'installation')", name="ck_integration_configuration_scope"),
        CheckConstraint("environment IN ('sandbox', 'production')", name="ck_integration_configuration_environment"),
        CheckConstraint("error_code IS NULL OR error_code IN ('not_configured', 'client_id_required', 'test_unavailable', 'authentication_failed', 'rate_limited', 'provider_unavailable', 'provider_rejected', 'invalid_response', 'timeout', 'network_error')", name="ck_integration_configuration_error_code"),
        CheckConstraint("(scope = 'installation' AND owner_id = 'installation') OR (scope = 'tenant' AND owner_id <> 'installation')", name="ck_integration_configuration_owner"),
    )
