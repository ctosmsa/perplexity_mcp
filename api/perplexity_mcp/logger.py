"""
Structured logger for the Perplexity MCP Server.
Outputs to stderr to avoid interfering with STDIO transport.
Equivalent to src/logger.ts
"""

import json
import os
import sys
from datetime import datetime, timezone
from enum import IntEnum


class LogLevel(IntEnum):
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3


LOG_LEVEL_NAMES = {
    LogLevel.DEBUG: "DEBUG",
    LogLevel.INFO: "INFO",
    LogLevel.WARN: "WARN",
    LogLevel.ERROR: "ERROR",
}


def _get_log_level() -> LogLevel:
    """Gets the configured log level from the environment variable. Defaults to ERROR."""
    level = os.environ.get("PERPLEXITY_LOG_LEVEL", "").upper()
    mapping = {
        "DEBUG": LogLevel.DEBUG,
        "INFO": LogLevel.INFO,
        "WARN": LogLevel.WARN,
        "ERROR": LogLevel.ERROR,
    }
    return mapping.get(level, LogLevel.ERROR)


_current_log_level = _get_log_level()


def _safe_stringify(obj: object) -> str:
    try:
        return json.dumps(obj)
    except Exception:
        return "[Unstringifiable]"


def _format_message(level: LogLevel, message: str, meta: dict | None = None) -> str:
    timestamp = datetime.now(timezone.utc).isoformat()
    level_name = LOG_LEVEL_NAMES[level]
    if meta:
        return f"[{timestamp}] {level_name}: {message} {_safe_stringify(meta)}"
    return f"[{timestamp}] {level_name}: {message}"


def _log(level: LogLevel, message: str, meta: dict | None = None) -> None:
    if level >= _current_log_level:
        formatted = _format_message(level, message, meta)
        print(formatted, file=sys.stderr)  # stderr avoids interfering with STDIO transport


class Logger:
    """Structured logger interface."""

    def debug(self, message: str, meta: dict | None = None) -> None:
        _log(LogLevel.DEBUG, message, meta)

    def info(self, message: str, meta: dict | None = None) -> None:
        _log(LogLevel.INFO, message, meta)

    def warn(self, message: str, meta: dict | None = None) -> None:
        _log(LogLevel.WARN, message, meta)

    def error(self, message: str, meta: dict | None = None) -> None:
        _log(LogLevel.ERROR, message, meta)


logger = Logger()
