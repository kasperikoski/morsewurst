# ============================================================
# morsewurst/core/timing_quality.py
# ============================================================

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean, pstdev
from typing import Any, Iterable, Optional

import morsewurst.config as config
from morsewurst.core.adaptive_decoder import MORSE_TO_CHAR, decode_tone_events


@dataclass
class SourceTimingQuality:
    source: str
    ok: bool
    reason: str

    used_rounds: int
    element_count: int
    dot_count: int
    dash_count: int
    letter_gap_count: int
    word_gap_count: int

    dot_consistency_score: Optional[float]
    dash_consistency_score: Optional[float]
    dash_dot_ratio_score: Optional[float]
    gap_score: Optional[float]

    total_score: Optional[float]


@dataclass
class RoundTimingQuality:
    ok: bool
    reason: str

    total_score: Optional[float]
    factor: float

    source: str
    straight_score: Optional[float]
    iambic_score: Optional[float]

    element_score: Optional[float]
    gap_score: Optional[float]
    ratio_score: Optional[float]
    dot_consistency_score: Optional[float]
    dash_consistency_score: Optional[float]
    intra_gap_score: Optional[float]
    letter_gap_score: Optional[float]
    word_gap_score: Optional[float]

    details: dict[str, Any]


@dataclass
class TimingQuality:
    ok: bool
    reason: str

    used_rounds: int
    total_score: Optional[float]
    factor: float

    straight: SourceTimingQuality
    iambic: SourceTimingQuality

    details: dict[str, Any]


def _cfg(name: str, default: Any) -> Any:
    return getattr(config, name, default)


def _source_specific_weight(
    prefix: str,
    source_name: str,
    kind: str,
    default: float,
) -> float:
    source_key = str(source_name or "").upper()
    kind_key = str(kind or "").upper()

    specific_name = f"{prefix}_{source_key}_{kind_key}_GAP_WEIGHT"

    try:
        return float(_cfg(specific_name, default))
    except Exception:
        return float(default)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _safe_mean(values: Iterable[float]) -> Optional[float]:
    cleaned = [float(value) for value in values if isinstance(value, (int, float))]

    if not cleaned:
        return None

    return float(mean(cleaned))


def _weighted_average(parts: list[tuple[Optional[float], float]]) -> Optional[float]:
    numerator = 0.0
    denominator = 0.0

    for value, weight in parts:
        if value is None:
            continue

        weight = max(0.0, float(weight))

        if weight <= 0:
            continue

        numerator += float(value) * weight
        denominator += weight

    if denominator <= 0:
        return None

    return numerator / denominator


def _consistency_score(values: list[float]) -> Optional[float]:
    """Return 0..100 score from duration consistency.

    Uses population coefficient of variation: stdev / mean.
    """

    if len(values) < 2:
        return None

    avg = mean(values)

    if avg <= 0:
        return None

    cv = pstdev(values) / avg
    zero_at = float(_cfg("SKILL_RATING_TIMING_CONSISTENCY_CV_AT_ZERO", 0.70))

    if zero_at <= 0:
        zero_at = 0.70

    return _clamp(100.0 * (1.0 - (cv / zero_at)), 0.0, 100.0)


def _dash_dot_ratio_score(dot_values: list[float], dash_values: list[float]) -> Optional[float]:
    if not dot_values or not dash_values:
        return None

    dot_avg = mean(dot_values)
    dash_avg = mean(dash_values)

    if dot_avg <= 0 or dash_avg <= 0:
        return None

    ratio = dash_avg / dot_avg

    target = float(_cfg("SKILL_RATING_DASH_DOT_RATIO_TARGET", 3.0))
    zero_at = float(_cfg("SKILL_RATING_DASH_DOT_RATIO_ERROR_AT_ZERO", 1.50))

    if zero_at <= 0:
        zero_at = 1.50

    error = abs(ratio - target)

    return _clamp(100.0 * (1.0 - (error / zero_at)), 0.0, 100.0)


