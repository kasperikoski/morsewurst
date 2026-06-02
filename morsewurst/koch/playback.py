# ============================================================
# morsewurst/koch/playback.py
# ============================================================

from __future__ import annotations

import os
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Callable

from morsewurst.core.scoring import CHAR_TO_MORSE
from morsewurst.koch.models import KochSettings
from morsewurst.koch.schedule import koch_timing_ms, make_koch_target_schedule, schedule_duration_ms
from morsewurst.koch.tone_renderer import koch_background_noise_lead_in_ms, render_koch_wave_file

try:
    import winsound
except ImportError:  # pragma: no cover - platform dependent
    winsound = None


def _make_temp_wave_path() -> str:
    handle = tempfile.NamedTemporaryFile(prefix="morsewurst_koch_", suffix=".wav", delete=False)
    try:
        return handle.name
    finally:
        handle.close()


@dataclass
class _PreparedKochWave:
    target: str
    settings: KochSettings
    schedule: list[dict[str, int | str]]
    temp_path: str
    ready_event: threading.Event
    error: Exception | None = None
    claimed: bool = False
    discarded: bool = False


class KochPlayback:
    """Threaded Koch playback using a clean rendered PCM sine-wave drill.

    On Windows the rendered WAV is started with SND_ASYNC and the worker thread
    only watches timing/stop state. That keeps the Tk UI responsive when the
    user cancels the practice during playback.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._temp_wave_path: str | None = None
        self._prepared_wave: _PreparedKochWave | None = None

    @property
    def running(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def stop(self, *, discard_prepared: bool = True) -> None:
        self._stop_event.set()
        if winsound is not None:
            try:
                winsound.PlaySound(None, 0)
            except Exception:
                pass

        if discard_prepared:
            with self._lock:
                self._discard_prepared_wave_locked()

    def prepare(self, *, target: str, settings: KochSettings) -> list[dict[str, int | str]]:
        """Begin rendering the Koch WAV in the background.

        This is called at the start of the countdown. If rendering finishes
        before the countdown ends, playback can start immediately while still
        keeping the intentional radio-noise lead-in inside the WAV.
        """

        normalized = settings.normalized()
        schedule = make_koch_target_schedule(target, normalized)

        if winsound is None:
            return schedule

        prepared = _PreparedKochWave(
            target=str(target or ""),
            settings=normalized,
            schedule=schedule,
            temp_path=_make_temp_wave_path(),
            ready_event=threading.Event(),
        )

        with self._lock:
            self._discard_prepared_wave_locked()
            self._prepared_wave = prepared

        thread = threading.Thread(
            target=self._render_prepared_wave,
            args=(prepared,),
            daemon=True,
        )
        thread.start()

        return schedule

    def start(
        self,
        *,
        target: str,
        settings: KochSettings,
        on_finished: Callable[[], None] | None = None,
        on_started: Callable[[], None] | None = None,
    ) -> list[dict[str, int | str]]:
        self.stop(discard_prepared=False)

        with self._lock:
            self._stop_event = threading.Event()
            normalized = settings.normalized()
            prepared = self._claim_prepared_wave_locked(target=str(target or ""), settings=normalized)
            schedule = prepared.schedule if prepared is not None else make_koch_target_schedule(target, normalized)
            thread = threading.Thread(
                target=self._run,
                args=(target, normalized, schedule, self._stop_event, on_finished, on_started, prepared),
                daemon=True,
            )
            self._thread = thread
            thread.start()

        return schedule

    def _discard_prepared_wave_locked(self) -> None:
        prepared = self._prepared_wave
        self._prepared_wave = None

        if prepared is None:
            return

        prepared.discarded = True
        try:
            os.remove(prepared.temp_path)
        except OSError:
            pass

    def _claim_prepared_wave_locked(
        self,
        *,
        target: str,
        settings: KochSettings,
    ) -> _PreparedKochWave | None:
        prepared = self._prepared_wave

        if prepared is None:
            return None

        if prepared.target != target or prepared.settings != settings:
            self._discard_prepared_wave_locked()
            return None

        prepared.claimed = True
        self._prepared_wave = None
        return prepared

    def _render_prepared_wave(self, prepared: _PreparedKochWave) -> None:
        try:
            render_koch_wave_file(prepared.temp_path, prepared.target, prepared.settings)
        except Exception as exc:
            prepared.error = exc
        finally:
            prepared.ready_event.set()

        with self._lock:
            should_delete = bool(
                prepared.discarded
                or (not prepared.claimed and self._prepared_wave is not prepared)
            )

        if should_delete:
            try:
                os.remove(prepared.temp_path)
            except OSError:
                pass

    def _wait_for_prepared_wave(
        self,
        prepared: _PreparedKochWave,
        stop_event: threading.Event,
    ) -> bool:
        while not prepared.ready_event.is_set():
            if stop_event.is_set():
                prepared.discarded = True
                return False
            prepared.ready_event.wait(0.02)

        if stop_event.is_set():
            prepared.discarded = True
            return False

        return True

    def _sleep_ms(self, ms: float, stop_event: threading.Event) -> None:
        end = time.perf_counter() + (max(0.0, ms) / 1000.0)

        while not stop_event.is_set():
            remaining = end - time.perf_counter()
            if remaining <= 0:
                return
            time.sleep(min(0.02, remaining))

    def _fallback_silent_playback(
        self,
        target: str,
        settings: KochSettings,
        stop_event: threading.Event,
        on_started: Callable[[], None] | None = None,
    ) -> None:
        timing = koch_timing_ms(settings)
        element_unit_ms = timing["element_unit_ms"]
        element_gap_ms = timing["element_gap_ms"]
        char_gap_ms = timing["char_gap_ms"]
        word_gap_ms = timing["word_gap_ms"]

        previous_symbol = False
        pending_word_gap = False

        if on_started is not None and not stop_event.is_set():
            on_started()

        for raw_char in str(target or "").upper():
            if stop_event.is_set():
                return

            if raw_char.isspace():
                if previous_symbol:
                    pending_word_gap = True
                continue

            code = CHAR_TO_MORSE.get(raw_char)
            if not code:
                continue

            if previous_symbol:
                self._sleep_ms(word_gap_ms if pending_word_gap else char_gap_ms, stop_event)

            for index, element in enumerate(code):
                if stop_event.is_set():
                    return
                if index > 0:
                    self._sleep_ms(element_gap_ms, stop_event)
                duration = element_unit_ms if element == "." else 3.0 * element_unit_ms
                self._sleep_ms(duration, stop_event)

            previous_symbol = True
            pending_word_gap = False

    def _play_rendered_wave(
        self,
        target: str,
        settings: KochSettings,
        schedule: list[dict[str, int | str]],
        stop_event: threading.Event,
        on_started: Callable[[], None] | None = None,
        prepared: _PreparedKochWave | None = None,
    ) -> None:
        if winsound is None:
            self._fallback_silent_playback(target, settings, stop_event, on_started)
            return

        temp_path: str | None = None
        duration_ms = schedule_duration_ms(schedule)

        try:
            if prepared is not None:
                if not self._wait_for_prepared_wave(prepared, stop_event):
                    return
                if prepared.error is None:
                    temp_path = prepared.temp_path
                else:
                    try:
                        os.remove(prepared.temp_path)
                    except OSError:
                        pass
                    temp_path = _make_temp_wave_path()
                    render_koch_wave_file(temp_path, target, settings)
            else:
                temp_path = _make_temp_wave_path()
                render_koch_wave_file(temp_path, target, settings)

            self._temp_wave_path = temp_path

            if stop_event.is_set():
                return

            lead_in_ms = koch_background_noise_lead_in_ms()
            winsound.PlaySound(temp_path, winsound.SND_FILENAME | winsound.SND_ASYNC)

            if lead_in_ms > 0.0:
                self._sleep_ms(lead_in_ms, stop_event)

            if on_started is not None and not stop_event.is_set():
                on_started()

            remaining_ms = max(0.0, float(duration_ms))
            self._sleep_ms(remaining_ms + 80, stop_event)
        finally:
            try:
                winsound.PlaySound(None, 0)
            except Exception:
                pass
            if temp_path is not None and self._temp_wave_path == temp_path:
                self._temp_wave_path = None
            if temp_path is not None:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _run(
        self,
        target: str,
        settings: KochSettings,
        schedule: list[dict[str, int | str]],
        stop_event: threading.Event,
        on_finished: Callable[[], None] | None,
        on_started: Callable[[], None] | None,
        prepared: _PreparedKochWave | None,
    ) -> None:
        self._play_rendered_wave(target, settings, schedule, stop_event, on_started, prepared)

        if on_finished is not None and not stop_event.is_set():
            on_finished()
