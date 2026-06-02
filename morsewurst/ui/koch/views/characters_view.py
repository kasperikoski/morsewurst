# ============================================================
# morsewurst/ui/koch/views/characters_view.py
# ============================================================

from __future__ import annotations

from math import ceil
from typing import Any

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from morsewurst.koch.models import KochSettings
from morsewurst.koch.sequence import active_chars_for_stage, koch_sequence_by_key


class KochCharactersView(ttk.LabelFrame):
    """Character unlock grid for the selected Koch sequence."""

    def __init__(self, parent: tk.Misc, window: Any) -> None:
        super().__init__(parent, text=window.tr("koch.characters.title", "Characters"))
        self.window = window
        self.sequence_var = tk.StringVar(value="")
        self.progress_var = tk.StringVar(value="")
        self.grid_frame = ttk.Frame(self)
        self._last_settings: KochSettings | None = None
        self._resize_after_id: str | None = None
        self._last_render_signature: tuple[str, int, int, str] | None = None
        self._build()

    def _build(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=10, pady=(8, 4))

        self.progress_label = ttk.Label(header, textvariable=self.progress_var)
        self.progress_label.pack(side=tk.LEFT)

        self.sequence_label = ttk.Label(header, textvariable=self.sequence_var)
        self.sequence_label.pack(side=tk.RIGHT)

        self.grid_frame.pack(fill=tk.X, padx=10, pady=(4, 10))
        self.grid_frame.bind("<Configure>", self._on_grid_configure, add="+")

    def update_progress_summary(self, settings: KochSettings) -> None:
        sequence = koch_sequence_by_key(settings.sequence_key)
        active = active_chars_for_stage(sequence, settings.stage_index)
        self.sequence_var.set(self.window.sequence_display_label(sequence))
        self.progress_var.set(
            self.window.tr(
                "koch.progress.summary_compact",
                "{active}/{total} characters unlocked",
                active=len(active),
                total=len(sequence.characters),
            )
        )

    def update_character_grid(self, settings: KochSettings) -> None:
        self._last_settings = settings
        self._render_character_grid(settings, force=True)

    def _on_grid_configure(self, _event: tk.Event) -> None:
        if self._last_settings is None:
            return

        if self._resize_after_id is not None:
            try:
                self.after_cancel(self._resize_after_id)
            except tk.TclError:
                pass

        self._resize_after_id = self.after(80, self._rerender_after_resize)

    def _rerender_after_resize(self) -> None:
        self._resize_after_id = None
        if self._last_settings is not None:
            self._render_character_grid(self._last_settings, force=False)

    def _character_cell_width(self) -> int:
        try:
            font = tkfont.Font(font=("TkDefaultFont", 16))
            return max(24, font.measure("W")) + 18
        except tk.TclError:
            return 34

    def _column_count(self, total_chars: int) -> int:
        if total_chars <= 0:
            return 1

        desired_columns = max(1, ceil(float(total_chars) / 2.0))
        available_width = self.grid_frame.winfo_width()

        if available_width <= 1:
            available_width = max(1, self.winfo_width() - 24)

        fit_columns = max(1, int(available_width // self._character_cell_width()))
        return max(1, min(desired_columns, fit_columns))

    def _render_character_grid(self, settings: KochSettings, *, force: bool) -> None:
        sequence = koch_sequence_by_key(settings.sequence_key)
        active_chars = active_chars_for_stage(sequence, settings.stage_index)
        active = set(active_chars)
        columns = self._column_count(len(sequence.characters))
        signature = (sequence.key, int(settings.stage_index), columns, active_chars)

        if not force and signature == self._last_render_signature:
            return

        self._last_render_signature = signature

        for child in self.grid_frame.winfo_children():
            child.destroy()

        for column in range(columns):
            self.grid_frame.columnconfigure(column, weight=0)

        for index, char in enumerate(sequence.characters):
            row = index // columns
            column = index % columns
            label = tk.Label(
                self.grid_frame,
                text=char,
                font=("TkDefaultFont", 16),
                fg="#111111" if char in active else "#b8b8b8",
                padx=5,
                pady=2,
            )
            label.grid(row=row, column=column, sticky=tk.W, padx=(0, 7), pady=2)
