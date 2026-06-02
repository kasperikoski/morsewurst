# ============================================================
# morsewurst/koch/models.py
# ============================================================

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import morsewurst.config as config


def minimum_koch_target_chars(active_count: int) -> int:
    """Return the minimum useful Koch drill length for an active character set.

    Short drills are noisy: a learner can pass or fail because a few characters
    happened not to appear. The floor is always at least 30 copied characters.
    For larger active sets the floor grows to about 120% of the active character
    count, rounded up, so each active character can appear at least once with a
    little room for repeats.
    """

    absolute_minimum = max(1, int(getattr(config, "DEFAULT_KOCH_MIN_TARGET_CHARS_ABSOLUTE", 30)))
    active_total = max(0, int(active_count))
    active_factor = max(
        1.0,
        float(getattr(config, "DEFAULT_KOCH_MIN_TARGET_CHARS_ACTIVE_FACTOR", 1.50)),
    )
    active_minimum = int(math.ceil(float(active_total) * active_factor))

    return max(absolute_minimum, active_minimum)


def maximum_koch_target_chars() -> int:
    """Return the hard maximum generated Koch drill length.

    Koch scoring uses a rich text/time alignment. A cap keeps UI input, audio
    rendering and scoring predictable while still allowing substantially longer
    drills than the default 200 copied characters.
    """

    minimum = minimum_koch_target_chars(0)
    raw_maximum = getattr(config, "DEFAULT_KOCH_MAX_TARGET_CHARS", 1000)
    try:
        maximum = int(raw_maximum)
    except (TypeError, ValueError):
        maximum = 1000

    return max(minimum, maximum)


def normalize_koch_settings_for_active_count(
    settings: "KochSettings",
    active_count: int,
) -> "KochSettings":
    """Normalize settings and enforce the active-character target length floor.

    ``KochSettings.normalized()`` can only enforce the absolute floor because the
    dataclass does not know which sequence/stage is active. Call this helper
    after resolving the active character set whenever a real drill is created,
    scored, or displayed.
    """

    normalized = settings.normalized()
    minimum = minimum_koch_target_chars(active_count)
    maximum = maximum_koch_target_chars()
    target_chars = max(minimum, min(maximum, int(normalized.target_chars)))

    if normalized.target_chars == target_chars:
        return normalized

    return KochSettings(
        **{
            **asdict(normalized),
            "target_chars": target_chars,
        }
    ).normalized()


@dataclass
class KochSettings:
    mode: str = "guided"
    sequence_key: str = "classic"
    stage_index: int = 2
    target_chars: int = 200
    character_wpm: int = 20
    effective_wpm: int = 15
    tone_hz: int = 600
    volume_percent: int = 70
    pass_accuracy: float = 90.0
    pass_cleanliness: float = 85.0
    new_char_min_attempts: int = 8
    new_char_min_accuracy: float = 80.0
    auto_score_delay_ms: int = 1500

    def normalized(self) -> "KochSettings":
        stage_index = max(1, int(self.stage_index))
        character_wpm = max(5, min(80, int(self.character_wpm)))
        effective_wpm = max(5, min(80, int(self.effective_wpm)))
        effective_wpm = min(effective_wpm, character_wpm)

        return KochSettings(
            mode=str(self.mode or "guided").strip().lower(),
            sequence_key=str(self.sequence_key or "classic").strip().lower(),
            stage_index=stage_index,
            target_chars=max(
                minimum_koch_target_chars(0),
                min(maximum_koch_target_chars(), int(self.target_chars)),
            ),
            character_wpm=character_wpm,
            effective_wpm=effective_wpm,
            tone_hz=max(100, min(2000, int(self.tone_hz))),
            volume_percent=max(0, min(100, int(self.volume_percent))),
            pass_accuracy=max(0.0, min(100.0, float(self.pass_accuracy))),
            pass_cleanliness=max(0.0, min(100.0, float(self.pass_cleanliness))),
            new_char_min_attempts=max(1, int(self.new_char_min_attempts)),
            new_char_min_accuracy=max(0.0, min(100.0, float(self.new_char_min_accuracy))),
            auto_score_delay_ms=max(0, min(10_000, int(self.auto_score_delay_ms))),
        )


@dataclass
class KochCharacterResult:
    position_index: int
    target_char: str | None
    entered_char: str | None
    result: str
    target_stage_index: int | None = None
    is_new_stage_char: bool = False
    expected_start_ms: int | None = None
    expected_end_ms: int | None = None
    typed_at_ms: int | None = None
    latency_ms: int | None = None
    timing_weight: float = 1.0
    timing_status: str = ""


@dataclass
class KochSessionResult:
    target: str
    entered: str
    active_chars: str
    new_stage_char: str | None
    sequence_key: str
    stage_index: int
    mode: str

    correct_count: int
    error_count: int
    substitutions: int
    insertions: int
    deletions: int
    length_target: int
    length_entered: int

    accuracy: float
    aligned_accuracy: float
    time_aligned_accuracy: float
    timing_fit: float
    cleanliness: float
    new_char_accuracy: float | None
    new_char_attempts: int

    character_wpm: int
    effective_wpm: int
    speed_factor: float
    coverage_factor: float
    score: float
    level_estimate: float

    duration_ms: int
    pass_eligible: bool
    passed: bool
    advanced_from_stage: int | None = None
    advanced_to_stage: int | None = None
    demoted_from_stage: int | None = None
    demoted_to_stage: int | None = None
    demotion_reason: str = ""
    guided_fail_streak_after: int = 0
    pass_reason: str = ""
    settings_json: dict[str, Any] = field(default_factory=dict)
    character_results: list[KochCharacterResult] = field(default_factory=list)


@dataclass
class KochProgress:
    sequence_key: str
    guided_unlocked_stage: int
    guided_current_stage: int
    guided_fail_streak: int = 0
    guided_fail_stage: int | None = None
    last_demoted_from_stage: int | None = None
    last_demoted_to_stage: int | None = None
    last_demoted_at: str | None = None
    total_sessions: int = 0
    total_practice_seconds: int = 0
    last_session_id: int | None = None


@dataclass
class KochSkillSummary:
    """Rolling Koch receive-skill summary.

    This is intentionally separate from normal send-practice skill rating. It
    describes the user's current Koch receive ability using the current guided
    character coverage and rolling Koch receive-practice averages.
    """

    level: float = 0.0
    title_key: str = "koch.skill.title.no_level"
    title_default: str = "No copy level yet"
    confidence: float = 0.0
    sessions_used: int = 0
    total_sessions: int = 0
    required_sessions: int = 30
    displayable: bool = False

    # Main displayed rolling metrics.
    average_accuracy: float = 0.0
    average_cleanliness: float = 0.0
    average_character_wpm: float = 0.0
    average_effective_wpm: float = 0.0
    average_target_length: float = 0.0

    # Compatibility fields for existing views/statistics that still use these
    # names. They now hold rounded rolling averages rather than "best" values.
    best_effective_wpm: int = 0
    best_character_wpm: int = 0
    best_level: float = 0.0
    full_charset_passes: int = 0

    # Model factors saved to snapshots for future graphs and tuning.
    active_char_count: int = 0
    total_character_count: int = 0
    base_sequence_key: str = ""
    classic_active_count: int = 0
    lcwo_active_count: int = 0
    base_level: float = 0.0
    speed_factor: float = 0.0
    accuracy_factor: float = 0.0
    cleanliness_factor: float = 0.0
    length_factor: float = 0.0
    normalizer: float = 0.0
    raw_level: float = 0.0