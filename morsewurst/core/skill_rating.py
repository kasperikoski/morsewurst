# ============================================================
# morsewurst/core/skill_rating.py
# ============================================================

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from statistics import mean, median
from typing import Any, Dict, Iterable, Optional, Sequence

import morsewurst.config as config
from morsewurst.core.progression import progression_from_raw_skill
from morsewurst.core.scoring import paris_wpm_for_text
from morsewurst.core.timing_quality import calculate_timing_quality


@dataclass
class CharacterMastery:
    char: str
    attempts: int
    correct: int
    errors: int
    accuracy: float
    confidence: float
    mastery: float
    covered: bool


@dataclass
class SkillRating:
    ok: bool
    reason: str

    model_version: int

    recent_rounds: int
    total_rounds: int
    used_rounds: int

    effective_wpm: Optional[float]

    # Capped skill-evidence WPM values. These are used internally by the
    # skill model and may be capped by the target WPM.
    iambic_wpm: Optional[float]
    straight_wpm: Optional[float]

    # Uncapped display-only PARIS WPM values. These show the user's actual
    # demonstrated PARIS speed per key source and are not capped by target WPM.
    iambic_paris_wpm: Optional[float]
    straight_paris_wpm: Optional[float]

    iambic_used_rounds: int
    straight_used_rounds: int

    avg_accuracy: Optional[float]
    avg_cleanliness: Optional[float]

    quality_factor: float
    character_mastery_factor: float
    coverage_factor: float
    timing_stability_factor: float

    timing_quality_score: Optional[float]
    straight_timing_score: Optional[float]
    iambic_timing_score: Optional[float]
    timing_used_rounds: int
    timing_reason: str

    sample_confidence: float
    rating_confidence: float
    mastery_adjustment: float

    raw_skill: Optional[float]

    # Level-only adjusted skill. raw_skill remains the displayed Overall skill WPM.
    level_skill: Optional[float]
    full_charset_total: int
    full_charset_qualified_count: int
    full_charset_qualified_coverage: float
    charset_scope_factor: float

    level: int
    level_progress: float
    title: str

    expected_charset: str
    character_mastery: Dict[str, CharacterMastery] = field(default_factory=dict)


def _cfg(name: str, default: Any) -> Any:
    return getattr(config, name, default)


MODEL_VERSION = int(_cfg("SKILL_RATING_MODEL_VERSION", 1))

DEFAULT_RECENT_ROUNDS = int(_cfg("DEFAULT_SKILL_RATING_RECENT_ROUNDS", 1000))
MIN_TARGET_CHARS = int(_cfg("SKILL_RATING_MIN_TARGET_CHARS", 12))
MIN_QUALIFIED_ROUNDS = int(_cfg("SKILL_RATING_MIN_QUALIFIED_ROUNDS", 50))

QUALIFIED_MIN_ACCURACY = float(_cfg("SKILL_RATING_QUALIFIED_MIN_ACCURACY", 85.0))
QUALIFIED_MIN_CLEANLINESS = float(_cfg("SKILL_RATING_QUALIFIED_MIN_CLEANLINESS", 80.0))

CONFIDENCE_K = float(_cfg("SKILL_RATING_CHARACTER_CONFIDENCE_K", 15.0))
COVERAGE_MIN_ATTEMPTS = int(_cfg("SKILL_RATING_COVERAGE_MIN_ATTEMPTS", 5))

FULL_CHARSET_MIN_ATTEMPTS = int(_cfg("SKILL_RATING_FULL_CHARSET_MIN_ATTEMPTS", 15))
FULL_CHARSET_MIN_ROUNDS = int(_cfg("SKILL_RATING_FULL_CHARSET_MIN_ROUNDS", 15))
FULL_CHARSET_MIN_ACCURACY = float(_cfg("SKILL_RATING_FULL_CHARSET_MIN_ACCURACY", 75.0))
CHARSET_SCOPE_MIN_FACTOR = float(_cfg("SKILL_RATING_CHARSET_SCOPE_MIN_FACTOR", 0.70))
CHARSET_SCOPE_MAX_FACTOR = float(_cfg("SKILL_RATING_CHARSET_SCOPE_MAX_FACTOR", 1.00))

SAMPLE_CONFIDENCE_K = float(_cfg("SKILL_RATING_SAMPLE_CONFIDENCE_K", 30.0))

