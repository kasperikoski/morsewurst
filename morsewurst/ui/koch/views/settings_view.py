# ============================================================
# morsewurst/ui/koch/views/settings_view.py
# ============================================================

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk

from morsewurst.koch.models import maximum_koch_target_chars


class KochSettingsView(ttk.Frame):
    """Main Koch receive-practice settings shown inside the Koch window."""

    def __init__(self, parent: tk.Misc, window: Any) -> None:
        super().__init__(parent)
        self.window = window

        self.columnconfigure(0, weight=1)
        self._build()

    def _field_frame(
        self,
        parent: ttk.Frame,
        *,
        label_key: str,
        fallback: str,
        column: int,
    ) -> ttk.Frame:
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=column, sticky=tk.NSEW, padx=(0 if column == 0 else 8, 0))
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text=self.window.tr(label_key, fallback)).grid(
            row=0,
            column=0,
            sticky=tk.W,
            pady=(0, 2),
        )
        return frame

    def _grid_field_widget(self, field: ttk.Frame, widget: tk.Widget) -> None:
        widget.grid(row=1, column=0, sticky=tk.EW)

    def _build(self) -> None:
        top_row = ttk.Frame(self)
        top_row.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(8, 6))

        bottom_row = ttk.Frame(self)
        bottom_row.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=(0, 8))

        for column in range(3):
            top_row.columnconfigure(column, weight=1, uniform="koch_settings_top")

        for column in range(5):
            bottom_row.columnconfigure(column, weight=1, uniform="koch_settings_bottom")

        mode_field = self._field_frame(
            top_row,
            label_key="koch.settings.mode",
            fallback="Mode",
            column=0,
        )
        self.mode_combo = ttk.Combobox(
            mode_field,
            textvariable=self.window.mode_label_var,
            values=list(self.window.mode_label_to_key.keys()),
            state="readonly",
            width=18,
        )
        self._grid_field_widget(mode_field, self.mode_combo)
        self.mode_combo.bind("<<ComboboxSelected>>", lambda _event: self.window.on_mode_changed())

        sequence_field = self._field_frame(
            top_row,
            label_key="koch.settings.sequence",
            fallback="Sequence",
            column=1,
        )
        self.sequence_combo = ttk.Combobox(
            sequence_field,
            textvariable=self.window.sequence_var,
            values=list(self.window.sequence_label_to_key.keys()),
            state="readonly",
            width=18,
        )
        self._grid_field_widget(sequence_field, self.sequence_combo)
        self.sequence_combo.bind("<<ComboboxSelected>>", self.window.on_sequence_changed)

        stage_field = self._field_frame(
            top_row,
            label_key="koch.settings.stage",
            fallback="Stage",
            column=2,
        )
        self.stage_spin = ttk.Spinbox(
            stage_field,
            from_=1,
            to=54,
            textvariable=self.window.stage_var,
            width=8,
            command=self.window.manual_setting_changed,
        )
        self._grid_field_widget(stage_field, self.stage_spin)
        self.stage_spin.bind("<KeyRelease>", lambda _event: self.window.manual_setting_changed())

        char_wpm_field = self._field_frame(
            bottom_row,
            label_key="koch.settings.char_wpm",
            fallback="Char WPM",
            column=0,
        )
        self.char_wpm_spin = ttk.Spinbox(
            char_wpm_field,
            from_=5,
            to=80,
            textvariable=self.window.character_wpm_var,
            width=8,
            command=self.window.manual_setting_changed,
        )
        self._grid_field_widget(char_wpm_field, self.char_wpm_spin)
        self.char_wpm_spin.bind("<KeyRelease>", lambda _event: self.window.manual_setting_changed())

        effective_wpm_field = self._field_frame(
            bottom_row,
            label_key="koch.settings.effective_wpm",
            fallback="Effective WPM",
            column=1,
        )
        self.effective_wpm_spin = ttk.Spinbox(
            effective_wpm_field,
            from_=5,
            to=80,
            textvariable=self.window.effective_wpm_var,
            width=8,
            command=self.window.manual_setting_changed,
        )
        self._grid_field_widget(effective_wpm_field, self.effective_wpm_spin)
        self.effective_wpm_spin.bind("<KeyRelease>", lambda _event: self.window.manual_setting_changed())

        tone_field = self._field_frame(
            bottom_row,
            label_key="koch.settings.tone",
            fallback="Tone Hz",
            column=2,
        )
        self.tone_spin = ttk.Spinbox(
            tone_field,
            from_=100,
            to=2000,
            increment=25,
            textvariable=self.window.tone_hz_var,
            width=8,
            command=self.window.manual_setting_changed,
        )
        self._grid_field_widget(tone_field, self.tone_spin)
        self.tone_spin.bind("<KeyRelease>", lambda _event: self.window.manual_setting_changed())

        volume_field = self._field_frame(
            bottom_row,
            label_key="koch.settings.volume",
            fallback="Volume %",
            column=3,
        )
        self.volume_spin = ttk.Spinbox(
            volume_field,
            from_=0,
            to=100,
            increment=5,
            textvariable=self.window.volume_percent_var,
            width=8,
            command=self.window.manual_setting_changed,
        )
        self._grid_field_widget(volume_field, self.volume_spin)
        self.volume_spin.bind("<KeyRelease>", lambda _event: self.window.manual_setting_changed())

        target_chars_field = self._field_frame(
            bottom_row,
            label_key="koch.settings.target_chars",
            fallback="Target chars",
            column=4,
        )
        self.target_chars_spin = ttk.Spinbox(
            target_chars_field,
            from_=30,
            to=maximum_koch_target_chars(),
            increment=10,
            textvariable=self.window.target_chars_var,
            width=8,
            command=self.window.manual_setting_changed,
        )
        self._grid_field_widget(target_chars_field, self.target_chars_spin)
        self.target_chars_spin.bind("<KeyRelease>", lambda _event: self.window.manual_setting_changed())

        self.refresh_mode_controls()

    def set_stage_bounds(self, max_stage: int) -> None:
        self.stage_spin.configure(to=max(1, int(max_stage)))

    def set_target_chars_minimum(self, minimum: int) -> None:
        self.target_chars_spin.configure(from_=max(1, int(minimum)))

    def set_target_chars_maximum(self, maximum: int) -> None:
        self.target_chars_spin.configure(to=max(1, int(maximum)))

    def refresh_mode_controls(self) -> None:
        mode = self.window.mode_key()
        readonly_stage = mode in {"guided", "full_charset"}
        self.stage_spin.configure(state="disabled" if readonly_stage else "normal")
