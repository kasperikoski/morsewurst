from __future__ import annotations

import importlib
import io
import random
import wave
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import morsewurst.config as config
import morsewurst.koch.models as koch_models
from morsewurst.koch.generator import generate_koch_target
from morsewurst.koch.models import KochSettings, minimum_koch_target_chars
from morsewurst.koch.schedule import koch_timing_ms, make_koch_target_schedule, schedule_duration_ms
from morsewurst.koch.scoring import score_koch_copy
from morsewurst.koch.sequence import active_chars_for_stage, koch_sequence_by_key
from morsewurst.koch.service import KochPracticeService
from morsewurst.koch.tone_renderer import render_koch_wave_bytes
from morsewurst.storage.database import Database


def _score_settings(**overrides: Any) -> KochSettings:
    data: dict[str, Any] = {
        "mode": "manual",
        "sequence_key": "classic",
        "stage_index": 2,
        "target_chars": 30,
        "character_wpm": 20,
        "effective_wpm": 20,
        "pass_accuracy": 90.0,
        "pass_cleanliness": 85.0,
        "new_char_min_attempts": 1,
        "new_char_min_accuracy": 80.0,
    }
    data.update(overrides)
    return KochSettings(**data)


def _copy_text(target: str) -> str:
    return "".join(str(target or "").upper().split())


class _ProgressOnlyDb:
    def __init__(self, progress: dict[str, Any] | None = None) -> None:
        self.progress = progress
        self.ensure_schema_called = False

    def ensure_koch_schema(self) -> None:
        self.ensure_schema_called = True

    def koch_progress(self, _sequence_key: str) -> dict[str, Any] | None:
        return self.progress

    def recent_koch_sessions(self, limit: int = 1000) -> list[Any]:
        return []

    def koch_character_stats(self, recent_sessions: int = 1000, limit: int = 50) -> list[Any]:
        return []


def test_koch_accuracy_is_copy_accuracy_and_timing_metrics_are_diagnostics() -> None:
    settings = _score_settings(
        target_chars=2,
        pass_accuracy=100.0,
        pass_cleanliness=100.0,
    )
    target = "KM"
    target_schedule = [
        {"char": "K", "start_ms": 0, "end_ms": 300},
        {"char": "M", "start_ms": 500, "end_ms": 800},
    ]
    typed_events = [
        {"key": "K", "char": "K", "typed_at_ms": 8_300},
        {"key": "M", "char": "M", "typed_at_ms": 8_800},
    ]

    result = score_koch_copy(
        target=target,
        entered=target,
        settings=settings,
        duration_ms=12_000,
        typed_events=typed_events,
        target_schedule=target_schedule,
    )

    assert result.aligned_accuracy == pytest.approx(100.0)
    assert result.accuracy == pytest.approx(result.aligned_accuracy)
    assert result.time_aligned_accuracy < result.aligned_accuracy
    assert result.timing_fit < 100.0
    assert result.passed is True
    assert result.pass_reason == "passed"
    assert all(char.typed_at_ms is not None for char in result.character_results)
    assert all(char.timing_status == "recovered_late" for char in result.character_results)


def test_koch_scoring_keeps_keypress_timing_on_character_results() -> None:
    schedule = [
        {"char": "K", "start_ms": 100, "end_ms": 600},
        {"char": "M", "start_ms": 900, "end_ms": 1300},
    ]
    typed_events = [
        {"key": "K", "char": "K", "typed_at_ms": 700},
        {"key": "M", "char": "M", "typed_at_ms": 1500},
    ]

    result = score_koch_copy(
        target="KM",
        entered="KM",
        settings=_score_settings(target_chars=2),
        duration_ms=5_000,
        typed_events=typed_events,
        target_schedule=schedule,
    )

    assert [(char.target_char, char.entered_char) for char in result.character_results] == [("K", "K"), ("M", "M")]
    assert [char.expected_start_ms for char in result.character_results] == [100, 900]
    assert [char.expected_end_ms for char in result.character_results] == [600, 1300]
    assert [char.typed_at_ms for char in result.character_results] == [700, 1500]
    assert [char.latency_ms for char in result.character_results] == [100, 200]


def test_koch_pass_requires_new_stage_character_evidence() -> None:
    settings = _score_settings(
        target_chars=8,
        new_char_min_attempts=3,
    )

    result = score_koch_copy(
        target="KKKKKKKK",
        entered="KKKKKKKK",
        settings=settings,
        duration_ms=10_000,
    )

    assert result.accuracy == pytest.approx(100.0)
    assert result.cleanliness == pytest.approx(100.0)
    assert result.new_char_attempts == 0
    assert result.passed is False
    assert result.pass_reason == "not_enough_new_char_evidence"


def test_koch_pass_no_longer_depends_on_length_or_duration_gate() -> None:
    short_fast_result = score_koch_copy(
        target="KM",
        entered="KM",
        settings=_score_settings(
            target_chars=30,
            pass_accuracy=100.0,
            pass_cleanliness=100.0,
        ),
        duration_ms=1,
    )

    assert short_fast_result.pass_eligible is True
    assert short_fast_result.passed is True
    assert short_fast_result.pass_reason == "passed"


