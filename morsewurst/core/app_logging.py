# ============================================================
# morsewurst/core/app_logging.py
# ============================================================

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from morsewurst.core.logging_service import log_event, log_exception


APP_LOG_CHANNEL = "app"


def log_app_event(
    event: str,
    *,
    level: str = "info",
    message: str = "",
    context: Mapping[str, Any] | None = None,
) -> None:
    """Write one application-level structured log event without risking UI flow."""
    try:
        log_event(
            APP_LOG_CHANNEL,
            event,
            level=level,
            message=message,
            context=context,
        )
    except Exception:
        pass


def log_app_exception(
    event: str,
    exc: BaseException,
    *,
    level: str = "error",
    message: str = "",
    context: Mapping[str, Any] | None = None,
) -> None:
    """Write one application-level exception log without risking UI flow."""
    try:
        log_exception(
            APP_LOG_CHANNEL,
            event,
            exc,
            level=level,
            message=message,
            context=context,
        )
    except Exception:
        pass


def safe_len(value: Any) -> int:
    try:
        return len(value)
    except Exception:
        return 0


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except Exception:
        return default


def safe_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except Exception:
        return None


def summarize_challenge_settings(settings: Any) -> dict[str, Any]:
    """Return non-sensitive, compact practice settings for application logs."""
    if settings is None:
        return {}

    if is_dataclass(settings):
        raw = asdict(settings)
    elif isinstance(settings, Mapping):
        raw = dict(settings)
    else:
        raw = vars(settings) if hasattr(settings, "__dict__") else {}

    keys = (
        "use_letters",
        "use_numbers",
        "use_punctuation",
        "min_groups",
        "max_groups",
        "min_chars_per_group",
        "max_chars_per_group",
        "target_wpm",
        "practice_problem_chars",
        "practice_rounds",
        "countdown_seconds",
        "sound_enabled",
        "problem_recent_rounds",
        "problem_char_weight_percent",
        "problem_char_limit",
        "auto_optimize_recent_rounds",
        "auto_optimize_min_accuracy",
    )

    return {key: raw.get(key) for key in keys if key in raw}


def summarize_ui_settings(data: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a compact UI-settings summary instead of dumping the full file."""
    if not isinstance(data, Mapping):
        return {}

    keys = (
        "language",
        "target_wpm",
        "practice_rounds",
        "min_groups",
        "max_groups",
        "min_chars",
        "max_chars",
        "use_letters",
        "use_numbers",
        "use_punctuation",
        "practice_problem_chars",
        "practice_wxmor",
        "wxmor_profile",
        "sound_enabled",
        "use_telemetry_as_truth",
        "keep_focus",
        "auto_connect_serial",
        "keyboard_morse_enabled",
        "keyboard_morse_key",
        "use_timing_profile",
        "decoder_profile_recent_rounds",
        "decoder_profile_min_accuracy",
        "decoder_profile_min_cleanliness",
        "auto_finish_on_idle",
        "auto_finish_idle_units",
        "auto_finish_min_seconds",
        "debug_snapshot_enabled",
        "debug_snapshot_save_history",
        "raw_telemetry_pixels_per_unit",
        "problem_recent_rounds",
        "problem_char_weight_percent",
        "problem_char_limit",
        "stats_recent_rounds",
        "skill_recent_rounds",
        "effective_wpm_recent_rounds",
        "effective_wpm_min_accuracy",
        "effective_wpm_min_cleanliness",
    )

    return {key: data.get(key) for key in keys if key in data}


def summarize_score_summary(summary: Any) -> dict[str, Any]:
    """Return safe round metrics without raw target or entered text."""
    if summary is None:
        return {}

    return {
        "target_length": safe_len(getattr(summary, "target", "")),
        "entered_length": safe_len(getattr(summary, "entered", "")),
        "source": getattr(summary, "source", None),
        "finish_reason": getattr(summary, "finish_reason", None),
        "accuracy": getattr(summary, "accuracy", None),
        "cleanliness": getattr(summary, "cleanliness", None),
        "overall_score": getattr(summary, "overall_score", None),
        "speed_score": getattr(summary, "speed_score", None),
        "timing_score": getattr(summary, "timing_score", None),
        "correct_count": getattr(summary, "correct_count", None),
        "error_count": getattr(summary, "error_count", None),
        "substitutions": getattr(summary, "substitutions", None),
        "insertions": getattr(summary, "insertions", None),
        "deletions": getattr(summary, "deletions", None),
        "elapsed_us": getattr(summary, "elapsed_us", None),
        "standard_time_us": getattr(summary, "standard_time_us", None),
        "time_ok": getattr(summary, "time_ok", None),
        "gross_wpm": getattr(summary, "gross_wpm", None),
        "net_wpm": getattr(summary, "net_wpm", None),
        "avg_wpm": getattr(summary, "avg_wpm", None),
        "profile_eligible": getattr(summary, "profile_eligible", None),
        "profile_reject_reason": getattr(summary, "profile_reject_reason", None),
    }


def summarize_rating(rating: Any) -> dict[str, Any]:
    """Return the visible skill-rating headline metrics for logs."""
    if rating is None:
        return {}

    return {
        "model_version": getattr(rating, "model_version", None),
        "recent_sessions": getattr(rating, "recent_sessions", None),
        "total_rounds": getattr(rating, "total_rounds", None),
        "used_rounds": getattr(rating, "used_rounds", None),
        "effective_wpm": getattr(rating, "effective_wpm", None),
        "raw_skill": getattr(rating, "raw_skill", None),
        "level": getattr(rating, "level", None),
        "level_progress": getattr(rating, "level_progress", None),
        "title": getattr(rating, "title", None),
        "rating_confidence": getattr(rating, "rating_confidence", None),
        "sample_confidence": getattr(rating, "sample_confidence", None),
        "coverage_factor": getattr(rating, "coverage_factor", None),
        "timing_stability_factor": getattr(rating, "timing_stability_factor", None),
    }


def summarize_timing_profile(profile: Any) -> dict[str, Any]:
    """Return compact timing profile metrics without sample-level data."""
    if profile is None:
        return {}

    return {
        "source": getattr(profile, "source", None),
        "element_unit_us": getattr(profile, "element_unit_us", None),
        "gap_unit_us": getattr(profile, "gap_unit_us", None),
        "dot_us": getattr(profile, "dot_us", None),
        "dash_us": getattr(profile, "dash_us", None),
        "dash_dot_ratio": getattr(profile, "dash_dot_ratio", None),
        "letter_gap_us": getattr(profile, "letter_gap_us", None),
        "word_gap_us": getattr(profile, "word_gap_us", None),
        "element_confidence": getattr(profile, "element_confidence", None),
        "gap_confidence": getattr(profile, "gap_confidence", None),
        "sample_rounds": getattr(profile, "sample_rounds", None),
        "sample_events": getattr(profile, "sample_events", None),
        "updated_from_session_id": getattr(profile, "updated_from_session_id", None),
    }


def path_context(path: Any) -> str:
    if isinstance(path, Path):
        return str(path)
    return str(path or "")
