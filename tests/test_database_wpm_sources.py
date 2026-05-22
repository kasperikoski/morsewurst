from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from morsewurst.core.scoring import estimate_paris_time_us
from morsewurst.core.skill_rating import calculate_skill_rating
from morsewurst.storage.database import Database


TARGET = "PARISPARISPARIS"


def _new_db(tmp_path: Path) -> Database:
    return Database(tmp_path / "morsewurst_test.sqlite3")


def _settings_json(*, target_wpm: float = 20.0) -> str:
    return json.dumps(
        {
            "use_letters": True,
            "use_numbers": True,
            "use_punctuation": False,
            "target_wpm": target_wpm,
        },
        ensure_ascii=False,
    )


def _actual_elapsed_us(target: str, wpm: float) -> int:
    elapsed = estimate_paris_time_us(target, wpm)

    assert elapsed is not None
    assert elapsed > 0

    return int(elapsed)


def _insert_round(
    db: Database,
    *,
    finished_at: datetime,
    target: str = TARGET,
    entered: str | None = None,
    actual_wpm: float = 20.0,
    target_wpm: float = 20.0,
    accuracy: float = 100.0,
    cleanliness: float = 100.0,
    source_counts: dict[str, int] | None = None,
    char_result: str = "correct",
    elapsed_us: int | None = None,
    length_target: int | None = None,
) -> int:
    """Insert one lightweight session directly into the database.

    The tests intentionally insert rows directly so the database query methods
    can be tested without depending on UI or scoring-controller code paths.
    """

    target = str(target)
    entered = target if entered is None else str(entered)
    length_target = len(target.replace(" ", "")) if length_target is None else int(length_target)

    if elapsed_us is None:
        elapsed_us = _actual_elapsed_us(target, actual_wpm)

    started_at = finished_at - timedelta(seconds=1)

    cur = db.conn.cursor()
    cur.execute(
        """
        INSERT INTO sessions (
            started_at,
            finished_at,
            target,
            entered,
            source,
            finish_reason,

            accuracy,
            cleanliness,
            overall_score,
            speed_score,
            timing_score,

            correct_count,
            error_count,
            substitutions,
            insertions,
            deletions,
            length_target,
            length_entered,

            elapsed_us,
            standard_time_us,
            time_ok,

            avg_wpm,
            gross_wpm,
            net_wpm,

            settings_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            started_at.isoformat(timespec="seconds"),
            finished_at.isoformat(timespec="seconds"),
            target,
            entered,
            "adaptive_telemetry",
            "completed",

            float(accuracy),
            float(cleanliness),
            100.0,
            None,
            None,

            length_target,
            0,
            0,
            0,
            0,
            length_target,
            len(entered.replace(" ", "")),

            elapsed_us,
            None,
            None,

            None,
            float(actual_wpm),
            float(actual_wpm),

            _settings_json(target_wpm=target_wpm),
        ),
    )

    lastrowid = cur.lastrowid

    if lastrowid is None:
        raise RuntimeError("Test session insert failed: SQLite did not return lastrowid.")

    session_id = int(lastrowid)

    if source_counts is None:
        source_counts = {"straight": length_target}

    position = 0

    for source, count in source_counts.items():
        for _ in range(int(count)):
            cur.execute(
                """
                INSERT INTO char_results (
                    session_id,
                    position_index,
                    target_char,
                    entered_char,
                    result,
                    entered_code,
                    source
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    position,
                    "A",
                    "A",
                    char_result,
                    ".-",
                    source,
                ),
            )
            position += 1

    db.conn.commit()
    return session_id


