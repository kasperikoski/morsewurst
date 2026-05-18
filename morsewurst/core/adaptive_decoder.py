# ============================================================
# morsewurst/core/adaptive_decoder.py
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from morsewurst.core.adaptive_timing import (
    DecoderSettings,
    NormalizedToneEvent,
    SourceTimingEstimate,
    TimingEstimate,
    estimate_adaptive_timing,
    normalize_tone_events,
)


MORSE_TO_CHAR: dict[str, str] = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E",
    "..-.": "F", "--.": "G", "....": "H", "..": "I", ".---": "J",
    "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O",
    ".--.": "P", "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X", "-.--": "Y", "--..": "Z",
    "-----": "0", ".----": "1", "..---": "2", "...--": "3", "....-": "4",
    ".....": "5", "-....": "6", "--...": "7", "---..": "8", "----.": "9",
    ".-.-.-": ".", "--..--": ",", "..--..": "?", "-.-.--": "!", "-..-.": "/",
    "-.--.": "(", "-.--.-": ")", ".-...": "&", "---...": ":", "-.-.-.": ";",
    "-...-": "=", ".-.-.": "+", "-....-": "-", "..--.-": "_", ".-..-.": '"',
    ".--.-.": "@", "...-..-": "$", ".----.": "'",
}


@dataclass
class DecodedTelemetry:
    text: str
    symbols: list[str]
    timing: TimingEstimate
    pending_symbol: str = ""
    char_infos: list[dict[str, Any]] = field(default_factory=list)
    element_infos: list[dict[str, Any]] = field(default_factory=list)
    gap_infos: list[dict[str, Any]] = field(default_factory=list)
    rescue_attempts: list[dict[str, Any]] = field(default_factory=list)

    def timing_for_source(self, source: Any) -> SourceTimingEstimate:
        return self.timing.for_source(source)

    @property
    def element_unit_us(self) -> float:
        return self.timing.element_unit_us

    @property
    def gap_unit_us(self) -> float:
        return self.timing.gap_unit_us

    @property
    def visual_unit_us(self) -> float:
        return min(self.element_unit_us, self.gap_unit_us)

    @property
    def unit_us(self) -> float:
        # Backward-compatible convenience property for older drawing code.
        return self.gap_unit_us

    @property
    def soft_boundary_count(self) -> int:
        return sum(1 for info in self.gap_infos if bool(info.get("soft_boundary")))


def _decode_symbol(symbol: str, settings: DecoderSettings) -> str:
    return MORSE_TO_CHAR.get(symbol, settings.unknown_char or "?")


def _letter_gap_units(source: str, settings: DecoderSettings) -> float:
    return float(settings.iambic_letter_gap_units if source == "iambic" else settings.straight_letter_gap_units)


def _word_gap_units(source: str, settings: DecoderSettings) -> float:
    return float(settings.iambic_word_gap_units if source == "iambic" else settings.straight_word_gap_units)


def _live_final_settle_units(source: str, settings: DecoderSettings) -> float:
    return float(settings.iambic_live_final_settle_units if source == "iambic" else settings.straight_live_final_settle_units)


def _cutoff(gap_unit_us: float, units: float, tolerance_units: float) -> float:
    return max(0.0, float(units) - float(tolerance_units)) * max(1.0, float(gap_unit_us))


def _positive_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except Exception:
        return None

    if number <= 0:
        return None

    if number != number:
        return None

    if number in (float("inf"), float("-inf")):
        return None

    return number


def _gap_cutoffs(
    estimate: SourceTimingEstimate,
    source: str,
    settings: DecoderSettings,
) -> tuple[float, float, str]:
    gap_unit_us = max(1.0, float(estimate.gap_unit_us))

    default_letter_cutoff_us = _cutoff(
        gap_unit_us,
        _letter_gap_units(source, settings),
        settings.gap_tolerance_units,
    )

    default_word_cutoff_us = _cutoff(
        gap_unit_us,
        _word_gap_units(source, settings),
        settings.gap_tolerance_units,
    )

    if source != "iambic":
        return default_letter_cutoff_us, default_word_cutoff_us, "unit_ratio"

    profile_letter_gap_us = _positive_float(getattr(estimate, "letter_gap_us", None))
    profile_word_gap_us = _positive_float(getattr(estimate, "word_gap_us", None))

    if profile_letter_gap_us is None or profile_word_gap_us is None:
        return default_letter_cutoff_us, default_word_cutoff_us, "standard_iambic_unit_ratio"

    element_unit_us = max(1.0, float(estimate.element_unit_us))

    letter_cutoff_us = (element_unit_us + profile_letter_gap_us) / 2.0
    word_cutoff_us = (profile_letter_gap_us + profile_word_gap_us) / 2.0

    word_cutoff_us = max(
        word_cutoff_us,
        letter_cutoff_us + element_unit_us * 0.50,
    )

    return letter_cutoff_us, word_cutoff_us, "iambic_profile_letter_word"


