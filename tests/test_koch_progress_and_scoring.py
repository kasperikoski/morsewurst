from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from morsewurst.koch.models import KochSettings, maximum_koch_target_chars
from morsewurst.koch.scoring import score_koch_copy
from morsewurst.storage.database import Database


def _save_result(db: Database, result) -> int:
    started_at = datetime(2026, 1, 1, 12, 0, 0)
    finished_at = started_at + timedelta(milliseconds=max(1, int(result.duration_ms)))
    return db.save_koch_session(
        started_at=started_at,
        finished_at=finished_at,
        result=result,
        typed_events=[],
        target_schedule=[],
    )


def test_koch_target_chars_are_capped_to_safe_maximum() -> None:
    maximum = maximum_koch_target_chars()

    assert maximum == 1000
    assert KochSettings(target_chars=5000).normalized().target_chars == maximum


def test_manual_koch_session_does_not_advance_guided_progress(tmp_path) -> None:
    db = Database(tmp_path / "morsewurst.sqlite3")
    settings = KochSettings(
        mode="manual",
        sequence_key="classic",
        stage_index=20,
        target_chars=30,
    ).normalized()
    result = score_koch_copy(
        target="K" * 30,
        entered="K" * 30,
        settings=settings,
        duration_ms=1000,
    )

    _save_result(db, result)
    progress = db.koch_progress("classic")

    assert progress is not None
    assert progress["guided_unlocked_stage"] == 2
    assert progress["guided_current_stage"] == 2
    assert progress["total_sessions"] == 1


def test_guided_pass_advances_guided_progress(tmp_path) -> None:
    db = Database(tmp_path / "morsewurst.sqlite3")
    settings = KochSettings(
        mode="guided",
        sequence_key="classic",
        stage_index=2,
        target_chars=30,
    ).normalized()
    result = score_koch_copy(
        target="KM" * 15,
        entered="KM" * 15,
        settings=settings,
        duration_ms=1000,
    )

    assert result.passed is True
    assert result.advanced_to_stage == 3

    _save_result(db, result)
    progress = db.koch_progress("classic")

    assert progress is not None
    assert progress["guided_unlocked_stage"] == 3
    assert progress["guided_current_stage"] == 3


