# ============================================================
# morsewurst/ui/controllers/scratchpad_controller.py
# ============================================================

from __future__ import annotations

import time
from collections import Counter
from typing import TYPE_CHECKING, Any, Optional

import morsewurst.config as config
from morsewurst.core.app_logging import log_app_event, log_app_exception
from morsewurst.core.scoring import paris_wpm_for_text
from morsewurst.core.telemetry import (
    derive_tone_from_key_pair,
    key_event_identity,
    normalize_key_event,
)

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class ScratchpadController:
    """Owns the live free-copy Scratchpad session.

    The Scratchpad is intentionally memory-only. It keeps raw key/tone events,
    decoded text and session statistics in RAM while the window is open. The
    only persistent data written to ui_settings.json is window/display state.
    """

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app
        self.live_decoder: Any | None = None
        self.events: list[dict[str, Any]] = []
        self.active_key_events: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
        self.accepted_tone_keys: set[tuple[str, int, int, str, str, str, str]] = set()
        self.source_counts: Counter[str] = Counter()
        self.session_started_monotonic: float | None = None
        self.first_tone_t0_us: int | None = None
        self.last_activity_t1_us: int | None = None
        self.committed_char_info_count = 0
        self.committed_decoded_text = ""
        self.last_decoded_text = ""
        self.last_pending_symbol = ""
        self.last_source = ""
        self.last_current_wpm: float | None = None
        self.unknown_count = 0
        self.paused = False
        self._refresh_after_id: str | None = None

    # ------------------------------------------------------------
    # Mode lifecycle and saved window settings
    # ------------------------------------------------------------

    def is_active(self) -> bool:
        """Return True when the Scratchpad window exists and owns Morse input."""
        if str(getattr(self.app, "active_mode", "main") or "main") == "scratchpad":
            return True

        window = getattr(self.app, "scratchpad_window", None)
        if window is None:
            return False

        try:
            return bool(window.winfo_exists())
        except Exception:
            return True

    def enter_mode(self) -> None:
        self.reset_session(clear_window=False)
        self.paused = False
        self.app.active_mode = "scratchpad"
        self.app.start_trigger_timestamps.clear()
        self.app.practice_controller.update_practice_buttons()
        self.app.status_controller.set_main_status(
            self.app.i18n.t(
                "scratchpad.status.active",
                "Scratchpad is active. Morse input is routed to the Scratchpad.",
            ),
            state="normal",
        )
        self.start_refresh_timer()
        log_app_event(
            "app.scratchpad.entered",
            message="Scratchpad mode entered.",
        )

    def leave_mode(self) -> None:
        self.stop_refresh_timer()
        self.active_key_events.clear()
        if str(getattr(self.app, "active_mode", "main") or "main") == "scratchpad":
            self.app.active_mode = "main"
        self.app.start_trigger_timestamps.clear()
        self.app.practice_controller.update_practice_buttons()
        self.app.status_controller.set_main_status(
            self.app.i18n.t(
                "scratchpad.status.closed",
                "Scratchpad closed.",
            ),
            state="normal",
        )
        log_app_event(
            "app.scratchpad.closed",
            message="Scratchpad mode closed.",
        )

    def default_window_geometry(self) -> str:
        return str(getattr(config, "UI_SCRATCHPAD_WINDOW_GEOMETRY", "800x600"))

    def window_geometry(self) -> str:
        try:
            value = str(self.app.scratchpad_window_geometry_var.get() or "").strip()
        except Exception:
            value = ""
        return value or self.default_window_geometry()

    def remember_window_geometry(self, geometry: str) -> None:
        geometry = str(geometry or "").strip()
        if not geometry:
            return
        try:
            self.app.scratchpad_window_geometry_var.set(geometry)
        except Exception:
            pass

    def remember_raw_panel_visible(self, visible: bool) -> None:
        try:
            self.app.scratchpad_raw_panel_visible_var.set(bool(visible))
        except Exception:
            pass
        try:
            self.app.settings_controller.save_ui_settings_async()
        except Exception:
            pass

    # ------------------------------------------------------------
    # Session data and text/statistics
    # ------------------------------------------------------------

    def reset_session(self, *, clear_window: bool = True) -> None:
        """Clear all in-memory Scratchpad telemetry and decoded session data."""
        self.live_decoder = self.app.decoder_controller.new_live_decoder(target_text="")
        self.events.clear()
        self.active_key_events.clear()
        self.accepted_tone_keys.clear()
        self.source_counts.clear()
        self.session_started_monotonic = None
        self.first_tone_t0_us = None
        self.last_activity_t1_us = None
        self.committed_char_info_count = 0
        self.committed_decoded_text = ""
        self.last_decoded_text = ""
        self.last_pending_symbol = ""
        self.last_source = ""
        self.last_current_wpm = None
        self.unknown_count = 0

        window = getattr(self.app, "scratchpad_window", None)
        if window is not None:
            try:
                window.refresh_from_controller()
                if clear_window:
                    window.clear_text(keep_session=True)
            except Exception:
                pass

    def clear_text_and_session(self) -> None:
        self.reset_session(clear_window=False)
        window = getattr(self.app, "scratchpad_window", None)
        if window is not None:
            try:
                window.clear_text(keep_session=True)
                window.refresh_from_controller()
            except Exception:
                pass

    def reset_stats_only(self) -> None:
        """Reset timing statistics without deleting the visible note text."""
        self.events.clear()
        self.active_key_events.clear()
        self.accepted_tone_keys.clear()
        self.source_counts.clear()
        self.session_started_monotonic = None
        self.first_tone_t0_us = None
        self.last_activity_t1_us = None
        self.committed_char_info_count = 0
        self.committed_decoded_text = ""
        self.last_decoded_text = ""
        self.last_pending_symbol = ""
        self.last_source = ""
        self.last_current_wpm = None
        self.unknown_count = 0
        self.live_decoder = self.app.decoder_controller.new_live_decoder(target_text="")
        self.refresh_window()

    def toggle_paused(self) -> None:
        self.paused = not self.paused
        self.active_key_events.clear()
        self.app.input_controller.cancel_keyboard_morse_press()
        self.refresh_window()
        self.app.status_controller.set_main_status(
            self.app.i18n.t(
                "scratchpad.status.paused" if self.paused else "scratchpad.status.resumed",
                "Scratchpad input paused." if self.paused else "Scratchpad input resumed.",
            ),
            state="normal",
        )

    def text_content(self) -> str:
        window = getattr(self.app, "scratchpad_window", None)
        if window is None:
            return ""
        try:
            return window.text_content()
        except Exception:
            return ""

    def stats(self) -> dict[str, Any]:
        text = self.text_content()
        chars = len(text)
        words = len([part for part in text.split() if part])
        elapsed_seconds = self.elapsed_seconds()

        return {
            "chars": chars,
            "words": words,
            "elapsed_seconds": elapsed_seconds,
            "avg_wpm": self.average_wpm(elapsed_seconds),
            "current_wpm": self.last_current_wpm,
            "pending": self.last_pending_symbol,
            "source": self.source_label(),
            "unknown": self.unknown_count,
            "tones": len(self.events),
            "paused": self.paused,
        }

    def elapsed_seconds(self) -> float:
        """Return active sending time, not wall-clock idle time.

        This keeps the average WPM stable after the last decoded character
        instead of letting it drift downward while the user pauses.
        """
        if self.first_tone_t0_us is None or self.last_activity_t1_us is None:
            return 0.0
        return max(
            0.0,
            (float(self.last_activity_t1_us) - float(self.first_tone_t0_us)) / 1_000_000.0,
        )

    def average_wpm(self, elapsed_seconds: float) -> float | None:
        if elapsed_seconds <= 0.0:
            return None
        text = self.committed_decoded_text.strip()
        if not text:
            return None
        try:
            return float(paris_wpm_for_text(text, elapsed_us=int(elapsed_seconds * 1_000_000)))
        except Exception:
            return None

    def source_label(self) -> str:
        active_sources = [source for source, count in self.source_counts.items() if count > 0]
        if not active_sources:
            return "-"
        if len(active_sources) > 1:
            return "mixed"
        return active_sources[0]

    # ------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------

    def handle_key_event(self, event: dict[str, Any]) -> None:
        """Handle one V1 key down/up event without touching the practice round."""
        if self.paused:
            return

        try:
            clean = normalize_key_event(event)
        except Exception as exc:
            log_app_exception(
                "app.scratchpad.invalid_key_event",
                exc,
                level="warning",
                message="Invalid Scratchpad key event was ignored.",
                context={"event_type": event.get("type")},
            )
            return

        now = time.time()
        clean.setdefault("_host_received_time", now)
        clean["_host_processed_time"] = now

        state = str(clean.get("state") or "")
        identity = key_event_identity(clean)

        if state == "down":
            # Some devices and operating systems can repeat a down event while
            # the key is already held. Do not overwrite the original down time,
            # because that turns one long press into a short bogus dot.
            if identity in self.active_key_events:
                self.refresh_window()
                return

            self.active_key_events[identity] = clean
            self._ensure_session_started(clean.get("t"))
            self.refresh_window()
            return

        down_event = self.active_key_events.pop(identity, None)
        if down_event is None:
            self.refresh_window()
            return

        tone = derive_tone_from_key_pair(down_event, clean)
        if tone is None:
            self.refresh_window()
            return

        self.handle_tone_event(tone)

    def handle_tone_event(self, event: dict[str, Any]) -> None:
        """Handle one completed tone event in the Scratchpad session."""
        if self.paused:
            return

        if event.get("type") != "tone":
            return

        now = time.time()
        tone = dict(event)
        tone.setdefault("_host_received_time", now)
        tone["_host_processed_time"] = now

        try:
            t0 = int(tone.get("t0"))
            t1 = int(tone.get("t1"))
        except Exception:
            return

        if t1 <= t0:
            return

        tone["t0"] = t0
        tone["t1"] = t1
        tone["dur"] = float(t1 - t0)

        if not self._accept_tone_duration(tone):
            self.refresh_window()
            return

        tone_key = self._tone_key(tone)
        if tone_key in self.accepted_tone_keys:
            self.refresh_window()
            return
        self.accepted_tone_keys.add(tone_key)

        self._ensure_session_started(t0)
        if self.first_tone_t0_us is None:
            self.first_tone_t0_us = t0
        self.last_activity_t1_us = max(int(self.last_activity_t1_us or t1), t1)

        self.events.append(tone)
        self.events.sort(key=lambda item: (int(item.get("t0", 0)), int(item.get("t1", 0))))
        self.source_counts[self._source_from_event(tone)] += 1

        if self.live_decoder is None:
            self.live_decoder = self.app.decoder_controller.new_live_decoder(target_text="")
        self.live_decoder.replace_events(self.events)

        self.decode_and_append(force=True)

    def _accept_tone_duration(self, tone: dict[str, Any]) -> bool:
        try:
            duration_us = int(tone["t1"]) - int(tone["t0"])
        except Exception:
            return False

        if self.app.input_controller.is_keyboard_morse_tone_event(tone):
            min_tone_us = int(getattr(config, "KEYBOARD_MORSE_MIN_TONE_US", 1_000))
            return duration_us >= min_tone_us

        if tone.get("src") == "straight" and tone.get("_derived_from") == "v1_key_down_up":
            min_tone_us = int(getattr(config, "SERIAL_STRAIGHT_KEY_MIN_TONE_US", 10_000))
            if duration_us < min_tone_us:
                log_app_event(
                    "app.scratchpad.v1_straight_key_bounce_ignored",
                    message="Very short Scratchpad straight-key V1 pulse was ignored as a derived decoder tone.",
                    context={
                        "duration_us": duration_us,
                        "min_tone_us": min_tone_us,
                        "src": tone.get("src"),
                    },
                )
                return False

        return True

    # ------------------------------------------------------------
    # Live decoding and refresh
    # ------------------------------------------------------------

    def start_refresh_timer(self) -> None:
        self.stop_refresh_timer()
        self.schedule_refresh_timer()

    def schedule_refresh_timer(self) -> None:
        if not self.is_active():
            return
        try:
            interval_ms = int(getattr(config, "UI_SCRATCHPAD_LIVE_REFRESH_MS", 80))
            self._refresh_after_id = self.app.after(max(20, interval_ms), self.refresh_tick)
        except Exception:
            self._refresh_after_id = None

    def stop_refresh_timer(self) -> None:
        if self._refresh_after_id is None:
            return
        try:
            self.app.after_cancel(self._refresh_after_id)
        except Exception:
            pass
        self._refresh_after_id = None

    def refresh_tick(self) -> None:
        self._refresh_after_id = None
        try:
            self.decode_and_append(force=False)
        finally:
            self.schedule_refresh_timer()

    def decode_and_append(self, *, force: bool = False) -> None:
        if self.live_decoder is None:
            self.refresh_window()
            return

        current_time_us = self.current_device_time_us()
        try:
            decoded = self.live_decoder.decode(
                current_time_us=current_time_us,
                flush_final=False,
                settings=self.app.decoder_controller.decoder_settings_from_ui(),
                seed_unit_us=self.app.decoder_controller.adaptive_seed_unit_us(),
                target_text="",
            )
        except Exception as exc:
            log_app_exception(
                "app.scratchpad.decode_failed",
                exc,
                level="warning",
                message="Scratchpad live decode failed.",
            )
            return

        text = str(getattr(decoded, "text", "") or "")
        pending = str(getattr(decoded, "pending_symbol", "") or "")
        infos = list(getattr(decoded, "char_infos", []) or [])
        delta = ""

        if len(infos) < self.committed_char_info_count:
            # Adaptive decoding can very rarely re-segment early live output.
            # In a free editable notepad we must never append the whole decoded
            # string again, because that duplicates large text blocks. Keep the
            # visible text untouched and resume committing from the current end.
            self.committed_char_info_count = len(infos)

        if len(infos) > self.committed_char_info_count:
            new_infos = infos[self.committed_char_info_count:]
            delta = "".join(str(info.get("ch") or "") for info in new_infos)
            self.committed_char_info_count = len(infos)

        self.committed_decoded_text = "".join(
            str(info.get("ch") or "")
            for info in infos[: self.committed_char_info_count]
        )
        self.last_decoded_text = text
        self.last_pending_symbol = pending
        self._update_last_character_stats(decoded)

        if delta:
            window = getattr(self.app, "scratchpad_window", None)
            if window is not None:
                try:
                    window.insert_decoded_text(delta)
                except Exception as exc:
                    log_app_exception(
                        "app.scratchpad.text_insert_failed",
                        exc,
                        level="warning",
                        message="Decoded Scratchpad text could not be inserted.",
                    )
            self.app.status_controller.set_main_status(
                self.app.i18n.t(
                    "scratchpad.status.receiving",
                    "Scratchpad receiving Morse input.",
                ),
                state="normal",
            )

        if force or delta or pending:
            self.refresh_window()

    def current_device_time_us(self) -> Optional[int]:
        candidates: list[dict[str, Any]] = []

        for event in self.events:
            if event.get("type") == "tone" and isinstance(event.get("t1"), int):
                candidates.append({"t": int(event["t1"]), "_host_received_time": event.get("_host_received_time")})

        for event in self.active_key_events.values():
            if isinstance(event, dict) and isinstance(event.get("t"), int):
                candidates.append({"t": int(event["t"]), "_host_received_time": event.get("_host_received_time")})

        if not candidates:
            return None

        last_event = max(candidates, key=lambda item: int(item["t"]))
        host_received = last_event.get("_host_received_time")
        if not isinstance(host_received, (int, float)):
            return int(last_event["t"])

        elapsed_us = max(0, int((time.time() - float(host_received)) * 1_000_000))
        return int(last_event["t"]) + elapsed_us

    def _update_last_character_stats(self, decoded: Any) -> None:
        infos = list(getattr(decoded, "char_infos", []) or [])
        committed_infos = infos[: self.committed_char_info_count]
        unknown_char = str(getattr(config, "DECODER_UNKNOWN_CHAR", "�"))
        self.unknown_count = sum(
            1 for info in committed_infos if str(info.get("ch") or "") == unknown_char
        )

        element_infos = list(getattr(decoded, "element_infos", []) or [])
        if element_infos:
            last_element = element_infos[-1]
            self.last_source = self._source_from_info(last_element)
            try:
                wpm = float(last_element.get("wpm"))
            except Exception:
                wpm = None
            if wpm and wpm > 0:
                self.last_current_wpm = wpm

        for info in reversed(committed_infos):
            ch = str(info.get("ch") or "")
            if not ch or ch.isspace():
                continue
            self.last_source = self._source_from_info(info)
            try:
                wpm = float(info.get("wpm"))
            except Exception:
                wpm = None
            if wpm and wpm > 0:
                self.last_current_wpm = wpm
            return

    def refresh_window(self) -> None:
        window = getattr(self.app, "scratchpad_window", None)
        if window is None:
            return
        try:
            window.refresh_from_controller()
        except Exception:
            pass

    # ------------------------------------------------------------
    # Raw telemetry helpers
    # ------------------------------------------------------------

    def raw_tone_events(self) -> list[dict[str, Any]]:
        """Return closed and currently open tones for the Scratchpad canvas."""
        tones = [
            dict(event)
            for event in self.events
            if event.get("type") == "tone"
            and isinstance(event.get("t0"), int)
            and isinstance(event.get("t1"), int)
            and isinstance(event.get("dur"), (int, float))
        ]

        current_time_us = self.current_device_time_us()
        for down_event in self.active_key_events.values():
            if not isinstance(down_event, dict):
                continue
            t0 = down_event.get("t")
            if not isinstance(t0, int):
                continue
            t1 = int(current_time_us if current_time_us is not None else t0)
            if t1 <= int(t0):
                t1 = int(t0) + 1
            live_tone = {
                "v": 1,
                "type": "tone",
                "src": down_event.get("src", "unknown"),
                "t0": int(t0),
                "t1": t1,
                "dur": float(t1 - int(t0)),
                "_open": True,
                "_derived_from": "v1_key_down_up",
            }
            for key in ("el", "unit", "wpm", "dit", "device", "mode", "key", "pin"):
                if key in down_event:
                    live_tone[key] = down_event.get(key)
            tones.append(live_tone)

        tones.sort(key=lambda event: (int(event["t0"]), int(event["t1"])))
        return tones

    def raw_telemetry_unit_us(self, current_time_us: Optional[int]) -> float:
        """Return the same style of visual unit used by the main raw telemetry."""
        try:
            if self.live_decoder is not None:
                live_state = self.live_decoder.current_state()
                if live_state.decoded is not None:
                    return max(20_000.0, float(live_state.decoded.visual_unit_us))

            decoded_for_scale = self.app.decoder_controller.decode_tone_events(
                self.events,
                current_time_us=current_time_us,
                flush_final=False,
                seed_unit_us=self.app.decoder_controller.adaptive_seed_unit_us(),
                target_text="",
            )
            return max(20_000.0, float(decoded_for_scale.visual_unit_us))
        except Exception:
            return 60_000.0

    # ------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------

    def _ensure_session_started(self, t_us: Any) -> None:
        if self.session_started_monotonic is None:
            self.session_started_monotonic = time.monotonic()
        try:
            if self.first_tone_t0_us is None and t_us is not None:
                self.first_tone_t0_us = int(t_us)
        except Exception:
            pass

    def _source_from_event(self, event: dict[str, Any]) -> str:
        if event.get("device") == "keyboard" or event.get("mode") == "keyboard_straight":
            return "keyboard"
        source = str(event.get("src") or "unknown").strip().lower()
        if source in {"straight", "iambic"}:
            return source
        return "unknown"

    def _source_from_info(self, info: dict[str, Any]) -> str:
        if info.get("device") == "keyboard" or info.get("mode") == "keyboard_straight":
            return "keyboard"
        source = str(info.get("source") or info.get("src") or "unknown").strip().lower()
        if source in {"straight", "iambic", "keyboard"}:
            return source
        return "unknown"

    def _tone_key(self, tone: dict[str, Any]) -> tuple[str, int, int, str, str, str, str]:
        return (
            str(tone.get("src") or "unknown"),
            int(tone.get("t0") or 0),
            int(tone.get("t1") or 0),
            str(tone.get("device") or ""),
            str(tone.get("mode") or ""),
            str(tone.get("key") or ""),
            str(tone.get("pin") or ""),
        )
