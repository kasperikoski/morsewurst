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

    history_frame = ttk.LabelFrame(parent, text="Viimeisimmät kierrokset")
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
        ("id", "ID", 46),
        ("finished", "Aika", 140),
        ("accuracy", "Tarkkuus", 80),
        ("cleanliness", "Puhtaus", 80),
        ("score", "Pisteet", 75),
        ("errors", "Virheet", 65),
        ("wpm", "Brutto-WPM", 85),
        ("time", "Kesto", 80),
        ("entered", "Syöte", 190),
        ("target", "Tavoite", 190),
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