def test_koch_alignment_metrics_are_stored_as_session_columns(tmp_path) -> None:
    db = Database(tmp_path / "morsewurst.sqlite3")
    settings = KochSettings(
        mode="guided",
        sequence_key="classic",
        stage_index=2,
        target_chars=30,
    ).normalized()
    result = score_koch_copy(
        target="KM" * 15,
        entered="KM" * 15,
        settings=settings,
        duration_ms=1000,
    )

    session_id = _save_result(db, result)
    row = db.recent_koch_sessions(limit=1)[0]

    assert row["id"] == session_id
    assert row["aligned_accuracy"] == result.aligned_accuracy
    assert row["time_aligned_accuracy"] == result.time_aligned_accuracy
    assert row["timing_fit"] == result.timing_fit

    char_row = db.conn.execute(
        """
        SELECT timing_weight, timing_status
        FROM koch_char_results
        WHERE koch_session_id = ?
        ORDER BY position_index ASC
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()

    assert char_row is not None
    assert char_row["timing_weight"] == 1.0
    assert char_row["timing_status"] == ""


def _set_guided_progress(db: Database, *, sequence_key: str, current_stage: int, unlocked_stage: int | None = None) -> None:
    now = datetime(2026, 1, 1, 12, 0, 0).isoformat(timespec="seconds")
    unlocked = int(unlocked_stage if unlocked_stage is not None else current_stage)
    db.ensure_koch_schema()
    db.conn.execute(
        """
        INSERT INTO koch_progress (
            sequence_key,
            guided_unlocked_stage,
            guided_current_stage,
            guided_fail_streak,
            guided_fail_stage,
            total_sessions,
            total_practice_seconds,
            updated_at
        ) VALUES (?, ?, ?, 0, NULL, 0, 0, ?)
        ON CONFLICT(sequence_key) DO UPDATE SET
            guided_unlocked_stage = excluded.guided_unlocked_stage,
            guided_current_stage = excluded.guided_current_stage,
            guided_fail_streak = 0,
            guided_fail_stage = NULL,
            updated_at = excluded.updated_at
        """,
        (sequence_key, unlocked, int(current_stage), now),
    )
    db.conn.commit()


def _insert_koch_skill_sample(
    db: Database,
    *,
    index: int,
    sequence_key: str = "classic",
    stage_index: int = 54,
    active_chars: str = "",
    target_length: int = 100,
    character_wpm: int = 20,
    effective_wpm: int = 20,
    accuracy: float = 90.0,
    cleanliness: float = 85.0,
    coverage_factor: float = 1.0,
) -> None:
    started_at = datetime(2026, 1, 1, 12, 0, 0) + timedelta(minutes=index)
    finished_at = started_at + timedelta(seconds=60)

    db.ensure_koch_schema()
    db.conn.execute(
        """
        INSERT INTO koch_sessions (
            started_at,
            finished_at,
            mode,
            sequence_key,
            stage_index,
            active_chars,
            target_text,
            entered_text,
            target_length,
            entered_length,
            character_wpm,
            effective_wpm,
            duration_ms,
            pass_accuracy,
            pass_cleanliness,
            new_char_min_attempts,
            new_char_min_accuracy,
            correct_count,
            error_count,
            substitutions,
            insertions,
            deletions,
            accuracy,
            aligned_accuracy,
            time_aligned_accuracy,
            timing_fit,
            cleanliness,
            new_char_accuracy,
            new_char_attempts,
            score,
            speed_factor,
            coverage_factor,
            level_estimate,
            pass_eligible,
            passed,
            pass_reason,
            settings_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            started_at.isoformat(timespec="seconds"),
            finished_at.isoformat(timespec="seconds"),
            "manual",
            sequence_key,
            int(stage_index),
            active_chars,
            "K" * target_length,
            "K" * target_length,
            int(target_length),
            int(target_length),
            int(character_wpm),
            int(effective_wpm),
            60_000,
            90.0,
            85.0,
            1,
            80.0,
            int(round(target_length * (accuracy / 100.0))),
            int(round(target_length * ((100.0 - accuracy) / 100.0))),
            int(round(target_length * ((100.0 - accuracy) / 100.0))),
            0,
            0,
            float(accuracy),
            float(accuracy),
            float(accuracy),
            100.0,
            float(cleanliness),
            None,
            0,
            100.0,
            1.0,
            float(coverage_factor),
            0.0,
            1,
            1,
            "passed",
            "{}",
        ),
    )
    db.conn.commit()


def test_koch_receive_skill_model_reference_level_is_about_100(tmp_path, monkeypatch) -> None:
    import morsewurst.config as config
    from morsewurst.koch.sequence import koch_sequence_by_key
    from morsewurst.koch.service import KochPracticeService

    monkeypatch.setattr(config, "DEFAULT_KOCH_SKILL_MIN_SESSIONS", 30)
    db = Database(tmp_path / "morsewurst.sqlite3")
    sequence = koch_sequence_by_key("classic")
    _set_guided_progress(db, sequence_key="classic", current_stage=len(sequence.characters))

    for index in range(30):
        _insert_koch_skill_sample(
            db,
            index=index,
            sequence_key="classic",
            stage_index=len(sequence.characters),
            active_chars=sequence.characters,
            target_length=100,
            character_wpm=20,
            effective_wpm=20,
            accuracy=90.0,
            cleanliness=85.0,
            coverage_factor=1.0,
        )

    summary = KochPracticeService(db).skill_summary()

    assert summary.displayable is True
    assert summary.sessions_used == 30
    assert summary.active_char_count == len(sequence.characters)
    assert summary.level == pytest.approx(100.0, abs=0.02)
    assert summary.raw_level == pytest.approx(100.0, abs=0.02)
    assert summary.normalizer == pytest.approx(1.19154, abs=0.00001)


