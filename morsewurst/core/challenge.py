# ============================================================
# morsewurst/core/challenge.py
# ============================================================

from __future__ import annotations
from typing import Any, Optional

import random
import re
from typing import Iterable, List

import morsewurst.config as config
from morsewurst.models import ChallengeSettings


WXMOR_PROFILE_ALIASES = {
    "auto": "auto",
    "automatic": "auto",
    "automaattinen": "auto",

    "minimum": "minimum",
    "minimal": "minimum",
    "minimi": "minimum",

    "basic": "basic",
    "perus": "basic",

    "compact": "compact",
    "kompakti": "compact",

    "extended": "extended",
    "wide": "extended",
    "laaja": "extended",
}


def base_charset_from_settings(settings: ChallengeSettings) -> str:
    chars = ""

    if settings.use_letters:
        chars += config.LETTERS

    if settings.use_numbers:
        chars += config.NUMBERS

    if settings.use_punctuation:
        chars += config.PUNCTUATION

    # Safety fallback: never generate an empty challenge.
    # If the user unchecks all character classes, use letters and numbers.
    return chars or (config.LETTERS + config.NUMBERS)


def filtered_problem_chars(
    settings: ChallengeSettings,
    problem_chars: Iterable[str] | None = None,
) -> str:
    if not problem_chars:
        return ""

    allowed = set(base_charset_from_settings(settings))

    limit = max(
        1,
        int(
            getattr(
                settings,
                "problem_char_limit",
                getattr(config, "DEFAULT_PROBLEM_CHAR_LIMIT", 12),
            )
        ),
    )

    chars: list[str] = []

    for ch in problem_chars:
        if not ch:
            continue

        ch = str(ch).upper()

        if ch.isspace():
            continue

        if ch not in allowed:
            continue

        if ch in chars:
            continue

        chars.append(ch)

        if len(chars) >= limit:
            break

    return "".join(chars)


def charset_from_settings(
    settings: ChallengeSettings,
    problem_chars: Iterable[str] | None = None,
) -> str:
    """Return the normal allowed character set.

    Problem characters no longer replace the full charset. They are used as
    weighted extra candidates inside generate_challenge().
    """

    return base_charset_from_settings(settings)


def choose_weighted_character(
    settings: ChallengeSettings,
    base_chars: str,
    problem_chars: str,
) -> str:
    if not base_chars:
        base_chars = config.LETTERS + config.NUMBERS

    if not settings.practice_problem_chars or not problem_chars:
        return random.choice(base_chars)

    weight_percent = int(
        getattr(
            settings,
            "problem_char_weight_percent",
            getattr(config, "DEFAULT_PROBLEM_CHAR_WEIGHT_PERCENT", 30),
        )
    )

    weight_percent = max(0, min(100, weight_percent))

    if weight_percent <= 0:
        return random.choice(base_chars)

    if random.randint(1, 100) <= weight_percent:
        return random.choice(problem_chars)

    return random.choice(base_chars)


def generate_challenge(
    settings: ChallengeSettings,
    problem_chars: Iterable[str] | None = None,
) -> str:
    min_groups = min(settings.min_groups, settings.max_groups)
    max_groups = max(settings.min_groups, settings.max_groups)
    min_chars = min(settings.min_chars_per_group, settings.max_chars_per_group)
    max_chars = max(settings.min_chars_per_group, settings.max_chars_per_group)

    base_chars = base_charset_from_settings(settings)
    weighted_problem_chars = filtered_problem_chars(settings, problem_chars)

    group_count = random.randint(min_groups, max_groups)
    groups: List[str] = []

    for _ in range(group_count):
        length = random.randint(min_chars, max_chars)

        group = "".join(
            choose_weighted_character(
                settings,
                base_chars,
                weighted_problem_chars,
            )
            for _ in range(length)
        )

        groups.append(group)

    return " ".join(groups).upper()


