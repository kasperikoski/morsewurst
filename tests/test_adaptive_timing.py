from __future__ import annotations

from morsewurst.core.adaptive_timing import (
    DecoderSettings,
    SourceTimingEstimate,
    estimate_adaptive_timing,
    normalize_tone_events,
)
from morsewurst.core.timing_profile import TimingProfile

from .conftest import make_tone_events


def _estimate_from_text(
    text: str,
    *,
    unit_us: int = 100_000,
    source: str = "iambic",
    include_hints: bool = True,
    settings: DecoderSettings | None = None,
):
    tones = normalize_tone_events(
        make_tone_events(
            text,
            unit_us=unit_us,
            source=source,
            include_hints=include_hints,
        )
    )
    return estimate_adaptive_timing(tones, settings or DecoderSettings(target_unit_us=unit_us))


def test_normalize_tone_events_filters_invalid_and_sorts_by_time() -> None:
    raw = [
        {"type": "tone", "t0": 200, "t1": 300, "dur": 100, "src": "iambic", "el": ".", "unit": "bad"},
        {"type": "noise", "t0": 0, "t1": 1, "dur": 1},
        {"type": "tone", "t0": 50, "t1": 150, "dur": 100, "src": "bad-source", "el": "x"},
        {"type": "tone", "t0": 500, "t1": 400, "dur": 100},
        {"type": "tone", "t0": "1", "t1": 2, "dur": 1},
        {"type": "tone", "t0": 1, "t1": 2, "dur": 0},
        "not-a-dict",
    ]

    tones = normalize_tone_events(raw)  # type: ignore[list-item]

    assert [tone.t0 for tone in tones] == [50, 200]
    assert tones[0].source == "unknown"
    assert tones[0].element_hint is None
    assert tones[0].firmware_unit_us is None
    assert tones[1].source == "iambic"
    assert tones[1].element_hint == "."


def test_normalize_tone_events_preserves_positive_unit_and_wpm_metadata() -> None:
    tones = normalize_tone_events(
        [
            {
                "type": "tone",
                "t0": 0,
                "t1": 100,
                "dur": 100,
                "src": "straight",
                "el": "-",
                "unit": 50_000,
                "wpm": 24,
            }
        ]
    )

    assert len(tones) == 1
    assert tones[0].firmware_unit_us == 50_000
    assert tones[0].wpm == 24
    assert tones[0].raw["dur"] == 100.0


def test_iambic_timing_uses_firmware_unit_as_authoritative_element_unit() -> None:
    tones = normalize_tone_events(make_tone_events("TEST", unit_us=90_000, source="iambic", include_hints=True))

    estimate = estimate_adaptive_timing(tones, DecoderSettings(target_unit_us=100_000))
    iambic = estimate.for_source("iambic")

    assert estimate.dominant_source == "iambic"
    assert estimate.primary_source == "iambic"
    assert estimate.element_unit_us == 90_000
    assert iambic.element_unit_us == 90_000
    assert iambic.element_confidence == 1.0
    assert iambic.using_target_element_anchor is False
    assert iambic.details["element"]["basis"] == "firmware_unit"
    assert iambic.details["element_blend"]["target_unit_ignored"] is True


def test_iambic_timing_uses_element_hints_when_firmware_unit_is_missing() -> None:
    events = make_tone_events("TEST", unit_us=80_000, source="iambic", include_hints=True)

    for event in events:
        event.pop("unit", None)
        event.pop("wpm", None)

    estimate = estimate_adaptive_timing(normalize_tone_events(events), DecoderSettings(target_unit_us=100_000))
    iambic = estimate.for_source("iambic")

    assert estimate.dominant_source == "iambic"
    assert 75_000 <= iambic.element_unit_us <= 85_000
    assert iambic.element_confidence > 0
    assert iambic.using_target_element_anchor is False
    assert iambic.details["element"]["basis"] == "element_hint"


def test_iambic_timing_falls_back_to_target_when_no_element_telemetry_exists() -> None:
    events = make_tone_events("TEST", unit_us=80_000, source="iambic", include_hints=False)

    for event in events:
        event.pop("unit", None)
        event.pop("wpm", None)

    estimate = estimate_adaptive_timing(normalize_tone_events(events), DecoderSettings(target_unit_us=100_000))
    iambic = estimate.for_source("iambic")

    assert iambic.element_unit_us == 100_000
    assert iambic.element_confidence == 0.0
    assert iambic.using_target_element_anchor is True
    assert iambic.details["element_blend"]["basis"] == "iambic_element_not_available"