def _gap_target_units(source: str, kind: str) -> float:
    source = source.lower()
    kind = kind.lower()

    if source == "iambic":
        if kind == "word":
            return float(_cfg("SKILL_RATING_IAMBIC_WORD_GAP_UNITS", 7.0))
        return float(_cfg("SKILL_RATING_IAMBIC_LETTER_GAP_UNITS", 3.0))

    if kind == "word":
        return float(_cfg("SKILL_RATING_STRAIGHT_WORD_GAP_UNITS", 7.0))

    return float(_cfg("SKILL_RATING_STRAIGHT_LETTER_GAP_UNITS", 3.0))


def _gap_score_from_units(actual_units: float, target_units: float) -> float:
    zero_at = float(_cfg("SKILL_RATING_GAP_ERROR_AT_ZERO_UNITS", 3.0))

    if zero_at <= 0:
        zero_at = 3.0

    error = abs(float(actual_units) - float(target_units))

    return _clamp(100.0 * (1.0 - (error / zero_at)), 0.0, 100.0)


def _target_gap_expectations(
    target_text: Optional[str],
    *,
    source_name: str,
) -> dict[str, int]:
    """Return expected gap counts from the target text.

    Straight key:
    - intra-character gaps are scored, because the sender controls them
    - letter gaps are scored
    - word gaps are scored

    Iambic:
    - intra-character gaps are NOT scored, because the keyer creates them
    - letter gaps are scored
    - word gaps are scored
    """

    source_name = str(source_name or "").lower()

    if not target_text:
        return {
            "intra": 0,
            "letter": 0,
            "word": 0,
            "chars": 0,
        }

    char_to_morse = {value: key for key, value in MORSE_TO_CHAR.items()}
    normalized = str(target_text).upper().replace("\n", " ")
    groups = [group for group in normalized.split(" ") if group]

    intra_count = 0
    letter_count = 0
    word_count = max(0, len(groups) - 1)
    char_count = 0

    for group in groups:
        group_chars = [ch for ch in group if ch in char_to_morse]
        char_count += len(group_chars)

        if len(group_chars) >= 2:
            letter_count += len(group_chars) - 1

        if source_name != "iambic":
            for ch in group_chars:
                code = char_to_morse.get(ch, "")
                if len(code) >= 2:
                    intra_count += len(code) - 1

    return {
        "intra": intra_count,
        "letter": letter_count,
        "word": word_count,
        "chars": char_count,
    }


def _apply_missing_expected_scores(
    scores: list[float],
    *,
    expected_count: Optional[int],
) -> list[float]:
    if expected_count is None:
        return scores

    expected_count = max(0, int(expected_count))
    if expected_count <= len(scores):
        return scores

    # Missing expected gaps are real timing evidence: if the target contained a
    # letter gap and the decoded telemetry never produced one, that part of the
    # rhythm should not receive a free pass.
    return scores + [0.0] * (expected_count - len(scores))


