# ============================================================
# morsewurst/ui/controllers/status_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

from tkinter import ttk

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class StatusController:
    """Owns main status text, serial status text and status label styling."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def set_serial_status(self, text: str, state: str = "disconnected") -> None:
        app = self.app

        app.serial_status_var.set(text)

        if not hasattr(app, "serial_status_label"):
            return

        self.configure_state_label(app.serial_status_label, state)

    def set_main_status(self, text: str, state: str = "normal") -> None:
        app = self.app

        app.status_var.set(text)

        if not hasattr(app, "status_label"):
            return

        self.configure_state_label(app.status_label, state)

    def configure_state_label(self, label: ttk.Label, state: str) -> None:
        styles = {
            "connected": ("#178a2f", ("Segoe UI", 9, "bold")),
            "success": ("#178a2f", ("Segoe UI", 9, "bold")),
            "busy": ("#8a5a00", ("Segoe UI", 9, "bold")),
            "warning": ("#8a5a00", ("Segoe UI", 9, "bold")),
            "error": ("#b00020", ("Segoe UI", 9, "bold")),
            "disconnected": ("#b00020", ("Segoe UI", 9, "bold")),
        }

        foreground, font = styles.get(state, ("", ("Segoe UI", 9)))
        label.configure(foreground=foreground, font=font)