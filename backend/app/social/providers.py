from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.social.schemas import DiscoveryContext, NormalizedOpportunity, OpportunityType


class OpportunitySource(ABC):
    source_id: str
    supported_categories: tuple[OpportunityType, ...]

    @abstractmethod
    def discover(self, context: DiscoveryContext) -> list[dict[str, Any]]: ...

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> NormalizedOpportunity: ...

    def health(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "status": "READY"}


class FakeOpportunitySource(OpportunitySource):
    source_id = "fake"
    supported_categories = tuple(OpportunityType)

    def __init__(self, rows: list[dict[str, Any]] | None = None, *, fail: bool = False):
        self.rows = rows or []
        self.fail = fail

    def discover(self, context: DiscoveryContext) -> list[dict[str, Any]]:
        if self.fail:
            raise RuntimeError("Fake source failure")
        return self.rows[: context.max_results]

    def normalize(self, raw: dict[str, Any]) -> NormalizedOpportunity:
        return NormalizedOpportunity.model_validate({"provider": self.source_id, **raw})


class TicketmasterOpportunitySource(OpportunitySource):
    """Bounded Discovery API v2 adapter. It performs discovery only, never commerce."""

    source_id = "ticketmaster"
    supported_categories = (
        OpportunityType.concert,
        OpportunityType.football,
        OpportunityType.sport,
        OpportunityType.festival,
        OpportunityType.exhibition,
        OpportunityType.other,
    )

    def __init__(self, api_key: str, *, base_url: str = "https://app.ticketmaster.com/discovery/v2", timeout_seconds: float = 10):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def discover(self, context: DiscoveryContext) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "apikey": self.api_key,
            "size": min(context.max_results, 100),
            "sort": "date,asc",
            "startDateTime": context.window_start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDateTime": context.window_end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if context.city:
            params["city"] = context.city
        if context.country_code:
            params["countryCode"] = context.country_code.upper()
        if context.categories:
            names = {_ticketmaster_classification(item) for item in context.categories}
            params["classificationName"] = ",".join(sorted(name for name in names if name))
        request = Request(f"{self.base_url}/events.json?{urlencode(params)}", headers={"Accept": "application/json", "User-Agent": "LifeOS/1.8C"})
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - fixed configured provider URL
            payload = json.loads(response.read().decode("utf-8"))
        return list(payload.get("_embedded", {}).get("events", []))[: context.max_results]

    def normalize(self, raw: dict[str, Any]) -> NormalizedOpportunity:
        dates = raw.get("dates") or {}
        start = dates.get("start") or {}
        raw_start = start.get("dateTime")
        if not raw_start:
            raise ValueError("Ticketmaster event has no concrete start date-time")
        venues = (raw.get("_embedded") or {}).get("venues") or []
        venue = venues[0] if venues else {}
        classifications = raw.get("classifications") or []
        segment = ((classifications[0] if classifications else {}).get("segment") or {}).get("name", "")
        genre = ((classifications[0] if classifications else {}).get("genre") or {}).get("name", "")
        prices = raw.get("priceRanges") or []
        price = prices[0] if prices else {}
        attractions = (raw.get("_embedded") or {}).get("attractions") or []
        return NormalizedOpportunity(
            provider=self.source_id,
            external_id=str(raw["id"]),
            opportunity_type=_ticketmaster_type(segment, genre),
            title=str(raw.get("name") or "Untitled event"),
            description=(raw.get("info") or raw.get("pleaseNote")),
            starts_at=datetime.fromisoformat(raw_start.replace("Z", "+00:00")),
            timezone=venue.get("timezone") or "UTC",
            venue=venue.get("name"),
            city=(venue.get("city") or {}).get("name"),
            region=(venue.get("state") or {}).get("name"),
            country_code=(venue.get("country") or {}).get("countryCode"),
            source_url=raw.get("url"),
            cost_min=price.get("min"),
            cost_max=price.get("max"),
            currency=price.get("currency"),
            pricing_source="ticketmaster" if prices else None,
            status="CANCELLED" if (dates.get("status") or {}).get("code") == "cancelled" else "ACTIVE",
            tags=tuple(filter(None, [segment, genre])),
            entities=tuple({"type": "attraction", "id": item.get("id"), "name": item.get("name")} for item in attractions[:10]),
            source_updated_at=datetime.now(UTC),
            metadata={"locale": raw.get("locale"), "test": bool(raw.get("test"))},
        )


def _ticketmaster_classification(value: OpportunityType) -> str:
    if value == OpportunityType.concert:
        return "music"
    if value in {OpportunityType.football, OpportunityType.sport}:
        return "sports"
    return "arts & theatre" if value in {OpportunityType.exhibition, OpportunityType.other} else ""


def _ticketmaster_type(segment: str, genre: str) -> OpportunityType:
    value = f"{segment} {genre}".lower()
    if "music" in value:
        return OpportunityType.concert
    if "football" in value or "soccer" in value:
        return OpportunityType.football
    if "sport" in value:
        return OpportunityType.sport
    if "festival" in value:
        return OpportunityType.festival
    if "museum" in value or "exhibition" in value:
        return OpportunityType.exhibition
    return OpportunityType.other