def _live_finish_cutoff_us(
    estimate: SourceTimingEstimate,
    source: str,
    settings: DecoderSettings,
) -> float:
    letter_cutoff_us, _word_cutoff_us, _basis = _gap_cutoffs(
        estimate,
        source,
        settings,
    )

    settle_us = (
        _live_final_settle_units(source, settings)
        * max(1.0, float(estimate.gap_unit_us))
    )

    return letter_cutoff_us + settle_us


def _classify_gap(previous: NormalizedToneEvent, current: NormalizedToneEvent, timing: TimingEstimate, settings: DecoderSettings) -> dict[str, Any]:
    source = previous.source
    estimate = timing.for_source(source)
    gap_us = max(0, int(current.t0) - int(previous.t1))
    gap_unit_us = max(1.0, float(estimate.gap_unit_us))
    gap_units = float(gap_us) / gap_unit_us

    letter_cutoff_us, word_cutoff_us, cutoff_basis = _gap_cutoffs(
        estimate,
        source,
        settings,
    )

    if gap_us >= word_cutoff_us:
        kind = "word"
        boundary = "hard"
    elif gap_us >= letter_cutoff_us:
        kind = "letter"
        boundary = "hard"
    else:
        kind = "intra"
        boundary = "none"

    return {
        "kind": kind,
        "boundary_kind": boundary,
        "soft_boundary": False,
        "source": source,
        "gap_us": gap_us,
        "gap_units": gap_units,
        "gap_unit_us": gap_unit_us,
        "letter_cutoff_us": letter_cutoff_us,
        "word_cutoff_us": word_cutoff_us,
        "cutoff_basis": cutoff_basis,
        "profile_letter_gap_us": getattr(estimate, "letter_gap_us", None),
        "profile_word_gap_us": getattr(estimate, "word_gap_us", None),
        "from_t1": int(previous.t1),
        "to_t0": int(current.t0),
    }


def _event_element(event: NormalizedToneEvent, source_timing: SourceTimingEstimate, settings: DecoderSettings) -> str:
    if event.source == "iambic" and event.element_hint in {".", "-"}:
        return event.element_hint

    unit_us = max(1.0, float(source_timing.element_unit_us))
    threshold = float(settings.straight_dit_dah_threshold if event.source == "straight" else 2.0)
    return "-" if float(event.dur) >= unit_us * threshold else "."


def _element_info(event: NormalizedToneEvent, element: str, source_timing: SourceTimingEstimate) -> dict[str, Any]:
    element_unit_us = max(1.0, float(source_timing.element_unit_us))
    wpm = 1_200_000.0 / element_unit_us if element_unit_us > 0 else None
    return {
        "element": element,
        "src": event.source,
        "source": event.source,
        "t0": int(event.t0),
        "t1": int(event.t1),
        "dur": float(event.dur),
        "element_unit_us": element_unit_us,
        "gap_unit_us": float(source_timing.gap_unit_us),
        "unit_us": element_unit_us,
        "dit_us": element_unit_us,
        "wpm": wpm,
        "hint": event.element_hint,
    }


def _char_info(
    *,
    decoded_char: str,
    code: str,
    elements: list[dict[str, Any]],
    gap_before_us: Optional[int],
    gap_before_units: Optional[float],
    gap_kind: Optional[str],
) -> dict[str, Any]:
    first = elements[0] if elements else {}
    last = elements[-1] if elements else {}
    source = str(first.get("source") or first.get("src") or "unknown")
    return {
        "ch": decoded_char,
        "code": code,
        "source": source,
        "char_time_us": int(last.get("t1") or 0),
        "first_element_us": int(first.get("t0")) if isinstance(first.get("t0"), int) else None,
        "last_element_us": int(last.get("t1")) if isinstance(last.get("t1"), int) else None,
        "gap_before_us": gap_before_us,
        "gap_before_units": gap_before_units,
        "gap_kind": gap_kind,
        "boundary_kind": "hard" if gap_kind in {"letter", "word"} else None,
        "element_unit_us": first.get("element_unit_us"),
        "gap_unit_us": first.get("gap_unit_us"),
        "dit_us": first.get("dit_us"),
        "wpm": first.get("wpm"),
        "soft_boundary_rescue": False,
        "rescue_original_code": None,
        "rescue_confidence": None,
        "rescue_kind": None,
    }


