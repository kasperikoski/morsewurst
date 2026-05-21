# ============================================================
# morsewurst/ui/controllers/input_controller.py
# ============================================================

from __future__ import annotations

import queue
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

import tkinter as tk

import morsewurst.config as config

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

        app.keyboard_morse_key_var.set(selected_key)
        self.cancel_keyboard_morse_press()

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

        if self.keyboard_morse_enabled():
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
        """Poll pending serial events from the event queue and dispatch them."""
        app = self.app

        while True:
            try:
                event = app.event_queue.get_nowait()
            except queue.Empty:
                break

            self.handle_serial_event(event)

        app.after(config.UI_POLL_INTERVAL_MS, self.poll_serial_events)

    def drain_serial_queue(self) -> None:
        """Discard all currently queued serial events."""
        app = self.app

        while True:
            try:
                app.event_queue.get_nowait()
            except queue.Empty:
                return

    def handle_serial_event(self, event: Dict[str, Any]) -> None:
        """Handle one incoming serial, virtual keyboard or local tone event."""
        app = self.app
        event_type = str(
            event.get(
                "type",
                app.i18n.t("input.event.unknown", "unknown"),
            )
        )

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

        self.maybe_start_practice_from_key(event)

        if not app.round.accepting_input or app.round.finished or event_type != "tone":
            return

        if not self.accept_tone_event(event):
            return

        self.record_tone_event(event)
        app.practice_controller.start_round_clock_from_tone_event(event)
        app.decoder_controller.draw_raw_telemetry()
        app.practice_controller.update_adaptive_decoded_text(flush_final=False)
        app.practice_controller.evaluate_live()
        app.practice_controller.check_round_completion()
        app.app_lifecycle_controller.focus_input()

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
            app.status_controller.set_main_status(
                app.i18n.t(
                    "input.serial.invalid_message",
                    "Invalid message received from serial port.",
                ),
                state="warning",
            )
            return True

        if event_type == "hello":
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

        event["_host_received_time"] = time.time()
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