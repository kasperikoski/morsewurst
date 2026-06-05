# ============================================================
# morsewurst/koch/service.py
# ============================================================

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

import morsewurst.config as config
from morsewurst.core.app_logging import log_app_exception
from morsewurst.koch.generator import generate_koch_target
from morsewurst.koch.models import (
    KochProgress,
    KochSessionResult,
    KochSettings,
    KochSkillSummary,
    minimum_koch_target_chars,
    normalize_koch_settings_for_active_count,
)
from morsewurst.koch.scoring import score_koch_copy
from morsewurst.koch.sequence import active_chars_for_stage, all_koch_sequences, koch_sequence_by_key


def default_koch_settings() -> KochSettings:
    return KochSettings(
        mode=str(getattr(config, "DEFAULT_KOCH_MODE", "guided")),
        sequence_key=str(getattr(config, "DEFAULT_KOCH_SEQUENCE", "classic")),
        stage_index=int(getattr(config, "DEFAULT_KOCH_STAGE_INDEX", 2)),
        target_chars=int(getattr(config, "DEFAULT_KOCH_TARGET_CHARS", 30)),
        character_wpm=int(getattr(config, "DEFAULT_KOCH_CHARACTER_WPM", 20)),
        effective_wpm=int(getattr(config, "DEFAULT_KOCH_EFFECTIVE_WPM", 15)),
        tone_hz=int(getattr(config, "DEFAULT_KOCH_TONE_HZ", 600)),
        volume_percent=int(getattr(config, "DEFAULT_KOCH_VOLUME_PERCENT", 70)),
        pass_accuracy=float(getattr(config, "DEFAULT_KOCH_PASS_ACCURACY", 90.0)),
        pass_cleanliness=float(getattr(config, "DEFAULT_KOCH_PASS_CLEANLINESS", 85.0)),
        new_char_min_attempts=int(getattr(config, "DEFAULT_KOCH_NEW_CHAR_MIN_ATTEMPTS", 8)),
        new_char_min_accuracy=float(getattr(config, "DEFAULT_KOCH_NEW_CHAR_MIN_ACCURACY", 80.0)),
        auto_score_delay_ms=int(getattr(config, "DEFAULT_KOCH_AUTO_SCORE_DELAY_MS", 1500)),
    ).normalized()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)

    if result != result:
        return float(default)

    return result


def _safe_average(values: list[float]) -> float:
    clean = [float(value) for value in values if value == value]
    if not clean:
        return 0.0

    return sum(clean) / len(clean)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(float(minimum), min(float(maximum), float(value)))


def _positive_ratio(value: float, reference: float) -> float:
    if reference <= 0.0:
        return 0.0

    return max(0.0, float(value)) / float(reference)


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


