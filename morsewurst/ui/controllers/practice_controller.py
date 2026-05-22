# ============================================================
# morsewurst/ui/controllers/practice_controller.py
# ============================================================

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

import tkinter as tk

import morsewurst.config as config
from morsewurst.core.challenge import (
    generate_challenge,
    generate_wxmor_challenge,
    score_text,
)
from morsewurst.core.scoring import estimate_paris_time_us, score_round
from morsewurst.core.skill_rating import calculate_skill_rating
from morsewurst.models import RoundState
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


class PracticeController:
    """Owns practice series lifecycle, round completion and practice timers."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

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

    def start_practice(self) -> None:
        """Start a full practice series from the current UI settings."""
        app = self.app

        if app.start_countdown_running:
            self._cancel_start_countdown(restore_state_text=False)

        app.serial_controller.request_auto_connect_scan()
        app.settings = app.challenge_settings_controller.settings_from_ui()
        app.decoder_controller.refresh_timing_profiles()
        app.practice_running = True
        app.current_round_number = 0
        app.total_rounds = app.settings.practice_rounds
        app.practice_summaries = []

        self._update_practice_buttons()
        app.results_controller.update_practice_series_summary()
        app.status_controller.set_main_status(
            app.i18n.t(
                "practice.status.starting",
                "Practice starts. Total rounds: {total_rounds}.",
                total_rounds=app.total_rounds,
            ),
            state="normal",
        )
        self._start_next_round()

    def stop_practice(self) -> None:
        """Stop the current practice series or cancel a pending countdown."""
        app = self.app

        if app.start_countdown_running:
            self._cancel_start_countdown(restore_state_text=True)
            app.status_controller.set_main_status(
                app.i18n.t("practice.status.start_cancelled", "Start cancelled."),
                state="normal",
            )
            return

        app.practice_running = False

        if app.round.active and not app.round.finished:
            self._discard_current_round(FINISH_REASON_USER_STOPPED)

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
        target = self._generate_round_target()

        app.round = RoundState(
            target=target,
            active=True,
            accepting_input=True,
            finished=False,
            round_number=app.current_round_number,
            total_rounds=app.total_rounds,
        )
        app.live_decoder = app.decoder_controller.new_live_decoder(target)
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
            return generate_wxmor_challenge(
                profile=app.wxmor_controller.profile(),
            )

        problem_chars = app.db.problem_chars_for_practice(
            getattr(config, "DEFAULT_PROBLEM_CHAR_CANDIDATE_LIMIT", 50),
            helpers.safe_int_var(
                app.problem_recent_rounds_var,
                default=config.DEFAULT_PROBLEM_RECENT_ROUNDS,
                minimum=1,
                maximum=100000,
            ),
        )

        return generate_challenge(app.settings, problem_chars)

    def _finish_practice_series(self) -> None:
        """Mark the practice series as finished without starting another round."""
        app = self.app

        app.practice_running = False
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

    def finish_round(self, reason: str, auto_continue: bool = True) -> None:
        """Finalize the current round and schedule automatic saving."""
        app = self.app

        if not app.round.target or app.round.finished:
            return

        self._mark_round_finished(reason)
        self._finalize_round_decoding_and_score()

        if app.last_summary is not None:
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

            app.after(
                50,
                lambda: self._save_finished_round(auto_continue=auto_continue),
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

    def _advance_after_finished_round(self) -> None:
        """Continue to the next round or finish the whole practice series."""
        app = self.app

        if app.current_round_number < app.total_rounds:
            app.after(1200, self._start_next_round)
            return

        app.practice_running = False
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

    def _save_finished_round(self, *, auto_continue: bool = True) -> None:
        """Persist the finished round and schedule slower after-save updates."""
        app = self.app

        if app.last_summary is None:
            if auto_continue and app.practice_running:
                self._advance_after_finished_round()
            return

        app.round.started_at = app.round.started_at or datetime.now()

        session_id = app.db.save_session(
            app.round.started_at,
            app.last_summary,
            app.settings,
            app.round.events,
            app.last_char_results,
        )

        app.debug_controller.write_round_snapshot_if_enabled()
        app.decoder_controller.refresh_timing_profiles()

        app.status_var.set(
            app.i18n.t(
                "practice.status.saved_round",
                "Saved round #{session_id}",
                session_id=session_id,
            )
        )

        if auto_continue and app.practice_running:
            self._advance_after_finished_round()

        app.after(
            150,
            lambda session_id=session_id: self._deferred_after_round_updates(session_id),
        )

    def _deferred_after_round_updates(self, session_id: int) -> None:
        """Update skill, history, problem tables and summaries after saving."""
        app = self.app
        helpers = app.ui_helpers_controller
        rating = None

        try:
            recent_rounds = helpers.safe_int_var(
                app.skill_recent_rounds_var,
                default=getattr(config, "DEFAULT_SKILL_RATING_RECENT_ROUNDS", 1000),
                minimum=1,
                maximum=100000,
            )

            rating = calculate_skill_rating(
                app.db,
                recent_rounds=recent_rounds,
            )

            app.db.save_skill_rating_snapshot(session_id, rating)

        except Exception as exc:
            app.status_var.set(
                app.i18n.t(
                    "practice.status.saved_round_skill_failed",
                    "Saved round #{session_id}, but saving the skill rating failed: {error}",
                    session_id=session_id,
                    error=exc,
                )
            )

        try:
            app.history_controller.load_history_table()
            app.history_controller.load_problem_table()
            app.history_controller.update_stats_summary()

            if rating is not None:
                app.history_controller.update_skill_rating_summary(cached_rating=rating)

            if not bool(getattr(app, "practice_running", False)):
                app.history_controller.update_target_wpm_suggestion_indicator()
            app.history_controller.refresh_stats_window_if_open()

        except Exception as exc:
            app.status_var.set(
                app.i18n.t(
                    "practice.status.saved_round_summary_failed",
                    "Saved round #{session_id}, but updating summaries failed: {error}",
                    session_id=session_id,
                    error=exc,
                )
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

            app.round.started_at = None
            app.round.host_start_time = None

        app.input_var.set("")
        app.decoder_controller.clear_telemetry_display()
        app.timer_var.set(self._reference_time_label())
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

    def _begin_start_countdown(self) -> None:
        """Start the visual pre-practice countdown."""
        app = self.app

        if app.practice_running or app.start_countdown_running:
            return

        self._cancel_pending_countdown_callback()
        app.start_trigger_timestamps.clear()
        app.start_countdown_running = True
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
            self.finish_round(FINISH_REASON_LONG_PAUSE, auto_continue=True)

    def _start_round_clock_from_host_input(self) -> None:
        """Start the round clock when text input begins."""
        app = self.app

        if app.round.host_start_time is not None:
            return

        app.results_controller.reset_latest_result_values_when_round_starts()
        app.round.started_at = datetime.now()
        app.round.host_start_time = time.monotonic()
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

        self._update_adaptive_decoded_text(flush_final=False)
        app.decoder_controller.draw_raw_telemetry()

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

    def _update_adaptive_decoded_text(self, flush_final: bool = False) -> None:
        """Decode tone telemetry and update the visible adaptive telemetry text."""
        app = self.app

        decoded = app.decoder_controller.decode_tone_events(
            app.round.events,
            current_time_us=app.decoder_controller.adaptive_current_device_time_us(),
            flush_final=flush_final,
            seed_unit_us=app.decoder_controller.adaptive_seed_unit_us(),
        )
        app.decoder_controller.update_telemetry_display_from_decoded(decoded)

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