from __future__ import annotations

import random

from morsewurst.core.challenge import (
    base_charset_from_settings,
    filtered_problem_chars,
    generate_challenge,
    normalize_wxmor_profile,
    score_text,
    scored_target_and_input,
    target_exactly_completed,
)
from morsewurst.models import ChallengeSettings


def test_base_charset_falls_back_when_all_classes_are_disabled() -> None:
    settings = ChallengeSettings(use_letters=False, use_numbers=False, use_punctuation=False)

    charset = base_charset_from_settings(settings)

    assert "A" in charset
    assert "0" in charset
    assert charset


def test_filtered_problem_chars_are_uppercase_unique_allowed_and_limited() -> None:
    settings = ChallengeSettings(
        use_letters=True,
        use_numbers=False,
        use_punctuation=False,
        problem_char_limit=3,
    )

    assert filtered_problem_chars(settings, "a a b 1 c d") == "ABC"


def test_generate_challenge_respects_group_and_character_limits() -> None:
    random.seed(1234)
    settings = ChallengeSettings(
        use_letters=True,
        use_numbers=False,
        use_punctuation=False,
        min_groups=2,
        max_groups=2,
        min_chars_per_group=4,
        max_chars_per_group=4,
    )

    challenge = generate_challenge(settings)
    groups = challenge.split(" ")

    assert len(groups) == 2
    assert all(len(group) == 4 for group in groups)
    assert all(char.isalpha() and char.isupper() for group in groups for char in group)


def test_score_text_collapses_whitespace_and_can_ignore_spaces() -> None:
    assert score_text("  ab\n  cd  ") == "AB CD"
    assert score_text("  ab\n  cd  ", keep_spaces=False) == "ABCD"


def test_completion_requires_exact_scored_text_including_internal_spaces() -> None:
    assert target_exactly_completed("AB CD", " ab   cd ") is True
    assert target_exactly_completed("AB CD", "ABCD") is False
    assert scored_target_and_input(" a b ", "A  B") == ("A B", "A B")


def test_wxmor_profile_aliases_are_normalized_safely() -> None:
    assert normalize_wxmor_profile("minimi") == "minimum"
    assert normalize_wxmor_profile("perus") == "basic"
    assert normalize_wxmor_profile("unknown-profile") == "auto"