MASTERY_ADJUSTMENT_MIN = float(_cfg("SKILL_RATING_MASTERY_ADJUSTMENT_MIN", 0.75))
MASTERY_ADJUSTMENT_MAX = float(_cfg("SKILL_RATING_MASTERY_ADJUSTMENT_MAX", 1.05))

TIMING_MIN_FACTOR = float(_cfg("SKILL_RATING_TIMING_MIN_FACTOR", 0.85))
TIMING_MAX_FACTOR = float(_cfg("SKILL_RATING_TIMING_MAX_FACTOR", 1.05))


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except Exception:
        pass

    try:
        return row.get(key, default)
    except Exception:
        return default


def _safe_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)

    if value is None:
        return None

    try:
        return float(value)
    except Exception:
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_mean(values: Iterable[float]) -> Optional[float]:
    cleaned = [float(value) for value in values if isinstance(value, (int, float))]

    if not cleaned:
        return None

    return float(mean(cleaned))


def _target_wpm_from_settings_json(settings_json: str) -> Optional[float]:
    try:
        settings = json.loads(settings_json)
    except Exception:
        return None

    if not isinstance(settings, dict):
        return None

    value = settings.get("target_wpm")

    try:
        target_wpm = float(value)
    except Exception:
        return None

    if target_wpm <= 0:
        return None

    min_wpm = float(getattr(config, "EFFECTIVE_WPM_MIN_WPM", 5))
    max_wpm = float(getattr(config, "EFFECTIVE_WPM_MAX_WPM", 80))

    return _clamp(target_wpm, min_wpm, max_wpm)


def _round_actual_paris_wpm(row: Any) -> Optional[float]:
    """Return uncapped PARIS WPM for one round.

    This is the actual demonstrated speed based on target Morse units and
    elapsed time. It is suitable for display metrics, not for capped skill
    evidence.
    """

    elapsed_us = _safe_float(_row_get(row, "elapsed_us"))

    if elapsed_us is None or elapsed_us <= 0:
        return None

    target = str(_row_get(row, "target", "") or "")

    actual_wpm = paris_wpm_for_text(target, elapsed_us)

    if actual_wpm is None:
        return None

    if actual_wpm < 1 or actual_wpm > 150:
        return None

    return float(actual_wpm)


def _round_real_wpm(row: Any) -> Optional[float]:
    """Return capped skill-evidence WPM for one round.

    Skill evidence may be capped by target WPM so that a very low configured
    target speed cannot prove a higher skill level by itself.
    """

    actual_wpm = _round_actual_paris_wpm(row)

    if actual_wpm is None:
        return None

    settings_json = str(_row_get(row, "settings_json", "") or "")
    target_wpm = _target_wpm_from_settings_json(settings_json)

    cap_by_target = bool(_cfg("SKILL_RATING_CAP_BY_TARGET_WPM", True))

    if target_wpm is None or not cap_by_target:
        return float(actual_wpm)

    return float(min(actual_wpm, target_wpm))


def _qualified_wpm_values(rows: Sequence[Any]) -> list[float]:
    values: list[float] = []

    for row in rows:
        accuracy = _safe_float(_row_get(row, "accuracy"))
        cleanliness = _safe_float(_row_get(row, "cleanliness"))

        if accuracy is None or cleanliness is None:
            continue

        if accuracy < QUALIFIED_MIN_ACCURACY:
            continue

        if cleanliness < QUALIFIED_MIN_CLEANLINESS:
            continue

        real_wpm = _round_real_wpm(row)

        if real_wpm is not None:
            values.append(real_wpm)

    return values


def _qualified_paris_wpm_values(rows: Sequence[Any]) -> list[float]:
    """Return uncapped PARIS WPM values from qualified rounds.

    Uses the same accuracy and cleanliness filters as effective WPM, but does
    not cap the result by target WPM.
    """

    values: list[float] = []

    for row in rows:
        accuracy = _safe_float(_row_get(row, "accuracy"))
        cleanliness = _safe_float(_row_get(row, "cleanliness"))

        if accuracy is None or cleanliness is None:
            continue

        if accuracy < QUALIFIED_MIN_ACCURACY:
            continue

        if cleanliness < QUALIFIED_MIN_CLEANLINESS:
            continue

        actual_wpm = _round_actual_paris_wpm(row)

        if actual_wpm is not None:
            values.append(actual_wpm)

    return values


