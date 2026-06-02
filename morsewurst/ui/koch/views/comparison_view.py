# ============================================================
# morsewurst/ui/koch/views/comparison_view.py
# ============================================================

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk


class KochComparisonView(ttk.LabelFrame):
    """Single-line colored corrected-copy comparison shown after a Koch drill."""

    def __init__(self, parent: tk.Misc, window: Any) -> None:
        super().__init__(parent, text=window.tr("koch.comparison.title", "Target comparison"))
        self.window = window
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        self.text = tk.Text(
            self,
            height=1,
            wrap=tk.NONE,
            font=("TkDefaultFont", 15, "bold"),
            padx=8,
            pady=6,
            state=tk.DISABLED,
            cursor="arrow",
        )
        self.text.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(10, 0))

        scrollbar = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.text.xview)
        self.text.configure(xscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=(0, 10))

        self.text.tag_configure("correct", foreground="#1f7a1f")
        self.text.tag_configure("wrong", foreground="#c83333")
        self.text.tag_configure("missing", foreground="#8a8a8a")
        self.text.tag_configure("extra", foreground="#fdc745")
        self.text.tag_configure("neutral", foreground="#333333")

        self.clear()

    def clear(self) -> None:
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert(
            tk.END,
            self.window.tr(
                "koch.comparison.placeholder",
                "The corrected copy appears here after scoring.",
            ),
            ("neutral",),
        )
        self.text.xview_moveto(0.0)
        self.text.configure(state=tk.DISABLED)

    def _comparison_cell(self, char_result: Any) -> tuple[str, str]:
        result_name = str(getattr(char_result, "result", "") or "")
        target_char = getattr(char_result, "target_char", None)
        entered_char = getattr(char_result, "entered_char", None)

        if result_name == "correct":
            return str(target_char or entered_char or ""), "correct"

        if result_name == "deletion":
            return str(target_char or "·"), "missing"

        if result_name == "insertion":
            return str(entered_char or "·"), "extra"

        if result_name == "substitution":
            return str(target_char or entered_char or "·"), "wrong"

        return str(target_char or entered_char or "·"), "wrong"

    def show_result(self, result: Any) -> None:
        cells: list[tuple[str, str]] = []

        for char_result in getattr(result, "character_results", []) or []:
            value, tag = self._comparison_cell(char_result)
            if value:
                cells.append((value, tag))

        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        if not cells:
            self.text.insert(
                tk.END,
                self.window.tr(
                    "koch.comparison.no_data",
                    "No comparison data is available for this result.",
                ),
                ("neutral",),
            )
            self.text.xview_moveto(0.0)
            self.text.configure(state=tk.DISABLED)
            return

        for value, tag in cells:
            self.text.insert(tk.END, value, (tag,))

        self.text.xview_moveto(0.0)
        self.text.configure(state=tk.DISABLED)