def _source_quality_from_events(
    sessions: list[dict[str, Any]],
    source_name: str,
) -> SourceTimingQuality:
    source_name = source_name.lower()

    min_elements = int(_cfg("SKILL_RATING_TIMING_MIN_ELEMENTS", 8))
    min_dots = int(_cfg("SKILL_RATING_TIMING_MIN_DOTS", 3))
    min_dashes = int(_cfg("SKILL_RATING_TIMING_MIN_DASHES", 3))
    min_gaps = int(_cfg("SKILL_RATING_TIMING_MIN_GAPS", 3))

    letter_gap_min_units = float(_cfg("SKILL_RATING_LETTER_GAP_MIN_UNITS", 2.0))
    word_gap_min_units = float(_cfg("SKILL_RATING_WORD_GAP_MIN_UNITS", 5.0))

    dot_values: list[float] = []
    dash_values: list[float] = []
    letter_gap_scores: list[float] = []
    word_gap_scores: list[float] = []

    used_round_ids: set[int] = set()

    for session in sessions:
        events = session.get("events") or []

        if not isinstance(events, list) or not events:
            continue

        decoded = decode_tone_events(events, flush_final=True)
        elements = list(decoded.element_infos)
        gap_infos = list(getattr(decoded, "gap_infos", []))

        if not elements:
            continue

        session_used = False

        for element in elements:
            if str(element.get("src", "")).lower() != source_name:
                continue

            duration = element.get("dur")
            element_name = element.get("element")

            if not isinstance(duration, (int, float)):
                continue

            if element_name == ".":
                dot_values.append(float(duration))
                session_used = True

            elif element_name == "-":
                dash_values.append(float(duration))
                session_used = True

        if gap_infos:
            for gap_info in gap_infos:
                previous_source = str(gap_info.get("source", "")).lower()

                if previous_source != source_name:
                    continue

                gap_kind = str(gap_info.get("kind", "")).lower()
                gap_units = gap_info.get("gap_units")

                if not isinstance(gap_units, (int, float)):
                    continue

                if gap_kind == "word":
                    target_units = _gap_target_units(source_name, "word")
                    word_gap_scores.append(
                        _gap_score_from_units(float(gap_units), target_units)
                    )
                    session_used = True

                elif gap_kind == "letter":
                    target_units = _gap_target_units(source_name, "letter")
                    letter_gap_scores.append(
                        _gap_score_from_units(float(gap_units), target_units)
                    )
                    session_used = True

        else:
            for previous, current in zip(elements, elements[1:]):
                previous_source = str(previous.get("src", "")).lower()

                if previous_source != source_name:
                    continue

                previous_t1 = previous.get("t1")
                current_t0 = current.get("t0")
                previous_gap_unit = previous.get("gap_unit_us") or previous.get("unit_us")

                if not isinstance(previous_t1, int):
                    continue

                if not isinstance(current_t0, int):
                    continue

                if not isinstance(previous_gap_unit, (int, float)):
                    continue

                if float(previous_gap_unit) <= 0:
                    continue

                gap_us = max(0.0, float(current_t0 - previous_t1))
                gap_units = gap_us / float(previous_gap_unit)

                if gap_units >= word_gap_min_units:
                    target_units = _gap_target_units(source_name, "word")
                    word_gap_scores.append(
                        _gap_score_from_units(gap_units, target_units)
                    )
                    session_used = True

                elif gap_units >= letter_gap_min_units:
                    target_units = _gap_target_units(source_name, "letter")
                    letter_gap_scores.append(
                        _gap_score_from_units(gap_units, target_units)
                    )
                    session_used = True

        if session_used:
            try:
                used_round_ids.add(int(session["id"]))
            except Exception:
                pass

    element_count = len(dot_values) + len(dash_values)
    dot_count = len(dot_values)
    dash_count = len(dash_values)
    letter_gap_count = len(letter_gap_scores)
    word_gap_count = len(word_gap_scores)

    dot_consistency = None
    dash_consistency = None
    ratio_score = None

    if source_name == "straight":
        if dot_count >= min_dots:
            dot_consistency = _consistency_score(dot_values)

        if dash_count >= min_dashes:
            dash_consistency = _consistency_score(dash_values)

        if dot_count >= min_dots and dash_count >= min_dashes:
            ratio_score = _dash_dot_ratio_score(dot_values, dash_values)

    letter_gap_score = (
        _safe_mean(letter_gap_scores)
        if letter_gap_count >= min_gaps
        else None
    )

    word_gap_score = (
        _safe_mean(word_gap_scores)
        if word_gap_count >= min_gaps
        else None
    )

    gap_score = _weighted_average(
        [
            (
                letter_gap_score,
                float(_cfg("SKILL_RATING_LETTER_GAP_WEIGHT", 0.75)),
            ),
            (
                word_gap_score,
                float(_cfg("SKILL_RATING_WORD_GAP_WEIGHT", 0.25)),
            ),
        ]
    )

    if source_name == "straight":
        if element_count < min_elements:
            total_score = gap_score
            reason = (
                "Straight-telemetriassa ei ole vielä tarpeeksi elementtejä "
                "pisteiden ja viivojen tasalaatuisuuden arviointiin."
            )
        else:
            total_score = _weighted_average(
                [
                    (
                        dot_consistency,
                        float(_cfg("SKILL_RATING_STRAIGHT_DOT_CONSISTENCY_WEIGHT", 0.25)),
                    ),
                    (
                        dash_consistency,
                        float(_cfg("SKILL_RATING_STRAIGHT_DASH_CONSISTENCY_WEIGHT", 0.25)),
                    ),
                    (
                        ratio_score,
                        float(_cfg("SKILL_RATING_STRAIGHT_DASH_DOT_RATIO_WEIGHT", 0.30)),
                    ),
                    (
                        gap_score,
                        float(_cfg("SKILL_RATING_STRAIGHT_GAP_WEIGHT", 0.20)),
                    ),
                ]
            )
            reason = ""
    else:
        total_score = _weighted_average(
            [
                (
                    gap_score,
                    float(_cfg("SKILL_RATING_IAMBIC_GAP_WEIGHT", 1.00)),
                ),
            ]
        )
        reason = ""

    if total_score is None:
        if source_name == "iambic":
            reason = "Iambic-telemetriassa ei ole vielä tarpeeksi kirjain- tai sanavälejä."
        elif not reason:
            reason = "Straight-telemetriassa ei ole vielä tarpeeksi ajoitusdataa."

    return SourceTimingQuality(
        source=source_name,
        ok=total_score is not None,
        reason=reason,
        used_rounds=len(used_round_ids),
        element_count=element_count,
        dot_count=dot_count,
        dash_count=dash_count,
        letter_gap_count=letter_gap_count,
        word_gap_count=word_gap_count,
        dot_consistency_score=None if dot_consistency is None else round(dot_consistency, 2),
        dash_consistency_score=None if dash_consistency is None else round(dash_consistency, 2),
        dash_dot_ratio_score=None if ratio_score is None else round(ratio_score, 2),
        gap_score=None if gap_score is None else round(gap_score, 2),
        total_score=None if total_score is None else round(total_score, 2),
    )


