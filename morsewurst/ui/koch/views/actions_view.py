# ============================================================
# morsewurst/ui/koch/views/actions_view.py
# ============================================================

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk


class KochCountdownView(ttk.Frame):
    """Reserved countdown strip between settings and character grid."""

    def __init__(self, parent: tk.Misc, window: Any) -> None:
        super().__init__(parent)
        self.window = window
        self._label_text = ""
        self._progress = 0.0
        self.canvas = tk.Canvas(self, height=28, highlightthickness=0, borderwidth=0)
        self.canvas.pack(fill=tk.X, expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._redraw())
        self.set_idle()

    def set_countdown(self, seconds_remaining: float, progress: float) -> None:
        self._progress = max(0.0, min(100.0, float(progress)))
        self._label_text = self.window.tr(
            "koch.countdown.label",
            "Practice starts in {seconds}",
            seconds=f"{max(0.0, seconds_remaining):.1f} s",
        )
        self._redraw()

    def set_running(self) -> None:
        self._progress = 0.0
        self._label_text = ""
        self._redraw()

    def set_idle(self) -> None:
        self._progress = 0.0
        self._label_text = ""
        self._redraw()

    def _redraw(self) -> None:
        width = max(1, int(self.canvas.winfo_width()))
        height = max(1, int(self.canvas.winfo_height()))
        self.canvas.delete("all")

        right = max(0, width - 1)
        bottom = max(0, height - 5)
        self.canvas.create_rectangle(0, 4, right, bottom, outline="#b7b7b7", fill="#f5f5f5")

        fill_width = min(right, int(right * (self._progress / 100.0)))
        if fill_width > 0:
            self.canvas.create_rectangle(1, 5, fill_width, max(5, bottom - 1), outline="", fill="#7fc97f")

        if self._label_text:
            self.canvas.create_text(width // 2, height // 2, text=self._label_text, anchor=tk.CENTER)


class KochActionsView(ttk.LabelFrame):
    """Action buttons for Koch mode."""

    def __init__(self, parent: tk.Misc, window: Any) -> None:
        super().__init__(parent, text=window.tr("koch.actions.title", "Practice"))
        self.window = window
        self._build()
        self.set_idle()

    def _build(self) -> None:
        self.start_button = ttk.Button(
            self,
            text=self.window.tr("koch.button.start", "Start Koch practice"),
            command=lambda: self.window.app.koch_controller.start_session(self.window),
        )
        self.start_button.pack(fill=tk.X, padx=8, pady=(10, 4))

        self.stop_button = ttk.Button(
            self,
            text=self.window.tr("koch.button.stop", "Cancel practice"),
            command=self.window.stop_clicked,
        )
        self.stop_button.pack(fill=tk.X, padx=8, pady=4)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=8)

        self.close_button = ttk.Button(
            self,
            text=self.window.tr("koch.button.close", "Close"),
            command=self.window.on_close,
        )
        self.close_button.pack(fill=tk.X, padx=8, pady=(4, 10))

    def set_countdown(self) -> None:
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)

    def set_running(self) -> None:
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)

    def set_idle(self) -> None:
        self.start_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)