from __future__ import annotations

from morsewurst.core.timing_profile import (
    TimingProfile,
    TimingProfileSample,
    build_timing_profile,
    normalize_source,
)


def test_normalize_source_rejects_unknown_source_names() -> None:
    assert normalize_source("straight") == "straight"
    assert normalize_source("IAMBIC") == "iambic"
    assert normalize_source("keyboard") == "unknown"


def test_timing_profile_seed_unit_prefers_gap_then_element_then_fallback() -> None:
    assert TimingProfile(source="straight", element_unit_us=80_000, element_confidence=0.6).seed_unit_us(100_000) == 80_000
    assert TimingProfile(source="straight", gap_unit_us=90_000, gap_confidence=0.6, element_unit_us=80_000, element_confidence=0.6).seed_unit_us(100_000) == 90_000
    assert TimingProfile(source="straight").seed_unit_us(100_000) == 100_000


def test_build_straight_timing_profile_uses_robust_medians() -> None:
    samples = [
        TimingProfileSample(session_id=index, source="straight", element_unit_us=100_000, gap_unit_us=100_000, dot_us=100_000, dash_us=300_000, letter_gap_us=300_000, word_gap_us=700_000, event_count=10)
        for index in range(1, 31)
    ]

    profile = build_timing_profile(samples, source="straight")

    assert profile.source == "straight"
    assert profile.element_unit_us == 100_000
    assert profile.gap_unit_us == 100_000
    assert profile.dash_dot_ratio == 3.0
    assert profile.sample_rounds == 30
    assert profile.sample_events == 300
    assert profile.updated_from_session_id == 30
    assert profile.has_element_seed is True


def test_build_iambic_timing_profile_derives_gap_unit_from_letter_and_word_gaps() -> None:
    samples = [
        TimingProfileSample(session_id=index, source="iambic", element_unit_us=100_000, letter_gap_us=330_000, word_gap_us=770_000, event_count=5)
        for index in range(1, 31)
    ]

    profile = build_timing_profile(samples, source="iambic")

    assert profile.source == "iambic"
    assert profile.element_unit_us == 100_000
    assert profile.gap_unit_us == 110_000
    assert profile.letter_gap_us == 330_000
    assert profile.word_gap_us == 770_000
