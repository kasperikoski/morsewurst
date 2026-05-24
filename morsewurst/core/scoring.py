# ============================================================
# morsewurst/core/scoring.py
# ============================================================

from __future__ import annotations

import re
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional, Tuple

import morsewurst.config as config
from morsewurst.core.adaptive_decoder import DecodedTelemetry, MORSE_TO_CHAR, decode_tone_events
from morsewurst.core.challenge import score_text
from morsewurst.core.timing_quality import calculate_round_timing_quality
from morsewurst.models import CharacterResult, ChallengeSettings, ScoreSummary


def normalize_text(text: str) -> str:
    return text.upper().replace("\n", " ").strip()


def normalize_for_score(text: str, *, keep_spaces: bool = True) -> str:
    return score_text(text, keep_spaces=keep_spaces)


def telemetry_visible_text(text: str, max_chars: int) -> str:
    text = text.replace("\n", " ")
    text = re.sub(r" {2,}", " ", text).strip()

    if max_chars <= 0:
        return text

    if len(text) <= max_chars:
        return text

    return text[-max_chars:]


def _round_float(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None

    return round(float(value), digits)


def _safe_mean(values: List[float]) -> Optional[float]:
    return mean(values) if values else None


def _safe_pstdev(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return None

    return float(pstdev(values))

def _first_numeric(*values: Any) -> Optional[float]:
    for value in values:
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _safe_percent(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0

    return max(0.0, min(100.0, (numerator / denominator) * 100.0))


def _cleanliness_percent(
    *,
    errors: int,
    target_length: int,
    entered_length: int,
) -> float:
    denominator = max(1, target_length, entered_length)
    return max(0.0, min(100.0, 100.0 - ((errors / denominator) * 100.0)))


def _speed_percent(
    *,
    elapsed_us: Optional[float],
    reference_us: Optional[float],
) -> Optional[float]:
    if elapsed_us is None or reference_us is None:
        return None

    if elapsed_us <= 0 or reference_us <= 0:
        return None

    # 100 means the user matched or exceeded the target WPM.
    # Faster-than-target performance is not given extra round-score bonus.
    return max(0.0, min(100.0, (reference_us / elapsed_us) * 100.0))


def _cfg_float(name: str, default: float) -> float:
    try:
        return float(getattr(config, name, default))
    except Exception:
        return float(default)


def _overall_score(
    *,
    character_accuracy: float,
    cleanliness: float,
    speed: Optional[float],
    timing: Optional[float],
) -> float:
    # Speed and timing are useful, but they should not dominate learning
    # accuracy. If either component is unavailable, that component is neutral.
    speed_component = 100.0 if speed is None else min(100.0, speed)
    timing_component = 100.0 if timing is None else min(100.0, timing)

    weights = {
        "accuracy": max(0.0, _cfg_float("ROUND_SCORE_ACCURACY_WEIGHT", 0.60)),
        "cleanliness": max(0.0, _cfg_float("ROUND_SCORE_CLEANLINESS_WEIGHT", 0.20)),
        "speed": max(0.0, _cfg_float("ROUND_SCORE_SPEED_WEIGHT", 0.10)),
        "timing": max(0.0, _cfg_float("ROUND_SCORE_TIMING_WEIGHT", 0.10)),
    }

    total_weight = sum(weights.values())
    if total_weight <= 0:
        weights = {"accuracy": 0.60, "cleanliness": 0.20, "speed": 0.10, "timing": 0.10}
        total_weight = 1.0

    return (
        character_accuracy * weights["accuracy"]
        + cleanliness * weights["cleanliness"]
        + speed_component * weights["speed"]
        + timing_component * weights["timing"]
    ) / total_weight


def _keep_spaces_for_target(target: str) -> bool:
    """
    Spaces are always scored.

    A missing target space, an extra entered space, or a space in the wrong
    position is treated as an edit-distance error.
    """
    return True


def build_character_timing(
    events: List[Dict[str, Any]],
    *,
    keep_spaces: bool = True,
    decoded: Optional[DecodedTelemetry] = None,
) -> List[Dict[str, Any]]:
    """Return per-character timing from adaptive telemetry decoding.

    The adaptive decoder is the single source of truth for Morse symbols, gap
    handling and character timing.
    """

    if decoded is None:
        decoded = decode_tone_events(events, flush_final=True)

    if keep_spaces:
        return list(decoded.char_infos)

    return [
        info for info in decoded.char_infos
        if info.get("ch") != " "
    ]


def _levenshtein_backtrace(
    target_n: str,
    entered_n: str,
) -> List[Tuple[str, Optional[int], Optional[int]]]:
    n = len(target_n)
    m = len(entered_n)

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    back = [[""] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = i
        back[i][0] = "delete"

    for j in range(1, m + 1):
        dp[0][j] = j
        back[0][j] = "insert"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if target_n[i - 1] == entered_n[j - 1] else 1

            candidates = [
                (dp[i - 1][j - 1] + cost, "equal" if cost == 0 else "substitution"),
                (dp[i - 1][j] + 1, "delete"),
                (dp[i][j - 1] + 1, "insert"),
            ]

            best_cost, best_action = min(
                candidates,
                key=lambda item: (
                    item[0],
                    0 if item[1] in {"equal", "substitution"} else 1,
                    2 if item[1] == "insert" else 0,
                ),
            )

            dp[i][j] = best_cost
            back[i][j] = best_action

    reversed_ops: list[Tuple[str, Optional[int], Optional[int]]] = []

    i = n
    j = m

    while i > 0 or j > 0:
        action = back[i][j]

        if i > 0 and j > 0 and action in {"equal", "substitution"}:
            reversed_ops.append((action, i - 1, j - 1))
            i -= 1
            j -= 1
            continue

        if i > 0 and (j == 0 or action == "delete"):
            reversed_ops.append(("delete", i - 1, None))
            i -= 1
            continue

        if j > 0:
            reversed_ops.append(("insert", None, j - 1))
            j -= 1
            continue

        break

    return list(reversed(reversed_ops))


def _timing_info_for_entered_index(
    char_infos: List[Dict[str, Any]],
    entered_index: Optional[int],
) -> Dict[str, Any]:
    if entered_index is None:
        return {}

    if 0 <= entered_index < len(char_infos):
        return char_infos[entered_index]

    return {}


def levenshtein_results(
    target: str,
    entered: str,
    events: List[Dict[str, Any]],
    count_missing: bool = True,
    decoded: Optional[DecodedTelemetry] = None,
    keep_spaces: Optional[bool] = None,
) -> Tuple[int, int, int, int, int, List[CharacterResult]]:
    """Align target and entered text with edit distance.

    If keep_spaces is True, internal spaces are scored as real characters.
    If keep_spaces is False, spaces are ignored.
    During live scoring, count_missing=False means that trailing target
    characters are not yet counted as missing.
    """

    if keep_spaces is None:
        keep_spaces = _keep_spaces_for_target(target)

    target_n = normalize_for_score(target, keep_spaces=keep_spaces)
    entered_n = normalize_for_score(entered, keep_spaces=keep_spaces)

    if not count_missing:
        target_n = target_n[: max(len(entered_n), 0)]

    char_infos = build_character_timing(
        events,
        keep_spaces=keep_spaces,
        decoded=decoded,
    )

    ops = _levenshtein_backtrace(target_n, entered_n)

    correct = 0
    substitutions = 0
    deletions = 0
    insertions = 0

    results: list[CharacterResult] = []

    for visual_index, (action, target_index, entered_index) in enumerate(ops):
        target_char = target_n[target_index] if target_index is not None else None
        entered_char = entered_n[entered_index] if entered_index is not None else None
        info = _timing_info_for_entered_index(char_infos, entered_index)

        if action == "equal":
            result_name = "correct"
            correct += 1

        elif action == "substitution":
            result_name = "substitution"
            substitutions += 1

        elif action == "delete":
            result_name = "deletion"
            deletions += 1

        else:
            result_name = "insertion"
            insertions += 1

        results.append(
            CharacterResult(
                position_index=visual_index,
                target_char=target_char,
                entered_char=entered_char,
                result=result_name,
                entered_code=info.get("code"),
                source=info.get("source"),
                char_time_us=info.get("char_time_us"),
                first_element_us=info.get("first_element_us"),
                last_element_us=info.get("last_element_us"),
                gap_before_us=info.get("gap_before_us"),
                dit_us=info.get("dit_us"),
                wpm=info.get("wpm"),
                element_unit_us=info.get("element_unit_us"),
                gap_unit_us=info.get("gap_unit_us"),
                gap_before_units=info.get("gap_before_units"),
                gap_kind=info.get("gap_kind"),
            )
        )

    errors = substitutions + insertions + deletions

    return correct, errors, substitutions, insertions, deletions, results


def event_metrics(
    events: List[Dict[str, Any]],
    *,
    decoded: Optional[DecodedTelemetry] = None,
) -> Dict[str, Optional[float]]:
    if decoded is None:
        decoded = decode_tone_events(events, flush_final=True)

    char_infos = decoded.char_infos
    element_infos = decoded.element_infos

    if not element_infos:
        return {
            "elapsed_us": None,
            "avg_wpm": None,
            "avg_dit_us": None,
            "dit_sd_us": None,
            "straight_dot_us": None,
            "straight_dot_sd_us": None,
            "straight_dash_us": None,
            "straight_dash_sd_us": None,
            "straight_dash_dot_ratio": None,
            "avg_letter_gap_us": None,
            "letter_gap_sd_us": None,
            "avg_word_gap_us": None,
            "word_gap_sd_us": None,
        }

    wpm_values = [
        float(info["wpm"])
        for info in element_infos
        if isinstance(info.get("wpm"), (int, float))
    ]

    element_unit_values = [
        float(value)
        for info in element_infos
        for value in [_first_numeric(info.get("element_unit_us"), info.get("unit_us"))]
        if value is not None
    ]

    straight_dots = [
        float(info["dur"])
        for info in element_infos
        if info.get("src") == "straight"
        and info.get("element") == "."
        and isinstance(info.get("dur"), (int, float))
    ]

    straight_dashes = [
        float(info["dur"])
        for info in element_infos
        if info.get("src") == "straight"
        and info.get("element") == "-"
        and isinstance(info.get("dur"), (int, float))
    ]

    letter_gaps = [
        float(info["gap_before_us"])
        for info in char_infos
        if info.get("ch") != " "
        and info.get("gap_kind") == "letter"
        and isinstance(info.get("gap_before_us"), int)
    ]

    word_gaps = [
        float(info["gap_before_us"])
        for info in char_infos
        if info.get("ch") == " "
        and info.get("gap_kind") == "word"
        and isinstance(info.get("gap_before_us"), int)
    ]

    first_t = min(int(info["t0"]) for info in element_infos)
    last_t = max(int(info["t1"]) for info in element_infos)

    elapsed_us = float(last_t - first_t) if last_t >= first_t else None

    dot_avg = _safe_mean(straight_dots)
    dash_avg = _safe_mean(straight_dashes)
    ratio = dash_avg / dot_avg if dot_avg and dash_avg else None

    return {
        "elapsed_us": elapsed_us,
        "avg_wpm": _safe_mean(wpm_values),
        "avg_dit_us": _safe_mean(element_unit_values),
        "dit_sd_us": _safe_pstdev(element_unit_values),
        "straight_dot_us": dot_avg,
        "straight_dot_sd_us": _safe_pstdev(straight_dots),
        "straight_dash_us": dash_avg,
        "straight_dash_sd_us": _safe_pstdev(straight_dashes),
        "straight_dash_dot_ratio": ratio,
        "avg_letter_gap_us": _safe_mean(letter_gaps),
        "letter_gap_sd_us": _safe_pstdev(letter_gaps),
        "avg_word_gap_us": _safe_mean(word_gaps),
        "word_gap_sd_us": _safe_pstdev(word_gaps),
    }

def _char_to_morse_table() -> dict[str, str]:
    table: dict[str, str] = {}

    for code, char in MORSE_TO_CHAR.items():
        if not char:
            continue

        if any(element not in {".", "-"} for element in str(code)):
            continue

        table[str(char).upper()] = str(code)

    return table


CHAR_TO_MORSE = _char_to_morse_table()


def morse_symbol_unit_count(code: str) -> int:
    """Return Morse timing units inside one character.

    Dit = 1 unit
    Dah = 3 units
    Gap between elements inside the same character = 1 unit
    """

    units = 0

    for index, element in enumerate(code):
        if index > 0:
            units += 1

        if element == ".":
            units += 1
        elif element == "-":
            units += 3

    return units


def paris_unit_count(text: str) -> int:
    """Return PARIS-style unit count for text.

    Character gap = 3 units
    Word gap = 7 units

    This counts the target text as Morse timing units, not as plain characters.
    """

    normalized = normalize_text(text)

    total_units = 0
    has_previous_symbol = False
    pending_word_gap = False

    for char in normalized:
        if char.isspace():
            if has_previous_symbol:
                pending_word_gap = True
            continue

        code = CHAR_TO_MORSE.get(char)

        if code is None:
            continue

        if has_previous_symbol:
            if pending_word_gap:
                total_units += 7
            else:
                total_units += 3

        total_units += morse_symbol_unit_count(code)

        has_previous_symbol = True
        pending_word_gap = False

    return total_units


def paris_wpm_for_text(text: str, elapsed_us: Optional[float]) -> Optional[float]:
    """Return effective PARIS WPM for completing text in elapsed_us."""

    if elapsed_us is None or elapsed_us <= 0:
        return None

    units = paris_unit_count(text)

    if units <= 0:
        return None

    return (units * 1_200_000.0) / float(elapsed_us)


def estimate_paris_time_us(text: str, target_wpm: float) -> Optional[int]:
    """Return expected completion time for text at target PARIS WPM."""

    if target_wpm <= 0:
        return None

    units = paris_unit_count(text)

    if units <= 0:
        return None

    return int(round((units * 1_200_000.0) / float(target_wpm)))


def profile_learning_eligibility(
    decoded: Optional[DecodedTelemetry],
) -> tuple[bool, Optional[str], Optional[float], Optional[float]]:
    if decoded is None:
        return True, None, None, None

    max_element_units: Optional[float] = None
    max_gap_units: Optional[float] = None

    for info in getattr(decoded, "element_infos", []) or []:
        if not isinstance(info, dict):
            continue

        dur = _first_numeric(info.get("dur"))
        unit_us = _first_numeric(info.get("element_unit_us"), info.get("unit_us"))

        if dur is None or unit_us is None or unit_us <= 0:
            continue

        units = float(dur) / float(unit_us)
        max_element_units = units if max_element_units is None else max(max_element_units, units)

    for info in getattr(decoded, "char_infos", []) or []:
        if not isinstance(info, dict):
            continue

        units = _first_numeric(info.get("gap_before_units"))

        if units is None or units < 0:
            continue

        max_gap_units = units if max_gap_units is None else max(max_gap_units, units)

    reject_reasons: list[str] = []

    if bool(getattr(config, "DECODER_PROFILE_REJECT_EXTREME_ELEMENTS", True)):
        element_limit = float(getattr(config, "DECODER_PROFILE_MAX_ELEMENT_UNITS", 12.0))
        if max_element_units is not None and max_element_units > element_limit:
            reject_reasons.append("extreme_element_duration")

    if bool(getattr(config, "DECODER_PROFILE_REJECT_EXTREME_GAPS", True)):
        gap_limit = float(getattr(config, "DECODER_PROFILE_MAX_GAP_UNITS", 30.0))
        if max_gap_units is not None and max_gap_units > gap_limit:
            reject_reasons.append("extreme_gap_duration")

    return (
        not reject_reasons,
        ",".join(reject_reasons) if reject_reasons else None,
        _round_float(max_element_units),
        _round_float(max_gap_units),
    )


def score_round(
    target: str,
    entered: str,
    source: str,
    events: List[Dict[str, Any]],
    settings: ChallengeSettings,
    finish_reason: str,
    count_missing: bool = True,
    *,
    decoder_settings: Any | None = None,
    seed_unit_us: Optional[float] = None,
    decoded: Optional[DecodedTelemetry] = None,
) -> Tuple[ScoreSummary, List[CharacterResult]]:
    target_display = normalize_text(target)
    entered_display = normalize_text(entered)

    # Accuracy is based on actual transmitted characters only.
    # Spaces are ignored here, so a missing or extra word/group gap does not reduce
    # character accuracy.
    target_accuracy_score = normalize_for_score(target, keep_spaces=False)
    entered_accuracy_score = normalize_for_score(entered, keep_spaces=False)

    # Cleanliness and error counts include internal spaces.
    # This means missing, extra, or misplaced spaces are still counted as errors.
    target_clean_score = normalize_for_score(target, keep_spaces=True)
    entered_clean_score = normalize_for_score(entered, keep_spaces=True)

    if decoded is None:
        decoded = decode_tone_events(
            events,
            flush_final=True,
            settings=decoder_settings,
            seed_unit_us=seed_unit_us,
            target_wpm=settings.target_wpm,
            target_text=target_display,
        )

    accuracy_correct, _accuracy_errors, _accuracy_substitutions, _accuracy_insertions, _accuracy_deletions, _accuracy_results = levenshtein_results(
        target,
        entered,
        events,
        count_missing=count_missing,
        decoded=decoded,
        keep_spaces=False,
    )

    _clean_correct, errors, substitutions, insertions, deletions, results = levenshtein_results(
        target,
        entered,
        events,
        count_missing=count_missing,
        decoded=decoded,
        keep_spaces=True,
    )

    metrics = event_metrics(events, decoded=decoded)
    timing_quality = calculate_round_timing_quality(
        events,
        decoded=decoded,
        target_text=target_display,
    )
    timing_score = timing_quality.total_score
    soft_boundary_count = int(getattr(decoded, "soft_boundary_count", 0))

    (
        profile_eligible,
        profile_reject_reason,
        profile_max_element_units,
        profile_max_gap_units,
    ) = profile_learning_eligibility(decoded)

    standard_time_us = estimate_paris_time_us(
        target_display,
        settings.target_wpm,
    )

    time_ok = None

    if metrics["elapsed_us"] is not None and standard_time_us is not None:
        time_ok = metrics["elapsed_us"] <= standard_time_us

    character_accuracy = _safe_percent(
        accuracy_correct,
        len(target_accuracy_score),
    )

    cleanliness = _cleanliness_percent(
        errors=errors,
        target_length=len(target_clean_score),
        entered_length=len(entered_clean_score),
    )

    speed_score = _speed_percent(
        elapsed_us=metrics["elapsed_us"],
        reference_us=standard_time_us,
    )

    overall_score = _overall_score(
        character_accuracy=character_accuracy,
        cleanliness=cleanliness,
        speed=speed_score,
        timing=timing_score,
    )

    gross_wpm = None
    net_wpm = None

    elapsed_us = metrics["elapsed_us"]

    if elapsed_us is not None and elapsed_us > 0:
        # Completed rounds use the full target text, because the user has
        # reached the intended exercise length.
        #
        # Interrupted or idle-finished rounds use the actually entered text.
        # Otherwise a long target plus one quickly sent character can produce
        # an absurd PARIS WPM, because telemetry elapsed time only covers the
        # sent tone events and does not include the final idle timeout.
        #
        # Very short interrupted rounds are ignored for WPM display, because
        # one or two entered characters are too little evidence for a useful
        # PARIS WPM value.
        wpm_text = target_display

        if finish_reason != "completed":
            wpm_text = entered_display

            if len(normalize_for_score(wpm_text, keep_spaces=False)) < 3:
                wpm_text = ""

        gross_wpm = paris_wpm_for_text(wpm_text, elapsed_us)

        # Net WPM is kept for continuity, but accuracy and cleanliness are the
        # primary learning metrics.
        if gross_wpm is not None:
            accuracy_factor = character_accuracy / 100.0
            cleanliness_factor = cleanliness / 100.0
            net_wpm = gross_wpm * accuracy_factor * cleanliness_factor * timing_quality.factor

    summary = ScoreSummary(
        target=target_display,
        entered=entered_display,
        source=source,
        accuracy=round(character_accuracy, 2),
        cleanliness=round(cleanliness, 2),
        overall_score=round(overall_score, 2),
        speed_score=_round_float(speed_score),
        timing_score=_round_float(timing_score),
        correct_count=accuracy_correct,
        error_count=errors,
        substitutions=substitutions,
        insertions=insertions,
        deletions=deletions,
        length_target=len(target_accuracy_score),
        length_entered=len(entered_accuracy_score),
        soft_boundary_count=soft_boundary_count,
        elapsed_us=int(metrics["elapsed_us"]) if metrics["elapsed_us"] is not None else None,
        standard_time_us=standard_time_us,
        time_ok=time_ok,
        avg_wpm=_round_float(metrics["avg_wpm"]),
        gross_wpm=_round_float(gross_wpm),
        net_wpm=_round_float(net_wpm),
        avg_dit_us=_round_float(metrics["avg_dit_us"]),
        dit_sd_us=_round_float(metrics["dit_sd_us"]),
        straight_dot_us=_round_float(metrics["straight_dot_us"]),
        straight_dot_sd_us=_round_float(metrics["straight_dot_sd_us"]),
        straight_dash_us=_round_float(metrics["straight_dash_us"]),
        straight_dash_sd_us=_round_float(metrics["straight_dash_sd_us"]),
        straight_dash_dot_ratio=_round_float(metrics["straight_dash_dot_ratio"]),
        avg_letter_gap_us=_round_float(metrics["avg_letter_gap_us"]),
        letter_gap_sd_us=_round_float(metrics["letter_gap_sd_us"]),
        avg_word_gap_us=_round_float(metrics["avg_word_gap_us"]),
        word_gap_sd_us=_round_float(metrics["word_gap_sd_us"]),
        timing_element_score=timing_quality.element_score,
        timing_gap_score=timing_quality.gap_score,
        timing_ratio_score=timing_quality.ratio_score,
        timing_dot_consistency=timing_quality.dot_consistency_score,
        timing_dash_consistency=timing_quality.dash_consistency_score,
        timing_intra_gap_score=timing_quality.intra_gap_score,
        timing_letter_gap_score=timing_quality.letter_gap_score,
        timing_word_gap_score=timing_quality.word_gap_score,
        profile_eligible=profile_eligible,
        profile_reject_reason=profile_reject_reason,
        profile_max_element_units=profile_max_element_units,
        profile_max_gap_units=profile_max_gap_units,
        finish_reason=finish_reason,
    )

    return summary, results