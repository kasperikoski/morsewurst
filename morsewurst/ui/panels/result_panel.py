# ============================================================
# morsewurst/ui/panels/result_panel.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def _metric_cell(
    parent: ttk.Frame,
    row: int,
    column: int,
    label: str,
    variable: tk.StringVar,
    *,
    width: int = 15,
) -> None:
    cell = ttk.Frame(parent)
    cell.grid(row=row, column=column, sticky=tk.W, padx=(0, 14), pady=(0, 4))

    ttk.Label(
        cell,
        text=label,
        foreground="#666666",
        font=("Segoe UI", 8),
    ).pack(anchor=tk.W)

    ttk.Label(
        cell,
        textvariable=variable,
        font=("Segoe UI", 9, "bold"),
        width=width,
        anchor=tk.W,
    ).pack(anchor=tk.W)


def _section_title(
    parent: ttk.Frame,
    text: str | None = None,
    variable: tk.StringVar | None = None,
) -> None:
    kwargs = {
        "font": ("Segoe UI", 11, "bold"),
    }

    if variable is not None:
        kwargs["textvariable"] = variable
    else:
        kwargs["text"] = text or ""

    ttk.Label(
        parent,
        **kwargs,
    ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))


def build_result_panel(app: tk.Misc, parent: ttk.Frame) -> None:
    """Build the compact result panel."""

    result_frame = ttk.LabelFrame(parent, text=app.i18n.t("result_panel.frame_title"))
    result_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    # ============================================================
    # Top status area
    # ============================================================

    top = ttk.Frame(result_frame)
    top.pack(fill=tk.X, padx=12, pady=(8, 0))

    status_area = ttk.Frame(top)
    status_area.pack(fill=tk.X, anchor=tk.W)

    app.round_state_label = ttk.Label(
        status_area,
        textvariable=app.round_state_var,
    )
    app.round_state_label.pack(anchor=tk.W)

    app.start_countdown_canvas = tk.Canvas(
        status_area,
        width=getattr(app, "start_countdown_bar_width", 140),
        height=getattr(app, "start_countdown_bar_height", 18),
        highlightthickness=0,
        borderwidth=0,
    )

    ttk.Label(
        top,
        textvariable=app.timer_var,
        font=("Segoe UI", 15, "bold"),
    ).pack(anchor=tk.W, pady=(4, 8))

    # ============================================================
    # Compact two-column result grid
    # ============================================================

    content = ttk.Frame(result_frame)
    content.pack(fill=tk.X, padx=12, pady=(0, 8))

    content.columnconfigure(0, weight=1)
    content.columnconfigure(1, weight=1)

    # ============================================================
    # Column 1: current practice series
    # ============================================================

    practice_box = ttk.Frame(content)
    practice_box.grid(row=0, column=0, sticky=tk.NW, padx=(0, 28))

    _section_title(practice_box, app.i18n.t("result_panel.practice_title"))

    _metric_cell(practice_box, 1, 0, app.i18n.t("result_panel.practice_rounds"), app.result_practice_rounds_var)
    _metric_cell(practice_box, 1, 1, app.i18n.t("result_panel.practice_accuracy"), app.result_practice_accuracy_var)

    _metric_cell(practice_box, 2, 0, app.i18n.t("result_panel.practice_cleanliness"), app.result_practice_cleanliness_var)
    _metric_cell(practice_box, 2, 1, app.i18n.t("result_panel.practice_score"), app.result_practice_score_var)

    _metric_cell(practice_box, 3, 0, app.i18n.t("result_panel.practice_timing"), app.result_practice_timing_var)
    _metric_cell(practice_box, 3, 1, app.i18n.t("result_panel.practice_net_wpm"), app.result_practice_net_wpm_var)

    _metric_cell(practice_box, 4, 0, app.i18n.t("result_panel.practice_gross_wpm"), app.result_practice_gross_wpm_var)
    _metric_cell(practice_box, 4, 1, app.i18n.t("result_panel.practice_device_wpm"), app.result_practice_device_wpm_var)

    _metric_cell(practice_box, 5, 0, app.i18n.t("result_panel.practice_straight_ratio"), app.result_practice_straight_ratio_var)
    _metric_cell(practice_box, 5, 1, app.i18n.t("result_panel.practice_element_variation"), app.result_practice_element_variation_var)

    # ============================================================
    # Column 2: latest round
    # ============================================================

    latest_box = ttk.Frame(content)
    latest_box.grid(row=0, column=1, sticky=tk.NW)

    _section_title(latest_box, variable=app.result_latest_title_var)

    _metric_cell(latest_box, 1, 0, app.i18n.t("result_panel.latest_accuracy"), app.result_latest_accuracy_var)
    _metric_cell(latest_box, 1, 1, app.i18n.t("result_panel.latest_cleanliness"), app.result_latest_cleanliness_var)

    _metric_cell(latest_box, 2, 0, app.i18n.t("result_panel.latest_score"), app.result_latest_score_var)
    _metric_cell(latest_box, 2, 1, app.i18n.t("result_panel.latest_timing"), app.result_latest_timing_var)

    _metric_cell(latest_box, 3, 0, app.i18n.t("result_panel.latest_errors"), app.result_latest_errors_var)
    _metric_cell(latest_box, 3, 1, app.i18n.t("result_panel.latest_extra_missing"), app.result_latest_extra_missing_var)

    _metric_cell(latest_box, 4, 0, app.i18n.t("result_panel.latest_substitutions"), app.result_latest_substitutions_var)
    _metric_cell(latest_box, 4, 1, app.i18n.t("result_panel.latest_straight_ratio"), app.result_latest_straight_ratio_var)

    _metric_cell(latest_box, 5, 0, app.i18n.t("result_panel.latest_dot_variation"), app.result_latest_dot_variation_var)
    _metric_cell(latest_box, 5, 1, app.i18n.t("result_panel.latest_dash_variation"), app.result_latest_dash_variation_var)