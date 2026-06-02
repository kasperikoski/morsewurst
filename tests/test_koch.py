from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from morsewurst.koch.models import KochSettings
from morsewurst.koch.scoring import score_koch_copy
from morsewurst.koch.sequence import koch_sequence_by_key
from morsewurst.storage.database import Database


def test_koch_score_uses_edit_distance_not_bag_of_characters() -> None:
    settings = KochSettings(
        mode="manual",
        sequence_key="classic",
        stage_index=2,
        target_chars=4,
        effective_wpm=20,
        new_char_min_attempts=1,
    )

    result = score_koch_copy(
        target="KMKM",
        entered="KKKK",
        settings=settings,
        duration_ms=10_000,
    )

    assert result.correct_count == 2
    assert result.substitutions == 2
    assert result.accuracy == pytest.approx(50.0)
    assert result.passed is False



def test_koch_score_handles_extra_typed_characters_without_crashing() -> None:
    settings = KochSettings(
        mode="manual",
        sequence_key="classic",
        stage_index=2,
        target_chars=2,
        effective_wpm=20,
        new_char_min_attempts=1,
    )

    result = score_koch_copy(
        target="KM",
        entered="KMM",
        settings=settings,
        duration_ms=10_000,
    )

    assert result.correct_count == 2
    assert result.insertions == 1
    assert result.error_count == 1
    assert any(char.result == "insertion" for char in result.character_results)

def test_koch_full_set_perfect_copy_at_20_wpm_is_level_50() -> None:
    sequence = koch_sequence_by_key("morsewurst")
    settings = KochSettings(
        mode="manual",
        sequence_key="morsewurst",
        stage_index=len(sequence.characters),
        target_chars=len(sequence.characters),
        character_wpm=20,
        effective_wpm=20,
        new_char_min_attempts=1,
    )

    result = score_koch_copy(
        target=sequence.characters,
        entered=sequence.characters,
        settings=settings,
        duration_ms=120_000,
    )

    assert result.accuracy == pytest.approx(100.0)
    assert result.coverage_factor == pytest.approx(1.0)
    assert result.level_estimate == pytest.approx(50.0)


def test_koch_full_set_perfect_copy_at_40_wpm_is_level_100() -> None:
    sequence = koch_sequence_by_key("morsewurst")
    settings = KochSettings(
        mode="manual",
        sequence_key="morsewurst",
        stage_index=len(sequence.characters),
        target_chars=len(sequence.characters),
        character_wpm=40,
        effective_wpm=40,
        new_char_min_attempts=1,
    )

    result = score_koch_copy(
        target=sequence.characters,
        entered=sequence.characters,
        settings=settings,
        duration_ms=120_000,
    )

    assert result.level_estimate == pytest.approx(100.0)


def test_koch_schema_is_additive_and_saves_session(tmp_path: Path) -> None:
    db = Database(tmp_path / "morsewurst.sqlite3")
    db.ensure_koch_schema()

    settings = KochSettings(
        mode="guided",
        sequence_key="classic",
        stage_index=2,
        target_chars=4,
        effective_wpm=20,
        new_char_min_attempts=1,
    )
    result = score_koch_copy(
        target="KMKM",
        entered="KMKM",
        settings=settings,
        duration_ms=10_000,
    )

    session_id = db.save_koch_session(
        started_at=datetime.now() - timedelta(seconds=10),
        finished_at=datetime.now(),
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

    progress = db.koch_progress("classic")
    assert progress is not None
    assert progress["last_session_id"] == session_id
