# ============================================================
# morsewurst/ui/panels/general_info_panel.py
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
    width: int = 11,
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


def _section_title(parent: ttk.Frame, text: str) -> None:
    ttk.Label(
        parent,
        text=text,
        font=("Segoe UI", 11, "bold"),
    ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))


def build_general_info_panel(app: tk.Misc, parent: ttk.Frame) -> None:
    """Build the general information panel.

    This panel is intended for long-term or supporting information.
    At the moment it contains history summary values.
    """

    info_frame = ttk.LabelFrame(parent, text="Yleistä tietoa")
    info_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    content = ttk.Frame(info_frame)
    content.pack(fill=tk.X, padx=12, pady=(8, 8))

    # ============================================================
    # History summary
    # ============================================================

    history_box = ttk.Frame(content)
    history_box.pack(anchor=tk.NW, fill=tk.X)

    _section_title(history_box, "Historia")

    _metric_cell(history_box, 1, 0, "Kierroksia", app.result_history_rounds_var)
    _metric_cell(history_box, 1, 1, "Tarkkuus", app.result_history_accuracy_var)

    _metric_cell(history_box, 2, 0, "Puhtaus", app.result_history_cleanliness_var)
    _metric_cell(history_box, 2, 1, "Pisteet", app.result_history_score_var)

    _metric_cell(history_box, 3, 0, "Brutto-WPM", app.result_history_gross_wpm_var)
    _metric_cell(history_box, 3, 1, "Netto-WPM", app.result_history_net_wpm_var)

    _metric_cell(history_box, 4, 0, "Laite-WPM", app.result_history_device_wpm_var)
    _metric_cell(history_box, 4, 1, "Viivasuhde", app.result_history_straight_ratio_var)

    _metric_cell(history_box, 5, 0, "Dit-hajonta", app.result_history_dot_variation_var)
    _metric_cell(history_box, 5, 1, "Dah-hajonta", app.result_history_dash_variation_var)

    # Reserved space for future general information.
    placeholder = ttk.Frame(content)
    placeholder.pack(fill=tk.X, pady=(8, 0))

    ttk.Label(
        placeholder,
        text="",
        foreground="#666666",
        font=("Segoe UI", 9),
    ).pack(anchor=tk.W)