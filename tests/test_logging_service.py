from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

import morsewurst.config as config
import morsewurst.core.logging_service as logging_service
from morsewurst.core.logging_service import (
    log_event,
    log_exception,
    sanitize_context,
    setup_logging,
)


def _clear_morsewurst_loggers() -> None:
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        if not logger_name.startswith("morsewurst."):
            continue
        logger = logging.getLogger(logger_name)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass


@pytest.fixture(autouse=True)
def reset_logging_service_state():
    _clear_morsewurst_loggers()
    logging_service._CONFIGURED_DATA_DIR = None
    logging_service._LOG_DIR = None
    logging_service._CONFIGURED_CHANNELS.clear()
    yield
    _clear_morsewurst_loggers()
    logging_service._CONFIGURED_DATA_DIR = None
    logging_service._LOG_DIR = None
    logging_service._CONFIGURED_CHANNELS.clear()


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_log_event_before_setup_does_not_create_global_data_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    global_data = tmp_path / "global-data"
    monkeypatch.setattr(config, "DATA_DIR", global_data)

    log_event("network", "network.before_setup", message="Should stay silent.")

    assert not (global_data / "logs").exists()


def test_setup_logging_writes_jsonl_to_profile_logs_and_masks_sensitive_context(tmp_path: Path) -> None:
    setup_logging(tmp_path)

    log_event(
        "network",
        "network.test_event",
        level="warning",
        message="Hello JSONL.",
        context={
            "password": "secret",
            "nested": {"auth_proof": "proof-secret"},
            "client_id": "client-abcdef1234567890",
            "safe": "visible",
        },
    )

    rows = _read_jsonl(tmp_path / "logs" / "network.jsonl")
    assert len(rows) == 1
    row = rows[0]

    assert row["level"] == "warning"
    assert row["channel"] == "network"
    assert row["event"] == "network.test_event"
    assert row["message"] == "Hello JSONL."
    assert isinstance(row["time"], str)
    assert isinstance(row["time_monotonic"], float)

    context = row["context"]
    assert isinstance(context, dict)
    assert context["password"] == "[masked]"
    assert context["nested"] == {"auth_proof": "[masked]"}
    assert context["safe"] == "visible"
    assert str(context["client_id"]).startswith("client…")
    assert context["client_id"] != "client-abcdef1234567890"


def test_log_exception_records_type_message_and_traceback(tmp_path: Path) -> None:
    setup_logging(tmp_path)

    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        log_exception("network", "network.test_exception", exc, context={"token": "secret"})

    [row] = _read_jsonl(tmp_path / "logs" / "network.jsonl")
    assert row["event"] == "network.test_exception"
    assert row["exception_type"] == "RuntimeError"
    assert row["exception_message"] == "boom"
    assert "RuntimeError: boom" in str(row["traceback"])
    context = row["context"]
    assert isinstance(context, dict)
    assert context["token"] == "[masked]"


def test_setup_logging_reconfigures_existing_loggers_to_new_profile_directory(tmp_path: Path) -> None:
    first_profile = tmp_path / "profile-one"
    second_profile = tmp_path / "profile-two"

    setup_logging(first_profile)
    log_event("network", "network.first")

    setup_logging(second_profile)
    log_event("network", "network.second")

    first_rows = _read_jsonl(first_profile / "logs" / "network.jsonl")
    second_rows = _read_jsonl(second_profile / "logs" / "network.jsonl")

    assert [row["event"] for row in first_rows] == ["network.first"]
    assert [row["event"] for row in second_rows] == ["network.second"]


def test_app_channel_uses_morsewurst_jsonl_filename(tmp_path: Path) -> None:
    setup_logging(tmp_path)

    log_event("app", "app.test")

    assert (tmp_path / "logs" / "morsewurst.jsonl").exists()
    assert not (tmp_path / "logs" / "app.jsonl").exists()


def test_log_rotation_uses_configured_limits(tmp_path: Path) -> None:
    setup_logging(tmp_path, max_bytes=250, backup_count=2)

    for index in range(40):
        log_event("network", f"network.rotation.{index}", message="x" * 120)

    log_dir = tmp_path / "logs"
    rotated = sorted(path.name for path in log_dir.glob("network.jsonl*"))
    assert "network.jsonl" in rotated
    assert "network.jsonl.1" in rotated
    assert len(rotated) <= 3


def test_sanitize_context_limits_depth_sequence_length_and_string_length() -> None:
    deep: dict[str, object] = {"value": "bottom"}
    for _ in range(10):
        deep = {"child": deep}

    sanitized = sanitize_context(
        {
            "items": list(range(150)),
            "long": "x" * 2500,
            "deep": deep,
        }
    )

    assert len(sanitized["items"]) == 101
    assert sanitized["items"][-1] == "[truncated:50]"
    assert str(sanitized["long"]).endswith("[truncated:500]")
    assert "[max-depth]" in repr(sanitized["deep"])
