# ============================================================
# morsewurst/ui/network/views/settings_view.py
# ============================================================

from __future__ import annotations

import tkinter as tk

from morsewurst.ui.network_matrix_theme import (
    MatrixTheme,
    make_button,
    make_entry,
    make_label,
    make_panel,
)

class SettingsViewMixin:
    def show_settings_view(self) -> None:
        self.current_view = "settings"
        self._clear_content()
        self._render_footer()

        panel = make_panel(self.content, padx=22, pady=20)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)

        make_label(
            panel,
            self.tr("network.settings.title"),
            font=("Consolas", 22, "bold"),
            foreground=MatrixTheme.accent,
        ).grid(row=0, column=0, sticky="w")

        make_label(
            panel,
            self.tr("network.settings.description"),
            foreground=MatrixTheme.text_dim,
            wraplength=980,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 18))

        columns = tk.Frame(panel, background=MatrixTheme.panel)
        columns.grid(row=2, column=0, sticky="nsew")
        columns.columnconfigure(0, weight=1, uniform="settings_columns")
        columns.columnconfigure(1, weight=1, uniform="settings_columns")
        columns.rowconfigure(0, weight=1)

        left = tk.Frame(columns, background=MatrixTheme.panel)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        left.columnconfigure(0, weight=1)

        right = tk.Frame(columns, background=MatrixTheme.panel)
        right.grid(row=0, column=1, sticky="nsew", padx=(18, 0))
        right.columnconfigure(0, weight=1)

        self._settings_text_field(
            left,
            row=0,
            title=self.tr("network.settings.callsign.title"),
            help_text=self.tr("network.settings.callsign.help"),
            variable=self.callsign_var,
            width=34,
        )

        self._section_title(
            left,
            1,
            self.tr("network.settings.audio_playback.title"),
        )

        self._settings_text_field(
            left,
            row=2,
            title=self.tr("network.settings.tone_frequency.title"),
            help_text=self.tr("network.settings.tone_frequency.help"),
            variable=self.frequency_var,
            width=16,
            suffix="Hz",
        )

        self._settings_scale_field(
            left,
            row=3,
            title=self.tr("network.settings.volume.title"),
            help_text=self.tr("network.settings.volume.help"),
            variable=self.volume_percent_var,
            minimum=0,
            maximum=100,
            resolution=1,
            suffix="%",
        )

        audio_toggles = tk.Frame(left, background=MatrixTheme.panel)
        audio_toggles.grid(row=4, column=0, sticky="ew", pady=(0, 14))

        self._make_checkbutton(
            audio_toggles,
            self.tr("network.settings.playback_enabled"),
            self.playback_enabled_var,
        ).pack(anchor="w")

        self._section_title(
            right,
            0,
            self.tr("network.settings.reception_buffer.title"),
        )

        self._settings_scale_field(
            right,
            row=1,
            title=self.tr("network.settings.jitter_buffer.title"),
            help_text=self.tr("network.settings.jitter_buffer.help"),
            variable=self.jitter_buffer_var,
            minimum=250,
            maximum=5000,
            resolution=50,
            suffix="ms",
        )

        self._section_title(
            right,
            2,
            self.tr("network.settings.local_network_mode.title"),
        )

        network_toggles = tk.Frame(right, background=MatrixTheme.panel)
        network_toggles.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        self._make_checkbutton(
            network_toggles,
            self.tr("network.settings.transmit_enabled"),
            self.transmit_enabled_var,
        ).pack(anchor="w")

        buttons = tk.Frame(panel, background=MatrixTheme.panel)
        buttons.grid(row=3, column=0, sticky="w", pady=(22, 0))

        make_button(
            buttons,
            self.tr("network.button.save"),
            self.save_settings,
        ).pack(side=tk.LEFT)

        make_button(
            buttons,
            self.tr("network.button.reset_to_defaults"),
            self.reset_playback_defaults,
        ).pack(side=tk.LEFT, padx=(10, 0))

        make_button(
            buttons,
            self.tr("network.button.back"),
            self.show_lobby_view if not self.connected_room_key else self.show_room_view,
        ).pack(side=tk.LEFT, padx=(10, 0))

    def _section_title(self, parent: tk.Misc, row: int, text: str) -> None:
        make_label(
            parent,
            text,
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.accent,
        ).grid(row=row, column=0, sticky="w", pady=(18, 0))

    def _settings_text_field(
        self,
        parent: tk.Misc,
        *,
        row: int,
        title: str,
        help_text: str,
        variable: tk.StringVar,
        width: int,
        suffix: str = "",
    ) -> None:
        box = tk.Frame(parent, background=MatrixTheme.panel)
        box.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        box.columnconfigure(0, weight=1)

        make_label(
            box,
            title,
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.text,
            background=MatrixTheme.panel,
        ).grid(row=0, column=0, sticky="w")

        make_label(
            box,
            help_text,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.panel,
            wraplength=760,
        ).grid(row=1, column=0, sticky="ew", pady=(2, 6))

        input_row = tk.Frame(box, background=MatrixTheme.panel)
        input_row.grid(row=2, column=0, sticky="w")

        make_entry(input_row, variable, width=width).pack(side=tk.LEFT)

        if suffix:
            make_label(
                input_row,
                suffix,
                foreground=MatrixTheme.text_dim,
                background=MatrixTheme.panel,
            ).pack(side=tk.LEFT, padx=(8, 0))

    def _settings_scale_field(
        self,
        parent: tk.Misc,
        *,
        row: int,
        title: str,
        help_text: str,
        variable: tk.IntVar,
        minimum: int,
        maximum: int,
        resolution: int,
        suffix: str,
    ) -> None:
        box = tk.Frame(parent, background=MatrixTheme.panel)
        box.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        box.columnconfigure(0, weight=1)

        current_row = 0

        if title:
            make_label(
                box,
                title,
                font=MatrixTheme.heading_font,
                foreground=MatrixTheme.text,
                background=MatrixTheme.panel,
            ).grid(row=current_row, column=0, sticky="w")
            current_row += 1

        make_label(
            box,
            help_text,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.panel,
            wraplength=760,
        ).grid(row=current_row, column=0, sticky="ew", pady=(2, 6))
        current_row += 1

        slider_row = tk.Frame(box, background=MatrixTheme.panel)
        slider_row.grid(row=current_row, column=0, sticky="w")

        value_var = tk.StringVar(value=f"{int(variable.get())} {suffix}")

        scale = tk.Scale(
            slider_row,
            from_=minimum,
            to=maximum,
            length=300,
            resolution=resolution,
            orient=tk.HORIZONTAL,
            variable=variable,
            showvalue=False,
            bg=MatrixTheme.panel,
            fg=MatrixTheme.text,
            activebackground=MatrixTheme.accent,
            highlightthickness=0,
            troughcolor=MatrixTheme.input_bg,
            bd=0,
            command=lambda _value: value_var.set(f"{int(variable.get())} {suffix}"),
        )
        scale.grid(row=0, column=0, sticky="w")

        make_label(
            slider_row,
            variable=value_var,
            font=MatrixTheme.mono_font,
            foreground=MatrixTheme.accent,
            background=MatrixTheme.panel,
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))

    def _make_checkbutton(
        self,
        parent: tk.Misc,
        text: str,
        variable: tk.BooleanVar,
    ) -> tk.Checkbutton:
        return tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            font=MatrixTheme.body_font,
            fg=MatrixTheme.text,
            bg=MatrixTheme.panel,
            activeforeground=MatrixTheme.accent,
            activebackground=MatrixTheme.panel,
            selectcolor=MatrixTheme.input_bg,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )

    def _back_from_settings(self) -> None:
        if self.connected_room_key or self.connected_room_id:
            self.show_room_view()
            return
        self.show_lobby_view()

    def reset_playback_defaults(self) -> None:
        self.frequency_var.set("650")
        self.volume_percent_var.set(100)
        self.jitter_buffer_var.set(750)
        self.save_settings(last_room=self.connected_room_key or self.settings.last_room)
        self._show_notice(
            self.tr("network.settings.defaults_restored"),
            "success",
        )