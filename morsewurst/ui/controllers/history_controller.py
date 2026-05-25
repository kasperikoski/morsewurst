# ============================================================
# morsewurst/ui/controllers/history_controller.py
# ============================================================

from __future__ import annotations

from datetime import datetime
import threading
from typing import TYPE_CHECKING, Any, Optional

import tkinter as tk

import morsewurst.config as config
from morsewurst.core.progression import title_key_for_level
from morsewurst.core.skill_rating import calculate_skill_rating
from morsewurst.models import ScoreSummary
from morsewurst.ui.controllers.results_controller import SOURCE_ADAPTIVE_TELEMETRY

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class HistoryController:
    """Owns history tables, saved-round viewing, problem table and skill summaries."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def load_tables(self, *, skill_rating: Optional[Any] = None) -> None:
        self.load_history_table()
        self.load_problem_table()
        self.update_stats_summary()
        self.update_skill_rating_summary(cached_rating=skill_rating)
        self.update_target_wpm_suggestion_indicator()
        self.refresh_stats_window_if_open()

    def load_keying_event_summary_for_startup(self) -> None:
        """Load keying event totals synchronously during the startup screen.

        Startup runs before Tk's mainloop is active. The normal background
        refresher schedules its result back with after(), which is reliable
        after startup but can leave the startup-time panel stuck in the
        loading state. During the splash screen we do the count directly so
        the values are ready before the main window is shown.
        """

        app = self.app

        app.keying_event_summary_loading = True
        self.set_keying_event_summary_loading()

        try:
            summary = app.db.keying_event_summary()
        except Exception as error:
            app.keying_event_summary_loaded = False
            app.general_straight_presses_var.set("-")
            app.general_iambic_elements_var.set("-")
            app.general_tone_total_var.set("-")

            try:
                app.status_controller.set_main_status(
                    f"Keying statistics startup load failed: {error}",
                    state="warning",
                )
            except Exception:
                pass
        else:
            self.apply_keying_event_summary(summary)
        finally:
            app.keying_event_summary_loading = False

    def schedule_initial_keying_event_summary(self) -> None:
        """Schedule the first keying event summary refresh after startup.

        The first full count can scan a large events table. Scheduling it after
        the UI has entered the Tk event loop avoids leaving the panel stuck in
        the loading state during application startup.
        """

        app = self.app

        if getattr(app, "keying_event_summary_loaded", False):
            return

        if getattr(app, "keying_event_summary_loading", False):
            return

        if getattr(app, "keying_event_summary_startup_scheduled", False):
            return

        app.keying_event_summary_startup_scheduled = True

        def start_refresh() -> None:
            app.keying_event_summary_startup_scheduled = False

            if getattr(app, "keying_event_summary_loaded", False):
                return

            if getattr(app, "keying_event_summary_loading", False):
                return

            self.update_keying_event_summary_async()

        try:
            app.after(750, start_refresh)
        except Exception:
            app.keying_event_summary_startup_scheduled = False


    def update_keying_event_summary_async(self, *, force: bool = False) -> None:
        """Load keying event totals in a background thread.

        The query can eventually scan a large events table, so it should not block
        the Tk UI thread. A separate SQLite connection is used inside the worker.
        """

        app = self.app

        if getattr(app, "keying_event_summary_loading", False) and not force:
            return

        app.keying_event_summary_loading = True
        self.set_keying_event_summary_loading()

        def worker() -> None:
            summary: dict[str, int] | None = None
            error: Exception | None = None

            try:
                summary = app.db.keying_event_summary_from_file()
            except Exception as exc:
                error = exc

            def finish() -> None:
                app.keying_event_summary_loading = False

                if summary is None:
                    app.keying_event_summary_loaded = False
                    app.general_straight_presses_var.set("-")
                    app.general_iambic_elements_var.set("-")
                    app.general_tone_total_var.set("-")

                    if error is not None:
                        app.status_controller.set_main_status(
                            f"Keying statistics refresh failed: {error}",
                            state="warning",
                        )
                    return

                self.apply_keying_event_summary(summary)

            try:
                app.after(0, finish)
            except Exception:
                app.keying_event_summary_loading = False

        threading.Thread(target=worker, daemon=True).start()


    def set_keying_event_summary_loading(self) -> None:
        """Show a lightweight loading state for keying event totals."""

        app = self.app
        loading_text = app.i18n.t("general_info.calculating", "calculating...")

        app.general_straight_presses_var.set("-")
        app.general_iambic_elements_var.set("-")
        app.general_tone_total_var.set(loading_text)
        app.general_straight_chars_var.set("-")
        app.general_iambic_chars_var.set("-")


    def apply_keying_event_summary(self, summary: dict[str, int]) -> None:
        """Store and display keying event totals."""

        app = self.app

        clean_summary = {
            "straight_presses": max(0, int(summary.get("straight_presses", 0) or 0)),
            "iambic_elements": max(0, int(summary.get("iambic_elements", 0) or 0)),
            "tone_total": max(0, int(summary.get("tone_total", 0) or 0)),
            "straight_chars": max(0, int(summary.get("straight_chars", 0) or 0)),
            "iambic_chars": max(0, int(summary.get("iambic_chars", 0) or 0)),
            "produced_chars_total": max(0, int(summary.get("produced_chars_total", 0) or 0)),
        }

        app.keying_event_summary = clean_summary
        app.keying_event_summary_loaded = True

        self.update_keying_event_summary_display()


    def increment_keying_event_summary_from_round(
        self,
        events: list[dict[str, Any]],
        char_results: list[Any],
    ) -> None:
        """Increment displayed keying and produced-character totals from a saved round."""

        app = self.app

        if not getattr(app, "keying_event_summary_loaded", False):
            return

        summary = dict(getattr(app, "keying_event_summary", {}) or {})

        straight_presses = int(summary.get("straight_presses", 0) or 0)
        iambic_elements = int(summary.get("iambic_elements", 0) or 0)
        tone_total = int(summary.get("tone_total", 0) or 0)
        straight_chars = int(summary.get("straight_chars", 0) or 0)
        iambic_chars = int(summary.get("iambic_chars", 0) or 0)
        produced_chars_total = int(summary.get("produced_chars_total", 0) or 0)

        for event in events:
            if event.get("type") != "tone":
                continue

            tone_total += 1
            source = str(event.get("src", "")).strip().lower()

            if source == "straight":
                straight_presses += 1
            elif source == "iambic":
                iambic_elements += 1

        for char_result in char_results:
            entered_char = self.char_result_value(char_result, "entered_char")
            result = str(self.char_result_value(char_result, "result", "") or "").strip().lower()
            source = str(self.char_result_value(char_result, "source", "") or "").strip().lower()

            if not self.is_countable_produced_character(entered_char, result):
                continue

            produced_chars_total += 1

            if source == "straight":
                straight_chars += 1
            elif source == "iambic":
                iambic_chars += 1

        self.apply_keying_event_summary(
            {
                "straight_presses": straight_presses,
                "iambic_elements": iambic_elements,
                "tone_total": tone_total,
                "straight_chars": straight_chars,
                "iambic_chars": iambic_chars,
                "produced_chars_total": produced_chars_total,
            }
        )


    def char_result_value(self, char_result: Any, field: str, default: Any = None) -> Any:
        """Return a value from either a CharacterResult object or a dict."""

        if isinstance(char_result, dict):
            return char_result.get(field, default)

        return getattr(char_result, field, default)


    def is_countable_produced_character(
        self,
        entered_char: Any,
        result: str,
    ) -> bool:
        """Return whether a char_result row should count as a produced character."""

        if result not in {"correct", "substitution", "insertion"}:
            return False

        char = "" if entered_char is None else str(entered_char)

        if char == "":
            return False

        if char == " ":
            return False

        if char == "�":
            return False

        return True


    def update_keying_event_summary_display(self) -> None:
        """Update keying event total variables from the cached summary."""

        app = self.app
        summary = getattr(app, "keying_event_summary", {}) or {}

        app.general_straight_presses_var.set(
            self.format_keying_count(summary.get("straight_presses", 0))
        )
        app.general_iambic_elements_var.set(
            self.format_keying_count(summary.get("iambic_elements", 0))
        )
        app.general_tone_total_var.set(
            self.format_keying_count(summary.get("tone_total", 0))
        )
        app.general_straight_chars_var.set(
            self.format_keying_count(summary.get("straight_chars", 0))
        )
        app.general_iambic_chars_var.set(
            self.format_keying_count(summary.get("iambic_chars", 0))
        )


    def format_keying_count(self, value: Any) -> str:
        """Format a keying event count for the compact general info panel."""

        try:
            count = max(0, int(value))
        except Exception:
            return "-"

        text = f"{count:,}"

        try:
            language = str(self.app.i18n.language)
        except Exception:
            language = "en"

        if language == "fi":
            text = text.replace(",", " ")

        return f"~ {text}"

    def load_history_table(self) -> None:
        app = self.app

        for row_id in app.history_tree.get_children():
            app.history_tree.delete(row_id)

        for row in app.db.recent_sessions(1000):
            app.history_tree.insert("", tk.END, values=self.history_row_values(row))

    def history_row_values(self, row: Any) -> tuple[Any, ...]:
        elapsed_us = self.row_get(row, "elapsed_us")
        elapsed = "-" if elapsed_us is None else f"{float(elapsed_us) / 1_000_000:.1f}s"
        accuracy = self.row_get(row, "accuracy", 0.0)
        cleanliness = self.row_get(row, "cleanliness")
        overall = self.row_get(row, "overall_score")
        wpm = self.row_get(row, "gross_wpm")

        return (
            self.row_get(row, "id", "-"),
            self.format_datetime(str(self.row_get(row, "finished_at", ""))),
            "-" if accuracy is None else f"{float(accuracy):.1f} %",
            "-" if cleanliness is None else f"{float(cleanliness):.1f} %",
            "-" if overall is None else f"{float(overall):.1f}",
            self.row_get(row, "error_count", "-"),
            "-" if wpm is None else f"{float(wpm):.1f}",
            elapsed,
            self.row_get(row, "entered", ""),
            self.row_get(row, "target", ""),
        )

    def open_history_round_from_selection(self, event: tk.Event) -> None:
        app = self.app
        widget = event.widget

        if widget is not getattr(app, "history_tree", None):
            return

        if not widget.selection():
            return

        app.after_idle(self.open_selected_history_round)

    def open_selected_history_round(self) -> None:
        app = self.app

        if app.round.accepting_input and not app.round.finished:
            app.status_controller.set_main_status(
                app.i18n.t(
                    "history.status.active_round_blocked",
                    "History round cannot be opened during an active round.",
                ),
                state="warning",
            )
            return

        session_id = self.selected_history_session_id()

        if session_id is None:
            return

        if app.viewing_history_session_id == session_id:
            return

        details = app.db.session_details(session_id)

        if details is None:
            app.status_controller.set_main_status(
                app.i18n.t(
                    "history.status.round_not_found",
                    "Round #{session_id} was not found.",
                    session_id=session_id,
                ),
                state="error",
            )
            self.load_tables()
            return

        self.show_history_round_in_main_view(details)

    def selected_history_session_id(self) -> Optional[int]:
        app = self.app

        if not hasattr(app, "history_tree"):
            return None

        selection = app.history_tree.selection()

        if not selection:
            return None

        try:
            values = app.history_tree.item(selection[0], "values")
        except Exception:
            return None

        if not values:
            return None

        try:
            return int(values[0])
        except Exception:
            return None

    def show_history_round_in_main_view(self, details: dict[str, Any]) -> None:
        app = self.app
        summary = self.summary_from_session_details(details)

        try:
            session_id = int(details.get("id"))
        except Exception:
            session_id = 0

        events = list(details.get("events") or [])

        app.viewing_history_session_id = session_id
        app.last_summary = summary
        app.last_char_results = []

        app.input_var.set("")
        app.target_var.set(summary.target)

        if events and summary.source == SOURCE_ADAPTIVE_TELEMETRY:
            try:
                decoded = app.decoder_controller.decode_tone_events(
                    events,
                    flush_final=True,
                    target_text=summary.target,
                )
                app.decoder_controller.update_telemetry_display_from_decoded(decoded)
            except Exception:
                app.decoder_controller.update_telemetry_display_from_text(summary.entered)
        else:
            app.decoder_controller.update_telemetry_display_from_text(summary.entered)

        app.decoder_controller.draw_raw_telemetry(
            events=events,
            freeze_time=True,
        )

        app.results_controller.update_latest_result_values(summary)
        app.result_latest_title_var.set(
            app.i18n.t(
                "history.latest_round_title",
                "Round #{session_id} ({elapsed})",
                session_id=session_id,
                elapsed=app.results_controller.format_seconds_label(summary.elapsed_us),
            )
        )
        self.update_practice_result_values_from_single_history_round(summary)

        app.timer_var.set(self.history_time_label(summary))
        app.round_state_var.set(
            app.i18n.t(
                "history.round_state.ready",
                "History round #{session_id}: complete ({reason})",
                session_id=session_id,
                reason=app.practice_controller.finish_reason_label(summary.finish_reason),
            )
        )

        app.status_controller.set_main_status(
            app.i18n.t(
                "history.status.showing_round",
                "Showing history round #{session_id}.",
                session_id=session_id,
            ),
            state="normal",
        )

    def summary_from_session_details(self, details: dict[str, Any]) -> ScoreSummary:
        return ScoreSummary(
            target=str(details.get("target") or ""),
            entered=str(details.get("entered") or ""),
            source=str(details.get("source") or ""),

            accuracy=float(details.get("accuracy") or 0.0),
            cleanliness=float(details.get("cleanliness") or 0.0),
            overall_score=float(details.get("overall_score") or 0.0),
            speed_score=self.optional_float(details.get("speed_score")),
            timing_score=self.optional_float(details.get("timing_score")),

            correct_count=int(details.get("correct_count") or 0),
            error_count=int(details.get("error_count") or 0),
            substitutions=int(details.get("substitutions") or 0),
            insertions=int(details.get("insertions") or 0),
            deletions=int(details.get("deletions") or 0),
            length_target=int(details.get("length_target") or 0),
            length_entered=int(details.get("length_entered") or 0),

            elapsed_us=self.optional_int(details.get("elapsed_us")),
            standard_time_us=self.optional_int(details.get("standard_time_us")),
            time_ok=self.optional_bool(details.get("time_ok")),

            avg_wpm=self.optional_float(details.get("avg_wpm")),
            gross_wpm=self.optional_float(details.get("gross_wpm")),
            net_wpm=self.optional_float(details.get("net_wpm")),
            avg_dit_us=self.optional_float(details.get("avg_dit_us")),
            dit_sd_us=self.optional_float(details.get("dit_sd_us")),

            straight_dot_us=self.optional_float(details.get("straight_dot_us")),
            straight_dot_sd_us=self.optional_float(details.get("straight_dot_sd_us")),

            straight_dash_us=self.optional_float(details.get("straight_dash_us")),
            straight_dash_sd_us=self.optional_float(details.get("straight_dash_sd_us")),

            straight_dash_dot_ratio=self.optional_float(
                details.get("straight_dash_dot_ratio")
            ),

            avg_letter_gap_us=self.optional_float(details.get("avg_letter_gap_us")),
            letter_gap_sd_us=self.optional_float(details.get("letter_gap_sd_us")),

            avg_word_gap_us=self.optional_float(details.get("avg_word_gap_us")),
            word_gap_sd_us=self.optional_float(details.get("word_gap_sd_us")),

            timing_element_score=self.optional_float(details.get("timing_element_score")),
            timing_gap_score=self.optional_float(details.get("timing_gap_score")),
            timing_ratio_score=self.optional_float(details.get("timing_ratio_score")),
            timing_dot_consistency=self.optional_float(details.get("timing_dot_consistency")),
            timing_dash_consistency=self.optional_float(details.get("timing_dash_consistency")),
            timing_intra_gap_score=self.optional_float(details.get("timing_intra_gap_score")),
            timing_letter_gap_score=self.optional_float(details.get("timing_letter_gap_score")),
            timing_word_gap_score=self.optional_float(details.get("timing_word_gap_score")),

            finish_reason=str(details.get("finish_reason") or "in_progress"),
        )

    def update_practice_result_values_from_single_history_round(
        self,
        summary: ScoreSummary,
    ) -> None:
        app = self.app

        app.result_practice_rounds_var.set("1/1")
        app.result_practice_accuracy_var.set(
            f"{summary.accuracy:.1f} %"
        )
        app.result_practice_cleanliness_var.set(
            app.results_controller.fmt_percent(summary.cleanliness)
        )
        app.result_practice_score_var.set(
            app.results_controller.fmt_number(summary.overall_score)
        )
        app.result_practice_timing_var.set(
            app.results_controller.fmt_percent(summary.timing_score)
        )
        app.result_practice_gross_wpm_var.set(
            app.results_controller.fmt_number(summary.gross_wpm)
        )
        app.result_practice_net_wpm_var.set(
            app.results_controller.fmt_number(summary.net_wpm)
        )
        app.result_practice_device_wpm_var.set(
            app.results_controller.fmt_number(summary.avg_wpm)
        )
        app.result_practice_straight_ratio_var.set(
            app.results_controller.fmt_straight_ratio(summary.straight_dash_dot_ratio)
        )
        app.result_practice_dot_variation_var.set(
            app.results_controller.fmt_variation_percent(app.results_controller.summary_dot_variation(summary))
        )
        app.result_practice_dash_variation_var.set(
            app.results_controller.fmt_variation_percent(app.results_controller.summary_dash_variation(summary))
        )
        app.result_practice_element_variation_var.set(
            f"{app.results_controller.fmt_variation_percent(app.results_controller.summary_dot_variation(summary))} / {app.results_controller.fmt_variation_percent(app.results_controller.summary_dash_variation(summary))}"
        )

    def history_time_label(self, summary: ScoreSummary) -> str:
        app = self.app
        elapsed_text = app.results_controller.format_seconds_label(summary.elapsed_us)

        if summary.standard_time_us is None:
            return app.i18n.t(
                "history.time.total",
                "Total time: {elapsed}",
                elapsed=elapsed_text,
            )

        return app.i18n.t(
            "history.time.total_with_reference",
            "Total time: {elapsed} | Reference time {reference}",
            elapsed=elapsed_text,
            reference=app.results_controller.format_seconds_label(summary.standard_time_us),
        )

    def optional_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None

        try:
            return int(value)
        except Exception:
            return None

    def optional_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None

        try:
            return float(value)
        except Exception:
            return None

    def optional_bool(self, value: Any) -> Optional[bool]:
        if value is None:
            return None

        try:
            return bool(int(value))
        except Exception:
            return None

    def load_problem_table(self) -> None:
        app = self.app
        helpers = app.ui_helpers_controller

        for row_id in app.problem_tree.get_children():
            app.problem_tree.delete(row_id)

        for row in app.db.problem_characters(
            getattr(config, "PROBLEM_CHARACTER_DISPLAY_LIMIT", 10000),
            helpers.safe_int_var(
                app.problem_recent_rounds_var,
                default=config.DEFAULT_PROBLEM_RECENT_ROUNDS,
                minimum=1,
                maximum=100000,
            ),
        ):
            app.problem_tree.insert(
                "",
                tk.END,
                values=(
                    self.row_get(row, "char", ""),
                    self.row_get(row, "attempts", ""),
                    self.row_get(row, "errors", ""),
                    self.row_get(row, "error_rate", ""),
                ),
            )

    def refresh_stats_window_if_open(self) -> None:
        app = self.app

        if app.stats_window is None:
            return
        try:
            if app.stats_window.winfo_exists():
                app.stats_window.refresh()
        except Exception:
            pass

    def update_stats_summary(self) -> None:
        app = self.app
        helpers = app.ui_helpers_controller

        try:
            recent_rounds = helpers.safe_int_var(
                app.stats_recent_rounds_var,
                default=1000,
                minimum=1,
                maximum=100000,
            )

            stats = app.db.stats_summary(recent_rounds)
            rounds = int(stats.get("rounds") or 0)

        except Exception:
            self.reset_history_summary_vars("-")
            return

        if rounds <= 0:
            self.reset_history_summary_vars("0")
            return

        if rounds >= recent_rounds:
            app.result_history_rounds_var.set(
                app.i18n.t(
                    "result_panel.history_rounds_limited",
                    "Latest {count}",
                    count=recent_rounds,
                )
            )
        else:
            app.result_history_rounds_var.set(str(rounds))

        app.result_history_accuracy_var.set("-" if stats.get("avg_accuracy") is None else f"{float(stats.get('avg_accuracy')):.1f} %")
        app.result_history_cleanliness_var.set("-" if stats.get("avg_cleanliness") is None else f"{float(stats.get('avg_cleanliness')):.1f} %")
        app.result_history_score_var.set("-" if stats.get("avg_overall_score") is None else f"{float(stats.get('avg_overall_score')):.1f}")
        app.result_history_gross_wpm_var.set("-" if stats.get("avg_gross_wpm") is None else f"{float(stats.get('avg_gross_wpm')):.1f}")
        app.result_history_net_wpm_var.set("-" if stats.get("avg_net_wpm") is None else f"{float(stats.get('avg_net_wpm')):.1f}")
        app.result_history_device_wpm_var.set("-" if stats.get("avg_device_wpm") is None else f"{float(stats.get('avg_device_wpm')):.1f}")
        app.result_history_straight_ratio_var.set(app.results_controller.fmt_straight_ratio(stats.get("avg_straight_dash_dot_ratio")))
        app.result_history_dot_variation_var.set(app.results_controller.fmt_variation_percent(stats.get("avg_straight_dot_variation_percent")))
        app.result_history_dash_variation_var.set(app.results_controller.fmt_variation_percent(stats.get("avg_straight_dash_variation_percent")))

    def reset_history_summary_vars(self, rounds_text: str) -> None:
        app = self.app

        app.result_history_rounds_var.set(rounds_text)
        app.result_history_accuracy_var.set("-")
        app.result_history_cleanliness_var.set("-")
        app.result_history_score_var.set("-")
        app.result_history_gross_wpm_var.set("-")
        app.result_history_net_wpm_var.set("-")
        app.result_history_device_wpm_var.set("-")
        app.result_history_straight_ratio_var.set("-")
        app.result_history_dot_variation_var.set("-")
        app.result_history_dash_variation_var.set("-")

    def update_skill_rating_summary(self, *, cached_rating: Optional[Any] = None) -> None:
        app = self.app
        helpers = app.ui_helpers_controller

        recent_rounds = helpers.safe_int_var(
            app.skill_recent_rounds_var,
            default=getattr(config, "DEFAULT_SKILL_RATING_RECENT_ROUNDS", 1000),
            minimum=1,
            maximum=100000,
        )

        if cached_rating is not None and int(getattr(cached_rating, "recent_rounds", -1)) == recent_rounds:
            rating = cached_rating
        else:
            try:
                rating = calculate_skill_rating(app.db, recent_rounds=recent_rounds)
            except Exception as exc:
                self.set_skill_error(str(exc))
                return

        if rating is None or rating.raw_skill is None:
            self.set_empty_skill_rating(rating, recent_rounds)
            return

        self.set_skill_rating_values(rating)

    def skill_two_col(self, left_label: str, left_value: str, right_label: str = "", right_value: str = "") -> str:
        left = f"{left_label:<18}{left_value:<10}"
        right = f"{right_label:<14}{right_value}" if right_label else ""
        return left + right

    def reset_skill_metric_values(self) -> None:
        app = self.app

        app.skill_accuracy_value_var.set("-")
        app.skill_cleanliness_value_var.set("-")
        app.skill_timing_value_var.set("-")
        app.skill_adjustment_value_var.set("-")
        app.skill_confidence_value_var.set("-")
        app.skill_mastery_value_var.set("-")
        app.skill_coverage_value_var.set("-")
        app.skill_used_rounds_value_var.set("-")
        app.skill_total_used_rounds_value_var.set("-")
        app.skill_charset_coverage_value_var.set("-")
        app.skill_charset_scope_value_var.set("-")

    def set_skill_error(self, message: str) -> None:
        app = self.app

        app.skill_title_var.set("-")
        app.skill_rating_var.set(
            app.i18n.t("skill.status.calculation_failed", "Calculation failed")
        )
        app.skill_key_wpm_var.set("-")
        self.reset_skill_metric_values()
        app.skill_warning_var.set(message)

    def set_empty_skill_rating(self, rating: Any, recent_rounds: int) -> None:
        app = self.app

        app.skill_title_var.set(
            app.i18n.t("skill.status.not_enough_data", "Not enough data yet")
        )

        rounds_text = (
            f"{getattr(rating, 'total_rounds', 0)}/{recent_rounds}"
            if rating is not None
            else f"0/{recent_rounds}"
        )

        app.skill_rating_var.set(
            "\n".join([
                self.skill_two_col(
                    app.i18n.t("skill.rounds", "Rounds"),
                    rounds_text,
                    app.i18n.t("skill.straight_wpm", "Straight WPM"),
                    "-",
                ),
                self.skill_two_col(
                    app.i18n.t("skill.effective_wpm", "Effective WPM"),
                    "-",
                    app.i18n.t("skill.iambic_wpm", "Iambic WPM"),
                    "-",
                ),
            ])
        )
        app.skill_key_wpm_var.set("")
        self.reset_skill_metric_values()
        app.skill_warning_var.set("" if rating is None else rating.reason)

    def set_skill_rating_values(self, rating: Any) -> None:
        app = self.app
        progress_percent = rating.level_progress * 100.0
        confidence_percent = rating.rating_confidence * 100.0

        # Uncapped PARIS WPM values are shown to the user when available.
        # The capped straight_wpm/iambic_wpm values remain available for the
        # internal skill model.
        iambic_wpm = getattr(
            rating,
            "iambic_paris_wpm",
            getattr(rating, "iambic_wpm", None),
        )
        straight_wpm = getattr(
            rating,
            "straight_paris_wpm",
            getattr(rating, "straight_wpm", None),
        )

        iambic_rounds = int(getattr(rating, "iambic_used_rounds", 0) or 0)
        straight_rounds = int(getattr(rating, "straight_used_rounds", 0) or 0)
        total_key_rounds = straight_rounds + iambic_rounds

        iambic_text = "-" if iambic_wpm is None else f"{float(iambic_wpm):.1f} ({iambic_rounds})"
        straight_text = "-" if straight_wpm is None else f"{float(straight_wpm):.1f} ({straight_rounds})"

        title_suffix = (
            app.i18n.t("skill.title_suffix.preliminary", " (preliminary)")
            if not getattr(rating, "ok", True)
            else ""
        )

        level = int(rating.level)
        title_key = getattr(rating, "title_key", title_key_for_level(level))
        title_text = app.i18n.t(title_key, str(rating.title))

        app.skill_title_var.set(
            app.i18n.t(
                "skill.level_title",
                "Level {level} - {title}{suffix}",
                level=level,
                title=title_text,
                suffix=title_suffix,
            )
        )

        app.skill_rating_var.set("\n".join([
            self.skill_two_col(
                app.i18n.t("skill.overall_wpm", "Overall skill WPM"),
                f"{rating.raw_skill:.2f}",
                app.i18n.t("skill.straight_wpm", "Straight WPM"),
                straight_text,
            ),
            self.skill_two_col(
                app.i18n.t("skill.both_wpm", "Both keys WPM"),
                "-" if rating.effective_wpm is None else f"{rating.effective_wpm:.1f}",
                app.i18n.t("skill.iambic_wpm", "Iambic WPM"),
                iambic_text,
            ),
            self.skill_two_col(
                app.i18n.t("skill.next_level", "Next level"),
                f"{progress_percent:.0f} %",
            ),
        ]))

        app.skill_key_wpm_var.set("")
        app.skill_accuracy_value_var.set("-" if rating.avg_accuracy is None else f"{rating.avg_accuracy:.1f} %")
        app.skill_cleanliness_value_var.set("-" if rating.avg_cleanliness is None else f"{rating.avg_cleanliness:.1f} %")
        app.skill_timing_value_var.set(self.skill_timing_text(rating))
        app.skill_adjustment_value_var.set(f"{rating.mastery_adjustment:.2f}x")
        app.skill_confidence_value_var.set(f"{confidence_percent:.0f} % ({self.confidence_word(rating.rating_confidence)})")
        app.skill_mastery_value_var.set(f"{rating.character_mastery_factor * 100:.0f} %")
        app.skill_coverage_value_var.set(f"{rating.coverage_factor * 100:.0f} %")
        app.skill_used_rounds_value_var.set(str(rating.used_rounds))
        app.skill_total_used_rounds_value_var.set(str(total_key_rounds))

        full_total = int(getattr(rating, "full_charset_total", 0) or 0)
        qualified_count = int(getattr(rating, "full_charset_qualified_count", 0) or 0)
        qualified_coverage = float(getattr(rating, "full_charset_qualified_coverage", 0.0) or 0.0)
        charset_scope_factor = float(getattr(rating, "charset_scope_factor", 1.0) or 1.0)

        if full_total > 0:
            app.skill_charset_coverage_value_var.set(
                f"{qualified_count}/{full_total} ({qualified_coverage * 100:.0f} %)"
            )
        else:
            app.skill_charset_coverage_value_var.set("-")

        charset_scope_text = f"{charset_scope_factor:.2f}x"
        if charset_scope_factor >= 0.9995:
            charset_scope_text += f" ({app.i18n.t('skill.charset_scope_max', 'max')})"

        app.skill_charset_scope_value_var.set(charset_scope_text)
        app.skill_warning_var.set(rating.reason)

    def skill_timing_text(self, rating: Any) -> str:
        timing_score = getattr(rating, "timing_quality_score", None)
        if timing_score is None:
            return f"{rating.timing_stability_factor * 100:.0f} %"

        parts = [f"{float(timing_score):.0f} %", f"{float(rating.timing_stability_factor):.2f}x"]
        source_parts = []

        straight_timing_score = getattr(rating, "straight_timing_score", None)
        iambic_timing_score = getattr(rating, "iambic_timing_score", None)

        if straight_timing_score is not None:
            source_parts.append(f"S {float(straight_timing_score):.0f}")
        if iambic_timing_score is not None:
            source_parts.append(f"I {float(iambic_timing_score):.0f}")
        if source_parts:
            parts.append("(" + ", ".join(source_parts) + ")")

        return " ".join(parts)

    def update_target_wpm_suggestion_indicator(self) -> None:
        app = self.app
        helpers = app.ui_helpers_controller

        if (
            bool(getattr(app, "practice_running", False))
            or bool(getattr(app, "start_countdown_running", False))
            or bool(getattr(getattr(app, "round", None), "accepting_input", False))
        ):
            return

        if not hasattr(app, "target_wpm_suggestion_delta_var") or not hasattr(app, "target_wpm_delta_label"):
            return

        try:
            result = app.db.optimized_wpm_from_recent_sessions(
                recent_sessions=helpers.safe_int_var(
                    app.effective_wpm_recent_rounds_var,
                    default=getattr(config, "DEFAULT_EFFECTIVE_WPM_RECENT_ROUNDS", 1000),
                    minimum=1,
                    maximum=100000,
                ),
                min_accuracy=helpers.safe_int_var(
                    app.effective_wpm_min_accuracy_var,
                    default=getattr(config, "DEFAULT_EFFECTIVE_WPM_MIN_ACCURACY", 90),
                    minimum=0,
                    maximum=100,
                ),
                min_cleanliness=helpers.safe_int_var(
                    app.effective_wpm_min_cleanliness_var,
                    default=getattr(config, "DEFAULT_EFFECTIVE_WPM_MIN_CLEANLINESS", 85),
                    minimum=0,
                    maximum=100,
                ),
            )
        except Exception:
            self.clear_target_wpm_suggestion_indicator()
            return

        if not result.get("ok") or int(result.get("used_rounds") or 0) < getattr(config, "EFFECTIVE_WPM_MIN_ROUNDS_REQUIRED", 3):
            self.clear_target_wpm_suggestion_indicator()
            return

        try:
            raw_wpm = float(result["wpm"])
            current_wpm = helpers.safe_int_var(
                app.target_wpm_var,
                default=config.DEFAULT_TARGET_WPM,
                minimum=5,
                maximum=80,
            )
        except Exception:
            self.clear_target_wpm_suggestion_indicator()
            return

        suggested_wpm = max(
            config.EFFECTIVE_WPM_MIN_WPM,
            min(config.EFFECTIVE_WPM_MAX_WPM, round(raw_wpm + 1.0)),
        )
        delta = suggested_wpm - current_wpm

        if delta > 0:
            app.target_wpm_suggestion_delta_var.set(f"+{delta}")
            app.target_wpm_delta_label.configure(foreground="#178a2f")
        elif delta < 0:
            app.target_wpm_suggestion_delta_var.set(str(delta))
            app.target_wpm_delta_label.configure(foreground="#b00020")
        else:
            app.target_wpm_suggestion_delta_var.set("✓")
            app.target_wpm_delta_label.configure(foreground="#666666")

    def clear_target_wpm_suggestion_indicator(self) -> None:
        app = self.app
        app.target_wpm_suggestion_delta_var.set("")
        app.target_wpm_delta_label.configure(foreground="#666666")

    def sort_history_tree(self, column: str, reverse: bool = False) -> None:
        app = self.app
        rows = [
            (self.sort_value(app.history_tree.set(item_id, column)), item_id)
            for item_id in app.history_tree.get_children("")
        ]
        rows.sort(key=lambda item: item[0], reverse=reverse)
        for index, (_value, item_id) in enumerate(rows):
            app.history_tree.move(item_id, "", index)
        app.history_tree.heading(column, command=lambda: self.sort_history_tree(column, not reverse))

    def sort_value(self, value: str) -> Any:
        text = str(value).strip()
        if text in {"", "-"}:
            return float("-inf")
        cleaned = text.replace("%", "").replace("s", "").replace(",", ".").strip()
        try:
            return float(cleaned)
        except ValueError:
            return text.lower()

    def row_get(self, row: Any, key: str, default: Any = None) -> Any:
        try:
            return row[key]
        except Exception:
            pass
        try:
            return row.get(key, default)
        except Exception:
            return default

    def format_datetime(self, iso_value: str) -> str:
        try:
            return datetime.fromisoformat(iso_value).strftime("%d.%m.%Y %H:%M:%S")
        except Exception:
            return iso_value

    def confidence_word(self, value: float) -> str:
        app = self.app
        value = max(0.0, min(1.0, float(value)))

        if value < 0.20:
            return app.i18n.t("skill.confidence.low", "low")
        if value < 0.45:
            return app.i18n.t("skill.confidence.preliminary", "preliminary")
        if value < 0.70:
            return app.i18n.t("skill.confidence.moderate", "moderate")
        if value < 0.90:
            return app.i18n.t("skill.confidence.good", "good")

        return app.i18n.t("skill.confidence.excellent", "excellent")

    def confidence_label(self, value: float, accepted_count: int | None = None) -> str:
        value = max(0.0, min(1.0, float(value)))
        percent = int(round(value * 100))
        label = self.confidence_word(value)

        try:
            required_rounds = int(getattr(config, "DECODER_PROFILE_MIN_ROUNDS_REQUIRED", 100))
        except Exception:
            required_rounds = 100

        if accepted_count is not None and accepted_count < required_rounds:
            return self.app.i18n.t(
                "skill.confidence.learning",
                "{label} ({percent} %) - learning in progress",
                label=label,
                percent=percent,
            )

        return self.app.i18n.t(
            "skill.confidence.label",
            "{label} ({percent} %)",
            label=label,
            percent=percent,
        )