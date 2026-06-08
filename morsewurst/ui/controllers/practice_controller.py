# ============================================================
# morsewurst/ui/controllers/practice_controller.py
# ============================================================

from __future__ import annotations

import copy
import queue
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Sequence

import tkinter as tk

import morsewurst.config as config
from morsewurst.core.challenge import (
    generate_challenge,
    generate_wxmor_challenge,
    score_text,
)
from morsewurst.core.scoring import estimate_paris_time_us, score_round
from morsewurst.core.app_logging import (
    log_app_event,
    log_app_exception,
    summarize_challenge_settings,
    summarize_rating,
    summarize_score_summary,
)
from morsewurst.core.skill_rating import calculate_skill_rating
from morsewurst.models import RoundState
from morsewurst.storage.database import Database
from morsewurst.ui.controllers.results_controller import SOURCE_ADAPTIVE_TELEMETRY

FINISH_REASON_USER_STOPPED = "user_stopped"
FINISH_REASON_LONG_PAUSE = "long_pause"
FINISH_REASON_COMPLETED = "completed"
FINISH_REASON_IN_PROGRESS = "in_progress"

FINISH_REASON_I18N_KEYS = {
    FINISH_REASON_USER_STOPPED: "practice.finish_reason.user_stopped",
    FINISH_REASON_LONG_PAUSE: "practice.finish_reason.long_pause",
    FINISH_REASON_COMPLETED: "practice.finish_reason.completed",
    FINISH_REASON_IN_PROGRESS: "practice.finish_reason.in_progress",
}

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


def _elapsed_ms(started_monotonic: float) -> float:
    """Return elapsed milliseconds for compact performance log contexts."""

    return round(max(0.0, (time.monotonic() - float(started_monotonic)) * 1000.0), 2)


