# ============================================================
# morsewurst/models.py
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ChallengeSettings:
    use_letters: bool = True
    use_numbers: bool = True
    use_punctuation: bool = False
    character_mix_letters_percent: int = 70
    character_mix_numbers_percent: int = 25
    character_mix_punctuation_percent: int = 5
    min_groups: int = 1
    max_groups: int = 1
    min_chars_per_group: int = 3
    max_chars_per_group: int = 7
    target_wpm: int = 20
    practice_problem_chars: bool = False
    practice_rounds: int = 5
    countdown_seconds: int = 0
    sound_enabled: bool = True
    problem_recent_rounds: int = 50
    problem_char_weight_percent: int = 30
    problem_char_limit: int = 12
    auto_optimize_recent_rounds: int = 1000
    auto_optimize_min_accuracy: int = 90


@dataclass
class RoundState:
    target: str = ""
    started_at: Optional[datetime] = None
    host_start_time: Optional[float] = None
    device_start_us: Optional[int] = None
    finished_at: Optional[datetime] = None
    host_finished_time: Optional[float] = None
    accepting_input: bool = False
    active: bool = False
    finished: bool = False
    finish_reason: str = ""
    hid_text: str = ""
    telemetry_text: str = ""
    events: List[Dict[str, Any]] = field(default_factory=list)
    round_number: int = 0
    total_rounds: int = 0


@dataclass
class CharacterResult:
    position_index: int
    target_char: Optional[str]
    entered_char: Optional[str]
    result: str
    entered_code: Optional[str] = None
    source: Optional[str] = None
    char_time_us: Optional[int] = None
    first_element_us: Optional[int] = None
    last_element_us: Optional[int] = None
    gap_before_us: Optional[int] = None
    dit_us: Optional[float] = None
    wpm: Optional[float] = None

    element_unit_us: Optional[float] = None
    gap_unit_us: Optional[float] = None
    gap_before_units: Optional[float] = None
    gap_kind: Optional[str] = None


@dataclass
class ScoreSummary:
    target: str
    entered: str
    source: str

    # Main learning metrics.
    accuracy: float
    cleanliness: float
    overall_score: float
    speed_score: Optional[float]
    timing_score: Optional[float]

    # Edit-distance result.
    correct_count: int
    error_count: int
    substitutions: int
    insertions: int
    deletions: int
    length_target: int
    length_entered: int

    # Timing and speed.
    elapsed_us: Optional[int]
    standard_time_us: Optional[int]
    time_ok: Optional[bool]
    avg_wpm: Optional[float]
    gross_wpm: Optional[float]
    net_wpm: Optional[float]
    avg_dit_us: Optional[float]
    dit_sd_us: Optional[float]

    straight_dot_us: Optional[float]
    straight_dot_sd_us: Optional[float]

    straight_dash_us: Optional[float]
    straight_dash_sd_us: Optional[float]

    straight_dash_dot_ratio: Optional[float]

    avg_letter_gap_us: Optional[float]
    letter_gap_sd_us: Optional[float]

    avg_word_gap_us: Optional[float]
    word_gap_sd_us: Optional[float]

    # Round-level timing quality components.
    timing_element_score: Optional[float]
    timing_gap_score: Optional[float]
    timing_ratio_score: Optional[float]
    timing_dot_consistency: Optional[float]
    timing_dash_consistency: Optional[float]
    timing_intra_gap_score: Optional[float]
    timing_letter_gap_score: Optional[float]
    timing_word_gap_score: Optional[float]

    finish_reason: str

    profile_eligible: bool = True
    profile_reject_reason: Optional[str] = None
    profile_max_element_units: Optional[float] = None
    profile_max_gap_units: Optional[float] = None
