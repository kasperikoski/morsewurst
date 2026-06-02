# ============================================================
# morsewurst/koch/generator.py
# ============================================================

from __future__ import annotations

import random
from collections import Counter

from morsewurst.koch.models import KochSettings, normalize_koch_settings_for_active_count
from morsewurst.koch.sequence import active_chars_for_stage, koch_sequence_by_key


def _group_text(chars: list[str], *, min_group: int = 3, max_group: int = 7) -> str:
    groups: list[str] = []
    index = 0

    while index < len(chars):
        remaining = len(chars) - index
        size = random.randint(min_group, max_group)

        if remaining <= max_group:
            size = remaining

        groups.append("".join(chars[index:index + size]))
        index += size

    return " ".join(group for group in groups if group)


def _weighted_character(active_chars: str, newest_char: str) -> str:
    if len(active_chars) > 1 and random.random() < 0.30:
        return newest_char

    return random.choice(active_chars)


def _replace_duplicate_with_newest(generated: list[str], newest_char: str) -> bool:
    counts = Counter(generated)
    candidates = [
        index
        for index, char in enumerate(generated)
        if char != newest_char and counts[char] > 1
    ]

    if not candidates:
        return False

    replace_index = random.choice(candidates)
    generated[replace_index] = newest_char
    return True


def generate_koch_target(settings: KochSettings) -> str:
    """Generate a grouped Koch receive-practice target.

    The newest stage character is deliberately overweighted, because passing a
    stage should prove that the newly introduced character was really heard. In
    sufficiently long drills every active character is guaranteed to appear at
    least once, which prevents short random targets from skipping a character
    that should be part of the current stage.
    """

    settings = settings.normalized()
    sequence = koch_sequence_by_key(settings.sequence_key)
    active_chars = active_chars_for_stage(sequence, settings.stage_index)

    if not active_chars:
        active_chars = sequence.characters[:1]

    unique_active_chars = list(dict.fromkeys(active_chars))
    settings = normalize_koch_settings_for_active_count(settings, len(unique_active_chars))
    target_len = int(settings.target_chars)
    newest_char = active_chars[-1] if len(active_chars) >= 2 else active_chars[0]

    generated: list[str] = []

    if target_len >= len(unique_active_chars):
        generated.extend(unique_active_chars)

    while len(generated) < target_len:
        generated.append(_weighted_character(active_chars, newest_char))

    # Make sure the newest stage character appears often enough without removing
    # the only copy of another active character.
    min_attempts = min(settings.new_char_min_attempts, target_len)
    while generated.count(newest_char) < min_attempts:
        if not _replace_duplicate_with_newest(generated, newest_char):
            break

    random.shuffle(generated)
    return _group_text(generated).upper()
