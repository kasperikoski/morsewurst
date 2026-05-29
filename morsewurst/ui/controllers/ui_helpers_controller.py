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

        try:
            initial_value = int(textvariable.get())
        except Exception:
            initial_value = from_

        initial_value = max(from_, min(to, initial_value))
        editing_var = tk.StringVar(master=app, value=str(initial_value))
        syncing = {"active": False}

        def commit_text_value() -> None:
            """Validate, clamp and copy the editable text back to the IntVar."""
            raw_value = editing_var.get().strip()

            try:
                value = int(raw_value)
            except Exception:
                value = from_

            value = max(from_, min(to, value))
            normalized = str(value)

            syncing["active"] = True
            try:
                if editing_var.get() != normalized:
                    editing_var.set(normalized)

                try:
                    current_value = int(textvariable.get())
                except Exception:
                    current_value = None

                if current_value != value:
                    textvariable.set(value)
            finally:
                syncing["active"] = False

        def sync_from_model(*_args: object) -> None:
            """Keep the visible spinbox text in sync with external IntVar changes."""
            if syncing["active"]:
                return

            try:
                value = int(textvariable.get())
            except Exception:
                return

            value = max(from_, min(to, value))
            normalized = str(value)

            if editing_var.get() == normalized:
                return

            syncing["active"] = True
            try:
                editing_var.set(normalized)
            finally:
                syncing["active"] = False

        spinbox = ttk.Spinbox(
            parent,
            from_=from_,
            to=to,
            textvariable=editing_var,
            width=width,
            validate="key",
            validatecommand=(validate_command, "%P"),
            command=commit_text_value,
        )

        trace_id = textvariable.trace_add("write", sync_from_model)

        def remove_trace(event: tk.Event) -> None:
            """Remove the model trace when the widget is destroyed."""
            if event.widget is not spinbox:
                return

            try:
                textvariable.trace_remove("write", trace_id)
            except Exception:
                pass

        spinbox.bind("<Destroy>", remove_trace, add="+")
        spinbox.bind("<FocusOut>", lambda _event: commit_text_value(), add="+")
        spinbox.bind("<Return>", lambda _event: (commit_text_value(), "break")[-1], add="+")

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
            current_value = int(variable.get())
        except Exception:
            current_value = None

        if current_value != value:
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
            current_value = float(variable.get())
        except Exception:
            current_value = None

        if current_value is None or abs(current_value - value) > 0.000001:
            try:
                variable.set(value)
            except Exception:
                pass

        return value