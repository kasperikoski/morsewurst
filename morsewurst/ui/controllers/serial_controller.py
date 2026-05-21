# ============================================================
# morsewurst/ui/controllers/serial_controller.py
# ============================================================

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Optional

import tkinter as tk
from tkinter import messagebox

import morsewurst.config as config
from morsewurst.hardware.serial_reader import SerialReader

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class SerialController:
    """Owns serial port discovery, connection lifecycle and auto-connect scanning."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def refresh_ports(self) -> None:
        """Refresh available serial ports and update the port dropdown."""
        app = self.app

        ports = SerialReader.available_ports()

        if hasattr(app, "port_combo"):
            app.port_combo["values"] = ports

        current_port = app.port_var.get().strip()

        if ports:
            app.port_var.set(current_port if current_port in ports else current_port or ports[0])
        else:
            app.port_var.set("")

        if not SerialReader.serial_available():
            app.status_controller.set_serial_status(
                app.i18n.t("serial.status.pyserial_missing", "pyserial missing"),
                state="disconnected",
            )

        self.update_serial_buttons()

    def is_serial_port_busy_error(self, exc: Exception) -> bool:
        """Return True when an exception looks like a temporarily busy serial port."""
        text = str(exc or "").casefold()

        return (
            "permissionerror" in text
            or "access is denied" in text
            or "käyttö estetty" in text
            or (
                "could not open port" in text
                and ("denied" in text or "estetty" in text)
            )
        )

    def serial_port_busy_message(self, port: str) -> str:
        """Build a user-facing message for a temporarily busy serial port."""
        app = self.app

        fallback_port = app.i18n.t("serial.port.selected_fallback", "selected port")
        port_text = str(port or fallback_port).strip() or fallback_port

        return app.i18n.t(
            "serial.message.port_busy",
            "{port} is temporarily busy. Automatic device discovery or another program may be using the port. Wait a moment and try again.",
            port=port_text,
        )

    def connect_serial_port(self, port: str, automatic: bool = False) -> None:
        """Connect to a specific serial port manually or from auto-connect."""
        app = self.app
        port = str(port or "").strip()

        if not port:
            if not automatic:
                messagebox.showwarning(
                    config.APP_NAME,
                    app.i18n.t("serial.message.select_port_first", "Select a COM port first."),
                )
            return

        if not automatic and bool(getattr(app, "auto_connect_running", False)):
            app.status_controller.set_serial_status(
                app.i18n.t("serial.status.searching_device", "Searching for device..."),
                state="busy",
            )
            app.status_controller.set_main_status(
                app.i18n.t(
                    "serial.message.auto_search_in_progress_retry",
                    "Automatic serial port scan is in progress. Wait a moment and try again.",
                ),
                state="warning",
            )
            self.update_serial_buttons()
            return

        try:
            app.serial_reader.connect(port, config.SERIAL_BAUDRATE)

        except Exception as exc:
            app.serial_connected = False
            self.update_serial_buttons()

            if self.is_serial_port_busy_error(exc):
                message = self.serial_port_busy_message(port)
                app.status_controller.set_serial_status(
                    app.i18n.t("serial.status.port_busy", "Port is busy"),
                    state="warning",
                )
                app.status_controller.set_main_status(message, state="warning")

                if not automatic:
                    messagebox.showwarning(
                        config.APP_NAME,
                        message,
                    )
                else:
                    app.after(800, self.request_auto_connect_scan)

                return

            if not automatic:
                messagebox.showerror(
                    config.APP_NAME,
                    app.i18n.t(
                        "serial.message.open_failed",
                        "Opening the serial port failed:\n{error}",
                        error=str(exc),
                    ),
                )

            app.status_controller.set_serial_status(
                app.i18n.t("serial.status.connection_failed", "Connection failed"),
                state="disconnected",
            )
            return

        app.serial_connected = True
        app.auto_connect_running = False
        app.port_var.set(port)
        app.status_controller.set_serial_status(
            f"{port} @ {config.SERIAL_BAUDRATE}",
            state="connected",
        )
        app.status_controller.set_main_status(
            app.i18n.t("serial.message.device_connected", "Serial device connected."),
            state="normal",
        )
        app.audio_controller.play_sound("serial_connected")
        self.update_serial_buttons()
        app.app_lifecycle_controller.focus_input(force=True)

    def connect_serial(self) -> None:
        """Connect to the currently selected serial port from the UI."""
        app = self.app

        if bool(getattr(app, "auto_connect_running", False)):
            app.status_controller.set_serial_status(
                app.i18n.t("serial.status.searching_device", "Searching for device..."),
                state="busy",
            )
            app.status_controller.set_main_status(
                app.i18n.t(
                    "serial.message.auto_search_in_progress_retry",
                    "Automatic serial port scan is in progress. Wait a moment and try again.",
                ),
                state="warning",
            )
            self.update_serial_buttons()
            return

        self.connect_serial_port(app.port_var.get(), automatic=False)

    def disconnect_serial(self) -> None:
        """Disconnect the currently active serial connection."""
        app = self.app

        if bool(getattr(app, "auto_connect_running", False)):
            app.status_controller.set_serial_status(
                app.i18n.t("serial.status.searching_device", "Searching for device..."),
                state="busy",
            )
            app.status_controller.set_main_status(
                app.i18n.t(
                    "serial.message.auto_search_in_progress_disconnect_not_needed",
                    "Automatic serial port scan is in progress. Disconnecting is not necessary.",
                ),
                state="warning",
            )
            self.update_serial_buttons()
            return

        was_connected = app.serial_connected

        app.serial_reader.disconnect()
        app.serial_connected = False
        app.status_controller.set_serial_status(
            app.i18n.t("serial.status.disconnected", "No connection"),
            state="disconnected",
        )
        self.update_serial_buttons()

        if was_connected:
            app.audio_controller.play_sound("serial_disconnected")

    def handle_serial_disconnect_event(self, event: dict[str, object]) -> None:
        """Handle a serial disconnect event and restart auto-connect scanning."""
        app = self.app

        app.serial_connected = False
        app.auto_connect_running = False

        try:
            app.serial_reader.disconnect()
        except Exception:
            pass

        app.status_controller.set_serial_status(
            app.i18n.t("serial.status.disconnected", "No connection"),
            state="disconnected",
        )
        app.last_event_var.set(
            app.i18n.t(
                "input.event.label",
                "Event: {event_type}",
                event_type=app.i18n.t("serial.event.connection_lost", "connection lost"),
            )
        )
        app.audio_controller.play_sound("serial_disconnected")
        app.status_controller.set_main_status(
            app.i18n.t("serial.message.device_disconnected", "Serial device disconnected."),
            state="error",
        )

        self.refresh_ports()
        self.update_serial_buttons()
        app.after(500, self.request_auto_connect_scan)

    def request_auto_connect_scan(self) -> None:
        """Start an automatic serial scan when settings and state allow it."""
        app = self.app

        if app.input_controller.keyboard_morse_enabled():
            return

        if (
            app.auto_connect_serial_var.get()
            and not app.serial_connected
            and not app.auto_connect_running
            and SerialReader.serial_available()
        ):
            self.start_auto_connect_scan()

    def auto_connect_tick(self) -> None:
        """Periodic timer callback that keeps auto-connect scanning active."""
        app = self.app

        self.request_auto_connect_scan()
        app.after(
            getattr(config, "SERIAL_AUTO_CONNECT_INTERVAL_MS", 5000),
            self.auto_connect_tick,
        )

    def start_auto_connect_scan(self) -> None:
        """Start a background scan for a Morsewurst-compatible serial device."""
        app = self.app

        ports = SerialReader.available_ports()

        if not ports:
            app.status_controller.set_serial_status(
                app.i18n.t("serial.status.disconnected", "No connection"),
                state="disconnected",
            )
            self.update_serial_buttons()
            return

        app.auto_connect_running = True
        app.status_controller.set_serial_status(
            app.i18n.t("serial.status.searching_device", "Searching for device..."),
            state="busy",
        )
        self.update_serial_buttons()

        app.auto_connect_thread = threading.Thread(
            target=self.auto_connect_worker,
            args=(ports,),
            daemon=True,
        )
        app.auto_connect_thread.start()

    def auto_connect_worker(self, ports: list[str]) -> None:
        """Probe serial ports in a background thread and report the first matching port."""
        app = self.app
        found_port: Optional[str] = None

        for port in ports:
            if app.serial_connected:
                break

            result = SerialReader.probe_port(
                port,
                config.SERIAL_BAUDRATE,
                timeout_seconds=getattr(config, "SERIAL_AUTO_CONNECT_PROBE_SECONDS", 1.5),
            )

            if result is not None:
                found_port = port
                break

        app.after(0, lambda: self.finish_auto_connect_scan(found_port))

    def finish_auto_connect_scan(self, port: Optional[str]) -> None:
        """Finish an automatic scan and connect to the detected port when available."""
        app = self.app

        app.auto_connect_running = False

        if app.input_controller.keyboard_morse_enabled():
            self.update_serial_buttons()
            return

        if app.serial_connected:
            self.update_serial_buttons()
            return

        if port is None:
            app.status_controller.set_serial_status(
                app.i18n.t("serial.status.disconnected", "No connection"),
                state="disconnected",
            )
            self.update_serial_buttons()
            return

        self.connect_serial_port(port, automatic=True)

    def update_serial_buttons(self) -> None:
        """Update serial connection buttons and dropdown state according to current state."""
        app = self.app
        auto_scanning = bool(getattr(app, "auto_connect_running", False))

        if hasattr(app, "connect_serial_button"):
            app.connect_serial_button.configure(
                state=tk.DISABLED if app.serial_connected or auto_scanning else tk.NORMAL
            )

        if hasattr(app, "disconnect_serial_button"):
            app.disconnect_serial_button.configure(
                state=tk.NORMAL if app.serial_connected and not auto_scanning else tk.DISABLED
            )

        if hasattr(app, "port_combo"):
            try:
                app.port_combo.configure(state=tk.DISABLED if auto_scanning else "readonly")
            except Exception:
                pass