def _score_gap_infos_for_source(
    gap_infos: list[dict[str, Any]],
    source_name: str,
    *,
    prefix: str = "ROUND_TIMING",
    include_intra: bool = True,
    expected_counts: Optional[dict[str, int]] = None,
) -> dict[str, Any]:
    source_name = source_name.lower()
    expected_counts = expected_counts or {}

    intra_scores: list[float] = []
    letter_scores: list[float] = []
    word_scores: list[float] = []

    for gap_info in gap_infos:
        previous_source = str(gap_info.get("source", "")).lower()

        if previous_source != source_name:
            continue

        gap_kind = str(gap_info.get("kind", "")).lower()
        gap_units = gap_info.get("gap_units")

        if not isinstance(gap_units, (int, float)):
            continue

        if gap_kind == "word":
            target_units = _gap_target_units(source_name, "word")
            word_scores.append(_gap_score_from_units(float(gap_units), target_units))

        elif gap_kind == "letter":
            target_units = _gap_target_units(source_name, "letter")
            letter_scores.append(_gap_score_from_units(float(gap_units), target_units))

        elif gap_kind == "intra" and include_intra:
            intra_scores.append(_gap_score_from_units(float(gap_units), 1.0))

    if bool(_cfg("ROUND_TIMING_USE_TARGET_EXPECTATIONS", True)) and source_name != "iambic":
        if include_intra:
            intra_scores = _apply_missing_expected_scores(
                intra_scores,
                expected_count=expected_counts.get("intra"),
            )

        letter_scores = _apply_missing_expected_scores(
            letter_scores,
            expected_count=expected_counts.get("letter"),
        )

        word_scores = _apply_missing_expected_scores(
            word_scores,
            expected_count=expected_counts.get("word"),
        )

    intra_score = _safe_mean(intra_scores) if include_intra else None
    letter_score = _safe_mean(letter_scores)
    word_score = _safe_mean(word_scores)

    if include_intra:
        gap_score = _weighted_average(
            [
                (
                    intra_score,
                    _source_specific_weight(prefix, source_name, "INTRA", 0.30),
                ),
                (
                    letter_score,
                    _source_specific_weight(prefix, source_name, "LETTER", 0.55),
                ),
                (
                    word_score,
                    _source_specific_weight(prefix, source_name, "WORD", 0.15),
                ),
            ]
        )
    else:
        # Iambic keyer creates element timing and intra-character spacing. Round
        # timing for iambic should therefore only score the user's manual
        # letter/word gaps. If neither exists, return None instead of letting
        # perfect intra-keyer timing inflate the score.
        gap_score = _weighted_average(
            [
                (
                    letter_score,
                    _source_specific_weight(prefix, source_name, "LETTER", 0.75),
                ),
                (
                    word_score,
                    _source_specific_weight(prefix, source_name, "WORD", 0.25),
                ),
            ]
        )

    return {
        "gap_score": gap_score,
        "intra_gap_score": intra_score,
        "letter_gap_score": letter_score,
        "word_gap_score": word_score,
        "intra_gap_count": len(intra_scores),
        "letter_gap_count": len(letter_scores),
        "word_gap_count": len(word_scores),
    }


