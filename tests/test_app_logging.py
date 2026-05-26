from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

import morsewurst.core.app_logging as app_logging
from morsewurst.core.app_logging import (
    log_app_event,
    log_app_exception,
    safe_float,
    safe_int,
    safe_len,
    summarize_challenge_settings,
    summarize_score_summary,
    summarize_timing_profile,
    summarize_ui_settings,
)


@dataclass
class DummySettings:
    use_letters: bool = True
    use_numbers: bool = False
    use_punctuation: bool = True
    min_groups: int = 1
    max_groups: int = 3
    min_chars_per_group: int = 2
    max_chars_per_group: int = 5
    target_wpm: int = 17
    practice_problem_chars: bool = True
    practice_rounds: int = 10
    internal_secret: str = "do-not-log"


def test_log_app_event_and_exception_never_break_application_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_event(*_args, **_kwargs) -> None:
        raise RuntimeError("logger unavailable")

    def fail_exception(*_args, **_kwargs) -> None:
        raise RuntimeError("exception logger unavailable")

    monkeypatch.setattr(app_logging, "log_event", fail_event)
    monkeypatch.setattr(app_logging, "log_exception", fail_exception)

    log_app_event("app.test.event", context={"safe": "value"})

    try:
        raise ValueError("boom")
    except ValueError as exc:
        log_app_exception("app.test.exception", exc)


def test_summarize_score_summary_excludes_raw_target_and_entered_text() -> None:
    summary = SimpleNamespace(
        target="SECRET TARGET TEXT",
        entered="SECRET ENTERED TEXT",
        source="adaptive_telemetry",
        finish_reason="completed",
        accuracy=95.0,
        cleanliness=90.0,
        overall_score=91.2,
        speed_score=88.0,
        timing_score=77.0,
        correct_count=10,
        error_count=1,
        substitutions=1,
        insertions=0,
        deletions=0,
        elapsed_us=123456,
        standard_time_us=120000,
        time_ok=True,
        gross_wpm=18.5,
        net_wpm=17.0,
        avg_wpm=18.0,
        profile_eligible=True,
        profile_reject_reason=None,
    )

    data = summarize_score_summary(summary)

    assert "target" not in data
    assert "entered" not in data
    assert repr(data).find("SECRET") == -1
    assert data["target_length"] == len(summary.target)
    assert data["entered_length"] == len(summary.entered)
    assert data["accuracy"] == 95.0
    assert data["gross_wpm"] == 18.5


def test_summarize_ui_settings_keeps_only_expected_non_secret_keys() -> None:
    data = summarize_ui_settings(
        {
            "language": "fi",
            "target_wpm": 17,
            "practice_rounds": 5,
            "keyboard_morse_enabled": True,
            "debug_snapshot_enabled": False,
            "password": "secret",
            "auth_token": "secret",
            "custom_large_blob": "x" * 1000,
        }
    )

    assert data == {
        "language": "fi",
        "target_wpm": 17,
        "practice_rounds": 5,
        "keyboard_morse_enabled": True,
        "debug_snapshot_enabled": False,
    }


def test_summarize_challenge_settings_filters_dataclass_fields() -> None:
    data = summarize_challenge_settings(DummySettings())

    assert data["use_letters"] is True
    assert data["use_numbers"] is False
    assert data["target_wpm"] == 17
    assert data["practice_rounds"] == 10
    assert "internal_secret" not in data


def test_summarize_timing_profile_excludes_sample_level_data() -> None:
    profile = SimpleNamespace(
        source="iambic",
        element_unit_us=70000,
        gap_unit_us=210000,
        dot_us=70000,
        dash_us=210000,
        dash_dot_ratio=3.0,
        letter_gap_us=210000,
        word_gap_us=490000,
        element_confidence=0.8,
        gap_confidence=0.7,
        sample_rounds=42,
        sample_events=500,
        updated_from_session_id=123,
        samples=[{"raw": "do not log"}],
        event_details=[{"raw": "do not log"}],
    )

    data = summarize_timing_profile(profile)

    assert data["source"] == "iambic"
    assert data["sample_rounds"] == 42
    assert data["sample_events"] == 500
    assert "samples" not in data
    assert "event_details" not in data
    assert "do not log" not in repr(data)


def test_safe_helpers_are_defensive() -> None:
    class BrokenLen:
        def __len__(self) -> int:
            raise RuntimeError("broken")

    assert safe_len(BrokenLen()) == 0
    assert safe_len([1, 2, 3]) == 3
    assert safe_int("12") == 12
    assert safe_int(True, default=7) == 7
    assert safe_int("bad", default=4) == 4
    assert safe_float("1.5") == 1.5
    assert safe_float(None) is None
    assert safe_float(False) is None
    assert safe_float("bad") is None