def _space_info(gap_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "ch": " ",
        "code": None,
        "source": "gap",
        "char_time_us": int(gap_info.get("to_t0") or 0),
        "first_element_us": None,
        "last_element_us": None,
        "gap_before_us": int(gap_info.get("gap_us") or 0),
        "gap_before_units": float(gap_info.get("gap_units") or 0.0),
        "gap_kind": "word",
        "boundary_kind": "hard",
        "element_unit_us": None,
        "gap_unit_us": float(gap_info.get("gap_unit_us") or 0.0),
        "dit_us": None,
        "wpm": None,
        "soft_boundary_rescue": False,
        "rescue_original_code": None,
        "rescue_confidence": None,
        "rescue_kind": None,
    }


def decode_tone_events(
    events: list[dict[str, Any]],
    *,
    current_time_us: Optional[int] = None,
    flush_final: bool = False,
    seed_unit_us: Optional[float] = None,
    settings: Optional[DecoderSettings] = None,
    target_wpm: Optional[float] = None,
    target_text: Optional[str] = None,
) -> DecodedTelemetry:
    """Decode tone events into Morse text."""

    if settings is None:
        settings = DecoderSettings.from_config(target_wpm=target_wpm, seed_unit_us=seed_unit_us)
    elif seed_unit_us is not None:
        settings = settings.with_target_unit_us(seed_unit_us)

    tones = normalize_tone_events(events)
    timing = estimate_adaptive_timing(tones, settings)

    text_parts: list[str] = []
    symbols: list[str] = []
    char_infos: list[dict[str, Any]] = []
    element_infos: list[dict[str, Any]] = []
    gap_infos: list[dict[str, Any]] = []

    current_symbol = ""
    current_elements: list[dict[str, Any]] = []
    current_gap_before_us: Optional[int] = None
    current_gap_before_units: Optional[float] = None
    current_gap_kind: Optional[str] = None

    def reset_current() -> None:
        nonlocal current_symbol, current_elements, current_gap_before_us, current_gap_before_units, current_gap_kind
        current_symbol = ""
        current_elements = []
        current_gap_before_us = None
        current_gap_before_units = None
        current_gap_kind = None

    def finish_current() -> None:
        if not current_symbol:
            reset_current()
            return
        decoded_char = _decode_symbol(current_symbol, settings)
        symbols.append(current_symbol)
        text_parts.append(decoded_char)
        char_infos.append(
            _char_info(
                decoded_char=decoded_char,
                code=current_symbol,
                elements=current_elements,
                gap_before_us=current_gap_before_us,
                gap_before_units=current_gap_before_units,
                gap_kind=current_gap_kind,
            )
        )
        reset_current()

    previous: Optional[NormalizedToneEvent] = None

    for event in tones:
        if previous is not None:
            gap = _classify_gap(previous, event, timing, settings)
            gap_infos.append(gap)
            if gap["kind"] == "word":
                finish_current()
                if text_parts and text_parts[-1] != " ":
                    text_parts.append(" ")
                    char_infos.append(_space_info(gap))
                current_gap_before_us = int(gap["gap_us"])
                current_gap_before_units = float(gap["gap_units"])
                current_gap_kind = "word"
            elif gap["kind"] == "letter":
                finish_current()
                current_gap_before_us = int(gap["gap_us"])
                current_gap_before_units = float(gap["gap_units"])
                current_gap_kind = "letter"

        source_timing = timing.for_source(event.source)
        element = _event_element(event, source_timing, settings)
        info = _element_info(event, element, source_timing)
        element_infos.append(info)
        current_elements.append(info)
        current_symbol += element
        previous = event

    if previous is not None and current_symbol:
        should_finish = bool(flush_final)
        if not should_finish and current_time_us is not None:
            source_timing = timing.for_source(previous.source)
            silence_us = max(0, int(current_time_us) - int(previous.t1))
            required_us = _live_finish_cutoff_us(
                source_timing,
                previous.source,
                settings,
            )
            should_finish = silence_us >= required_us
        if should_finish:
            finish_current()

    return DecodedTelemetry(
        text="".join(text_parts),
        symbols=symbols,
        timing=timing,
        pending_symbol=current_symbol,
        char_infos=char_infos,
        element_infos=element_infos,
        gap_infos=gap_infos,
        rescue_attempts=[],
    )
