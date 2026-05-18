# ============================================================
# morsewurst/ui/network/views/callsign_view.py
# ============================================================

from __future__ import annotations

import tkinter as tk

from morsewurst.network.settings_store import sanitize_callsign
from morsewurst.ui.network_matrix_theme import (
    MatrixTheme,
    make_button,
    make_entry,
    make_label,
    make_panel,
)

class CallsignViewMixin:
    def _needs_first_callsign(self) -> bool:
        if not self.settings_file_exists:
            return True
        return sanitize_callsign(self.settings.callsign) == "Morsewurst"

    def show_callsign_view(self) -> None:
        self.current_view = "callsign"
        self._clear_content()
        self._render_footer()

        panel = make_panel(self.content, padx=24, pady=22)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)

        make_label(
            panel,
            "SELECT NETWORK CALLSIGN",
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.accent,
        ).grid(row=0, column=0, sticky="w")

        make_label(
            panel,
            "Choose the callsign shown to other users in Morsewurst Network. You can change it later in Network settings.",
            foreground=MatrixTheme.text_dim,
            wraplength=760,
        ).grid(row=1, column=0, sticky="ew", pady=(8, 18))

        entry = make_entry(panel, self.callsign_var, width=32)
        entry.grid(row=2, column=0, sticky="w")
        entry.focus_set()

        self.callsign_notice_var = tk.StringVar(value="")
        make_label(
            panel,
            variable=self.callsign_notice_var,
            foreground=MatrixTheme.warning,
        ).grid(row=3, column=0, sticky="w", pady=(10, 0))

        make_button(
            panel,
            "SAVE AND ENTER LOBBY",
            self._save_first_callsign,
        ).grid(row=4, column=0, sticky="w", pady=(18, 0))

        entry.bind("<Return>", lambda _event: self._save_first_callsign())

    def _save_first_callsign(self) -> None:
        callsign = sanitize_callsign(self.callsign_var.get())

        if callsign == "Morsewurst":
            self.callsign_notice_var.set("Please enter your own network callsign first.")
            return

        self.callsign_var.set(callsign)
        self._save_current_settings(last_room=self.settings.last_room)
        self.show_lobby_view()