def _round_source_quality_from_decoded(
    decoded: Any,
    source_name: str,
    *,
    expected_counts: Optional[dict[str, int]] = None,
) -> dict[str, Any]:
    source_name = source_name.lower()

    dot_values: list[float] = []
    dash_values: list[float] = []

    for element in list(getattr(decoded, "element_infos", []) or []):
        if str(element.get("src", "")).lower() != source_name:
            continue

        duration = element.get("dur")
        element_name = element.get("element")

        if not isinstance(duration, (int, float)):
            continue

        if element_name == ".":
            dot_values.append(float(duration))
        elif element_name == "-":
            dash_values.append(float(duration))

    include_intra = source_name != "iambic"
    gap_data = _score_gap_infos_for_source(
        list(getattr(decoded, "gap_infos", []) or []),
        source_name,
        include_intra=include_intra,
        expected_counts=expected_counts,
    )

    if source_name == "straight":
        dot_consistency = _consistency_score(dot_values)
        dash_consistency = _consistency_score(dash_values)
        ratio_score = _dash_dot_ratio_score(dot_values, dash_values)
        element_score = _weighted_average(
            [
                (dot_consistency, 0.50),
                (dash_consistency, 0.50),
            ]
        )
    else:
        dot_consistency = None
        dash_consistency = None
        ratio_score = None
        element_score = None

    if source_name == "straight":
        total_score = _weighted_average(
            [
                (dot_consistency, float(_cfg("ROUND_TIMING_STRAIGHT_DOT_CONSISTENCY_WEIGHT", 0.20))),
                (dash_consistency, float(_cfg("ROUND_TIMING_STRAIGHT_DASH_CONSISTENCY_WEIGHT", 0.20))),
                (ratio_score, float(_cfg("ROUND_TIMING_STRAIGHT_DASH_DOT_RATIO_WEIGHT", 0.25))),
                (gap_data["gap_score"], float(_cfg("ROUND_TIMING_STRAIGHT_GAP_WEIGHT", 0.35))),
            ]
        )
    else:
        total_score = _weighted_average(
            [
                (gap_data["gap_score"], float(_cfg("ROUND_TIMING_IAMBIC_GAP_WEIGHT", 1.00))),
            ]
        )

    return {
        "source": source_name,
        "total_score": total_score,
        "element_score": element_score,
        "gap_score": gap_data["gap_score"],
        "ratio_score": ratio_score,
        "dot_consistency_score": dot_consistency,
        "dash_consistency_score": dash_consistency,
        "intra_gap_score": gap_data["intra_gap_score"],
        "letter_gap_score": gap_data["letter_gap_score"],
        "word_gap_score": gap_data["word_gap_score"],
        "dot_count": len(dot_values),
        "dash_count": len(dash_values),
        "intra_gap_count": gap_data["intra_gap_count"],
        "letter_gap_count": gap_data["letter_gap_count"],
        "word_gap_count": gap_data["word_gap_count"],
    }


def _round_factor_from_score(score: Optional[float]) -> float:
    min_factor = float(_cfg("ROUND_NET_WPM_TIMING_MIN_FACTOR", 0.90))
    max_factor = float(_cfg("ROUND_NET_WPM_TIMING_MAX_FACTOR", 1.00))

    if score is None:
        return 1.0

    score = _clamp(float(score), 0.0, 100.0)

    return _clamp(
        min_factor + ((score / 100.0) * (max_factor - min_factor)),
        min_factor,
        max_factor,
    )


