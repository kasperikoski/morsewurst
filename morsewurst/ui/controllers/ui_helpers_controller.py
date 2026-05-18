# ============================================================
# morsewurst/ui/controllers/ui_helpers_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

import tkinter as tk
from tkinter import ttk

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class UiHelpersController:
    """Owns small UI helper methods for validation, spinboxes and Tk variables."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def validate_positive_integer_text(self, proposed: str) -> bool:
        return proposed == "" or proposed.isdigit()

    def validate_positive_float_text(self, proposed: str) -> bool:
        if proposed == "":
            return True

        normalized = proposed.replace(",", ".")
        return normalized.count(".") <= 1 and all(
            part.isdigit()
            for part in normalized.split(".")
        )

    def make_int_spinbox(
        self,
        parent: tk.Misc,
        *,
        from_: int,
        to: int,
        textvariable: tk.IntVar,
        width: int = 8,
    ) -> ttk.Spinbox:
        app = self.app

        validate_command = app.register(self.validate_positive_integer_text)

        spinbox = ttk.Spinbox(
            parent,
            from_=from_,
            to=to,
            textvariable=textvariable,
            width=width,
            validate="key",
            validatecommand=(validate_command, "%P"),
        )

        spinbox.bind(
            "<FocusOut>",
            lambda _event: self.safe_int_var(
                textvariable,
                default=from_,
                minimum=from_,
                maximum=to,
            ),
        )
        spinbox.bind(
            "<Return>",
            lambda _event: self.safe_int_var(
                textvariable,
                default=from_,
                minimum=from_,
                maximum=to,
            ),
        )

        return spinbox

    def make_float_spinbox(
        self,
        parent: tk.Misc,
        *,
        from_: float,
        to: float,
        increment: float,
        textvariable: tk.DoubleVar,
        width: int = 8,
    ) -> ttk.Spinbox:
        app = self.app

        validate_command = app.register(self.validate_positive_float_text)

        spinbox = ttk.Spinbox(
            parent,
            from_=from_,
            to=to,
            increment=increment,
            textvariable=textvariable,
            width=width,
            validate="key",
            validatecommand=(validate_command, "%P"),
        )

        spinbox.bind(
            "<FocusOut>",
            lambda _event: self.safe_float_var(
                textvariable,
                default=from_,
                minimum=from_,
                maximum=to,
            ),
        )
        spinbox.bind(
            "<Return>",
            lambda _event: self.safe_float_var(
                textvariable,
                default=from_,
                minimum=from_,
                maximum=to,
            ),
        )

        return spinbox

    def safe_int_var(
        self,
        variable: tk.IntVar,
        *,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            value = int(variable.get())
        except Exception:
            value = default

        value = max(minimum, min(maximum, value))

        try:
            variable.set(value)
        except Exception:
            pass

        return value

    def safe_float_var(
        self,
        variable: tk.DoubleVar,
        *,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            value = float(variable.get())
        except Exception:
            value = default

        value = max(minimum, min(maximum, value))

        try:
            variable.set(value)
        except Exception:
            pass

        return value