class PracticeController:
    """Owns practice series lifecycle, round completion and practice timers."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app
        self.current_practice_id: Optional[int] = None
        self.current_practice_token: Optional[int] = None
        self.current_practice_started_at: Optional[datetime] = None
        self.pending_after_round_updates_session_id: Optional[int] = None
        self.pending_after_round_snapshot_session_ids: list[int] = []
        self._last_round_generation_context: dict[str, Any] = {}
        self._practice_token_counter = 0
        self._practice_token_lock = threading.Lock()
        self._practice_db_ids_by_token: dict[int, int] = {}
        self._practice_problem_chars_cache: list[str] = []
        self._practice_problem_chars_cache_key: Optional[tuple[int, int]] = None
        self._practice_problem_chars_generation = 0

        self._background_queue: queue.Queue[tuple[str, float, Callable[[], None]] | None] = queue.Queue()
        self._background_worker_thread: Optional[threading.Thread] = None
        self._background_worker_lock = threading.Lock()
        self._background_shutdown = False
        self._background_save_generation = 0
        self._after_round_analytics_generation = 0
        self._after_round_analytics_after_id: Optional[str] = None
        self._timing_profile_refresh_generation = 0

        self.inter_round_countdown_running = False
        self.inter_round_countdown_after_id: Optional[str] = None
        self.inter_round_countdown_generation = 0
        self.inter_round_countdown_started_at: Optional[float] = None
        self.inter_round_countdown_seconds = 3.0

    def finish_reason_label(self, reason: object) -> str:
        reason_code = str(reason or "").strip()
        key = FINISH_REASON_I18N_KEYS.get(reason_code)

        if key is None:
            return reason_code

        return self.app.i18n.t(key, reason_code)

    # ------------------------------------------------------------
    # Public controller API used by other controllers
    # ------------------------------------------------------------

    def begin_start_countdown(self) -> None:
        """Start the visual pre-practice countdown from an external controller."""
        self._begin_start_countdown()

    def start_round_clock_from_host_input(self) -> None:
        """Start the round clock when text input begins."""
        self._start_round_clock_from_host_input()

    def start_round_clock_from_tone_event(self, event: Dict[str, Any]) -> None:
        """Start the round clock from the first accepted tone event."""
        self._start_round_clock_from_tone_event(event)

    def update_adaptive_decoded_text(self, flush_final: bool = False) -> None:
        """Decode tone telemetry and update the visible adaptive telemetry text."""
        self._update_adaptive_decoded_text(flush_final=flush_final)

    def mark_live_ui_dirty(self) -> None:
        """Request a throttled live telemetry and score refresh."""
        self._mark_live_ui_dirty()

    def refresh_live_ui(self, *, force: bool = False) -> None:
        """Refresh live telemetry and score panels when a throttled update is due."""
        self._refresh_live_ui(force=force)

    def check_round_completion(self) -> None:
        """Check whether the current round should be finished."""
        self._maybe_finish_completed()

    def reference_time_label(self) -> str:
        """Return the static reference time label for the current target."""
        return self._reference_time_label()

    def tick_timer(self) -> None:
        """Public Tk timer callback for live round timing."""
        self._tick_timer()

    def update_practice_buttons(self) -> None:
        """Update practice button states from an external controller."""
        self._update_practice_buttons()

    # ------------------------------------------------------------
    # Background persistence and analytics
    # ------------------------------------------------------------

    def _new_practice_token(self, *, started_at: datetime) -> int:
        """Create an in-memory practice token without touching SQLite.

        The actual practices row is created lazily in the background save path.
        This keeps the Start button and countdown path independent from any
        long-running read or write that may still be happening on another
        SQLite connection after the previous round.
        """

        self._practice_token_counter += 1
        token = self._practice_token_counter
        self.current_practice_token = token
        self.current_practice_started_at = started_at

        with self._practice_token_lock:
            self._practice_db_ids_by_token.pop(token, None)

        return token

    def _practice_db_id_for_token(self, token: Optional[int]) -> Optional[int]:
        if token is None:
            return None

        with self._practice_token_lock:
            return self._practice_db_ids_by_token.get(int(token))

    def _remember_practice_db_id_for_token(self, token: Optional[int], practice_id: int) -> None:
        if token is None:
            return

        token = int(token)
        practice_id = int(practice_id)

        with self._practice_token_lock:
            self._practice_db_ids_by_token[token] = practice_id

        def apply_if_current() -> None:
            if self.current_practice_token == token and self.current_practice_id is None:
                self.current_practice_id = practice_id

        self._schedule_on_main_thread(apply_if_current)

    def _clear_current_practice_reference(self) -> None:
        self.current_practice_id = None
        self.current_practice_token = None
        self.current_practice_started_at = None

    def _cancel_low_priority_history_render(self) -> None:
        try:
            self.app.history_controller.cancel_history_table_render()
        except Exception:
            pass

    def _cancel_scheduled_after_round_analytics(self) -> None:
        after_id = self._after_round_analytics_after_id
        self._after_round_analytics_after_id = None

        if after_id is None:
            return

        try:
            self.app.after_cancel(after_id)
        except Exception:
            pass

    def _analytics_delay_ms(self, *, active_reschedule: bool = False) -> int:
        setting_name = (
            "AFTER_ROUND_ANALYTICS_ACTIVE_RESCHEDULE_MS"
            if active_reschedule
            else "AFTER_ROUND_ANALYTICS_DELAY_MS"
        )
        default = 1000 if active_reschedule else 1500

        try:
            return max(1, int(getattr(config, setting_name, default)))
        except Exception:
            return default

    def shutdown_background_worker(self, *, wait_seconds: float = 5.0) -> None:
        """Ask the practice background worker to finish queued work and stop."""
        self._background_shutdown = True

        with self._background_worker_lock:
            worker = self._background_worker_thread

        if worker is None:
            return

        self._background_queue.put(None)
        worker.join(timeout=max(0.0, float(wait_seconds)))

    def _ensure_background_worker(self) -> None:
        with self._background_worker_lock:
            worker = self._background_worker_thread

            if worker is not None and worker.is_alive():
                return

            self._background_shutdown = False
            worker = threading.Thread(
                target=self._background_worker_loop,
                name="MorsewurstPracticeWorker",
                daemon=True,
            )
            self._background_worker_thread = worker
            worker.start()

    def _background_queue_size(self) -> int | None:
        try:
            return int(self._background_queue.qsize())
        except Exception:
            return None

    def _enqueue_background_job(self, label: str, job: Callable[[], None]) -> bool:
        if self._background_shutdown:
            log_app_event(
                "app.practice.background_job_skipped_shutdown",
                level="warning",
                message="Practice background job was skipped because shutdown has started.",
                context={"label": label},
            )
            return False

        queued_at = time.monotonic()
        queue_size_before = self._background_queue_size()
        self._ensure_background_worker()
        self._background_queue.put((label, queued_at, job))
        log_app_event(
            "app.practice.background_job_queued",
            message="Practice background job was queued.",
            context={
                "label": label,
                "queue_size_before": queue_size_before,
                "queue_size_after": self._background_queue_size(),
            },
        )
        return True

    def _background_worker_loop(self) -> None:
        while True:
            item = self._background_queue.get()
            label = "shutdown"
            job_started_at = time.monotonic()

            try:
                if item is None:
                    return

                label, queued_at, job = item
                job_started_at = time.monotonic()
                log_app_event(
                    "app.practice.background_job_started",
                    message="Practice background job started.",
                    context={
                        "label": label,
                        "queue_wait_ms": round(max(0.0, (job_started_at - queued_at) * 1000.0), 2),
                        "queue_size_remaining": self._background_queue_size(),
                    },
                )
                job()
                log_app_event(
                    "app.practice.background_job_completed",
                    message="Practice background job completed.",
                    context={
                        "label": label,
                        "elapsed_ms": _elapsed_ms(job_started_at),
                        "queue_size_remaining": self._background_queue_size(),
                    },
                )
            except Exception as exc:
                log_app_exception(
                    "app.practice.background_job_failed",
                    exc,
                    message="Practice background job failed.",
                    context={
                        "label": label,
                        "elapsed_ms": _elapsed_ms(job_started_at),
                        "queue_size_remaining": self._background_queue_size(),
                    },
                )
            finally:
                self._background_queue.task_done()

    def _schedule_on_main_thread(self, callback: Callable[[], None]) -> None:
        try:
            self.app.after(0, callback)
        except Exception:
            pass

    def _active_round_or_countdown_running(self) -> bool:
        app = self.app
        return bool(
            getattr(app, "practice_running", False)
            or getattr(app, "start_countdown_running", False)
            or getattr(getattr(app, "round", None), "active", False)
            or getattr(getattr(app, "round", None), "accepting_input", False)
        )

    def _can_apply_decoder_profile_update(self) -> bool:
        return not self._active_round_or_countdown_running()

    def _timing_profile_parameters_from_ui(self) -> dict[str, Any]:
        app = self.app
        helpers = app.ui_helpers_controller

        try:
            use_profile = bool(app.use_timing_profile_var.get())
        except Exception:
            use_profile = bool(getattr(config, "DECODER_USE_TIMING_PROFILE_DEFAULT", True))

        try:
            recent_sessions = helpers.safe_int_var(
                app.decoder_profile_recent_rounds_var,
                default=int(getattr(config, "DECODER_PROFILE_RECENT_ROUNDS", 300)),
                minimum=int(getattr(config, "DECODER_PROFILE_MIN_ROUNDS_REQUIRED", 100)),
                maximum=100000,
            )
        except Exception:
            recent_sessions = int(getattr(config, "DECODER_PROFILE_RECENT_ROUNDS", 300))

        try:
            min_accuracy = float(app.decoder_profile_min_accuracy_var.get())
        except Exception:
            min_accuracy = float(getattr(config, "DECODER_PROFILE_MIN_ACCURACY", 90.0))

        try:
            min_cleanliness = float(app.decoder_profile_min_cleanliness_var.get())
        except Exception:
            min_cleanliness = float(getattr(config, "DECODER_PROFILE_MIN_CLEANLINESS", 85.0))

        return {
            "use_profile": use_profile,
            "recent_sessions": recent_sessions,
            "min_accuracy": min_accuracy,
            "min_cleanliness": min_cleanliness,
            "min_timing_score": float(getattr(config, "DECODER_PROFILE_MIN_TIMING_SCORE", 30.0)),
        }

    def _request_timing_profile_refresh_async(self, *, reason: str) -> None:
        app = self.app
        params = self._timing_profile_parameters_from_ui()

        if not bool(params.get("use_profile")):
            app.timing_profiles = app.decoder_controller.default_timing_profiles()
            return

        self._timing_profile_refresh_generation += 1
        generation = self._timing_profile_refresh_generation
        db_path = app.db.path
        log_app_event(
            "app.timing_profile.async_requested",
            message="Async timing profile refresh was requested.",
            context={"generation": generation, "reason": reason, "params": params},
        )

        def worker() -> None:
            worker_started_at = time.monotonic()
            profiles: Any = None
            error: Exception | None = None
            db: Database | None = None
            perf: dict[str, Any] = {}

            try:
                step_started_at = time.monotonic()
                db = Database.open_background(db_path)
                perf["db_open_elapsed_ms"] = _elapsed_ms(step_started_at)

                step_started_at = time.monotonic()
                profiles = db.load_timing_profiles(
                    recent_sessions=int(params["recent_sessions"]),
                    min_accuracy=float(params["min_accuracy"]),
                    min_cleanliness=float(params["min_cleanliness"]),
                    min_timing_score=float(params["min_timing_score"]),
                )
                perf["load_elapsed_ms"] = _elapsed_ms(step_started_at)
            except Exception as exc:
                error = exc
            finally:
                perf["worker_elapsed_ms"] = _elapsed_ms(worker_started_at)
                log_app_event(
                    "app.timing_profile.async_worker_completed",
                    message="Async timing profile refresh worker completed.",
                    context={
                        "generation": generation,
                        "reason": reason,
                        "error": str(error) if error is not None else None,
                        "perf": perf,
                    },
                )
                if db is not None:
                    db.close()

            self._schedule_on_main_thread(
                lambda: self._apply_timing_profile_refresh_result(
                    generation=generation,
                    reason=reason,
                    profiles=profiles,
                    error=error,
                )
            )

        self._enqueue_background_job("timing_profile_refresh", worker)

    def _request_problem_chars_prefetch_async(
        self,
        *,
        limit: int,
        recent_rounds: int,
        reason: str,
    ) -> None:
        """Refresh problem-character practice candidates without blocking start."""

        app = self.app
        limit = max(1, int(limit))
        recent_rounds = max(1, int(recent_rounds))
        cache_key = (limit, recent_rounds)

        self._practice_problem_chars_generation += 1
        generation = self._practice_problem_chars_generation
        db_path = app.db.path
        log_app_event(
            "app.practice.problem_chars_prefetch_requested",
            message="Problem-character practice prefetch was requested.",
            context={
                "generation": generation,
                "reason": reason,
                "limit": limit,
                "recent_rounds": recent_rounds,
                "cache_key": cache_key,
            },
        )

        def worker() -> None:
            worker_started_at = time.monotonic()
            chars: list[str] = []
            error: Exception | None = None
            db: Database | None = None
            perf: dict[str, Any] = {}

            try:
                step_started_at = time.monotonic()
                db = Database.open_background(db_path)
                perf["db_open_elapsed_ms"] = _elapsed_ms(step_started_at)

                step_started_at = time.monotonic()
                chars = [
                    str(char)
                    for char in db.problem_chars_for_practice(limit, recent_rounds)
                    if str(char or "").strip()
                ]
                perf["load_elapsed_ms"] = _elapsed_ms(step_started_at)
            except Exception as exc:
                error = exc
            finally:
                perf["worker_elapsed_ms"] = _elapsed_ms(worker_started_at)
                log_app_event(
                    "app.practice.problem_chars_prefetch_worker_completed",
                    message="Problem-character practice prefetch worker completed.",
                    context={
                        "generation": generation,
                        "reason": reason,
                        "limit": limit,
                        "recent_rounds": recent_rounds,
                        "count": len(chars),
                        "error": str(error) if error is not None else None,
                        "perf": perf,
                    },
                )
                if db is not None:
                    db.close()

            def apply() -> None:
                if generation != self._practice_problem_chars_generation:
                    log_app_event(
                        "app.practice.problem_chars_prefetch_stale_skipped",
                        message="Stale problem-character practice prefetch was skipped.",
                        context={
                            "generation": generation,
                            "latest": self._practice_problem_chars_generation,
                            "reason": reason,
                            "limit": limit,
                            "recent_rounds": recent_rounds,
                        },
                    )
                    return

                if error is not None:
                    log_app_exception(
                        "app.practice.problem_chars_prefetch_failed",
                        error,
                        level="warning",
                        message="Problem-character practice prefetch failed.",
                        context={
                            "generation": generation,
                            "reason": reason,
                            "limit": limit,
                            "recent_rounds": recent_rounds,
                        },
                    )
                    return

                apply_started_at = time.monotonic()
                self._practice_problem_chars_cache = list(chars)
                self._practice_problem_chars_cache_key = cache_key
                log_app_event(
                    "app.practice.problem_chars_prefetched",
                    message="Problem-character practice candidates were prefetched.",
                    context={
                        "generation": generation,
                        "reason": reason,
                        "limit": limit,
                        "recent_rounds": recent_rounds,
                        "count": len(chars),
                        "apply_elapsed_ms": _elapsed_ms(apply_started_at),
                    },
                )

            self._schedule_on_main_thread(apply)

        self._enqueue_background_job("problem_chars_prefetch", worker)

    def _update_problem_chars_practice_cache_from_rows(
        self,
        rows: list[Any],
        *,
        limit: int,
        recent_rounds: int,
    ) -> None:
        limit = max(1, int(limit))
        recent_rounds = max(1, int(recent_rounds))
        chars: list[str] = []

        for row in rows:
            try:
                char = row["char"]
            except Exception:
                try:
                    char = row.get("char")
                except Exception:
                    char = None

            char_text = str(char or "")
            if char_text and not char_text.isspace():
                chars.append(char_text)

            if len(chars) >= limit:
                break

        self._practice_problem_chars_cache = chars
        self._practice_problem_chars_cache_key = (limit, recent_rounds)

    def _apply_timing_profile_refresh_result(
        self,
        *,
        generation: int,
        reason: str,
        profiles: Any,
        error: Exception | None,
    ) -> None:
        app = self.app

        if generation != self._timing_profile_refresh_generation:
            log_app_event(
                "app.timing_profile.async_stale_skipped",
                message="Stale async timing profile refresh result was skipped.",
                context={"generation": generation, "latest": self._timing_profile_refresh_generation, "reason": reason},
            )
            return

        if error is not None:
            log_app_exception(
                "app.timing_profile.async_failed",
                error,
                level="warning",
                message="Async timing profile refresh failed.",
                context={"generation": generation, "reason": reason},
            )
            if self._can_apply_decoder_profile_update():
                app.timing_profiles = app.decoder_controller.default_timing_profiles()
            return

        if profiles is None:
            return

        if not self._can_apply_decoder_profile_update():
            log_app_event(
                "app.timing_profile.async_apply_deferred",
                message="Async timing profile result was not applied during active practice.",
                context={"generation": generation, "reason": reason},
            )
            return

        app.timing_profiles = profiles
        log_app_event(
            "app.timing_profile.async_applied",
            message="Async timing profile refresh result was applied.",
            context={"generation": generation, "reason": reason},
        )

    def _after_round_analytics_parameters_from_ui(self) -> dict[str, Any]:
        app = self.app
        helpers = app.ui_helpers_controller
        timing = self._timing_profile_parameters_from_ui()

        return {
            "timing": timing,
            "skill_recent_rounds": helpers.safe_int_var(
                app.skill_recent_rounds_var,
                default=getattr(config, "DEFAULT_SKILL_RATING_RECENT_ROUNDS", 1000),
                minimum=1,
                maximum=100000,
            ),
            "history_recent_sessions": int(getattr(config, "HISTORY_TABLE_RECENT_SESSIONS", 1000)),
            "problem_limit": int(getattr(config, "PROBLEM_CHARACTER_DISPLAY_LIMIT", 10000)),
            "problem_recent_rounds": helpers.safe_int_var(
                app.problem_recent_rounds_var,
                default=config.DEFAULT_PROBLEM_RECENT_ROUNDS,
                minimum=1,
                maximum=100000,
            ),
            "stats_recent_rounds": helpers.safe_int_var(
                app.stats_recent_rounds_var,
                default=1000,
                minimum=1,
                maximum=100000,
            ),
            "effective_recent_rounds": helpers.safe_int_var(
                app.effective_wpm_recent_rounds_var,
                default=getattr(config, "DEFAULT_EFFECTIVE_WPM_RECENT_ROUNDS", 1000),
                minimum=1,
                maximum=100000,
            ),
            "effective_min_accuracy": helpers.safe_int_var(
                app.effective_wpm_min_accuracy_var,
                default=getattr(config, "DEFAULT_EFFECTIVE_WPM_MIN_ACCURACY", 90),
                minimum=0,
                maximum=100,
            ),
            "effective_min_cleanliness": helpers.safe_int_var(
                app.effective_wpm_min_cleanliness_var,
                default=getattr(config, "DEFAULT_EFFECTIVE_WPM_MIN_CLEANLINESS", 85),
                minimum=0,
                maximum=100,
            ),
        }

    def _request_after_round_analytics_async(
        self,
        session_id: int,
        snapshot_session_ids: Sequence[int] | None = None,
    ) -> None:
        app = self.app
        params = self._after_round_analytics_parameters_from_ui()
        db_path = app.db.path

        snapshot_ids = self._normalize_snapshot_session_ids(snapshot_session_ids, fallback=session_id)

        self._after_round_analytics_generation += 1
        generation = self._after_round_analytics_generation
        log_app_event(
            "app.practice.after_round_analytics_requested",
            message="Background after-round analytics was requested.",
            context={
                "session_id": session_id,
                "snapshot_session_ids": snapshot_ids,
                "snapshot_count": len(snapshot_ids),
                "generation": generation,
                "params": params,
                "active_round_or_countdown": self._active_round_or_countdown_running(),
            },
        )

        def worker() -> None:
            worker_started_at = time.monotonic()
            payload: dict[str, Any] = {"errors": {}, "perf": {}}
            db: Database | None = None

            def record_step(step: str, started_at: float, extra: dict[str, Any] | None = None) -> None:
                elapsed = _elapsed_ms(started_at)
                payload["perf"][f"{step}_elapsed_ms"] = elapsed
                context: dict[str, Any] = {
                    "session_id": session_id,
                    "generation": generation,
                    "step": step,
                    "elapsed_ms": elapsed,
                }
                if extra:
                    context.update(extra)
                log_app_event(
                    "app.practice.after_round_analytics_step",
                    message="Background after-round analytics step completed.",
                    context=context,
                )

            try:
                step_started_at = time.monotonic()
                db = Database.open_background(db_path)
                record_step("db_open", step_started_at)

                timing = dict(params.get("timing") or {})
                if bool(timing.get("use_profile")):
                    try:
                        step_started_at = time.monotonic()
                        payload["timing_profiles"] = db.load_timing_profiles(
                            recent_sessions=int(timing["recent_sessions"]),
                            min_accuracy=float(timing["min_accuracy"]),
                            min_cleanliness=float(timing["min_cleanliness"]),
                            min_timing_score=float(timing["min_timing_score"]),
                        )
                        record_step("timing_profiles", step_started_at)
                    except Exception as exc:
                        payload["errors"]["timing_profiles"] = str(exc)
                        log_app_exception(
                            "app.timing_profile.background_refresh_failed",
                            exc,
                            level="warning",
                            message="Background timing profile refresh failed after round.",
                            context={"session_id": session_id, "generation": generation},
                        )

                try:
                    step_started_at = time.monotonic()
                    latest_rating = None
                    saved_snapshot_ids: list[int] = []

                    for snapshot_session_id in snapshot_ids:
                        rating = calculate_skill_rating(
                            db,
                            recent_rounds=int(params["skill_recent_rounds"]),
                            max_session_id=int(snapshot_session_id),
                        )
                        db.save_skill_rating_snapshot(int(snapshot_session_id), rating)
                        latest_rating = rating
                        saved_snapshot_ids.append(int(snapshot_session_id))

                    if latest_rating is None:
                        latest_rating = calculate_skill_rating(
                            db,
                            recent_rounds=int(params["skill_recent_rounds"]),
                            max_session_id=int(session_id),
                        )
                        db.save_skill_rating_snapshot(int(session_id), latest_rating)
                        saved_snapshot_ids.append(int(session_id))

                    payload["rating"] = latest_rating
                    payload["skill_snapshot_session_ids"] = saved_snapshot_ids

                    record_step(
                        "skill_rating_snapshot_batch",
                        step_started_at,
                        {
                            "snapshot_count": len(saved_snapshot_ids),
                            "snapshot_session_ids": saved_snapshot_ids,
                            "latest_session_id": saved_snapshot_ids[-1] if saved_snapshot_ids else session_id,
                            "rating": summarize_rating(latest_rating),
                        },
                    )
                except Exception as exc:
                    payload["errors"]["skill_rating"] = str(exc)
                    log_app_exception(
                        "app.skill_rating.background_failed",
                        exc,
                        message="Background skill rating calculation or snapshot save failed after round.",
                        context={
                            "session_id": session_id,
                            "snapshot_session_ids": snapshot_ids,
                            "generation": generation,
                        },
                    )

                try:
                    step_started_at = time.monotonic()
                    payload["history_rows"] = [
                        dict(row)
                        for row in db.recent_sessions(int(params["history_recent_sessions"]))
                    ]
                    record_step(
                        "history_rows",
                        step_started_at,
                        {"row_count": len(payload["history_rows"])},
                    )
                except Exception as exc:
                    payload["errors"]["history_rows"] = str(exc)
                    log_app_exception(
                        "app.history.background_table_failed",
                        exc,
                        message="Background recent sessions load failed after round.",
                        context={"session_id": session_id, "generation": generation},
                    )

                try:
                    step_started_at = time.monotonic()
                    payload["problem_rows"] = [
                        dict(row)
                        for row in db.problem_characters(
                            int(params["problem_limit"]),
                            int(params["problem_recent_rounds"]),
                        )
                    ]
                    record_step(
                        "problem_rows",
                        step_started_at,
                        {"row_count": len(payload["problem_rows"])},
                    )
                except Exception as exc:
                    payload["errors"]["problem_rows"] = str(exc)
                    log_app_exception(
                        "app.history.background_problem_table_failed",
                        exc,
                        message="Background problem-character load failed after round.",
                        context={"session_id": session_id, "generation": generation},
                    )

                try:
                    step_started_at = time.monotonic()
                    payload["stats"] = db.stats_summary(int(params["stats_recent_rounds"]))
                    record_step(
                        "stats",
                        step_started_at,
                        {"rounds": (payload["stats"] or {}).get("rounds")},
                    )
                except Exception as exc:
                    payload["errors"]["stats"] = str(exc)
                    log_app_exception(
                        "app.history.background_stats_failed",
                        exc,
                        message="Background stats summary load failed after round.",
                        context={"session_id": session_id, "generation": generation},
                    )

                try:
                    step_started_at = time.monotonic()
                    payload["effective_wpm_result"] = db.optimized_wpm_from_recent_sessions(
                        recent_sessions=int(params["effective_recent_rounds"]),
                        min_accuracy=int(params["effective_min_accuracy"]),
                        min_cleanliness=int(params["effective_min_cleanliness"]),
                    )
                    result = payload["effective_wpm_result"] or {}
                    record_step(
                        "effective_wpm",
                        step_started_at,
                        {"ok": bool(result.get("ok")), "used_rounds": result.get("used_rounds")},
                    )
                except Exception as exc:
                    payload["errors"]["effective_wpm"] = str(exc)
                    log_app_exception(
                        "app.effective_wpm.background_indicator_failed",
                        exc,
                        level="warning",
                        message="Background effective WPM indicator calculation failed after round.",
                        context={"session_id": session_id, "generation": generation},
                    )
            finally:
                payload["perf"]["worker_elapsed_ms"] = _elapsed_ms(worker_started_at)
                log_app_event(
                    "app.practice.after_round_analytics_worker_completed",
                    message="Background after-round analytics worker completed.",
                    context={
                        "session_id": session_id,
                        "snapshot_session_ids": snapshot_ids,
                        "generation": generation,
                        "errors": dict(payload.get("errors") or {}),
                        "perf": dict(payload.get("perf") or {}),
                    },
                )
                if db is not None:
                    db.close()

            self._schedule_on_main_thread(
                lambda: self._apply_after_round_analytics_result(
                    generation=generation,
                    session_id=session_id,
                    params=params,
                    payload=payload,
                )
            )

        self._enqueue_background_job("after_round_analytics", worker)

    def _apply_after_round_analytics_result(
        self,
        *,
        generation: int,
        session_id: int,
        params: dict[str, Any],
        payload: dict[str, Any],
    ) -> None:
        app = self.app

        if generation != self._after_round_analytics_generation:
            log_app_event(
                "app.practice.after_round_analytics_stale_skipped",
                message="Stale after-round analytics result was skipped.",
                context={"session_id": session_id, "generation": generation, "latest": self._after_round_analytics_generation},
            )
            return

        apply_started_at = time.monotonic()
        ui_perf: dict[str, Any] = {}

        def record_ui_step(step: str, started_at: float, extra: dict[str, Any] | None = None) -> None:
            elapsed = _elapsed_ms(started_at)
            ui_perf[f"{step}_elapsed_ms"] = elapsed
            context: dict[str, Any] = {
                "session_id": session_id,
                "generation": generation,
                "step": step,
                "elapsed_ms": elapsed,
            }
            if extra:
                context.update(extra)
            log_app_event(
                "app.practice.after_round_analytics_ui_step",
                message="After-round analytics UI step completed.",
                context=context,
            )

        log_app_event(
            "app.practice.after_round_analytics_apply_started",
            message="Background after-round analytics apply started on the UI thread.",
            context={
                "session_id": session_id,
                "generation": generation,
                "worker_perf": dict(payload.get("perf") or {}),
                "active_round_or_countdown": self._active_round_or_countdown_running(),
                "history_row_count": len(payload.get("history_rows") or []),
                "problem_row_count": len(payload.get("problem_rows") or []),
            },
        )

        try:
            profiles = payload.get("timing_profiles")
            if profiles is not None and self._can_apply_decoder_profile_update():
                step_started_at = time.monotonic()
                app.timing_profiles = profiles
                record_ui_step("timing_profiles_apply", step_started_at)

            if "history_rows" in payload:
                history_rows = list(payload.get("history_rows") or [])
                step_started_at = time.monotonic()
                incremental_done = False

                if bool(getattr(config, "HISTORY_TABLE_INCREMENTAL_AFTER_ROUND", True)) and history_rows:
                    incremental_done = app.history_controller.update_recent_history_table_incremental(
                        history_rows[0],
                        limit=int(params["history_recent_sessions"]),
                    )

                if not incremental_done:
                    app.history_controller.load_history_table(rows=history_rows)

                record_ui_step(
                    "history_table_incremental_update" if incremental_done else "history_table_schedule",
                    step_started_at,
                    {
                        "row_count": len(history_rows),
                        "incremental": incremental_done,
                    },
                )

            if "problem_rows" in payload:
                problem_rows = payload["problem_rows"]
                step_started_at = time.monotonic()
                app.history_controller.load_problem_table(rows=problem_rows)
                record_ui_step("problem_table_apply", step_started_at, {"row_count": len(problem_rows)})

                step_started_at = time.monotonic()
                self._update_problem_chars_practice_cache_from_rows(
                    problem_rows,
                    limit=int(getattr(config, "DEFAULT_PROBLEM_CHAR_CANDIDATE_LIMIT", 50)),
                    recent_rounds=int(params["problem_recent_rounds"]),
                )
                record_ui_step("problem_practice_cache_update", step_started_at, {"row_count": len(problem_rows)})

            if "stats" in payload:
                step_started_at = time.monotonic()
                app.history_controller.update_stats_summary(
                    stats=payload["stats"],
                    recent_rounds=int(params["stats_recent_rounds"]),
                )
                record_ui_step("stats_summary_apply", step_started_at)

            rating = payload.get("rating")
            if rating is not None:
                step_started_at = time.monotonic()
                app.history_controller.update_skill_rating_summary(
                    cached_rating=rating,
                    allow_level_up_sound=True,
                    allow_recalculate=False,
                )
                record_ui_step("skill_summary_apply", step_started_at, {"rating": summarize_rating(rating)})

            if "effective_wpm_result" in payload:
                step_started_at = time.monotonic()
                app.history_controller.update_target_wpm_suggestion_indicator(
                    result=payload["effective_wpm_result"],
                )
                result = payload.get("effective_wpm_result") or {}
                record_ui_step(
                    "effective_wpm_indicator_apply",
                    step_started_at,
                    {"ok": bool(result.get("ok")), "used_rounds": result.get("used_rounds")},
                )

            if not self._active_round_or_countdown_running():
                step_started_at = time.monotonic()
                app.history_controller.refresh_stats_window_if_open()
                record_ui_step("stats_window_refresh", step_started_at)

            ui_perf["total_apply_elapsed_ms"] = _elapsed_ms(apply_started_at)
            log_app_event(
                "app.practice.after_round_analytics_applied",
                message="Background after-round analytics result was applied.",
                context={
                    "session_id": session_id,
                    "generation": generation,
                    "errors": dict(payload.get("errors") or {}),
                    "worker_perf": dict(payload.get("perf") or {}),
                    "ui_perf": ui_perf,
                },
            )
        except Exception as exc:
            log_app_exception(
                "app.practice.after_round_analytics_apply_failed",
                exc,
                message="Applying background after-round analytics failed.",
                context={
                    "session_id": session_id,
                    "generation": generation,
                    "worker_perf": dict(payload.get("perf") or {}),
                    "ui_perf": ui_perf,
                    "elapsed_ms": _elapsed_ms(apply_started_at),
                },
            )
            if not self._active_round_or_countdown_running():
                app.status_var.set(
                    app.i18n.t(
                        "practice.status.saved_round_summary_failed",
                        "Saved round #{session_id}, but updating summaries failed: {error}",
                        session_id=session_id,
                        error=exc,
                    )
                )

    def start_practice(self) -> None:
        """Start a full practice series from the current UI settings."""
        app = self.app
        start_started_at = time.monotonic()

        if app.start_countdown_running:
            self._cancel_start_countdown(restore_state_text=False)

        log_app_event(
            "app.practice.start_requested",
            message="Practice start requested.",
            context={
                "start_countdown_running": bool(getattr(app, "start_countdown_running", False)),
                "serial_connected": bool(getattr(app, "serial_connected", False)),
            },
        )

        self._cancel_low_priority_history_render()

        app.serial_controller.request_auto_connect_scan()
        app.settings = app.challenge_settings_controller.settings_from_ui()
        self._request_timing_profile_refresh_async(reason="start_practice")
        app.practice_running = True
        app.current_round_number = 0
        app.total_rounds = max(1, int(app.settings.practice_rounds))
        app.practice_summaries = []
        self._reschedule_pending_after_round_analytics(reason="start_practice")

        practice_started_at = datetime.now()
        practice_token = self._new_practice_token(started_at=practice_started_at)
        self.current_practice_id = None
        log_app_event(
            "app.practice.started",
            message="Practice series started in the UI; database practice row creation is deferred until the first background save.",
            context={
                "practice_token": practice_token,
                "practice_id": None,
                "total_rounds": app.total_rounds,
                "settings": summarize_challenge_settings(app.settings),
            },
        )

        self.pending_after_round_updates_session_id = None

        step_started_at = time.monotonic()
        self._update_practice_buttons()
        app.results_controller.update_practice_series_summary()
        log_app_event(
            "app.practice.start_ui_prepared",
            message="Practice start UI preparation completed.",
            context={"elapsed_ms": _elapsed_ms(step_started_at), "practice_token": practice_token},
        )
        app.status_controller.set_main_status(
            app.i18n.t(
                "practice.status.starting",
                "Practice starts. Total rounds: {total_rounds}.",
                total_rounds=app.total_rounds,
            ),
            state="normal",
        )
        self._start_next_round()
        log_app_event(
            "app.practice.start_completed",
            message="Practice start completed on the UI thread.",
            context={
                "practice_token": practice_token,
                "total_rounds": app.total_rounds,
                "elapsed_ms": _elapsed_ms(start_started_at),
            },
        )

    def stop_practice(self) -> None:
        """Stop the current practice series or cancel a pending countdown."""
        app = self.app

        if app.start_countdown_running:
            log_app_event(
                "app.practice.start_countdown_cancelled",
                message="Practice start countdown was cancelled by stop request.",
            )
            self._cancel_start_countdown(restore_state_text=True)
            app.status_controller.set_main_status(
                app.i18n.t("practice.status.start_cancelled", "Start cancelled."),
                state="normal",
            )
            return

        self._cancel_inter_round_countdown(restore_state_text=True)

        log_app_event(
            "app.practice.stop_requested",
            message="Practice stop requested.",
            context={
                "practice_id": self.current_practice_id,
                "round_number": getattr(app.round, "round_number", 0),
                "round_active": bool(getattr(app.round, "active", False)),
                "round_finished": bool(getattr(app.round, "finished", False)),
            },
        )

        app.practice_running = False

        if app.round.active and not app.round.finished:
            self._discard_current_round(FINISH_REASON_USER_STOPPED)

        if self.current_practice_id is not None:
            stopped_practice_id = self.current_practice_id
            app.db.finish_practice(stopped_practice_id, "stopped")
            log_app_event(
                "app.practice.stopped",
                message="Practice series was stopped.",
                context={"practice_id": stopped_practice_id},
            )
        elif self.current_practice_token is not None:
            log_app_event(
                "app.practice.stopped_ui_only",
                message="Practice series was stopped before its database practice row had been created.",
                context={"practice_token": self.current_practice_token},
            )

        self._clear_current_practice_reference()
        self._schedule_pending_after_round_updates()

        app.round_state_var.set(
            app.i18n.t("practice.round_state.stopped", "Practice: stopped")
        )
        app.status_var.set(
            app.i18n.t(
                "practice.status.stopped_not_saved",
                "Practice stopped. The unfinished round was not saved.",
            )
        )
        app.input_entry.configure(state=tk.NORMAL)
        app.app_lifecycle_controller.focus_input(force=True)
        self._update_practice_buttons()

    def _start_next_round(self) -> None:
        """Create and display the next round target."""
        app = self.app

        if not app.practice_running:
            return

        if app.current_round_number >= app.total_rounds:
            self._finish_practice_series()
            return

        app.current_round_number += 1
        target_generation_started_at = time.monotonic()
        target = self._generate_round_target()
        target_generation_elapsed_ms = _elapsed_ms(target_generation_started_at)
        generation_context = dict(self._last_round_generation_context)
        log_app_event(
            "app.practice.round_target_generated",
            message="Practice round target generated.",
            context={
                "practice_id": self.current_practice_id,
                "round_number": app.current_round_number,
                "total_rounds": app.total_rounds,
                "target_length": len(target),
                "target_generation_elapsed_ms": target_generation_elapsed_ms,
                **generation_context,
            },
        )

        app.round = RoundState(
            target=target,
            active=True,
            accepting_input=True,
            finished=False,
            round_number=app.current_round_number,
            total_rounds=app.total_rounds,
        )

        log_app_event(
            "app.practice.round_started",
            message="Practice round started.",
            context={
                "practice_id": self.current_practice_id,
                "round_number": app.current_round_number,
                "total_rounds": app.total_rounds,
                "target_length": len(target),
            },
        )

        app.live_decoder = app.decoder_controller.new_live_decoder(target)
        app.live_ui_dirty = False
        app.live_result_dirty = False
        app.last_live_ui_refresh_monotonic = 0.0
        app.last_live_score_refresh_monotonic = 0.0
        app.last_summary = None
        app.last_char_results = []
        app.last_tone_event_key = None
        app.viewing_history_session_id = None
        app.latest_result_reset_for_current_round = False

        app.input_entry.configure(state=tk.NORMAL)
        app.input_var.set("")
        app.target_var.set(target)
        app.decoder_controller.clear_telemetry_display()
        app.timer_var.set(self._reference_time_label())
        app.round_state_var.set(
            app.i18n.t(
                "practice.round_state.ready_to_start",
                "Round {current}/{total}: ready to start",
                current=app.current_round_number,
                total=app.total_rounds,
            )
        )
        app.status_var.set(
            app.i18n.t("practice.status.start_morse", "Start sending Morse.")
        )

        app.input_controller.drain_serial_queue()
        app.decoder_controller.clear_raw_telemetry()
        app.app_lifecycle_controller.focus_input(force=True)

    def _generate_round_target(self) -> str:
        """Generate the target text for one practice round."""
        app = self.app
        helpers = app.ui_helpers_controller

        if app.wxmor_controller.mode_enabled():
            wxmor_profile = app.wxmor_controller.profile()
            self._last_round_generation_context = {
                "wxmor": True,
                "wxmor_profile": wxmor_profile,
                "settings": summarize_challenge_settings(app.settings),
            }
            return generate_wxmor_challenge(
                profile=wxmor_profile,
            )

        problem_recent_rounds = helpers.safe_int_var(
            app.problem_recent_rounds_var,
            default=config.DEFAULT_PROBLEM_RECENT_ROUNDS,
            minimum=1,
            maximum=100000,
        )
        problem_limit = int(getattr(config, "DEFAULT_PROBLEM_CHAR_CANDIDATE_LIMIT", 50))
        problem_chars_enabled = bool(getattr(app.settings, "practice_problem_chars", False))
        problem_chars: list[str] = []
        problem_cache_hit = False

        if problem_chars_enabled:
            cache_key = (problem_limit, problem_recent_rounds)

            if self._practice_problem_chars_cache_key == cache_key:
                problem_chars = list(self._practice_problem_chars_cache)
                problem_cache_hit = True
            else:
                self._request_problem_chars_prefetch_async(
                    limit=problem_limit,
                    recent_rounds=problem_recent_rounds,
                    reason="start_round_target_generation",
                )

        self._last_round_generation_context = {
            "wxmor": False,
            "problem_chars_enabled": problem_chars_enabled,
            "problem_recent_rounds": problem_recent_rounds,
            "problem_char_candidates_count": len(problem_chars),
            "problem_char_cache_hit": problem_cache_hit,
            "settings": summarize_challenge_settings(app.settings),
        }

        return generate_challenge(app.settings, problem_chars)

    def _finish_practice_series(self) -> None:
        """Mark the practice series as finished without starting another round."""
        app = self.app

        app.practice_running = False

        if self.current_practice_id is not None:
            completed_practice_id = self.current_practice_id
            app.db.finish_practice(completed_practice_id, "completed")
            log_app_event(
                "app.practice.series_completed",
                message="Practice series completed.",
                context={"practice_id": completed_practice_id, "total_rounds": app.total_rounds},
            )
        elif self.current_practice_token is not None:
            log_app_event(
                "app.practice.series_completed_ui_only",
                message="Practice series was completed before its database practice row had been created.",
                context={"practice_token": self.current_practice_token, "total_rounds": app.total_rounds},
            )

        self._clear_current_practice_reference()
        self._schedule_pending_after_round_updates()

        app.round_state_var.set(
            app.i18n.t("practice.round_state.series_complete", "Practice: complete")
        )
        app.status_var.set(
            app.i18n.t(
                "practice.status.series_complete",
                "The whole practice series is complete.",
            )
        )
        app.input_entry.configure(state=tk.NORMAL)
        app.app_lifecycle_controller.focus_input(force=True)
        self._update_practice_buttons()

    def _discard_current_round(self, reason: str) -> None:
        """Discard the active unfinished round without saving it."""
        app = self.app

        app.round.accepting_input = False
        app.round.active = False
        app.round.finished = True
        app.round.finish_reason = reason
        app.round.finished_at = datetime.now()
        app.round.host_finished_time = time.monotonic()

        app.input_var.set("")
        app.decoder_controller.clear_telemetry_display()
        app.timer_var.set(app.i18n.t("runtime.timer_placeholder", "Time: -"))

        if app.latest_result_reset_for_current_round:
            app.results_controller.reset_latest_result_values()

        app.decoder_controller.clear_raw_telemetry()
        app.live_decoder = None
        app.live_ui_dirty = False
        app.live_result_dirty = False
        log_app_event(
            "app.practice.round_discarded",
            message="Unfinished practice round discarded.",
            context={
                "practice_id": self.current_practice_id,
                "round_number": app.round.round_number,
                "finish_reason": reason,
            },
        )

    def finish_round(self, reason: str, auto_continue: bool = True) -> None:
        """Finalize the current round and schedule automatic saving."""
        app = self.app

        if not app.round.target or app.round.finished:
            return

        log_app_event(
            "app.practice.round_finish_requested",
            message="Practice round finish requested.",
            context={
                "practice_id": self.current_practice_id,
                "round_number": app.round.round_number,
                "finish_reason": reason,
                "auto_continue": bool(auto_continue),
                "target_length": len(app.round.target),
                "event_count": len(app.round.events),
            },
        )

        self._mark_round_finished(reason)
        self._finalize_round_decoding_and_score()

        if app.last_summary is not None:
            log_app_event(
                "app.practice.round_finished",
                message="Practice round finalized and scored.",
                context={
                    "practice_id": self.current_practice_id,
                    "round_number": app.round.round_number,
                    "finish_reason": reason,
                    "event_count": len(app.round.events),
                    "char_result_count": len(app.last_char_results),
                    "summary": summarize_score_summary(app.last_summary),
                },
            )
            app.practice_summaries.append(app.last_summary)
            app.results_controller.update_practice_series_summary()
            reason_label = self.finish_reason_label(reason)

            app.round_state_var.set(
                app.i18n.t(
                    "practice.round_state.complete_with_reason",
                    "Round {current}/{total}: complete ({reason})",
                    current=app.current_round_number,
                    total=app.total_rounds,
                    reason=reason_label,
                )
            )
            app.status_var.set(
                app.i18n.t(
                    "practice.status.auto_saving_round",
                    "Round is being saved automatically.",
                )
            )
            app.input_entry.configure(state=tk.DISABLED)

            round_started_at = app.round.started_at or datetime.now()
            app.round.started_at = round_started_at

            round_summary = app.last_summary
            round_settings = copy.deepcopy(app.settings)
            round_events = [dict(event) for event in app.round.events]
            round_char_results = list(app.last_char_results)
            round_practice_id = self.current_practice_id
            round_practice_token = self.current_practice_token
            round_practice_started_at = self.current_practice_started_at or round_started_at
            round_total_rounds = int(app.total_rounds)
            round_number = int(app.round.round_number)

            should_continue_to_next_round = (
                auto_continue
                and app.practice_running
                and app.current_round_number < app.total_rounds
            )

            if should_continue_to_next_round:
                self._begin_inter_round_countdown()
                save_auto_continue = False
            else:
                save_auto_continue = auto_continue

            app.after(
                50,
                lambda: self._save_finished_round(
                    auto_continue=save_auto_continue,
                    show_saved_status=not should_continue_to_next_round,
                    started_at=round_started_at,
                    summary=round_summary,
                    settings_snapshot=round_settings,
                    events=round_events,
                    char_results=round_char_results,
                    practice_id=round_practice_id,
                    practice_token=round_practice_token,
                    practice_started_at=round_practice_started_at,
                    practice_planned_rounds=round_total_rounds,
                    round_number=round_number,
                ),
            )
            return

        if auto_continue and app.practice_running:
            self._advance_after_finished_round()

    def _mark_round_finished(self, reason: str) -> None:
        """Freeze the current round state and store finish timestamps."""
        app = self.app

        app.round.accepting_input = False
        app.round.active = False
        app.round.finished = True
        app.round.finish_reason = reason
        app.round.started_at = app.round.started_at or datetime.now()
        app.round.finished_at = datetime.now()
        app.round.host_finished_time = time.monotonic()

    def _finalize_round_decoding_and_score(self) -> None:
        """Run final decoding, telemetry drawing and scoring for the round."""
        app = self.app

        self._update_adaptive_decoded_text(flush_final=True)
        app.decoder_controller.draw_raw_telemetry()
        self.evaluate_live()
        app.live_ui_dirty = False
        app.live_result_dirty = False

    def _advance_after_finished_round(self, *, finish_database: bool = True) -> None:
        """Continue to the next round or finish the whole practice series."""
        app = self.app

        if app.current_round_number < app.total_rounds:
            self._begin_inter_round_countdown()
            return

        app.practice_running = False

        if self.current_practice_id is not None:
            completed_practice_id = self.current_practice_id

            if finish_database:
                app.db.finish_practice(completed_practice_id, "completed")
                log_app_event(
                    "app.practice.series_completed",
                    message="Practice series completed after final round.",
                    context={"practice_id": completed_practice_id, "total_rounds": app.total_rounds},
                )
            else:
                log_app_event(
                    "app.practice.series_completed_ui_only",
                    message="Practice series was completed in the UI; database finish is queued in the background.",
                    context={"practice_id": completed_practice_id, "total_rounds": app.total_rounds},
                )
        elif self.current_practice_token is not None:
            log_app_event(
                "app.practice.series_completed_ui_only",
                message="Practice series was completed in the UI before its database practice row had been created.",
                context={"practice_token": self.current_practice_token, "total_rounds": app.total_rounds},
            )

        self._clear_current_practice_reference()

        if finish_database:
            self._schedule_pending_after_round_updates()

        app.status_controller.set_main_status(
            app.i18n.t(
                "practice.status.series_complete_upper",
                "PRACTICE SERIES COMPLETE",
            ),
            state="success",
        )
        app.round_state_var.set(
            app.i18n.t("practice.round_state.series_complete", "Practice: complete")
        )
        app.audio_controller.play_sound("practice_complete")
        app.results_controller.set_practice_total_time_label()
        app.input_entry.configure(state=tk.NORMAL)
        self._update_practice_buttons()

    def shutdown_active_practice(self) -> None:
        """Mark an unfinished practice as interrupted during application shutdown.

        Already saved rounds remain saved. An active unfinished round is not saved.
        """

        app = self.app

        self._cancel_inter_round_countdown(restore_state_text=False)

        if self.current_practice_id is None:
            self._clear_current_practice_reference()
            app.practice_running = False
            return

        try:
            interrupted_practice_id = self.current_practice_id
            app.db.finish_practice(interrupted_practice_id, "interrupted")
            log_app_event(
                "app.practice.interrupted_on_shutdown",
                message="Active practice was marked interrupted during shutdown.",
                context={"practice_id": interrupted_practice_id},
            )
        finally:
            self._clear_current_practice_reference()
            app.practice_running = False

    def _save_finished_round(
        self,
        *,
        auto_continue: bool = True,
        show_saved_status: bool = True,
        started_at: Optional[datetime] = None,
        summary: Any = None,
        settings_snapshot: Optional[Any] = None,
        events: Optional[list[Dict[str, Any]]] = None,
        char_results: Optional[list[Any]] = None,
        practice_id: Optional[int] = None,
        practice_token: Optional[int] = None,
        practice_started_at: Optional[datetime] = None,
        practice_planned_rounds: Optional[int] = None,
        round_number: Optional[int] = None,
    ) -> None:
        """Queue persistence for a finished round from an immutable snapshot."""
        app = self.app
        prepare_started_at = time.monotonic()

        summary = summary if summary is not None else app.last_summary

        if summary is None:
            if auto_continue and app.practice_running:
                self._advance_after_finished_round()
            return

        started_at = started_at or app.round.started_at or datetime.now()
        events = copy.deepcopy(
            events
            if events is not None
            else [dict(event) for event in app.round.events]
        )
        char_results = copy.deepcopy(
            char_results
            if char_results is not None
            else list(app.last_char_results)
        )
        summary = copy.deepcopy(summary)
        settings = copy.deepcopy(settings_snapshot if settings_snapshot is not None else app.settings)

        if practice_token is None:
            practice_token = self.current_practice_token

        if practice_id is None:
            practice_id = self._practice_db_id_for_token(practice_token)

        practice_started_at = practice_started_at or self.current_practice_started_at or started_at
        practice_planned_rounds = max(
            1,
            int(practice_planned_rounds if practice_planned_rounds is not None else app.total_rounds),
        )

        if round_number is None:
            round_number = int(app.round.round_number)

        self._background_save_generation += 1
        save_generation = self._background_save_generation
        db_path = app.db.path

        finish_practice_status: str | None = None
        should_finish_practice_in_background = bool(
            auto_continue
            and app.practice_running
            and int(round_number) >= int(app.total_rounds)
        )

        if should_finish_practice_in_background:
            finish_practice_status = "completed"

        log_app_event(
            "app.practice.round_save_queued",
            message="Finished practice round save was queued for the background worker.",
            context={
                "practice_id": practice_id,
                "practice_token": practice_token,
                "round_number": round_number,
                "save_generation": save_generation,
                "finish_practice_status": finish_practice_status,
                "event_count": len(events),
                "char_result_count": len(char_results),
                "prepare_elapsed_ms": _elapsed_ms(prepare_started_at),
                "summary": summarize_score_summary(summary),
            },
        )

        try:
            app.debug_controller.write_round_snapshot_if_enabled()
        except Exception as exc:
            log_app_exception(
                "app.debug.snapshot_write_after_round_failed",
                exc,
                level="warning",
                message="Round debug snapshot write failed before background save.",
                context={"practice_id": practice_id, "practice_token": practice_token, "round_number": round_number},
            )

        def worker() -> None:
            session_id: int | None = None
            saved_practice_id: int | None = None
            history_row: dict[str, Any] | None = None
            error: Exception | None = None
            db: Database | None = None
            worker_started_at = time.monotonic()
            perf: dict[str, Any] = {}

            try:
                log_app_event(
                    "app.practice.round_save_started",
                    message="Finished practice round save started in the background worker.",
                    context={
                        "practice_id": practice_id,
                        "practice_token": practice_token,
                        "round_number": round_number,
                        "save_generation": save_generation,
                        "event_count": len(events),
                        "char_result_count": len(char_results),
                        "prepare_elapsed_ms": _elapsed_ms(prepare_started_at),
                        "summary": summarize_score_summary(summary),
                    },
                )
                step_started_at = time.monotonic()
                db = Database.open_background(db_path)
                perf["db_open_elapsed_ms"] = _elapsed_ms(step_started_at)

                saved_practice_id = None if practice_id is None else int(practice_id)

                if saved_practice_id is None:
                    saved_practice_id = self._practice_db_id_for_token(practice_token)

                if saved_practice_id is None:
                    step_started_at = time.monotonic()
                    saved_practice_id = db.create_practice(
                        practice_started_at,
                        int(practice_planned_rounds),
                        settings,
                    )
                    perf["create_practice_elapsed_ms"] = _elapsed_ms(step_started_at)
                    self._remember_practice_db_id_for_token(practice_token, saved_practice_id)
                    log_app_event(
                        "app.practice.background_practice_created",
                        message="Deferred practice row was created in the background worker.",
                        context={
                            "practice_id": saved_practice_id,
                            "practice_token": practice_token,
                            "planned_rounds": int(practice_planned_rounds),
                        },
                    )

                step_started_at = time.monotonic()
                session_id = db.save_session(
                    started_at,
                    summary,
                    settings,
                    events,
                    char_results,
                    practice_id=int(saved_practice_id),
                    round_number=int(round_number),
                )
                perf["save_session_elapsed_ms"] = _elapsed_ms(step_started_at)

                step_started_at = time.monotonic()
                try:
                    row = db.session_history_row(int(session_id))
                    history_row = None if row is None else dict(row)
                finally:
                    perf["history_row_elapsed_ms"] = _elapsed_ms(step_started_at)

                step_started_at = time.monotonic()
                db.refresh_practice_progress(int(saved_practice_id))
                perf["refresh_practice_progress_elapsed_ms"] = _elapsed_ms(step_started_at)

                if finish_practice_status is not None:
                    step_started_at = time.monotonic()
                    db.finish_practice(int(saved_practice_id), finish_practice_status)
                    perf["finish_practice_elapsed_ms"] = _elapsed_ms(step_started_at)

            except Exception as exc:
                error = exc
            finally:
                perf["worker_elapsed_ms"] = _elapsed_ms(worker_started_at)
                log_app_event(
                    "app.practice.round_save_worker_completed",
                    message="Finished practice round save worker completed.",
                    context={
                        "session_id": session_id,
                        "practice_id": saved_practice_id,
                        "practice_token": practice_token,
                        "round_number": round_number,
                        "save_generation": save_generation,
                        "error": str(error) if error is not None else None,
                        "perf": perf,
                    },
                )
                if db is not None:
                    db.close()

            self._schedule_on_main_thread(
                lambda: self._apply_finished_round_save_result(
                    save_generation=save_generation,
                    session_id=session_id,
                    error=error,
                    show_saved_status=show_saved_status,
                    events=events,
                    char_results=char_results,
                    practice_id=saved_practice_id,
                    practice_token=practice_token,
                    round_number=int(round_number),
                    summary=summary,
                    history_row=history_row,
                )
            )

        queued = self._enqueue_background_job("save_finished_round", worker)

        if should_finish_practice_in_background:
            self._advance_after_finished_round(finish_database=False)
        elif auto_continue and app.practice_running:
            self._advance_after_finished_round()

        if not queued and not self._active_round_or_countdown_running():
            app.status_var.set(
                app.i18n.t(
                    "practice.status.save_not_queued",
                    "Round could not be queued for saving because the application is shutting down.",
                )
            )

    def _apply_finished_round_save_result(
        self,
        *,
        save_generation: int,
        session_id: int | None,
        error: Exception | None,
        show_saved_status: bool,
        events: list[Dict[str, Any]],
        char_results: list[Any],
        practice_id: Optional[int],
        practice_token: Optional[int],
        round_number: int,
        summary: Any,
        history_row: Optional[dict[str, Any]] = None,
    ) -> None:
        app = self.app

        if error is not None or session_id is None:
            log_app_exception(
                "app.practice.round_save_failed",
                error or RuntimeError("Background save did not return a session id."),
                message="Finished practice round background save failed.",
                context={
                    "practice_id": practice_id,
                    "practice_token": practice_token,
                    "round_number": round_number,
                    "save_generation": save_generation,
                    "event_count": len(events),
                    "char_result_count": len(char_results),
                    "summary": summarize_score_summary(summary),
                },
            )
            if not self._active_round_or_countdown_running():
                app.status_controller.set_main_status(
                    app.i18n.t(
                        "practice.status.save_failed",
                        "Round save failed: {error}",
                        error=error,
                    ),
                    state="error",
                )
            return

        if practice_id is None:
            log_app_exception(
                "app.practice.round_save_missing_practice_id",
                RuntimeError("Background save completed without a practice id."),
                message="Finished practice round background save returned no practice id.",
                context={
                    "session_id": session_id,
                    "practice_token": practice_token,
                    "round_number": round_number,
                    "save_generation": save_generation,
                },
            )
            return

        if practice_token is not None:
            self._remember_practice_db_id_for_token(practice_token, int(practice_id))

        log_app_event(
            "app.practice.round_saved",
            message="Finished practice round background save completed.",
            context={
                "session_id": session_id,
                "practice_id": practice_id,
                "practice_token": practice_token,
                "round_number": round_number,
                "save_generation": save_generation,
                "event_count": len(events),
                "char_result_count": len(char_results),
                "summary": summarize_score_summary(summary),
            },
        )

        try:
            app.history_controller.increment_keying_event_summary_from_round(events, char_results)
        except Exception as exc:
            log_app_exception(
                "app.history.keying_summary_increment_failed",
                exc,
                level="warning",
                message="Keying event summary increment failed after saving a round.",
                context={"session_id": session_id},
            )

        if history_row is not None and bool(getattr(config, "HISTORY_TABLE_INCREMENTAL_AFTER_ROUND", True)):
            try:
                app.history_controller.update_recent_history_table_incremental(
                    history_row,
                    limit=int(getattr(config, "HISTORY_TABLE_RECENT_SESSIONS", 1000)),
                )
            except Exception as exc:
                log_app_exception(
                    "app.history.table_incremental_after_save_failed",
                    exc,
                    level="warning",
                    message="Saved round could not be inserted into the Recent rounds table immediately.",
                    context={"session_id": session_id},
                )

        if show_saved_status and not self._active_round_or_countdown_running():
            app.status_var.set(
                app.i18n.t(
                    "practice.status.saved_round",
                    "Saved round #{session_id}",
                    session_id=session_id,
                )
            )

        self._mark_after_round_analytics_pending(int(session_id))

    def _reschedule_pending_after_round_analytics(self, *, reason: str) -> None:
        """Keep a pending after-round analytics job pending while practice is active."""

        if not self._pending_after_round_snapshot_ids():
            return

        self._cancel_scheduled_after_round_analytics()
        pending_ids = self._pending_after_round_snapshot_ids()
        log_app_event(
            "app.practice.after_round_analytics_rescheduled",
            message="Pending after-round analytics was rescheduled.",
            context={
                "session_id": pending_ids[-1],
                "snapshot_session_ids": pending_ids,
                "snapshot_count": len(pending_ids),
                "reason": reason,
                "active_round_or_countdown": self._active_round_or_countdown_running(),
            },
        )
        self._schedule_pending_after_round_updates(active_reschedule=True)

    def _pending_after_round_snapshot_ids(self) -> list[int]:
        """Return pending snapshot session ids in chronological order."""

        ids = list(self.pending_after_round_snapshot_session_ids)

        if self.pending_after_round_updates_session_id is not None:
            ids.append(int(self.pending_after_round_updates_session_id))

        return self._normalize_snapshot_session_ids(ids, fallback=None)

    def _normalize_snapshot_session_ids(
        self,
        session_ids: Sequence[int] | None,
        *,
        fallback: int | None,
    ) -> list[int]:
        """Return unique positive session ids in chronological order."""

        normalized: list[int] = []
        seen: set[int] = set()

        raw_ids: list[Any] = list(session_ids or [])
        if fallback is not None:
            raw_ids.append(fallback)

        for raw_session_id in raw_ids:
            try:
                session_id = int(raw_session_id)
            except Exception:
                continue

            if session_id <= 0 or session_id in seen:
                continue

            seen.add(session_id)
            normalized.append(session_id)

        normalized.sort()
        return normalized

    def _mark_after_round_analytics_pending(self, session_id: int) -> None:
        """Queue a saved round for later per-round skill snapshot analytics."""

        pending_ids = self._pending_after_round_snapshot_ids()
        if int(session_id) not in pending_ids:
            pending_ids.append(int(session_id))

        pending_ids = self._normalize_snapshot_session_ids(pending_ids, fallback=None)
        self.pending_after_round_snapshot_session_ids = pending_ids
        self.pending_after_round_updates_session_id = pending_ids[-1] if pending_ids else None

        log_app_event(
            "app.practice.after_round_analytics_pending_marked",
            message="Saved round was marked for idle after-round analytics.",
            context={
                "session_id": int(session_id),
                "snapshot_session_ids": pending_ids,
                "snapshot_count": len(pending_ids),
            },
        )
        self._schedule_pending_after_round_updates()

    def _schedule_pending_after_round_updates(self, *, active_reschedule: bool = False) -> None:
        """Queue heavy after-round updates once, preserving every saved round id.

        The actual CPU-heavy work is delayed and only started while the UI is
        idle. Running the skill calculation immediately after a round can still
        starve Tk's event loop, because that calculation is Python CPU work even
        when it runs on a worker thread.

        Every saved session id stays in a pending list until analytics runs.
        When the worker finally starts, it writes one as-of skill snapshot for
        each pending round, while the visible UI panels are still updated only
        from the newest snapshot.
        """

        snapshot_ids = self._pending_after_round_snapshot_ids()

        if not snapshot_ids:
            self.pending_after_round_updates_session_id = None
            self.pending_after_round_snapshot_session_ids = []
            return

        session_id = snapshot_ids[-1]
        self.pending_after_round_updates_session_id = session_id
        self.pending_after_round_snapshot_session_ids = snapshot_ids

        self._cancel_scheduled_after_round_analytics()
        delay_ms = self._analytics_delay_ms(active_reschedule=active_reschedule)

        def run_if_idle() -> None:
            self._after_round_analytics_after_id = None
            latest_snapshot_ids = self._pending_after_round_snapshot_ids()

            if not latest_snapshot_ids:
                self.pending_after_round_updates_session_id = None
                self.pending_after_round_snapshot_session_ids = []
                return

            latest_session_id = latest_snapshot_ids[-1]

            if self._active_round_or_countdown_running():
                log_app_event(
                    "app.practice.after_round_analytics_postponed_active",
                    message="After-round analytics was postponed because a round or countdown is active.",
                    context={
                        "session_id": latest_session_id,
                        "snapshot_session_ids": latest_snapshot_ids,
                        "snapshot_count": len(latest_snapshot_ids),
                        "delay_ms": self._analytics_delay_ms(active_reschedule=True),
                    },
                )
                self._schedule_pending_after_round_updates(active_reschedule=True)
                return

            self.pending_after_round_snapshot_session_ids = []
            self.pending_after_round_updates_session_id = None
            self._request_after_round_analytics_async(
                int(latest_session_id),
                snapshot_session_ids=latest_snapshot_ids,
            )

        try:
            self._after_round_analytics_after_id = self.app.after(delay_ms, run_if_idle)
            log_app_event(
                "app.practice.after_round_analytics_scheduled",
                message="After-round analytics was scheduled for idle execution.",
                context={
                    "session_id": session_id,
                    "snapshot_session_ids": snapshot_ids,
                    "snapshot_count": len(snapshot_ids),
                    "delay_ms": delay_ms,
                    "active_reschedule": active_reschedule,
                },
            )
        except Exception:
            # If Tk scheduling fails during shutdown, fall back to immediate queueing
            # rather than silently losing the saved-round summaries.
            self.pending_after_round_snapshot_session_ids = []
            self.pending_after_round_updates_session_id = None
            self._request_after_round_analytics_async(
                int(session_id),
                snapshot_session_ids=snapshot_ids,
            )

    def clear_round_input(self) -> None:
        """Clear the current round input and telemetry while preserving the round target."""
        app = self.app

        if app.round.accepting_input:
            app.round.hid_text = ""
            app.round.telemetry_text = ""
            app.round.events.clear()

            if app.live_decoder is not None:
                app.live_decoder.reset(
                    target_text=app.round.target,
                    seed_unit_us=app.decoder_controller.adaptive_seed_unit_us(),
                )

            app.live_ui_dirty = False
            app.live_result_dirty = False
            app.last_live_ui_refresh_monotonic = 0.0
            app.last_live_score_refresh_monotonic = 0.0

            app.round.started_at = None
            app.round.host_start_time = None

        app.input_var.set("")
        app.decoder_controller.clear_telemetry_display()
        app.timer_var.set(self._reference_time_label())
        log_app_event(
            "app.practice.input_cleared",
            message="Current round input and telemetry were cleared.",
            context={
                "round_accepting_input": bool(app.round.accepting_input),
                "round_number": getattr(app.round, "round_number", 0),
            },
        )
        app.status_var.set(
            app.i18n.t("practice.status.input_cleared", "Input cleared.")
        )
        app.decoder_controller.clear_raw_telemetry()

        if app.round.host_start_time is not None:
            app.results_controller.reset_latest_result_values()
            self.evaluate_live()

        app.app_lifecycle_controller.focus_input(force=True)

    def _update_practice_buttons(self) -> None:
        """Update start and stop button states based on practice state."""
        app = self.app

        if not hasattr(app, "start_button") or not hasattr(app, "stop_button"):
            return

        running = app.practice_running or app.start_countdown_running
        app.start_button.configure(state=tk.DISABLED if running else tk.NORMAL)
        app.stop_button.configure(state=tk.NORMAL if running else tk.DISABLED)

    def _clear_visible_training_texts(self) -> None:
        """Clear visible target, input and telemetry fields before countdown."""
        app = self.app

        app.target_var.set("")
        app.decoder_controller.clear_telemetry_display()
        app.input_var.set("")
        app.round.hid_text = ""
        app.round.telemetry_text = ""
        app.decoder_controller.clear_raw_telemetry()

    def _begin_inter_round_countdown(self) -> None:
        """Start the visual countdown before the next round in the same practice."""
        app = self.app

        if not app.practice_running:
            return

        if app.current_round_number >= app.total_rounds:
            return

        self._cancel_inter_round_countdown(restore_state_text=False)

        self.inter_round_countdown_running = True
        log_app_event(
            "app.practice.inter_round_countdown_started",
            message="Inter-round countdown started.",
            context={
                "practice_id": self.current_practice_id,
                "current_round": app.current_round_number,
                "next_round": app.current_round_number + 1,
                "total_rounds": app.total_rounds,
            },
        )
        self.inter_round_countdown_generation += 1
        self.inter_round_countdown_started_at = time.monotonic()

        next_round = app.current_round_number + 1

        app.input_entry.configure(state=tk.DISABLED)

        app.round_state_var.set(
            app.i18n.t(
                "practice.round_state.next_round_countdown",
                "Round {next}/{total}: starts soon",
                next=next_round,
                total=app.total_rounds,
            )
        )

        app.status_var.set(
            app.i18n.t(
                "practice.status.next_round_countdown",
                "Next round starts soon.",
            )
        )

        self._show_start_countdown_bar()
        self._update_practice_buttons()
        self._update_inter_round_countdown_bar(self.inter_round_countdown_generation)


    def _cancel_inter_round_countdown(self, restore_state_text: bool = True) -> None:
        """Cancel the countdown between practice rounds."""
        app = self.app

        self.inter_round_countdown_generation += 1

        if self.inter_round_countdown_after_id is not None:
            try:
                app.after_cancel(self.inter_round_countdown_after_id)
            except Exception:
                pass

        self.inter_round_countdown_after_id = None
        self.inter_round_countdown_started_at = None
        self.inter_round_countdown_running = False

        if restore_state_text:
            self._hide_start_countdown_bar()


    def _update_inter_round_countdown_bar(self, generation: int) -> None:
        """Redraw and advance the countdown before the next practice round."""
        app = self.app

        if generation != self.inter_round_countdown_generation:
            return

        if not self.inter_round_countdown_running or not app.practice_running:
            return

        self.inter_round_countdown_started_at = (
            self.inter_round_countdown_started_at or time.monotonic()
        )

        now = time.monotonic()
        duration = max(0.1, float(self.inter_round_countdown_seconds))
        elapsed = max(0.0, now - self.inter_round_countdown_started_at)
        remaining = max(0.0, duration - elapsed)
        fraction = max(0.0, min(1.0, remaining / duration))

        self._draw_start_countdown_bar(fraction, remaining)

        if remaining <= 0:
            self._finish_inter_round_countdown(generation)
            return

        self.inter_round_countdown_after_id = app.after(
            50,
            lambda: self._update_inter_round_countdown_bar(generation),
        )


    def _finish_inter_round_countdown(self, generation: int) -> None:
        """Finish the inter-round countdown and start the next round."""
        app = self.app

        if generation != self.inter_round_countdown_generation:
            return

        if not self.inter_round_countdown_running:
            return

        self.inter_round_countdown_running = False
        self.inter_round_countdown_after_id = None
        self.inter_round_countdown_started_at = None

        self._hide_start_countdown_bar()

        if app.practice_running:
            self._start_next_round()

    def _begin_start_countdown(self) -> None:
        """Start the visual pre-practice countdown."""
        app = self.app

        if app.practice_running or app.start_countdown_running:
            return

        self._cancel_low_priority_history_render()
        self._cancel_pending_countdown_callback()
        app.start_trigger_timestamps.clear()
        app.start_countdown_running = True
        log_app_event(
            "app.practice.start_countdown_started",
            message="Practice start countdown started.",
            context={
                "trigger_count": len(app.start_trigger_timestamps),
                "duration_seconds": getattr(app, "start_countdown_duration_seconds", None),
            },
        )
        app.start_countdown_generation += 1
        app.start_countdown_started_at = time.monotonic()

        self._clear_visible_training_texts()
        app.status_controller.set_main_status(
            app.i18n.t(
                "practice.status.countdown_starting",
                "Practice starts soon.",
            ),
            state="normal",
        )
        self._update_practice_buttons()
        self._show_start_countdown_bar()
        app.app_lifecycle_controller.focus_input(force=True)
        self._update_start_countdown_bar(app.start_countdown_generation)

    def _cancel_pending_countdown_callback(self) -> None:
        """Cancel the scheduled countdown timer callback when it exists."""
        app = self.app

        if app.start_countdown_after_id is None:
            return

        try:
            app.after_cancel(app.start_countdown_after_id)
        except Exception:
            pass

        app.start_countdown_after_id = None

    def _update_start_countdown_bar(self, generation: Optional[int] = None) -> None:
        """Redraw and advance the countdown progress bar."""
        app = self.app

        generation = app.start_countdown_generation if generation is None else generation

        if generation != app.start_countdown_generation or not app.start_countdown_running:
            return

        app.start_countdown_started_at = app.start_countdown_started_at or time.monotonic()

        now = time.monotonic()
        duration = max(0.1, float(app.start_countdown_duration_seconds))
        elapsed = max(0.0, now - app.start_countdown_started_at)
        remaining = max(0.0, duration - elapsed)
        fraction = max(0.0, min(1.0, remaining / duration))

        self._draw_start_countdown_bar(fraction, remaining)

        if remaining <= 0:
            self._finish_start_countdown(generation)
            return

        app.start_countdown_after_id = app.after(
            50,
            lambda: self._update_start_countdown_bar(generation),
        )

    def _draw_start_countdown_bar(self, fraction: float, remaining_seconds: float) -> None:
        """Draw the countdown progress bar on the training panel canvas."""
        app = self.app

        if not hasattr(app, "start_countdown_canvas"):
            return

        canvas = app.start_countdown_canvas
        height = int(getattr(app, "start_countdown_bar_height", 18))
        canvas.update_idletasks()

        width = int(canvas.winfo_width())

        if width <= 1:
            width = int(canvas.master.winfo_width())

        if width <= 1:
            width = 450

        canvas.configure(height=height)
        canvas.delete("all")

        fill_width = max(0, min(width, int(width * fraction)))
        number_text = str(max(1, int(remaining_seconds + 0.999)))

        canvas.create_rectangle(0, 0, width, height, fill="#eeeeee", outline="#cccccc")

        if fill_width > 0:
            canvas.create_rectangle(
                0,
                0,
                fill_width,
                height,
                fill="#178a2f",
                outline="#178a2f",
            )

        canvas.create_text(
            width // 2,
            height // 2,
            text=number_text,
            fill="#000000",
            font=("Segoe UI", 12, "bold"),
        )

    def _show_start_countdown_bar(self) -> None:
        """Replace the round state label with the countdown bar."""
        app = self.app

        if hasattr(app, "round_state_label"):
            app.round_state_label.pack_forget()

        if hasattr(app, "start_countdown_canvas"):
            app.start_countdown_canvas.pack(fill=tk.X, expand=True, anchor=tk.W)

    def _hide_start_countdown_bar(self) -> None:
        """Hide the countdown bar and restore the round state label."""
        app = self.app

        if hasattr(app, "start_countdown_canvas"):
            app.start_countdown_canvas.pack_forget()
            app.start_countdown_canvas.delete("all")

        if hasattr(app, "round_state_label"):
            app.round_state_label.pack(anchor=tk.W)

    def _finish_start_countdown(self, generation: Optional[int] = None) -> None:
        """Complete the countdown and start the actual practice series."""
        app = self.app

        if generation is not None and generation != app.start_countdown_generation:
            return

        if not app.start_countdown_running:
            return

        app.start_countdown_running = False
        log_app_event(
            "app.practice.start_countdown_completed",
            message="Practice start countdown completed.",
            context={"generation": generation},
        )
        app.start_countdown_after_id = None
        app.start_countdown_started_at = None

        self._hide_start_countdown_bar()
        self._update_practice_buttons()
        self.start_practice()

    def _cancel_start_countdown(self, restore_state_text: bool = True) -> None:
        """Cancel countdown state and restore the normal training UI."""
        app = self.app

        app.start_countdown_generation += 1
        self._cancel_pending_countdown_callback()
        app.start_countdown_running = False
        app.start_countdown_started_at = None
        app.start_trigger_timestamps.clear()
        self._hide_start_countdown_bar()

        if restore_state_text and not app.practice_running:
            app.round_state_var.set(
                app.i18n.t("runtime.round_state_inactive", "Practice: not running")
            )

        self._update_practice_buttons()
        app.app_lifecycle_controller.focus_input(force=True)

    def _completion_idle_units(self, event: Dict[str, Any]) -> float:
        """Return the symbol completion idle threshold for the event source."""
        source = event.get("src")

        if source == "iambic":
            return float(getattr(config, "DECODER_IAMBIC_COMPLETION_IDLE_UNITS", 4.8))

        if source == "straight":
            return float(getattr(config, "DECODER_STRAIGHT_COMPLETION_IDLE_UNITS", 7.0))

        return 4.8

    def _auto_finish_idle_required_us(self, unit_us: float) -> int:
        """Calculate the idle timeout required for automatic round finish."""
        app = self.app
        helpers = app.ui_helpers_controller

        idle_units = helpers.safe_int_var(
            app.auto_finish_idle_units_var,
            default=int(getattr(config, "DECODER_AUTO_FINISH_IDLE_UNITS", 14.0)),
            minimum=3,
            maximum=100,
        )
        min_seconds = helpers.safe_int_var(
            app.auto_finish_min_seconds_var,
            default=int(getattr(config, "DECODER_AUTO_FINISH_MIN_SECONDS", 2.0)),
            minimum=1,
            maximum=30,
        )

        return int(
            max(
                float(unit_us) * float(idle_units),
                float(min_seconds) * 1_000_000.0,
            )
        )

    def _maybe_finish_idle_timeout(self) -> None:
        """Finish the current telemetry round after a long enough idle pause."""
        app = self.app

        try:
            enabled = bool(app.auto_finish_on_idle_var.get())
        except Exception:
            enabled = bool(getattr(config, "DECODER_AUTO_FINISH_ON_IDLE", True))

        if not enabled or not app.round.accepting_input or app.round.finished:
            return

        if self._has_open_v1_key_event():
            return

        if not app.use_telemetry_as_truth_var.get() or not app.round.events:
            return

        last_event = app.decoder_controller.last_tone_event()
        current_time_us = app.decoder_controller.adaptive_current_device_time_us()

        if last_event is None or current_time_us is None:
            return

        decoded_candidate = app.decoder_controller.decode_tone_events(
            app.round.events,
            current_time_us=current_time_us,
            flush_final=False,
            seed_unit_us=app.decoder_controller.adaptive_seed_unit_us(),
        )

        last_t1 = int(last_event["t1"])
        source = str(last_event.get("src", "straight"))

        try:
            gap_unit_us = decoded_candidate.timing_for_source(source).gap_unit_us
        except Exception:
            gap_unit_us = decoded_candidate.unit_us or app.decoder_controller.adaptive_seed_unit_us()

        actual_idle_us = max(0, int(current_time_us) - last_t1)

        if actual_idle_us >= self._auto_finish_idle_required_us(gap_unit_us):
            log_app_event(
                "app.practice.auto_finish_triggered",
                message="Automatic idle finish triggered for telemetry round.",
                context={
                    "round_number": app.round.round_number,
                    "source": source,
                    "actual_idle_us": actual_idle_us,
                    "gap_unit_us": gap_unit_us,
                    "event_count": len(app.round.events),
                },
            )
            self.finish_round(FINISH_REASON_LONG_PAUSE, auto_continue=True)

    def _start_round_clock_from_host_input(self) -> None:
        """Start the round clock when text input begins."""
        app = self.app

        if app.round.host_start_time is not None:
            return

        app.results_controller.reset_latest_result_values_when_round_starts()
        app.round.started_at = datetime.now()
        app.round.host_start_time = time.monotonic()
        log_app_event(
            "app.practice.round_clock_started",
            message="Round clock started from HID input.",
            context={
                "round_number": app.current_round_number,
                "source": "hid",
                "target_length": len(app.round.target),
            },
        )
        app.round_state_var.set(
            app.i18n.t(
                "practice.round_state.running",
                "Round {current}/{total}: running",
                current=app.current_round_number,
                total=app.total_rounds,
            )
        )
        app.status_var.set(
            app.i18n.t("practice.status.clock_running", "Clock running.")
        )

    def _start_round_clock_from_tone_event(self, event: Dict[str, Any]) -> None:
        """Start the round clock from the first accepted tone event."""
        app = self.app

        if app.round.host_start_time is not None:
            return

        app.results_controller.reset_latest_result_values_when_round_starts()

        host_received = event.get("_host_received_time")
        app.round.started_at = (
            datetime.fromtimestamp(float(host_received))
            if isinstance(host_received, (int, float))
            else datetime.now()
        )
        app.round.host_start_time = time.monotonic()
        log_app_event(
            "app.practice.round_clock_started",
            message="Round clock started from tone event.",
            context={
                "round_number": app.current_round_number,
                "source": str(event.get("src", "")),
                "target_length": len(app.round.target),
            },
        )
        app.round_state_var.set(
            app.i18n.t(
                "practice.round_state.running",
                "Round {current}/{total}: running",
                current=app.current_round_number,
                total=app.total_rounds,
            )
        )
        app.status_var.set(
            app.i18n.t("practice.status.clock_running", "Clock running.")
        )

    def _mark_live_ui_dirty(self) -> None:
        """Mark live telemetry and live result panels as needing a refresh."""
        app = self.app
        app.live_ui_dirty = True
        app.live_result_dirty = True

    def _live_refresh_due(self, *, last_attr: str, interval_ms: int, now: float) -> bool:
        """Return True when a throttled live refresh interval has elapsed."""
        app = self.app

        try:
            last_refresh = float(getattr(app, last_attr, 0.0) or 0.0)
        except Exception:
            last_refresh = 0.0

        interval_seconds = max(0.0, float(interval_ms) / 1000.0)
        return now - last_refresh >= interval_seconds

    def _live_decoder_has_pending_symbol(self) -> bool:
        """Return True while the live decoder still has an unflushed symbol."""
        app = self.app

        try:
            live_decoder = getattr(app, "live_decoder", None)
            if live_decoder is None:
                return False
            return bool(live_decoder.current_state().pending_symbol)
        except Exception:
            return False

    def _has_open_v1_key_event(self) -> bool:
        """Return True while a V1 key down event has not yet received its up event."""
        try:
            active = getattr(self.app, "active_v1_key_events", None)
            return bool(active)
        except Exception:
            return False

    def _refresh_live_ui(self, *, force: bool = False) -> None:
        """Run throttled live telemetry redraw and live score refreshes."""
        app = self.app

        if not app.round.accepting_input or app.round.finished:
            return

        now = time.monotonic()

        telemetry_interval_ms = int(
            getattr(config, "LIVE_TELEMETRY_REFRESH_MS", config.TIMER_TICK_MS)
        )
        telemetry_due = self._live_refresh_due(
            last_attr="last_live_ui_refresh_monotonic",
            interval_ms=telemetry_interval_ms,
            now=now,
        )

        telemetry_dirty = bool(getattr(app, "live_ui_dirty", False))
        telemetry_pending = self._live_decoder_has_pending_symbol()
        telemetry_key_open = self._has_open_v1_key_event()

        if force or ((telemetry_dirty or telemetry_pending or telemetry_key_open) and telemetry_due):
            decoded = self._update_adaptive_decoded_text(flush_final=False)
            app.decoder_controller.draw_raw_telemetry()
            app.live_ui_dirty = bool(getattr(decoded, "pending_symbol", "")) or self._has_open_v1_key_event()
            app.last_live_ui_refresh_monotonic = now
            app.app_lifecycle_controller.focus_input()

        result_interval_ms = int(getattr(config, "LIVE_RESULT_REFRESH_MS", 300))
        result_due = self._live_refresh_due(
            last_attr="last_live_score_refresh_monotonic",
            interval_ms=result_interval_ms,
            now=now,
        )

        if force or (bool(getattr(app, "live_result_dirty", False)) and result_due):
            self.evaluate_live()
            app.live_result_dirty = False
            app.last_live_score_refresh_monotonic = now

    def _live_elapsed_us(self) -> Optional[int]:
        """Return the current round elapsed time in microseconds."""
        app = self.app

        if app.round.host_start_time is None:
            return None

        return max(0, int((time.monotonic() - app.round.host_start_time) * 1_000_000))

    def _reference_time_label(self) -> str:
        """Return the static reference time label for the current target."""
        app = self.app

        standard_time_us = estimate_paris_time_us(app.round.target, app.settings.target_wpm)

        return app.i18n.t(
            "practice.time.placeholder_with_reference",
            "Time: - | Reference time {reference}",
            reference=app.results_controller.format_seconds_label(standard_time_us),
        )

    def _tick_timer(self) -> None:
        """Periodic timer tick for live round timing."""
        app = self.app

        if app.round.accepting_input and not app.round.finished:
            self._update_live_round_timer()

        app.after(config.TIMER_TICK_MS, self.tick_timer)

    def _update_live_round_timer(self) -> None:
        """Update live timer, telemetry and automatic finish checks."""
        app = self.app

        self._refresh_live_ui(force=False)

        elapsed_us = self._live_elapsed_us()

        if elapsed_us is None:
            app.timer_var.set(self._reference_time_label())
        else:
            app.timer_var.set(self._live_time_label(elapsed_us))
            self._maybe_finish_completed()

            if not app.round.finished:
                self._maybe_finish_idle_timeout()

    def _live_time_label(self, elapsed_us: int) -> str:
        """Build the live elapsed-time label for the active round."""
        app = self.app

        elapsed_text = app.results_controller.format_seconds_label(elapsed_us)
        standard_us = estimate_paris_time_us(app.round.target, app.settings.target_wpm)

        if standard_us is None:
            return app.i18n.t(
                "practice.time.elapsed",
                "Time: {elapsed}",
                elapsed=elapsed_text,
            )

        return app.i18n.t(
            "practice.time.elapsed_with_reference",
            "Time: {elapsed} | Reference time {reference}",
            elapsed=elapsed_text,
            reference=app.results_controller.format_seconds_label(standard_us),
        )

    def _maybe_finish_completed(self) -> None:
        """Finish the round when the entered or decoded text reaches target length."""
        app = self.app

        if not app.round.accepting_input or app.round.finished:
            return

        if self._has_open_v1_key_event():
            return

        target_score_no_spaces = score_text(app.round.target, keep_spaces=False)

        if not target_score_no_spaces:
            return

        entered, source = app.results_controller.selected_source_text()
        target_len = len(target_score_no_spaces)

        if source != SOURCE_ADAPTIVE_TELEMETRY:
            if len(score_text(entered, keep_spaces=False)) >= target_len:
                self.finish_round(FINISH_REASON_COMPLETED, auto_continue=True)
            return

        self._maybe_finish_completed_from_adaptive_telemetry(target_len)

    def _maybe_finish_completed_from_adaptive_telemetry(self, target_len: int) -> None:
        """Finish adaptive telemetry immediately only when the final decoded text matches the target."""
        app = self.app

        current_time_us = app.decoder_controller.adaptive_current_device_time_us()
        last_event = app.decoder_controller.last_tone_event()

        if current_time_us is None or last_event is None:
            return

        decoded_live = app.decoder_controller.decode_tone_events(
            app.round.events,
            current_time_us=current_time_us,
            flush_final=False,
            seed_unit_us=app.decoder_controller.adaptive_seed_unit_us(),
        )

        source = str(last_event.get("src", "straight"))

        try:
            gap_unit_us = decoded_live.timing_for_source(source).gap_unit_us
        except Exception:
            gap_unit_us = decoded_live.unit_us or app.decoder_controller.adaptive_seed_unit_us()

        if not self._last_symbol_has_completion_idle(
            last_event,
            gap_unit_us,
            current_time_us,
        ):
            return

        decoded_final = app.decoder_controller.decode_tone_events(
            app.round.events,
            current_time_us=current_time_us,
            flush_final=True,
            seed_unit_us=app.decoder_controller.adaptive_seed_unit_us(),
        )
        candidate_text = decoded_final.text.upper()

        target_plain = score_text(app.round.target, keep_spaces=False)
        candidate_plain = score_text(candidate_text, keep_spaces=False)

        # Do not finish merely because the decoded text became long enough.
        # If the decoder over-splits gaps, length can be reached far too early.
        # Exact completion can finish immediately. Otherwise the normal idle timeout
        # will finish the round after the user stops sending.
        if candidate_plain == target_plain:
            app.decoder_controller.update_telemetry_display_from_decoded(decoded_final)
            self.finish_round(FINISH_REASON_COMPLETED, auto_continue=True)

    def _last_symbol_has_completion_idle(
        self,
        last_event: Dict[str, Any],
        fallback_gap_unit_us: float,
        current_time_us: int,
    ) -> bool:
        """Return True when the last decoded symbol has enough following idle time."""
        app = self.app

        last_t1 = int(last_event["t1"])
        gap_unit_us = max(20_000.0, float(fallback_gap_unit_us))
        actual_idle_us = max(0, int(current_time_us) - last_t1)

        gap_tolerance_units = float(getattr(config, "DECODER_GAP_TOLERANCE_UNITS", 0.15))

        required_idle_us = int(
            gap_unit_us
            * max(0.0, self._completion_idle_units(last_event) - gap_tolerance_units)
        )

        return actual_idle_us >= required_idle_us

    def _update_adaptive_decoded_text(self, flush_final: bool = False) -> Any:
        """Decode tone telemetry, update the visible text and return the decoded state."""
        app = self.app

        decoded = app.decoder_controller.decode_tone_events(
            app.round.events,
            current_time_us=app.decoder_controller.adaptive_current_device_time_us(),
            flush_final=flush_final,
            seed_unit_us=app.decoder_controller.adaptive_seed_unit_us(),
        )
        app.decoder_controller.update_telemetry_display_from_decoded(decoded)
        return decoded

    def evaluate_live(self) -> None:
        """Score the current live round and update latest result values."""
        app = self.app

        if not app.round.target:
            return

        entered, source = app.results_controller.selected_source_text()

        summary, results = score_round(
            app.round.target,
            entered,
            source,
            app.round.events,
            app.settings,
            app.round.finish_reason or FINISH_REASON_IN_PROGRESS,
            count_missing=app.round.finished,
            decoder_settings=app.decoder_controller.decoder_settings_from_ui(),
            seed_unit_us=app.decoder_controller.adaptive_seed_unit_us(),
        )

        app.last_summary = summary
        app.last_char_results = results
        app.results_controller.update_latest_result_values(summary)