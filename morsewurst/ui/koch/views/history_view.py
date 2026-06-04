# ============================================================
# morsewurst/ui/koch/views/history_view.py
# ============================================================

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk


def _row_value(row: Any, key: str, default: Any = "") -> Any:
    try:
        return row[key]
    except Exception:
        return default


def _short_text(value: Any, limit: int = 80) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)]}…"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


class KochHistoryView(ttk.LabelFrame):
    """Recent Koch session table."""

    def __init__(self, parent: tk.Misc, window: Any) -> None:
        super().__init__(parent, text=window.tr("koch.history.title", "Recent Koch sessions"))
        self.window = window
        self._build()

    def _build(self) -> None:
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        columns = (
            "stage",
            "accuracy",
            "wpm",
            "target_chars",
            "duration",
            "entered",
            "target",
        )
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=8)
        headings = {
            "stage": self.window.tr("koch.history.stage", "Stage"),
            "accuracy": self.window.tr("koch.history.accuracy", "Accuracy"),
            "wpm": self.window.tr("koch.history.wpm", "Farnsworth/char WPM"),
            "target_chars": self.window.tr("koch.history.target_chars", "Chars"),
            "duration": self.window.tr("koch.history.duration", "Duration"),
            "entered": self.window.tr("koch.history.entered", "Entered"),
            "target": self.window.tr("koch.history.target", "Target"),
        }
        widths = {
            "stage": 70,
            "accuracy": 95,
            "wpm": 150,
            "target_chars": 80,
            "duration": 90,
            "entered": 260,
            "target": 260,
        }

        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                anchor="center" if column not in {"entered", "target"} else "w",
                stretch=column in {"entered", "target"},
            )

        scroll_y = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        scroll_x = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tree.grid(row=0, column=0, sticky=tk.NSEW, padx=(10, 0), pady=(10, 0))
        scroll_y.grid(row=0, column=1, sticky=tk.NS, padx=(0, 10), pady=(10, 0))
        scroll_x.grid(row=1, column=0, sticky=tk.EW, padx=(10, 0), pady=(0, 10))

    def load_recent_sessions(self, rows: list[Any]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in rows:
            accuracy = _safe_float(_row_value(row, "accuracy", 0.0))
            effective_wpm = _safe_int(_row_value(row, "effective_wpm", 0))
            character_wpm = _safe_int(_row_value(row, "character_wpm", 0))
            target_length = _safe_int(_row_value(row, "target_length", 0))
            duration_ms = _safe_int(_row_value(row, "duration_ms", 0))

            self.tree.insert(
                "",
                tk.END,
                values=(
                    _row_value(row, "stage_index", ""),
                    f"{accuracy:.1f} %",
                    f"{effective_wpm}/{character_wpm}",
                    target_length,
                    f"{duration_ms / 1000.0:.1f} s",
                    _short_text(_row_value(row, "entered_text", "")),
                    _short_text(_row_value(row, "target_text", "")),
                ),
            )


class KochProblemCharactersView(ttk.LabelFrame):
    """Most difficult Koch receive-practice characters."""

    def __init__(self, parent: tk.Misc, window: Any) -> None:
        super().__init__(parent, text=window.tr("koch.problem_characters.title", "Most difficult characters"))
        self.window = window
        self._build()

    def _build(self) -> None:
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        columns = ("char", "attempts", "errors", "accuracy")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=8)

        definitions = [
            ("char", self.window.tr("koch.problem_characters.char", "Char"), 65),
            ("attempts", self.window.tr("koch.problem_characters.attempts", "Attempts"), 80),
            ("errors", self.window.tr("koch.problem_characters.errors", "Errors"), 70),
            ("accuracy", self.window.tr("koch.problem_characters.accuracy", "Accuracy"), 90),
        ]

        for column, title, width in definitions:
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, anchor="center", stretch=True)

        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=0, column=0, sticky=tk.NSEW, padx=(10, 0), pady=10)
        scrollbar.grid(row=0, column=1, sticky=tk.NS, padx=(0, 10), pady=10)

    def load_character_stats(self, rows: list[Any]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in rows:
            attempts = _safe_int(_row_value(row, "attempts", 0))
            correct = _safe_int(_row_value(row, "correct", 0))
            errors = _safe_int(_row_value(row, "errors", 0))
            accuracy = 0.0 if attempts <= 0 else (correct / attempts) * 100.0

            self.tree.insert(
                "",
                tk.END,
                values=(
                    _row_value(row, "char", ""),
                    attempts,
                    errors,
                    f"{accuracy:.1f} %",
                ),
            )