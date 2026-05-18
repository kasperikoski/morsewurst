from __future__ import annotations

from morsewurst.core.adaptive_decoder import decode_tone_events
from morsewurst.core.adaptive_timing import DecoderSettings

from .conftest import make_tone_events


def _decode(
    text: str,
    *,
    unit_us: int = 100_000,
    source: str = "iambic",
    include_hints: bool = True,
    settings: DecoderSettings | None = None,
    flush_final: bool = True,
):
    events = make_tone_events(text, unit_us=unit_us, source=source, include_hints=include_hints)
    return decode_tone_events(
        events,
        flush_final=flush_final,
        settings=settings or DecoderSettings(target_unit_us=unit_us),
    )


def _manual_iambic_events_for_symbol(symbol: str, *, unit_us: int = 100_000) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    t = 0

    for index, element in enumerate(symbol):
        if index > 0:
            t += unit_us

        duration = unit_us if element == "." else 3 * unit_us

        events.append(
            {
                "type": "tone",
                "t0": t,
                "t1": t + duration,
                "dur": float(duration),
                "src": "iambic",
                "unit": unit_us,
                "wpm": 1_200_000.0 / unit_us,
                "el": element,
            }
        )

        t += duration

    return events


def test_iambic_decoder_decodes_known_message() -> None:
    decoded = _decode("SOS", source="iambic", include_hints=True)

    assert decoded.text == "SOS"
    assert decoded.symbols == ["...", "---", "..."]
    assert decoded.pending_symbol == ""
    assert decoded.timing.dominant_source == "iambic"
    assert decoded.timing.primary_source == "iambic"
    assert decoded.timing.for_source("iambic").element_sample_count == len(decoded.element_infos)


def test_decoder_preserves_word_gap_as_space() -> None:
    decoded = _decode("E T", source="iambic", include_hints=True)

    assert decoded.text == "E T"
    assert [info["ch"] for info in decoded.char_infos] == ["E", " ", "T"]
    assert any(info["kind"] == "word" for info in decoded.gap_infos)
    assert any(info["ch"] == " " and info["gap_kind"] == "word" for info in decoded.char_infos)


def test_decoder_records_letter_gap_metadata_between_characters() -> None:
    decoded = _decode("ET", source="iambic", include_hints=True)

    assert decoded.text == "ET"
    assert [info["ch"] for info in decoded.char_infos] == ["E", "T"]
    assert decoded.char_infos[1]["gap_kind"] == "letter"
    assert decoded.char_infos[1]["gap_before_us"] is not None
    assert decoded.char_infos[1]["gap_before_units"] is not None
    assert any(info["kind"] == "letter" for info in decoded.gap_infos)


def test_live_decode_keeps_final_symbol_pending_until_flushed_or_idle() -> None:
    events = make_tone_events("E", source="iambic", include_hints=True)

    live = decode_tone_events(
        events,
        current_time_us=120_000,
        flush_final=False,
        settings=DecoderSettings(target_unit_us=100_000),
    )
    flushed = decode_tone_events(
        events,
        flush_final=True,
        settings=DecoderSettings(target_unit_us=100_000),
    )
    idle_finished = decode_tone_events(
        events,
        current_time_us=700_000,
        flush_final=False,
        settings=DecoderSettings(target_unit_us=100_000),
    )

    assert live.text == ""
    assert live.symbols == []
    assert live.pending_symbol == "."
    assert flushed.text == "E"
    assert flushed.pending_symbol == ""
    assert idle_finished.text == "E"
    assert idle_finished.pending_symbol == ""


def test_straight_decoder_classifies_by_duration_when_no_element_hints_exist() -> None:
    events = make_tone_events("SOS", source="straight", include_hints=False)

    decoded = decode_tone_events(
        events,
        flush_final=True,
        settings=DecoderSettings(target_unit_us=100_000),
    )

    assert decoded.text == "SOS"
    assert decoded.symbols == ["...", "---", "..."]
    assert decoded.timing.dominant_source == "straight"
    assert decoded.timing.for_source("straight").element_sample_count == len(events)
    assert all(info["source"] == "straight" for info in decoded.element_infos)


