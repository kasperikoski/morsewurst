# ============================================================
# morsewurst/core/timing_profile.py
# ============================================================

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median
from typing import Any, Iterable, Optional


VALID_SOURCES = {"straight", "iambic", "mixed", "unknown"}


def _as_float(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except Exception:
        return None

    if result <= 0:
        return None

    if result != result:
        return None

    if result in (float("inf"), float("-inf")):
        return None

    return result


def _clean_values(values: Iterable[Any]) -> list[float]:
    result: list[float] = []
    for value in values:
        numeric = _as_float(value)
        if numeric is not None:
            result.append(numeric)
    return result


def _median(values: Iterable[Any]) -> Optional[float]:
    cleaned = _clean_values(values)
    if not cleaned:
        return None
    return float(median(cleaned))


def _mad(values: Iterable[Any], center: Optional[float] = None) -> Optional[float]:
    cleaned = _clean_values(values)
    if len(cleaned) < 2:
        return None
    center = float(center if center is not None else median(cleaned))
    return float(median(abs(value - center) for value in cleaned))


def _coefficient_of_variation(values: Iterable[Any]) -> Optional[float]:
    cleaned = _clean_values(values)
    if len(cleaned) < 2:
        return None
    center = float(median(cleaned))
    if center <= 0:
        return None
    mad = _mad(cleaned, center)
    if mad is None:
        return None
    # MAD is intentionally used instead of standard deviation because keying
    # telemetry often contains a few accidental outliers.
    return float(mad / center)


def _sample_confidence(count: int, *, full_at: int) -> float:
    count = max(0, int(count))
    full_at = max(1, int(full_at))
    return max(0.0, min(1.0, count / float(full_at)))


def _stability_confidence(values: Iterable[Any]) -> float:
    cv = _coefficient_of_variation(values)
    if cv is None:
        return 0.0
    # CV 0.00 -> 1.0, CV 0.50 -> 0.0.
    return max(0.0, min(1.0, 1.0 - (cv / 0.50)))


def _combined_confidence(count: int, values: Iterable[Any], *, full_at: int) -> float:
    return round(_sample_confidence(count, full_at=full_at) * _stability_confidence(values), 4)


def normalize_source(source: Any) -> str:
    source_name = str(source or "unknown").strip().lower()
    return source_name if source_name in VALID_SOURCES else "unknown"


@dataclass(frozen=True)
class TimingProfile:
    """A recent, user-specific Morse rhythm profile.

    The profile is a seed, not a command. The live decoder may move away from
    these values when the current round provides cleaner evidence.
    """

    source: str = "unknown"

    element_unit_us: Optional[float] = None
    gap_unit_us: Optional[float] = None

    dot_us: Optional[float] = None
    dash_us: Optional[float] = None
    dash_dot_ratio: Optional[float] = None

    letter_gap_us: Optional[float] = None
    word_gap_us: Optional[float] = None

    element_confidence: float = 0.0
    gap_confidence: float = 0.0

    sample_rounds: int = 0
    sample_events: int = 0

    updated_from_session_id: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", normalize_source(self.source))
        object.__setattr__(self, "element_confidence", max(0.0, min(1.0, float(self.element_confidence))))
        object.__setattr__(self, "gap_confidence", max(0.0, min(1.0, float(self.gap_confidence))))

    @property
    def has_element_seed(self) -> bool:
        return self.element_unit_us is not None and self.element_confidence > 0.05

    @property
    def has_gap_seed(self) -> bool:
        return self.gap_unit_us is not None and self.gap_confidence > 0.05

    @property
    def is_empty(self) -> bool:
        return not self.has_element_seed and not self.has_gap_seed

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def seed_unit_us(self, fallback_unit_us: float) -> float:
        """Return the best single seed for legacy callers.

        Older UI code passes one seed value. Prefer the gap unit because live
        finalisation and idle timeout are usually more sensitive to a bad seed
        than straight-key dot/dash classification.
        """

        if self.has_gap_seed and self.gap_unit_us is not None:
            return float(self.gap_unit_us)
        if self.has_element_seed and self.element_unit_us is not None:
            return float(self.element_unit_us)
        return float(fallback_unit_us)


@dataclass(frozen=True)
class TimingProfileSample:
    session_id: Optional[int]
    source: str

    element_unit_us: Optional[float] = None
    gap_unit_us: Optional[float] = None

    dot_us: Optional[float] = None
    dash_us: Optional[float] = None
    letter_gap_us: Optional[float] = None
    word_gap_us: Optional[float] = None

    event_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", normalize_source(self.source))


def build_timing_profile(
    samples: Iterable[TimingProfileSample],
    *,
    source: str = "unknown",
    max_samples: Optional[int] = None,
) -> TimingProfile:
    """Build a robust timing profile from recent good rounds.

    The input should already be filtered by accuracy and cleanliness. This
    function still resists outliers by using medians and MAD-based confidence.
    """

    source_name = normalize_source(source)
    rows = [sample for sample in samples if normalize_source(sample.source) in {source_name, "unknown", "mixed"} or source_name == "mixed"]

    if max_samples is not None and max_samples > 0:
        rows = rows[: int(max_samples)]

    if not rows:
        return TimingProfile(source=source_name)

    element_values = [sample.element_unit_us for sample in rows if _as_float(sample.element_unit_us) is not None]
    gap_values = [sample.gap_unit_us for sample in rows if _as_float(sample.gap_unit_us) is not None]
    dot_values = [sample.dot_us for sample in rows if _as_float(sample.dot_us) is not None]
    dash_values = [sample.dash_us for sample in rows if _as_float(sample.dash_us) is not None]
    letter_values = [sample.letter_gap_us for sample in rows if _as_float(sample.letter_gap_us) is not None]
    word_values = [sample.word_gap_us for sample in rows if _as_float(sample.word_gap_us) is not None]

    dot_us = _median(dot_values)
    dash_us = _median(dash_values)

    element_unit_us = _median(element_values)
    if element_unit_us is None and dot_us is not None:
        element_unit_us = dot_us
    if element_unit_us is None and dash_us is not None:
        element_unit_us = dash_us / 3.0

    letter_gap_us = _median(letter_values)
    word_gap_us = _median(word_values)

    if source_name == "iambic":
        if letter_gap_us is not None and word_gap_us is not None:
            letter_unit_values = [
                value / 3.0
                for value in _clean_values(letter_values)
            ]

            word_unit_values = [
                value / 7.0
                for value in _clean_values(word_values)
            ]

            gap_unit_candidates = letter_unit_values + word_unit_values
        else:
            gap_unit_candidates = []

        gap_basis = gap_unit_candidates
    else:
        gap_unit_candidates = []
        gap_unit_candidates.extend(_clean_values(gap_values))

        if letter_gap_us is not None:
            gap_unit_candidates.append(letter_gap_us / 3.0)

        if word_gap_us is not None:
            gap_unit_candidates.append(word_gap_us / 7.0)

        gap_basis = gap_values or gap_unit_candidates

    gap_unit_us = _median(gap_unit_candidates)

    dash_dot_ratio = None
    if dot_us is not None and dash_us is not None and dot_us > 0:
        dash_dot_ratio = float(dash_us / dot_us)

    event_count = sum(max(0, int(sample.event_count or 0)) for sample in rows)
    latest_session_ids = [sample.session_id for sample in rows if sample.session_id is not None]

    element_confidence = _combined_confidence(
        len(element_values) or len(dot_values),
        element_values or dot_values,
        full_at=300,
    )

    # Straight-key element confidence is weak if the dot/dash relationship is
    # not recognisably Morse-like.
    if source_name == "straight" and dash_dot_ratio is not None:
        ratio_quality = max(0.0, min(1.0, 1.0 - (abs(dash_dot_ratio - 3.0) / 1.50)))
        element_confidence = round(element_confidence * ratio_quality, 4)

    gap_confidence = _combined_confidence(
        len(gap_basis),
        gap_basis,
        full_at=300,
    )

    return TimingProfile(
        source=source_name,
        element_unit_us=element_unit_us,
        gap_unit_us=gap_unit_us,
        dot_us=dot_us,
        dash_us=dash_us,
        dash_dot_ratio=dash_dot_ratio,
        letter_gap_us=letter_gap_us,
        word_gap_us=word_gap_us,
        element_confidence=element_confidence,
        gap_confidence=gap_confidence,
        sample_rounds=len(rows),
        sample_events=event_count,
        updated_from_session_id=max(latest_session_ids) if latest_session_ids else None,
    )
