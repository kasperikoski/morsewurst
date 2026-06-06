from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from morsewurst.core.skill_rating import calculate_skill_rating
from morsewurst.storage.database import Database


def _insert_skill_session(db: Database, *, source: str, target: str = "ABCDEFGHIJKL") -> int:
    cur = db.conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")

    cur.execute(
        """
        INSERT INTO sessions (
            started_at, finished_at, target, entered, source, finish_reason,
            accuracy, cleanliness, overall_score, speed_score, timing_score,
            correct_count, error_count, substitutions, insertions, deletions,
            length_target, length_entered, elapsed_us, standard_time_us, time_ok,
            avg_wpm, gross_wpm, net_wpm, settings_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            now,
            target,
            target,
            source,
            "completed",
            100.0,
            100.0,
            95.0,
            90.0,
            80.0,
            len(target),
            0,
            0,
            0,
            0,
            len(target),
            len(target),
            60_000_000,
            60_000_000,
            1,
            15.0,
            15.0,
            15.0,
            json.dumps(
                {
                    "use_letters": True,
                    "use_numbers": False,
                    "use_punctuation": False,
                }
            ),
        ),
    )
    session_id = int(cur.lastrowid)

    for index, char in enumerate(target):
        cur.execute(
            """
            INSERT INTO char_results (
                session_id, position_index, target_char, entered_char, result, source, wpm
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, index, char, char, "correct", source, 15.0),
        )

    db.conn.commit()
    return session_id


def test_skill_rating_can_be_calculated_as_of_a_session_id(tmp_path: Path) -> None:
    db = Database(tmp_path / "morsewurst.sqlite3")
    try:
        first = _insert_skill_session(db, source="straight")
        second = _insert_skill_session(db, source="iambic")
        third = _insert_skill_session(db, source="straight")
        fourth = _insert_skill_session(db, source="iambic")

        assert [row["id"] for row in db.skill_recent_sessions(100)] == [first, second, third, fourth]
        assert [row["id"] for row in db.skill_recent_sessions(100, max_session_id=second)] == [first, second]

        all_rating = calculate_skill_rating(db, recent_rounds=100)
        second_rating = calculate_skill_rating(db, recent_rounds=100, max_session_id=second)

        assert all_rating.total_rounds == 4
        assert second_rating.total_rounds == 2
    finally:
        db.close()