def _effective_wpm(rows: Sequence[Any]) -> tuple[Optional[float], int]:
    values = _qualified_wpm_values(rows)

    if not values:
        return None, 0

    return float(median(values)), len(values)


def _display_paris_wpm(rows: Sequence[Any]) -> tuple[Optional[float], int]:
    values = _qualified_paris_wpm_values(rows)

    if not values:
        return None, 0

    return float(median(values)), len(values)


def _round_quality_factor(row: Any) -> float:
    accuracy = _safe_float(_row_get(row, "accuracy"))
    cleanliness = _safe_float(_row_get(row, "cleanliness"))

    accuracy_factor = 0.0 if accuracy is None else _clamp(accuracy / 100.0, 0.0, 1.0)
    cleanliness_factor = 0.0 if cleanliness is None else _clamp(cleanliness / 100.0, 0.0, 1.0)

    return _clamp(
        (accuracy_factor ** 0.70) * (cleanliness_factor ** 0.30),
        0.0,
        1.0,
    )


def _raw_skill_wpm(rows: Sequence[Any]) -> Optional[float]:
    """Return raw practical Skill WPM from all eligible recent rounds.

    Eligibility is already handled by db.skill_recent_sessions():
    only rounds with at least MIN_TARGET_CHARS target characters are included.

    Unlike effective_wpm, this does not discard rounds by accuracy or cleanliness.
    Poor rounds reduce the result through the per-round quality factor instead.
    """

    values: list[float] = []

    for row in rows:
        real_wpm = _round_real_wpm(row)

        if real_wpm is None:
            continue

        quality = _round_quality_factor(row)
        values.append(float(real_wpm) * quality)

    if not values:
        return None

    return float(median(values))


def _source_rows_by_key(
    db: Any,
    recent_rounds: int,
) -> dict[str, list[Any]]:
    rows: dict[str, list[Any]] = {
        "straight": [],
        "iambic": [],
    }

    if not hasattr(db, "skill_recent_sessions_by_key_source"):
        return rows

    try:
        data = db.skill_recent_sessions_by_key_source(
            recent_sessions_per_source=recent_rounds,
            min_target_chars=MIN_TARGET_CHARS,
        )
    except Exception:
        return rows

    if not isinstance(data, dict):
        return rows

    for source in ("straight", "iambic"):
        value = data.get(source, [])

        if isinstance(value, list):
            rows[source] = value

    return rows


def _average_pair(
    left: Optional[float],
    right: Optional[float],
) -> Optional[float]:
    if left is None or right is None:
        return None

    return (float(left) + float(right)) / 2.0


def _key_source_wpm_from_rows(
    source_rows: dict[str, list[Any]],
) -> dict[str, Any]:
    straight_wpm, straight_used = _effective_wpm(source_rows.get("straight", []))
    iambic_wpm, iambic_used = _effective_wpm(source_rows.get("iambic", []))

    return {
        "straight_wpm": straight_wpm,
        "iambic_wpm": iambic_wpm,
        "straight_used_rounds": straight_used,
        "iambic_used_rounds": iambic_used,
    }


def _key_source_paris_wpm_from_rows(
    source_rows: dict[str, list[Any]],
) -> dict[str, Any]:
    straight_wpm, straight_used = _display_paris_wpm(source_rows.get("straight", []))
    iambic_wpm, iambic_used = _display_paris_wpm(source_rows.get("iambic", []))

    return {
        "straight_paris_wpm": straight_wpm,
        "iambic_paris_wpm": iambic_wpm,
        "straight_paris_used_rounds": straight_used,
        "iambic_paris_used_rounds": iambic_used,
    }


def _balanced_effective_wpm_from_rows(
    source_rows: dict[str, list[Any]],
) -> tuple[Optional[float], int]:
    key_source_wpm = _key_source_wpm_from_rows(source_rows)

    straight_wpm = key_source_wpm.get("straight_wpm")
    iambic_wpm = key_source_wpm.get("iambic_wpm")

    straight_used = int(key_source_wpm.get("straight_used_rounds") or 0)
    iambic_used = int(key_source_wpm.get("iambic_used_rounds") or 0)

    # Confidence is limited by the weaker sample size.
    used_rounds = min(straight_used, iambic_used)

    return _average_pair(straight_wpm, iambic_wpm), used_rounds


