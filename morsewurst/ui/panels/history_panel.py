# ============================================================
# morsewurst/ui/panels/history_panel.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import morsewurst.config as config


def build_history_panel(app: tk.Misc, parent: ttk.Frame) -> None:
    """Build the recent rounds table.

    This table intentionally has horizontal scrolling because decoded input and
    target strings can become wider than the available screen area.
    """

    history_frame = ttk.LabelFrame(parent, text=app.i18n.t("history.panel_title"))
    history_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    columns = (
        "id",
        "finished",
        "accuracy",
        "cleanliness",
        "score",
        "errors",
        "wpm",
        "time",
        "entered",
        "target",
    )

    history_inner = ttk.Frame(history_frame)
    history_inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    history_inner.columnconfigure(0, weight=1)
    history_inner.columnconfigure(1, weight=0)
    history_inner.rowconfigure(0, weight=1)
    history_inner.rowconfigure(1, weight=0)

    app.history_tree = ttk.Treeview(
        history_inner,
        columns=columns,
        show="headings",
        height=getattr(config, "HISTORY_VISIBLE_ROWS", 10),
    )

    definitions = [
        ("id", app.i18n.t("history.column.id"), 46),
        ("finished", app.i18n.t("history.column.time"), 140),
        ("accuracy", app.i18n.t("history.column.accuracy"), 80),
        ("cleanliness", app.i18n.t("history.column.cleanliness"), 80),
        ("score", app.i18n.t("history.column.score"), 75),
        ("errors", app.i18n.t("history.column.errors"), 65),
        ("wpm", app.i18n.t("history.column.gross_wpm"), 85),
        ("time", app.i18n.t("history.column.duration"), 80),
        ("entered", app.i18n.t("history.column.input"), 190),
        ("target", app.i18n.t("history.column.target"), 190),
    ]

    for col, title, width in definitions:
        app.history_tree.heading(
            col,
            text=title,
            anchor=tk.W,
            command=lambda c=col: app.history_controller.sort_history_tree(c, False),
        )
        app.history_tree.column(col, width=width, anchor=tk.W, stretch=False)

    history_scroll_y = ttk.Scrollbar(
        history_inner,
        orient=tk.VERTICAL,
        command=app.history_tree.yview,
    )

    history_scroll_x = ttk.Scrollbar(
        history_inner,
        orient=tk.HORIZONTAL,
        command=app.history_tree.xview,
    )

    app.history_tree.configure(
        yscrollcommand=history_scroll_y.set,
        xscrollcommand=history_scroll_x.set,
    )

    app.history_tree.grid(row=0, column=0, sticky="nsew")
    history_scroll_y.grid(row=0, column=1, sticky="ns")
    history_scroll_x.grid(row=1, column=0, sticky="ew")

    app.history_tree.bind(
        "<<TreeviewSelect>>",
        app.history_controller.open_history_round_from_selection,
    )

    app.history_tree.bind(
        "<Return>",
        lambda _event: app.history_controller.open_selected_history_round(),
    )