def test_koch_receive_skill_model_speed_scales_without_upper_cap(tmp_path, monkeypatch) -> None:
    import morsewurst.config as config
    from morsewurst.koch.sequence import koch_sequence_by_key
    from morsewurst.koch.service import KochPracticeService

    monkeypatch.setattr(config, "DEFAULT_KOCH_SKILL_MIN_SESSIONS", 30)
    db = Database(tmp_path / "morsewurst.sqlite3")
    sequence = koch_sequence_by_key("classic")
    _set_guided_progress(db, sequence_key="classic", current_stage=len(sequence.characters))

    for index in range(30):
        _insert_koch_skill_sample(
            db,
            index=index,
            sequence_key="classic",
            stage_index=len(sequence.characters),
            active_chars=sequence.characters,
            target_length=100,
            character_wpm=40,
            effective_wpm=40,
            accuracy=90.0,
            cleanliness=85.0,
            coverage_factor=1.0,
        )

    summary = KochPracticeService(db).skill_summary()

    assert summary.displayable is True
    assert summary.speed_factor == pytest.approx(2.0)
    assert summary.level == pytest.approx(200.0, abs=0.04)


def test_koch_service_saves_receive_skill_snapshot_after_scored_session(tmp_path, monkeypatch) -> None:
    import morsewurst.config as config
    from morsewurst.koch.service import KochPracticeService

    monkeypatch.setattr(config, "DEFAULT_KOCH_SKILL_MIN_SESSIONS", 1)

    db = Database(tmp_path / "morsewurst.sqlite3")
    service = KochPracticeService(db)
    settings = KochSettings(
        mode="guided",
        sequence_key="classic",
        stage_index=2,
        target_chars=30,
        character_wpm=20,
        effective_wpm=20,
        new_char_min_attempts=1,
    )

    started_at = datetime(2026, 1, 1, 12, 0, 0)
    session_id, result = service.score_session(
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=30),
        target="KM" * 15,
        entered="KM" * 15,
        settings=settings,
        typed_events=[],
        target_schedule=[],
    )

    assert result.passed is True

    snapshots = db.recent_koch_skill_snapshots(limit=1)
    assert len(snapshots) == 1
    assert snapshots[0]["koch_session_id"] == session_id
    assert snapshots[0]["sessions_used"] == 1
    assert snapshots[0]["displayable"] == 1
    assert snapshots[0]["display_level"] is not None


def test_guided_failure_streak_demotes_and_records_progress_snapshot(tmp_path) -> None:
    db = Database(tmp_path / "morsewurst.sqlite3")
    settings = KochSettings(
        mode="guided",
        sequence_key="classic",
        stage_index=4,
        target_chars=30,
        new_char_min_attempts=1,
    ).normalized()

    _set_guided_progress(db, sequence_key="classic", current_stage=4, unlocked_stage=8)

    for _index in range(5):
        result = score_koch_copy(
            target="KMRS" * 8,
            entered="",
            settings=settings,
            duration_ms=1000,
        )
        _save_result(db, result)

    progress = db.koch_progress("classic")
    assert progress is not None
    assert progress["guided_current_stage"] == 3
    assert progress["guided_unlocked_stage"] == 8
    assert progress["guided_fail_streak"] == 0

    latest_snapshot = db.conn.execute(
        """
        SELECT *
        FROM koch_progress_snapshots
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    assert latest_snapshot is not None
    assert latest_snapshot["stage_before"] == 4
    assert latest_snapshot["stage_after"] == 3
    assert latest_snapshot["unlocked_before"] == 8
    assert latest_snapshot["unlocked_after"] == 8
    assert latest_snapshot["guided_fail_streak_before"] == 4
    assert latest_snapshot["guided_fail_streak_after"] == 0
    assert latest_snapshot["demoted_from_stage"] == 4
    assert latest_snapshot["demoted_to_stage"] == 3
    assert latest_snapshot["demotion_reason"] == "guided_failure_streak"
