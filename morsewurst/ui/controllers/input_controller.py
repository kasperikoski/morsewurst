# ============================================================
# morsewurst/ui/controllers/input_controller.py
# ============================================================

from __future__ import annotations

import queue
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

import tkinter as tk

import morsewurst.config as config
from morsewurst.core.app_logging import log_app_event

KEYBOARD_MORSE_KEY_LABEL_KEYS = {
    "space": ("input.keyboard_key.space", "Space"),
    "Return": ("input.keyboard_key.enter", "Enter"),

    "Up": ("input.keyboard_key.up", "Arrow Up"),
    "Down": ("input.keyboard_key.down", "Arrow Down"),
    "Left": ("input.keyboard_key.left", "Arrow Left"),
    "Right": ("input.keyboard_key.right", "Arrow Right"),

    "Control_L": ("input.keyboard_key.left_ctrl", "Left Ctrl"),
    "Control_R": ("input.keyboard_key.right_ctrl", "Right Ctrl"),
    "Shift_L": ("input.keyboard_key.left_shift", "Left Shift"),
    "Shift_R": ("input.keyboard_key.right_shift", "Right Shift"),
    "Alt_L": ("input.keyboard_key.left_alt", "Left Alt"),
    "Alt_R": ("input.keyboard_key.right_alt", "Right Alt"),
}

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class InputController:
    """Owns HID input, keyboard Morse input and incoming tone event handling."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def keyboard_morse_key_label(self, key: str, fallback: str = "") -> str:
        key = str(key or "").strip()
        fallback = str(fallback or "").strip()

        label_data = KEYBOARD_MORSE_KEY_LABEL_KEYS.get(key)

        if label_data is None:
            return fallback or key

        label_key, default = label_data

        return self.app.i18n.t(label_key, default)

    def keyboard_morse_key_options(self) -> tuple[tuple[str, str], ...]:
        """Return user-facing keyboard Morse key options as label and Tkinter keysym pairs."""
        options = getattr(config, "KEYBOARD_MORSE_KEY_OPTIONS", ())

        if not options:
            return ((self.keyboard_morse_key_label("space", "Space"), "space"),)

        cleaned: list[tuple[str, str]] = []

        for item in options:
            try:
                label, key = item
            except Exception:
                continue

            label = str(label).strip()
            key = str(key).strip()

            if label and key:
                cleaned.append((self.keyboard_morse_key_label(key, label), key))

        return tuple(cleaned) or ((self.keyboard_morse_key_label("space", "Space"), "space"),)

    def keyboard_morse_key_labels(self) -> list[str]:
        """Return the visible names shown in the keyboard Morse dropdown."""
        return [label for label, _key in self.keyboard_morse_key_options()]

    def keyboard_morse_label_from_key(self, key: str) -> str:
        """Convert a stored Tkinter keysym into a user-facing dropdown label."""
        key = str(key or "").strip()

        for label, option_key in self.keyboard_morse_key_options():
            if option_key == key:
                return label

        return self.keyboard_morse_key_options()[0][0]

    def keyboard_morse_key_from_label(self, label: str) -> str:
        """Convert a user-facing dropdown label into a Tkinter keysym."""
        label = str(label or "").strip()

        for option_label, key in self.keyboard_morse_key_options():
            if option_label == label:
                return key

        return str(getattr(config, "KEYBOARD_MORSE_DEFAULT_KEY", "space"))

    def on_keyboard_morse_key_changed(self, _event: tk.Event | None = None) -> None:
        """Store the selected keyboard Morse key when the dropdown value changes."""
        app = self.app

        selected_label = str(app.keyboard_morse_key_label_var.get() or "").strip()
        selected_key = self.keyboard_morse_key_from_label(selected_label)

        old_key = str(app.keyboard_morse_key_var.get() or "")
        app.keyboard_morse_key_var.set(selected_key)
        self.cancel_keyboard_morse_press()
        if old_key != selected_key:
            log_app_event(
                "app.input.keyboard_morse_key_changed",
                message="Keyboard Morse key changed.",
                context={"old_key": old_key, "new_key": selected_key, "label": selected_label},
            )

        if self.keyboard_morse_enabled():
            app.status_controller.set_main_status(
                app.i18n.t(
                    "input.keyboard_morse.key_changed",
                    "Keyboard Morse key changed: {keyboard_key}.",
                    keyboard_key=selected_label,
                ),
                state="normal",
            )
            app.app_lifecycle_controller.focus_input(force=True)

    def keyboard_morse_enabled(self) -> bool:
        """Return True when computer keyboard Morse input is active."""
        try:
            return bool(self.app.keyboard_morse_enabled_var.get())
        except Exception:
            return False

    def keyboard_morse_expected_key(self) -> str:
        """Return the Tkinter keysym used as the virtual straight key."""
        app = self.app

        key = str(app.keyboard_morse_key_var.get() or "").strip()

        if not key:
            key = self.keyboard_morse_key_from_label(
                str(app.keyboard_morse_key_label_var.get() or "")
            )

        if not key:
            key = str(getattr(config, "KEYBOARD_MORSE_DEFAULT_KEY", "space"))

        return key or "space"

    def is_keyboard_morse_key_event(self, event: tk.Event) -> bool:
        """Check whether this key event belongs to the selected virtual straight key."""
        if not self.keyboard_morse_enabled():
            return False

        return str(getattr(event, "keysym", "")) == self.keyboard_morse_expected_key()

    def keyboard_morse_now_us(self) -> int:
        """Return a stable app-local timestamp in microseconds for virtual tone events."""
        return max(
            0,
            int((time.monotonic() - self.app.keyboard_morse_time_base) * 1_000_000),
        )

    def is_keyboard_morse_tone_event(self, event: Dict[str, Any]) -> bool:
        """Return True when a tone event was generated by the computer keyboard."""
        return (
            event.get("type") == "tone"
            and event.get("device") == "keyboard"
            and event.get("mode") == "keyboard_straight"
        )

    def make_keyboard_morse_tone_event(
        self,
        *,
        t0_us: int,
        t1_us: int,
        key: str,
    ) -> Dict[str, Any]:
        """Build a normal straight-key tone event from one keyboard press and release."""
        duration_us = max(0, int(t1_us) - int(t0_us))

        return {
            "type": "tone",
            "src": "straight",
            "t0": int(t0_us),
            "t1": int(t1_us),
            "dur": float(duration_us),
            "device": "keyboard",
            "mode": "keyboard_straight",
            "key": str(key),
        }

    def cancel_keyboard_morse_press(self) -> None:
        """Forget an unfinished keyboard press without emitting a tone event."""
        app = self.app

        app.keyboard_morse_pressed = False
        app.keyboard_morse_press_t0_us = None
        app.keyboard_morse_press_key = ""

    def handle_keyboard_morse_key_press(self, event: tk.Event) -> bool:
        """Start one virtual straight-key tone when the selected keyboard key is pressed."""
        app = self.app

        if not self.is_keyboard_morse_key_event(event):
            return False

        self.apply_keyboard_morse_setting_constraints(show_status=False)

        if app.keyboard_morse_pressed:
            return True

        app.keyboard_morse_pressed = True
        app.keyboard_morse_press_t0_us = self.keyboard_morse_now_us()
        app.keyboard_morse_press_key = str(getattr(event, "keysym", ""))

        return True

    def handle_keyboard_morse_key_release(self, event: tk.Event) -> bool:
        """Finish one virtual straight-key tone and feed it into the normal tone pipeline."""
        app = self.app

        if not self.is_keyboard_morse_key_event(event):
            return False

        if not app.keyboard_morse_pressed or app.keyboard_morse_press_t0_us is None:
            self.cancel_keyboard_morse_press()
            return True

        t0_us = int(app.keyboard_morse_press_t0_us)
        t1_us = self.keyboard_morse_now_us()
        key = app.keyboard_morse_press_key or str(getattr(event, "keysym", ""))

        self.cancel_keyboard_morse_press()

        min_tone_us = int(getattr(config, "KEYBOARD_MORSE_MIN_TONE_US", 1_000))
        if t1_us - t0_us < min_tone_us:
            return True

        tone_event = self.make_keyboard_morse_tone_event(
            t0_us=t0_us,
            t1_us=t1_us,
            key=key,
        )

        self.handle_serial_event(tone_event)
        return True

    def on_input_key_press(self, event: tk.Event) -> Optional[str]:
        """Route key presses either to keyboard Morse or to the existing HID input."""
        if self.handle_keyboard_morse_key_press(event):
            return "break"

        return None

    def on_input_key_release(self, event: tk.Event) -> Optional[str]:
        """Route key releases either to keyboard Morse or to the existing HID input."""
        if self.handle_keyboard_morse_key_release(event):
            return "break"

        self.on_hid_key_release(event)
        return None
    
    def on_global_keyboard_morse_key_press(self, event: tk.Event) -> Optional[str]:
        """Handle keyboard Morse key presses regardless of which app window has focus."""
        if self.handle_keyboard_morse_key_press(event):
            return "break"

        return None

    def on_global_keyboard_morse_key_release(self, event: tk.Event) -> Optional[str]:
        """Handle keyboard Morse key releases regardless of which app window has focus.

        This global handler must not call on_hid_key_release(), because normal
        HID text input belongs only to the hidden main input field.
        """
        if self.handle_keyboard_morse_key_release(event):
            return "break"

        return None

    def apply_keyboard_morse_setting_constraints(self, *, show_status: bool = True) -> None:
        """Keep keyboard Morse mode in a safe telemetry-based configuration."""
        app = self.app

        if not self.keyboard_morse_enabled():
            return

        changed = False

        if not app.use_telemetry_as_truth_var.get():
            app.use_telemetry_as_truth_var.set(True)
            changed = True

        if app.auto_connect_serial_var.get():
            app.auto_connect_serial_var.set(False)
            changed = True

        if changed:
            log_app_event(
                "app.input.keyboard_morse_constraints_applied",
                message="Keyboard Morse constraints were applied.",
                context={
                    "use_telemetry_as_truth": bool(app.use_telemetry_as_truth_var.get()),
                    "auto_connect_serial": bool(app.auto_connect_serial_var.get()),
                },
            )
            app.serial_controller.update_serial_buttons()

        if show_status and changed:
            app.status_controller.set_main_status(
                app.i18n.t(
                    "input.keyboard_morse.constraints_applied",
                    "Keyboard Morse uses raw telemetry. Telemetry was set as truth and serial auto-connect was disabled.",
                ),
                state="normal",
            )

    def on_keyboard_morse_enabled_changed(self) -> None:
        """Handle the settings checkbox for computer keyboard Morse input."""
        app = self.app

        self.cancel_keyboard_morse_press()
        self.apply_keyboard_morse_setting_constraints(show_status=True)

        enabled = self.keyboard_morse_enabled()
        log_app_event(
            "app.input.keyboard_morse_enabled" if enabled else "app.input.keyboard_morse_disabled",
            message="Keyboard Morse setting changed.",
            context={"enabled": bool(enabled), "key": self.keyboard_morse_expected_key()},
        )

        if enabled:
            selected_label = self.keyboard_morse_label_from_key(
                self.keyboard_morse_expected_key()
            )
            app.status_controller.set_main_status(
                app.i18n.t(
                    "input.keyboard_morse.enabled",
                    "Keyboard Morse enabled. Press {keyboard_key} like a straight key.",
                    keyboard_key=selected_label,
                ),
                state="normal",
            )
        else:
            app.status_controller.set_main_status(
                app.i18n.t(
                    "input.keyboard_morse.disabled",
                    "Keyboard Morse disabled.",
                ),
                state="normal",
            )

        app.practice_controller.evaluate_live()
        app.app_lifecycle_controller.focus_input(force=True)

    def on_use_telemetry_as_truth_changed(self) -> None:
        """Prevent telemetry scoring from being disabled while keyboard Morse is active."""
        app = self.app

        if self.keyboard_morse_enabled() and not app.use_telemetry_as_truth_var.get():
            log_app_event(
                "app.input.telemetry_as_truth_forced",
                level="warning",
                message="Telemetry-as-truth was forced because Keyboard Morse is enabled.",
            )
            app.use_telemetry_as_truth_var.set(True)
            app.status_controller.set_main_status(
                app.i18n.t(
                    "input.keyboard_morse.telemetry_required",
                    "Keyboard Morse requires telemetry as truth, so the setting was not disabled.",
                ),
                state="warning",
            )

        app.practice_controller.evaluate_live()
        app.app_lifecycle_controller.focus_input(force=True)

    def on_auto_connect_serial_changed(self) -> None:
        """Prevent serial auto-connect from being enabled while keyboard Morse is active."""
        app = self.app

        if self.keyboard_morse_enabled() and app.auto_connect_serial_var.get():
            log_app_event(
                "app.input.serial_auto_connect_blocked_by_keyboard_morse",
                level="warning",
                message="Serial auto-connect was blocked because Keyboard Morse is enabled.",
            )
            app.auto_connect_serial_var.set(False)
            app.status_controller.set_main_status(
                app.i18n.t(
                    "input.keyboard_morse.serial_auto_connect_blocked",
                    "Keyboard Morse is enabled, so serial auto-connect is kept disabled.",
                ),
                state="warning",
            )

        app.serial_controller.update_serial_buttons()
        app.app_lifecycle_controller.focus_input(force=True)

    def on_hid_key_release(self, _event: tk.Event) -> None:
        """Handle HID keyboard-style text input from a connected keyer."""
        app = self.app

        app.serial_controller.request_auto_connect_scan()

        if not app.round.accepting_input or app.round.finished:
            app.input_var.set("")
            return

        current_text = app.input_var.get().upper()

        if current_text:
            app.practice_controller.start_round_clock_from_host_input()

        app.round.hid_text = current_text
        app.practice_controller.evaluate_live()
        app.practice_controller.check_round_completion()
        app.app_lifecycle_controller.focus_input()

    def poll_serial_events(self) -> None:
        """Poll pending serial events from the event queue and dispatch them.

        Keep each UI poll short so Tkinter can repaint the raw telemetry canvas
        between bursts of incoming tone events.
        """
        app = self.app

        max_events = int(getattr(config, "UI_MAX_SERIAL_EVENTS_PER_POLL", 8))
        max_events = max(1, max_events)

        queued_before = self.serial_queue_size()
        warning_threshold = int(getattr(config, "UI_SERIAL_QUEUE_WARNING_THRESHOLD", 64))
        if queued_before >= warning_threshold:
            now = time.monotonic()
            last_warning = float(getattr(app, "_last_serial_queue_warning_time", 0.0) or 0.0)
            if now - last_warning >= 2.0:
                setattr(app, "_last_serial_queue_warning_time", now)
                log_app_event(
                    "app.input.serial_queue_backlog",
                    level="warning",
                    message="Serial event queue backlog detected.",
                    context={
                        "queue_size": queued_before,
                        "warning_threshold": warning_threshold,
                        "max_events_per_poll": max_events,
                    },
                )

        processed = 0
        queue_empty = False

        while processed < max_events:
            try:
                event = app.event_queue.get_nowait()
            except queue.Empty:
                queue_empty = True
                break

            self.handle_serial_event(event)
            processed += 1

        if queue_empty:
            delay_ms = int(getattr(config, "UI_POLL_INTERVAL_MS", 40))
        else:
            delay_ms = int(getattr(config, "UI_SERIAL_POLL_BACKLOG_DELAY_MS", 1))

        app.after(delay_ms, self.poll_serial_events)

    def serial_queue_size(self) -> int:
        """Return the pending serial event count when the queue implementation supports it."""
        try:
            return int(self.app.event_queue.qsize())
        except Exception:
            return -1

    def drain_serial_queue(self) -> int:
        """Discard all currently queued serial events and return the number discarded."""
        app = self.app

        discarded = 0
        while True:
            try:
                app.event_queue.get_nowait()
            except queue.Empty:
                return discarded
            else:
                discarded += 1

    def serial_event_connection_id(self, event: Dict[str, Any]) -> Optional[int]:
        """Return the serial connection id attached by SerialReader, when available."""
        raw_connection_id = event.get("_serial_connection_id")

        if raw_connection_id is None:
            return None

        try:
            return int(raw_connection_id)
        except Exception:
            return None

    def should_drop_stale_serial_event(
        self,
        event: Dict[str, Any],
        event_type: str,
    ) -> bool:
        """Return True if an event belongs to an older serial connection."""
        if self.is_keyboard_morse_tone_event(event):
            return False

        event_connection_id = self.serial_event_connection_id(event)
        if event_connection_id is None:
            return False

        current_connection_id = int(getattr(self.app, "serial_connection_id", 0) or 0)

        if current_connection_id and event_connection_id != current_connection_id:
            log_app_event(
                "app.input.serial_event_dropped_stale_connection",
                level="warning",
                message="Serial event from an older connection was dropped.",
                context={
                    "event_type": event_type,
                    "event_connection_id": event_connection_id,
                    "current_connection_id": current_connection_id,
                    "event_port": event.get("_serial_port"),
                },
            )
            return True

        return False

    def should_drop_stale_tone_event(self, event: Dict[str, Any]) -> bool:
        """Return True if a queued tone event is too old to be trusted."""
        if self.is_keyboard_morse_tone_event(event):
            return False

        received_time = event.get("_host_received_time")
        if received_time is None:
            return False

        try:
            lag_seconds = time.time() - float(received_time)
        except Exception:
            return False

        stale_drop_seconds = float(getattr(config, "UI_SERIAL_STALE_TONE_DROP_SECONDS", 5.0))
        lag_log_seconds = float(getattr(config, "UI_SERIAL_EVENT_LAG_LOG_SECONDS", 1.0))

        if lag_seconds >= stale_drop_seconds:
            log_app_event(
                "app.input.serial_tone_dropped_stale",
                level="warning",
                message="Stale serial tone event was dropped before practice handling.",
                context={
                    "lag_seconds": round(lag_seconds, 3),
                    "stale_drop_seconds": stale_drop_seconds,
                    "event_connection_id": event.get("_serial_connection_id"),
                    "event_port": event.get("_serial_port"),
                    "src": event.get("src"),
                    "t0": event.get("t0"),
                    "t1": event.get("t1"),
                },
            )
            return True

        if lag_seconds >= lag_log_seconds:
            log_app_event(
                "app.input.serial_tone_lag_detected",
                level="warning",
                message="Serial tone event was processed with noticeable delay.",
                context={
                    "lag_seconds": round(lag_seconds, 3),
                    "lag_log_seconds": lag_log_seconds,
                    "event_connection_id": event.get("_serial_connection_id"),
                    "event_port": event.get("_serial_port"),
                    "src": event.get("src"),
                    "t0": event.get("t0"),
                    "t1": event.get("t1"),
                },
            )

        return False

    def handle_serial_event(self, event: Dict[str, Any]) -> None:
        """Handle one incoming serial, virtual keyboard or local tone event."""
        app = self.app
        event_type = str(
            event.get(
                "type",
                app.i18n.t("input.event.unknown", "unknown"),
            )
        )

        if self.should_drop_stale_serial_event(event, event_type):
            return

        app.last_event_var.set(
            app.i18n.t(
                "input.event.label",
                "Event: {event_type}",
                event_type=event_type,
            )
        )

        if self.handle_non_tone_serial_event(event, event_type):
            return

        if (
            event_type == "tone"
            and self.keyboard_morse_enabled()
            and not self.is_keyboard_morse_tone_event(event)
        ):
            return

        if event_type == "tone":
            try:
                app.network_manager.publish_local_tone(dict(event))
            except Exception:
                pass

            try:
                network_window = getattr(app, "network_window", None)
                if network_window is not None and network_window.winfo_exists():
                    network_window.notify_local_tone(dict(event))
            except Exception:
                pass

            if bool(getattr(app, "network_modal_active", False)):
                return

        if event_type == "tone" and self.should_drop_stale_tone_event(event):
            return

        self.maybe_start_practice_from_key(event)

        if not app.round.accepting_input or app.round.finished or event_type != "tone":
            return

        if not self.accept_tone_event(event):
            return

        self.record_tone_event(event)
        app.practice_controller.start_round_clock_from_tone_event(event)
        app.practice_controller.mark_live_ui_dirty()

    def handle_non_tone_serial_event(
        self,
        event: Dict[str, Any],
        event_type: str,
    ) -> bool:
        """Handle serial events that are not tone events."""
        app = self.app

        if event_type == "serial_error":
            app.serial_controller.handle_serial_disconnect_event(event)
            return True

        if event_type in {"serial_non_json", "serial_non_object"}:
            log_app_event(
                "app.input.invalid_serial_message",
                level="warning",
                message="Invalid serial message was ignored.",
                context={"event_type": event_type},
            )
            app.status_controller.set_main_status(
                app.i18n.t(
                    "input.serial.invalid_message",
                    "Invalid message received from serial port.",
                ),
                state="warning",
            )
            return True

        if event_type == "hello":
            log_app_event(
                "app.input.device_hello_received",
                message="Serial device hello received.",
                context={
                    "device": event.get("device"),
                    "app": event.get("app"),
                    "fw": event.get("fw"),
                    "mode": event.get("mode"),
                },
            )
            app.status_var.set(
                app.i18n.t(
                    "input.serial.device_detected",
                    "Device detected: {device}",
                    device=event.get(
                        "device",
                        app.i18n.t("input.event.unknown", "unknown"),
                    ),
                )
            )
            return True

        return False

    def accept_tone_event(self, event: Dict[str, Any]) -> bool:
        """Return True when the tone event is valid and not a duplicate."""
        app = self.app

        tone_key = self.tone_event_key(event)

        if tone_key is None:
            return False

        if tone_key == app.last_tone_event_key:
            return False

        app.last_tone_event_key = tone_key
        return True

    def record_tone_event(self, event: Dict[str, Any]) -> None:
        """Append an accepted tone event to the current round and live decoder."""
        app = self.app

        now = time.time()
        event.setdefault("_host_received_time", now)
        event["_host_processed_time"] = now
        app.round.events.append(event)

        if app.live_decoder is not None:
            app.live_decoder.feed_event(event)

    def maybe_start_practice_from_key(self, event: Dict[str, Any]) -> None:
        """Start the countdown when enough tone events arrive while practice is idle."""
        app = self.app

        if app.practice_running or app.start_countdown_running:
            return

        if app.round.accepting_input and not app.round.finished:
            return

        if event.get("type") != "tone":
            return

        now = time.monotonic()

        app.start_trigger_timestamps = [
            timestamp
            for timestamp in app.start_trigger_timestamps
            if now - timestamp <= app.start_trigger_window_seconds
        ]

        app.start_trigger_timestamps.append(now)

        if len(app.start_trigger_timestamps) >= app.start_trigger_count:
            log_app_event(
                "app.input.practice_auto_start_triggered",
                message="Practice start countdown triggered by incoming tone events.",
                context={
                    "trigger_count": len(app.start_trigger_timestamps),
                    "required_count": app.start_trigger_count,
                    "window_seconds": app.start_trigger_window_seconds,
                    "source": event.get("src"),
                },
            )
            app.practice_controller.begin_start_countdown()

    def tone_event_key(self, event: Dict[str, Any]) -> Optional[tuple[str, int, int]]:
        """Return the deduplication key for one tone event."""
        if event.get("type") != "tone":
            return None

        src = event.get("src")
        t0 = event.get("t0")
        t1 = event.get("t1")

        if not isinstance(src, str) or not isinstance(t0, int) or not isinstance(t1, int):
            return None

        return src, t0, t1