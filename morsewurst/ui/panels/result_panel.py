# ============================================================
# morsewurst/ui/panels/result_panel.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

import morsewurst.config as config


def _config_int(name: str, default: int) -> int:
    try:
        return int(getattr(config, name, default))
    except (TypeError, ValueError):
        return int(default)


def _metric_cell(
    parent: ttk.Frame,
    row: int,
    column: int,
    label: str,
    variable: tk.StringVar,
    *,
    width: int = 15,
    metric_cells: list[dict[str, Any]] | None = None,
) -> None:
    cell = ttk.Frame(parent)
    cell.grid(row=row, column=column, sticky=tk.W, padx=(0, 14), pady=(0, 4))

    label_widget = ttk.Label(
        cell,
        text=label,
        foreground="#666666",
        font=("Segoe UI", 8),
    )
    label_widget.pack(anchor=tk.W)

    value_widget = ttk.Label(
        cell,
        textvariable=variable,
        font=("Segoe UI", 9, "bold"),
        width=width,
        anchor=tk.W,
    )
    value_widget.pack(anchor=tk.W)

    if metric_cells is not None:
        metric_cells.append(
            {
                "cell": cell,
                "label": label_widget,
                "value": value_widget,
                "normal_width": width,
            }
        )


def _apply_metric_layout(metric_cells: list[dict[str, Any]], *, compact: bool) -> None:
    compact_value_width = _config_int("UI_RESULT_COMPACT_VALUE_WIDTH", 10)
    compact_pady = _config_int("UI_RESULT_COMPACT_CELL_PADY", 2)

    for metric in metric_cells:
        cell = metric["cell"]
        label_widget = metric["label"]
        value_widget = metric["value"]
        normal_width = int(metric["normal_width"])

        label_widget.pack_forget()
        value_widget.pack_forget()

        if compact:
            cell.grid_configure(pady=(0, compact_pady))
            value_widget.configure(width=max(normal_width, compact_value_width))
            label_widget.pack(side=tk.LEFT, anchor=tk.W)
            value_widget.pack(side=tk.LEFT, anchor=tk.W, padx=(6, 0))
        else:
            cell.grid_configure(pady=(0, 4))
            value_widget.configure(width=normal_width)
            label_widget.pack(anchor=tk.W)
            value_widget.pack(anchor=tk.W)


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

    metric_cells: list[dict[str, Any]] = []

    def metric_cell(
        metric_parent: ttk.Frame,
        row: int,
        column: int,
        label: str,
        variable: tk.StringVar,
        *,
        width: int = 15,
    ) -> None:
        _metric_cell(
            metric_parent,
            row,
            column,
            label,
            variable,
            width=width,
            metric_cells=metric_cells,
        )

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

    metric_cell(practice_box, 1, 0, app.i18n.t("result_panel.practice_rounds"), app.result_practice_rounds_var)
    metric_cell(practice_box, 1, 1, app.i18n.t("result_panel.practice_accuracy"), app.result_practice_accuracy_var)

    metric_cell(practice_box, 2, 0, app.i18n.t("result_panel.practice_cleanliness"), app.result_practice_cleanliness_var)
    metric_cell(practice_box, 2, 1, app.i18n.t("result_panel.practice_score"), app.result_practice_score_var)

    metric_cell(practice_box, 3, 0, app.i18n.t("result_panel.practice_timing"), app.result_practice_timing_var)
    metric_cell(practice_box, 3, 1, app.i18n.t("result_panel.practice_net_wpm"), app.result_practice_net_wpm_var)

    metric_cell(practice_box, 4, 0, app.i18n.t("result_panel.practice_gross_wpm"), app.result_practice_gross_wpm_var)
    metric_cell(practice_box, 4, 1, app.i18n.t("result_panel.practice_device_wpm"), app.result_practice_device_wpm_var)

    metric_cell(practice_box, 5, 0, app.i18n.t("result_panel.practice_straight_ratio"), app.result_practice_straight_ratio_var)
    metric_cell(practice_box, 5, 1, app.i18n.t("result_panel.practice_element_variation"), app.result_practice_element_variation_var)

    # ============================================================
    # Column 2: latest round
    # ============================================================

    latest_box = ttk.Frame(content)
    latest_box.grid(row=0, column=1, sticky=tk.NW)

    _section_title(latest_box, variable=app.result_latest_title_var)

    metric_cell(latest_box, 1, 0, app.i18n.t("result_panel.latest_accuracy"), app.result_latest_accuracy_var)
    metric_cell(latest_box, 1, 1, app.i18n.t("result_panel.latest_cleanliness"), app.result_latest_cleanliness_var)

    metric_cell(latest_box, 2, 0, app.i18n.t("result_panel.latest_score"), app.result_latest_score_var)
    metric_cell(latest_box, 2, 1, app.i18n.t("result_panel.latest_timing"), app.result_latest_timing_var)

    metric_cell(latest_box, 3, 0, app.i18n.t("result_panel.latest_errors"), app.result_latest_errors_var)
    metric_cell(latest_box, 3, 1, app.i18n.t("result_panel.latest_extra_missing"), app.result_latest_extra_missing_var)

    metric_cell(latest_box, 4, 0, app.i18n.t("result_panel.latest_substitutions"), app.result_latest_substitutions_var)
    metric_cell(latest_box, 4, 1, app.i18n.t("result_panel.latest_straight_ratio"), app.result_latest_straight_ratio_var)

    metric_cell(latest_box, 5, 0, app.i18n.t("result_panel.latest_dot_variation"), app.result_latest_dot_variation_var)
    metric_cell(latest_box, 5, 1, app.i18n.t("result_panel.latest_dash_variation"), app.result_latest_dash_variation_var)

    metric_layout_state: dict[str, bool | None] = {"compact": None}

    def apply_result_metric_layout() -> None:
        threshold = _config_int("UI_RESULT_COMPACT_HEIGHT_THRESHOLD", 840)
        window_height = int(app.winfo_height())
        if window_height <= 1:
            window_height = _config_int("UI_MIN_HEIGHT", 800)

        compact = window_height < threshold
        if metric_layout_state["compact"] == compact:
            return

        metric_layout_state["compact"] = compact
        _apply_metric_layout(metric_cells, compact=compact)

    def update_result_metric_layout(event: tk.Event | None = None) -> None:
        if event is not None and event.widget is not app:
            return
        apply_result_metric_layout()

    apply_result_metric_layout()
    app.after_idle(apply_result_metric_layout)
    app.bind("<Configure>", update_result_metric_layout, add="+")