def _round_value(data: dict[str, Any], key: str) -> Optional[float]:
    value = data.get(key)
    if value is None:
        return None
    return round(float(value), 2)


def calculate_round_timing_quality(
    events: list[dict[str, Any]],
    *,
    decoded: Any | None = None,
    target_text: Optional[str] = None,
) -> RoundTimingQuality:
    """Return round-level Morse rhythm quality from raw telemetry.

    This is intentionally separate from accuracy/cleanliness. It measures how
    close the actual element lengths and gaps are to Morse rhythm:

    - intra-character gaps around 1 unit
    - letter gaps around 3 units
    - word gaps around 7 units
    - straight-key dash/dot ratio around 3:1
    - straight-key dot and dash consistency
    """

    if decoded is None:
        decoded = decode_tone_events(events, flush_final=True)

    elements = list(getattr(decoded, "element_infos", []) or [])
    gap_infos = list(getattr(decoded, "gap_infos", []) or [])

    if not elements and not gap_infos:
        return RoundTimingQuality(
            ok=False,
            reason="Ei ajoitusdataa.",
            total_score=None,
            factor=1.0,
            source="unknown",
            straight_score=None,
            iambic_score=None,
            element_score=None,
            gap_score=None,
            ratio_score=None,
            dot_consistency_score=None,
            dash_consistency_score=None,
            intra_gap_score=None,
            letter_gap_score=None,
            word_gap_score=None,
            details={},
        )

    straight_expected_counts = _target_gap_expectations(
        target_text,
        source_name="straight",
    )
    iambic_expected_counts = _target_gap_expectations(
        target_text,
        source_name="iambic",
    )

    straight = _round_source_quality_from_decoded(
        decoded,
        "straight",
        expected_counts=straight_expected_counts,
    )
    iambic = _round_source_quality_from_decoded(
        decoded,
        "iambic",
        expected_counts=iambic_expected_counts,
    )

    dominant_source = "unknown"
    try:
        dominant_source = str(decoded.timing.dominant_source or "unknown").lower()
    except Exception:
        pass

    if dominant_source == "iambic":
        primary = iambic
        combined_score = iambic["total_score"]

    elif dominant_source == "straight":
        primary = straight
        combined_score = straight["total_score"]

    else:
        # Fallback only for genuinely mixed or unclear telemetry.
        combined_score = _weighted_average(
            [
                (straight["total_score"], float(_cfg("ROUND_TIMING_STRAIGHT_SOURCE_WEIGHT", 1.00))),
                (iambic["total_score"], float(_cfg("ROUND_TIMING_IAMBIC_SOURCE_WEIGHT", 0.60))),
            ]
        )

        if iambic["total_score"] is not None and straight["total_score"] is None:
            primary = iambic
        elif straight["total_score"] is not None and iambic["total_score"] is None:
            primary = straight
        else:
            primary = iambic if iambic["total_score"] is not None else straight

    if combined_score is None:
        if dominant_source == "iambic":
            reason = "Iambic-ajoituksessa ei ollut pisteytettäviä kirjain- tai sanavälejä."
        elif dominant_source == "straight":
            reason = "Straight-ajoituksessa ei ollut riittävästi pisteytettävää ajoitusdataa."
        else:
            reason = "Ajoituspisteisiin ei löytynyt riittävästi piste-, viiva- tai välidataa."
    else:
        reason = ""

    return RoundTimingQuality(
        ok=combined_score is not None,
        reason=reason,
        total_score=None if combined_score is None else round(combined_score, 2),
        factor=round(_round_factor_from_score(combined_score), 4),
        source=dominant_source,
        straight_score=_round_value(straight, "total_score"),
        iambic_score=_round_value(iambic, "total_score"),
        element_score=_round_value(primary, "element_score"),
        gap_score=_round_value(primary, "gap_score"),
        ratio_score=_round_value(primary, "ratio_score"),
        dot_consistency_score=_round_value(primary, "dot_consistency_score"),
        dash_consistency_score=_round_value(primary, "dash_consistency_score"),
        intra_gap_score=_round_value(primary, "intra_gap_score"),
        letter_gap_score=_round_value(primary, "letter_gap_score"),
        word_gap_score=_round_value(primary, "word_gap_score"),
        details={
            "straight": straight,
            "iambic": iambic,
            "dominant_source": dominant_source,
            "target_expectations": {
                "straight": straight_expected_counts,
                "iambic": iambic_expected_counts,
            },
        },
    )


