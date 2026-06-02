# ============================================================
# morsewurst/ui/controllers/koch_controller.py
# ============================================================

from __future__ import annotations

import queue
import time
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

import tkinter as tk
from tkinter import messagebox

import morsewurst.config as config
from morsewurst.core.app_logging import log_app_event, log_app_exception
from morsewurst.koch.models import (
    KochSettings,
    maximum_koch_target_chars,
    minimum_koch_target_chars,
    normalize_koch_settings_for_active_count,
)
from morsewurst.koch.playback import KochPlayback
from morsewurst.koch.service import KochPracticeService, default_koch_settings
from morsewurst.koch.sequence import active_chars_for_stage, all_koch_sequences, koch_sequence_by_key

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp
    from morsewurst.ui.koch.window import KochWindow


class KochController:
    """Owns Koch receive-practice mode state and service coordination."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app
        self.playback = KochPlayback()
        self.service: KochPracticeService | None = None

        self.current_target = ""
        self.current_target_schedule: list[dict[str, Any]] = []
        self.started_at: datetime | None = None
        self.started_monotonic: float | None = None
        self.typed_events: list[dict[str, Any]] = []
        self.practice_active = False
        self.current_settings: KochSettings | None = None
        self._playback_callback_queue: queue.Queue[tuple[int, Callable[[], None]]] = queue.Queue()
        self._playback_callback_after_id: str | None = None
        self._playback_callback_token = 0

        defaults = default_koch_settings()
        self.mode_var = tk.StringVar(value=defaults.mode)
        self.sequence_key_var = tk.StringVar(value=defaults.sequence_key)
        self.stage_index_var = tk.IntVar(value=defaults.stage_index)
        self.target_chars_var = tk.IntVar(value=defaults.target_chars)
        self.character_wpm_var = tk.IntVar(value=defaults.character_wpm)
        self.effective_wpm_var = tk.IntVar(value=defaults.effective_wpm)
        self.tone_hz_var = tk.IntVar(value=defaults.tone_hz)
        self.volume_percent_var = tk.IntVar(value=defaults.volume_percent)
        self.window_geometry_var = tk.StringVar(
            value=str(getattr(config, "UI_KOCH_WINDOW_GEOMETRY", "1260x1000"))
        )

        self.auto_score_delay_ms_var = tk.IntVar(value=defaults.auto_score_delay_ms)

    def ensure_service(self) -> KochPracticeService:
        if self.service is None:
            self.service = KochPracticeService(self.app.db)
        return self.service

    def enter_mode(self) -> None:
        self.app.active_mode = "koch"
        self.app.status_controller.set_main_status(
            self.app.i18n.t(
                "koch.status.active",
                "Koch receive mode is active.",
            ),
            state="normal",
        )

    def leave_mode(self) -> None:
        self.stop_session()
        self.app.active_mode = "main"
        self.app.status_controller.set_main_status(
            self.app.i18n.t(
                "koch.status.closed",
                "Koch receive mode closed.",
            ),
            state="normal",
        )

    def default_settings(self) -> KochSettings:
        defaults = default_koch_settings()
        return KochSettings(
            **{
                **asdict(defaults),
                **self.saved_practice_settings_data(),
                **self.advanced_settings_data(),
            }
        ).normalized()

    def saved_practice_settings_data(self) -> dict[str, Any]:
        helpers = self.app.ui_helpers_controller

        return {
            "mode": str(self.mode_var.get() or getattr(config, "DEFAULT_KOCH_MODE", "guided")),
            "sequence_key": str(
                self.sequence_key_var.get()
                or getattr(config, "DEFAULT_KOCH_SEQUENCE", "classic")
            ),
            "stage_index": helpers.safe_int_var(
                self.stage_index_var,
                default=int(getattr(config, "DEFAULT_KOCH_STAGE_INDEX", 2)),
                minimum=1,
                maximum=1000,
            ),
            "target_chars": helpers.safe_int_var(
                self.target_chars_var,
                default=int(getattr(config, "DEFAULT_KOCH_TARGET_CHARS", 30)),
                minimum=minimum_koch_target_chars(0),
                maximum=maximum_koch_target_chars(),
            ),
            "character_wpm": helpers.safe_int_var(
                self.character_wpm_var,
                default=int(getattr(config, "DEFAULT_KOCH_CHARACTER_WPM", 20)),
                minimum=5,
                maximum=80,
            ),
            "effective_wpm": helpers.safe_int_var(
                self.effective_wpm_var,
                default=int(getattr(config, "DEFAULT_KOCH_EFFECTIVE_WPM", 15)),
                minimum=5,
                maximum=80,
            ),
            "tone_hz": helpers.safe_int_var(
                self.tone_hz_var,
                default=int(getattr(config, "DEFAULT_KOCH_TONE_HZ", 600)),
                minimum=100,
                maximum=2000,
            ),
            "volume_percent": helpers.safe_int_var(
                self.volume_percent_var,
                default=int(getattr(config, "DEFAULT_KOCH_VOLUME_PERCENT", 70)),
                minimum=0,
                maximum=100,
            ),
        }

    def koch_window_geometry(self) -> str:
        geometry = str(
            self.window_geometry_var.get()
            or getattr(config, "UI_KOCH_WINDOW_GEOMETRY", "1260x1000")
        ).strip()

        if "x" not in geometry.lower():
            return str(getattr(config, "UI_KOCH_WINDOW_GEOMETRY", "1260x1000"))

        return geometry

    def remember_window_geometry(self, geometry: str) -> None:
        value = str(geometry or "").strip()
        if "x" in value.lower():
            self.window_geometry_var.set(value)

    def remember_window_settings(self, window: "KochWindow") -> None:
        try:
            data = window.collect_settings()
        except Exception:
            return

        self.mode_var.set(str(data.get("mode", self.mode_var.get()) or "guided"))
        self.sequence_key_var.set(
            str(data.get("sequence_key", self.sequence_key_var.get()) or "classic")
        )

        for key, variable in (
            ("stage_index", self.stage_index_var),
            ("target_chars", self.target_chars_var),
            ("character_wpm", self.character_wpm_var),
            ("effective_wpm", self.effective_wpm_var),
            ("tone_hz", self.tone_hz_var),
            ("volume_percent", self.volume_percent_var),
        ):
            try:
                variable.set(int(data.get(key, variable.get())))
            except Exception:
                pass

    def advanced_settings_data(self) -> dict[str, Any]:
        helpers = self.app.ui_helpers_controller

        return {
            "auto_score_delay_ms": helpers.safe_int_var(
                self.auto_score_delay_ms_var,
                default=int(getattr(config, "DEFAULT_KOCH_AUTO_SCORE_DELAY_MS", 1500)),
                minimum=0,
                maximum=10000,
            ),
        }

    def progress_stage_for_sequence(self, sequence_key: str) -> int:
        try:
            progress = self.ensure_service().progress_for_sequence(sequence_key)
            return max(2, int(progress.guided_current_stage))
        except Exception:
            return 2

    def minimum_target_chars_for_settings(self, settings: KochSettings) -> int:
        settings = settings.normalized()
        sequence = koch_sequence_by_key(settings.sequence_key)
        active_chars = active_chars_for_stage(sequence, settings.stage_index)
        return minimum_koch_target_chars(len(set(active_chars)))

    def settings_with_target_minimum(self, settings: KochSettings) -> KochSettings:
        settings = settings.normalized()
        sequence = koch_sequence_by_key(settings.sequence_key)
        active_chars = active_chars_for_stage(sequence, settings.stage_index)
        return normalize_koch_settings_for_active_count(settings, len(set(active_chars)))


    def _start_playback_callback_poll(self) -> None:
        if self._playback_callback_after_id is not None:
            return

        try:
            self._playback_callback_after_id = self.app.after(50, self._poll_playback_callback_queue)
        except Exception:
            self._playback_callback_after_id = None

    def _poll_playback_callback_queue(self) -> None:
        self._playback_callback_after_id = None

        while True:
            try:
                token, callback = self._playback_callback_queue.get_nowait()
            except queue.Empty:
                break

            if token != self._playback_callback_token:
                continue

            try:
                callback()
            except Exception as exc:
                log_app_exception(
                    "app.koch.playback_callback_failed",
                    exc,
                    level="warning",
                    message="Koch playback callback failed on the UI thread.",
                )

        if self.playback.running or not self._playback_callback_queue.empty():
            self._start_playback_callback_poll()

    def _queue_playback_callback(self, token: int, callback: Callable[[], None]) -> None:
        self._playback_callback_queue.put((int(token), callback))


    def koch_sequence_progress_items(self, service: KochPracticeService | None = None) -> list[dict[str, Any]]:
        """Return guided progress rows for each visible Koch sequence.

        Guided progress is stored by sequence key, so Classic Koch and LCWO are
        intentionally shown as separate progress bars.
        """

        service = service or self.ensure_service()
        items: list[dict[str, Any]] = []

        for sequence in all_koch_sequences():
            try:
                progress = service.progress_for_sequence(sequence.key)
                current = max(1, int(progress.guided_current_stage))
            except Exception:
                current = 2

            total = max(1, len(sequence.characters))
            current = max(0, min(current, total))

            items.append(
                {
                    "key": sequence.key,
                    "label": self.app.i18n.t(f"koch.sequence.{sequence.key}", sequence.label),
                    "current": current,
                    "total": total,
                }
            )

        all_unlocked = any(
            int(item.get("current", 0) or 0) >= int(item.get("total", 1) or 1)
            for item in items
        )
        if all_unlocked:
            for item in items:
                item["all_unlocked"] = True

        return items

    def collect_settings(self, window: "KochWindow") -> KochSettings:
        raw = {**window.collect_settings(), **self.advanced_settings_data()}
        settings = KochSettings(**raw).normalized()

        if settings.mode == "guided":
            stage = self.progress_stage_for_sequence(settings.sequence_key)
            settings = KochSettings(**{**raw, "stage_index": stage}).normalized()

        return self.settings_with_target_minimum(settings)

    def refresh_window_state(self, window: "KochWindow") -> None:
        try:
            service = self.ensure_service()
            settings = self.collect_settings(window)
            target_minimum = self.minimum_target_chars_for_settings(settings)
            window.set_stage_bounds(len(koch_sequence_by_key(settings.sequence_key).characters))
            if window.set_target_chars_minimum(target_minimum):
                self.target_chars_var.set(int(window.target_chars_var.get()))
                settings = self.collect_settings(window)
            window.update_character_grid(settings)
            window.update_progress_summary(settings)
            window.load_recent_sessions(service.recent_sessions(limit=25))
            window.load_character_stats(service.character_stats(recent_sessions=1000, limit=50))
            window.update_skill_summary(
                service.skill_summary(),
                self.koch_sequence_progress_items(service),
            )
        except Exception as exc:
            log_app_exception(
                "app.koch.refresh_failed",
                exc,
                level="warning",
                message="Koch window refresh failed.",
            )

    def start_session(self, window: "KochWindow") -> None:
        if self.practice_active:
            return

        try:
            settings = self.collect_settings(window)
            service = self.ensure_service()
            target, _active_chars = service.create_target(settings)
        except Exception as exc:
            log_app_exception(
                "app.koch.start_failed",
                exc,
                level="warning",
                message="Koch practice could not be started.",
            )
            messagebox.showerror(
                config.APP_NAME,
                self.app.i18n.t(
                    "koch.message.start_failed",
                    "Koch practice could not be started:\n\n{error}",
                    error=str(exc),
                ),
            )
            return

        countdown_seconds = int(getattr(config, "DEFAULT_KOCH_COUNTDOWN_SECONDS", 5))
        self.current_target = target
        self.current_target_schedule = []
        self.current_settings = settings
        self.typed_events = []
        self.started_at = None
        self.started_monotonic = None
        self.practice_active = False

        try:
            self.current_target_schedule = self.playback.prepare(target=target, settings=settings)
        except Exception as exc:
            self.current_target_schedule = []
            log_app_exception(
                "app.koch.prepare_playback_failed",
                exc,
                level="warning",
                message="Koch playback pre-render failed; rendering will be retried at playback start.",
            )

        window.prepare_for_countdown(target=target, settings=settings, seconds=countdown_seconds)
        window.start_countdown(
            countdown_seconds,
            lambda: self._begin_playback(window, target=target, settings=settings),
        )

    def _begin_playback(self, window: "KochWindow", *, target: str, settings: KochSettings) -> None:
        if not self.current_target:
            return

        self.typed_events = []
        self.started_at = None
        self.started_monotonic = None
        self.practice_active = False
        self.current_settings = settings

        window.prepare_for_session(target=target, settings=settings)

        self._playback_callback_token += 1
        callback_token = self._playback_callback_token

        def _started_on_main_thread() -> None:
            self.started_at = datetime.now()
            self.started_monotonic = time.monotonic()
            self.practice_active = True

        def _finished_on_main_thread() -> None:
            score_delay_ms = max(0, int(settings.auto_score_delay_ms))

            def _score_if_current_session() -> None:
                if callback_token != self._playback_callback_token:
                    return
                self.score_session(window, automatic=True)

            self.app.after(score_delay_ms, _score_if_current_session)

        def _started() -> None:
            self._queue_playback_callback(callback_token, _started_on_main_thread)

        def _finished() -> None:
            self._queue_playback_callback(callback_token, _finished_on_main_thread)

        self._start_playback_callback_poll()

        try:
            self.current_target_schedule = self.playback.start(
                target=target,
                settings=settings,
                on_finished=_finished,
                on_started=_started,
            )
        except Exception as exc:
            self.practice_active = False
            log_app_exception(
                "app.koch.playback_failed",
                exc,
                level="warning",
                message="Koch playback failed.",
            )
            messagebox.showerror(
                config.APP_NAME,
                self.app.i18n.t(
                    "koch.message.playback_failed",
                    "Koch playback failed:\n\n{error}",
                    error=str(exc),
                ),
            )
            window.reset_after_stopped()
            return

        log_app_event(
            "app.koch.started",
            message="Koch receive practice started.",
            context={
                "sequence_key": settings.sequence_key,
                "stage_index": settings.stage_index,
                "target_chars": settings.target_chars,
                "minimum_target_chars": self.minimum_target_chars_for_settings(settings),
                "character_wpm": settings.character_wpm,
                "effective_wpm": settings.effective_wpm,
            },
        )

    def stop_session(self) -> None:
        try:
            self.playback.stop()
        except Exception:
            pass

        self._playback_callback_token += 1
        self.practice_active = False
        self.current_settings = None
        self.current_target = ""
        self.current_target_schedule = []

    def record_typed_character(self, key: str, char: str) -> None:
        if not self.practice_active or self.started_monotonic is None:
            return

        typed_at_ms = int(round((time.monotonic() - self.started_monotonic) * 1000.0))
        self.typed_events.append(
            {
                "key": str(key or ""),
                "char": str(char or "").upper(),
                "typed_at_ms": typed_at_ms,
            }
        )

    def pop_last_typed_character(self) -> None:
        if self.typed_events:
            self.typed_events.pop()

    def score_session(self, window: "KochWindow", *, automatic: bool = False) -> None:
        if not self.practice_active and automatic:
            return

        if not self.current_target:
            return

        if self.started_at is None:
            self.started_at = datetime.now()
            self.started_monotonic = time.monotonic()

        settings = self.current_settings or self.collect_settings(window)

        self.playback.stop()
        self._playback_callback_token += 1
        self.practice_active = False
        self.current_settings = None

        finished_at = datetime.now()
        entered = window.entered_text()

        try:
            session_id, result = self.ensure_service().score_session(
                started_at=self.started_at,
                finished_at=finished_at,
                target=self.current_target,
                entered=entered,
                settings=settings,
                typed_events=list(self.typed_events),
                target_schedule=list(self.current_target_schedule),
            )
        except Exception as exc:
            log_app_exception(
                "app.koch.score_failed",
                exc,
                level="warning",
                message="Koch practice scoring failed.",
            )
            messagebox.showerror(
                config.APP_NAME,
                self.app.i18n.t(
                    "koch.message.save_failed",
                    "Koch result could not be saved:\n\n{error}",
                    error=str(exc),
                ),
            )
            return

        window.show_result(session_id, result)
        self.refresh_window_state(window)

        if result.passed:
            self.app.audio_controller.play_sound("level_up")

        log_app_event(
            "app.koch.scored",
            message="Koch receive practice scored.",
            context={
                "session_id": session_id,
                "passed": bool(result.passed),
                "accuracy": result.accuracy,
                "stage_index": result.stage_index,
                "advanced_to_stage": result.advanced_to_stage,
            },
        )
