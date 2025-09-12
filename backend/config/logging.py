"""
Structured JSON logging configuration with request-context injection.

Usage:
    from logging_config import configure_logging
    configure_logging()
"""
import logging
import json
import time
from typing import Any, Dict

from utils.request_context import get_request_context


class RequestContextFilter(logging.Filter):
    """Logging filter that injects request-scoped keys (request_id, user_id, tenant_id)."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = get_request_context() or {}
        # Attach keys to the record so the formatter can include them
        record.request_id = ctx.get("request_id")
        record.user_id = ctx.get("user_id")
        record.tenant_id = ctx.get("tenant_id")
        return True


class JSONFormatter(logging.Formatter):
    """Simple JSON formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        # Base payload
        payload: Dict[str, Any] = {
            "timestamp": int(time.time()),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "line": record.lineno,
        }

        # Attach request-related fields if present
        for k in ("request_id", "user_id", "tenant_id"):
            val = getattr(record, k, None)
            if val is not None:
                payload[k] = val

        # Attach exc info if any
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        # Attach any extra attrs passed via logger.extra
        extras = {}
        for key, val in record.__dict__.items():
            if key not in (
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
                "request_id",
                "user_id",
                "tenant_id",
            ):
                try:
                    json.dumps({key: val})
                    extras[key] = val
                except Exception:
                    extras[key] = repr(val)
        if extras:
            payload["extra"] = extras

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """
    Set up root logger with JSONFormatter and RequestContextFilter.
    Call early during app startup.
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Avoid adding duplicate handlers when called multiple times
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(JSONFormatter())
        root.addHandler(handler)

    # Ensure the filter exists once
    if not any(isinstance(f, RequestContextFilter) for f in root.filters):
        root.addFilter(RequestContextFilter())