def _factor_from_score(score: Optional[float]) -> float:
    min_factor = float(_cfg("SKILL_RATING_TIMING_MIN_FACTOR", 0.85))
    max_factor = float(_cfg("SKILL_RATING_TIMING_MAX_FACTOR", 1.05))

    if score is None:
        return 1.0

    score = _clamp(float(score), 0.0, 100.0)

    return _clamp(
        min_factor + ((score / 100.0) * (max_factor - min_factor)),
        min_factor,
        max_factor,
    )


def calculate_timing_quality(
    db: Any,
    *,
    recent_rounds: int,
    min_target_chars: int,
    min_accuracy: float,
    min_cleanliness: float,
    max_session_id: int | None = None,
) -> TimingQuality:
    if not bool(_cfg("SKILL_RATING_TIMING_QUALITY_ENABLED", True)):
        empty_straight = SourceTimingQuality(
            source="straight",
            ok=False,
            reason="Rytmianalyysi ei ole käytössä.",
            used_rounds=0,
            element_count=0,
            dot_count=0,
            dash_count=0,
            letter_gap_count=0,
            word_gap_count=0,
            dot_consistency_score=None,
            dash_consistency_score=None,
            dash_dot_ratio_score=None,
            gap_score=None,
            total_score=None,
        )
        empty_iambic = SourceTimingQuality(
            source="iambic",
            ok=False,
            reason="Rytmianalyysi ei ole käytössä.",
            used_rounds=0,
            element_count=0,
            dot_count=0,
            dash_count=0,
            letter_gap_count=0,
            word_gap_count=0,
            dot_consistency_score=None,
            dash_consistency_score=None,
            dash_dot_ratio_score=None,
            gap_score=None,
            total_score=None,
        )

        return TimingQuality(
            ok=False,
            reason="Rytmianalyysi ei ole käytössä.",
            used_rounds=0,
            total_score=None,
            factor=1.0,
            straight=empty_straight,
            iambic=empty_iambic,
            details={},
        )

    if not hasattr(db, "skill_timing_source_data"):
        raise RuntimeError("Database.skill_timing_source_data puuttuu.")

    sessions = db.skill_timing_source_data(
        recent_sessions=recent_rounds,
        min_target_chars=min_target_chars,
        min_accuracy=min_accuracy,
        min_cleanliness=min_cleanliness,
        max_session_id=max_session_id,
    )

    straight = _source_quality_from_events(sessions, "straight")
    iambic = _source_quality_from_events(sessions, "iambic")

    combined_score = _weighted_average(
        [
            (
                straight.total_score,
                float(_cfg("SKILL_RATING_STRAIGHT_TIMING_SOURCE_WEIGHT", 1.00)),
            ),
            (
                iambic.total_score,
                float(_cfg("SKILL_RATING_IAMBIC_TIMING_SOURCE_WEIGHT", 0.60)),
            ),
        ]
    )

    factor = _factor_from_score(combined_score)

    reasons = []

    if not straight.ok and straight.reason:
        reasons.append(f"Straight: {straight.reason}")

    if not iambic.ok and iambic.reason:
        reasons.append(f"Iambic: {iambic.reason}")

    if combined_score is None:
        reason = "Rytmianalyysiin ei löytynyt vielä riittävästi telemetriaa."
    else:
        reason = ""

    if reasons and combined_score is not None:
        reason = " ".join(reasons)

    used_rounds = max(straight.used_rounds, iambic.used_rounds)

    return TimingQuality(
        ok=combined_score is not None,
        reason=reason,
        used_rounds=used_rounds,
        total_score=None if combined_score is None else round(combined_score, 2),
        factor=round(factor, 4),
        straight=straight,
        iambic=iambic,
        details={
            "straight": asdict(straight),
            "iambic": asdict(iambic),
        },
    )