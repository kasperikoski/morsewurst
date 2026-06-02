# ============================================================
# morsewurst/ui/koch/window.py
# ============================================================

from __future__ import annotations

from typing import Any, Callable

import tkinter as tk
from tkinter import messagebox, ttk

import morsewurst.config as config
from morsewurst.koch.models import (
    KochSessionResult,
    KochSettings,
    KochSkillSummary,
    maximum_koch_target_chars,
)
from morsewurst.koch.sequence import all_koch_sequences, koch_sequence_by_key
from morsewurst.ui.koch.views import (
    KochActionsView,
    KochCountdownView,
    KochCharactersView,
    KochComparisonView,
    KochHistoryView,
    KochInputView,
    KochProblemCharactersView,
    KochResultView,
    KochSettingsView,
    KochSkillView,
)


class KochWindow(tk.Toplevel):
    """Koch receive-practice window."""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.app = app
        self.tr = app.i18n.t

        self.title(self.tr("koch.window.title", "Koch receive practice"))
        self.geometry(self.app.koch_controller.koch_window_geometry())
        self.minsize(
            int(getattr(config, "UI_KOCH_WINDOW_MIN_WIDTH", 1200)),
            int(getattr(config, "UI_KOCH_WINDOW_MIN_HEIGHT", 920)),
        )
        self.transient(app)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Configure>", self._on_configure, add="+")

        defaults = app.koch_controller.default_settings()
        self.sequence_label_to_key = {
            self.sequence_display_label(seq): seq.key
            for seq in all_koch_sequences()
        }
        self.sequence_key_to_label = {
            seq.key: self.sequence_display_label(seq)
            for seq in all_koch_sequences()
        }

        self.mode_label_to_key = {
            self.tr("koch.mode.guided", "Guided"): "guided",
            self.tr("koch.mode.manual", "Manual stage"): "manual",
            self.tr("koch.mode.full_charset", "Full charset"): "full_charset",
        }
        self.mode_key_to_label = {value: key for key, value in self.mode_label_to_key.items()}
        self.mode_label_var = tk.StringVar(value=self.mode_key_to_label.get(defaults.mode, "Guided"))
        self.sequence_var = tk.StringVar(
            value=self.sequence_key_to_label.get(defaults.sequence_key, all_koch_sequences()[0].label)
        )
        self.stage_var = tk.IntVar(value=defaults.stage_index)
        self.target_chars_var = tk.IntVar(value=defaults.target_chars)
        self.character_wpm_var = tk.IntVar(value=defaults.character_wpm)
        self.effective_wpm_var = tk.IntVar(value=defaults.effective_wpm)
        self.tone_hz_var = tk.IntVar(value=defaults.tone_hz)
        self.volume_percent_var = tk.IntVar(value=defaults.volume_percent)

        self._countdown_after_id: str | None = None
        self._countdown_cancelled = False
        self._last_demotion_notice_session_id: int | None = None

        self._build_ui()
        self.center_over_parent()
        self.app.koch_controller.enter_mode()
        self.app.koch_controller.refresh_window_state(self)
        self.after(100, self.input_view.input_text.focus_set)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        right_width = int(getattr(config, "UI_KOCH_RIGHT_PANEL_WIDTH", 500))

        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=0, minsize=right_width)
        root.rowconfigure(0, weight=1)

        left = ttk.Frame(root)
        left.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 12))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(3, weight=0)
        left.rowconfigure(4, weight=0)
        left.rowconfigure(6, weight=1)

        right = ttk.Frame(root, width=right_width)
        right.grid(row=0, column=1, sticky=tk.NSEW)
        right.grid_propagate(False)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        self.settings_view = KochSettingsView(left, self)
        self.settings_view.grid(row=0, column=0, sticky=tk.EW)

        self.countdown_view = KochCountdownView(left, self)
        self.countdown_view.grid(row=1, column=0, sticky=tk.EW, pady=(10, 0))

        self.characters_view = KochCharactersView(left, self)
        self.characters_view.grid(row=2, column=0, sticky=tk.EW, pady=(8, 0))

        self.input_view = KochInputView(left, self)
        self.input_view.grid(row=3, column=0, sticky=tk.EW, pady=(12, 0))

        self.comparison_view = KochComparisonView(left, self)
        self.comparison_view.grid(row=4, column=0, sticky=tk.EW, pady=(8, 0))

        self.result_view = KochResultView(left, self)
        self.result_view.grid(row=5, column=0, sticky=tk.EW, pady=(8, 0))

        self.actions_view = KochActionsView(right, self)
        self.actions_view.grid(row=0, column=0, sticky=tk.EW)

        self.skill_view = KochSkillView(right, self)
        self.skill_view.grid(row=1, column=0, sticky=tk.EW, pady=(12, 0))

        self.problem_characters_view = KochProblemCharactersView(right, self)
        self.problem_characters_view.grid(row=2, column=0, sticky=tk.NSEW, pady=(12, 0))

        self.history_view = KochHistoryView(left, self)
        self.history_view.grid(row=6, column=0, sticky=tk.NSEW, pady=(8, 0))

    def center_over_parent(self) -> None:
        self.update_idletasks()
        parent = self.app
        try:
            parent.update_idletasks()
            width = self.winfo_width() or int(getattr(config, "UI_KOCH_WINDOW_MIN_WIDTH", 1200))
            height = self.winfo_height() or int(getattr(config, "UI_KOCH_WINDOW_MIN_HEIGHT", 920))
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_width = parent.winfo_width()
            parent_height = parent.winfo_height()
            x = parent_x + max(0, (parent_width - width) // 2)
            y = parent_y + max(0, (parent_height - height) // 2)
            self.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass

    def sequence_display_label(self, sequence: Any) -> str:
        return self.tr(f"koch.sequence.{sequence.key}", sequence.label)

    def mode_key(self) -> str:
        return self.mode_label_to_key.get(self.mode_label_var.get(), "guided")

    def on_mode_changed(self) -> None:
        mode = self.mode_key()
        if mode == "guided":
            key = self.sequence_label_to_key.get(self.sequence_var.get(), "classic")
            self.stage_var.set(self.app.koch_controller.progress_stage_for_sequence(key))
        elif mode == "full_charset":
            key = self.sequence_label_to_key.get(self.sequence_var.get(), "classic")
            sequence = koch_sequence_by_key(key)
            self.stage_var.set(len(sequence.characters))

        self.settings_view.refresh_mode_controls()
        self.app.koch_controller.remember_window_settings(self)
        self.app.koch_controller.refresh_window_state(self)

    def on_sequence_changed(self, _event: tk.Event | None = None) -> None:
        key = self.sequence_label_to_key.get(self.sequence_var.get(), "classic")
        if self.mode_key() == "guided":
            self.stage_var.set(self.app.koch_controller.progress_stage_for_sequence(key))
        elif self.mode_key() == "full_charset":
            self.stage_var.set(len(koch_sequence_by_key(key).characters))

        self.app.koch_controller.remember_window_settings(self)
        self.app.koch_controller.refresh_window_state(self)

    def manual_setting_changed(self) -> None:
        self.app.koch_controller.remember_window_settings(self)
        self.app.koch_controller.refresh_window_state(self)

    def collect_settings(self) -> dict[str, Any]:
        sequence_key = self.sequence_label_to_key.get(self.sequence_var.get(), "classic")
        sequence = koch_sequence_by_key(sequence_key)
        mode = self.mode_key()

        stage_index = int(self.stage_var.get())
        if mode == "full_charset":
            stage_index = len(sequence.characters)

        return {
            "mode": mode,
            "sequence_key": sequence.key,
            "stage_index": stage_index,
            "target_chars": int(self.target_chars_var.get()),
            "character_wpm": int(self.character_wpm_var.get()),
            "effective_wpm": int(self.effective_wpm_var.get()),
            "tone_hz": int(self.tone_hz_var.get()),
            "volume_percent": int(self.volume_percent_var.get()),
        }

    def set_stage_bounds(self, max_stage: int) -> None:
        self.settings_view.set_stage_bounds(max_stage)
        self.settings_view.refresh_mode_controls()

    def set_target_chars_minimum(self, minimum: int) -> bool:
        minimum = max(1, int(minimum))
        maximum = maximum_koch_target_chars()
        self.settings_view.set_target_chars_minimum(minimum)
        self.settings_view.set_target_chars_maximum(maximum)

        try:
            current = int(self.target_chars_var.get())
        except Exception:
            current = minimum

        if current < minimum:
            self.target_chars_var.set(minimum)
            return True

        if current > maximum:
            self.target_chars_var.set(maximum)
            return True

        return False

    def update_progress_summary(self, settings: KochSettings) -> None:
        self.characters_view.update_progress_summary(settings)

    def update_character_grid(self, settings: KochSettings) -> None:
        self.characters_view.update_character_grid(settings)

    def update_skill_summary(
        self,
        summary: KochSkillSummary,
        progress_items: list[dict[str, Any]] | None = None,
    ) -> None:
        self.skill_view.update_summary(summary, progress_items)

    def prepare_for_countdown(self, *, target: str, settings: KochSettings, seconds: int) -> None:
        del target, settings
        self.cancel_countdown()
        self._countdown_cancelled = False
        self.input_view.clear_and_focus()
        self.comparison_view.clear()
        self.result_view.result_var.set(self.tr("koch.result.running", "Practice is running. The target text is hidden."))
        self.input_view.status_var.set(
            self.tr("koch.status.countdown", "Get ready. Playback starts after the countdown.")
        )
        self.actions_view.set_countdown()
        self.countdown_view.set_countdown(float(seconds), 100.0)

    def start_countdown(self, seconds: int, on_done: Callable[[], None]) -> None:
        total_ms = max(0, int(seconds) * 1000)
        started_at = self._now_ms()

        def tick() -> None:
            if self._countdown_cancelled:
                return
            elapsed = self._now_ms() - started_at
            remaining_ms = max(0, total_ms - elapsed)
            progress = 0.0 if total_ms <= 0 else (remaining_ms / total_ms) * 100.0
            self.countdown_view.set_countdown(remaining_ms / 1000.0, progress)
            if remaining_ms <= 0:
                self._countdown_after_id = None
                on_done()
                return
            self._countdown_after_id = self.after(50, tick)

        tick()

    def cancel_countdown(self) -> None:
        self._countdown_cancelled = True
        if self._countdown_after_id is not None:
            try:
                self.after_cancel(self._countdown_after_id)
            except Exception:
                pass
            self._countdown_after_id = None

    def prepare_for_session(self, *, target: str, settings: KochSettings) -> None:
        del target, settings
        self.input_view.clear_and_focus()
        self.comparison_view.clear()
        self.actions_view.set_running()
        self.countdown_view.set_running()
        self.input_view.status_var.set(
            self.tr(
                "koch.status.running",
                "Playing. Type the characters as you hear them. Target is hidden until scoring.",
            )
        )
        self.result_view.result_var.set(
            self.tr(
                "koch.result.running",
                "Practice is running. The target text is hidden.",
            )
        )

    def reset_after_stopped(self) -> None:
        self.cancel_countdown()
        self.actions_view.set_idle()
        self.countdown_view.set_idle()
        self.input_view.status_var.set(self.tr("koch.status.stopped", "Practice cancelled."))

    def entered_text(self) -> str:
        return self.input_view.entered_text()

    def on_input_key_press(self, event: tk.Event) -> str | None:
        controller = self.app.koch_controller

        if not controller.practice_active:
            return "break"

        keysym = str(getattr(event, "keysym", "") or "")

        if keysym == "BackSpace":
            return "break"

        if keysym in {"Return", "KP_Enter"}:
            return "break"

        char = str(getattr(event, "char", "") or "")
        if len(char) != 1 or ord(char) < 32:
            return "break"

        char = char.upper()
        sequence = koch_sequence_by_key(self.sequence_label_to_key.get(self.sequence_var.get(), "classic"))

        if char not in sequence.characters:
            return "break"

        self.input_view.input_text.insert(tk.INSERT, char)
        controller.record_typed_character(key=keysym, char=char)
        return "break"

    def stop_clicked(self) -> None:
        self.cancel_countdown()
        self.app.koch_controller.stop_session()
        self.reset_after_stopped()

    def show_result(self, session_id: int, result: KochSessionResult) -> None:
        self.actions_view.set_idle()
        self.countdown_view.set_idle()

        status_key = "koch.result.passed" if result.passed else "koch.result.not_passed"
        status_default = "Passed." if result.passed else "Not passed yet."

        self.input_view.status_var.set(self.tr(status_key, status_default))

        new_char = result.new_stage_char or "-"
        new_acc = "-" if result.new_char_accuracy is None else f"{result.new_char_accuracy:.1f} %"

        demotion_line = ""
        if result.demoted_from_stage is not None and result.demoted_to_stage is not None:
            demotion_line = "\n" + self.tr(
                "koch.result.demoted",
                "Guided level dropped: {from_stage} -> {to_stage}",
                from_stage=int(result.demoted_from_stage),
                to_stage=int(result.demoted_to_stage),
            )

        self.result_view.result_var.set(
            self.tr(
                "koch.result.summary",
                (
                    "Session #{session_id}\n"
                    "Copy accuracy: {accuracy} %\n"
                    "Timing accuracy: {time_accuracy} %\n"
                    "Timing fit: {timing_fit} %\n"
                    "Cleanliness: {cleanliness} %\n"
                    "New char {new_char}: {new_accuracy}\n"
                    "Pass eligible: {eligible}"
                    "{demotion_line}"
                ),
                session_id=session_id,
                accuracy=f"{result.accuracy:.1f}",
                time_accuracy=f"{result.time_aligned_accuracy:.1f}",
                timing_fit=f"{result.timing_fit:.1f}",
                cleanliness=f"{result.cleanliness:.1f}",
                new_char=new_char,
                new_accuracy=new_acc,
                eligible=self.tr("koch.yes", "yes") if result.pass_eligible else self.tr("koch.no", "no"),
                demotion_line=demotion_line,
            )
        )
        self.comparison_view.show_result(result)
        self.after(75, lambda: self._show_demotion_notice(session_id, result))

    def _show_demotion_notice(self, session_id: int, result: KochSessionResult) -> None:
        if result.demoted_from_stage is None or result.demoted_to_stage is None:
            return

        if self._last_demotion_notice_session_id == session_id:
            return

        self._last_demotion_notice_session_id = session_id

        try:
            sequence = koch_sequence_by_key(result.sequence_key)
            sequence_label = self.sequence_display_label(sequence)
        except Exception:
            sequence_label = str(result.sequence_key or "")

        pass_accuracy = float(result.settings_json.get("pass_accuracy", 90.0))
        pass_cleanliness = float(result.settings_json.get("pass_cleanliness", 85.0))

        title = self.tr("koch.demotion_notice.title", "Level lowered")
        message = self.tr(
            "koch.demotion_notice.message",
            (
                "Five consecutive {sequence} practice sessions stayed below the target.\n\n"
                "Reaching the target requires at least {accuracy:g} % text accuracy and "
                "{cleanliness:g} % cleanliness.\n\n"
                "The stage is lowered from {from_stage} to {to_stage}."
            ),
            sequence=sequence_label,
            accuracy=pass_accuracy,
            cleanliness=pass_cleanliness,
            from_stage=int(result.demoted_from_stage),
            to_stage=int(result.demoted_to_stage),
        )

        messagebox.showinfo(title, message, parent=self)

    def load_recent_sessions(self, rows: list[Any]) -> None:
        self.history_view.load_recent_sessions(rows)

    def load_character_stats(self, rows: list[Any]) -> None:
        self.problem_characters_view.load_character_stats(rows)

    def _on_configure(self, event: tk.Event) -> None:
        if getattr(event, "widget", None) is not self:
            return

        try:
            self.app.koch_controller.remember_window_geometry(self.geometry())
        except Exception:
            pass

    def on_close(self) -> None:
        self.cancel_countdown()
        self.app.koch_controller.remember_window_settings(self)
        self.app.koch_controller.remember_window_geometry(self.geometry())
        try:
            self.app.settings_controller.save_ui_settings_async()
        except Exception:
            pass
        self.app.koch_controller.leave_mode()
        self.app.koch_window = None
        self.destroy()

    @staticmethod
    def _now_ms() -> int:
        import time

        return int(round(time.monotonic() * 1000.0))
