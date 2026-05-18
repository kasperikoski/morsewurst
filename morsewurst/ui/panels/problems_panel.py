# ============================================================
# morsewurst/ui/panels/problems_panel.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import morsewurst.config as config


def build_problems_panel(app: tk.Misc, parent: ttk.Frame) -> None:
    """Build the most difficult characters panel."""

    problems = ttk.LabelFrame(parent, text="Vaikeimmat merkit")
    problems.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    columns = ("char", "attempts", "errors", "rate")

    inner = ttk.Frame(problems)
    inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    inner.columnconfigure(0, weight=1)
    inner.columnconfigure(1, weight=0)
    inner.rowconfigure(0, weight=1)

    app.problem_tree = ttk.Treeview(
        inner,
        columns=columns,
        show="headings",
        height=getattr(config, "PROBLEM_VISIBLE_ROWS", 8),
    )

    definitions = [
        ("char", "Merkki", 60),
        ("attempts", "Yritykset", 75),
        ("errors", "Virheet", 65),
        ("rate", "Virhe %", 70),
    ]

    for col, title, width in definitions:
        app.problem_tree.heading(col, text=title)
        app.problem_tree.column(col, width=width, anchor=tk.W, stretch=True)

    scroll_y = ttk.Scrollbar(
        inner,
        orient=tk.VERTICAL,
        command=app.problem_tree.yview,
    )

    app.problem_tree.configure(yscrollcommand=scroll_y.set)

    app.problem_tree.grid(row=0, column=0, sticky="nsew")
    scroll_y.grid(row=0, column=1, sticky="ns")