import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


class ObservabilityAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("request_id", "-")
        extra.setdefault("user_id", "-")
        extra.setdefault("world_revision", "-")
        extra.setdefault("planner_version", "-")
        extra.setdefault("event_type", "-")
        return msg, kwargs


def get_logger(name: str) -> ObservabilityAdapter:
    return ObservabilityAdapter(logging.getLogger(name), {})