def test_minimum_koch_target_chars_uses_absolute_floor_and_active_factor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(koch_models.config, "DEFAULT_KOCH_MIN_TARGET_CHARS_ABSOLUTE", 30, raising=False)
    monkeypatch.setattr(koch_models.config, "DEFAULT_KOCH_MIN_TARGET_CHARS_ACTIVE_FACTOR", 1.50, raising=False)

    assert minimum_koch_target_chars(0) == 30
    assert minimum_koch_target_chars(10) == 30
    assert minimum_koch_target_chars(30) == 45
    assert minimum_koch_target_chars(54) == 81


def test_koch_settings_normalized_enforces_absolute_target_floor() -> None:
    settings = KochSettings(target_chars=1, character_wpm=120, effective_wpm=120)

    normalized = settings.normalized()

    assert normalized.target_chars >= 30
    assert normalized.character_wpm == 80
    assert normalized.effective_wpm == 80


def test_koch_service_enforces_dynamic_target_minimum_for_selected_stage() -> None:
    service = KochPracticeService(_ProgressOnlyDb())
    sequence = koch_sequence_by_key("morsewurst")
    stage_index = min(len(sequence.characters), 40)
    settings = KochSettings(
        mode="manual",
        sequence_key=sequence.key,
        stage_index=stage_index,
        target_chars=1,
    )

    minimum = service.minimum_target_chars_for_settings(settings)
    normalized = service.settings_with_target_minimum(settings)

    active_count = len(set(active_chars_for_stage(sequence, stage_index)))
    assert minimum == minimum_koch_target_chars(active_count)
    assert normalized.target_chars == minimum
    assert normalized.target_chars >= active_count


def test_koch_service_guided_progress_updates_stage_before_target_minimum() -> None:
    progress = {
        "sequence_key": "morsewurst",
        "guided_unlocked_stage": 12,
        "guided_current_stage": 12,
        "total_sessions": 4,
        "total_practice_seconds": 300,
        "last_session_id": 99,
    }
    service = KochPracticeService(_ProgressOnlyDb(progress=progress))
    settings = KochSettings(
        mode="guided",
        sequence_key="morsewurst",
        stage_index=2,
        target_chars=1,
    )

    normalized = service.settings_with_progress(settings)
    minimum = service.minimum_target_chars_for_settings(normalized)

    assert normalized.stage_index == 12
    assert normalized.target_chars == minimum


def test_koch_generator_includes_every_active_character_when_target_is_long_enough() -> None:
    random.seed(20260601)
    sequence = koch_sequence_by_key("morsewurst")
    stage_index = min(len(sequence.characters), 40)
    settings = KochSettings(
        mode="manual",
        sequence_key=sequence.key,
        stage_index=stage_index,
        target_chars=1,
        new_char_min_attempts=8,
    )
    active_chars = list(dict.fromkeys(active_chars_for_stage(sequence, stage_index)))
    newest_char = active_chars[-1]

    target = generate_koch_target(settings)
    copied = _copy_text(target)

    assert len(copied) >= minimum_koch_target_chars(len(active_chars))
    assert set(active_chars).issubset(set(copied))
    assert copied.count(newest_char) >= 8
    assert all(group.isupper() for group in target.split())


def test_koch_generator_preserves_all_active_characters_when_boosting_newest_character() -> None:
    random.seed(12345)
    settings = KochSettings(
        mode="manual",
        sequence_key="classic",
        stage_index=6,
        target_chars=30,
        new_char_min_attempts=20,
    )
    sequence = koch_sequence_by_key(settings.sequence_key)
    active_chars = list(dict.fromkeys(active_chars_for_stage(sequence, settings.stage_index)))
    newest_char = active_chars[-1]

    copied = _copy_text(generate_koch_target(settings))

    assert set(active_chars).issubset(set(copied))
    assert copied.count(newest_char) >= 20


def test_koch_timing_keeps_character_speed_but_stretches_spacing_at_lower_effective_wpm() -> None:
    normal = koch_timing_ms(KochSettings(character_wpm=20, effective_wpm=20))
    farnsworth = koch_timing_ms(KochSettings(character_wpm=20, effective_wpm=10))

    assert farnsworth["element_unit_ms"] == pytest.approx(normal["element_unit_ms"])
    assert farnsworth["element_gap_ms"] == pytest.approx(normal["element_gap_ms"])
    assert farnsworth["char_gap_ms"] == pytest.approx(normal["char_gap_ms"] * 2.0)
    assert farnsworth["word_gap_ms"] == pytest.approx(normal["word_gap_ms"] * 2.0)


