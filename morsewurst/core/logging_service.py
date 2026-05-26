# ============================================================
# morsewurst/core/logging_service.py
# ============================================================

from __future__ import annotations

import json
import logging
import sys
import time
import traceback as traceback_module
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Mapping

import morsewurst.config as config


_LOGGER_PREFIX = "morsewurst"
_CONFIGURED_DATA_DIR: Path | None = None
_LOG_DIR: Path | None = None
_CONFIGURED_CHANNELS: set[str] = set()

SENSITIVE_KEY_PARTS = (
    "password",
    "passphrase",
    "proof",
    "verifier",
    "token",
    "secret",
    "credential",
    "auth",
    "private_key",
)

MASKED_IDENTIFIER_KEYS = {
    "client_id",
    "installation_id",
    "sender_id",
    "stream_id",
}

_MAX_CONTEXT_DEPTH = 6
_MAX_STRING_LENGTH = 2000
_MAX_SEQUENCE_LENGTH = 100


class JsonLineFormatter(logging.Formatter):
    """Format logging records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        channel = str(getattr(record, "mw_channel", "") or record.name.rsplit(".", 1)[-1])
        event = str(getattr(record, "mw_event", "") or record.getMessage() or "event")

        item: dict[str, Any] = {
            "time": _now_iso(),
            "time_monotonic": time.monotonic(),
            "level": record.levelname.lower(),
            "channel": channel,
            "event": event,
            "message": record.getMessage(),
            "context": sanitize_context(getattr(record, "mw_context", None)),
        }

        exception_type = getattr(record, "mw_exception_type", None)
        exception_message = getattr(record, "mw_exception_message", None)
        exception_traceback = getattr(record, "mw_traceback", None)

        if exception_type:
            item["exception_type"] = str(exception_type)
        if exception_message:
            item["exception_message"] = str(exception_message)
        if exception_traceback:
            item["traceback"] = str(exception_traceback)

        if record.exc_info and not exception_type:
            exc_type, exc, tb = record.exc_info
            if exc_type is not None:
                item["exception_type"] = exc_type.__name__
            if exc is not None:
                item["exception_message"] = str(exc)
            item["traceback"] = "".join(traceback_module.format_exception(exc_type, exc, tb))

        return json.dumps(item, ensure_ascii=False, separators=(",", ":"), default=_json_default)


def setup_logging(
    data_dir: str | Path | None = None,
    *,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> Path:
    """Configure Morsewurst JSONL logging under the active profile data directory."""

    global _CONFIGURED_DATA_DIR
    global _LOG_DIR

    target_data_dir = Path(data_dir) if data_dir is not None else Path(config.DATA_DIR)
    target_data_dir = target_data_dir.expanduser().resolve()
    log_dir = target_data_dir / str(getattr(config, "LOG_DIRNAME", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    if _CONFIGURED_DATA_DIR == target_data_dir and _LOG_DIR == log_dir:
        return log_dir

    _CONFIGURED_DATA_DIR = target_data_dir
    _LOG_DIR = log_dir
    _CONFIGURED_CHANNELS.clear()

    # Reconfigure any existing Morsewurst loggers so profile switches do not
    # keep writing to the previous profile's files.
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        if not logger_name.startswith(f"{_LOGGER_PREFIX}."):
            continue
        logger = logging.getLogger(logger_name)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

    _configure_channel("app", max_bytes=max_bytes, backup_count=backup_count)
    _configure_channel("network", max_bytes=max_bytes, backup_count=backup_count)

    return log_dir


def get_logger(channel: str) -> logging.Logger:
    """Return a Morsewurst logger for the given logical channel.

    Before setup_logging() has been called, this returns a silent logger.
    This prevents early imports, tests or pre-profile startup code from
    creating logs under the global data directory.
    """

    clean_channel = _clean_channel(channel)
    logger = logging.getLogger(f"{_LOGGER_PREFIX}.{clean_channel}")

    if _LOG_DIR is None:
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        if not any(isinstance(handler, logging.NullHandler) for handler in logger.handlers):
            logger.addHandler(logging.NullHandler())

        return logger

    if clean_channel not in _CONFIGURED_CHANNELS:
        _configure_channel(clean_channel)

    return logger


def log_event(
    channel: str,
    event: str,
    *,
    level: str = "info",
    message: str = "",
    context: Mapping[str, Any] | None = None,
) -> None:
    """Write a structured event to a channel log file."""

    logger = get_logger(channel)
    log_level = _logging_level(level)

    logger.log(
        log_level,
        str(message or ""),
        extra={
            "mw_channel": _clean_channel(channel),
            "mw_event": str(event or "event"),
            "mw_context": sanitize_context(context),
        },
    )


def log_exception(
    channel: str,
    event: str,
    exc: BaseException,
    *,
    level: str = "error",
    message: str = "",
    context: Mapping[str, Any] | None = None,
) -> None:
    """Write a structured exception event with traceback information."""

    logger = get_logger(channel)
    log_level = _logging_level(level)

    logger.log(
        log_level,
        str(message or str(exc) or exc.__class__.__name__),
        extra={
            "mw_channel": _clean_channel(channel),
            "mw_event": str(event or "exception"),
            "mw_context": sanitize_context(context),
            "mw_exception_type": exc.__class__.__name__,
            "mw_exception_message": str(exc),
            "mw_traceback": "".join(
                traceback_module.format_exception(type(exc), exc, exc.__traceback__)
            ),
        },
    )


def sanitize_context(value: Any) -> Any:
    """Return a JSON-safe context object with sensitive values masked."""

    return _sanitize_value(value, depth=0, key="")


def _configure_channel(
    channel: str,
    *,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> None:
    if _LOG_DIR is None:
        return

    clean_channel = _clean_channel(channel)
    logger = logging.getLogger(f"{_LOGGER_PREFIX}.{clean_channel}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    handler = RotatingFileHandler(
        _LOG_DIR / _log_filename(clean_channel),
        maxBytes=int(max_bytes if max_bytes is not None else getattr(config, "LOG_MAX_BYTES", 2 * 1024 * 1024)),
        backupCount=int(backup_count if backup_count is not None else getattr(config, "LOG_BACKUP_COUNT", 5)),
        encoding="utf-8",
    )
    handler.setFormatter(JsonLineFormatter())
    logger.addHandler(handler)
    _CONFIGURED_CHANNELS.add(clean_channel)


def _log_filename(channel: str) -> str:
    clean_channel = _clean_channel(channel)
    if clean_channel == "app":
        return "morsewurst.jsonl"
    return f"{clean_channel}.jsonl"


def _clean_channel(channel: str) -> str:
    text = str(channel or "app").strip().lower()
    clean = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in text)
    return clean.strip("_-") or "app"


def _logging_level(level: str) -> int:
    text = str(level or "info").strip().lower()
    if text == "critical":
        return logging.CRITICAL
    if text == "error":
        return logging.ERROR
    if text in {"warning", "warn"}:
        return logging.WARNING
    if text == "debug":
        return logging.DEBUG
    return logging.INFO


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _sanitize_value(value: Any, *, depth: int, key: str) -> Any:
    if depth > _MAX_CONTEXT_DEPTH:
        return "[max-depth]"

    key_text = str(key or "").lower()

    if _is_sensitive_key(key_text):
        return "[masked]"

    if key_text in MASKED_IDENTIFIER_KEYS:
        return _mask_identifier(value)

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, str):
        return _clip_string(value)

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, Mapping):
        return {
            str(item_key): _sanitize_value(item_value, depth=depth + 1, key=str(item_key))
            for item_key, item_value in value.items()
        }

    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        clipped = items[:_MAX_SEQUENCE_LENGTH]
        result = [
            _sanitize_value(item, depth=depth + 1, key="")
            for item in clipped
        ]
        if len(items) > _MAX_SEQUENCE_LENGTH:
            result.append(f"[truncated:{len(items) - _MAX_SEQUENCE_LENGTH}]")
        return result

    if hasattr(value, "__dict__"):
        return _sanitize_value(vars(value), depth=depth + 1, key=key)

    return _clip_string(str(value))


def _is_sensitive_key(key_text: str) -> bool:
    if not key_text:
        return False
    return any(part in key_text for part in SENSITIVE_KEY_PARTS)


def _mask_identifier(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    # Avoid storing the full identifier. A short stable-ish hint is enough for
    # correlating adjacent events during one debugging session.
    import hashlib

    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:12]
    prefix = text[:6] if len(text) >= 6 else text[:2]
    return f"{prefix}…{digest}"


def _clip_string(value: str) -> str:
    text = value.replace("\x00", "")
    if len(text) <= _MAX_STRING_LENGTH:
        return text
    return text[:_MAX_STRING_LENGTH] + f"…[truncated:{len(text) - _MAX_STRING_LENGTH}]"


def _json_default(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        return repr(value)