def _insert_char_result(
    db: Database,
    *,
    session_id: int,
    position_index: int,
    target_char: str | None,
    result: str,
    source: str,
) -> None:
    db.conn.execute(
        """
        INSERT INTO char_results (
            session_id,
            position_index,
            target_char,
            entered_char,
            result,
            entered_code,
            source
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            int(position_index),
            target_char,
            target_char,
            result,
            ".-",
            source,
        ),
    )
    db.conn.commit()


def test_optimized_wpm_uses_recent_limit_per_key_source_and_best_uncapped_paris_median(tmp_path: Path) -> None:
    db = _new_db(tmp_path)
    base = datetime(2026, 1, 1, 12, 0, 0)

    # Older iambic rounds. These must still be considered even when newer
    # straight rounds fill the shared recent history.
    _insert_round(
        db,
        finished_at=base + timedelta(minutes=1),
        actual_wpm=30.0,
        target_wpm=5.0,
        accuracy=99.0,
        cleanliness=99.0,
        source_counts={"iambic": 12},
    )
    _insert_round(
        db,
        finished_at=base + timedelta(minutes=2),
        actual_wpm=32.0,
        target_wpm=5.0,
        accuracy=99.0,
        cleanliness=99.0,
        source_counts={"iambic": 12},
    )

    # Newer straight rounds.
    _insert_round(
        db,
        finished_at=base + timedelta(minutes=3),
        actual_wpm=9.0,
        target_wpm=9.0,
        accuracy=99.0,
        cleanliness=99.0,
        source_counts={"straight": 12},
    )
    _insert_round(
        db,
        finished_at=base + timedelta(minutes=4),
        actual_wpm=10.0,
        target_wpm=10.0,
        accuracy=99.0,
        cleanliness=99.0,
        source_counts={"straight": 12},
    )
    _insert_round(
        db,
        finished_at=base + timedelta(minutes=5),
        actual_wpm=11.0,
        target_wpm=11.0,
        accuracy=99.0,
        cleanliness=99.0,
        source_counts={"straight": 12},
    )

    result = db.optimized_wpm_from_recent_sessions(
        recent_sessions=2,
        min_accuracy=90.0,
        min_cleanliness=85.0,
        min_target_chars=1,
    )

    assert result["ok"] is True
    assert result["best_source"] == "iambic"

    assert result["straight_used_rounds"] == 2
    assert result["iambic_used_rounds"] == 2
    assert result["used_rounds"] == 2
    assert result["total_used_rounds"] == 4

    assert result["straight_wpm"] == pytest.approx(10.5, abs=0.05)
    assert result["iambic_wpm"] == pytest.approx(31.0, abs=0.05)
    assert result["wpm"] == pytest.approx(31.0, abs=0.05)

    # The iambic rounds used target_wpm=5. If the suggestion were capped,
    # it could not be around 31 WPM.
    assert result["wpm"] > 5.0


def test_optimized_wpm_filters_quality_length_elapsed_source_and_result_rows(tmp_path: Path) -> None:
    db = _new_db(tmp_path)
    base = datetime(2026, 1, 2, 12, 0, 0)

    _insert_round(
        db,
        finished_at=base + timedelta(minutes=1),
        actual_wpm=40.0,
        accuracy=50.0,
        cleanliness=100.0,
        source_counts={"iambic": 12},
    )
    _insert_round(
        db,
        finished_at=base + timedelta(minutes=2),
        actual_wpm=41.0,
        accuracy=100.0,
        cleanliness=50.0,
        source_counts={"iambic": 12},
    )
    _insert_round(
        db,
        finished_at=base + timedelta(minutes=3),
        target="AB",
        actual_wpm=42.0,
        accuracy=100.0,
        cleanliness=100.0,
        source_counts={"iambic": 2},
    )
    _insert_round(
        db,
        finished_at=base + timedelta(minutes=4),
        actual_wpm=43.0,
        accuracy=100.0,
        cleanliness=100.0,
        elapsed_us=0,
        source_counts={"iambic": 12},
    )
    _insert_round(
        db,
        finished_at=base + timedelta(minutes=5),
        actual_wpm=44.0,
        accuracy=100.0,
        cleanliness=100.0,
        source_counts={"keyboard": 12},
    )
    _insert_round(
        db,
        finished_at=base + timedelta(minutes=6),
        actual_wpm=45.0,
        accuracy=100.0,
        cleanliness=100.0,
        source_counts={"iambic": 12},
        char_result="insertion",
    )

    valid = _insert_round(
        db,
        finished_at=base + timedelta(minutes=7),
        actual_wpm=18.0,
        target_wpm=3.0,
        accuracy=100.0,
        cleanliness=100.0,
        source_counts={"straight": 12},
    )

    result = db.optimized_wpm_from_recent_sessions(
        recent_sessions=100,
        min_accuracy=90.0,
        min_cleanliness=85.0,
        min_target_chars=12,
    )

    assert result["ok"] is True
    assert result["best_source"] == "straight"
    assert result["straight_used_rounds"] == 1
    assert result["iambic_used_rounds"] == 0
    assert result["total_used_rounds"] == 1
    assert result["wpm"] == pytest.approx(18.0, abs=0.05)
    assert valid > 0


def test_optimized_wpm_returns_not_ok_when_no_qualified_rounds_exist(tmp_path: Path) -> None:
    db = _new_db(tmp_path)
    base = datetime(2026, 1, 3, 12, 0, 0)

    _insert_round(
        db,
        finished_at=base,
        actual_wpm=20.0,
        accuracy=10.0,
        cleanliness=10.0,
        source_counts={"straight": 12},
    )

    result = db.optimized_wpm_from_recent_sessions(
        recent_sessions=100,
        min_accuracy=90.0,
        min_cleanliness=85.0,
        min_target_chars=12,
    )

    assert result["ok"] is False
    assert result["wpm"] is None
    assert result["used_rounds"] == 0
    assert result["total_used_rounds"] == 0
    assert result["straight_wpm"] is None
    assert result["iambic_wpm"] is None


def test_stats_key_source_wpm_between_returns_uncapped_paris_wpm_dominant_source_and_sorted_rows(tmp_path: Path) -> None:
    db = _new_db(tmp_path)
    base = datetime(2026, 1, 4, 12, 0, 0)

    before = _insert_round(
        db,
        finished_at=base - timedelta(days=1),
        actual_wpm=99.0,
        target_wpm=99.0,
        source_counts={"straight": 12},
    )

    straight_id = _insert_round(
        db,
        finished_at=base + timedelta(minutes=1),
        actual_wpm=12.0,
        target_wpm=12.0,
        source_counts={"straight": 12},
    )

    iambic_id = _insert_round(
        db,
        finished_at=base + timedelta(minutes=2),
        actual_wpm=25.0,
        target_wpm=5.0,
        source_counts={"iambic": 12},
    )

    tie_id = _insert_round(
        db,
        finished_at=base + timedelta(minutes=3),
        actual_wpm=16.0,
        target_wpm=16.0,
        source_counts={"straight": 3, "iambic": 3},
    )

    after = _insert_round(
        db,
        finished_at=base + timedelta(days=1),
        actual_wpm=88.0,
        target_wpm=88.0,
        source_counts={"iambic": 12},
    )

    rows = db.stats_key_source_wpm_between(
        (base - timedelta(minutes=1)).isoformat(timespec="seconds"),
        (base + timedelta(minutes=10)).isoformat(timespec="seconds"),
    )

    assert [row["session_id"] for row in rows] == [straight_id, iambic_id, tie_id]
    assert before not in [row["session_id"] for row in rows]
    assert after not in [row["session_id"] for row in rows]

    assert rows[0]["key_source"] == "straight"
    assert rows[0]["wpm"] == pytest.approx(12.0, abs=0.05)

    assert rows[1]["key_source"] == "iambic"
    assert rows[1]["wpm"] == pytest.approx(25.0, abs=0.05)

    # target_wpm was 5, so this verifies the stats series is uncapped.
    assert rows[1]["wpm"] > 5.0

    # Equal straight/iambic source counts resolve to straight by the SQL order.
    assert rows[2]["session_id"] == tie_id
    assert rows[2]["key_source"] == "straight"
    assert rows[2]["wpm"] == pytest.approx(16.0, abs=0.05)


def test_stats_key_source_wpm_between_ignores_sessions_without_scored_straight_or_iambic_target_chars(tmp_path: Path) -> None:
    db = _new_db(tmp_path)
    base = datetime(2026, 1, 5, 12, 0, 0)

    no_valid_chars = _insert_round(
        db,
        finished_at=base + timedelta(minutes=1),
        actual_wpm=20.0,
        source_counts={},
    )
    _insert_char_result(
        db,
        session_id=no_valid_chars,
        position_index=0,
        target_char=" ",
        result="correct",
        source="straight",
    )
    _insert_char_result(
        db,
        session_id=no_valid_chars,
        position_index=1,
        target_char="A",
        result="insertion",
        source="straight",
    )

    unsupported_source = _insert_round(
        db,
        finished_at=base + timedelta(minutes=2),
        actual_wpm=30.0,
        source_counts={"keyboard": 12},
    )

    valid = _insert_round(
        db,
        finished_at=base + timedelta(minutes=3),
        actual_wpm=22.0,
        source_counts={"iambic": 12},
    )

    rows = db.stats_key_source_wpm_between(
        base.isoformat(timespec="seconds"),
        (base + timedelta(minutes=10)).isoformat(timespec="seconds"),
    )

    assert [row["session_id"] for row in rows] == [valid]
    assert no_valid_chars not in [row["session_id"] for row in rows]
    assert unsupported_source not in [row["session_id"] for row in rows]
    assert rows[0]["key_source"] == "iambic"
    assert rows[0]["wpm"] == pytest.approx(22.0, abs=0.05)


def test_skill_recent_sessions_by_key_source_uses_limit_per_source_and_returns_chronological_order(tmp_path: Path) -> None:
    db = _new_db(tmp_path)
    base = datetime(2026, 1, 6, 12, 0, 0)

    old_straight = _insert_round(
        db,
        finished_at=base + timedelta(minutes=1),
        actual_wpm=10.0,
        source_counts={"straight": 12},
    )
    mid_straight = _insert_round(
        db,
        finished_at=base + timedelta(minutes=2),
        actual_wpm=11.0,
        source_counts={"straight": 12},
    )
    new_straight = _insert_round(
        db,
        finished_at=base + timedelta(minutes=3),
        actual_wpm=12.0,
        source_counts={"straight": 12},
    )

    old_iambic = _insert_round(
        db,
        finished_at=base + timedelta(minutes=4),
        actual_wpm=20.0,
        source_counts={"iambic": 12},
    )
    mid_iambic = _insert_round(
        db,
        finished_at=base + timedelta(minutes=5),
        actual_wpm=21.0,
        source_counts={"iambic": 12},
    )
    new_iambic = _insert_round(
        db,
        finished_at=base + timedelta(minutes=6),
        actual_wpm=22.0,
        source_counts={"iambic": 12},
    )

    result = db.skill_recent_sessions_by_key_source(
        recent_sessions_per_source=2,
        min_target_chars=12,
    )

    # The oldest per-source row is dropped, but the remaining rows are returned
    # in chronological order within each source bucket.
    assert [row["id"] for row in result["straight"]] == [mid_straight, new_straight]
    assert [row["id"] for row in result["iambic"]] == [mid_iambic, new_iambic]

    assert old_straight not in [row["id"] for row in result["straight"]]
    assert old_iambic not in [row["id"] for row in result["iambic"]]

    assert all(row["dominant_key_source"] == "straight" for row in result["straight"])
    assert all(row["dominant_key_source"] == "iambic" for row in result["iambic"])


def test_skill_recent_sessions_by_key_source_classifies_mixed_rounds_by_dominant_source_and_ties_to_straight(tmp_path: Path) -> None:
    db = _new_db(tmp_path)
    base = datetime(2026, 1, 7, 12, 0, 0)

    dominant_iambic = _insert_round(
        db,
        finished_at=base + timedelta(minutes=1),
        actual_wpm=20.0,
        source_counts={"straight": 2, "iambic": 5},
    )

    dominant_straight = _insert_round(
        db,
        finished_at=base + timedelta(minutes=2),
        actual_wpm=15.0,
        source_counts={"straight": 5, "iambic": 2},
    )

    tie_defaults_to_straight = _insert_round(
        db,
        finished_at=base + timedelta(minutes=3),
        actual_wpm=17.0,
        source_counts={"straight": 3, "iambic": 3},
    )

    result = db.skill_recent_sessions_by_key_source(
        recent_sessions_per_source=10,
        min_target_chars=12,
    )

    assert [row["id"] for row in result["iambic"]] == [dominant_iambic]
    assert [row["id"] for row in result["straight"]] == [
        dominant_straight,
        tie_defaults_to_straight,
    ]


def test_calculate_skill_rating_keeps_capped_skill_values_but_exposes_uncapped_paris_display_values(tmp_path: Path) -> None:
    db = _new_db(tmp_path)
    base = datetime(2026, 1, 8, 12, 0, 0)

    _insert_round(
        db,
        finished_at=base + timedelta(minutes=1),
        actual_wpm=20.0,
        target_wpm=10.0,
        accuracy=100.0,
        cleanliness=100.0,
        source_counts={"straight": 12},
    )
    _insert_round(
        db,
        finished_at=base + timedelta(minutes=2),
        actual_wpm=22.0,
        target_wpm=10.0,
        accuracy=100.0,
        cleanliness=100.0,
        source_counts={"straight": 12},
    )

    _insert_round(
        db,
        finished_at=base + timedelta(minutes=3),
        actual_wpm=30.0,
        target_wpm=40.0,
        accuracy=100.0,
        cleanliness=100.0,
        source_counts={"iambic": 12},
    )
    _insert_round(
        db,
        finished_at=base + timedelta(minutes=4),
        actual_wpm=32.0,
        target_wpm=40.0,
        accuracy=100.0,
        cleanliness=100.0,
        source_counts={"iambic": 12},
    )

    rating = calculate_skill_rating(db, recent_rounds=100)

    # Internal skill-evidence WPM is capped by target_wpm.
    assert rating.straight_wpm == pytest.approx(10.0, abs=0.05)
    assert rating.iambic_wpm == pytest.approx(31.0, abs=0.05)

    # Display-only values are uncapped PARIS WPM.
    assert rating.straight_paris_wpm == pytest.approx(21.0, abs=0.05)
    assert rating.iambic_paris_wpm == pytest.approx(31.0, abs=0.05)

    # Both keys WPM is now the average of capped straight/iambic skill values,
    # not the weaker value alone.
    assert rating.effective_wpm == pytest.approx(20.5, abs=0.05)

    assert rating.used_rounds == 2
    assert rating.straight_used_rounds == 2
    assert rating.iambic_used_rounds == 2


def test_database_no_longer_exposes_removed_legacy_key_source_wpm_method(tmp_path: Path) -> None:
    db = _new_db(tmp_path)

    assert not hasattr(db, "skill_key_source_wpm")
    assert not hasattr(db, "_demonstrated_wpm")
    assert not hasattr(db, "_clamp_wpm")