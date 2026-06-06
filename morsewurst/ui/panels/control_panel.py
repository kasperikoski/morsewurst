# ============================================================
# morsewurst/ui/panels/control_panel.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import morsewurst.config as config


def build_control_panel(app: tk.Misc, parent: ttk.Frame) -> None:
    """Build the main action buttons in two compact rows."""

    controls = ttk.Frame(parent)
    controls.pack(fill=tk.X, pady=(10, 0))
    controls.columnconfigure(0, weight=0)
    controls.columnconfigure(1, weight=1)

    button_area = ttk.Frame(controls)
    button_area.grid(row=0, column=0, sticky="nw")

    row1 = ttk.Frame(button_area)
    row1.pack(fill=tk.X)

    row2 = ttk.Frame(button_area)
    row2.pack(fill=tk.X, pady=(4, 0))

    app.start_button = ttk.Button(
        row1,
        text=app.i18n.t("control.start"),
        command=app.practice_controller.start_practice,
    )
    app.start_button.pack(side=tk.LEFT)

    app.stop_button = ttk.Button(
        row1,
        text=app.i18n.t("control.stop"),
        command=app.practice_controller.stop_practice,
        state=tk.DISABLED,
    )
    app.stop_button.pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        row1,
        text=app.i18n.t("control.clear"),
        command=app.practice_controller.clear_round_input,
    ).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        row1,
        text=app.i18n.t("control.delete_sessions"),
        command=app.window_controller.open_delete_sessions_window,
    ).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        row1,
        text=app.i18n.t("control.settings"),
        command=app.window_controller.open_advanced_settings,
    ).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        row2,
        text=app.i18n.t("control.stats"),
        command=app.window_controller.open_stats_window,
    ).pack(side=tk.LEFT)

    ttk.Button(
        row2,
        text=app.i18n.t("control.backups"),
        command=app.window_controller.open_backup_window,
    ).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        row2,
        text=app.i18n.t("control.switch_profile"),
        command=app.window_controller.open_profile_window,
    ).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        row2,
        text=app.i18n.t("control.help"),
        command=app.window_controller.open_help,
    ).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        row2,
        text=app.i18n.t("control.network"),
        command=app.window_controller.open_network_window,
    ).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(
        row2,
        text=app.i18n.t("control.koch"),
        command=app.window_controller.open_koch_window,
    ).pack(side=tk.LEFT, padx=(8, 0))

    status_area = ttk.Frame(controls)
    status_area.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
    status_area.columnconfigure(0, weight=1)
    status_area.rowconfigure(0, weight=1)

    app.status_label = ttk.Label(
        status_area,
        textvariable=app.status_var,
        anchor=tk.E,
        justify=tk.RIGHT,
        padding=(8, 0, 4, 0),
    )
    app.status_label.grid(row=0, column=0, sticky="nsew")
    app.status_controller.configure_state_label(app.status_label, "normal")

    def update_status_wrap(event: tk.Event) -> None:
        try:
            min_width = int(getattr(config, "UI_MAIN_STATUS_WRAP_MIN_PX", 260))
            padding = int(getattr(config, "UI_MAIN_STATUS_WRAP_PADDING_PX", 20))
            app.status_label.configure(wraplength=max(min_width, int(event.width) - padding))
        except Exception:
            pass

    status_area.bind("<Configure>", update_status_wrap)