def _balanced_raw_skill_wpm_from_rows(
    source_rows: dict[str, list[Any]],
) -> Optional[float]:
    straight_raw = _raw_skill_wpm(source_rows.get("straight", []))
    iambic_raw = _raw_skill_wpm(source_rows.get("iambic", []))

    return _average_pair(straight_raw, iambic_raw)


def _quality_factor(rows: Sequence[Any]) -> tuple[Optional[float], Optional[float], float]:
    accuracies: list[float] = []
    cleanliness_values: list[float] = []

    for row in rows:
        accuracy = _safe_float(_row_get(row, "accuracy"))
        cleanliness = _safe_float(_row_get(row, "cleanliness"))

        if accuracy is not None:
            accuracies.append(_clamp(accuracy, 0.0, 100.0))

        if cleanliness is not None:
            cleanliness_values.append(_clamp(cleanliness, 0.0, 100.0))

    avg_accuracy = _safe_mean(accuracies)
    avg_cleanliness = _safe_mean(cleanliness_values)

    if avg_accuracy is None and avg_cleanliness is None:
        return None, None, 0.0

    accuracy_factor = 1.0 if avg_accuracy is None else _clamp(avg_accuracy / 100.0, 0.0, 1.0)
    cleanliness_factor = 1.0 if avg_cleanliness is None else _clamp(avg_cleanliness / 100.0, 0.0, 1.0)

    quality = (accuracy_factor ** 0.70) * (cleanliness_factor ** 0.30)

    return avg_accuracy, avg_cleanliness, _clamp(quality, 0.0, 1.0)


def _charset_from_settings_json(settings_json: str) -> str:
    try:
        settings = json.loads(settings_json)
    except Exception:
        return ""

    if not isinstance(settings, dict):
        return ""

    chars = ""

    if settings.get("use_letters"):
        chars += config.LETTERS

    if settings.get("use_numbers"):
        chars += config.NUMBERS

    if settings.get("use_punctuation"):
        chars += config.PUNCTUATION

    return chars


def _expected_charset(rows: Sequence[Any]) -> str:
    chars = ""

    for row in rows:
        settings_json = str(_row_get(row, "settings_json", "") or "")
        chars += _charset_from_settings_json(settings_json)

    if not chars:
        for row in rows:
            target = str(_row_get(row, "target", "") or "")
            chars += "".join(ch for ch in target.upper() if ch and not ch.isspace())

    return "".join(dict.fromkeys(ch for ch in chars if ch and not ch.isspace()))


def _character_mastery(
    character_rows: Sequence[Any],
    expected_charset: str,
) -> tuple[Dict[str, CharacterMastery], float, float]:
    by_char: dict[str, dict[str, int]] = {}

    for row in character_rows:
        char = str(_row_get(row, "char", "") or "").upper()

        if not char or char.isspace():
            continue

        attempts = int(_row_get(row, "attempts", 0) or 0)
        correct = int(_row_get(row, "correct", 0) or 0)
        errors = int(_row_get(row, "errors", 0) or 0)

        if attempts <= 0:
            continue

        current = by_char.setdefault(
            char,
            {
                "attempts": 0,
                "correct": 0,
                "errors": 0,
            },
        )

        current["attempts"] += attempts
        current["correct"] += correct
        current["errors"] += errors

    expected = list(dict.fromkeys(ch for ch in expected_charset if ch and not ch.isspace()))

    if not expected:
        expected = sorted(by_char.keys())

    mastery: dict[str, CharacterMastery] = {}
    mastery_values_for_expected_chars: list[float] = []
    covered_count = 0

    for char in expected:
        stats = by_char.get(
            char,
            {
                "attempts": 0,
                "correct": 0,
                "errors": 0,
            },
        )

        attempts = int(stats["attempts"])
        correct = int(stats["correct"])
        errors = int(stats["errors"])

        if attempts > 0:
            accuracy = _clamp(correct / attempts, 0.0, 1.0)
            confidence = _clamp(attempts / (attempts + CONFIDENCE_K), 0.0, 1.0)
            value = _clamp(accuracy * confidence, 0.0, 1.0)
        else:
            accuracy = 0.0
            confidence = 0.0
            value = 0.0

        covered = attempts >= COVERAGE_MIN_ATTEMPTS

        if covered:
            covered_count += 1

        mastery_values_for_expected_chars.append(value)

        mastery[char] = CharacterMastery(
            char=char,
            attempts=attempts,
            correct=correct,
            errors=errors,
            accuracy=round(accuracy, 4),
            confidence=round(confidence, 4),
            mastery=round(value, 4),
            covered=covered,
        )

    if not expected:
        return mastery, 0.0, 0.0

    mastery_factor = _clamp(float(mean(mastery_values_for_expected_chars)), 0.0, 1.0)
    coverage_factor = _clamp(covered_count / len(expected), 0.0, 1.0)

    return mastery, mastery_factor, coverage_factor


