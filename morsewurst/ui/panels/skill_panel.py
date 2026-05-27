# ============================================================
# morsewurst/ui/panels/skill_panel.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def _summary_pair(
    parent: ttk.Frame,
    row: int,
    label_column: int,
    label: str,
    variable: tk.StringVar,
) -> None:
    ttk.Label(
        parent,
        text=label,
        font=("Segoe UI", 8),
        foreground="#333333",
    ).grid(row=row, column=label_column, sticky=tk.W, padx=(0, 6), pady=(0, 2))

    ttk.Label(
        parent,
        textvariable=variable,
        font=("Consolas", 9, "bold"),
        anchor=tk.E,
    ).grid(
        row=row,
        column=label_column + 1,
        sticky=tk.E,
        padx=(0, 14),
        pady=(0, 2),
    )


def _build_skill_summary_grid(app: tk.Misc, parent: ttk.Frame) -> None:
    summary_grid = ttk.Frame(parent)
    summary_grid.pack(anchor=tk.W, padx=8, pady=(4, 0), fill=tk.X)

    summary_grid.columnconfigure(0, weight=1)
    summary_grid.columnconfigure(1, weight=0)
    summary_grid.columnconfigure(2, weight=1)
    summary_grid.columnconfigure(3, weight=0)

    _summary_pair(
        summary_grid,
        0,
        0,
        app.i18n.t("skill.overall_wpm"),
        app.skill_overall_wpm_value_var,
    )
    _summary_pair(
        summary_grid,
        0,
        2,
        app.i18n.t("skill.straight_wpm"),
        app.skill_straight_wpm_value_var,
    )

    _summary_pair(
        summary_grid,
        1,
        0,
        app.i18n.t("skill.both_wpm"),
        app.skill_both_wpm_value_var,
    )
    _summary_pair(
        summary_grid,
        1,
        2,
        app.i18n.t("skill.iambic_wpm"),
        app.skill_iambic_wpm_value_var,
    )

    _summary_pair(
        summary_grid,
        2,
        0,
        app.i18n.t("skill.next_level"),
        app.skill_next_level_value_var,
    )


def _metric_cell(
    parent: ttk.Frame,
    row: int,
    column: int,
    label: str,
    variable: tk.StringVar,
) -> None:
    cell = ttk.Frame(parent)
    cell.grid(row=row, column=column, sticky=tk.W, padx=(0, 12), pady=(0, 3))

    ttk.Label(
        cell,
        text=label,
        font=("Segoe UI", 7),
        foreground="#666666",
    ).pack(anchor=tk.W)

    ttk.Label(
        cell,
        textvariable=variable,
        font=("Segoe UI", 8, "bold"),
    ).pack(anchor=tk.W)


def build_skill_panel(app: tk.Misc, parent: ttk.Frame) -> None:
    """Build the skill rating panel."""

    skill = ttk.LabelFrame(parent, text=app.i18n.t("skill.title"))
    skill.pack(fill=tk.X, pady=(8, 0))

    ttk.Label(
        skill,
        textvariable=app.skill_title_var,
        font=("Segoe UI", 12, "bold"),
        justify=tk.LEFT,
    ).pack(anchor=tk.W, padx=8, pady=(5, 0))

    _build_skill_summary_grid(app, skill)

    factors_grid = ttk.Frame(skill)
    factors_grid.pack(anchor=tk.W, padx=8, pady=(6, 0), fill=tk.X)

    _metric_cell(
        factors_grid,
        0,
        0,
        app.i18n.t("skill.accuracy"),
        app.skill_accuracy_value_var,
    )
    _metric_cell(
        factors_grid,
        0,
        1,
        app.i18n.t("skill.cleanliness"),
        app.skill_cleanliness_value_var,
    )
    _metric_cell(
        factors_grid,
        0,
        2,
        app.i18n.t("skill.timing"),
        app.skill_timing_value_var,
    )
    _metric_cell(
        factors_grid,
        0,
        3,
        app.i18n.t("skill.adjustment"),
        app.skill_adjustment_value_var,
    )

    confidence_grid = ttk.Frame(skill)
    confidence_grid.pack(anchor=tk.W, padx=8, pady=(4, 0), fill=tk.X)

    _metric_cell(
        confidence_grid,
        0,
        0,
        app.i18n.t("skill.confidence"),
        app.skill_confidence_value_var,
    )
    _metric_cell(
        confidence_grid,
        0,
        1,
        app.i18n.t("skill.mastery"),
        app.skill_mastery_value_var,
    )
    _metric_cell(
        confidence_grid,
        0,
        2,
        app.i18n.t("skill.coverage"),
        app.skill_coverage_value_var,
    )

    rounds_grid = ttk.Frame(skill)
    rounds_grid.pack(anchor=tk.W, padx=8, pady=(4, 0), fill=tk.X)

    _metric_cell(
        rounds_grid,
        0,
        0,
        app.i18n.t("skill.min_rounds"),
        app.skill_used_rounds_value_var,
    )
    _metric_cell(
        rounds_grid,
        0,
        1,
        app.i18n.t("skill.total_rounds"),
        app.skill_total_used_rounds_value_var,
    )

    charset_grid = ttk.Frame(skill)
    charset_grid.pack(anchor=tk.W, padx=8, pady=(4, 0), fill=tk.X)

    _metric_cell(
        charset_grid,
        0,
        0,
        app.i18n.t("skill.charset_coverage"),
        app.skill_charset_coverage_value_var,
    )
    _metric_cell(
        charset_grid,
        0,
        1,
        app.i18n.t("skill.charset_scope_factor"),
        app.skill_charset_scope_value_var,
    )

    ttk.Label(
        skill,
        textvariable=app.skill_warning_var,
        font=("Segoe UI", 8),
        justify=tk.LEFT,
        foreground="#8a5a00",
        wraplength=320,
    ).pack(anchor=tk.W, padx=8, pady=(3, 5))