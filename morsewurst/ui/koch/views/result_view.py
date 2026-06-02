# ============================================================
# morsewurst/ui/koch/views/result_view.py
# ============================================================

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk


class KochResultView(ttk.LabelFrame):
    """Latest Koch result panel."""

    def __init__(self, parent: tk.Misc, window: Any) -> None:
        super().__init__(parent, text=window.tr("koch.result.title", "Latest result"))
        self.window = window
        self.result_var = tk.StringVar(value=window.tr("koch.result.placeholder", "No result yet."))
        self._build()

    def _build(self) -> None:
        label = ttk.Label(
            self,
            textvariable=self.result_var,
            justify=tk.LEFT,
            anchor=tk.NW,
            wraplength=430,
        )
        label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