class KochPracticeService:
    """Application-facing service for Koch receive practice."""

    def __init__(self, db: Any) -> None:
        self.db = db
        try:
            self.db.ensure_koch_schema()
        except AttributeError:
            pass

    def progress_for_sequence(self, sequence_key: str) -> KochProgress:
        sequence = koch_sequence_by_key(sequence_key)

        row = self.db.koch_progress(sequence.key)
        if row is None:
            return KochProgress(
                sequence_key=sequence.key,
                guided_unlocked_stage=2,
                guided_current_stage=2,
            )

        return KochProgress(
            sequence_key=str(row["sequence_key"]),
            guided_unlocked_stage=int(row["guided_unlocked_stage"]),
            guided_current_stage=int(row["guided_current_stage"]),
            guided_fail_streak=int(_row_value(row, "guided_fail_streak", 0) or 0),
            guided_fail_stage=_row_value(row, "guided_fail_stage"),
            last_demoted_from_stage=_row_value(row, "last_demoted_from_stage"),
            last_demoted_to_stage=_row_value(row, "last_demoted_to_stage"),
            last_demoted_at=_row_value(row, "last_demoted_at"),
            total_sessions=int(row["total_sessions"]),
            total_practice_seconds=int(row["total_practice_seconds"]),
            last_session_id=row["last_session_id"],
        )

    def minimum_target_chars_for_settings(self, settings: KochSettings) -> int:
        settings = settings.normalized()
        sequence = koch_sequence_by_key(settings.sequence_key)
        active_chars = active_chars_for_stage(sequence, settings.stage_index)
        return minimum_koch_target_chars(len(set(active_chars)))

    def settings_with_target_minimum(self, settings: KochSettings) -> KochSettings:
        settings = settings.normalized()
        sequence = koch_sequence_by_key(settings.sequence_key)
        active_chars = active_chars_for_stage(sequence, settings.stage_index)
        return normalize_koch_settings_for_active_count(settings, len(set(active_chars)))

    def settings_with_progress(self, settings: KochSettings) -> KochSettings:
        settings = settings.normalized()

        if settings.mode == "guided":
            progress = self.progress_for_sequence(settings.sequence_key)
            stage = max(2, int(progress.guided_current_stage))
            settings = KochSettings(**{**asdict(settings), "stage_index": stage}).normalized()

        return self.settings_with_target_minimum(settings)

    def create_target(self, settings: KochSettings) -> tuple[str, str]:
        settings = self.settings_with_progress(settings)
        target = generate_koch_target(settings)
        sequence = koch_sequence_by_key(settings.sequence_key)
        return target, active_chars_for_stage(sequence, settings.stage_index)

    def score_session(
        self,
        *,
        started_at: datetime,
        finished_at: datetime,
        target: str,
        entered: str,
        settings: KochSettings,
        typed_events: list[dict[str, Any]],
        target_schedule: list[dict[str, Any]],
    ) -> tuple[int, KochSessionResult]:
        duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
        settings = self.settings_with_progress(settings)

        result = score_koch_copy(
            target=target,
            entered=entered,
            settings=settings,
            duration_ms=duration_ms,
            typed_events=typed_events,
            target_schedule=target_schedule,
        )

        session_id = self.db.save_koch_session(
            started_at=started_at,
            finished_at=finished_at,
            result=result,
            typed_events=typed_events,
            target_schedule=target_schedule,
        )

        summary = self.skill_summary()
        try:
            self.db.save_koch_skill_snapshot(session_id, summary)
        except AttributeError:
            pass
        except Exception as exc:
            log_app_exception(
                "app.koch.skill_snapshot_save_failed",
                exc,
                level="warning",
                message="Saving Koch receive-skill snapshot failed.",
                context={"session_id": session_id},
            )

        return session_id, result

    def _koch_skill_active_counts(self) -> tuple[dict[str, int], int, str, int]:
        """Return current guided active-character counts for each Koch order."""

        counts: dict[str, int] = {}
        total_character_count = 0
        best_sequence_key = ""
        best_active_count = 0

        for sequence in all_koch_sequences():
            total = max(1, len(sequence.characters))
            total_character_count = max(total_character_count, total)

            try:
                progress = self.progress_for_sequence(sequence.key)
                stage = int(progress.guided_current_stage)
            except Exception:
                stage = int(getattr(config, "DEFAULT_KOCH_GUIDED_MIN_STAGE", 2))

            active_count = len(active_chars_for_stage(sequence, stage))
            active_count = max(0, min(active_count, total))
            counts[sequence.key] = active_count

            if active_count > best_active_count:
                best_sequence_key = sequence.key
                best_active_count = active_count

        return counts, max(1, total_character_count), best_sequence_key, best_active_count

    def _koch_skill_title(self, level: float, displayable: bool) -> tuple[str, str]:
        if not displayable:
            return "koch.skill.title.no_level", "No copy level yet"

        if level >= 200:
            return "koch.skill.title.extreme_receiver", "Extreme receiver"
        if level >= 150:
            return "koch.skill.title.master_receiver", "Master receiver"
        if level >= 100:
            return "koch.skill.title.elite_receiver", "Elite receiver"
        if level >= 75:
            return "koch.skill.title.fast_receiver", "Fast receiver"
        if level >= 60:
            return "koch.skill.title.advanced_receiver", "Advanced receiver"
        if level >= 45:
            return "koch.skill.title.solid_receiver", "Solid receiver"
        if level >= 30:
            return "koch.skill.title.developing_receiver", "Developing receiver"
        if level >= 15:
            return "koch.skill.title.beginner_receiver", "Beginner receiver"

        return "koch.skill.title.first_copies", "First copies"

    def skill_summary(self, recent_limit: int | None = None) -> KochSkillSummary:
        """Calculate the rolling Koch receive-skill summary.

        The model uses only Koch receive-practice sessions. It does not affect
        the normal Morse sending-practice score or skill rating.

        Reference point:
        full current character set + 20/20 WPM + 90 % accuracy + 85 %
        cleanliness + 100 target characters => approximately level 100.
        Speed is intentionally uncapped, so 40/40 WPM at the same quality is
        approximately level 200.
        """

        configured_recent = int(getattr(config, "DEFAULT_KOCH_SKILL_RECENT_ROUNDS", 300))
        recent_limit = configured_recent if recent_limit is None else int(recent_limit)
        recent_limit = max(1, recent_limit)
        required_sessions = max(1, int(getattr(config, "DEFAULT_KOCH_SKILL_MIN_SESSIONS", 30)))

        rows = list(self.db.recent_koch_sessions(limit=recent_limit))

        accuracies: list[float] = []
        cleanliness_values: list[float] = []
        character_wpm_values: list[float] = []
        effective_wpm_values: list[float] = []
        target_lengths: list[float] = []
        full_charset_passes = 0

        for row in rows:
            try:
                accuracies.append(_clamp(_safe_float(row["accuracy"]), 0.0, 100.0))
                cleanliness_values.append(_clamp(_safe_float(row["cleanliness"]), 0.0, 100.0))
                character_wpm_values.append(max(0.0, _safe_float(row["character_wpm"])))
                effective_wpm_values.append(max(0.0, _safe_float(row["effective_wpm"])))
                target_lengths.append(max(0.0, _safe_float(row["target_length"])))
                if bool(row["passed"]) and _safe_float(row["coverage_factor"]) >= 1.0:
                    full_charset_passes += 1
            except Exception:
                continue

        sessions_used = len(accuracies)
        try:
            total_sessions = int(self.db.count_koch_sessions())
        except AttributeError:
            total_sessions = sessions_used
        except Exception:
            total_sessions = sessions_used

        active_counts, total_character_count, base_sequence_key, active_char_count = self._koch_skill_active_counts()
        base_level = (float(active_char_count) / float(max(1, total_character_count))) * 100.0

        avg_accuracy = _safe_average(accuracies)
        avg_cleanliness = _safe_average(cleanliness_values)
        avg_character_wpm = _safe_average(character_wpm_values)
        avg_effective_wpm = _safe_average(effective_wpm_values)
        avg_target_length = _safe_average(target_lengths)

        char_ref = max(0.0001, float(getattr(config, "KOCH_SKILL_REFERENCE_CHARACTER_WPM", 20.0)))
        eff_ref = max(0.0001, float(getattr(config, "KOCH_SKILL_REFERENCE_EFFECTIVE_WPM", 20.0)))
        length_ref = max(0.0001, float(getattr(config, "KOCH_SKILL_REFERENCE_TARGET_CHARS", 100.0)))
        reference_accuracy = max(0.0001, float(getattr(config, "KOCH_SKILL_REFERENCE_ACCURACY", 90.0)))
        reference_cleanliness = max(0.0001, float(getattr(config, "KOCH_SKILL_REFERENCE_CLEANLINESS", 85.0)))
        character_exponent = float(getattr(config, "KOCH_SKILL_CHARACTER_WPM_EXPONENT", 0.35))
        effective_exponent = float(getattr(config, "KOCH_SKILL_EFFECTIVE_WPM_EXPONENT", 0.65))
        cleanliness_base = _clamp(
            float(getattr(config, "KOCH_SKILL_CLEANLINESS_BASE_FACTOR", 0.55)),
            0.0,
            1.0,
        )
        length_exponent = float(getattr(config, "KOCH_SKILL_LENGTH_EXPONENT", 0.15))
        min_length_factor = float(getattr(config, "KOCH_SKILL_LENGTH_MIN_FACTOR", 0.75))
        max_length_factor = float(getattr(config, "KOCH_SKILL_LENGTH_MAX_FACTOR", 1.08))

        speed_factor = (
            _positive_ratio(avg_character_wpm, char_ref) ** character_exponent
            * _positive_ratio(avg_effective_wpm, eff_ref) ** effective_exponent
        )
        accuracy_factor = _clamp(avg_accuracy / 100.0, 0.0, 1.0)
        cleanliness_factor = cleanliness_base + ((1.0 - cleanliness_base) * _clamp(avg_cleanliness / 100.0, 0.0, 1.0))
        length_factor = _clamp(
            _positive_ratio(avg_target_length, length_ref) ** length_exponent,
            min_length_factor,
            max_length_factor,
        )

        reference_cleanliness_factor = cleanliness_base + (
            (1.0 - cleanliness_base) * _clamp(reference_cleanliness / 100.0, 0.0, 1.0)
        )
        normalizer = 1.0 / max(
            0.0001,
            (reference_accuracy / 100.0) * reference_cleanliness_factor,
        )

        raw_level = (
            base_level
            * speed_factor
            * accuracy_factor
            * cleanliness_factor
            * length_factor
            * normalizer
        )

        displayable = sessions_used >= required_sessions
        level = max(0.0, float(raw_level)) if displayable else 0.0
        confidence = min(100.0, (sessions_used / float(required_sessions)) * 100.0)

        title_key, title_default = self._koch_skill_title(level, displayable)

        return KochSkillSummary(
            level=round(level, 2),
            title_key=title_key,
            title_default=title_default,
            confidence=confidence,
            sessions_used=sessions_used,
            total_sessions=total_sessions,
            required_sessions=required_sessions,
            displayable=displayable,
            average_accuracy=avg_accuracy,
            average_cleanliness=avg_cleanliness,
            average_character_wpm=avg_character_wpm,
            average_effective_wpm=avg_effective_wpm,
            average_target_length=avg_target_length,
            best_effective_wpm=int(round(avg_effective_wpm)),
            best_character_wpm=int(round(avg_character_wpm)),
            best_level=round(level, 2),
            full_charset_passes=full_charset_passes,
            active_char_count=active_char_count,
            total_character_count=total_character_count,
            base_sequence_key=base_sequence_key,
            classic_active_count=int(active_counts.get("classic", 0)),
            lcwo_active_count=int(active_counts.get("lcwo", 0)),
            base_level=round(base_level, 4),
            speed_factor=round(speed_factor, 6),
            accuracy_factor=round(accuracy_factor, 6),
            cleanliness_factor=round(cleanliness_factor, 6),
            length_factor=round(length_factor, 6),
            normalizer=round(normalizer, 6),
            raw_level=round(raw_level, 4),
        )

    def character_stats(self, recent_sessions: int = 300, limit: int = 50) -> list[Any]:
        return self.db.koch_character_stats(
            recent_sessions=recent_sessions,
            limit=limit,
        )

    def recent_sessions(self, limit: int = 20) -> list[Any]:
        return self.db.recent_koch_sessions(limit=limit)