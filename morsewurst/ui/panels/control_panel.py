# ============================================================
# morsewurst/ui/panels/control_panel.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def build_control_panel(app: tk.Misc, parent: ttk.Frame) -> None:
    """Build the main action button row."""

    buttons = ttk.Frame(parent)
    buttons.pack(fill=tk.X, pady=(10, 0))

    app.start_button = ttk.Button(
        buttons,
        text="Aloita harjoitus",
        command=app.practice_controller.start_practice,
    )
    app.start_button.pack(side=tk.LEFT)

    app.stop_button = ttk.Button(
        buttons,
        text="Lopeta harjoitus",
        command=app.practice_controller.stop_practice,
        state=tk.DISABLED,
    )
    app.stop_button.pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        buttons,
        text="Tyhjennä",
        command=app.practice_controller.clear_round_input,
    ).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        buttons,
        text="Ohje",
        command=app.window_controller.open_help,
    ).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        buttons,
        text="Poista harjoituksia",
        command=app.window_controller.open_delete_sessions_window,
    ).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        buttons,
        text="Asetukset",
        command=app.window_controller.open_advanced_settings,
    ).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        buttons,
        text="Tilastot",
        command=app.window_controller.open_stats_window,
    ).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        buttons,
        text="Network",
        command=app.window_controller.open_network_window,
    ).pack(side=tk.LEFT, padx=(8, 0))

    app.status_label = ttk.Label(
        buttons,
        textvariable=app.status_var,
    )

    app.status_label.pack(side=tk.LEFT, padx=(16, 0))