def score_text(text: str, *, keep_spaces: bool = True) -> str:
    """Return the text used by scoring and completion logic.

    Leading and trailing whitespace is ignored because many keyers create a
    final automatic word-space after the last character. Internal whitespace is
    collapsed to a single space. When keep_spaces=True, internal spaces are
    scored as real characters.
    """
    normalized = re.sub(r"\s+", " ", text.upper().replace("\n", " ")).strip()
    if keep_spaces:
        return normalized
    return normalized.replace(" ", "")

def scoring_keep_spaces(target: str) -> bool:
    """
    Spaces are always scored.

    This means that an extra internal space is an error even when the target
    contains only one group.
    """
    return True


def scored_target_and_input(target: str, entered: str) -> tuple[str, str]:
    """Return the exact strings used by scoring and completion logic."""
    keep_spaces = scoring_keep_spaces(target)
    return score_text(target, keep_spaces=keep_spaces), score_text(entered, keep_spaces=keep_spaces)


def target_exactly_completed(target: str, entered: str) -> bool:
    """Return True only when the scored input equals the scored target.

    This intentionally does not use subsequence matching. The round can end
    immediately on a perfect target, but a wrong or inserted character continues
    until the input tolerance limit is reached.
    """
    target_s, entered_s = scored_target_and_input(target, entered)
    return bool(target_s) and entered_s == target_s


def normalize_wxmor_profile(profile: Optional[str]) -> str:
    value = str(profile or getattr(config, "DEFAULT_WXMOR_PROFILE", "auto")).strip().lower()
    normalized = WXMOR_PROFILE_ALIASES.get(value, value)

    allowed = set(getattr(config, "WXMOR_PROFILE_OPTIONS", ("auto", "minimum", "basic", "compact", "extended")))

    if normalized not in allowed:
        return "auto"

    return normalized


def _message_from_wxmor_result(result: Any) -> str:
    if isinstance(result, str):
        return result.strip()

    if isinstance(result, dict):
        value = result.get("message") or result.get("text") or result.get("target")
        if value is not None:
            return str(value).strip()

    value = getattr(result, "message", None)
    if value is not None:
        return str(value).strip()

    value = getattr(result, "text", None)
    if value is not None:
        return str(value).strip()

    return str(result).strip()


def generate_wxmor_challenge(
    *,
    profile: Optional[str] = None,
    locations: Optional[list[str]] = None,
    scenario_weights: Optional[dict[str, float]] = None,
) -> str:
    """Generate one WX-MOR practice target.

    This function is intentionally a thin adapter around the WX-MOR generator.
    The normal random challenge generator remains unchanged.
    """

    from morsewurst.core.wxmor import generator as wxmor_generator

    normalized_profile = normalize_wxmor_profile(profile)

    locations = locations or list(getattr(config, "WXMOR_LOCATIONS", []))
    scenario_weights = scenario_weights or dict(getattr(config, "WXMOR_SCENARIO_WEIGHTS", {}))

    # Support the generator function name you created earlier.
    # The first one is the recommended name.
    if hasattr(wxmor_generator, "generate_wxmor_message"):
        result = wxmor_generator.generate_wxmor_message(
            profile=normalized_profile,
            locations=locations or None,
            scenario_weights=scenario_weights,
        )
    elif hasattr(wxmor_generator, "generate_message"):
        result = wxmor_generator.generate_message(
            profile=normalized_profile,
            locations=locations,
            scenario_weights=scenario_weights,
        )
    elif hasattr(wxmor_generator, "generate"):
        result = wxmor_generator.generate(
            profile=normalized_profile,
            locations=locations,
            scenario_weights=scenario_weights,
        )
    else:
        raise RuntimeError(
            "WX-MOR generator function was not found. "
            "Expected generate_wxmor_message(), generate_message() or generate()."
        )

    message = _message_from_wxmor_result(result)

    if not message:
        raise RuntimeError("WX-MOR generator returned an empty message.")

    return message.upper()