def test_iambic_profile_spacing_sets_gap_unit_and_letter_word_gap_values() -> None:
    settings = DecoderSettings(
        target_unit_us=100_000,
        profile_iambic_letter_gap_us=420_000,
        profile_iambic_word_gap_us=980_000,
        profile_iambic_gap_confidence=0.75,
    )

    estimate = _estimate_from_text("ET", unit_us=100_000, source="iambic", include_hints=True, settings=settings)
    iambic = estimate.for_source("iambic")

    assert iambic.gap_unit_us == 140_000
    assert iambic.letter_gap_us == 420_000
    assert iambic.word_gap_us == 980_000
    assert iambic.gap_confidence == 0.75
    assert iambic.using_target_gap_anchor is False
    assert iambic.details["gap"]["has_external_spacing_profile"] is True


def test_straight_timing_learns_dot_and_dash_unit_from_durations() -> None:
    tones = normalize_tone_events(make_tone_events("SOS", unit_us=100_000, source="straight", include_hints=False))

    estimate = estimate_adaptive_timing(tones, DecoderSettings(target_unit_us=100_000))
    straight = estimate.for_source("straight")

    assert estimate.dominant_source == "straight"
    assert estimate.primary_source == "straight"
    assert 90_000 <= straight.element_unit_us <= 110_000
    assert straight.element_sample_count == len(tones)
    assert straight.element_confidence > 0
    assert straight.details["element"]["dot_us"] is not None
    assert straight.details["element"]["dash_us"] is not None


def test_straight_timing_uses_single_short_cluster_fallback_for_too_few_or_uniform_samples() -> None:
    tones = normalize_tone_events(
        [
            {"type": "tone", "t0": 0, "t1": 100_000, "dur": 100_000, "src": "straight"},
            {"type": "tone", "t0": 200_000, "t1": 300_000, "dur": 100_000, "src": "straight"},
            {"type": "tone", "t0": 400_000, "t1": 500_000, "dur": 100_000, "src": "straight"},
            {"type": "tone", "t0": 600_000, "t1": 700_000, "dur": 100_000, "src": "straight"},
        ]
    )

    estimate = estimate_adaptive_timing(tones, DecoderSettings(target_unit_us=120_000, straight_element_min_samples=4))
    straight = estimate.for_source("straight")

    assert straight.details["element"]["reason"] == "single short cluster fallback"
    assert 100_000 <= straight.element_unit_us <= 120_000
    assert straight.element_confidence < 0.30
    assert straight.using_target_element_anchor is True


def test_straight_gap_unit_is_not_allowed_below_element_floor() -> None:
    estimate = _estimate_from_text("EEEEE", unit_us=100_000, source="straight", include_hints=False)
    straight = estimate.for_source("straight")

    assert straight.gap_unit_us >= straight.element_unit_us * straight.details["gap_blend"]["element_floor_ratio"]
    assert "element_floor_applied" in straight.details["gap_blend"]


def test_mixed_sources_are_reported_as_mixed_with_straight_primary_on_tie() -> None:
    straight_events = make_tone_events("E", unit_us=100_000, source="straight", include_hints=False)
    iambic_events = make_tone_events("T", unit_us=90_000, source="iambic", include_hints=True)

    for event in iambic_events:
        t0_raw = event["t0"]
        t1_raw = event["t1"]

        assert isinstance(t0_raw, int)
        assert isinstance(t1_raw, int)

        event["t0"] = t0_raw + 500_000
        event["t1"] = t1_raw + 500_000

    estimate = estimate_adaptive_timing(
        normalize_tone_events(straight_events + iambic_events),
        DecoderSettings(target_unit_us=100_000),
    )

    assert estimate.dominant_source == "mixed"
    assert estimate.primary_source == "straight"
    assert estimate.for_source("iambic").element_unit_us == 90_000


def test_empty_timing_estimate_uses_straight_target_defaults() -> None:
    estimate = estimate_adaptive_timing([], DecoderSettings(target_unit_us=75_000))

    assert estimate.dominant_source == "straight"
    assert estimate.primary_source == "straight"
    assert estimate.target_unit_us == 75_000
    assert estimate.element_unit_us == 75_000
    assert estimate.gap_unit_us == 75_000
    assert estimate.for_source("unknown").source == "straight"