def test_koch_target_schedule_matches_scored_text_and_word_gap_is_longer_than_letter_gap() -> None:
    settings = KochSettings(character_wpm=20, effective_wpm=10)
    letter_schedule = make_koch_target_schedule("ET", settings)
    word_schedule = make_koch_target_schedule("E T", settings)
    timing = koch_timing_ms(settings)

    assert [item["char"] for item in word_schedule] == ["E", "T"]
    assert schedule_duration_ms(word_schedule) == word_schedule[-1]["end_ms"]

    letter_gap = int(letter_schedule[1]["start_ms"]) - int(letter_schedule[0]["end_ms"])
    word_gap = int(word_schedule[1]["start_ms"]) - int(word_schedule[0]["end_ms"])

    assert letter_gap == pytest.approx(timing["char_gap_ms"], abs=1)
    assert word_gap == pytest.approx(timing["word_gap_ms"], abs=1)
    assert word_gap > letter_gap


def test_koch_wave_renderer_returns_valid_mono_pcm_wav_bytes() -> None:
    data = render_koch_wave_bytes(
        "ET",
        KochSettings(character_wpm=20, effective_wpm=20, tone_hz=600, volume_percent=20),
    )

    with wave.open(io.BytesIO(data), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == config.DEFAULT_KOCH_AUDIO_SAMPLE_RATE
        assert wav.getnframes() > 0


def test_koch_session_persistence_saves_schedule_key_events_and_progress(tmp_path: Path) -> None:
    db = Database(tmp_path / "morsewurst.sqlite3")
    now = datetime.now()
    result = score_koch_copy(
        target="KMKM",
        entered="KMKM",
        settings=_score_settings(mode="guided", target_chars=4),
        duration_ms=10_000,
    )

    session_id = db.save_koch_session(
        started_at=now - timedelta(seconds=10),
        finished_at=now,
        result=result,
        typed_events=[
            {"key": "K", "char": "K", "typed_at_ms": 500},
            {"key": "M", "char": "M", "typed_at_ms": 900},
        ],
        target_schedule=[
            {"char": "K", "start_ms": 0, "end_ms": 300},
            {"char": "M", "start_ms": 700, "end_ms": 1000},
        ],
    )

    rows = db.recent_koch_sessions(limit=5)
    assert rows[0]["id"] == session_id
    assert rows[0]["passed"] == 1
    assert "K" in rows[0]["target_schedule_json"]

    key_rows = db.conn.execute(
        "SELECT key, char, typed_at_ms FROM koch_key_events WHERE koch_session_id = ? ORDER BY event_index",
        (session_id,),
    ).fetchall()
    assert [(row["key"], row["char"], row["typed_at_ms"]) for row in key_rows] == [
        ("K", "K", 500),
        ("M", "M", 900),
    ]

    progress = db.koch_progress("classic")
    assert progress is not None
    assert progress["last_session_id"] == session_id


def test_koch_character_stats_orders_problem_characters_by_error_rate(tmp_path: Path) -> None:
    db = Database(tmp_path / "morsewurst.sqlite3")
    now = datetime.now()

    result = score_koch_copy(
        target="KMMK",
        entered="KKKK",
        settings=_score_settings(target_chars=4),
        duration_ms=10_000,
        typed_events=[
            {"key": "K", "char": "K", "typed_at_ms": 500},
            {"key": "K", "char": "K", "typed_at_ms": 900},
            {"key": "K", "char": "K", "typed_at_ms": 1300},
            {"key": "K", "char": "K", "typed_at_ms": 1700},
        ],
        target_schedule=[
            {"char": "K", "start_ms": 0, "end_ms": 300},
            {"char": "M", "start_ms": 700, "end_ms": 1000},
            {"char": "M", "start_ms": 1200, "end_ms": 1500},
            {"char": "K", "start_ms": 1700, "end_ms": 2000},
        ],
    )
    session_id = db.save_koch_session(
        started_at=now - timedelta(seconds=10),
        finished_at=now,
        result=result,
        typed_events=[],
        target_schedule=[],
    )

    rows = db.koch_character_stats(recent_sessions=5, limit=5)
    by_char = {row["char"]: row for row in rows}

    assert session_id > 0
    assert by_char["M"]["attempts"] == 2
    assert by_char["M"]["errors"] == 2
    assert by_char["M"]["error_rate"] == pytest.approx(100.0)
    assert by_char["K"]["attempts"] == 2
    assert by_char["K"]["correct"] == 2


def test_koch_ui_views_import_without_creating_windows() -> None:
    modules = [
        "morsewurst.ui.koch.window",
        "morsewurst.ui.koch.views.actions_view",
        "morsewurst.ui.koch.views.characters_view",
        "morsewurst.ui.koch.views.comparison_view",
        "morsewurst.ui.koch.views.history_view",
        "morsewurst.ui.koch.views.input_view",
        "morsewurst.ui.koch.views.result_view",
        "morsewurst.ui.koch.views.settings_view",
        "morsewurst.ui.koch.views.skill_view",
    ]

    imported = [importlib.import_module(module_name) for module_name in modules]

    assert all(module is not None for module in imported)
