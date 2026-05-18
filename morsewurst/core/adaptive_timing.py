# ============================================================
# morsewurst/core/adaptive_timing.py
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, replace
from statistics import median
from typing import Any, Optional

import morsewurst.config as config
from morsewurst.core.timing_profile import TimingProfile, normalize_source


def _cfg(name: str, default: Any) -> Any:
    return getattr(config, name, default)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(float(minimum), min(float(maximum), float(value)))


def _as_positive_float(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except Exception:
        return None
    return result if result > 0 else None


def _median(values: list[float]) -> Optional[float]:
    cleaned = sorted(float(value) for value in values if value > 0)
    if not cleaned:
        return None
    return float(median(cleaned))


def _mad(values: list[float], center: Optional[float] = None) -> Optional[float]:
    cleaned = sorted(float(value) for value in values if value > 0)
    if len(cleaned) < 2:
        return None
    center = float(center if center is not None else median(cleaned))
    return float(median(abs(value - center) for value in cleaned))


def _sample_confidence(count: int, full_at: int) -> float:
    count = max(0, int(count))
    full_at = max(1, int(full_at))
    return _clamp(count / float(full_at), 0.0, 1.0)


def _stability_confidence(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    center = _median(values)
    if center is None or center <= 0:
        return 0.0
    mad = _mad(values, center)
    if mad is None:
        return 0.0
    cv = mad / center
    return _clamp(1.0 - (cv / 0.55), 0.0, 1.0)


def _combined_confidence(values: list[float], full_at: int) -> float:
    return _clamp(_sample_confidence(len(values), full_at) * _stability_confidence(values), 0.0, 1.0)


def _weighted_average(items: list[tuple[Optional[float], float]]) -> Optional[float]:
    total_weight = 0.0
    total = 0.0
    for value, weight in items:
        numeric = _as_positive_float(value)
        weight = max(0.0, float(weight))
        if numeric is None or weight <= 0:
            continue
        total += numeric * weight
        total_weight += weight
    if total_weight <= 0:
        return None
    return total / total_weight


@dataclass(frozen=True)
class DecoderSettings:
    """Runtime settings for the new timing estimator.

    The dataclass intentionally keeps the old public field names so the rest of
    the project can migrate gradually. Most fields are now used as conservative
    guardrails instead of many competing adaptive rules.
    """

    target_wpm: float = 12.0
    target_unit_us: Optional[float] = None
    unknown_char: str = "?"

    min_element_unit_us: float = 10_000.0
    max_element_unit_us: float = 1_000_000.0
    min_gap_unit_us: float = 10_000.0
    max_gap_unit_us: float = 1_000_000.0

    straight_dit_dah_threshold: float = 2.0

    iambic_letter_gap_units: float = 3.0
    iambic_word_gap_units: float = 7.0
    straight_letter_gap_units: float = 3.0
    straight_word_gap_units: float = 7.0

    iambic_live_final_settle_units: float = 2.0
    straight_live_final_settle_units: float = 1.0
    gap_tolerance_units: float = 0.20

    straight_element_min_samples: int = 4
    straight_gap_min_samples: int = 3
    iambic_gap_min_samples: int = 2

    # Legacy compatibility guardrails. The new estimator does not need all of
    # these as separate tuning knobs, but it accepts them from old UI code.
    straight_element_anchor_k: float = 8.0
    straight_gap_anchor_k: float = 8.0
    iambic_element_anchor_k: float = 3.0
    iambic_gap_anchor_k: float = 6.0
    straight_element_min_target_ratio: float = 0.40
    straight_element_max_target_ratio: float = 2.40
    iambic_element_min_target_ratio: float = 0.40
    iambic_element_max_target_ratio: float = 2.40
    straight_gap_min_target_ratio: float = 0.40
    straight_gap_max_target_ratio: float = 2.80
    iambic_gap_min_target_ratio: float = 0.40
    iambic_gap_max_target_ratio: float = 2.80
    straight_gap_min_element_ratio: float = 0.90
    iambic_gap_min_element_ratio: float = 0.80

    max_gap_for_learning_units: float = 30.0

    # Rescue settings remain accepted by the decoder API but the simplified
    # decoder does not depend on target-assisted rescue for live stability.
    soft_boundary_rescue_enabled: bool = False
    soft_boundary_unknown_only: bool = True
    soft_boundary_max_splits: int = 0
    soft_letter_gap_min_units: float = 2.35
    soft_letter_gap_target_units: float = 3.0
    soft_boundary_contrast_ratio: float = 1.35
    soft_boundary_min_score: float = 58.0
    soft_boundary_split_penalty: float = 7.0
    target_split_rescue_enabled: bool = False
    target_split_max_splits: int = 0
    target_split_min_gap_units: float = 2.0
    target_split_min_score: float = 42.0

    # New profile seed values.
    profile_straight_element_unit_us: Optional[float] = None
    profile_straight_gap_unit_us: Optional[float] = None
    profile_straight_element_confidence: float = 0.0
    profile_straight_gap_confidence: float = 0.0
    profile_straight_letter_gap_us: Optional[float] = None
    profile_straight_word_gap_us: Optional[float] = None

    profile_iambic_element_unit_us: Optional[float] = None
    profile_iambic_gap_unit_us: Optional[float] = None
    profile_iambic_element_confidence: float = 0.0
    profile_iambic_gap_confidence: float = 0.0
    profile_iambic_letter_gap_us: Optional[float] = None
    profile_iambic_word_gap_us: Optional[float] = None

    @classmethod
    def from_config(cls, **overrides: Any) -> "DecoderSettings":
        seed_unit_us = overrides.pop("seed_unit_us", None)
        target_wpm = overrides.pop("target_wpm", None)

        values: dict[str, Any] = {
            "target_wpm": float(_cfg("DEFAULT_TARGET_WPM", 12)),
            "unknown_char": str(_cfg("DECODER_UNKNOWN_CHAR", "�")),
            "min_element_unit_us": float(_cfg("DECODER_MIN_ELEMENT_UNIT_US", 10_000.0)),
            "max_element_unit_us": float(_cfg("DECODER_MAX_ELEMENT_UNIT_US", 1_000_000.0)),
            "min_gap_unit_us": float(_cfg("DECODER_MIN_GAP_UNIT_US", 10_000.0)),
            "max_gap_unit_us": float(_cfg("DECODER_MAX_GAP_UNIT_US", 1_000_000.0)),
            "straight_dit_dah_threshold": float(_cfg("DECODER_DASH_THRESHOLD_UNITS", 2.0)),
            "iambic_letter_gap_units": float(_cfg("DECODER_IAMBIC_LETTER_GAP_UNITS", 3.0)),
            "iambic_word_gap_units": float(_cfg("DECODER_IAMBIC_WORD_GAP_UNITS", 7.0)),
            "straight_letter_gap_units": float(_cfg("DECODER_STRAIGHT_LETTER_GAP_UNITS", 3.0)),
            "straight_word_gap_units": float(_cfg("DECODER_STRAIGHT_WORD_GAP_UNITS", 7.0)),
            "iambic_live_final_settle_units": float(_cfg("DECODER_IAMBIC_COMPLETION_IDLE_UNITS", 4.8)),
            "straight_live_final_settle_units": float(_cfg("DECODER_STRAIGHT_COMPLETION_IDLE_UNITS", 7.0)),
            "gap_tolerance_units": float(_cfg("DECODER_GAP_TOLERANCE_UNITS", 0.15)),
            "straight_element_min_samples": int(_cfg("DECODER_STRAIGHT_ELEMENT_MIN_SAMPLES", 4)),
            "straight_gap_min_samples": int(_cfg("DECODER_STRAIGHT_GAP_MIN_SAMPLES", 3)),
            "iambic_gap_min_samples": int(_cfg("DECODER_IAMBIC_GAP_MIN_SAMPLES", 2)),
            "straight_gap_min_element_ratio": float(_cfg("DECODER_STRAIGHT_GAP_MIN_ELEMENT_RATIO", 0.90)),
            "iambic_gap_min_element_ratio": float(_cfg("DECODER_IAMBIC_GAP_MIN_ELEMENT_RATIO", 0.80)),
            "max_gap_for_learning_units": float(_cfg("DECODER_MAX_GAP_FOR_LEARNING_UNITS", 30.0)),
        }

        if target_wpm is not None:
            try:
                values["target_wpm"] = float(target_wpm)
            except Exception:
                pass

        valid = set(cls.__dataclass_fields__)
        for key, value in overrides.items():
            if key in valid and value is not None:
                values[key] = value

        seed = _as_positive_float(seed_unit_us)
        if seed is not None:
            values["target_unit_us"] = seed

        return cls(**values)

    def with_target_unit_us(self, target_unit_us: Optional[float]) -> "DecoderSettings":
        unit = _as_positive_float(target_unit_us)
        if unit is None:
            return self
        return replace(self, target_unit_us=unit)

    def with_profiles(
        self,
        *,
        straight: Optional[TimingProfile] = None,
        iambic: Optional[TimingProfile] = None,
    ) -> "DecoderSettings":
        values: dict[str, Any] = {}
        if straight is not None:
            values.update(
                profile_straight_element_unit_us=straight.element_unit_us,
                profile_straight_gap_unit_us=straight.gap_unit_us,
                profile_straight_element_confidence=straight.element_confidence,
                profile_straight_gap_confidence=straight.gap_confidence,
                profile_straight_letter_gap_us=straight.letter_gap_us,
                profile_straight_word_gap_us=straight.word_gap_us,
            )
        if iambic is not None:
            values.update(
                profile_iambic_element_unit_us=iambic.element_unit_us,
                profile_iambic_gap_unit_us=iambic.gap_unit_us,
                profile_iambic_element_confidence=iambic.element_confidence,
                profile_iambic_gap_confidence=iambic.gap_confidence,
                profile_iambic_letter_gap_us=iambic.letter_gap_us,
                profile_iambic_word_gap_us=iambic.word_gap_us,
            )
        return replace(self, **values)

    def resolved_target_unit_us(self) -> float:
        explicit = _as_positive_float(self.target_unit_us)
        if explicit is not None:
            return _clamp(explicit, min(self.min_element_unit_us, self.min_gap_unit_us), max(self.max_element_unit_us, self.max_gap_unit_us))
        return _clamp(1_200_000.0 / max(1.0, float(self.target_wpm)), min(self.min_element_unit_us, self.min_gap_unit_us), max(self.max_element_unit_us, self.max_gap_unit_us))

    def profile_element_seed(self, source: str) -> tuple[Optional[float], float]:
        source = normalize_source(source)
        if source == "iambic":
            return self.profile_iambic_element_unit_us, _clamp(self.profile_iambic_element_confidence, 0.0, 1.0)
        return self.profile_straight_element_unit_us, _clamp(self.profile_straight_element_confidence, 0.0, 1.0)

    def profile_gap_seed(self, source: str) -> tuple[Optional[float], float]:
        source = normalize_source(source)
        if source == "iambic":
            return self.profile_iambic_gap_unit_us, _clamp(self.profile_iambic_gap_confidence, 0.0, 1.0)
        return self.profile_straight_gap_unit_us, _clamp(self.profile_straight_gap_confidence, 0.0, 1.0)


@dataclass(frozen=True)
class NormalizedToneEvent:
    raw: dict[str, Any]
    source: str
    t0: int
    t1: int
    dur: float
    element_hint: Optional[str]
    firmware_unit_us: Optional[float]
    wpm: Optional[float]


@dataclass(frozen=True)
class SourceTimingEstimate:
    source: str
    target_unit_us: float
    element_unit_us: float
    gap_unit_us: float
    element_confidence: float
    gap_confidence: float
    element_sample_count: int
    gap_sample_count: int
    using_target_element_anchor: bool
    using_target_gap_anchor: bool
    details: dict[str, Any]
    letter_gap_us: Optional[float] = None
    word_gap_us: Optional[float] = None


@dataclass(frozen=True)
class TimingEstimate:
    dominant_source: str
    primary_source: str
    target_unit_us: float
    source_estimates: dict[str, SourceTimingEstimate]

    def for_source(self, source: Any) -> SourceTimingEstimate:
        source_name = normalize_source(source)
        if source_name in self.source_estimates:
            return self.source_estimates[source_name]
        if self.primary_source in self.source_estimates:
            return self.source_estimates[self.primary_source]
        if "straight" in self.source_estimates:
            return self.source_estimates["straight"]
        if "iambic" in self.source_estimates:
            return self.source_estimates["iambic"]
        return next(iter(self.source_estimates.values()))

    @property
    def element_unit_us(self) -> float:
        return self.for_source(self.primary_source).element_unit_us

    @property
    def gap_unit_us(self) -> float:
        return self.for_source(self.primary_source).gap_unit_us

    @property
    def element_confidence(self) -> float:
        return self.for_source(self.primary_source).element_confidence

    @property
    def gap_confidence(self) -> float:
        return self.for_source(self.primary_source).gap_confidence


def normalize_tone_events(events: list[dict[str, Any]]) -> list[NormalizedToneEvent]:
    tones: list[NormalizedToneEvent] = []
    for event in events:
        if not isinstance(event, dict) or event.get("type") != "tone":
            continue
        t0 = event.get("t0")
        t1 = event.get("t1")
        dur = event.get("dur")
        if not isinstance(t0, int) or not isinstance(t1, int):
            continue
        if not isinstance(dur, (int, float)) or float(dur) <= 0:
            continue
        if int(t1) < int(t0):
            continue
        source = normalize_source(event.get("src", "unknown"))
        element_hint = event.get("el")
        if element_hint not in {".", "-"}:
            element_hint = None
        copied = dict(event)
        copied["t0"] = int(t0)
        copied["t1"] = int(t1)
        copied["dur"] = float(dur)
        tones.append(
            NormalizedToneEvent(
                raw=copied,
                source=source,
                t0=int(t0),
                t1=int(t1),
                dur=float(dur),
                element_hint=element_hint,
                firmware_unit_us=_as_positive_float(event.get("unit")),
                wpm=_as_positive_float(event.get("wpm")),
            )
        )
    tones.sort(key=lambda item: (item.t0, item.t1))
    return tones


def _tones_for_source(tones: list[NormalizedToneEvent], source: str) -> list[NormalizedToneEvent]:
    source = normalize_source(source)
    return [tone for tone in tones if normalize_source(tone.source) == source]


def _gaps_for_source(tones: list[NormalizedToneEvent], source: str) -> list[float]:
    source_tones = _tones_for_source(tones, source)
    gaps: list[float] = []
    for previous, current in zip(source_tones, source_tones[1:]):
        gap = float(current.t0 - previous.t1)
        if gap > 0:
            gaps.append(gap)
    return gaps


def _estimate_straight_elements(tones: list[NormalizedToneEvent], settings: DecoderSettings) -> tuple[Optional[float], Optional[float], Optional[float], float, dict[str, Any]]:
    durations = sorted(float(tone.dur) for tone in tones if tone.dur > 0)
    if len(durations) < max(1, int(settings.straight_element_min_samples)):
        return None, None, None, 0.0, {"reason": "not enough straight durations", "count": len(durations)}

    # Try every split and choose the one that produces two stable groups and a
    # Morse-like dash/dot relationship. This is deterministic and transparent.
    best: Optional[dict[str, Any]] = None
    for split in range(1, len(durations)):
        lower = durations[:split]
        upper = durations[split:]
        if not lower or not upper:
            continue
        dot = _median(lower)
        dash = _median(upper)
        if dot is None or dash is None or dot <= 0:
            continue
        ratio = dash / dot
        if ratio < 1.45:
            continue
        lower_mad = _mad(lower, dot) or 0.0
        upper_mad = _mad(upper, dash) or 0.0
        separation = (min(upper) - max(lower)) / max(1.0, dot)
        ratio_quality = _clamp(1.0 - abs(ratio - 3.0) / 1.8, 0.0, 1.0)
        stability = _clamp(1.0 - ((lower_mad / dot) + (upper_mad / dash)) / 0.90, 0.0, 1.0)
        balance = _clamp(min(len(lower), len(upper)) / 5.0, 0.0, 1.0)
        separation_quality = _clamp(separation / 0.50, 0.0, 1.0)
        score = (ratio_quality * 0.45) + (stability * 0.25) + (balance * 0.15) + (separation_quality * 0.15)
        if best is None or score > best["score"]:
            best = {
                "split": split,
                "dot": dot,
                "dash": dash,
                "ratio": ratio,
                "score": score,
                "separation": separation,
                "lower_count": len(lower),
                "upper_count": len(upper),
            }

    if best is None or best["score"] < 0.25:
        shortest = durations[: max(1, min(5, len(durations) // 3 or 1))]
        dot = _median(shortest)
        return dot, None, None, _combined_confidence(shortest, 20) * 0.35, {
            "reason": "single short cluster fallback",
            "count": len(durations),
        }

    dot_us = float(best["dot"])
    dash_us = float(best["dash"])
    confidence = _clamp(float(best["score"]) * _sample_confidence(len(durations), 24), 0.0, 1.0)
    return dot_us, dash_us, dot_us, confidence, best


def _estimate_iambic_element(tones: list[NormalizedToneEvent], settings: DecoderSettings) -> tuple[Optional[float], float, dict[str, Any]]:
    firmware_units = [
        float(tone.firmware_unit_us)
        for tone in tones
        if _as_positive_float(tone.firmware_unit_us) is not None
    ]

    if firmware_units:
        unit_us = _median(firmware_units)
        return unit_us, 1.0 if unit_us is not None else 0.0, {
            "basis": "firmware_unit",
            "count": len(firmware_units),
            "authoritative": True,
        }

    candidates: list[float] = []
    for tone in tones:
        if tone.element_hint == ".":
            candidates.append(float(tone.dur))
        elif tone.element_hint == "-":
            candidates.append(float(tone.dur) / 3.0)
    if candidates:
        return _median(candidates), _combined_confidence(candidates, 12), {"basis": "element_hint", "count": len(candidates)}

    return None, 0.0, {"basis": "no_iambic_element_telemetry", "count": 0}


def _gap_unit_from_gaps(
    gaps: list[float],
    *,
    source: str,
    reference_unit_us: float,
    settings: DecoderSettings,
) -> tuple[Optional[float], float, dict[str, Any]]:
    source = normalize_source(source)
    min_samples = int(settings.iambic_gap_min_samples if source == "iambic" else settings.straight_gap_min_samples)
    if len(gaps) < max(1, min_samples):
        return None, 0.0, {"reason": "not enough gaps", "gap_count": len(gaps)}

    letter_units = settings.iambic_letter_gap_units if source == "iambic" else settings.straight_letter_gap_units
    word_units = settings.iambic_word_gap_units if source == "iambic" else settings.straight_word_gap_units

    candidates: list[float] = []
    kinds = {"intra": 0, "letter": 0, "word": 0}
    learning_limit = max(reference_unit_us, settings.min_gap_unit_us) * max(8.0, float(settings.max_gap_for_learning_units))

    for gap in gaps:
        if gap <= 0 or gap > learning_limit:
            continue
        unit_estimates = [
            ("intra", gap / 1.0, 0.20),
            ("letter", gap / max(1.0, float(letter_units)), 1.00),
            ("word", gap / max(1.0, float(word_units)), 1.10),
        ]
        # Prefer the interpretation whose implied unit is closest to the current
        # reference unit. Intra gaps are given low weight so they cannot collapse
        # letter/word detection by themselves.
        best_kind, best_unit, weight = min(
            unit_estimates,
            key=lambda item: abs((item[1] / max(1.0, reference_unit_us)) - 1.0) / item[2],
        )
        kinds[best_kind] += 1
        if best_kind == "intra":
            candidates.append(best_unit * 0.50)  # intentionally weak evidence
        else:
            candidates.append(best_unit)

    if not candidates:
        return None, 0.0, {"reason": "no usable gap candidates", "gap_count": len(gaps)}

    confidence = _combined_confidence(candidates, 18)
    # At least one probable letter/word gap makes gap learning much more useful.
    if kinds["letter"] + kinds["word"] == 0:
        confidence *= 0.35

    return _median(candidates), confidence, {"gap_count": len(gaps), "candidate_count": len(candidates), "kinds": kinds}


def _blend_unit(
    *,
    target_unit_us: float,
    profile_unit_us: Optional[float],
    profile_confidence: float,
    live_unit_us: Optional[float],
    live_confidence: float,
    minimum: float,
    maximum: float,
) -> tuple[float, float, dict[str, Any]]:
    profile_confidence = _clamp(profile_confidence, 0.0, 1.0)
    live_confidence = _clamp(live_confidence, 0.0, 1.0)

    # Live data can override the profile, but only when it is actually clean.
    target_weight = max(0.10, 1.0 - max(profile_confidence, live_confidence))
    profile_weight = profile_confidence * 1.40
    live_weight = live_confidence * 2.20

    value = _weighted_average([
        (target_unit_us, target_weight),
        (profile_unit_us, profile_weight),
        (live_unit_us, live_weight),
    ])
    if value is None:
        value = target_unit_us

    confidence = _clamp(max(profile_confidence * 0.70, live_confidence), 0.0, 1.0)
    return _clamp(value, minimum, maximum), confidence, {
        "target_weight": round(target_weight, 4),
        "profile_weight": round(profile_weight, 4),
        "live_weight": round(live_weight, 4),
        "profile_unit_us": profile_unit_us,
        "live_unit_us": live_unit_us,
        "live_confidence": round(live_confidence, 4),
        "profile_confidence": round(profile_confidence, 4),
    }


def _estimate_source_timing(source: str, tones: list[NormalizedToneEvent], all_tones: list[NormalizedToneEvent], settings: DecoderSettings) -> SourceTimingEstimate:
    source = normalize_source(source)
    target_unit_us = settings.resolved_target_unit_us()
    gaps = _gaps_for_source(all_tones, source)

    if source == "iambic":
        live_element_unit, live_element_confidence, element_details = _estimate_iambic_element(
            tones,
            settings,
        )
        measured_element_unit = _as_positive_float(live_element_unit)

        profile_letter_gap_us = _as_positive_float(
            settings.profile_iambic_letter_gap_us
        )
        profile_word_gap_us = _as_positive_float(
            settings.profile_iambic_word_gap_us
        )

        has_external_spacing_profile = (
            profile_letter_gap_us is not None
            and profile_word_gap_us is not None
        )

        if measured_element_unit is None:
            element_unit_us = _clamp(
                target_unit_us,
                settings.min_element_unit_us,
                settings.max_element_unit_us,
            )
            element_confidence = 0.0
            using_target_element_anchor = True

            element_blend_details = {
                "basis": "iambic_element_not_available",
                "target_unit_us": target_unit_us,
            }
        else:
            element_unit_us = _clamp(
                measured_element_unit,
                settings.min_element_unit_us,
                settings.max_element_unit_us,
            )
            element_confidence = _clamp(live_element_confidence, 0.0, 1.0)
            using_target_element_anchor = False

            element_blend_details = {
                "basis": "iambic_element_telemetry",
                "measured_element_unit_us": measured_element_unit,
                "element_unit_us": element_unit_us,
                "live_confidence": round(live_element_confidence, 4),
                "target_unit_ignored": True,
                "profile_unit_ignored": True,
            }

        if has_external_spacing_profile:
            gap_unit_candidates = [
                profile_letter_gap_us / max(1.0, float(settings.iambic_letter_gap_units)),
                profile_word_gap_us / max(1.0, float(settings.iambic_word_gap_units)),
            ]
            learned_gap_unit = _median(gap_unit_candidates)
            gap_confidence = _clamp(settings.profile_iambic_gap_confidence, 0.0, 1.0)
            using_target_gap_anchor = False
        else:
            learned_gap_unit = None
            gap_confidence = 0.0
            using_target_gap_anchor = True

        gap_unit_us = _clamp(
            learned_gap_unit if learned_gap_unit is not None else element_unit_us,
            settings.min_gap_unit_us,
            settings.max_gap_unit_us,
        )

        gap_details = {
            "basis": "iambic_external_spacing_profile",
            "gap_count": len(gaps),
            "element_unit_us": element_unit_us,
            "gap_unit_us": gap_unit_us,
            "profile_letter_gap_us": profile_letter_gap_us,
            "profile_word_gap_us": profile_word_gap_us,
            "has_external_spacing_profile": has_external_spacing_profile,
        }

        gap_blend_details = {
            "basis": "iambic_user_letter_and_word_spacing",
            "firmware_intragap_used_for_element_timing_only": True,
            "letter_gap_target_units": float(settings.iambic_letter_gap_units),
            "word_gap_target_units": float(settings.iambic_word_gap_units),
            "profile_gap_confidence": round(settings.profile_iambic_gap_confidence, 4),
        }

        return SourceTimingEstimate(
            source=source,
            target_unit_us=target_unit_us,
            element_unit_us=element_unit_us,
            gap_unit_us=gap_unit_us,
            element_confidence=element_confidence,
            gap_confidence=gap_confidence,
            element_sample_count=len(tones),
            gap_sample_count=len(gaps),
            using_target_element_anchor=using_target_element_anchor,
            using_target_gap_anchor=using_target_gap_anchor,
            details={
                "element": element_details,
                "element_blend": element_blend_details,
                "gap": gap_details,
                "gap_blend": gap_blend_details,
            },
            letter_gap_us=profile_letter_gap_us,
            word_gap_us=profile_word_gap_us,
        )

    dot_us, dash_us, live_element_unit, live_element_confidence, element_details = _estimate_straight_elements(tones, settings)
    element_details = dict(element_details)
    element_details.update({"dot_us": dot_us, "dash_us": dash_us})

    profile_element_unit, profile_element_confidence = settings.profile_element_seed(source)
    element_unit_us, element_confidence, element_blend_details = _blend_unit(
        target_unit_us=target_unit_us,
        profile_unit_us=profile_element_unit,
        profile_confidence=profile_element_confidence,
        live_unit_us=live_element_unit,
        live_confidence=live_element_confidence,
        minimum=settings.min_element_unit_us,
        maximum=settings.max_element_unit_us,
    )

    profile_gap_unit, profile_gap_confidence = settings.profile_gap_seed(source)
    gap_reference = _weighted_average([
        (target_unit_us, 0.50),
        (profile_gap_unit, profile_gap_confidence),
        (element_unit_us, element_confidence * 0.50),
    ]) or target_unit_us

    live_gap_unit, live_gap_confidence, gap_details = _gap_unit_from_gaps(
        gaps,
        source=source,
        reference_unit_us=gap_reference,
        settings=settings,
    )

    gap_unit_us, gap_confidence, gap_blend_details = _blend_unit(
        target_unit_us=target_unit_us,
        profile_unit_us=profile_gap_unit,
        profile_confidence=profile_gap_confidence,
        live_unit_us=live_gap_unit,
        live_confidence=live_gap_confidence,
        minimum=settings.min_gap_unit_us,
        maximum=settings.max_gap_unit_us,
    )

    gap_unit_before_element_clamp = float(gap_unit_us)

    if element_unit_us is not None and element_unit_us > 0:
        min_ratio = float(settings.straight_gap_min_element_ratio)
        min_gap_from_element_us = float(element_unit_us) * min_ratio
        gap_unit_us = max(float(gap_unit_us), min_gap_from_element_us)

        gap_blend_details = dict(gap_blend_details)
        gap_blend_details.update(
            {
                "element_floor_ratio": round(min_ratio, 4),
                "element_floor_us": round(min_gap_from_element_us, 2),
                "before_element_floor_us": round(gap_unit_before_element_clamp, 2),
                "after_element_floor_us": round(float(gap_unit_us), 2),
                "element_floor_applied": float(gap_unit_us) > gap_unit_before_element_clamp,
            }
        )

    return SourceTimingEstimate(
        source=source,
        target_unit_us=target_unit_us,
        element_unit_us=element_unit_us,
        gap_unit_us=gap_unit_us,
        element_confidence=element_confidence,
        gap_confidence=gap_confidence,
        element_sample_count=len(tones),
        gap_sample_count=len(gaps),
        using_target_element_anchor=element_confidence < 0.30,
        using_target_gap_anchor=gap_confidence < 0.30,
        details={
            "element": element_details,
            "element_blend": element_blend_details,
            "gap": gap_details,
            "gap_blend": gap_blend_details,
        },
    )


def estimate_adaptive_timing(tones: list[NormalizedToneEvent], settings: Optional[DecoderSettings] = None) -> TimingEstimate:
    settings = settings or DecoderSettings.from_config()
    target_unit_us = settings.resolved_target_unit_us()

    straight_tones = _tones_for_source(tones, "straight")
    iambic_tones = _tones_for_source(tones, "iambic")

    straight = _estimate_source_timing("straight", straight_tones, tones, settings)
    iambic = _estimate_source_timing("iambic", iambic_tones, tones, settings)

    if len(straight_tones) > len(iambic_tones):
        dominant = primary = "straight"
    elif len(iambic_tones) > len(straight_tones):
        dominant = primary = "iambic"
    elif not straight_tones and not iambic_tones:
        dominant = primary = "straight"
    else:
        dominant = "mixed"
        primary = "straight"

    return TimingEstimate(
        dominant_source=dominant,
        primary_source=primary,
        target_unit_us=target_unit_us,
        source_estimates={"straight": straight, "iambic": iambic},
    )