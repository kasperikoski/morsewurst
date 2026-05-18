from __future__ import annotations

from morsewurst.core.adaptive_decoder import decode_tone_events
from morsewurst.core.adaptive_timing import DecoderSettings
from morsewurst.core.scoring import (
    estimate_paris_time_us,
    event_metrics,
    levenshtein_results,
    paris_unit_count,
    paris_wpm_for_text,
    score_round,
    telemetry_visible_text,
)
from morsewurst.models import ChallengeSettings

from .conftest import make_tone_events


def test_levenshtein_counts_spaces_when_requested() -> None:
    correct, errors, substitutions, insertions, deletions, results = levenshtein_results(
        "AB CD",
        "ABCD",
        [],
        keep_spaces=True,
    )

    assert correct == 4
    assert errors == 1
    assert deletions == 1
    assert substitutions == 0
    assert insertions == 0
    assert [result.result for result in results].count("deletion") == 1


def test_levenshtein_can_ignore_spaces_for_character_accuracy() -> None:
    correct, errors, substitutions, insertions, deletions, _results = levenshtein_results(
        "AB CD",
        "ABCD",
        [],
        keep_spaces=False,
    )

    assert correct == 4
    assert errors == 0
    assert (substitutions, insertions, deletions) == (0, 0, 0)


def test_score_round_for_perfect_decoded_telemetry() -> None:
    events = make_tone_events("SOS", source="iambic", include_hints=True)
    settings = ChallengeSettings(target_wpm=12)
    decoded = decode_tone_events(events, flush_final=True, settings=DecoderSettings(target_unit_us=100_000))

    summary, results = score_round(
        "SOS",
        decoded.text,
        "iambic",
        events,
        settings,
        finish_reason="exact_match",
        decoded=decoded,
    )

    assert summary.accuracy == 100.0
    assert summary.cleanliness == 100.0
    assert summary.correct_count == 3
    assert summary.error_count == 0
    assert summary.length_target == 3
    assert len(results) == 3
    assert all(result.result == "correct" for result in results)
    assert summary.elapsed_us is not None and summary.elapsed_us > 0


def test_score_round_detects_substitution() -> None:
    settings = ChallengeSettings(target_wpm=12)

    summary, results = score_round(
        "SOS",
        "SOT",
        "manual",
        [],
        settings,
        finish_reason="manual",
    )

    assert summary.accuracy < 100.0
    assert summary.substitutions == 1
    assert summary.error_count == 1
    assert results[-1].result == "substitution"


def test_paris_timing_helpers_are_consistent() -> None:
    units = paris_unit_count("PARIS")
    expected_time = estimate_paris_time_us("PARIS", target_wpm=20)

    assert units == 43
    assert expected_time == 2_580_000
    assert paris_wpm_for_text("PARIS", expected_time) == 20.0


def test_event_metrics_and_visible_telemetry_are_stable() -> None:
    events = make_tone_events("ET", source="iambic", include_hints=True)
    decoded = decode_tone_events(events, flush_final=True, settings=DecoderSettings(target_unit_us=100_000))

    metrics = event_metrics(events, decoded=decoded)

    assert metrics["elapsed_us"] is not None
    assert metrics["avg_dit_us"] == 100_000
    assert telemetry_visible_text("  ABC   DEF  ", max_chars=5) == "C DEF"