def _full_supported_charset() -> str:
    """Return the full Morsewurst character set used for level-only scope."""

    chars = (
        str(getattr(config, "LETTERS", "") or "")
        + str(getattr(config, "NUMBERS", "") or "")
        + str(getattr(config, "PUNCTUATION", "") or "")
    )

    return "".join(dict.fromkeys(ch.upper() for ch in chars if ch and not ch.isspace()))


def _full_charset_scope_metrics(character_rows: Sequence[Any]) -> dict[str, float | int]:
    """Calculate full-character-set coverage used only for level progression.

    This is intentionally separate from _character_mastery() so that the existing
    mastery and coverage values keep their current meaning.

    The rows passed here should already come from high-quality skill evidence
    rounds. A character counts only after enough appearances, enough distinct
    high-quality rounds and sufficient character-specific accuracy.
    """

    full_charset = _full_supported_charset()
    full_charset_set = set(full_charset)
    full_total = len(full_charset)

    by_char: dict[str, dict[str, int]] = {}

    for row in character_rows:
        char = str(_row_get(row, "char", "") or "").upper()

        if not char or char.isspace() or char not in full_charset_set:
            continue

        attempts = int(_row_get(row, "attempts", 0) or 0)
        correct = int(_row_get(row, "correct", 0) or 0)
        qualified_rounds = int(_row_get(row, "qualified_rounds", 0) or 0)

        if attempts <= 0:
            continue

        current = by_char.setdefault(
            char,
            {
                "attempts": 0,
                "correct": 0,
                "qualified_rounds": 0,
            },
        )

        current["attempts"] += attempts
        current["correct"] += correct
        current["qualified_rounds"] += qualified_rounds

    qualified_count = 0

    for char in full_charset:
        stats = by_char.get(char, {"attempts": 0, "correct": 0, "qualified_rounds": 0})
        attempts = int(stats["attempts"])
        correct = int(stats["correct"])
        qualified_rounds = int(stats["qualified_rounds"])

        if attempts < FULL_CHARSET_MIN_ATTEMPTS:
            continue

        if qualified_rounds < FULL_CHARSET_MIN_ROUNDS:
            continue

        accuracy = (correct / attempts) * 100.0 if attempts > 0 else 0.0

        if accuracy >= FULL_CHARSET_MIN_ACCURACY:
            qualified_count += 1

    coverage = 0.0 if full_total <= 0 else _clamp(qualified_count / full_total, 0.0, 1.0)

    min_factor = _clamp(CHARSET_SCOPE_MIN_FACTOR, 0.0, 1.0)
    max_factor = _clamp(CHARSET_SCOPE_MAX_FACTOR, min_factor, 1.0)
    scope_factor = _clamp(
        min_factor + ((max_factor - min_factor) * coverage),
        min_factor,
        max_factor,
    )

    return {
        "full_charset_total": int(full_total),
        "full_charset_qualified_count": int(qualified_count),
        "full_charset_qualified_coverage": round(coverage, 4),
        "charset_scope_factor": round(scope_factor, 4),
    }


def _relative_score(actual: Optional[float], ideal: Optional[float]) -> Optional[float]:
    if actual is None or ideal is None:
        return None

    if actual <= 0 or ideal <= 0:
        return None

    relative_error = abs(actual - ideal) / ideal
    return _clamp(1.0 - relative_error, 0.0, 1.0)


