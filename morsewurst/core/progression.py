# ============================================================
# morsewurst/core/progression.py
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Optional


LEVELS_PER_SKILL_WPM = 2.5


PROGRESSION_TITLES: tuple[tuple[int | None, str, str], ...] = (
    (0, "progression.title.no_level", "No level yet"),
    (5, "progression.title.first_steps", "First steps"),
    (10, "progression.title.beginner", "Beginner"),
    (15, "progression.title.trainee", "Trainee"),
    (25, "progression.title.basic", "Basic level"),
    (35, "progression.title.developing_operator", "Developing operator"),
    (50, "progression.title.skilled_operator", "Skilled operator"),
    (75, "progression.title.advanced_operator", "Advanced operator"),
    (100, "progression.title.experienced_operator", "Experienced operator"),
    (125, "progression.title.fast_operator", "Fast operator"),
    (None, "progression.title.elite_operator", "Elite operator"),
)


@dataclass(frozen=True)
class ProgressionResult:
    raw_skill: Optional[float]
    level: int
    level_progress: float
    title: str
    title_key: str


def progression_title_data_for_level(level: int) -> tuple[str, str]:
    if level <= 0:
        return "progression.title.no_level", "No level yet"

    for upper_limit, title_key, fallback_title in PROGRESSION_TITLES:
        if upper_limit is None or level < upper_limit:
            return title_key, fallback_title

    return "progression.title.elite_operator", "Elite operator"


def title_key_for_level(level: int) -> str:
    title_key, _fallback_title = progression_title_data_for_level(level)
    return title_key


def title_for_level(level: int) -> str:
    _title_key, fallback_title = progression_title_data_for_level(level)
    return fallback_title


def progression_from_raw_skill(raw_skill: Optional[float]) -> ProgressionResult:
    if raw_skill is None or raw_skill <= 0:
        level = 0
        title_key, fallback_title = progression_title_data_for_level(level)

        return ProgressionResult(
            raw_skill=raw_skill,
            level=level,
            level_progress=0.0,
            title=fallback_title,
            title_key=title_key,
        )

    level_float = float(raw_skill) * LEVELS_PER_SKILL_WPM
    level = max(1, int(floor(level_float)))
    level_progress = max(0.0, min(1.0, level_float - level))
    title_key, fallback_title = progression_title_data_for_level(level)

    return ProgressionResult(
        raw_skill=float(raw_skill),
        level=level,
        level_progress=level_progress,
        title=fallback_title,
        title_key=title_key,
    )