def test_iambic_decoder_uses_element_hints_when_duration_would_be_ambiguous() -> None:
    events = make_tone_events("T", source="iambic", include_hints=True)

    for event in events:
        t0_raw = event["t0"]
        assert isinstance(t0_raw, int)

        event["dur"] = 100_000.0
        event["t1"] = t0_raw + 100_000

    decoded = decode_tone_events(
        events,
        flush_final=True,
        settings=DecoderSettings(target_unit_us=100_000),
    )

    assert decoded.text == "T"
    assert decoded.symbols == ["-"]
    assert decoded.element_infos[0]["hint"] == "-"


def test_straight_decoder_ignores_wrong_element_hints_and_uses_duration() -> None:
    events = make_tone_events("T", source="straight", include_hints=True)
    events[0]["el"] = "."

    decoded = decode_tone_events(
        events,
        flush_final=True,
        settings=DecoderSettings(target_unit_us=100_000),
    )

    assert decoded.text == "T"
    assert decoded.symbols == ["-"]


def test_unknown_morse_symbol_uses_settings_unknown_char() -> None:
    events = _manual_iambic_events_for_symbol("......", unit_us=100_000)

    decoded = decode_tone_events(
        events,
        flush_final=True,
        settings=DecoderSettings(target_unit_us=100_000, unknown_char="?"),
    )

    assert decoded.text == "?"
    assert decoded.symbols == ["......"]
    assert decoded.char_infos[0]["code"] == "......"


def test_empty_or_invalid_events_return_empty_decoding_with_target_timing() -> None:
    decoded = decode_tone_events(
        [
            {"type": "noise", "t0": 0, "t1": 1, "dur": 1},
            {"type": "tone", "t0": 10, "t1": 1, "dur": 1},
        ],
        flush_final=True,
        settings=DecoderSettings(target_unit_us=80_000),
    )

    assert decoded.text == ""
    assert decoded.symbols == []
    assert decoded.pending_symbol == ""
    assert decoded.char_infos == []
    assert decoded.element_infos == []
    assert decoded.gap_infos == []
    assert decoded.timing.target_unit_us == 80_000


def test_decoded_telemetry_unit_properties_follow_primary_source() -> None:
    decoded = _decode("E", unit_us=75_000, source="iambic", include_hints=True)

    assert decoded.element_unit_us == decoded.timing.element_unit_us
    assert decoded.gap_unit_us == decoded.timing.gap_unit_us
    assert decoded.visual_unit_us == min(decoded.element_unit_us, decoded.gap_unit_us)
    assert decoded.unit_us == decoded.gap_unit_us
    assert decoded.timing_for_source("iambic") == decoded.timing.for_source("iambic")


def test_element_infos_include_timing_fields_for_each_tone() -> None:
    events = make_tone_events("A", source="iambic", include_hints=True)

    decoded = decode_tone_events(
        events,
        flush_final=True,
        settings=DecoderSettings(target_unit_us=100_000),
    )

    assert decoded.text == "A"
    assert [info["element"] for info in decoded.element_infos] == [".", "-"]
    assert all(info["element_unit_us"] > 0 for info in decoded.element_infos)
    assert all(info["gap_unit_us"] > 0 for info in decoded.element_infos)
    assert all(info["dit_us"] > 0 for info in decoded.element_infos)
    assert all(info["wpm"] is not None for info in decoded.element_infos)


def test_word_gap_does_not_create_duplicate_spaces() -> None:
    events = make_tone_events("E   T", source="iambic", include_hints=True)

    decoded = decode_tone_events(
        events,
        flush_final=True,
        settings=DecoderSettings(target_unit_us=100_000),
    )

    assert decoded.text == "E T"
    assert [info["ch"] for info in decoded.char_infos].count(" ") == 1