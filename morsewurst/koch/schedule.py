# ============================================================
# morsewurst/koch/schedule.py
# ============================================================

from __future__ import annotations

from morsewurst.core.scoring import CHAR_TO_MORSE
from morsewurst.koch.models import KochSettings


def koch_timing_ms(settings: KochSettings) -> dict[str, float]:
    """Return PARIS-based Farnsworth timing for Koch receive playback.

    Character WPM controls the dot length, dash length and intra-character
    element gaps. Effective WPM controls only the silence between characters
    and word/groups. The inter-character and word/group gaps share the same
    Farnsworth gap unit, so their normal 3:7 Morse timing relationship stays
    intact while the overall PARIS word duration matches the effective WPM.
    """

    normalized = settings.normalized()
    character_wpm = max(1.0, float(normalized.character_wpm))
    effective_wpm = max(1.0, float(normalized.effective_wpm))

    # Standard PARIS timing contains 50 dot units in total. Of those units,
    # 31 are inside the letters P A R I S, including their intra-character
    # element gaps. The remaining 19 are the four inter-character gaps plus
    # the trailing word gap. Farnsworth timing keeps the 31 internal units at
    # character WPM and stretches only the 19 external spacing units.
    paris_total_units = 50.0
    paris_internal_units = 31.0
    paris_spacing_units = 19.0

    element_unit_ms = 1200.0 / character_wpm

    if effective_wpm >= character_wpm:
        farnsworth_gap_unit_ms = element_unit_ms
    else:
        effective_unit_ms = 1200.0 / effective_wpm
        farnsworth_gap_unit_ms = (
            (paris_total_units * effective_unit_ms)
            - (paris_internal_units * element_unit_ms)
        ) / paris_spacing_units
        farnsworth_gap_unit_ms = max(element_unit_ms, farnsworth_gap_unit_ms)

    return {
        "element_unit_ms": element_unit_ms,
        "element_gap_ms": element_unit_ms,
        "farnsworth_gap_unit_ms": farnsworth_gap_unit_ms,
        "char_gap_ms": 3.0 * farnsworth_gap_unit_ms,
        "word_gap_ms": 7.0 * farnsworth_gap_unit_ms,
    }


def make_koch_target_schedule(
    target: str,
    settings: KochSettings,
) -> list[dict[str, int | str]]:
    """Build per-character timing metadata for scoring and latency analysis.

    The returned list contains one item for each audible target character. Its
    order matches the normalized target text used by the Koch scoring code
    where spaces are removed.
    """

    timing = koch_timing_ms(settings)
    element_unit_ms = timing["element_unit_ms"]
    element_gap_ms = timing["element_gap_ms"]
    char_gap_ms = timing["char_gap_ms"]
    word_gap_ms = timing["word_gap_ms"]

    schedule: list[dict[str, int | str]] = []
    current_ms = 0.0
    previous_symbol = False
    pending_word_gap = False
    position_index = 0

    for raw_char in str(target or "").upper():
        if raw_char.isspace():
            if previous_symbol:
                pending_word_gap = True
            continue

        code = CHAR_TO_MORSE.get(raw_char)
        if not code:
            continue

        if previous_symbol:
            current_ms += word_gap_ms if pending_word_gap else char_gap_ms

        start_ms = current_ms

        for element_index, element in enumerate(code):
            if element_index > 0:
                current_ms += element_gap_ms
            current_ms += element_unit_ms if element == "." else 3.0 * element_unit_ms

        end_ms = current_ms

        schedule.append(
            {
                "position_index": position_index,
                "char": raw_char,
                "code": code,
                "start_ms": int(round(start_ms)),
                "end_ms": int(round(end_ms)),
            }
        )

        position_index += 1
        previous_symbol = True
        pending_word_gap = False

    return schedule


def schedule_duration_ms(schedule: list[dict[str, int | str]]) -> int:
    if not schedule:
        return 0

    raw_end = schedule[-1].get("end_ms", 0)
    try:
        return max(0, int(raw_end))
    except (TypeError, ValueError):
        return 0
