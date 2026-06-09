# ============================================================
# morsewurst/ui/panels/control_panel.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import morsewurst.config as config


def _config_int(name: str, default: int) -> int:
    try:
        return int(getattr(config, name, default))
    except (TypeError, ValueError):
        return int(default)


def build_control_panel(app: tk.Misc, parent: ttk.Frame) -> None:
    """Build the main action buttons with a responsive one/two-row layout."""

    controls = ttk.Frame(parent)
    controls.pack(fill=tk.X, pady=(10, 0))
    controls.columnconfigure(0, weight=0)
    controls.columnconfigure(1, weight=1)

    button_area = ttk.Frame(controls)
    button_area.grid(row=0, column=0, sticky="nw")

    spacing = _config_int("UI_CONTROL_BUTTON_SPACING_PX", 8)
    stats_gap = _config_int("UI_CONTROL_STATS_SINGLE_ROW_GAP_PX", spacing)

    row1 = ttk.Frame(button_area)
    row2 = ttk.Frame(button_area)

    def pack_button(button: ttk.Button, *, first: bool = False) -> None:
        button.pack(side=tk.LEFT, padx=(0 if first else spacing, 0))

    app.start_button = ttk.Button(
        row1,
        text=app.i18n.t("control.start"),
        command=app.practice_controller.start_practice,
    )
    pack_button(app.start_button, first=True)

    app.stop_button = ttk.Button(
        row1,
        text=app.i18n.t("control.stop"),
        command=app.practice_controller.stop_practice,
        state=tk.DISABLED,
    )
    pack_button(app.stop_button)

    pack_button(
        ttk.Button(
            row1,
            text=app.i18n.t("control.clear"),
            command=app.practice_controller.clear_round_input,
        )
    )

    pack_button(
        ttk.Button(
            row1,
            text=app.i18n.t("control.delete_sessions"),
            command=app.window_controller.open_delete_sessions_window,
        )
    )

    pack_button(
        ttk.Button(
            row1,
            text=app.i18n.t("control.settings"),
            command=app.window_controller.open_advanced_settings,
        )
    )

    pack_button(
        ttk.Button(
            row2,
            text=app.i18n.t("control.stats"),
            command=app.window_controller.open_stats_window,
        ),
        first=True,
    )

    pack_button(
        ttk.Button(
            row2,
            text=app.i18n.t("control.backups"),
            command=app.window_controller.open_backup_window,
        )
    )

    pack_button(
        ttk.Button(
            row2,
            text=app.i18n.t("control.switch_profile"),
            command=app.window_controller.open_profile_window,
        )
    )

    pack_button(
        ttk.Button(
            row2,
            text=app.i18n.t("control.help"),
            command=app.window_controller.open_help,
        )
    )

    pack_button(
        ttk.Button(
            row2,
            text=app.i18n.t("control.network"),
            command=app.window_controller.open_network_window,
        )
    )

    pack_button(
        ttk.Button(
            row2,
            text=app.i18n.t("control.koch"),
            command=app.window_controller.open_koch_window,
        )
    )

    pack_button(
        ttk.Button(
            row2,
            text=app.i18n.t("control.scratchpad"),
            command=app.window_controller.open_scratchpad_window,
        )
    )

    button_layout_state: dict[str, bool | None] = {"single_row": None}

    def apply_button_layout() -> None:
        threshold = _config_int("UI_CONTROL_SINGLE_ROW_MIN_WIDTH", 1440)
        window_width = int(app.winfo_width())
        if window_width <= 1:
            window_width = _config_int("UI_MIN_WIDTH", 1280)

        single_row = window_width >= threshold
        if button_layout_state["single_row"] == single_row:
            return

        button_layout_state["single_row"] = single_row

        row1.pack_forget()
        row2.pack_forget()

        if single_row:
            row1.pack(side=tk.LEFT, anchor=tk.W)
            row2.pack(side=tk.LEFT, anchor=tk.W, padx=(stats_gap, 0))
        else:
            row1.pack(fill=tk.X, anchor=tk.W)
            row2.pack(fill=tk.X, anchor=tk.W, pady=(4, 0))

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

    def update_control_button_layout(event: tk.Event | None = None) -> None:
        if event is not None and event.widget is not app:
            return
        apply_button_layout()

    apply_button_layout()
    app.after_idle(apply_button_layout)
    app.bind("<Configure>", update_control_button_layout, add="+")
    status_area.bind("<Configure>", update_status_wrap)
