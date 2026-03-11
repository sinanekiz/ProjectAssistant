from __future__ import annotations

import json
import logging
import sys
from collections import deque
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings

_RESERVED_KEYS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
}

_recent_logs: deque[dict[str, Any]] = deque(maxlen=200)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = build_log_payload(record)
        return json.dumps(payload, default=str)


class InMemoryLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _recent_logs.appendleft(build_log_payload(record))


def build_log_payload(record: logging.LogRecord) -> dict[str, Any]:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
    }
    extras = {key: value for key, value in record.__dict__.items() if key not in _RESERVED_KEYS}
    if extras:
        payload["extra"] = extras
    if record.exc_info:
        payload["exception"] = logging.Formatter().formatException(record.exc_info)
    return payload


def configure_logging() -> None:
    settings = get_settings()
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level.upper())
    root_logger.handlers.clear()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(JsonFormatter())

    memory_handler = InMemoryLogHandler()
    memory_handler.setLevel(logging.INFO)

    root_logger.addHandler(stream_handler)
    root_logger.addHandler(memory_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def get_recent_logs(limit: int = 50) -> list[dict[str, Any]]:
    return list(_recent_logs)[:limit]
