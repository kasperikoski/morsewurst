# ============================================================
# morsewurst/ui/koch/views/input_view.py
# ============================================================

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk


class KochInputView(ttk.LabelFrame):
    """Single-line typed copy input for Koch receive practice."""

    def __init__(self, parent: tk.Misc, window: Any) -> None:
        super().__init__(parent, text=window.tr("koch.input.title", "Copy what you hear"))
        self.window = window
        self.status_var = tk.StringVar(value=window.tr("koch.status.ready", "Ready."))
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        self.input_text = tk.Entry(
            self,
            font=("TkDefaultFont", 15),
        )
        self.input_text.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(10, 0))
        self.input_text.bind("<KeyPress>", self.window.on_input_key_press)

        x_scrollbar = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.input_text.xview)
        self.input_text.configure(xscrollcommand=x_scrollbar.set)
        x_scrollbar.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=(0, 6))

        self.status_label = ttk.Label(self, textvariable=self.status_var)
        self.status_label.grid(row=2, column=0, sticky=tk.W, padx=10, pady=(0, 8))

    def clear_and_focus(self) -> None:
        self.input_text.delete(0, tk.END)
        self.input_text.xview_moveto(1.0)
        self.input_text.focus_set()

    def entered_text(self) -> str:
        return self.input_text.get()
