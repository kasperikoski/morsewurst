# ============================================================
# morsewurst/koch/scoring.py
# ============================================================

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import morsewurst.config as config
from morsewurst.core.challenge import score_text
from morsewurst.koch.alignment import time_aware_alignment
from morsewurst.koch.models import KochCharacterResult, KochSessionResult, KochSettings
from morsewurst.koch.sequence import active_chars_for_stage, koch_sequence_by_key


def _safe_percent(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0

    return max(0.0, min(100.0, (float(numerator) / float(denominator)) * 100.0))


def _cleanliness_percent(errors: int, target_length: int, entered_length: int) -> float:
    denominator = max(1, target_length, entered_length)
    return max(0.0, min(100.0, 100.0 - ((float(errors) / float(denominator)) * 100.0)))


def _speed_factor(settings: KochSettings) -> float:
    # 20 WPM is neutral for the round score. Above 20 gives a moderate bonus,
    # below 20 reduces the score. The level estimate below uses 40 WPM as level
    # 100 when the full character set is active and the copy is perfect.
    effective = max(1.0, float(settings.effective_wpm))
    return max(0.10, min(2.00, effective / 20.0))


def _coverage_factor(active_chars: str, sequence_length: int) -> float:
    if sequence_length <= 0:
        return 0.0

    return max(0.0, min(1.0, len(set(active_chars)) / float(sequence_length)))


def _quality_factor(accuracy: float, cleanliness: float, new_char_accuracy: float | None) -> float:
    new_component = accuracy if new_char_accuracy is None else new_char_accuracy
    quality = (accuracy * 0.70) + (cleanliness * 0.20) + (new_component * 0.10)
    return max(0.0, min(1.0, quality / 100.0))


def _level_estimate(
    *,
    settings: KochSettings,
    active_chars: str,
    sequence_length: int,
    accuracy: float,
    cleanliness: float,
    new_char_accuracy: float | None,
) -> float:
    coverage = _coverage_factor(active_chars, sequence_length)
    quality = _quality_factor(accuracy, cleanliness, new_char_accuracy)

    # Full set + perfect copy at 20 effective WPM => level 50.
    # Full set + perfect copy at 40 effective WPM => level 100.
    speed_level = (max(1.0, float(settings.effective_wpm)) / 40.0) * 100.0
    level = speed_level * coverage * quality

    return round(max(0.0, min(float(getattr(config, "KOCH_RATING_MAX_LEVEL", 100.0)), level)), 2)


def _schedule_value(
    target_schedule: list[dict[str, Any]],
    target_index: int | None,
    key: str,
) -> int | None:
    if target_index is None or target_index < 0 or target_index >= len(target_schedule):
        return None

    raw_value = target_schedule[target_index].get(key)
    if isinstance(raw_value, (int, float)):
        return int(raw_value)

    return None


def _typed_value(
    typed_events: list[dict[str, Any]],
    entered_index: int | None,
) -> int | None:
    if entered_index is None or entered_index < 0 or entered_index >= len(typed_events):
        return None

    raw_value = typed_events[entered_index].get("typed_at_ms")
    if isinstance(raw_value, (int, float)):
        return int(raw_value)

    return None


def score_koch_copy(
    *,
    target: str,
    entered: str,
    settings: KochSettings,
    duration_ms: int,
    typed_events: list[dict[str, Any]] | None = None,
    target_schedule: list[dict[str, Any]] | None = None,
) -> KochSessionResult:
    settings = settings.normalized()
    sequence = koch_sequence_by_key(settings.sequence_key)
    active_chars = active_chars_for_stage(sequence, settings.stage_index)
    new_stage_char = active_chars[-1] if len(active_chars) >= 1 else None

    target_n = score_text(target, keep_spaces=False)
    entered_n = score_text(entered, keep_spaces=False)
    typed_events = typed_events or []
    target_schedule = target_schedule or []

    alignment = time_aware_alignment(
        target=target_n,
        entered=entered_n,
        typed_events=typed_events,
        target_schedule=target_schedule,
    )

    correct = 0
    substitutions = 0
    deletions = 0
    insertions = 0
    new_char_correct = 0
    new_char_attempts = 0
    char_results: list[KochCharacterResult] = []

    for visual_index, op in enumerate(alignment.ops):
        target_index = op.target_index
        entered_index = op.entered_index
        target_char = target_n[target_index] if target_index is not None else None
        entered_char = entered_n[entered_index] if entered_index is not None else None

        if op.action == "equal":
            result_name = "correct"
            correct += 1
        elif op.action == "substitution":
            result_name = "substitution"
            substitutions += 1
        elif op.action == "delete":
            result_name = "deletion"
            deletions += 1
        else:
            result_name = "insertion"
            insertions += 1

        if target_char is not None and new_stage_char is not None and target_char == new_stage_char:
            new_char_attempts += 1
            if result_name == "correct":
                new_char_correct += 1

        typed_at_ms = _typed_value(typed_events, entered_index)
        expected_start_ms = _schedule_value(target_schedule, target_index, "start_ms")
        expected_end_ms = _schedule_value(target_schedule, target_index, "end_ms")

        latency_ms = None
        if typed_at_ms is not None and expected_end_ms is not None:
            latency_ms = int(typed_at_ms - expected_end_ms)

        char_results.append(
            KochCharacterResult(
                position_index=visual_index,
                target_char=target_char,
                entered_char=entered_char,
                result=result_name,
                target_stage_index=(
                    sequence.characters.find(target_char) + 1
                    if target_char is not None and target_char in sequence.characters
                    else None
                ),
                is_new_stage_char=bool(target_char and target_char == new_stage_char),
                expected_start_ms=expected_start_ms,
                expected_end_ms=expected_end_ms,
                typed_at_ms=typed_at_ms,
                latency_ms=latency_ms,
                timing_weight=round(float(op.timing_weight), 4),
                timing_status=str(op.timing_status or ""),
            )
        )

    errors = substitutions + insertions + deletions
    aligned_accuracy = round(float(alignment.aligned_accuracy), 2)
    time_aligned_accuracy = round(float(alignment.time_aligned_accuracy), 2)
    timing_fit = round(float(alignment.timing_fit), 2)

    # The final Koch pass/fail accuracy is the text-copy alignment. Timing still
    # helps choose a sensible alignment and remains available as diagnostics, but
    # it must not cap an otherwise correct copy.
    accuracy = aligned_accuracy
    cleanliness = round(_cleanliness_percent(errors, len(target_n), len(entered_n)), 2)
    new_char_accuracy = (
        round(_safe_percent(new_char_correct, new_char_attempts), 2)
        if new_char_attempts > 0
        else None
    )

    # Koch pass/fail is based on the actual copy quality. The drill length is
    # already constrained before generation, so no separate pass length or time
    # gate is applied here.
    pass_eligible = bool(target_n)

    enough_new_char_evidence = (
        new_char_attempts >= settings.new_char_min_attempts
        and (new_char_accuracy is None or new_char_accuracy >= settings.new_char_min_accuracy)
    )

    passed = (
        pass_eligible
        and accuracy >= settings.pass_accuracy
        and cleanliness >= settings.pass_cleanliness
        and enough_new_char_evidence
    )

    advanced_from_stage = None
    advanced_to_stage = None

    if passed and settings.mode == "guided" and settings.stage_index < len(sequence.characters):
        advanced_from_stage = settings.stage_index
        advanced_to_stage = settings.stage_index + 1

    quality = _quality_factor(accuracy, cleanliness, new_char_accuracy)
    coverage = _coverage_factor(active_chars, len(sequence.characters))
    speed = _speed_factor(settings)
    score = round(max(0.0, min(200.0, quality * coverage * speed * 100.0)), 2)

    if not pass_eligible:
        pass_reason = "empty_target"
    elif not enough_new_char_evidence:
        pass_reason = "not_enough_new_char_evidence"
    elif passed:
        pass_reason = "passed"
    else:
        pass_reason = "accuracy_or_cleanliness_too_low"

    settings_payload = asdict(settings)
    settings_payload.update(
        {
            "aligned_accuracy": aligned_accuracy,
            "time_aligned_accuracy": time_aligned_accuracy,
            "timing_fit": timing_fit,
            "copy_accuracy": aligned_accuracy,
            "final_accuracy": accuracy,
        }
    )

    return KochSessionResult(
        target=target_n,
        entered=entered_n,
        active_chars=active_chars,
        new_stage_char=new_stage_char,
        sequence_key=sequence.key,
        stage_index=settings.stage_index,
        mode=settings.mode,
        correct_count=correct,
        error_count=errors,
        substitutions=substitutions,
        insertions=insertions,
        deletions=deletions,
        length_target=len(target_n),
        length_entered=len(entered_n),
        accuracy=accuracy,
        aligned_accuracy=aligned_accuracy,
        time_aligned_accuracy=time_aligned_accuracy,
        timing_fit=timing_fit,
        cleanliness=cleanliness,
        new_char_accuracy=new_char_accuracy,
        new_char_attempts=new_char_attempts,
        character_wpm=settings.character_wpm,
        effective_wpm=settings.effective_wpm,
        speed_factor=round(speed, 4),
        coverage_factor=round(coverage, 4),
        score=score,
        level_estimate=_level_estimate(
            settings=settings,
            active_chars=active_chars,
            sequence_length=len(sequence.characters),
            accuracy=accuracy,
            cleanliness=cleanliness,
            new_char_accuracy=new_char_accuracy,
        ),
        duration_ms=max(0, int(duration_ms)),
        pass_eligible=pass_eligible,
        passed=passed,
        advanced_from_stage=advanced_from_stage,
        advanced_to_stage=advanced_to_stage,
        pass_reason=pass_reason,
        settings_json=settings_payload,
        character_results=char_results,
    )
