# ============================================================
# morsewurst/ui/controllers/status_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

from tkinter import ttk

import morsewurst.config as config

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

        self.configure_state_label(app.serial_status_label, state, size=9)

    def set_main_status(self, text: str, state: str = "normal") -> None:
        app = self.app

        app.status_var.set(text)

        if not hasattr(app, "status_label"):
            return

        self.configure_state_label(app.status_label, state)

    def configure_state_label(self, label: ttk.Label, state: str, *, size: int | None = None) -> None:
        family = str(getattr(config, "UI_MAIN_STATUS_FONT_FAMILY", "Segoe UI"))
        normal_weight = str(getattr(config, "UI_MAIN_STATUS_FONT_WEIGHT", "normal"))
        emphasis_weight = str(getattr(config, "UI_MAIN_STATUS_EMPHASIS_WEIGHT", "bold"))
        if size is None:
            size = int(getattr(config, "UI_MAIN_STATUS_FONT_SIZE", 10))
        else:
            size = int(size)

        styles = {
            "connected": ("#178a2f", (family, size, emphasis_weight)),
            "success": ("#178a2f", (family, size, emphasis_weight)),
            "busy": ("#8a5a00", (family, size, emphasis_weight)),
            "warning": ("#8a5a00", (family, size, emphasis_weight)),
            "error": ("#b00020", (family, size, emphasis_weight)),
            "disconnected": ("#b00020", (family, size, emphasis_weight)),
        }

        foreground, font = styles.get(state, ("", (family, size, normal_weight)))
        label.configure(foreground=foreground, font=font)
