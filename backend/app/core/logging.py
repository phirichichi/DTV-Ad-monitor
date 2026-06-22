#logging.py 
import json
import logging
import sys
import time
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class JsonFormatter(logging.Formatter):
    """
    Structured JSON log formatter for API and worker logs.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt),
        }

        standard_extra_fields = [
            "request_id",
            "path",
            "method",
            "status_code",
            "duration_ms",
            "channel_id",
            "channel_name",
            "advertisement_id",
            "advertiser_id",
            "detection_id",
            "detection_status",
            "confidence_score",
            "match_source",
            "save_path",
            "stream_url",
            "worker_name",
        ]

        for field in standard_extra_fields:
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def setup_logging() -> None:
    """
    Configure root logging once at startup.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduce noisy third-party logs if needed
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs request method, path, response status, and latency.
    """

    async def dispatch(self, request: Request, call_next):
        logger = logging.getLogger("dtv.request")
        start_time = time.perf_counter()

        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(
                "request_completed",
                extra={
                    "request_id": request.headers.get("x-request-id", "-"),
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": getattr(response, "status_code", 500),
                    "duration_ms": duration_ms,
                },
            )