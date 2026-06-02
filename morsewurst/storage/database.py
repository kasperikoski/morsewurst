# ============================================================
# morsewurst/storage/database.py
# ============================================================

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

import morsewurst.config as config
from morsewurst.core.scoring import paris_wpm_for_text
from morsewurst.core.app_logging import (
    log_app_event,
    log_app_exception,
    summarize_challenge_settings,
    summarize_rating,
    summarize_score_summary,
    summarize_timing_profile,
)
from morsewurst.core.timing_profile import TimingProfile, TimingProfileSample, build_timing_profile, normalize_source
from morsewurst.models import ChallengeSettings, CharacterResult, ScoreSummary

SCHEMA_VERSION = 1
SCHEMA_META_KEY = "schema_version"

class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        log_app_event(
            "app.database.open_started",
            message="Database open started.",
            context={"path": str(path), "database_existed": path.exists()},
        )

        self.path = path
        self.replaced_incompatible_database_path: Optional[Path] = None

        database_existed = path.exists()

        self.conn = self._connect()

        if database_existed:
            try:
                self._prepare_existing_database_for_current_schema()
            except Exception as exc:
                log_app_exception(
                    "app.database.schema_prepare_failed",
                    exc,
                    level="warning",
                    message="Existing database schema preparation failed; compatibility check will continue.",
                    context={"path": str(path)},
                )

        if database_existed and not self._schema_is_compatible():
            self.replaced_incompatible_database_path = self._replace_incompatible_database()
            log_app_event(
                "app.database.incompatible_replaced",
                level="warning",
                message="Incompatible database was moved aside and replaced.",
                context={
                    "path": str(path),
                    "replaced_path": str(self.replaced_incompatible_database_path),
                },
            )

        self.init_schema()
        self._ensure_current_schema_columns()
        self._ensure_practice_tracking_schema()
        self.ensure_koch_schema()
        self.ensure_practice_consistency()
        self.mark_in_progress_practices_interrupted()
        self._write_schema_version()
        log_app_event(
            "app.database.opened",
            message="Database opened and schema initialized.",
            context={
                "path": str(self.path),
                "database_existed": database_existed,
                "replaced_incompatible": self.replaced_incompatible_database_path is not None,
            },
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn
    

    def _table_exists(self, table: str) -> bool:
        cur = self.conn.cursor()

        row = cur.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name = ?
            """,
            (table,),
        ).fetchone()

        return row is not None

    def _prepare_existing_database_for_current_schema(self) -> None:
        """Bring an existing profile database up to the current additive schema.

        This is not legacy data conversion. It only creates the current tables
        and adds current columns that are missing from an otherwise usable
        profile database before the compatibility check runs.
        """

        self.init_schema()
        self._ensure_current_schema_columns()
        self._ensure_practice_tracking_schema()
        self.ensure_koch_schema()
        self.ensure_practice_consistency()

    def _ensure_practice_tracking_schema(self) -> None:
        cur = self.conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS practices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL DEFAULT 'in_progress',
                planned_rounds INTEGER NOT NULL DEFAULT 1,
                completed_rounds INTEGER NOT NULL DEFAULT 0,
                total_elapsed_us INTEGER NOT NULL DEFAULT 0,
                total_standard_time_us INTEGER NOT NULL DEFAULT 0,
                settings_json TEXT NOT NULL
            )
            """
        )

        if self._table_exists("sessions"):
            session_columns = self._column_names("sessions")

            if "practice_id" not in session_columns:
                cur.execute("ALTER TABLE sessions ADD COLUMN practice_id INTEGER")

            if "round_number" not in session_columns:
                cur.execute(
                    "ALTER TABLE sessions ADD COLUMN round_number INTEGER NOT NULL DEFAULT 1"
                )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_practice_round
            ON sessions(practice_id, round_number)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_practices_finished_at
            ON practices(finished_at)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_practices_status
            ON practices(status)
            """
        )

        self.conn.commit()


    def _ensure_current_schema_columns(self) -> None:
        """Add missing columns for the current non-Koch schema.

        ``CREATE TABLE IF NOT EXISTS`` is enough for fresh databases, but it does
        not update an existing table. This guard keeps an existing profile usable
        when the current schema gains additive columns.
        """

        cur = self.conn.cursor()

        def add_column_if_missing(
            *,
            table: str,
            known_columns: set[str],
            column: str,
            definition: str,
        ) -> None:
            if column in known_columns:
                return

            cur.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
            known_columns.add(column)

        def add_columns(table: str, definitions: list[tuple[str, str]]) -> None:
            if not self._table_exists(table):
                return

            known_columns = self._column_names(table)
            for column, definition in definitions:
                add_column_if_missing(
                    table=table,
                    known_columns=known_columns,
                    column=column,
                    definition=definition,
                )

        add_columns(
            "practices",
            [
                ("started_at", "started_at TEXT NOT NULL DEFAULT ''"),
                ("finished_at", "finished_at TEXT"),
                ("status", "status TEXT NOT NULL DEFAULT 'in_progress'"),
                ("planned_rounds", "planned_rounds INTEGER NOT NULL DEFAULT 1"),
                ("completed_rounds", "completed_rounds INTEGER NOT NULL DEFAULT 0"),
                ("total_elapsed_us", "total_elapsed_us INTEGER NOT NULL DEFAULT 0"),
                ("total_standard_time_us", "total_standard_time_us INTEGER NOT NULL DEFAULT 0"),
                ("settings_json", "settings_json TEXT NOT NULL DEFAULT '{}'"),
            ],
        )

        add_columns(
            "sessions",
            [
                ("started_at", "started_at TEXT NOT NULL DEFAULT ''"),
                ("finished_at", "finished_at TEXT NOT NULL DEFAULT ''"),
                ("target", "target TEXT NOT NULL DEFAULT ''"),
                ("entered", "entered TEXT NOT NULL DEFAULT ''"),
                ("source", "source TEXT NOT NULL DEFAULT ''"),
                ("finish_reason", "finish_reason TEXT NOT NULL DEFAULT ''"),
                ("practice_id", "practice_id INTEGER"),
                ("round_number", "round_number INTEGER NOT NULL DEFAULT 1"),
                ("accuracy", "accuracy REAL NOT NULL DEFAULT 0"),
                ("cleanliness", "cleanliness REAL NOT NULL DEFAULT 0"),
                ("overall_score", "overall_score REAL NOT NULL DEFAULT 0"),
                ("speed_score", "speed_score REAL"),
                ("timing_score", "timing_score REAL"),
                ("timing_element_score", "timing_element_score REAL"),
                ("timing_gap_score", "timing_gap_score REAL"),
                ("timing_ratio_score", "timing_ratio_score REAL"),
                ("timing_dot_consistency", "timing_dot_consistency REAL"),
                ("timing_dash_consistency", "timing_dash_consistency REAL"),
                ("timing_intra_gap_score", "timing_intra_gap_score REAL"),
                ("timing_letter_gap_score", "timing_letter_gap_score REAL"),
                ("timing_word_gap_score", "timing_word_gap_score REAL"),
                ("profile_eligible", "profile_eligible INTEGER NOT NULL DEFAULT 1"),
                ("profile_reject_reason", "profile_reject_reason TEXT"),
                ("profile_max_element_units", "profile_max_element_units REAL"),
                ("profile_max_gap_units", "profile_max_gap_units REAL"),
                ("correct_count", "correct_count INTEGER NOT NULL DEFAULT 0"),
                ("error_count", "error_count INTEGER NOT NULL DEFAULT 0"),
                ("substitutions", "substitutions INTEGER NOT NULL DEFAULT 0"),
                ("insertions", "insertions INTEGER NOT NULL DEFAULT 0"),
                ("deletions", "deletions INTEGER NOT NULL DEFAULT 0"),
                ("length_target", "length_target INTEGER NOT NULL DEFAULT 0"),
                ("length_entered", "length_entered INTEGER NOT NULL DEFAULT 0"),
                ("elapsed_us", "elapsed_us INTEGER"),
                ("standard_time_us", "standard_time_us INTEGER"),
                ("time_ok", "time_ok INTEGER"),
                ("avg_wpm", "avg_wpm REAL"),
                ("gross_wpm", "gross_wpm REAL"),
                ("net_wpm", "net_wpm REAL"),
                ("avg_dit_us", "avg_dit_us REAL"),
                ("dit_sd_us", "dit_sd_us REAL"),
                ("straight_dot_us", "straight_dot_us REAL"),
                ("straight_dot_sd_us", "straight_dot_sd_us REAL"),
                ("straight_dash_us", "straight_dash_us REAL"),
                ("straight_dash_sd_us", "straight_dash_sd_us REAL"),
                ("straight_dash_dot_ratio", "straight_dash_dot_ratio REAL"),
                ("avg_letter_gap_us", "avg_letter_gap_us REAL"),
                ("letter_gap_sd_us", "letter_gap_sd_us REAL"),
                ("avg_word_gap_us", "avg_word_gap_us REAL"),
                ("word_gap_sd_us", "word_gap_sd_us REAL"),
                ("settings_json", "settings_json TEXT NOT NULL DEFAULT '{}'"),
            ],
        )

        add_columns(
            "events",
            [
                ("session_id", "session_id INTEGER NOT NULL DEFAULT 0"),
                ("event_index", "event_index INTEGER NOT NULL DEFAULT 0"),
                ("event_type", "event_type TEXT NOT NULL DEFAULT ''"),
                ("event_json", "event_json TEXT NOT NULL DEFAULT '{}'"),
            ],
        )

        add_columns(
            "char_results",
            [
                ("session_id", "session_id INTEGER NOT NULL DEFAULT 0"),
                ("position_index", "position_index INTEGER NOT NULL DEFAULT 0"),
                ("target_char", "target_char TEXT"),
                ("entered_char", "entered_char TEXT"),
                ("result", "result TEXT NOT NULL DEFAULT ''"),
                ("entered_code", "entered_code TEXT"),
                ("source", "source TEXT"),
                ("char_time_us", "char_time_us INTEGER"),
                ("first_element_us", "first_element_us INTEGER"),
                ("last_element_us", "last_element_us INTEGER"),
                ("gap_before_us", "gap_before_us INTEGER"),
                ("gap_before_units", "gap_before_units REAL"),
                ("gap_kind", "gap_kind TEXT"),
                ("element_unit_us", "element_unit_us REAL"),
                ("gap_unit_us", "gap_unit_us REAL"),
                ("wpm", "wpm REAL"),
            ],
        )

        add_columns(
            "skill_rating_snapshots",
            [
                ("created_at", "created_at TEXT NOT NULL DEFAULT ''"),
                ("session_id", "session_id INTEGER"),
                ("model_version", "model_version INTEGER NOT NULL DEFAULT 1"),
                ("recent_sessions", "recent_sessions INTEGER NOT NULL DEFAULT 0"),
                ("total_rounds", "total_rounds INTEGER NOT NULL DEFAULT 0"),
                ("used_rounds", "used_rounds INTEGER NOT NULL DEFAULT 0"),
                ("effective_wpm", "effective_wpm REAL"),
                ("avg_accuracy", "avg_accuracy REAL"),
                ("avg_cleanliness", "avg_cleanliness REAL"),
                ("quality_factor", "quality_factor REAL NOT NULL DEFAULT 0"),
                ("character_mastery_factor", "character_mastery_factor REAL NOT NULL DEFAULT 0"),
                ("coverage_factor", "coverage_factor REAL NOT NULL DEFAULT 0"),
                ("timing_stability_factor", "timing_stability_factor REAL NOT NULL DEFAULT 0"),
                ("sample_confidence", "sample_confidence REAL NOT NULL DEFAULT 0"),
                ("rating_confidence", "rating_confidence REAL NOT NULL DEFAULT 0"),
                ("mastery_adjustment", "mastery_adjustment REAL NOT NULL DEFAULT 1"),
                ("raw_skill", "raw_skill REAL"),
                ("level", "level INTEGER NOT NULL DEFAULT 1"),
                ("level_progress", "level_progress REAL NOT NULL DEFAULT 0"),
                ("title", "title TEXT NOT NULL DEFAULT ''"),
                ("details_json", "details_json TEXT NOT NULL DEFAULT '{}'"),
            ],
        )

        add_columns(
            "problem_stats",
            [
                ("attempts", "attempts INTEGER NOT NULL DEFAULT 0"),
                ("errors", "errors INTEGER NOT NULL DEFAULT 0"),
                ("last_seen_at", "last_seen_at TEXT NOT NULL DEFAULT ''"),
            ],
        )

        add_columns(
            "timing_profile_state",
            [
                ("updated_at", "updated_at TEXT NOT NULL DEFAULT ''"),
                ("element_unit_us", "element_unit_us REAL"),
                ("gap_unit_us", "gap_unit_us REAL"),
                ("dot_us", "dot_us REAL"),
                ("dash_us", "dash_us REAL"),
                ("dash_dot_ratio", "dash_dot_ratio REAL"),
                ("letter_gap_us", "letter_gap_us REAL"),
                ("word_gap_us", "word_gap_us REAL"),
                ("element_confidence", "element_confidence REAL NOT NULL DEFAULT 0"),
                ("gap_confidence", "gap_confidence REAL NOT NULL DEFAULT 0"),
                ("sample_rounds", "sample_rounds INTEGER NOT NULL DEFAULT 0"),
                ("sample_events", "sample_events INTEGER NOT NULL DEFAULT 0"),
                ("updated_from_session_id", "updated_from_session_id INTEGER"),
            ],
        )

        self.conn.commit()


    def ensure_koch_schema(self) -> None:
        """Create Koch receive-practice tables without changing core schema compatibility.

        Koch mode is an additive feature. Missing Koch tables in an existing
        profile database must never make the old database look incompatible.
        """

        cur = self.conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS koch_progress (
                sequence_key TEXT PRIMARY KEY,
                guided_unlocked_stage INTEGER NOT NULL DEFAULT 2,
                guided_current_stage INTEGER NOT NULL DEFAULT 2,
                guided_fail_streak INTEGER NOT NULL DEFAULT 0,
                guided_fail_stage INTEGER,
                last_demoted_from_stage INTEGER,
                last_demoted_to_stage INTEGER,
                last_demoted_at TEXT,
                total_sessions INTEGER NOT NULL DEFAULT 0,
                total_practice_seconds INTEGER NOT NULL DEFAULT 0,
                last_session_id INTEGER,
                updated_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS koch_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                mode TEXT NOT NULL,
                sequence_key TEXT NOT NULL,
                stage_index INTEGER NOT NULL,
                active_chars TEXT NOT NULL,
                new_stage_char TEXT,
                target_text TEXT NOT NULL,
                entered_text TEXT NOT NULL,
                target_length INTEGER NOT NULL,
                entered_length INTEGER NOT NULL,
                character_wpm INTEGER NOT NULL,
                effective_wpm INTEGER NOT NULL,
                tone_hz INTEGER NOT NULL DEFAULT 600,
                volume_percent INTEGER NOT NULL DEFAULT 70,
                duration_ms INTEGER NOT NULL,
                pass_accuracy REAL NOT NULL,
                pass_cleanliness REAL NOT NULL,
                new_char_min_attempts INTEGER NOT NULL,
                new_char_min_accuracy REAL NOT NULL,
                correct_count INTEGER NOT NULL,
                error_count INTEGER NOT NULL,
                substitutions INTEGER NOT NULL,
                insertions INTEGER NOT NULL,
                deletions INTEGER NOT NULL,
                accuracy REAL NOT NULL,
                aligned_accuracy REAL NOT NULL DEFAULT 0,
                time_aligned_accuracy REAL NOT NULL DEFAULT 0,
                timing_fit REAL NOT NULL DEFAULT 0,
                cleanliness REAL NOT NULL,
                new_char_accuracy REAL,
                new_char_attempts INTEGER NOT NULL,
                score REAL NOT NULL,
                speed_factor REAL NOT NULL,
                coverage_factor REAL NOT NULL,
                level_estimate REAL NOT NULL,
                pass_eligible INTEGER NOT NULL,
                passed INTEGER NOT NULL,
                advanced_from_stage INTEGER,
                advanced_to_stage INTEGER,
                demoted_from_stage INTEGER,
                demoted_to_stage INTEGER,
                demotion_reason TEXT NOT NULL DEFAULT '',
                guided_fail_streak_after INTEGER NOT NULL DEFAULT 0,
                pass_reason TEXT NOT NULL,
                settings_json TEXT NOT NULL,
                target_schedule_json TEXT NOT NULL DEFAULT '[]'
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS koch_char_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                koch_session_id INTEGER NOT NULL,
                position_index INTEGER NOT NULL,
                target_char TEXT,
                entered_char TEXT,
                result TEXT NOT NULL,
                target_stage_index INTEGER,
                is_new_stage_char INTEGER NOT NULL DEFAULT 0,
                expected_start_ms INTEGER,
                expected_end_ms INTEGER,
                typed_at_ms INTEGER,
                latency_ms INTEGER,
                timing_weight REAL NOT NULL DEFAULT 1.0,
                timing_status TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(koch_session_id) REFERENCES koch_sessions(id)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS koch_key_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                koch_session_id INTEGER NOT NULL,
                event_index INTEGER NOT NULL,
                key TEXT NOT NULL,
                char TEXT,
                typed_at_ms INTEGER,
                event_json TEXT NOT NULL,
                FOREIGN KEY(koch_session_id) REFERENCES koch_sessions(id)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS koch_progress_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                koch_session_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                sequence_key TEXT NOT NULL,
                mode TEXT NOT NULL,
                session_stage_index INTEGER NOT NULL,
                stage_before INTEGER NOT NULL,
                stage_after INTEGER NOT NULL,
                unlocked_before INTEGER NOT NULL,
                unlocked_after INTEGER NOT NULL,
                active_chars TEXT NOT NULL,
                active_char_count INTEGER NOT NULL,
                target_length INTEGER NOT NULL,
                entered_length INTEGER NOT NULL,
                character_wpm INTEGER NOT NULL,
                effective_wpm INTEGER NOT NULL,
                tone_hz INTEGER NOT NULL,
                volume_percent INTEGER NOT NULL,
                duration_ms INTEGER NOT NULL,
                pass_accuracy REAL NOT NULL,
                pass_cleanliness REAL NOT NULL,
                new_char_min_attempts INTEGER NOT NULL,
                new_char_min_accuracy REAL NOT NULL,
                guided_fail_streak_before INTEGER NOT NULL DEFAULT 0,
                guided_fail_streak_after INTEGER NOT NULL DEFAULT 0,
                guided_fail_stage_before INTEGER,
                guided_fail_stage_after INTEGER,
                passed INTEGER NOT NULL,
                pass_eligible INTEGER NOT NULL,
                demoted_from_stage INTEGER,
                demoted_to_stage INTEGER,
                demotion_reason TEXT NOT NULL DEFAULT '',
                advanced_from_stage INTEGER,
                advanced_to_stage INTEGER,
                correct_count INTEGER NOT NULL,
                error_count INTEGER NOT NULL,
                substitutions INTEGER NOT NULL,
                insertions INTEGER NOT NULL,
                deletions INTEGER NOT NULL,
                accuracy REAL NOT NULL,
                aligned_accuracy REAL NOT NULL,
                time_aligned_accuracy REAL NOT NULL,
                timing_fit REAL NOT NULL,
                cleanliness REAL NOT NULL,
                new_char_accuracy REAL,
                new_char_attempts INTEGER NOT NULL,
                score REAL NOT NULL,
                speed_factor REAL NOT NULL,
                coverage_factor REAL NOT NULL,
                level_estimate REAL NOT NULL,
                settings_json TEXT NOT NULL,
                FOREIGN KEY(koch_session_id) REFERENCES koch_sessions(id)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS koch_skill_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                koch_session_id INTEGER,
                created_at TEXT NOT NULL,
                model_version INTEGER NOT NULL,
                recent_limit INTEGER NOT NULL,
                sessions_used INTEGER NOT NULL,
                required_sessions INTEGER NOT NULL,
                displayable INTEGER NOT NULL,
                confidence REAL NOT NULL,
                level REAL NOT NULL,
                raw_level REAL NOT NULL,
                display_level INTEGER,
                title_key TEXT NOT NULL,
                base_sequence_key TEXT NOT NULL,
                active_char_count INTEGER NOT NULL,
                total_character_count INTEGER NOT NULL,
                classic_active_count INTEGER NOT NULL,
                lcwo_active_count INTEGER NOT NULL,
                base_level REAL NOT NULL,
                average_accuracy REAL NOT NULL,
                average_cleanliness REAL NOT NULL,
                average_character_wpm REAL NOT NULL,
                average_effective_wpm REAL NOT NULL,
                average_target_length REAL NOT NULL,
                speed_factor REAL NOT NULL,
                accuracy_factor REAL NOT NULL,
                cleanliness_factor REAL NOT NULL,
                length_factor REAL NOT NULL,
                normalizer REAL NOT NULL,
                FOREIGN KEY(koch_session_id) REFERENCES koch_sessions(id)
            )
            """
        )

        def add_column_if_missing(
            *,
            table: str,
            known_columns: set[str],
            column: str,
            definition: str,
        ) -> None:
            if column in known_columns:
                return

            cur.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
            known_columns.add(column)

        current_koch_columns: dict[str, list[tuple[str, str]]] = {
            "koch_progress": [
                ("guided_unlocked_stage", "guided_unlocked_stage INTEGER NOT NULL DEFAULT 2"),
                ("guided_current_stage", "guided_current_stage INTEGER NOT NULL DEFAULT 2"),
                ("guided_fail_streak", "guided_fail_streak INTEGER NOT NULL DEFAULT 0"),
                ("guided_fail_stage", "guided_fail_stage INTEGER"),
                ("last_demoted_from_stage", "last_demoted_from_stage INTEGER"),
                ("last_demoted_to_stage", "last_demoted_to_stage INTEGER"),
                ("last_demoted_at", "last_demoted_at TEXT"),
                ("total_sessions", "total_sessions INTEGER NOT NULL DEFAULT 0"),
                ("total_practice_seconds", "total_practice_seconds INTEGER NOT NULL DEFAULT 0"),
                ("last_session_id", "last_session_id INTEGER"),
                ("updated_at", "updated_at TEXT NOT NULL DEFAULT ''"),
            ],
            "koch_sessions": [
                ("started_at", "started_at TEXT NOT NULL DEFAULT ''"),
                ("finished_at", "finished_at TEXT NOT NULL DEFAULT ''"),
                ("mode", "mode TEXT NOT NULL DEFAULT 'guided'"),
                ("sequence_key", "sequence_key TEXT NOT NULL DEFAULT 'classic'"),
                ("stage_index", "stage_index INTEGER NOT NULL DEFAULT 2"),
                ("active_chars", "active_chars TEXT NOT NULL DEFAULT ''"),
                ("new_stage_char", "new_stage_char TEXT"),
                ("target_text", "target_text TEXT NOT NULL DEFAULT ''"),
                ("entered_text", "entered_text TEXT NOT NULL DEFAULT ''"),
                ("target_length", "target_length INTEGER NOT NULL DEFAULT 0"),
                ("entered_length", "entered_length INTEGER NOT NULL DEFAULT 0"),
                ("character_wpm", "character_wpm INTEGER NOT NULL DEFAULT 20"),
                ("effective_wpm", "effective_wpm INTEGER NOT NULL DEFAULT 15"),
                ("tone_hz", "tone_hz INTEGER NOT NULL DEFAULT 600"),
                ("volume_percent", "volume_percent INTEGER NOT NULL DEFAULT 70"),
                ("duration_ms", "duration_ms INTEGER NOT NULL DEFAULT 0"),
                ("pass_accuracy", "pass_accuracy REAL NOT NULL DEFAULT 90"),
                ("pass_cleanliness", "pass_cleanliness REAL NOT NULL DEFAULT 85"),
                ("new_char_min_attempts", "new_char_min_attempts INTEGER NOT NULL DEFAULT 8"),
                ("new_char_min_accuracy", "new_char_min_accuracy REAL NOT NULL DEFAULT 80"),
                ("correct_count", "correct_count INTEGER NOT NULL DEFAULT 0"),
                ("error_count", "error_count INTEGER NOT NULL DEFAULT 0"),
                ("substitutions", "substitutions INTEGER NOT NULL DEFAULT 0"),
                ("insertions", "insertions INTEGER NOT NULL DEFAULT 0"),
                ("deletions", "deletions INTEGER NOT NULL DEFAULT 0"),
                ("accuracy", "accuracy REAL NOT NULL DEFAULT 0"),
                ("aligned_accuracy", "aligned_accuracy REAL NOT NULL DEFAULT 0"),
                ("time_aligned_accuracy", "time_aligned_accuracy REAL NOT NULL DEFAULT 0"),
                ("timing_fit", "timing_fit REAL NOT NULL DEFAULT 0"),
                ("cleanliness", "cleanliness REAL NOT NULL DEFAULT 0"),
                ("new_char_accuracy", "new_char_accuracy REAL"),
                ("new_char_attempts", "new_char_attempts INTEGER NOT NULL DEFAULT 0"),
                ("score", "score REAL NOT NULL DEFAULT 0"),
                ("speed_factor", "speed_factor REAL NOT NULL DEFAULT 0"),
                ("coverage_factor", "coverage_factor REAL NOT NULL DEFAULT 0"),
                ("level_estimate", "level_estimate REAL NOT NULL DEFAULT 0"),
                ("pass_eligible", "pass_eligible INTEGER NOT NULL DEFAULT 0"),
                ("passed", "passed INTEGER NOT NULL DEFAULT 0"),
                ("advanced_from_stage", "advanced_from_stage INTEGER"),
                ("advanced_to_stage", "advanced_to_stage INTEGER"),
                ("demoted_from_stage", "demoted_from_stage INTEGER"),
                ("demoted_to_stage", "demoted_to_stage INTEGER"),
                ("demotion_reason", "demotion_reason TEXT NOT NULL DEFAULT ''"),
                ("guided_fail_streak_after", "guided_fail_streak_after INTEGER NOT NULL DEFAULT 0"),
                ("pass_reason", "pass_reason TEXT NOT NULL DEFAULT ''"),
                ("settings_json", "settings_json TEXT NOT NULL DEFAULT '{}'"),
                ("target_schedule_json", "target_schedule_json TEXT NOT NULL DEFAULT '[]'"),
            ],
            "koch_char_results": [
                ("koch_session_id", "koch_session_id INTEGER NOT NULL DEFAULT 0"),
                ("position_index", "position_index INTEGER NOT NULL DEFAULT 0"),
                ("target_char", "target_char TEXT"),
                ("entered_char", "entered_char TEXT"),
                ("result", "result TEXT NOT NULL DEFAULT ''"),
                ("target_stage_index", "target_stage_index INTEGER"),
                ("is_new_stage_char", "is_new_stage_char INTEGER NOT NULL DEFAULT 0"),
                ("expected_start_ms", "expected_start_ms INTEGER"),
                ("expected_end_ms", "expected_end_ms INTEGER"),
                ("typed_at_ms", "typed_at_ms INTEGER"),
                ("latency_ms", "latency_ms INTEGER"),
                ("timing_weight", "timing_weight REAL NOT NULL DEFAULT 1.0"),
                ("timing_status", "timing_status TEXT NOT NULL DEFAULT ''"),
            ],
            "koch_key_events": [
                ("koch_session_id", "koch_session_id INTEGER NOT NULL DEFAULT 0"),
                ("event_index", "event_index INTEGER NOT NULL DEFAULT 0"),
                ("key", "key TEXT NOT NULL DEFAULT ''"),
                ("char", "char TEXT"),
                ("typed_at_ms", "typed_at_ms INTEGER"),
                ("event_json", "event_json TEXT NOT NULL DEFAULT '{}'"),
            ],
            "koch_progress_snapshots": [
                ("koch_session_id", "koch_session_id INTEGER NOT NULL DEFAULT 0"),
                ("created_at", "created_at TEXT NOT NULL DEFAULT ''"),
                ("sequence_key", "sequence_key TEXT NOT NULL DEFAULT 'classic'"),
                ("mode", "mode TEXT NOT NULL DEFAULT 'guided'"),
                ("session_stage_index", "session_stage_index INTEGER NOT NULL DEFAULT 2"),
                ("stage_before", "stage_before INTEGER NOT NULL DEFAULT 2"),
                ("stage_after", "stage_after INTEGER NOT NULL DEFAULT 2"),
                ("unlocked_before", "unlocked_before INTEGER NOT NULL DEFAULT 2"),
                ("unlocked_after", "unlocked_after INTEGER NOT NULL DEFAULT 2"),
                ("active_chars", "active_chars TEXT NOT NULL DEFAULT ''"),
                ("active_char_count", "active_char_count INTEGER NOT NULL DEFAULT 0"),
                ("target_length", "target_length INTEGER NOT NULL DEFAULT 0"),
                ("entered_length", "entered_length INTEGER NOT NULL DEFAULT 0"),
                ("character_wpm", "character_wpm INTEGER NOT NULL DEFAULT 20"),
                ("effective_wpm", "effective_wpm INTEGER NOT NULL DEFAULT 15"),
                ("tone_hz", "tone_hz INTEGER NOT NULL DEFAULT 600"),
                ("volume_percent", "volume_percent INTEGER NOT NULL DEFAULT 70"),
                ("duration_ms", "duration_ms INTEGER NOT NULL DEFAULT 0"),
                ("pass_accuracy", "pass_accuracy REAL NOT NULL DEFAULT 90"),
                ("pass_cleanliness", "pass_cleanliness REAL NOT NULL DEFAULT 85"),
                ("new_char_min_attempts", "new_char_min_attempts INTEGER NOT NULL DEFAULT 8"),
                ("new_char_min_accuracy", "new_char_min_accuracy REAL NOT NULL DEFAULT 80"),
                ("guided_fail_streak_before", "guided_fail_streak_before INTEGER NOT NULL DEFAULT 0"),
                ("guided_fail_streak_after", "guided_fail_streak_after INTEGER NOT NULL DEFAULT 0"),
                ("guided_fail_stage_before", "guided_fail_stage_before INTEGER"),
                ("guided_fail_stage_after", "guided_fail_stage_after INTEGER"),
                ("passed", "passed INTEGER NOT NULL DEFAULT 0"),
                ("pass_eligible", "pass_eligible INTEGER NOT NULL DEFAULT 0"),
                ("demoted_from_stage", "demoted_from_stage INTEGER"),
                ("demoted_to_stage", "demoted_to_stage INTEGER"),
                ("demotion_reason", "demotion_reason TEXT NOT NULL DEFAULT ''"),
                ("advanced_from_stage", "advanced_from_stage INTEGER"),
                ("advanced_to_stage", "advanced_to_stage INTEGER"),
                ("correct_count", "correct_count INTEGER NOT NULL DEFAULT 0"),
                ("error_count", "error_count INTEGER NOT NULL DEFAULT 0"),
                ("substitutions", "substitutions INTEGER NOT NULL DEFAULT 0"),
                ("insertions", "insertions INTEGER NOT NULL DEFAULT 0"),
                ("deletions", "deletions INTEGER NOT NULL DEFAULT 0"),
                ("accuracy", "accuracy REAL NOT NULL DEFAULT 0"),
                ("aligned_accuracy", "aligned_accuracy REAL NOT NULL DEFAULT 0"),
                ("time_aligned_accuracy", "time_aligned_accuracy REAL NOT NULL DEFAULT 0"),
                ("timing_fit", "timing_fit REAL NOT NULL DEFAULT 0"),
                ("cleanliness", "cleanliness REAL NOT NULL DEFAULT 0"),
                ("new_char_accuracy", "new_char_accuracy REAL"),
                ("new_char_attempts", "new_char_attempts INTEGER NOT NULL DEFAULT 0"),
                ("score", "score REAL NOT NULL DEFAULT 0"),
                ("speed_factor", "speed_factor REAL NOT NULL DEFAULT 0"),
                ("coverage_factor", "coverage_factor REAL NOT NULL DEFAULT 0"),
                ("level_estimate", "level_estimate REAL NOT NULL DEFAULT 0"),
                ("settings_json", "settings_json TEXT NOT NULL DEFAULT '{}'"),
            ],
            "koch_skill_snapshots": [
                ("koch_session_id", "koch_session_id INTEGER"),
                ("created_at", "created_at TEXT NOT NULL DEFAULT ''"),
                ("model_version", "model_version INTEGER NOT NULL DEFAULT 2"),
                ("recent_limit", "recent_limit INTEGER NOT NULL DEFAULT 1000"),
                ("sessions_used", "sessions_used INTEGER NOT NULL DEFAULT 0"),
                ("required_sessions", "required_sessions INTEGER NOT NULL DEFAULT 30"),
                ("displayable", "displayable INTEGER NOT NULL DEFAULT 0"),
                ("confidence", "confidence REAL NOT NULL DEFAULT 0"),
                ("level", "level REAL NOT NULL DEFAULT 0"),
                ("raw_level", "raw_level REAL NOT NULL DEFAULT 0"),
                ("display_level", "display_level INTEGER"),
                ("title_key", "title_key TEXT NOT NULL DEFAULT ''"),
                ("base_sequence_key", "base_sequence_key TEXT NOT NULL DEFAULT ''"),
                ("active_char_count", "active_char_count INTEGER NOT NULL DEFAULT 0"),
                ("total_character_count", "total_character_count INTEGER NOT NULL DEFAULT 0"),
                ("classic_active_count", "classic_active_count INTEGER NOT NULL DEFAULT 0"),
                ("lcwo_active_count", "lcwo_active_count INTEGER NOT NULL DEFAULT 0"),
                ("base_level", "base_level REAL NOT NULL DEFAULT 0"),
                ("average_accuracy", "average_accuracy REAL NOT NULL DEFAULT 0"),
                ("average_cleanliness", "average_cleanliness REAL NOT NULL DEFAULT 0"),
                ("average_character_wpm", "average_character_wpm REAL NOT NULL DEFAULT 0"),
                ("average_effective_wpm", "average_effective_wpm REAL NOT NULL DEFAULT 0"),
                ("average_target_length", "average_target_length REAL NOT NULL DEFAULT 0"),
                ("speed_factor", "speed_factor REAL NOT NULL DEFAULT 0"),
                ("accuracy_factor", "accuracy_factor REAL NOT NULL DEFAULT 0"),
                ("cleanliness_factor", "cleanliness_factor REAL NOT NULL DEFAULT 0"),
                ("length_factor", "length_factor REAL NOT NULL DEFAULT 0"),
                ("normalizer", "normalizer REAL NOT NULL DEFAULT 0"),
            ],
        }

        for table, definitions in current_koch_columns.items():
            if not self._table_exists(table):
                continue

            known_columns = self._column_names(table)
            for column, definition in definitions:
                add_column_if_missing(
                    table=table,
                    known_columns=known_columns,
                    column=column,
                    definition=definition,
                )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_koch_sessions_sequence_stage
            ON koch_sessions(sequence_key, stage_index, finished_at)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_koch_sessions_finished_at
            ON koch_sessions(finished_at)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_koch_char_results_session_result
            ON koch_char_results(koch_session_id, result)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_koch_key_events_session
            ON koch_key_events(koch_session_id, event_index)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_koch_progress_snapshots_sequence_created
            ON koch_progress_snapshots(sequence_key, created_at)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_koch_progress_snapshots_session
            ON koch_progress_snapshots(koch_session_id)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_koch_skill_snapshots_created
            ON koch_skill_snapshots(created_at)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_koch_skill_snapshots_session
            ON koch_skill_snapshots(koch_session_id)
            """
        )

        self.conn.commit()


    def _schema_is_compatible(self) -> bool:
        """Return True if the existing database looks usable by this version.

        This is a safety check, not a migration system. If the database is
        missing required tables or columns, the app will move it aside and
        create a clean database.
        """

        try:
            required_columns: dict[str, set[str]] = {
                "sessions": {
                    "id",
                    "started_at",
                    "finished_at",
                    "target",
                    "entered",
                    "source",
                    "finish_reason",
                    "practice_id",
                    "round_number",
                    "accuracy",
                    "cleanliness",
                    "overall_score",
                    "speed_score",
                    "timing_score",
                    "timing_element_score",
                    "timing_gap_score",
                    "timing_ratio_score",
                    "timing_dot_consistency",
                    "timing_dash_consistency",
                    "timing_intra_gap_score",
                    "timing_letter_gap_score",
                    "timing_word_gap_score",
                    "profile_eligible",
                    "profile_reject_reason",
                    "profile_max_element_units",
                    "profile_max_gap_units",
                    "correct_count",
                    "error_count",
                    "substitutions",
                    "insertions",
                    "deletions",
                    "length_target",
                    "length_entered",
                    "elapsed_us",
                    "standard_time_us",
                    "time_ok",
                    "avg_wpm",
                    "gross_wpm",
                    "net_wpm",
                    "avg_dit_us",
                    "dit_sd_us",
                    "straight_dot_us",
                    "straight_dot_sd_us",
                    "straight_dash_us",
                    "straight_dash_sd_us",
                    "straight_dash_dot_ratio",
                    "avg_letter_gap_us",
                    "letter_gap_sd_us",
                    "avg_word_gap_us",
                    "word_gap_sd_us",
                    "settings_json",
                },
                "practices": {
                    "id",
                    "started_at",
                    "finished_at",
                    "status",
                    "planned_rounds",
                    "completed_rounds",
                    "total_elapsed_us",
                    "total_standard_time_us",
                    "settings_json",
                },
                "events": {
                    "id",
                    "session_id",
                    "event_index",
                    "event_type",
                    "event_json",
                },
                "char_results": {
                    "id",
                    "session_id",
                    "position_index",
                    "target_char",
                    "entered_char",
                    "result",
                    "entered_code",
                    "source",
                    "char_time_us",
                    "first_element_us",
                    "last_element_us",
                    "gap_before_us",
                    "gap_before_units",
                    "gap_kind",
                    "element_unit_us",
                    "gap_unit_us",
                    "wpm",
                },
                "skill_rating_snapshots": {
                    "id",
                    "created_at",
                    "session_id",
                    "model_version",
                    "recent_sessions",
                    "total_rounds",
                    "used_rounds",
                    "effective_wpm",
                    "avg_accuracy",
                    "avg_cleanliness",
                    "quality_factor",
                    "character_mastery_factor",
                    "coverage_factor",
                    "timing_stability_factor",
                    "sample_confidence",
                    "rating_confidence",
                    "mastery_adjustment",
                    "raw_skill",
                    "level",
                    "level_progress",
                    "title",
                    "details_json",
                },
                "koch_skill_snapshots": {
                    "id",
                    "koch_session_id",
                    "created_at",
                    "model_version",
                    "recent_limit",
                    "sessions_used",
                    "required_sessions",
                    "displayable",
                    "confidence",
                    "level",
                    "raw_level",
                    "display_level",
                    "title_key",
                    "base_sequence_key",
                    "active_char_count",
                    "total_character_count",
                    "classic_active_count",
                    "lcwo_active_count",
                    "base_level",
                    "average_accuracy",
                    "average_cleanliness",
                    "average_character_wpm",
                    "average_effective_wpm",
                    "average_target_length",
                    "speed_factor",
                    "accuracy_factor",
                    "cleanliness_factor",
                    "length_factor",
                    "normalizer",
                },
                "problem_stats": {
                    "char",
                    "attempts",
                    "errors",
                    "last_seen_at",
                },
                "timing_profile_state": {
                    "source",
                    "updated_at",
                    "element_unit_us",
                    "gap_unit_us",
                    "dot_us",
                    "dash_us",
                    "dash_dot_ratio",
                    "letter_gap_us",
                    "word_gap_us",
                    "element_confidence",
                    "gap_confidence",
                    "sample_rounds",
                    "sample_events",
                    "updated_from_session_id",
                },
            }

            cur = self.conn.cursor()

            table_rows = cur.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()

            existing_tables = {str(row["name"]) for row in table_rows}

            for table_name, columns in required_columns.items():
                if table_name not in existing_tables:
                    return False

                existing_columns = self._column_names(table_name)

                if not columns.issubset(existing_columns):
                    return False

            return True

        except Exception:
            return False


    def _replace_incompatible_database(self) -> Path:
        """Move an incompatible database aside and open a fresh connection."""

        try:
            self.conn.close()
        except Exception:
            pass

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.path.with_name(
            f"{self.path.stem}.incompatible_{timestamp}{self.path.suffix}"
        )

        counter = 1
        while backup_path.exists():
            backup_path = self.path.with_name(
                f"{self.path.stem}.incompatible_{timestamp}_{counter}{self.path.suffix}"
            )
            counter += 1

        self.path.replace(backup_path)

        for suffix in ("-wal", "-shm"):
            sidecar_path = Path(str(self.path) + suffix)

            if not sidecar_path.exists():
                continue

            sidecar_backup_path = Path(str(backup_path) + suffix)

            try:
                sidecar_path.replace(sidecar_backup_path)
            except Exception:
                try:
                    sidecar_path.unlink()
                except Exception:
                    pass

        self.conn = self._connect()
        return backup_path
    

    def _write_schema_version(self) -> None:
        cur = self.conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            INSERT OR REPLACE INTO app_meta (key, value)
            VALUES (?, ?)
            """,
            (SCHEMA_META_KEY, str(SCHEMA_VERSION)),
        )

        self.conn.commit()

    def init_schema(self) -> None:
        cur = self.conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS practices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL DEFAULT 'in_progress',
                planned_rounds INTEGER NOT NULL DEFAULT 1,
                completed_rounds INTEGER NOT NULL DEFAULT 0,
                total_elapsed_us INTEGER NOT NULL DEFAULT 0,
                total_standard_time_us INTEGER NOT NULL DEFAULT 0,
                settings_json TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                target TEXT NOT NULL,
                entered TEXT NOT NULL,
                source TEXT NOT NULL,
                finish_reason TEXT NOT NULL,

                practice_id INTEGER,
                round_number INTEGER NOT NULL DEFAULT 1,

                accuracy REAL NOT NULL,
                cleanliness REAL NOT NULL DEFAULT 0,
                overall_score REAL NOT NULL DEFAULT 0,
                speed_score REAL,
                timing_score REAL,

                timing_element_score REAL,
                timing_gap_score REAL,
                timing_ratio_score REAL,
                timing_dot_consistency REAL,
                timing_dash_consistency REAL,
                timing_intra_gap_score REAL,
                timing_letter_gap_score REAL,
                timing_word_gap_score REAL,

                profile_eligible INTEGER NOT NULL DEFAULT 1,
                profile_reject_reason TEXT,
                profile_max_element_units REAL,
                profile_max_gap_units REAL,

                correct_count INTEGER NOT NULL,
                error_count INTEGER NOT NULL,
                substitutions INTEGER NOT NULL,
                insertions INTEGER NOT NULL,
                deletions INTEGER NOT NULL,
                length_target INTEGER NOT NULL,
                length_entered INTEGER NOT NULL,

                elapsed_us INTEGER,
                standard_time_us INTEGER,
                time_ok INTEGER,

                avg_wpm REAL,
                gross_wpm REAL,
                net_wpm REAL,

                avg_dit_us REAL,
                dit_sd_us REAL,

                straight_dot_us REAL,
                straight_dot_sd_us REAL,
                straight_dash_us REAL,
                straight_dash_sd_us REAL,
                straight_dash_dot_ratio REAL,

                avg_letter_gap_us REAL,
                letter_gap_sd_us REAL,
                avg_word_gap_us REAL,
                word_gap_sd_us REAL,

                settings_json TEXT NOT NULL,

                FOREIGN KEY(practice_id) REFERENCES practices(id)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                event_index INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_json TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_events_event_type
            ON events(event_type)
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS char_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                position_index INTEGER NOT NULL,
                target_char TEXT,
                entered_char TEXT,
                result TEXT NOT NULL,
                entered_code TEXT,
                source TEXT,

                char_time_us INTEGER,
                first_element_us INTEGER,
                last_element_us INTEGER,

                gap_before_us INTEGER,
                gap_before_units REAL,
                gap_kind TEXT,

                element_unit_us REAL,
                gap_unit_us REAL,

                wpm REAL,

                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_char_results_session_source_result
            ON char_results(session_id, source, result)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_skill_recent
            ON sessions(id, length_target, elapsed_us, accuracy, cleanliness)
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_rating_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id INTEGER,

                model_version INTEGER NOT NULL DEFAULT 1,

                recent_sessions INTEGER NOT NULL,
                total_rounds INTEGER NOT NULL DEFAULT 0,
                used_rounds INTEGER NOT NULL,

                effective_wpm REAL,
                avg_accuracy REAL,
                avg_cleanliness REAL,

                quality_factor REAL NOT NULL,
                character_mastery_factor REAL NOT NULL,
                coverage_factor REAL NOT NULL,
                timing_stability_factor REAL NOT NULL,

                sample_confidence REAL NOT NULL DEFAULT 0,
                rating_confidence REAL NOT NULL DEFAULT 0,
                mastery_adjustment REAL NOT NULL DEFAULT 1,

                raw_skill REAL,
                level INTEGER NOT NULL,
                level_progress REAL NOT NULL DEFAULT 0,
                title TEXT NOT NULL,

                details_json TEXT NOT NULL,

                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_skill_rating_snapshots_created_at
            ON skill_rating_snapshots(created_at)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_skill_rating_snapshots_session_id
            ON skill_rating_snapshots(session_id)
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS problem_stats (
                char TEXT PRIMARY KEY,
                attempts INTEGER NOT NULL DEFAULT 0,
                errors INTEGER NOT NULL DEFAULT 0,
                last_seen_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS timing_profile_state (
                source TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL,

                element_unit_us REAL,
                gap_unit_us REAL,

                dot_us REAL,
                dash_us REAL,
                dash_dot_ratio REAL,

                letter_gap_us REAL,
                word_gap_us REAL,

                element_confidence REAL NOT NULL DEFAULT 0,
                gap_confidence REAL NOT NULL DEFAULT 0,

                sample_rounds INTEGER NOT NULL DEFAULT 0,
                sample_events INTEGER NOT NULL DEFAULT 0,
                updated_from_session_id INTEGER
            )
            """
        )

        self.conn.commit()


    def _column_names(self, table: str) -> set[str]:
        cur = self.conn.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cur.fetchall()}
    
    def create_practice(
        self,
        started_at: datetime,
        planned_rounds: int,
        settings: ChallengeSettings,
    ) -> int:
        cur = self.conn.cursor()

        cur.execute(
            """
            INSERT INTO practices (
                started_at,
                finished_at,
                status,
                planned_rounds,
                completed_rounds,
                total_elapsed_us,
                total_standard_time_us,
                settings_json
            ) VALUES (?, NULL, 'in_progress', ?, 0, 0, 0, ?)
            """,
            (
                started_at.isoformat(timespec="seconds"),
                max(1, int(planned_rounds)),
                json.dumps(asdict(settings), ensure_ascii=False),
            ),
        )

        self.conn.commit()

        if cur.lastrowid is None:
            raise RuntimeError("Practice insert failed: SQLite did not return lastrowid.")

        practice_id = int(cur.lastrowid)
        log_app_event(
            "app.database.practice_created",
            message="Practice row created.",
            context={
                "practice_id": practice_id,
                "planned_rounds": max(1, int(planned_rounds)),
                "settings": summarize_challenge_settings(settings),
            },
        )
        return practice_id

    def refresh_practice_progress(self, practice_id: int) -> None:
        try:
            cur = self.conn.cursor()
            cur.execute("BEGIN")
            self._refresh_practice_progress_inside_transaction(int(practice_id))
            self.conn.commit()
            log_app_event(
                "app.database.practice_progress_refreshed",
                message="Practice progress refreshed.",
                context={"practice_id": int(practice_id)},
            )

        except Exception as exc:
            self.conn.rollback()
            log_app_exception(
                "app.database.practice_progress_refresh_failed",
                exc,
                message="Practice progress refresh failed.",
                context={"practice_id": int(practice_id)},
            )
            raise

    def finish_practice(self, practice_id: int | None, status: str) -> None:
        if practice_id is None:
            return

        status = str(status or "").strip().lower()

        if status not in {"completed", "stopped", "interrupted", "modified"}:
            status = "stopped"

        try:
            cur = self.conn.cursor()
            cur.execute("BEGIN")

            self._refresh_practice_progress_inside_transaction(int(practice_id))

            cur.execute(
                """
                UPDATE practices
                SET
                    status = ?,
                    finished_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    datetime.now().isoformat(timespec="seconds"),
                    int(practice_id),
                ),
            )

            self.conn.commit()
            log_app_event(
                "app.database.practice_finished",
                message="Practice row finished.",
                context={"practice_id": int(practice_id), "status": status},
            )

        except Exception as exc:
            self.conn.rollback()
            log_app_exception(
                "app.database.practice_finish_failed",
                exc,
                message="Practice finish failed.",
                context={"practice_id": int(practice_id), "status": status},
            )
            raise

    def _refresh_practice_progress_inside_transaction(self, practice_id: int) -> None:
        cur = self.conn.cursor()

        row = cur.execute(
            """
            SELECT
                COUNT(*) AS completed_rounds,
                COALESCE(SUM(elapsed_us), 0) AS total_elapsed_us,
                COALESCE(SUM(standard_time_us), 0) AS total_standard_time_us
            FROM sessions
            WHERE practice_id = ?
            """,
            (int(practice_id),),
        ).fetchone()

        if row is None:
            return

        completed_rounds = int(row["completed_rounds"] or 0)
        total_elapsed_us = int(row["total_elapsed_us"] or 0)
        total_standard_time_us = int(row["total_standard_time_us"] or 0)

        cur.execute(
            """
            UPDATE practices
            SET
                completed_rounds = ?,
                total_elapsed_us = ?,
                total_standard_time_us = ?
            WHERE id = ?
            """,
            (
                completed_rounds,
                total_elapsed_us,
                total_standard_time_us,
                int(practice_id),
            ),
        )

        practice_row = cur.execute(
            """
            SELECT status, planned_rounds
            FROM practices
            WHERE id = ?
            """,
            (int(practice_id),),
        ).fetchone()

        if practice_row is not None:
            status = str(practice_row["status"] or "")
            planned_rounds = int(practice_row["planned_rounds"] or 0)

            if (
                status == "completed"
                and planned_rounds > 0
                and completed_rounds < planned_rounds
            ):
                cur.execute(
                    """
                    UPDATE practices
                    SET status = 'modified'
                    WHERE id = ?
                    """,
                    (int(practice_id),),
                )
                log_app_event(
                    "app.database.practice_status_modified_after_session_change",
                    level="warning",
                    message="Completed practice was marked modified after related session changes.",
                    context={
                        "practice_id": int(practice_id),
                        "planned_rounds": planned_rounds,
                        "completed_rounds": completed_rounds,
                    },
                )

    def ensure_practice_consistency(self) -> int:
        if not self._table_exists("sessions") or not self._table_exists("practices"):
            return 0

        if "practice_id" not in self._column_names("sessions"):
            return 0

        cur = self.conn.cursor()

        rows = cur.execute(
            """
            SELECT
                id,
                started_at,
                finished_at,
                settings_json,
                elapsed_us,
                standard_time_us
            FROM sessions
            WHERE practice_id IS NULL
            ORDER BY id ASC
            """
        ).fetchall()

        if not rows:
            return 0

        try:
            cur.execute("BEGIN")

            for row in rows:
                cur.execute(
                    """
                    INSERT INTO practices (
                        started_at,
                        finished_at,
                        status,
                        planned_rounds,
                        completed_rounds,
                        total_elapsed_us,
                        total_standard_time_us,
                        settings_json
                    ) VALUES (?, ?, 'completed', 1, 1, ?, ?, ?)
                    """,
                    (
                        row["started_at"],
                        row["finished_at"],
                        int(row["elapsed_us"] or 0),
                        int(row["standard_time_us"] or 0),
                        row["settings_json"],
                    ),
                )

                practice_id = cur.lastrowid

                if practice_id is None:
                    raise RuntimeError("Practice insert failed during consistency repair.")

                cur.execute(
                    """
                    UPDATE sessions
                    SET
                        practice_id = ?,
                        round_number = 1
                    WHERE id = ?
                    """,
                    (
                        int(practice_id),
                        int(row["id"]),
                    ),
                )

            self.conn.commit()
            repaired = len(rows)
            log_app_event(
                "app.database.practice_consistency_repaired",
                level="warning",
                message="Legacy sessions without practice ids were repaired.",
                context={"repaired_count": repaired},
            )
            return repaired

        except Exception as exc:
            self.conn.rollback()
            log_app_exception(
                "app.database.practice_consistency_repair_failed",
                exc,
                message="Practice consistency repair failed.",
            )
            raise

    def mark_in_progress_practices_interrupted(self) -> int:
        if not self._table_exists("practices"):
            return 0

        cur = self.conn.cursor()

        rows = cur.execute(
            """
            SELECT id
            FROM practices
            WHERE status = 'in_progress'
            ORDER BY id ASC
            """
        ).fetchall()

        if not rows:
            return 0

        finished_at = datetime.now().isoformat(timespec="seconds")

        try:
            cur.execute("BEGIN")

            for row in rows:
                practice_id = int(row["id"])

                self._refresh_practice_progress_inside_transaction(practice_id)

                cur.execute(
                    """
                    UPDATE practices
                    SET
                        status = 'interrupted',
                        finished_at = COALESCE(finished_at, ?)
                    WHERE id = ?
                    """,
                    (
                        finished_at,
                        practice_id,
                    ),
                )

            self.conn.commit()
            interrupted = len(rows)
            log_app_event(
                "app.database.in_progress_marked_interrupted",
                level="warning",
                message="In-progress practices from a previous run were marked interrupted.",
                context={
                    "interrupted_count": interrupted,
                    "finished_at": finished_at,
                },
            )
            return interrupted

        except Exception as exc:
            self.conn.rollback()
            log_app_exception(
                "app.database.in_progress_interrupt_failed",
                exc,
                message="Marking in-progress practices as interrupted failed.",
            )
            raise

    def save_session(
        self,
        started_at: datetime,
        summary: ScoreSummary,
        settings: ChallengeSettings,
        events: List[Dict[str, Any]],
        char_results: List[CharacterResult],
        practice_id: int,
        round_number: int,
    ) -> int:
        finished_at = datetime.now()
        cur = self.conn.cursor()

        log_app_event(
            "app.database.session_save_started",
            message="Session save transaction started.",
            context={
                "practice_id": int(practice_id),
                "round_number": max(1, int(round_number)),
                "event_count": len(events),
                "char_result_count": len(char_results),
                "summary": summarize_score_summary(summary),
                "settings": summarize_challenge_settings(settings),
            },
        )

        try:
            cur.execute(
                """
                INSERT INTO sessions (
                    started_at,
                    finished_at,
                    target,
                    entered,
                    source,
                    finish_reason,
                    practice_id,
                    round_number,

                    accuracy,
                    cleanliness,
                    overall_score,
                    speed_score,
                    timing_score,

                    timing_element_score,
                    timing_gap_score,
                    timing_ratio_score,
                    timing_dot_consistency,
                    timing_dash_consistency,
                    timing_intra_gap_score,
                    timing_letter_gap_score,
                    timing_word_gap_score,

                    profile_eligible,
                    profile_reject_reason,
                    profile_max_element_units,
                    profile_max_gap_units,

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

                    avg_dit_us,
                    dit_sd_us,

                    straight_dot_us,
                    straight_dot_sd_us,
                    straight_dash_us,
                    straight_dash_sd_us,
                    straight_dash_dot_ratio,

                    avg_letter_gap_us,
                    letter_gap_sd_us,
                    avg_word_gap_us,
                    word_gap_sd_us,

                    settings_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    started_at.isoformat(timespec="seconds"),
                    finished_at.isoformat(timespec="seconds"),
                    summary.target,
                    summary.entered,
                    summary.source,
                    summary.finish_reason,
                    int(practice_id),
                    max(1, int(round_number)),

                    summary.accuracy,
                    summary.cleanliness,
                    summary.overall_score,
                    summary.speed_score,
                    summary.timing_score,

                    summary.timing_element_score,
                    summary.timing_gap_score,
                    summary.timing_ratio_score,
                    summary.timing_dot_consistency,
                    summary.timing_dash_consistency,
                    summary.timing_intra_gap_score,
                    summary.timing_letter_gap_score,
                    summary.timing_word_gap_score,

                    1 if summary.profile_eligible else 0,
                    summary.profile_reject_reason,
                    summary.profile_max_element_units,
                    summary.profile_max_gap_units,

                    summary.correct_count,
                    summary.error_count,
                    summary.substitutions,
                    summary.insertions,
                    summary.deletions,
                    summary.length_target,
                    summary.length_entered,

                    summary.elapsed_us,
                    summary.standard_time_us,
                    None if summary.time_ok is None else int(summary.time_ok),

                    summary.avg_wpm,
                    summary.gross_wpm,
                    summary.net_wpm,

                    summary.avg_dit_us,
                    summary.dit_sd_us,

                    summary.straight_dot_us,
                    summary.straight_dot_sd_us,
                    summary.straight_dash_us,
                    summary.straight_dash_sd_us,
                    summary.straight_dash_dot_ratio,

                    summary.avg_letter_gap_us,
                    summary.letter_gap_sd_us,
                    summary.avg_word_gap_us,
                    summary.word_gap_sd_us,

                    json.dumps(asdict(settings), ensure_ascii=False),
                ),
            )

            if cur.lastrowid is None:
                raise RuntimeError("Session insert failed: SQLite did not return lastrowid.")

            session_id = cur.lastrowid

            for index, event in enumerate(events):
                cur.execute(
                    """
                    INSERT INTO events (
                        session_id,
                        event_index,
                        event_type,
                        event_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        index,
                        str(event.get("type", "unknown")),
                        json.dumps(event, ensure_ascii=False),
                    ),
                )

            now = finished_at.isoformat(timespec="seconds")

            for result in char_results:
                gap_kind = (
                    None
                    if result.gap_kind is None
                    else str(result.gap_kind)
                )

                cur.execute(
                    """
                    INSERT INTO char_results (
                        session_id,
                        position_index,
                        target_char,
                        entered_char,
                        result,
                        entered_code,
                        source,

                        char_time_us,
                        first_element_us,
                        last_element_us,

                        gap_before_us,
                        gap_before_units,
                        gap_kind,

                        element_unit_us,
                        gap_unit_us,

                        wpm
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        result.position_index,
                        result.target_char,
                        result.entered_char,
                        result.result,
                        result.entered_code,
                        result.source,

                        result.char_time_us,
                        result.first_element_us,
                        result.last_element_us,

                        result.gap_before_us,
                        result.gap_before_units,
                        gap_kind,

                        result.element_unit_us,
                        result.gap_unit_us,

                        result.wpm,
                    ),
                )

                if result.target_char and result.target_char != " ":
                    cur.execute(
                        """
                        INSERT INTO problem_stats (
                            char,
                            attempts,
                            errors,
                            last_seen_at
                        ) VALUES (?, 1, ?, ?)
                        ON CONFLICT(char) DO UPDATE SET
                            attempts = attempts + 1,
                            errors = errors + excluded.errors,
                            last_seen_at = excluded.last_seen_at
                        """,
                        (
                            result.target_char,
                            0 if result.result == "correct" else 1,
                            now,
                        ),
                    )

            self.conn.commit()
            log_app_event(
                "app.database.session_saved",
                message="Session save transaction committed.",
                context={
                    "session_id": int(session_id),
                    "practice_id": int(practice_id),
                    "round_number": max(1, int(round_number)),
                    "event_count": len(events),
                    "char_result_count": len(char_results),
                    "summary": summarize_score_summary(summary),
                },
            )
            return session_id

        except Exception as exc:
            self.conn.rollback()
            log_app_exception(
                "app.database.session_save_failed",
                exc,
                message="Session save transaction failed.",
                context={
                    "practice_id": int(practice_id),
                    "round_number": max(1, int(round_number)),
                    "event_count": len(events),
                    "char_result_count": len(char_results),
                    "summary": summarize_score_summary(summary),
                },
            )
            raise

    def koch_progress(self, sequence_key: str) -> Optional[sqlite3.Row]:
        self.ensure_koch_schema()

        cur = self.conn.cursor()
        row = cur.execute(
            """
            SELECT *
            FROM koch_progress
            WHERE sequence_key = ?
            """,
            (str(sequence_key or "classic"),),
        ).fetchone()

        return row

    def save_koch_session(
        self,
        started_at: datetime,
        finished_at: datetime,
        result: Any,
        typed_events: List[Dict[str, Any]] | None = None,
        target_schedule: List[Dict[str, Any]] | None = None,
    ) -> int:
        """Persist one Koch receive-practice session and update guided progress."""

        self.ensure_koch_schema()

        typed_events = typed_events or []
        target_schedule = target_schedule or []
        cur = self.conn.cursor()
        settings_json = dict(getattr(result, "settings_json", {}) or {})

        try:
            koch_columns = [
                "started_at",
                "finished_at",
                "mode",
                "sequence_key",
                "stage_index",
                "active_chars",
                "new_stage_char",
                "target_text",
                "entered_text",
                "target_length",
                "entered_length",
                "character_wpm",
                "effective_wpm",
                "tone_hz",
                "volume_percent",
                "duration_ms",
                "pass_accuracy",
                "pass_cleanliness",
                "new_char_min_attempts",
                "new_char_min_accuracy",
                "correct_count",
                "error_count",
                "substitutions",
                "insertions",
                "deletions",
                "accuracy",
                "aligned_accuracy",
                "time_aligned_accuracy",
                "timing_fit",
                "cleanliness",
                "new_char_accuracy",
                "new_char_attempts",
                "score",
                "speed_factor",
                "coverage_factor",
                "level_estimate",
                "pass_eligible",
                "passed",
                "advanced_from_stage",
                "advanced_to_stage",
                "pass_reason",
                "settings_json",
                "target_schedule_json",
            ]
            koch_values = [
                started_at.isoformat(timespec="seconds"),
                finished_at.isoformat(timespec="seconds"),
                result.mode,
                result.sequence_key,
                int(result.stage_index),
                result.active_chars,
                result.new_stage_char,
                result.target,
                result.entered,
                int(result.length_target),
                int(result.length_entered),
                int(result.character_wpm),
                int(result.effective_wpm),
                int(settings_json.get("tone_hz", 600)),
                int(settings_json.get("volume_percent", 70)),
                int(result.duration_ms),
                float(settings_json.get("pass_accuracy", 90.0)),
                float(settings_json.get("pass_cleanliness", 85.0)),
                int(settings_json.get("new_char_min_attempts", 8)),
                float(settings_json.get("new_char_min_accuracy", 80.0)),
                int(result.correct_count),
                int(result.error_count),
                int(result.substitutions),
                int(result.insertions),
                int(result.deletions),
                float(result.accuracy),
                float(getattr(result, "aligned_accuracy", result.accuracy)),
                float(getattr(result, "time_aligned_accuracy", result.accuracy)),
                float(getattr(result, "timing_fit", 100.0 if result.accuracy > 0 else 0.0)),
                float(result.cleanliness),
                result.new_char_accuracy,
                int(result.new_char_attempts),
                float(result.score),
                float(result.speed_factor),
                float(result.coverage_factor),
                float(result.level_estimate),
                1 if result.pass_eligible else 0,
                1 if result.passed else 0,
                result.advanced_from_stage,
                result.advanced_to_stage,
                result.pass_reason,
                json.dumps(settings_json, ensure_ascii=False, sort_keys=True),
                json.dumps(target_schedule, ensure_ascii=False),
            ]

            placeholders = ", ".join(["?"] * len(koch_columns))
            cur.execute(
                f"""
                INSERT INTO koch_sessions (
                    {", ".join(koch_columns)}
                ) VALUES ({placeholders})
                """,
                tuple(koch_values),
            )

            session_id = int(cur.lastrowid)

            for char_result in getattr(result, "character_results", []) or []:
                cur.execute(
                    """
                    INSERT INTO koch_char_results (
                        koch_session_id,
                        position_index,
                        target_char,
                        entered_char,
                        result,
                        target_stage_index,
                        is_new_stage_char,
                        expected_start_ms,
                        expected_end_ms,
                        typed_at_ms,
                        latency_ms,
                        timing_weight,
                        timing_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        int(char_result.position_index),
                        char_result.target_char,
                        char_result.entered_char,
                        char_result.result,
                        char_result.target_stage_index,
                        1 if char_result.is_new_stage_char else 0,
                        char_result.expected_start_ms,
                        char_result.expected_end_ms,
                        char_result.typed_at_ms,
                        char_result.latency_ms,
                        float(getattr(char_result, "timing_weight", 1.0)),
                        str(getattr(char_result, "timing_status", "") or ""),
                    ),
                )

            for event_index, event in enumerate(typed_events):
                cur.execute(
                    """
                    INSERT INTO koch_key_events (
                        koch_session_id,
                        event_index,
                        key,
                        char,
                        typed_at_ms,
                        event_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        event_index,
                        str(event.get("key", "")),
                        event.get("char"),
                        event.get("typed_at_ms"),
                        json.dumps(event, ensure_ascii=False, sort_keys=True),
                    ),
                )

            now = datetime.now().isoformat(timespec="seconds")
            existing = cur.execute(
                """
                SELECT *
                FROM koch_progress
                WHERE sequence_key = ?
                """,
                (result.sequence_key,),
            ).fetchone()

            guided_min_stage = max(1, int(getattr(config, "DEFAULT_KOCH_GUIDED_MIN_STAGE", 2)))
            demote_after_failures = max(
                1,
                int(getattr(config, "DEFAULT_KOCH_GUIDED_DEMOTE_AFTER_FAILURES", 5)),
            )

            current_unlocked = guided_min_stage
            current_stage = guided_min_stage
            guided_fail_streak = 0
            guided_fail_stage: int | None = None
            last_demoted_from_stage: int | None = None
            last_demoted_to_stage: int | None = None
            last_demoted_at: str | None = None
            total_sessions = 0
            total_seconds = 0

            if existing is not None:
                current_unlocked = max(guided_min_stage, int(existing["guided_unlocked_stage"]))
                current_stage = max(guided_min_stage, int(existing["guided_current_stage"]))
                guided_fail_streak = max(0, int(existing["guided_fail_streak"]))
                if existing["guided_fail_stage"] is not None:
                    guided_fail_stage = int(existing["guided_fail_stage"])
                if existing["last_demoted_from_stage"] is not None:
                    last_demoted_from_stage = int(existing["last_demoted_from_stage"])
                if existing["last_demoted_to_stage"] is not None:
                    last_demoted_to_stage = int(existing["last_demoted_to_stage"])
                last_demoted_at = existing["last_demoted_at"]
                total_sessions = int(existing["total_sessions"])
                total_seconds = int(existing["total_practice_seconds"])

            current_unlocked = max(current_unlocked, current_stage)
            is_guided = str(getattr(result, "mode", "")).strip().lower() == "guided"
            result_stage = max(guided_min_stage, int(getattr(result, "stage_index", current_stage)))

            next_unlocked = current_unlocked
            next_stage = current_stage
            next_fail_streak = guided_fail_streak
            next_fail_stage = guided_fail_stage
            demoted_from_stage: int | None = None
            demoted_to_stage: int | None = None
            demotion_reason = ""

            if is_guided and bool(getattr(result, "passed", False)):
                advanced_to_stage = getattr(result, "advanced_to_stage", None)
                target_stage = int(advanced_to_stage) if advanced_to_stage is not None else result_stage
                next_unlocked = max(current_unlocked, target_stage)
                next_stage = max(current_stage, target_stage)
                next_fail_streak = 0
                next_fail_stage = None
            elif (
                is_guided
                and bool(getattr(result, "pass_eligible", False))
                and result_stage == current_stage
            ):
                if next_fail_stage != current_stage:
                    next_fail_streak = 1
                    next_fail_stage = current_stage
                else:
                    next_fail_streak += 1

                if next_fail_streak >= demote_after_failures:
                    if current_stage > guided_min_stage:
                        demoted_from_stage = current_stage
                        demoted_to_stage = current_stage - 1
                        demotion_reason = "guided_failure_streak"
                        next_stage = demoted_to_stage
                        next_fail_streak = 0
                        next_fail_stage = None
                        last_demoted_from_stage = demoted_from_stage
                        last_demoted_to_stage = demoted_to_stage
                        last_demoted_at = now
                    else:
                        next_fail_streak = demote_after_failures
                        next_fail_stage = current_stage

            setattr(result, "demoted_from_stage", demoted_from_stage)
            setattr(result, "demoted_to_stage", demoted_to_stage)
            setattr(result, "demotion_reason", demotion_reason)
            setattr(result, "guided_fail_streak_after", next_fail_streak)

            cur.execute(
                """
                UPDATE koch_sessions
                SET
                    demoted_from_stage = ?,
                    demoted_to_stage = ?,
                    demotion_reason = ?,
                    guided_fail_streak_after = ?
                WHERE id = ?
                """,
                (
                    demoted_from_stage,
                    demoted_to_stage,
                    demotion_reason,
                    int(next_fail_streak),
                    int(session_id),
                ),
            )

            total_sessions += 1
            total_seconds += max(0, int(result.duration_ms // 1000))

            cur.execute(
                """
                INSERT INTO koch_progress (
                    sequence_key,
                    guided_unlocked_stage,
                    guided_current_stage,
                    guided_fail_streak,
                    guided_fail_stage,
                    last_demoted_from_stage,
                    last_demoted_to_stage,
                    last_demoted_at,
                    total_sessions,
                    total_practice_seconds,
                    last_session_id,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sequence_key) DO UPDATE SET
                    guided_unlocked_stage = excluded.guided_unlocked_stage,
                    guided_current_stage = excluded.guided_current_stage,
                    guided_fail_streak = excluded.guided_fail_streak,
                    guided_fail_stage = excluded.guided_fail_stage,
                    last_demoted_from_stage = excluded.last_demoted_from_stage,
                    last_demoted_to_stage = excluded.last_demoted_to_stage,
                    last_demoted_at = excluded.last_demoted_at,
                    total_sessions = excluded.total_sessions,
                    total_practice_seconds = excluded.total_practice_seconds,
                    last_session_id = excluded.last_session_id,
                    updated_at = excluded.updated_at
                """,
                (
                    result.sequence_key,
                    int(next_unlocked),
                    int(next_stage),
                    int(next_fail_streak),
                    next_fail_stage,
                    last_demoted_from_stage,
                    last_demoted_to_stage,
                    last_demoted_at,
                    int(total_sessions),
                    int(total_seconds),
                    int(session_id),
                    now,
                ),
            )

            cur.execute(
                """
                INSERT INTO koch_progress_snapshots (
                    koch_session_id,
                    created_at,
                    sequence_key,
                    mode,
                    session_stage_index,
                    stage_before,
                    stage_after,
                    unlocked_before,
                    unlocked_after,
                    active_chars,
                    active_char_count,
                    target_length,
                    entered_length,
                    character_wpm,
                    effective_wpm,
                    tone_hz,
                    volume_percent,
                    duration_ms,
                    pass_accuracy,
                    pass_cleanliness,
                    new_char_min_attempts,
                    new_char_min_accuracy,
                    guided_fail_streak_before,
                    guided_fail_streak_after,
                    guided_fail_stage_before,
                    guided_fail_stage_after,
                    passed,
                    pass_eligible,
                    demoted_from_stage,
                    demoted_to_stage,
                    demotion_reason,
                    advanced_from_stage,
                    advanced_to_stage,
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
                    settings_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(session_id),
                    now,
                    result.sequence_key,
                    result.mode,
                    int(result_stage),
                    int(current_stage),
                    int(next_stage),
                    int(current_unlocked),
                    int(next_unlocked),
                    result.active_chars,
                    len(result.active_chars or ""),
                    int(result.length_target),
                    int(result.length_entered),
                    int(result.character_wpm),
                    int(result.effective_wpm),
                    int(settings_json.get("tone_hz", 600)),
                    int(settings_json.get("volume_percent", 70)),
                    int(result.duration_ms),
                    float(settings_json.get("pass_accuracy", 90.0)),
                    float(settings_json.get("pass_cleanliness", 85.0)),
                    int(settings_json.get("new_char_min_attempts", 8)),
                    float(settings_json.get("new_char_min_accuracy", 80.0)),
                    int(guided_fail_streak),
                    int(next_fail_streak),
                    guided_fail_stage,
                    next_fail_stage,
                    1 if result.passed else 0,
                    1 if result.pass_eligible else 0,
                    demoted_from_stage,
                    demoted_to_stage,
                    demotion_reason,
                    result.advanced_from_stage,
                    result.advanced_to_stage,
                    int(result.correct_count),
                    int(result.error_count),
                    int(result.substitutions),
                    int(result.insertions),
                    int(result.deletions),
                    float(result.accuracy),
                    float(getattr(result, "aligned_accuracy", result.accuracy)),
                    float(getattr(result, "time_aligned_accuracy", result.accuracy)),
                    float(getattr(result, "timing_fit", 100.0 if result.accuracy > 0 else 0.0)),
                    float(result.cleanliness),
                    result.new_char_accuracy,
                    int(result.new_char_attempts),
                    float(result.score),
                    float(result.speed_factor),
                    float(result.coverage_factor),
                    float(result.level_estimate),
                    json.dumps(settings_json, ensure_ascii=False, sort_keys=True),
                ),
            )

            self.conn.commit()
            return session_id

        except Exception as exc:
            self.conn.rollback()
            log_app_exception(
                "app.database.koch_session_save_failed",
                exc,
                level="warning",
                message="Saving Koch receive-practice session failed.",
                context={"sequence_key": getattr(result, "sequence_key", ""), "stage_index": getattr(result, "stage_index", None)},
            )
            raise

    def count_koch_sessions(self) -> int:
        self.ensure_koch_schema()

        cur = self.conn.cursor()
        row = cur.execute("SELECT COUNT(*) AS total FROM koch_sessions").fetchone()
        return int(row["total"] if row is not None else 0)

    def recent_koch_sessions(self, limit: int = 20) -> List[sqlite3.Row]:
        self.ensure_koch_schema()

        cur = self.conn.cursor()
        return cur.execute(
            """
            SELECT *
            FROM koch_sessions
            ORDER BY finished_at DESC, id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()

    def save_koch_skill_snapshot(self, koch_session_id: int | None, summary: Any) -> int:
        """Save the rolling Koch receive-skill state after a Koch session."""

        self.ensure_koch_schema()
        created_at = datetime.now().isoformat(timespec="seconds")
        display_level = (
            int(round(float(getattr(summary, "level", 0.0) or 0.0)))
            if bool(getattr(summary, "displayable", False))
            else None
        )

        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO koch_skill_snapshots (
                koch_session_id,
                created_at,
                model_version,
                recent_limit,
                sessions_used,
                required_sessions,
                displayable,
                confidence,
                level,
                raw_level,
                display_level,
                title_key,
                base_sequence_key,
                active_char_count,
                total_character_count,
                classic_active_count,
                lcwo_active_count,
                base_level,
                average_accuracy,
                average_cleanliness,
                average_character_wpm,
                average_effective_wpm,
                average_target_length,
                speed_factor,
                accuracy_factor,
                cleanliness_factor,
                length_factor,
                normalizer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                koch_session_id,
                created_at,
                int(getattr(config, "KOCH_SKILL_MODEL_VERSION", 2)),
                int(getattr(config, "DEFAULT_KOCH_SKILL_RECENT_ROUNDS", 1000)),
                int(getattr(summary, "sessions_used", 0) or 0),
                int(getattr(summary, "required_sessions", 30) or 30),
                1 if bool(getattr(summary, "displayable", False)) else 0,
                float(getattr(summary, "confidence", 0.0) or 0.0),
                float(getattr(summary, "level", 0.0) or 0.0),
                float(getattr(summary, "raw_level", 0.0) or 0.0),
                display_level,
                str(getattr(summary, "title_key", "") or ""),
                str(getattr(summary, "base_sequence_key", "") or ""),
                int(getattr(summary, "active_char_count", 0) or 0),
                int(getattr(summary, "total_character_count", 0) or 0),
                int(getattr(summary, "classic_active_count", 0) or 0),
                int(getattr(summary, "lcwo_active_count", 0) or 0),
                float(getattr(summary, "base_level", 0.0) or 0.0),
                float(getattr(summary, "average_accuracy", 0.0) or 0.0),
                float(getattr(summary, "average_cleanliness", 0.0) or 0.0),
                float(getattr(summary, "average_character_wpm", 0.0) or 0.0),
                float(getattr(summary, "average_effective_wpm", 0.0) or 0.0),
                float(getattr(summary, "average_target_length", 0.0) or 0.0),
                float(getattr(summary, "speed_factor", 0.0) or 0.0),
                float(getattr(summary, "accuracy_factor", 0.0) or 0.0),
                float(getattr(summary, "cleanliness_factor", 0.0) or 0.0),
                float(getattr(summary, "length_factor", 0.0) or 0.0),
                float(getattr(summary, "normalizer", 0.0) or 0.0),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def recent_koch_skill_snapshots(self, limit: int = 200) -> List[sqlite3.Row]:
        self.ensure_koch_schema()

        cur = self.conn.cursor()
        return cur.execute(
            """
            SELECT *
            FROM koch_skill_snapshots
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()

    def koch_character_stats(
        self,
        recent_sessions: int = 1000,
        limit: int = 50,
    ) -> List[sqlite3.Row]:
        self.ensure_koch_schema()

        cur = self.conn.cursor()
        return cur.execute(
            """
            SELECT
                target_char AS char,
                COUNT(*) AS attempts,
                SUM(CASE WHEN result = 'correct' THEN 1 ELSE 0 END) AS correct,
                SUM(CASE WHEN result != 'correct' THEN 1 ELSE 0 END) AS errors,
                ROUND(
                    SUM(CASE WHEN result != 'correct' THEN 1 ELSE 0 END)
                    * 100.0 / COUNT(*),
                    1
                ) AS error_rate,
                AVG(CASE WHEN latency_ms IS NOT NULL THEN latency_ms ELSE NULL END) AS avg_latency_ms
            FROM koch_char_results
            WHERE koch_session_id IN (
                SELECT id
                FROM koch_sessions
                ORDER BY finished_at DESC, id DESC
                LIMIT ?
            )
            AND target_char IS NOT NULL
            AND target_char != ''
            AND target_char != ' '
            AND result IN ('correct', 'substitution', 'deletion')
            GROUP BY target_char
            HAVING attempts > 0
            ORDER BY error_rate DESC, errors DESC, attempts DESC, char ASC
            LIMIT ?
            """,
            (max(1, int(recent_sessions)), max(1, int(limit))),
        ).fetchall()


    def recent_sessions(self, limit: int = 10) -> List[sqlite3.Row]:
        cur = self.conn.cursor()

        cur.execute(
            """
            SELECT
                id,
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

                elapsed_us,
                avg_wpm,
                gross_wpm,
                net_wpm,

                avg_dit_us,
                dit_sd_us,
                straight_dot_us,
                straight_dot_sd_us,
                straight_dash_us,
                straight_dash_sd_us,
                straight_dash_dot_ratio,

                time_ok
            FROM sessions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

        return list(cur.fetchall())
    
    def session_details(self, session_id: int) -> dict[str, Any] | None:
        """
        Return one practice session with its raw events and character results.

        This is used when the user clicks a row in the latest rounds table and
        wants to load that historical round back into the main view.
        """

        session_id = int(session_id)
        cur = self.conn.cursor()

        session_row = cur.execute(
            """
            SELECT *
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

        if session_row is None:
            return None

        event_rows = cur.execute(
            """
            SELECT
                event_index,
                event_type,
                event_json
            FROM events
            WHERE session_id = ?
            ORDER BY event_index ASC
            """,
            (session_id,),
        ).fetchall()

        events: list[dict[str, Any]] = []

        for row in event_rows:
            try:
                event = json.loads(str(row["event_json"] or "{}"))
            except Exception:
                continue

            if isinstance(event, dict):
                events.append(event)

        char_rows = cur.execute(
            """
            SELECT
                position_index,
                target_char,
                entered_char,
                result,
                entered_code,
                source,

                char_time_us,
                first_element_us,
                last_element_us,

                gap_before_us,
                gap_before_units,
                gap_kind,

                element_unit_us,
                gap_unit_us,

                wpm
            FROM char_results
            WHERE session_id = ?
            ORDER BY position_index ASC
            """,
            (session_id,),
        ).fetchall()

        char_results = [dict(row) for row in char_rows]

        result = dict(session_row)
        result["events"] = events
        result["char_results"] = char_results

        return result
    

    def sessions_for_management(self, limit: int = 1000) -> List[sqlite3.Row]:
        cur = self.conn.cursor()

        cur.execute(
            """
            SELECT
                id,
                finished_at,
                target,
                entered,
                accuracy,
                cleanliness,
                overall_score,
                timing_score,
                error_count,
                elapsed_us
            FROM sessions
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        )

        return list(cur.fetchall())


    def count_sessions_for_delete(
        self,
        *,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> int:
        cur = self.conn.cursor()

        where_parts: list[str] = []
        params: list[Any] = []

        if start_at is not None:
            where_parts.append("finished_at >= ?")
            params.append(start_at)

        if end_at is not None:
            where_parts.append("finished_at <= ?")
            params.append(end_at)

        where_sql = ""
        if where_parts:
            where_sql = "WHERE " + " AND ".join(where_parts)

        row = cur.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM sessions
            {where_sql}
            """,
            params,
        ).fetchone()

        return int(row["count"] or 0)


    def delete_sessions(
        self,
        *,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> int:
        cur = self.conn.cursor()

        where_parts: list[str] = []
        params: list[Any] = []

        if start_at is not None:
            where_parts.append("finished_at >= ?")
            params.append(start_at)

        if end_at is not None:
            where_parts.append("finished_at <= ?")
            params.append(end_at)

        where_sql = ""
        if where_parts:
            where_sql = "WHERE " + " AND ".join(where_parts)

        session_rows = cur.execute(
            f"""
            SELECT id, practice_id
            FROM sessions
            {where_sql}
            """,
            params,
        ).fetchall()

        session_ids = [int(row["id"]) for row in session_rows]

        practice_ids = sorted(
            {
                int(row["practice_id"])
                for row in session_rows
                if row["practice_id"] is not None
            }
        )

        if not session_ids:
            log_app_event(
                "app.database.sessions_delete_skipped_empty",
                message="Session delete requested but no sessions matched.",
                context={"start_at": start_at, "end_at": end_at},
            )
            return 0

        placeholders = ",".join("?" for _ in session_ids)

        try:
            cur.execute("BEGIN")

            if start_at is None and end_at is None:
                cur.execute("DELETE FROM skill_rating_snapshots")
            else:
                cur.execute(
                    f"DELETE FROM skill_rating_snapshots WHERE session_id IN ({placeholders})",
                    session_ids,
                )

            cur.execute(
                f"DELETE FROM events WHERE session_id IN ({placeholders})",
                session_ids,
            )

            cur.execute(
                f"DELETE FROM char_results WHERE session_id IN ({placeholders})",
                session_ids,
            )

            cur.execute(
                f"DELETE FROM sessions WHERE id IN ({placeholders})",
                session_ids,
            )

            if start_at is None and end_at is None:
                cur.execute("DELETE FROM practices")
            else:
                for practice_id in practice_ids:
                    remaining = cur.execute(
                        """
                        SELECT COUNT(*) AS count
                        FROM sessions
                        WHERE practice_id = ?
                        """,
                        (practice_id,),
                    ).fetchone()

                    if int(remaining["count"] or 0) == 0:
                        cur.execute(
                            """
                            DELETE FROM practices
                            WHERE id = ?
                            """,
                            (practice_id,),
                        )
                    else:
                        self._refresh_practice_progress_inside_transaction(practice_id)

            cur.execute("DELETE FROM timing_profile_state")

            self._rebuild_problem_stats_inside_transaction()

            self.conn.commit()

        except Exception as exc:
            self.conn.rollback()
            log_app_exception(
                "app.database.sessions_delete_failed",
                exc,
                message="Session delete transaction failed.",
                context={"start_at": start_at, "end_at": end_at, "session_count": len(session_ids)},
            )
            raise

        deleted_count = len(session_ids)
        log_app_event(
            "app.database.sessions_deleted",
            level="warning",
            message="Practice sessions were deleted.",
            context={"start_at": start_at, "end_at": end_at, "deleted_count": deleted_count},
        )
        return deleted_count
    

    def delete_session_by_id(self, session_id: int) -> int:
        """
        Delete one practice session and all data directly related to it.

        Returns the number of deleted sessions.
        """

        session_id = int(session_id)
        cur = self.conn.cursor()

        session_row = cur.execute(
            """
            SELECT id, practice_id
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

        if session_row is None:
            log_app_event(
                "app.database.session_delete_not_found",
                level="warning",
                message="Single session delete requested but session was not found.",
                context={"session_id": session_id},
            )
            return 0

        practice_id = (
            None
            if session_row["practice_id"] is None
            else int(session_row["practice_id"])
        )

        try:
            cur.execute("BEGIN")

            cur.execute(
                """
                DELETE FROM skill_rating_snapshots
                WHERE session_id = ?
                """,
                (session_id,),
            )

            cur.execute(
                """
                DELETE FROM events
                WHERE session_id = ?
                """,
                (session_id,),
            )

            cur.execute(
                """
                DELETE FROM char_results
                WHERE session_id = ?
                """,
                (session_id,),
            )

            cur.execute(
                """
                DELETE FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            )

            deleted = int(cur.rowcount or 0)

            if practice_id is not None:
                remaining = cur.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM sessions
                    WHERE practice_id = ?
                    """,
                    (practice_id,),
                ).fetchone()

                if int(remaining["count"] or 0) == 0:
                    cur.execute(
                        """
                        DELETE FROM practices
                        WHERE id = ?
                        """,
                        (practice_id,),
                    )
                else:
                    self._refresh_practice_progress_inside_transaction(practice_id)

            cur.execute("DELETE FROM timing_profile_state")

            self._rebuild_problem_stats_inside_transaction()

            self.conn.commit()

        except Exception as exc:
            self.conn.rollback()
            log_app_exception(
                "app.database.session_delete_failed",
                exc,
                message="Single session delete transaction failed.",
                context={"session_id": session_id},
            )
            raise

        log_app_event(
            "app.database.session_deleted",
            level="warning",
            message="Single practice session was deleted.",
            context={"session_id": session_id, "deleted": deleted, "practice_id": practice_id},
        )
        return deleted


    def _rebuild_problem_stats_inside_transaction(self) -> None:
        cur = self.conn.cursor()

        cur.execute("DELETE FROM problem_stats")

        cur.execute(
            """
            INSERT INTO problem_stats (
                char,
                attempts,
                errors,
                last_seen_at
            )
            SELECT
                cr.target_char AS char,
                COUNT(*) AS attempts,
                SUM(CASE WHEN cr.result = 'correct' THEN 0 ELSE 1 END) AS errors,
                MAX(s.finished_at) AS last_seen_at
            FROM char_results cr
            JOIN sessions s ON s.id = cr.session_id
            WHERE cr.target_char IS NOT NULL
            AND cr.target_char != ''
            AND cr.target_char != ' '
            AND cr.result IN ('correct', 'substitution', 'deletion')
            GROUP BY cr.target_char
            """
        )
        
    def keying_event_summary(self) -> Dict[str, int]:
        """Return total tone-event counts by key source.

        Straight tone events are close to physical straight-key presses.
        Iambic tone events are generated Morse elements, not physical paddle presses.
        """

        return self._keying_event_summary_from_connection(self.conn)


    def keying_event_summary_from_file(self) -> Dict[str, int]:
        """Return keying event totals using a separate read-only connection.

        This is safe to call from a background thread because it does not reuse
        the main Tk/UI thread SQLite connection.
        """

        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row

        try:
            return self._keying_event_summary_from_connection(conn)
        finally:
            conn.close()


    def _keying_event_summary_from_connection(
        self,
        conn: sqlite3.Connection,
    ) -> Dict[str, int]:
        """Return keying and produced-character totals from the given connection.

        Tone totals are based on raw telemetry events.

        Produced-character totals are based on recognized entered characters in
        char_results. They include correct, substitution and insertion rows, but
        exclude spaces, empty values, deletions and the decoder unknown character.
        """

        tone_row = conn.execute(
            """
            SELECT
                SUM(
                    CASE
                        WHEN LOWER(COALESCE(json_extract(event_json, '$.src'), '')) = 'straight'
                        THEN 1 ELSE 0
                    END
                ) AS straight_presses,
                SUM(
                    CASE
                        WHEN LOWER(COALESCE(json_extract(event_json, '$.src'), '')) = 'iambic'
                        THEN 1 ELSE 0
                    END
                ) AS iambic_elements,
                COUNT(*) AS tone_total
            FROM events
            WHERE event_type = 'tone'
            """
        ).fetchone()

        char_row = conn.execute(
            """
            SELECT
                SUM(
                    CASE
                        WHEN LOWER(COALESCE(source, '')) = 'straight'
                        THEN 1 ELSE 0
                    END
                ) AS straight_chars,
                SUM(
                    CASE
                        WHEN LOWER(COALESCE(source, '')) = 'iambic'
                        THEN 1 ELSE 0
                    END
                ) AS iambic_chars,
                COUNT(*) AS produced_chars_total
            FROM char_results
            WHERE entered_char IS NOT NULL
              AND entered_char != ''
              AND entered_char != ' '
              AND entered_char != ?
              AND result IN ('correct', 'substitution', 'insertion')
            """,
            (config.DECODER_UNKNOWN_CHAR,),
        ).fetchone()

        return {
            "straight_presses": int(tone_row["straight_presses"] or 0) if tone_row is not None else 0,
            "iambic_elements": int(tone_row["iambic_elements"] or 0) if tone_row is not None else 0,
            "tone_total": int(tone_row["tone_total"] or 0) if tone_row is not None else 0,
            "straight_chars": int(char_row["straight_chars"] or 0) if char_row is not None else 0,
            "iambic_chars": int(char_row["iambic_chars"] or 0) if char_row is not None else 0,
            "produced_chars_total": int(char_row["produced_chars_total"] or 0) if char_row is not None else 0,
        }

    def stats_summary(self, recent_sessions: int = 1000) -> Dict[str, Any]:
        recent_sessions = max(1, int(recent_sessions))

        cur = self.conn.cursor()
        row = cur.execute(
            """
            SELECT
                COUNT(*) AS rounds,

                AVG(accuracy) AS avg_accuracy,
                AVG(cleanliness) AS avg_cleanliness,
                AVG(overall_score) AS avg_overall_score,
                AVG(speed_score) AS avg_speed_score,
                AVG(timing_score) AS avg_timing_score,

                AVG(gross_wpm) AS avg_gross_wpm,
                AVG(net_wpm) AS avg_net_wpm,
                AVG(avg_wpm) AS avg_device_wpm,

                AVG(straight_dash_dot_ratio) AS avg_straight_dash_dot_ratio,

                AVG(
                    CASE
                        WHEN straight_dot_us IS NOT NULL
                        AND straight_dot_us > 0
                        AND straight_dot_sd_us IS NOT NULL
                        THEN straight_dot_sd_us * 100.0 / straight_dot_us
                        ELSE NULL
                    END
                ) AS avg_straight_dot_variation_percent,

                AVG(
                    CASE
                        WHEN straight_dash_us IS NOT NULL
                        AND straight_dash_us > 0
                        AND straight_dash_sd_us IS NOT NULL
                        THEN straight_dash_sd_us * 100.0 / straight_dash_us
                        ELSE NULL
                    END
                ) AS avg_straight_dash_variation_percent,

                AVG(elapsed_us) AS avg_elapsed_us,

                SUM(correct_count) AS total_correct,
                SUM(error_count) AS total_errors,
                SUM(substitutions) AS total_substitutions,
                SUM(insertions) AS total_insertions,
                SUM(deletions) AS total_deletions
            FROM (
                SELECT *
                FROM sessions
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (recent_sessions,),
        ).fetchone()

        if row is None:
            return {
                "rounds": 0,
                "avg_accuracy": None,
                "avg_cleanliness": None,
                "avg_overall_score": None,
                "avg_speed_score": None,
                "avg_timing_score": None,
                "avg_gross_wpm": None,
                "avg_net_wpm": None,
                "avg_device_wpm": None,
                "avg_elapsed_us": None,
                "avg_straight_dash_dot_ratio": None,
                "avg_straight_dot_variation_percent": None,
                "avg_straight_dash_variation_percent": None,
                "total_correct": 0,
                "total_errors": 0,
                "total_substitutions": 0,
                "total_insertions": 0,
                "total_deletions": 0,
            }

        return dict(row)

    def problem_characters(
        self,
        limit: int = 20,
        recent_sessions: int | None = None,
    ) -> List[sqlite3.Row]:
        cur = self.conn.cursor()

        if recent_sessions is not None and recent_sessions > 0:
            cur.execute(
                """
                WITH recent AS (
                    SELECT id
                    FROM sessions
                    ORDER BY id DESC
                    LIMIT ?
                )
                SELECT
                    target_char AS char,
                    COUNT(*) AS attempts,
                    SUM(CASE WHEN result = 'correct' THEN 0 ELSE 1 END) AS errors,
                    ROUND(
                        SUM(CASE WHEN result = 'correct' THEN 0 ELSE 1 END)
                        * 100.0 / COUNT(*),
                        1
                    ) AS error_rate
                FROM char_results
                WHERE session_id IN (SELECT id FROM recent)
                  AND target_char IS NOT NULL
                  AND target_char != ''
                  AND target_char != ' '
                  AND result IN ('correct', 'substitution', 'deletion')
                GROUP BY target_char
                HAVING attempts > 0
                ORDER BY error_rate DESC, errors DESC, attempts DESC
                LIMIT ?
                """,
                (recent_sessions, limit),
            )

            return list(cur.fetchall())

        cur.execute(
            """
            SELECT
                char,
                attempts,
                errors,
                ROUND(errors * 100.0 / attempts, 1) AS error_rate
            FROM problem_stats
            WHERE attempts > 0
            ORDER BY error_rate DESC, errors DESC, attempts DESC
            LIMIT ?
            """,
            (limit,),
        )

        return list(cur.fetchall())

    def problem_chars_for_practice(
        self,
        limit: int = 12,
        recent_sessions: int | None = None,
    ) -> List[str]:
        return [
            row["char"]
            for row in self.problem_characters(limit, recent_sessions)
        ]

    def optimized_wpm_from_recent_sessions(
        self,
        recent_sessions: int = 1000,
        min_accuracy: float = 90.0,
        min_cleanliness: float = 85.0,
        min_target_chars: int | None = None,
    ) -> Dict[str, Any]:
        """Return a robust suggested practice WPM from recent successful rounds.

        The suggestion is based on the best uncapped PARIS median from the two
        dominant key sources:

            max(straight_paris_wpm, iambic_paris_wpm)

        Up to recent_sessions qualified rounds are used per key source. This
        means the function may use up to recent_sessions straight rounds and up
        to recent_sessions iambic rounds.

        WPM is calculated from the target text's Morse timing units and elapsed
        time. Accuracy and cleanliness are quality filters only. Target WPM does
        not cap this suggestion.
        """

        per_source_limit = max(1, int(recent_sessions))

        if min_target_chars is None:
            min_target_chars = int(
                getattr(config, "SKILL_RATING_MIN_TARGET_CHARS", 12)
            )

        min_target_chars = max(1, int(min_target_chars))

        cur = self.conn.cursor()

        rows = cur.execute(
            """
            SELECT
                s.id,
                s.target,
                s.accuracy,
                s.cleanliness,
                s.elapsed_us,
                s.length_target,
                s.settings_json,
                LOWER(cr.source) AS key_source,
                COUNT(*) AS source_count
            FROM sessions s
            JOIN char_results cr ON cr.session_id = s.id
            WHERE COALESCE(
                NULLIF(s.length_target, 0),
                LENGTH(REPLACE(s.target, ' ', ''))
            ) >= ?
              AND s.elapsed_us IS NOT NULL
              AND s.elapsed_us > 0
              AND s.accuracy >= ?
              AND s.cleanliness >= ?
              AND cr.target_char IS NOT NULL
              AND cr.target_char != ''
              AND cr.target_char != ' '
              AND cr.result IN ('correct', 'substitution', 'deletion')
              AND LOWER(cr.source) IN ('straight', 'iambic')
            GROUP BY
                s.id,
                LOWER(cr.source)
            ORDER BY
                s.id DESC,
                source_count DESC,
                CASE LOWER(cr.source)
                    WHEN 'straight' THEN 0
                    ELSE 1
                END ASC
            """,
            (
                int(min_target_chars),
                float(min_accuracy),
                float(min_cleanliness),
            ),
        ).fetchall()

        dominant_by_session: dict[int, dict[str, Any]] = {}

        for row in rows:
            session_id = int(row["id"])
            source_count = int(row["source_count"] or 0)

            current = dominant_by_session.get(session_id)

            if current is None or source_count > int(current["source_count"] or 0):
                dominant_by_session[session_id] = dict(row)

        values_by_source: dict[str, list[float]] = {
            "straight": [],
            "iambic": [],
        }

        for row in dominant_by_session.values():
            key_source = str(row.get("key_source") or "").lower()

            if key_source not in values_by_source:
                continue

            if len(values_by_source[key_source]) >= per_source_limit:
                continue

            target = str(row.get("target") or "")
            elapsed_us = row.get("elapsed_us")

            actual_wpm = paris_wpm_for_text(target, elapsed_us)

            if actual_wpm is None:
                continue

            if not (1 <= actual_wpm <= 150):
                continue

            values_by_source[key_source].append(float(actual_wpm))

            if (
                len(values_by_source["straight"]) >= per_source_limit
                and len(values_by_source["iambic"]) >= per_source_limit
            ):
                break

        straight_values = values_by_source["straight"]
        iambic_values = values_by_source["iambic"]

        straight_wpm = None if not straight_values else float(median(straight_values))
        iambic_wpm = None if not iambic_values else float(median(iambic_values))

        candidates: list[tuple[str, float, int]] = []

        if straight_wpm is not None:
            candidates.append(("straight", straight_wpm, len(straight_values)))

        if iambic_wpm is not None:
            candidates.append(("iambic", iambic_wpm, len(iambic_values)))

        if not candidates:
            return {
                "ok": False,
                "reason": (
                    "Kannasta ei löytynyt yhtään sopivaa straight- tai iambic-kierrosta. "
                    "Tarvitaan riittävän pitkiä kierroksia, joissa tarkkuus ja puhtaus "
                    "ylittävät raja-arvot."
                ),
                "used_rounds": 0,
                "total_used_rounds": 0,
                "wpm": None,
                "straight_wpm": None,
                "iambic_wpm": None,
                "best_source": None,
                "min_accuracy": float(min_accuracy),
                "min_cleanliness": float(min_cleanliness),
                "min_target_chars": int(min_target_chars),
                "per_source_limit": int(per_source_limit),
            }

        best_source, best_wpm, best_used = max(
            candidates,
            key=lambda item: item[1],
        )

        all_values = straight_values + iambic_values

        return {
            "ok": True,
            "reason": "",
            "used_rounds": best_used,
            "total_used_rounds": len(all_values),
            "wpm": best_wpm,
            "straight_wpm": straight_wpm,
            "iambic_wpm": iambic_wpm,
            "best_source": best_source,
            "straight_used_rounds": len(straight_values),
            "iambic_used_rounds": len(iambic_values),
            "min_wpm": min(all_values),
            "max_wpm": max(all_values),
            "min_accuracy": float(min_accuracy),
            "min_cleanliness": float(min_cleanliness),
            "min_target_chars": int(min_target_chars),
            "per_source_limit": int(per_source_limit),
        }

    def skill_recent_sessions(
        self,
        limit: int = 1000,
        min_target_chars: int = 12,
    ) -> List[sqlite3.Row]:
        cur = self.conn.cursor()

        cur.execute(
            """
            WITH eligible AS (
                SELECT
                    *,
                    COALESCE(
                        NULLIF(length_target, 0),
                        LENGTH(REPLACE(target, ' ', ''))
                    ) AS effective_target_chars
                FROM sessions
                WHERE COALESCE(
                    NULLIF(length_target, 0),
                    LENGTH(REPLACE(target, ' ', ''))
                ) >= ?
                ORDER BY id DESC
                LIMIT ?
            )
            SELECT
                id,
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

                avg_dit_us,
                dit_sd_us,

                straight_dot_us,
                straight_dot_sd_us,
                straight_dash_us,
                straight_dash_sd_us,
                straight_dash_dot_ratio,

                avg_letter_gap_us,
                letter_gap_sd_us,
                avg_word_gap_us,
                word_gap_sd_us,

                settings_json
            FROM eligible
            ORDER BY id ASC
            """,
            (
                int(min_target_chars),
                int(limit),
            ),
        )

        return list(cur.fetchall())
    

    def skill_recent_sessions_by_key_source(
        self,
        recent_sessions_per_source: int = 1000,
        min_target_chars: int = 12,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Return recent skill rows split by dominant key source.

        Up to recent_sessions_per_source rows are returned for both straight and
        iambic. A session is assigned to the source that produced the most scored
        target characters in that session.
        """

        per_source_limit = max(1, int(recent_sessions_per_source))

        result: Dict[str, List[Dict[str, Any]]] = {
            "straight": [],
            "iambic": [],
        }

        cur = self.conn.cursor()

        cur.execute(
            """
            SELECT
                s.id,
                s.finished_at,
                s.target,
                s.entered,
                s.source,
                s.finish_reason,

                s.accuracy,
                s.cleanliness,
                s.overall_score,
                s.speed_score,
                s.timing_score,

                s.correct_count,
                s.error_count,
                s.substitutions,
                s.insertions,
                s.deletions,
                s.length_target,
                s.length_entered,

                s.elapsed_us,
                s.standard_time_us,
                s.time_ok,

                s.avg_wpm,
                s.gross_wpm,
                s.net_wpm,

                s.avg_dit_us,
                s.dit_sd_us,

                s.straight_dot_us,
                s.straight_dot_sd_us,
                s.straight_dash_us,
                s.straight_dash_sd_us,
                s.straight_dash_dot_ratio,

                s.avg_letter_gap_us,
                s.letter_gap_sd_us,
                s.avg_word_gap_us,
                s.word_gap_sd_us,

                s.settings_json,

                LOWER(cr.source) AS key_source,
                COUNT(*) AS source_count
            FROM sessions s
            JOIN char_results cr ON cr.session_id = s.id
            WHERE COALESCE(
                NULLIF(s.length_target, 0),
                LENGTH(REPLACE(s.target, ' ', ''))
            ) >= ?
            AND s.elapsed_us IS NOT NULL
            AND s.elapsed_us > 0
            AND cr.target_char IS NOT NULL
            AND cr.target_char != ''
            AND cr.target_char != ' '
            AND cr.result IN ('correct', 'substitution', 'deletion')
            AND LOWER(cr.source) IN ('straight', 'iambic')
            GROUP BY
                s.id,
                LOWER(cr.source)
            ORDER BY
                s.id DESC,
                source_count DESC,
                CASE LOWER(cr.source)
                    WHEN 'straight' THEN 0
                    ELSE 1
                END ASC
            """,
            (
                int(min_target_chars),
            ),
        )

        seen_sessions: set[int] = set()

        for row in cur:
            session_id = int(row["id"])

            if session_id in seen_sessions:
                continue

            seen_sessions.add(session_id)

            key_source = str(row["key_source"] or "").lower()

            if key_source not in result:
                continue

            if len(result[key_source]) >= per_source_limit:
                continue

            result[key_source].append(
                {
                    "id": session_id,
                    "finished_at": row["finished_at"],
                    "target": row["target"],
                    "entered": row["entered"],
                    "source": row["source"],
                    "finish_reason": row["finish_reason"],

                    "accuracy": row["accuracy"],
                    "cleanliness": row["cleanliness"],
                    "overall_score": row["overall_score"],
                    "speed_score": row["speed_score"],
                    "timing_score": row["timing_score"],

                    "correct_count": row["correct_count"],
                    "error_count": row["error_count"],
                    "substitutions": row["substitutions"],
                    "insertions": row["insertions"],
                    "deletions": row["deletions"],
                    "length_target": row["length_target"],
                    "length_entered": row["length_entered"],

                    "elapsed_us": row["elapsed_us"],
                    "standard_time_us": row["standard_time_us"],
                    "time_ok": row["time_ok"],

                    "avg_wpm": row["avg_wpm"],
                    "gross_wpm": row["gross_wpm"],
                    "net_wpm": row["net_wpm"],

                    "avg_dit_us": row["avg_dit_us"],
                    "dit_sd_us": row["dit_sd_us"],

                    "straight_dot_us": row["straight_dot_us"],
                    "straight_dot_sd_us": row["straight_dot_sd_us"],
                    "straight_dash_us": row["straight_dash_us"],
                    "straight_dash_sd_us": row["straight_dash_sd_us"],
                    "straight_dash_dot_ratio": row["straight_dash_dot_ratio"],

                    "avg_letter_gap_us": row["avg_letter_gap_us"],
                    "letter_gap_sd_us": row["letter_gap_sd_us"],
                    "avg_word_gap_us": row["avg_word_gap_us"],
                    "word_gap_sd_us": row["word_gap_sd_us"],

                    "settings_json": row["settings_json"],
                    "dominant_key_source": key_source,
                    "source_count": row["source_count"],
                }
            )

            if (
                len(result["straight"]) >= per_source_limit
                and len(result["iambic"]) >= per_source_limit
            ):
                break

        # Keep the same chronological order as skill_recent_sessions().
        result["straight"].reverse()
        result["iambic"].reverse()

        return result

    def skill_character_results(
        self,
        recent_sessions: int = 1000,
        min_target_chars: int = 12,
    ) -> List[sqlite3.Row]:
        cur = self.conn.cursor()

        cur.execute(
            """
            WITH recent AS (
                SELECT id
                FROM sessions
                WHERE COALESCE(
                    NULLIF(length_target, 0),
                    LENGTH(REPLACE(target, ' ', ''))
                ) >= ?
                ORDER BY id DESC
                LIMIT ?
            )
            SELECT
                target_char AS char,
                COUNT(*) AS attempts,
                SUM(CASE WHEN result = 'correct' THEN 1 ELSE 0 END) AS correct,
                SUM(CASE WHEN result = 'correct' THEN 0 ELSE 1 END) AS errors
            FROM char_results
            WHERE session_id IN (SELECT id FROM recent)
              AND target_char IS NOT NULL
              AND target_char != ''
              AND target_char != ' '
              AND result IN ('correct', 'substitution', 'deletion')
            GROUP BY target_char
            ORDER BY target_char ASC
            """,
            (
                int(min_target_chars),
                int(recent_sessions),
            ),
        )

        return list(cur.fetchall())
    

    def skill_full_charset_character_results(
        self,
        recent_sessions: int = 1000,
        min_target_chars: int = 12,
        min_accuracy: float = 90.0,
        min_cleanliness: float = 85.0,
    ) -> List[sqlite3.Row]:
        """Return character evidence for full-character-set level coverage.

        This is intentionally separate from skill_character_results(). It only
        uses high-quality, sufficiently long rounds so that the full charset
        level correction is based on demonstrated character use inside good
        overall performances.
        """

        cur = self.conn.cursor()

        cur.execute(
            """
            WITH base_recent AS (
                SELECT id
                FROM sessions
                WHERE COALESCE(
                    NULLIF(length_target, 0),
                    LENGTH(REPLACE(target, ' ', ''))
                ) >= ?
                ORDER BY id DESC
                LIMIT ?
            ),
            qualified_sessions AS (
                SELECT id
                FROM sessions
                WHERE id IN (SELECT id FROM base_recent)
                  AND accuracy >= ?
                  AND cleanliness >= ?
            )
            SELECT
                cr.target_char AS char,
                COUNT(*) AS attempts,
                SUM(CASE WHEN cr.result = 'correct' THEN 1 ELSE 0 END) AS correct,
                SUM(CASE WHEN cr.result = 'correct' THEN 0 ELSE 1 END) AS errors,
                COUNT(DISTINCT cr.session_id) AS qualified_rounds
            FROM char_results cr
            WHERE cr.session_id IN (SELECT id FROM qualified_sessions)
              AND cr.target_char IS NOT NULL
              AND cr.target_char != ''
              AND cr.target_char != ' '
              AND cr.result IN ('correct', 'substitution', 'deletion')
            GROUP BY cr.target_char
            ORDER BY cr.target_char ASC
            """,
            (
                int(min_target_chars),
                int(recent_sessions),
                float(min_accuracy),
                float(min_cleanliness),
            ),
        )

        return list(cur.fetchall())


    def skill_timing_source_data(
        self,
        recent_sessions: int = 1000,
        min_target_chars: int = 12,
        min_accuracy: float = 85.0,
        min_cleanliness: float = 80.0,
    ) -> List[Dict[str, Any]]:
        """Return eligible sessions with raw tone telemetry for timing analysis."""

        cur = self.conn.cursor()

        session_rows = cur.execute(
            """
            WITH eligible AS (
                SELECT
                    *,
                    COALESCE(
                        NULLIF(length_target, 0),
                        LENGTH(REPLACE(target, ' ', ''))
                    ) AS effective_target_chars
                FROM sessions
                WHERE COALESCE(
                    NULLIF(length_target, 0),
                    LENGTH(REPLACE(target, ' ', ''))
                ) >= ?
                AND accuracy >= ?
                AND cleanliness >= ?
                ORDER BY id DESC
                LIMIT ?
            )
            SELECT
                id,
                finished_at,
                target,
                entered,
                source,
                accuracy,
                cleanliness,
                elapsed_us,
                length_target,
                settings_json
            FROM eligible
            ORDER BY id ASC
            """,
            (
                int(min_target_chars),
                float(min_accuracy),
                float(min_cleanliness),
                int(recent_sessions),
            ),
        ).fetchall()

        if not session_rows:
            return []

        session_ids = [int(row["id"]) for row in session_rows]
        placeholders = ",".join("?" for _ in session_ids)

        event_rows = cur.execute(
            f"""
            SELECT
                session_id,
                event_index,
                event_type,
                event_json
            FROM events
            WHERE session_id IN ({placeholders})
            ORDER BY session_id ASC, event_index ASC
            """,
            session_ids,
        ).fetchall()

        events_by_session: dict[int, list[dict[str, Any]]] = {
            session_id: []
            for session_id in session_ids
        }

        for row in event_rows:
            try:
                event = json.loads(str(row["event_json"] or "{}"))
            except Exception:
                continue

            if not isinstance(event, dict):
                continue

            events_by_session[int(row["session_id"])].append(event)

        result: list[dict[str, Any]] = []

        for row in session_rows:
            session_id = int(row["id"])

            result.append(
                {
                    "id": session_id,
                    "finished_at": row["finished_at"],
                    "target": row["target"],
                    "entered": row["entered"],
                    "source": row["source"],
                    "accuracy": row["accuracy"],
                    "cleanliness": row["cleanliness"],
                    "elapsed_us": row["elapsed_us"],
                    "length_target": row["length_target"],
                    "settings_json": row["settings_json"],
                    "events": events_by_session.get(session_id, []),
                }
            )

        return result
    

    def skill_timing_score_average_by_key_source(
        self,
        recent_sessions: int | None = None,
        min_target_chars: int = 12,
        min_accuracy: float = 85.0,
        min_cleanliness: float = 80.0,
    ) -> Dict[str, Any]:
        """Return average stored round timing_score by dominant key source."""

        cur = self.conn.cursor()

        recent_limit = max(
            1,
            int(
                recent_sessions
                if recent_sessions is not None
                else getattr(config, "DEFAULT_SKILL_RATING_RECENT_ROUNDS", 1000)
            ),
        )

        rows = cur.execute(
            """
            WITH eligible AS (
                SELECT
                    id,
                    timing_score
                FROM sessions
                WHERE COALESCE(
                    NULLIF(length_target, 0),
                    LENGTH(REPLACE(target, ' ', ''))
                ) >= ?
                AND accuracy >= ?
                AND cleanliness >= ?
                AND timing_score IS NOT NULL
                ORDER BY id DESC
                LIMIT ?
            )
            SELECT
                eligible.id AS session_id,
                eligible.timing_score AS timing_score,
                LOWER(cr.source) AS key_source,
                COUNT(*) AS source_count
            FROM eligible
            JOIN char_results cr ON cr.session_id = eligible.id
            WHERE cr.source IS NOT NULL
              AND LOWER(cr.source) IN ('straight', 'iambic')
              AND cr.target_char IS NOT NULL
              AND cr.target_char != ''
              AND cr.target_char != ' '
              AND cr.result IN ('correct', 'substitution', 'deletion')
            GROUP BY
                eligible.id,
                LOWER(cr.source)
            ORDER BY
                eligible.id DESC,
                source_count DESC,
                CASE LOWER(cr.source)
                    WHEN 'straight' THEN 0
                    ELSE 1
                END ASC
            """,
            (
                int(min_target_chars),
                float(min_accuracy),
                float(min_cleanliness),
                recent_limit,
            ),
        ).fetchall()

        values_by_source: dict[str, list[float]] = {
            "straight": [],
            "iambic": [],
        }

        seen_sessions: set[int] = set()

        for row in rows:
            session_id = int(row["session_id"])

            if session_id in seen_sessions:
                continue

            seen_sessions.add(session_id)

            key_source = str(row["key_source"] or "").lower()

            if key_source not in values_by_source:
                continue

            try:
                timing_score = float(row["timing_score"])
            except Exception:
                continue

            values_by_source[key_source].append(timing_score)

        straight_values = values_by_source["straight"]
        iambic_values = values_by_source["iambic"]

        return {
            "straight_timing_score": (
                None
                if not straight_values
                else sum(straight_values) / len(straight_values)
            ),
            "iambic_timing_score": (
                None
                if not iambic_values
                else sum(iambic_values) / len(iambic_values)
            ),
            "straight_used_rounds": len(straight_values),
            "iambic_used_rounds": len(iambic_values),
        }


    def save_skill_rating_snapshot(self, session_id: int | None, rating: Any) -> int:
        cur = self.conn.cursor()
        created_at = datetime.now().isoformat(timespec="seconds")
        log_app_event(
            "app.database.skill_rating_snapshot_save_started",
            message="Skill rating snapshot save started.",
            context={"session_id": session_id, "rating": summarize_rating(rating)},
        )

        if is_dataclass(rating):
            details = asdict(rating)
        else:
            details = dict(rating)

        cur.execute(
            """
            INSERT INTO skill_rating_snapshots (
                created_at,
                session_id,

                model_version,

                recent_sessions,
                total_rounds,
                used_rounds,

                effective_wpm,
                avg_accuracy,
                avg_cleanliness,

                quality_factor,
                character_mastery_factor,
                coverage_factor,
                timing_stability_factor,

                sample_confidence,
                rating_confidence,
                mastery_adjustment,

                raw_skill,
                level,
                level_progress,
                title,

                details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                session_id,

                int(getattr(rating, "model_version", getattr(config, "SKILL_RATING_MODEL_VERSION", 1))),

                int(getattr(rating, "recent_rounds", 0)),
                int(getattr(rating, "total_rounds", 0)),
                int(getattr(rating, "used_rounds", 0)),

                getattr(rating, "effective_wpm", None),
                getattr(rating, "avg_accuracy", None),
                getattr(rating, "avg_cleanliness", None),

                float(getattr(rating, "quality_factor", 0.0)),
                float(getattr(rating, "character_mastery_factor", 0.0)),
                float(getattr(rating, "coverage_factor", 0.0)),
                float(getattr(rating, "timing_stability_factor", 1.0)),

                float(getattr(rating, "sample_confidence", 0.0)),
                float(getattr(rating, "rating_confidence", 0.0)),
                float(getattr(rating, "mastery_adjustment", 1.0)),

                getattr(rating, "raw_skill", None),
                int(getattr(rating, "level", 0)),
                float(getattr(rating, "level_progress", 0.0)),
                str(getattr(rating, "title", "")),

                json.dumps(details, ensure_ascii=False),
            ),
        )

        self.conn.commit()
        snapshot_id = int(cur.lastrowid)
        log_app_event(
            "app.database.skill_rating_snapshot_saved",
            message="Skill rating snapshot saved.",
            context={"snapshot_id": snapshot_id, "session_id": session_id, "rating": summarize_rating(rating)},
        )
        return snapshot_id


    def recent_skill_snapshots(self, limit: int = 200) -> List[sqlite3.Row]:
        cur = self.conn.cursor()

        cur.execute(
            """
            SELECT
                id,
                created_at,
                session_id,
                model_version,
                recent_sessions,
                total_rounds,
                used_rounds,
                effective_wpm,
                avg_accuracy,
                avg_cleanliness,
                quality_factor,
                character_mastery_factor,
                coverage_factor,
                timing_stability_factor,
                sample_confidence,
                rating_confidence,
                mastery_adjustment,
                raw_skill,
                level,
                level_progress,
                title,
                details_json
            FROM skill_rating_snapshots
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        )

        return list(cur.fetchall())
    

    def stats_date_bounds(self) -> Dict[str, Any]:
        cur = self.conn.cursor()

        row = cur.execute(
            """
            SELECT
                MIN(finished_at) AS first_finished_at,
                MAX(finished_at) AS last_finished_at
            FROM sessions
            """
        ).fetchone()

        if row is None:
            return {
                "first_finished_at": None,
                "last_finished_at": None,
            }

        return dict(row)


    def stats_sessions_between(
        self,
        start_at: str,
        end_at: str,
    ) -> List[sqlite3.Row]:
        cur = self.conn.cursor()

        cur.execute(
            """
            SELECT
                id,
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

                avg_dit_us,
                dit_sd_us,

                straight_dot_us,
                straight_dot_sd_us,
                straight_dash_us,
                straight_dash_sd_us,
                straight_dash_dot_ratio,

                avg_letter_gap_us,
                letter_gap_sd_us,
                avg_word_gap_us,
                word_gap_sd_us,

                settings_json
            FROM sessions
            WHERE finished_at >= ?
              AND finished_at <= ?
            ORDER BY finished_at ASC, id ASC
            """,
            (start_at, end_at),
        )

        return list(cur.fetchall())


    def stats_summary_between(
        self,
        start_at: str,
        end_at: str,
    ) -> Dict[str, Any]:
        cur = self.conn.cursor()

        row = cur.execute(
            """
            SELECT
                COUNT(*) AS rounds,

                AVG(accuracy) AS avg_accuracy,
                AVG(cleanliness) AS avg_cleanliness,
                AVG(overall_score) AS avg_overall_score,
                AVG(speed_score) AS avg_speed_score,
                AVG(timing_score) AS avg_timing_score,

                AVG(gross_wpm) AS avg_gross_wpm,
                AVG(net_wpm) AS avg_net_wpm,
                AVG(avg_wpm) AS avg_device_wpm,

                AVG(straight_dash_dot_ratio) AS avg_straight_dash_dot_ratio,

                AVG(
                    CASE
                        WHEN straight_dot_us IS NOT NULL
                        AND straight_dot_us > 0
                        AND straight_dot_sd_us IS NOT NULL
                        THEN straight_dot_sd_us * 100.0 / straight_dot_us
                        ELSE NULL
                    END
                ) AS avg_straight_dot_variation_percent,

                AVG(
                    CASE
                        WHEN straight_dash_us IS NOT NULL
                        AND straight_dash_us > 0
                        AND straight_dash_sd_us IS NOT NULL
                        THEN straight_dash_sd_us * 100.0 / straight_dash_us
                        ELSE NULL
                    END
                ) AS avg_straight_dash_variation_percent,

                AVG(elapsed_us) AS avg_elapsed_us,

                SUM(correct_count) AS total_correct,
                SUM(error_count) AS total_errors,
                SUM(substitutions) AS total_substitutions,
                SUM(insertions) AS total_insertions,
                SUM(deletions) AS total_deletions
            FROM sessions
            WHERE finished_at >= ?
              AND finished_at <= ?
            """,
            (start_at, end_at),
        ).fetchone()

        if row is None:
            return {
                "rounds": 0,
                "avg_accuracy": None,
                "avg_cleanliness": None,
                "avg_overall_score": None,
                "avg_speed_score": None,
                "avg_timing_score": None,
                "avg_gross_wpm": None,
                "avg_net_wpm": None,
                "avg_device_wpm": None,
                "avg_elapsed_us": None,
                "avg_straight_dash_dot_ratio": None,
                "avg_straight_dot_variation_percent": None,
                "avg_straight_dash_variation_percent": None,
                "total_correct": 0,
                "total_errors": 0,
                "total_substitutions": 0,
                "total_insertions": 0,
                "total_deletions": 0,
            }

        return dict(row)


    def stats_skill_snapshots_between(
        self,
        start_at: str,
        end_at: str,
    ) -> List[sqlite3.Row]:
        cur = self.conn.cursor()

        cur.execute(
            """
            SELECT
                id,
                created_at,
                session_id,
                model_version,
                recent_sessions,
                total_rounds,
                used_rounds,
                effective_wpm,
                avg_accuracy,
                avg_cleanliness,
                quality_factor,
                character_mastery_factor,
                coverage_factor,
                timing_stability_factor,
                sample_confidence,
                rating_confidence,
                mastery_adjustment,
                raw_skill,
                level,
                level_progress,
                title,
                details_json
            FROM skill_rating_snapshots
            WHERE created_at >= ?
              AND created_at <= ?
            ORDER BY created_at ASC, id ASC
            """,
            (start_at, end_at),
        )

        return list(cur.fetchall())


    def stats_problem_characters_between(
        self,
        start_at: str,
        end_at: str,
        limit: int = 20,
    ) -> List[sqlite3.Row]:
        cur = self.conn.cursor()

        cur.execute(
            """
            SELECT
                cr.target_char AS char,
                COUNT(*) AS attempts,
                SUM(CASE WHEN cr.result = 'correct' THEN 0 ELSE 1 END) AS errors,
                ROUND(
                    SUM(CASE WHEN cr.result = 'correct' THEN 0 ELSE 1 END)
                    * 100.0 / COUNT(*),
                    1
                ) AS error_rate
            FROM char_results cr
            JOIN sessions s ON s.id = cr.session_id
            WHERE s.finished_at >= ?
              AND s.finished_at <= ?
              AND cr.target_char IS NOT NULL
              AND cr.target_char != ''
              AND cr.target_char != ' '
              AND cr.result IN ('correct', 'substitution', 'deletion')
            GROUP BY cr.target_char
            HAVING attempts > 0
            ORDER BY error_rate DESC, errors DESC, attempts DESC
            LIMIT ?
            """,
            (start_at, end_at, int(limit)),
        )

        return list(cur.fetchall())
    

    def _profile_min_rounds_required(self) -> int:
        return max(
            1,
            int(getattr(config, "DECODER_PROFILE_MIN_ROUNDS_REQUIRED", 100)),
        )


    def _profile_min_confidence_required(self) -> float:
        return max(
            0.0,
            min(
                1.0,
                float(getattr(config, "DECODER_PROFILE_MIN_CONFIDENCE_FOR_SEED", 0.30)),
            ),
        )


    def _profile_element_outlier_ratio(self) -> float:
        return max(
            0.0,
            float(getattr(config, "DECODER_PROFILE_ELEMENT_OUTLIER_RATIO", 0.30)),
        )


    def _profile_gap_outlier_ratio(self) -> float:
        return max(
            0.0,
            float(getattr(config, "DECODER_PROFILE_GAP_OUTLIER_RATIO", 0.40)),
        )


    def _profile_max_element_change_ratio(self) -> float:
        return max(
            0.0,
            float(getattr(config, "DECODER_PROFILE_MAX_ELEMENT_CHANGE_RATIO", 0.10)),
        )


    def _profile_max_gap_change_ratio(self) -> float:
        return max(
            0.0,
            float(getattr(config, "DECODER_PROFILE_MAX_GAP_CHANGE_RATIO", 0.15)),
        )


    def _finite_positive_float(self, value: Any) -> Optional[float]:
        try:
            number = float(value)
        except Exception:
            return None

        if number <= 0:
            return None

        if number != number:
            return None

        if number in (float("inf"), float("-inf")):
            return None

        return number


    def _within_ratio(self, value: Any, center: Optional[float], max_ratio: float) -> bool:
        value_number = self._finite_positive_float(value)

        if value_number is None:
            return False

        if center is None or center <= 0:
            return True

        return abs(value_number - center) / center <= max_ratio


    def _sample_median(
        self,
        samples: list[TimingProfileSample],
        attribute: str,
    ) -> Optional[float]:
        values: list[float] = []

        for sample in samples:
            value = self._finite_positive_float(getattr(sample, attribute, None))
            if value is not None:
                values.append(value)

        if not values:
            return None

        return float(median(values))


    def _filter_timing_profile_outliers(
        self,
        samples: list[TimingProfileSample],
    ) -> list[TimingProfileSample]:
        if not samples:
            return []

        source_name = normalize_source(samples[0].source)

        element_center = self._sample_median(samples, "element_unit_us")
        element_ratio = self._profile_element_outlier_ratio()
        gap_ratio = self._profile_gap_outlier_ratio()

        if source_name == "iambic":
            letter_center = self._sample_median(samples, "letter_gap_us")
            word_center = self._sample_median(samples, "word_gap_us")

            filtered: list[TimingProfileSample] = []

            for sample in samples:
                element_ok = self._within_ratio(
                    sample.element_unit_us,
                    element_center,
                    element_ratio,
                )

                letter_value = self._finite_positive_float(sample.letter_gap_us)
                word_value = self._finite_positive_float(sample.word_gap_us)

                letter_ok = (
                    letter_value is not None
                    and self._within_ratio(
                        sample.letter_gap_us,
                        letter_center,
                        gap_ratio,
                    )
                )

                word_ok = (
                    word_value is not None
                    and self._within_ratio(
                        sample.word_gap_us,
                        word_center,
                        gap_ratio,
                    )
                )

                if element_ok and (letter_ok or word_ok):
                    filtered.append(sample)

            return filtered

        gap_center = self._sample_median(samples, "gap_unit_us")

        filtered = []

        for sample in samples:
            element_ok = self._within_ratio(
                sample.element_unit_us,
                element_center,
                element_ratio,
            )

            gap_ok = self._within_ratio(
                sample.gap_unit_us,
                gap_center,
                gap_ratio,
            )

            if element_ok and gap_ok:
                filtered.append(sample)

        return filtered


    def _profile_is_usable(self, profile: TimingProfile) -> bool:
        min_rounds = self._profile_min_rounds_required()
        min_confidence = self._profile_min_confidence_required()

        try:
            if int(profile.sample_rounds or 0) < min_rounds:
                return False

            element_confidence = float(profile.element_confidence or 0.0)
            gap_confidence = float(profile.gap_confidence or 0.0)

            if normalize_source(profile.source) == "iambic":
                return (
                    profile.letter_gap_us is not None
                    and profile.word_gap_us is not None
                    and profile.gap_unit_us is not None
                    and gap_confidence >= min_confidence
                )

            element_ok = (
                profile.element_unit_us is not None
                and element_confidence >= min_confidence
            )

            gap_ok = (
                profile.gap_unit_us is not None
                and gap_confidence >= min_confidence
            )

            return element_ok or gap_ok

        except Exception:
            return False


    def _load_persisted_timing_profile(self, source: str) -> TimingProfile:
        source_name = normalize_source(source)
        cur = self.conn.cursor()

        row = cur.execute(
            """
            SELECT
                source,
                element_unit_us,
                gap_unit_us,
                dot_us,
                dash_us,
                dash_dot_ratio,
                letter_gap_us,
                word_gap_us,
                element_confidence,
                gap_confidence,
                sample_rounds,
                sample_events,
                updated_from_session_id
            FROM timing_profile_state
            WHERE source = ?
            """,
            (source_name,),
        ).fetchone()

        if row is None:
            return TimingProfile(source=source_name)

        return TimingProfile(
            source=source_name,
            element_unit_us=row["element_unit_us"],
            gap_unit_us=row["gap_unit_us"],
            dot_us=row["dot_us"],
            dash_us=row["dash_us"],
            dash_dot_ratio=row["dash_dot_ratio"],
            letter_gap_us=row["letter_gap_us"],
            word_gap_us=row["word_gap_us"],
            element_confidence=float(row["element_confidence"] or 0.0),
            gap_confidence=float(row["gap_confidence"] or 0.0),
            sample_rounds=int(row["sample_rounds"] or 0),
            sample_events=int(row["sample_events"] or 0),
            updated_from_session_id=row["updated_from_session_id"],
        )


    def _clamp_profile_value(
        self,
        candidate_value: Any,
        previous_value: Any,
        max_change_ratio: float,
    ) -> Any:
        candidate = self._finite_positive_float(candidate_value)
        previous = self._finite_positive_float(previous_value)

        if candidate is None:
            return candidate_value

        if previous is None:
            return candidate

        lower = previous * (1.0 - max_change_ratio)
        upper = previous * (1.0 + max_change_ratio)

        return max(lower, min(upper, candidate))


    def _clamp_timing_profile_drift(
        self,
        candidate: TimingProfile,
        previous: TimingProfile,
    ) -> TimingProfile:
        if not self._profile_is_usable(previous):
            return candidate

        element_unit_us = self._clamp_profile_value(
            candidate.element_unit_us,
            previous.element_unit_us,
            self._profile_max_element_change_ratio(),
        )

        if candidate.source == "iambic":
            gap_unit_us = candidate.gap_unit_us
        else:
            gap_unit_us = self._clamp_profile_value(
                candidate.gap_unit_us,
                previous.gap_unit_us,
                self._profile_max_gap_change_ratio(),
            )

        return TimingProfile(
            source=candidate.source,
            element_unit_us=element_unit_us,
            gap_unit_us=gap_unit_us,
            dot_us=candidate.dot_us,
            dash_us=candidate.dash_us,
            dash_dot_ratio=candidate.dash_dot_ratio,
            letter_gap_us=candidate.letter_gap_us,
            word_gap_us=candidate.word_gap_us,
            element_confidence=candidate.element_confidence,
            gap_confidence=candidate.gap_confidence,
            sample_rounds=candidate.sample_rounds,
            sample_events=candidate.sample_events,
            updated_from_session_id=candidate.updated_from_session_id,
        )
    

    def _timing_profiles_effectively_equal(
        self,
        previous: TimingProfile,
        candidate: TimingProfile,
    ) -> bool:
        fields = (
            "element_unit_us",
            "gap_unit_us",
            "dot_us",
            "dash_us",
            "dash_dot_ratio",
            "letter_gap_us",
            "word_gap_us",
            "element_confidence",
            "gap_confidence",
        )

        for field in fields:
            previous_value = self._finite_positive_float(
                getattr(previous, field, None)
            )
            candidate_value = self._finite_positive_float(
                getattr(candidate, field, None)
            )

            if previous_value is None and candidate_value is None:
                continue

            if previous_value is None or candidate_value is None:
                return False

            tolerance = max(1.0, abs(candidate_value) * 0.002)

            if abs(previous_value - candidate_value) > tolerance:
                return False

        return True


    def _save_persisted_timing_profile(self, profile: TimingProfile) -> None:
        if not self._profile_is_usable(profile):
            log_app_event(
                "app.timing_profile.persistence_skipped",
                message="Timing profile was not usable enough to persist.",
                context={"profile": summarize_timing_profile(profile)},
            )
            return

        cur = self.conn.cursor()

        cur.execute(
            """
            INSERT INTO timing_profile_state (
                source,
                updated_at,

                element_unit_us,
                gap_unit_us,

                dot_us,
                dash_us,
                dash_dot_ratio,

                letter_gap_us,
                word_gap_us,

                element_confidence,
                gap_confidence,

                sample_rounds,
                sample_events,
                updated_from_session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                updated_at = excluded.updated_at,

                element_unit_us = excluded.element_unit_us,
                gap_unit_us = excluded.gap_unit_us,

                dot_us = excluded.dot_us,
                dash_us = excluded.dash_us,
                dash_dot_ratio = excluded.dash_dot_ratio,

                letter_gap_us = excluded.letter_gap_us,
                word_gap_us = excluded.word_gap_us,

                element_confidence = excluded.element_confidence,
                gap_confidence = excluded.gap_confidence,

                sample_rounds = excluded.sample_rounds,
                sample_events = excluded.sample_events,
                updated_from_session_id = excluded.updated_from_session_id
            """,
            (
                profile.source,
                datetime.now().isoformat(timespec="seconds"),

                profile.element_unit_us,
                profile.gap_unit_us,

                profile.dot_us,
                profile.dash_us,
                profile.dash_dot_ratio,

                profile.letter_gap_us,
                profile.word_gap_us,

                float(profile.element_confidence or 0.0),
                float(profile.gap_confidence or 0.0),

                int(profile.sample_rounds or 0),
                int(profile.sample_events or 0),
                profile.updated_from_session_id,
            ),
        )

        self.conn.commit()
        log_app_event(
            "app.timing_profile.persisted",
            message="Timing profile persisted.",
            context={"profile": summarize_timing_profile(profile)},
        )


    def load_timing_profile(
        self,
        source: str,
        *,
        recent_sessions: int = 300,
        min_accuracy: float = 90.0,
        min_cleanliness: float = 85.0,
        min_timing_score: Optional[float] = None,
    ) -> TimingProfile:
        """Build a stable timing profile from recent successful rounds.

        Bad rounds are kept in the database, but they are ignored here.

        A timing profile is only usable when the recent window contains enough
        high-quality rounds for this key source. The profile is calculated from
        accepted rounds, outliers are removed, and profile drift is limited
        against the previously persisted stable profile.
        """

        source_name = normalize_source(source)
        recent_limit = max(1, int(recent_sessions))
        min_rounds = self._profile_min_rounds_required()
        min_target_chars = max(
            1,
            int(getattr(config, "DECODER_PROFILE_MIN_TARGET_CHARS", 12)),
        )

        if min_timing_score is None:
            min_timing_score = float(getattr(config, "DECODER_PROFILE_MIN_TIMING_SCORE", 30.0))

        cur = self.conn.cursor()

        rows = cur.execute(
            """
            SELECT
                s.id AS session_id,
                LOWER(cr.source) AS key_source,
                COUNT(*) AS event_count,

                AVG(cr.element_unit_us) AS element_unit_us,
                AVG(cr.gap_unit_us) AS gap_unit_us,

                s.straight_dot_us AS dot_us,
                s.straight_dash_us AS dash_us,

                AVG(CASE WHEN cr.gap_kind = 'letter' THEN cr.gap_before_us END) AS letter_gap_us,
                AVG(CASE WHEN cr.gap_kind = 'word' THEN cr.gap_before_us END) AS word_gap_us
            FROM sessions s
            JOIN char_results cr ON cr.session_id = s.id
            WHERE s.accuracy >= ?
              AND s.cleanliness >= ?
              AND s.timing_score IS NOT NULL
              AND s.timing_score >= ?
              AND COALESCE(s.profile_eligible, 1) = 1

              AND cr.source IS NOT NULL
              AND LOWER(cr.source) = ?

              AND cr.target_char IS NOT NULL
              AND cr.target_char != ''
              AND cr.target_char != ' '

              AND cr.result IN ('correct', 'substitution', 'deletion')
              AND cr.element_unit_us IS NOT NULL
              AND cr.element_unit_us > 0
              AND cr.gap_unit_us IS NOT NULL
              AND cr.gap_unit_us > 0
            GROUP BY s.id, LOWER(cr.source)
            HAVING COUNT(*) >= ?
            ORDER BY s.id DESC
            LIMIT ?
            """,
            (
                float(min_accuracy),
                float(min_cleanliness),
                float(min_timing_score),
                source_name,
                int(min_target_chars),
                recent_limit,
            ),
        ).fetchall()

        raw_samples: list[TimingProfileSample] = []

        for row in rows:
            raw_samples.append(
                TimingProfileSample(
                    session_id=int(row["session_id"]),
                    source=str(row["key_source"] or source_name),
                    element_unit_us=row["element_unit_us"],
                    gap_unit_us=row["gap_unit_us"],
                    dot_us=row["dot_us"],
                    dash_us=row["dash_us"],
                    letter_gap_us=row["letter_gap_us"],
                    word_gap_us=row["word_gap_us"],
                    event_count=int(row["event_count"] or 0),
                )
            )

        if len(raw_samples) < min_rounds:
            log_app_event(
                "app.timing_profile.not_usable",
                message="Timing profile does not yet have enough raw samples.",
                context={
                    "source": source_name,
                    "raw_sample_count": len(raw_samples),
                    "min_rounds": min_rounds,
                    "recent_limit": recent_limit,
                },
            )
            return TimingProfile(source=source_name)

        filtered_samples = self._filter_timing_profile_outliers(raw_samples)

        if len(filtered_samples) < min_rounds:
            log_app_event(
                "app.timing_profile.not_usable",
                message="Timing profile does not yet have enough filtered samples.",
                context={
                    "source": source_name,
                    "raw_sample_count": len(raw_samples),
                    "filtered_sample_count": len(filtered_samples),
                    "min_rounds": min_rounds,
                },
            )
            return TimingProfile(source=source_name)

        candidate = build_timing_profile(
            filtered_samples,
            source=source_name,
            max_samples=recent_limit,
        )

        if not self._profile_is_usable(candidate):
            log_app_event(
                "app.timing_profile.not_usable",
                message="Timing profile candidate was not usable.",
                context={"profile": summarize_timing_profile(candidate)},
            )
            return TimingProfile(source=source_name)

        previous = self._load_persisted_timing_profile(source_name)

        previous_session_id = previous.updated_from_session_id
        candidate_session_id = candidate.updated_from_session_id

        # If the persisted profile was already built from the same newest
        # qualifying session, return it as-is. This prevents repeated app starts
        # from slowly walking the profile toward the same candidate again.
        same_evidence = (
            int(previous.sample_rounds or 0) == int(candidate.sample_rounds or 0)
            and int(previous.sample_events or 0) == int(candidate.sample_events or 0)
        )

        same_profile_values = self._timing_profiles_effectively_equal(
            previous,
            candidate,
        )

        if (
            self._profile_is_usable(previous)
            and same_evidence
            and same_profile_values
            and previous_session_id is not None
            and candidate_session_id is not None
            and int(candidate_session_id) <= int(previous_session_id)
        ):
            log_app_event(
                "app.timing_profile.loaded",
                message="Persisted timing profile reused without recalculation drift.",
                context={"profile": summarize_timing_profile(previous)},
            )
            return previous

        stable_profile = self._clamp_timing_profile_drift(candidate, previous)
        if self._profile_is_usable(previous) and not self._timing_profiles_effectively_equal(candidate, stable_profile):
            log_app_event(
                "app.timing_profile.drift_clamped",
                message="Timing profile drift was clamped before persistence.",
                context={
                    "source": source_name,
                    "candidate": summarize_timing_profile(candidate),
                    "previous": summarize_timing_profile(previous),
                    "stable": summarize_timing_profile(stable_profile),
                },
            )

        self._save_persisted_timing_profile(stable_profile)

        log_app_event(
            "app.timing_profile.loaded",
            message="Timing profile loaded from recent sessions.",
            context={"profile": summarize_timing_profile(stable_profile)},
        )
        return stable_profile
    

    def timing_profile_progress(
        self,
        source: str,
        *,
        recent_sessions: int = 300,
        min_accuracy: float = 90.0,
        min_cleanliness: float = 85.0,
        min_timing_score: Optional[float] = None,
    ) -> dict[str, int]:
        source_name = normalize_source(source)
        recent_limit = max(1, int(recent_sessions))
        min_target_chars = max(
            1,
            int(getattr(config, "DECODER_PROFILE_MIN_TARGET_CHARS", 12)),
        )

        if min_timing_score is None:
            min_timing_score = float(getattr(config, "DECODER_PROFILE_MIN_TIMING_SCORE", 30.0))

        cur = self.conn.cursor()

        rows = cur.execute(
            """
            SELECT
                s.id AS session_id,
                COUNT(*) AS event_count
            FROM sessions s
            JOIN char_results cr ON cr.session_id = s.id
            WHERE s.accuracy >= ?
              AND s.cleanliness >= ?
              AND s.timing_score IS NOT NULL
              AND s.timing_score >= ?
              AND COALESCE(s.profile_eligible, 1) = 1

              AND cr.source IS NOT NULL
              AND LOWER(cr.source) = ?

              AND cr.target_char IS NOT NULL
              AND cr.target_char != ''
              AND cr.target_char != ' '

              AND cr.result IN ('correct', 'substitution', 'deletion')
              AND cr.element_unit_us IS NOT NULL
              AND cr.element_unit_us > 0
              AND cr.gap_unit_us IS NOT NULL
              AND cr.gap_unit_us > 0
            GROUP BY s.id, LOWER(cr.source)
            HAVING COUNT(*) >= ?
            ORDER BY s.id DESC
            LIMIT ?
            """,
            (
                float(min_accuracy),
                float(min_cleanliness),
                float(min_timing_score),
                source_name,
                int(min_target_chars),
                recent_limit,
            ),
        ).fetchall()

        return {
            "source": source_name,
            "good_rounds": len(rows),
            "good_events": sum(int(row["event_count"] or 0) for row in rows),
        }
    

    def load_timing_profiles(
        self,
        *,
        recent_sessions: int = 300,
        min_accuracy: float = 90.0,
        min_cleanliness: float = 85.0,
        min_timing_score: Optional[float] = None,
    ) -> dict[str, TimingProfile]:
        return {
            "straight": self.load_timing_profile(
                "straight",
                recent_sessions=recent_sessions,
                min_accuracy=min_accuracy,
                min_cleanliness=min_cleanliness,
                min_timing_score=min_timing_score,
            ),
            "iambic": self.load_timing_profile(
                "iambic",
                recent_sessions=recent_sessions,
                min_accuracy=min_accuracy,
                min_cleanliness=min_cleanliness,
                min_timing_score=min_timing_score,
            ),
        }

    def stats_key_source_wpm_between(
        self,
        start_at: str,
        end_at: str,
    ) -> List[Dict[str, Any]]:
        """Return uncapped per-session PARIS WPM classified by dominant key source.

        The source is decided from char_results.source. If a round contains both
        straight and iambic characters, the source with more scored characters wins.

        This is display/statistics data, not capped skill evidence.
        """

        cur = self.conn.cursor()

        rows = cur.execute(
            """
            SELECT
                s.id AS session_id,
                s.finished_at,
                s.target,
                s.length_target,
                s.elapsed_us,
                LOWER(cr.source) AS key_source,
                COUNT(*) AS source_count
            FROM sessions s
            JOIN char_results cr ON cr.session_id = s.id
            WHERE s.finished_at >= ?
            AND s.finished_at <= ?
            AND s.elapsed_us IS NOT NULL
            AND s.elapsed_us > 0
            AND cr.target_char IS NOT NULL
            AND cr.target_char != ''
            AND cr.target_char != ' '
            AND cr.result IN ('correct', 'substitution', 'deletion')
            AND LOWER(cr.source) IN ('straight', 'iambic')
            GROUP BY
                s.id,
                LOWER(cr.source)
            ORDER BY
                s.finished_at ASC,
                s.id ASC,
                source_count DESC,
                CASE LOWER(cr.source)
                    WHEN 'straight' THEN 0
                    ELSE 1
                END ASC
            """,
            (start_at, end_at),
        ).fetchall()

        dominant_by_session: dict[int, Dict[str, Any]] = {}

        for row in rows:
            session_id = int(row["session_id"])
            source_count = int(row["source_count"] or 0)

            current = dominant_by_session.get(session_id)

            if current is None or source_count > int(current["source_count"] or 0):
                dominant_by_session[session_id] = dict(row)

        result: list[Dict[str, Any]] = []

        for row in dominant_by_session.values():
            elapsed_us = row.get("elapsed_us")

            if elapsed_us is None:
                continue

            target = str(row.get("target") or "")

            actual_wpm = paris_wpm_for_text(target, elapsed_us)

            if actual_wpm is None:
                continue

            if not (1 <= actual_wpm <= 150):
                continue

            result.append(
                {
                    "session_id": int(row["session_id"]),
                    "finished_at": row["finished_at"],
                    "key_source": row["key_source"],
                    "wpm": float(actual_wpm),
                    "source_count": int(row["source_count"] or 0),
                }
            )

        result.sort(key=lambda item: (str(item["finished_at"]), int(item["session_id"])))
        return result