def _timing_stability_factor(rows: Sequence[Any]) -> float:
    scores: list[float] = []

    for row in rows:
        ratio = _safe_float(_row_get(row, "straight_dash_dot_ratio"))

        if ratio is not None and ratio > 0:
            ratio_error = abs(ratio - 3.0)
            scores.append(_clamp(1.0 - (ratio_error / 1.5), 0.0, 1.0))

        avg_dit_us = _safe_float(_row_get(row, "avg_dit_us"))
        avg_letter_gap_us = _safe_float(_row_get(row, "avg_letter_gap_us"))
        avg_word_gap_us = _safe_float(_row_get(row, "avg_word_gap_us"))

        source = str(_row_get(row, "source", "") or "").lower()

        if "straight" in source:
            letter_units = float(getattr(config, "DECODER_STRAIGHT_LETTER_GAP_UNITS", 3.0))
            word_units = float(getattr(config, "DECODER_STRAIGHT_WORD_GAP_UNITS", 7.0))
        else:
            letter_units = float(getattr(config, "DECODER_IAMBIC_LETTER_GAP_UNITS", 3.0))
            word_units = float(getattr(config, "DECODER_IAMBIC_WORD_GAP_UNITS", 7.0))

        if avg_dit_us is not None and avg_dit_us > 0:
            letter_score = _relative_score(avg_letter_gap_us, avg_dit_us * letter_units)
            word_score = _relative_score(avg_word_gap_us, avg_dit_us * word_units)

            if letter_score is not None:
                scores.append(letter_score)

            if word_score is not None:
                scores.append(word_score)

    if not scores:
        return 1.0

    base_score = _clamp(float(mean(scores)), 0.0, 1.0)

    return _clamp(
        TIMING_MIN_FACTOR + ((TIMING_MAX_FACTOR - TIMING_MIN_FACTOR) * base_score),
        TIMING_MIN_FACTOR,
        TIMING_MAX_FACTOR,
    )


def _sample_confidence(used_rounds: int) -> float:
    if used_rounds <= 0:
        return 0.0

    return _clamp(used_rounds / (used_rounds + SAMPLE_CONFIDENCE_K), 0.0, 1.0)


def _rating_confidence(
    *,
    sample_confidence: float,
    character_mastery_factor: float,
    coverage_factor: float,
) -> float:
    return _clamp(
        (sample_confidence * 0.40)
        + (character_mastery_factor * 0.30)
        + (coverage_factor * 0.30),
        0.0,
        1.0,
    )


def _mastery_adjustment(rating_confidence: float) -> float:
    return _clamp(
        MASTERY_ADJUSTMENT_MIN
        + ((MASTERY_ADJUSTMENT_MAX - MASTERY_ADJUSTMENT_MIN) * rating_confidence),
        MASTERY_ADJUSTMENT_MIN,
        MASTERY_ADJUSTMENT_MAX,
    )


def confidence_label(value: float) -> str:
    value = _clamp(value, 0.0, 1.0)

    if value < 0.20:
        return "matala"

    if value < 0.45:
        return "alustava"

    if value < 0.70:
        return "kohtalainen"

    if value < 0.90:
        return "hyvä"

    return "erinomainen"


def empty_skill_rating(reason: str, recent_rounds: int) -> SkillRating:
    progression = progression_from_raw_skill(None)

    return SkillRating(
        ok=False,
        reason=reason,
        model_version=MODEL_VERSION,
        recent_rounds=recent_rounds,
        total_rounds=0,
        used_rounds=0,
        effective_wpm=None,
        iambic_wpm=None,
        straight_wpm=None,
        iambic_paris_wpm=None,
        straight_paris_wpm=None,
        iambic_used_rounds=0,
        straight_used_rounds=0,
        avg_accuracy=None,
        avg_cleanliness=None,
        quality_factor=0.0,
        character_mastery_factor=0.0,
        coverage_factor=0.0,
        timing_stability_factor=1.0,
        timing_quality_score=None,
        straight_timing_score=None,
        iambic_timing_score=None,
        timing_used_rounds=0,
        timing_reason="",
        sample_confidence=0.0,
        rating_confidence=0.0,
        mastery_adjustment=1.0,
        raw_skill=None,
        level_skill=None,
        full_charset_total=len(_full_supported_charset()),
        full_charset_qualified_count=0,
        full_charset_qualified_coverage=0.0,
        charset_scope_factor=round(
            _clamp(CHARSET_SCOPE_MIN_FACTOR, 0.0, 1.0),
            4,
        ),
        level=progression.level,
        level_progress=progression.level_progress,
        title=progression.title,
        expected_charset="",
        character_mastery={},
    )


