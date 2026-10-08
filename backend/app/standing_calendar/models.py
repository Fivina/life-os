from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FixtureSnapshotCache(Base):
    """Backend-only cache of normalized public fixture data."""

    __tablename__ = "fixture_snapshot_cache"

    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    team_id: Mapped[str] = mapped_column(String(80), nullable=False)
    base_url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fixtures_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
