# ============================================================
# morsewurst/core/progression.py
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Optional


LEVELS_PER_SKILL_WPM = 2.5


@dataclass(frozen=True)
class ProgressionResult:
    raw_skill: Optional[float]
    level: int
    level_progress: float
    title: str


def title_for_level(level: int) -> str:
    if level <= 0:
        return "Ei vielä tasoa"

    if level < 5:
        return "Ensiaskeleet"

    if level < 10:
        return "Aloittelija"

    if level < 15:
        return "Harjoittelija"

    if level < 25:
        return "Perustaso"

    if level < 35:
        return "Kehittyvä operaattori"

    if level < 50:
        return "Taitava operaattori"

    if level < 75:
        return "Edistynyt operaattori"

    if level < 100:
        return "Kokenut operaattori"

    if level < 125:
        return "Nopea operaattori"

    return "Huipputason operaattori"


def progression_from_raw_skill(raw_skill: Optional[float]) -> ProgressionResult:
    if raw_skill is None or raw_skill <= 0:
        return ProgressionResult(
            raw_skill=raw_skill,
            level=0,
            level_progress=0.0,
            title=title_for_level(0),
        )

    level_float = float(raw_skill) * LEVELS_PER_SKILL_WPM
    level = max(1, int(floor(level_float)))
    level_progress = max(0.0, min(1.0, level_float - level))

    return ProgressionResult(
        raw_skill=float(raw_skill),
        level=level,
        level_progress=level_progress,
        title=title_for_level(level),
    )