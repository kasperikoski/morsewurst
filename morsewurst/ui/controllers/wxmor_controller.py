# ============================================================
# morsewurst/ui/controllers/wxmor_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

import tkinter as tk

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class WxmorController:
    """Owns WX-MOR practice mode labels, value conversion and UI state."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def profile_labels(self) -> dict[str, str]:
        return {
            "auto": "Automaattinen",
            "minimum": "Minimi",
            "basic": "Perus",
            "compact": "Kompakti",
            "extended": "Laaja",
        }

    def profile_value_from_label(self, label: str) -> str:
        text = str(label or "").strip()
        text_lower = text.lower()

        labels = self.profile_labels()

        if text_lower in labels:
            return text_lower

        for value, display_label in labels.items():
            if text.casefold() == display_label.casefold():
                return value

        return "auto"

    def profile_label_from_value(self, value: str) -> str:
        labels = self.profile_labels()
        return labels.get(str(value or "auto").strip(), labels["auto"])

    def mode_enabled(self) -> bool:
        try:
            return bool(self.app.practice_wxmor_var.get())
        except Exception:
            return False

    def profile(self) -> str:
        try:
            return self.profile_value_from_label(self.app.wxmor_profile_var.get())
        except Exception:
            return "auto"

    def update_practice_state(self) -> None:
        app = self.app

        enabled = self.mode_enabled()
        disabled_state = tk.DISABLED if enabled else tk.NORMAL

        for widget in getattr(app, "wxmor_disabled_widgets", []):
            try:
                widget.configure(state=disabled_state)
            except Exception:
                pass

        if hasattr(app, "wxmor_profile_combo"):
            try:
                app.wxmor_profile_combo.configure(
                    state="readonly" if enabled else tk.DISABLED
                )
            except Exception:
                pass