def test_timing_estimate_for_source_falls_back_to_primary_source() -> None:
    estimate = _estimate_from_text("TEST", unit_us=90_000, source="iambic", include_hints=True)

    assert estimate.for_source("not-real-source").source == "iambic"


def test_decoder_settings_resolved_target_unit_is_clamped_and_overridable() -> None:
    default = DecoderSettings(target_wpm=20)
    explicit = DecoderSettings(target_wpm=20, target_unit_us=50_000)
    too_small = DecoderSettings(target_unit_us=1)
    too_large = DecoderSettings(target_unit_us=5_000_000)

    assert default.resolved_target_unit_us() == 60_000
    assert explicit.resolved_target_unit_us() == 50_000
    assert too_small.resolved_target_unit_us() == too_small.min_element_unit_us
    assert too_large.resolved_target_unit_us() == too_large.max_element_unit_us


def test_decoder_settings_with_target_unit_ignores_invalid_values() -> None:
    settings = DecoderSettings(target_unit_us=100_000)

    assert settings.with_target_unit_us(None) is settings
    assert settings.with_target_unit_us(-1) is settings
    assert settings.with_target_unit_us(80_000).target_unit_us == 80_000


def test_decoder_settings_from_config_accepts_overrides_and_seed_unit() -> None:
    settings = DecoderSettings.from_config(
        target_wpm=25,
        seed_unit_us=70_000,
        unknown_char="?",
        not_a_setting="ignored",
    )

    assert settings.target_wpm == 25
    assert settings.target_unit_us == 70_000
    assert settings.unknown_char == "?"


def test_decoder_settings_profile_seeds_are_clamped_to_confidence_range() -> None:
    settings = DecoderSettings(
        profile_straight_element_unit_us=88_000,
        profile_straight_gap_unit_us=110_000,
        profile_straight_element_confidence=2.0,
        profile_straight_gap_confidence=-1.0,
        profile_iambic_element_unit_us=77_000,
        profile_iambic_gap_unit_us=99_000,
        profile_iambic_element_confidence=0.5,
        profile_iambic_gap_confidence=0.6,
    )

    assert settings.profile_element_seed("straight") == (88_000, 1.0)
    assert settings.profile_gap_seed("straight") == (110_000, 0.0)
    assert settings.profile_element_seed("iambic") == (77_000, 0.5)
    assert settings.profile_gap_seed("iambic") == (99_000, 0.6)


def test_decoder_settings_with_profiles_copies_profile_values() -> None:
    straight = TimingProfile(
        source="straight",
        element_unit_us=90_000,
        gap_unit_us=120_000,
        element_confidence=0.8,
        gap_confidence=0.7,
        letter_gap_us=360_000,
        word_gap_us=840_000,
    )
    iambic = TimingProfile(
        source="iambic",
        element_unit_us=75_000,
        gap_unit_us=95_000,
        element_confidence=0.6,
        gap_confidence=0.5,
        letter_gap_us=300_000,
        word_gap_us=700_000,
    )

    settings = DecoderSettings().with_profiles(straight=straight, iambic=iambic)

    assert settings.profile_straight_element_unit_us == 90_000
    assert settings.profile_straight_gap_unit_us == 120_000
    assert settings.profile_straight_element_confidence == 0.8
    assert settings.profile_straight_gap_confidence == 0.7
    assert settings.profile_straight_letter_gap_us == 360_000
    assert settings.profile_straight_word_gap_us == 840_000
    assert settings.profile_iambic_element_unit_us == 75_000
    assert settings.profile_iambic_gap_unit_us == 95_000
    assert settings.profile_iambic_element_confidence == 0.6
    assert settings.profile_iambic_gap_confidence == 0.5
    assert settings.profile_iambic_letter_gap_us == 300_000
    assert settings.profile_iambic_word_gap_us == 700_000


def test_source_timing_estimate_exposes_expected_fields() -> None:
    estimate = _estimate_from_text("E", unit_us=100_000, source="iambic", include_hints=True)
    iambic = estimate.for_source("iambic")

    assert isinstance(iambic, SourceTimingEstimate)
    assert iambic.source == "iambic"
    assert iambic.target_unit_us == 100_000
    assert iambic.element_sample_count == 1
    assert iambic.gap_sample_count == 0
    assert isinstance(iambic.details, dict)