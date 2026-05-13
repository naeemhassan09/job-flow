from __future__ import annotations

import logging
from typing import Any

import structlog

from app.config import get_settings


def configure() -> None:
    level = getattr(logging, get_settings().app_log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _scrub_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def _scrub_processor(_logger: object, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    from app.observability.scrub import scrub_pii

    return scrub_pii(event_dict)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