def calculate_skill_rating(
    db: Any,
    *,
    recent_rounds: int = DEFAULT_RECENT_ROUNDS,
) -> SkillRating:
    recent_rounds = max(1, int(recent_rounds))

    session_rows = db.skill_recent_sessions(
        recent_rounds,
        min_target_chars=MIN_TARGET_CHARS,
    )

    if not session_rows:
        return empty_skill_rating(
            (
                "Tietokannassa ei ole vielä riittävän pitkiä harjoituskierroksia "
                f"taitotason laskentaan. Tarvitaan kierroksia, joissa tavoitteessa "
                f"on vähintään {MIN_TARGET_CHARS} merkkiä."
            ),
            recent_rounds,
        )

    source_rows_by_key = _source_rows_by_key(db, recent_rounds)

    key_source_wpm = _key_source_wpm_from_rows(source_rows_by_key)
    key_source_paris_wpm = _key_source_paris_wpm_from_rows(source_rows_by_key)

    effective_wpm, used_rounds = _balanced_effective_wpm_from_rows(source_rows_by_key)
    raw_skill_base_wpm = _balanced_raw_skill_wpm_from_rows(source_rows_by_key)

    if raw_skill_base_wpm is None:
        straight_count = len(source_rows_by_key.get("straight", []))
        iambic_count = len(source_rows_by_key.get("iambic", []))

        return empty_skill_rating(
            (
                "Taitotasoa ei voitu vielä laskea, koska yleistaitotaso vaatii "
                "laskentakelpoista dataa sekä straight- että iambic-kierroksista. "
                f"Straight-kierroksia löytyi {straight_count}, "
                f"iambic-kierroksia löytyi {iambic_count}."
            ),
            recent_rounds,
        )

    character_rows = db.skill_character_results(
        recent_rounds,
        min_target_chars=MIN_TARGET_CHARS,
    )
    expected_charset = _expected_charset(session_rows)

    character_mastery, character_mastery_factor, coverage_factor = _character_mastery(
        character_rows,
        expected_charset,
    )

    full_charset_row_loader = getattr(db, "skill_full_charset_character_results", None)
    if callable(full_charset_row_loader):
        full_charset_rows = full_charset_row_loader(
            recent_rounds,
            min_target_chars=MIN_TARGET_CHARS,
            min_accuracy=QUALIFIED_MIN_ACCURACY,
            min_cleanliness=QUALIFIED_MIN_CLEANLINESS,
        )
    else:
        full_charset_rows = []

    full_charset_scope = _full_charset_scope_metrics(full_charset_rows)

    avg_accuracy, avg_cleanliness, quality_factor = _quality_factor(session_rows)
    timing_quality_score = None
    straight_timing_score = None
    iambic_timing_score = None
    timing_used_rounds = 0
    timing_reason = ""

    try:
        timing_quality = calculate_timing_quality(
            db,
            recent_rounds=recent_rounds,
            min_target_chars=MIN_TARGET_CHARS,
            min_accuracy=QUALIFIED_MIN_ACCURACY,
            min_cleanliness=QUALIFIED_MIN_CLEANLINESS,
        )

        timing_stability_factor = float(timing_quality.factor)
        timing_quality_score = timing_quality.total_score

        straight_timing_score = timing_quality.straight.total_score
        iambic_timing_score = timing_quality.iambic.total_score

        if hasattr(db, "skill_timing_score_average_by_key_source"):
            timing_score_averages = db.skill_timing_score_average_by_key_source(
                recent_sessions=recent_rounds,
                min_target_chars=MIN_TARGET_CHARS,
                min_accuracy=QUALIFIED_MIN_ACCURACY,
                min_cleanliness=QUALIFIED_MIN_CLEANLINESS,
            )

            if timing_score_averages.get("straight_timing_score") is not None:
                straight_timing_score = float(timing_score_averages["straight_timing_score"])

            if timing_score_averages.get("iambic_timing_score") is not None:
                iambic_timing_score = float(timing_score_averages["iambic_timing_score"])

        timing_used_rounds = int(timing_quality.used_rounds)
        timing_reason = str(timing_quality.reason or "")

    except Exception as exc:
        # Fallback to the older coarse timing calculation.
        timing_stability_factor = _timing_stability_factor(session_rows)
        timing_reason = f"Rytmianalyysi epäonnistui, käytettiin vanhaa ajoituskerrointa: {exc}"

    sample_conf = _sample_confidence(used_rounds)
    rating_conf = _rating_confidence(
        sample_confidence=sample_conf,
        character_mastery_factor=character_mastery_factor,
        coverage_factor=coverage_factor,
    )
    mastery_adj = _mastery_adjustment(rating_conf)

    raw_skill = (
        raw_skill_base_wpm
        * timing_stability_factor
        * mastery_adj
    )

    charset_scope_factor = float(full_charset_scope["charset_scope_factor"])
    level_skill = raw_skill * charset_scope_factor

    progression = progression_from_raw_skill(level_skill)

    if used_rounds < MIN_QUALIFIED_ROUNDS:
        ok = False
        reason = (
            f"Arvio on alustava. Heikommalta avaintyypiltä sopivia kierroksia "
            f"löytyi {used_rounds}, mutta luotettavaan arvioon tarvitaan "
            f"vähintään {MIN_QUALIFIED_ROUNDS}."
        )
    elif rating_conf < 0.50:
        ok = True
        reason = (
            f"Arvion luottamus on {confidence_label(rating_conf)}. "
            "Harjoittele vielä laajempaa merkkivalikoimaa, jotta taso varmistuu."
        )
    else:
        ok = True
        reason = ""

    return SkillRating(
        ok=ok,
        reason=reason,
        model_version=MODEL_VERSION,
        recent_rounds=recent_rounds,
        total_rounds=len(session_rows),
        used_rounds=used_rounds,
        effective_wpm=None if effective_wpm is None else round(effective_wpm, 2),
        iambic_wpm=(
            None
            if key_source_wpm.get("iambic_wpm") is None
            else round(float(key_source_wpm["iambic_wpm"]), 2)
        ),
        straight_wpm=(
            None
            if key_source_wpm.get("straight_wpm") is None
            else round(float(key_source_wpm["straight_wpm"]), 2)
        ),
        iambic_paris_wpm=(
            None
            if key_source_paris_wpm.get("iambic_paris_wpm") is None
            else round(float(key_source_paris_wpm["iambic_paris_wpm"]), 2)
        ),
        straight_paris_wpm=(
            None
            if key_source_paris_wpm.get("straight_paris_wpm") is None
            else round(float(key_source_paris_wpm["straight_paris_wpm"]), 2)
        ),
        iambic_used_rounds=int(key_source_wpm.get("iambic_used_rounds") or 0),
        straight_used_rounds=int(key_source_wpm.get("straight_used_rounds") or 0),
        avg_accuracy=None if avg_accuracy is None else round(avg_accuracy, 2),
        avg_cleanliness=None if avg_cleanliness is None else round(avg_cleanliness, 2),
        quality_factor=round(quality_factor, 4),
        character_mastery_factor=round(character_mastery_factor, 4),
        coverage_factor=round(coverage_factor, 4),
        timing_stability_factor=round(timing_stability_factor, 4),
        timing_quality_score=None if timing_quality_score is None else round(float(timing_quality_score), 2),
        straight_timing_score=None if straight_timing_score is None else round(float(straight_timing_score), 2),
        iambic_timing_score=None if iambic_timing_score is None else round(float(iambic_timing_score), 2),
        timing_used_rounds=int(timing_used_rounds),
        timing_reason=timing_reason,
        sample_confidence=round(sample_conf, 4),
        rating_confidence=round(rating_conf, 4),
        mastery_adjustment=round(mastery_adj, 4),
        raw_skill=round(raw_skill, 2),
        level_skill=round(level_skill, 2),
        full_charset_total=int(full_charset_scope["full_charset_total"]),
        full_charset_qualified_count=int(full_charset_scope["full_charset_qualified_count"]),
        full_charset_qualified_coverage=float(full_charset_scope["full_charset_qualified_coverage"]),
        charset_scope_factor=round(charset_scope_factor, 4),
        level=progression.level,
        level_progress=round(progression.level_progress, 4),
        title=progression.title,
        expected_charset=expected_charset,
        character_mastery=character_mastery,
    )


def skill_rating_to_dict(rating: SkillRating) -> dict[str, Any]:
    return asdict(rating)