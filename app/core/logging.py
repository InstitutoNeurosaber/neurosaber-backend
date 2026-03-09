"""
Custom logging configuration for the app.
By default, uses standard Python logging.
To enable structlog-based structured logging, set ENABLE_STRUCTLOG=True in your config or environment.
"""

import json
import logging
import logging.config
import time
from typing import Any
from urllib.parse import parse_qsl

import structlog

from app.context import get_request_context, req_or_thread_id
from app.core.config import settings


def configure_logging(
    human_readable: bool = settings.HUMAN_READABLE_LOGGING,
    raw_log_level: str = settings.LOG_LEVEL,
) -> None:
    """
    Configures structlog-based structured logging for the application.

    Args:
        human_readable: If True, logs will be human-readable, otherwise JSON.
        log_level_str: The logging level as a string (e.g., "INFO", "DEBUG").
    """
    log_level = getattr(logging, raw_log_level.upper(), logging.INFO)

    shared_processors: list[structlog.Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),  # Renders stack_info if present
        structlog.processors.format_exc_info,  # Renders exc_info if present
        structlog.processors.UnicodeDecoder(),  # Decodes byte strings
        structlog.processors.TimeStamper(fmt="iso", utc=True),  # Add ISO timestamp
    ]

    # Configure structlog itself
    structlog.configure(
        processors=shared_processors
        + [
            # This must be the last processor in the chain for structlog records
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
        context_class=dict,
    )

    renderer: structlog.Processor = structlog.processors.JSONRenderer()
    if human_readable:
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )

    logging.captureWarnings(True)
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "structlog": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": renderer,
                    # These processors are applied to log records from the standard library
                    # *before* they are passed to the main `processor` above.
                    "foreign_pre_chain": [
                        structlog.stdlib.add_logger_name,
                        structlog.stdlib.add_log_level,
                        structlog.processors.TimeStamper(fmt="iso", utc=True),
                    ],
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "structlog",
                    "level": log_level,
                },
            },
            "loggers": {
                "": {
                    "handlers": ["console"],
                    "level": log_level,
                },
                "sqlalchemy": {
                    "handlers": ["console"],
                    "level": "WARN",
                    "propagate": False,
                },
                "uvicorn": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
            },
        }
    )

    # Explicitly disable uvicorn.access if middleware handles it fully
    logging.getLogger("uvicorn.access").disabled = True


class AccessLoggerMiddleware:
    def __init__(self, app):
        self.app = app
        self.logger = structlog.get_logger("app.access")
        configure_logging()

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)  # pragma: no cover

        request_info: dict[str, Any] = {
            "start_time": time.monotonic(),
            "status_code": 0,
        }

        async def capturing_send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                request_info["status_code"] = message["status"]
            elif message["type"] == "http.response.body" and message.get("body"):
                if (
                    400 <= request_info.get("status_code", 0) < 600
                ):  # Only capture error bodies
                    request_info["response_body_bytes"] = message["body"]
            await send(message)

        try:
            await self.app(scope, receive, capturing_send)
        except Exception as exc:
            request_info["status_code"] = 500
            self.logger.error(
                "unhandled_exception_in_request",
                exc_info=exc,
                path=scope.get("path", "unknown_path"),
                method=scope.get("method", "unknown_method"),
                client_ip=self._get_client_ip(scope),
            )

            raise  # Re-raise to allow FastAPI's default error handling
        finally:
            request_info["end_time"] = time.monotonic()
            self._log_access(scope, request_info)

    @staticmethod
    def _get_headers(scope: dict) -> dict:
        headers = {}
        for name, value in scope.get("headers", []):
            headers[name.decode("latin1").lower()] = value.decode("latin1")
        return headers

    @staticmethod
    def _get_query_params(scope: dict) -> dict:
        return dict(parse_qsl(scope.get("query_string", b"").decode()))

    @staticmethod
    def _get_client_ip(scope: dict) -> str:
        client: tuple[str, int] | None = scope.get("client")
        return client[0] if client else "-"

    def _log_access(self, scope, request_info: dict) -> None:
        try:
            headers = self._get_headers(scope)
            rq_ctx = get_request_context()
            trace_id = req_or_thread_id()

            log_event: dict[str, Any] = {
                "http_method": scope["method"],
                "http_path": scope["path"],
                "http_version": scope.get("http_version", "N/A"),
                "user_agent": headers.get("user-agent"),
                "content_length": headers.get("content-length"),
                "referer": headers.get("referer"),
                "query_params": self._get_query_params(scope),
                "status_code": request_info["status_code"],
                "process_time_ms": round(
                    (request_info["end_time"] - request_info["start_time"]) * 1000, 2
                ),
                "client_ip": self._get_client_ip(scope),
                "trace_id": str(trace_id),
                "user_id": rq_ctx.user_id if rq_ctx else None,
            }

            if 400 <= request_info["status_code"] < 600:
                if "response_body_bytes" in request_info:
                    try:
                        error_detail = json.loads(
                            request_info["response_body_bytes"].decode()
                        )
                    except Exception:  # pylint: disable=W0718
                        error_detail = request_info["response_body_bytes"].decode(
                            errors="replace"
                        )
                    log_event["error_detail"] = error_detail
                # If an unhandled exception occurred, exc_info was already logged.
                # This 'error_detail' is more for structured error responses from FastAPI.

            self.logger.info("http_access", **log_event)
        except Exception:  # pylint: disable=W0718
            self.logger.exception(
                "access_log_error",
                scope=scope,
            )


logger = structlog.get_logger("app")
