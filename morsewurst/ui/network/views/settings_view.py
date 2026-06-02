# ============================================================
# morsewurst/ui/network/views/settings_view.py
# ============================================================

from __future__ import annotations

import tkinter as tk

import morsewurst.config as config
from morsewurst.core.logging_service import log_event
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
        if str(getattr(self, "settings_view_tab", "") or "") not in {"general", "audio"}:
            self.settings_view_tab = "general"

        self._clear_content()
        self._render_footer()

        panel = make_panel(self.content, padx=22, pady=20)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(3, weight=1)

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
        ).grid(row=1, column=0, sticky="ew", pady=(4, 12))

        tabs = tk.Frame(panel, background=MatrixTheme.panel)
        tabs.grid(row=2, column=0, sticky="w", pady=(0, 16))

        self._settings_tab_button(
            tabs,
            key="general",
            text=self.tr("network.settings.tabs.general"),
        ).pack(side=tk.LEFT)

        self._settings_tab_button(
            tabs,
            key="audio",
            text=self.tr("network.settings.tabs.audio"),
        ).pack(side=tk.LEFT, padx=(8, 0))

        body = tk.Frame(panel, background=MatrixTheme.panel)
        body.grid(row=3, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        if self.settings_view_tab == "audio":
            self._render_audio_settings_tab(self._settings_scroll_area(body))
        else:
            self._render_general_settings_tab(body)

        buttons = tk.Frame(panel, background=MatrixTheme.panel)
        buttons.grid(row=4, column=0, sticky="w", pady=(22, 0))

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

    def _settings_tab_button(self, parent: tk.Misc, *, key: str, text: str) -> tk.Button:
        selected = self.settings_view_tab == key
        return tk.Button(
            parent,
            text=text,
            command=lambda tab=key: self._select_settings_tab(tab),
            font=MatrixTheme.heading_font,
            fg=MatrixTheme.panel if selected else MatrixTheme.accent,
            bg=MatrixTheme.accent if selected else MatrixTheme.input_bg,
            activeforeground=MatrixTheme.panel,
            activebackground=MatrixTheme.accent,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=6,
            highlightthickness=1,
            highlightbackground=MatrixTheme.border,
            highlightcolor=MatrixTheme.accent,
            cursor="hand2",
        )

    def _select_settings_tab(self, key: str) -> None:
        tab = str(key or "general").strip().lower()
        self.settings_view_tab = tab if tab in {"general", "audio"} else "general"
        self.show_settings_view()

    def _settings_scroll_area(self, parent: tk.Misc) -> tk.Frame:
        """Return a scrollable Matrix-themed content frame for long settings tabs."""

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        container = tk.Frame(parent, background=MatrixTheme.panel)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        canvas = tk.Canvas(
            container,
            background=MatrixTheme.panel,
            highlightthickness=0,
            bd=0,
        )
        canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Canvas(
            container,
            width=14,
            background=MatrixTheme.input_bg,
            highlightthickness=1,
            highlightbackground=MatrixTheme.border,
            bd=0,
        )
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(8, 0))

        thumb_id = scrollbar.create_rectangle(
            3,
            3,
            11,
            28,
            fill=MatrixTheme.accent,
            outline=MatrixTheme.accent,
            state="hidden",
        )
        scroll_state = {
            "first": 0.0,
            "last": 1.0,
            "drag_y": 0.0,
            "drag_first": 0.0,
        }

        def _set_scrollbar(first: object, last: object) -> None:
            try:
                first_value = max(0.0, min(1.0, float(first)))
                last_value = max(first_value, min(1.0, float(last)))
            except Exception:
                first_value = 0.0
                last_value = 1.0

            scroll_state["first"] = first_value
            scroll_state["last"] = last_value

            height = max(1, int(scrollbar.winfo_height()))
            visible_fraction = max(0.0, min(1.0, last_value - first_value))

            if height <= 1 or visible_fraction >= 0.999:
                scrollbar.itemconfigure(thumb_id, state="hidden")
                return

            thumb_height = max(26, int(round(visible_fraction * height)))
            thumb_height = min(height, thumb_height)
            y1 = int(round(first_value * height))
            y1 = max(1, min(height - thumb_height - 1, y1))
            y2 = max(y1 + thumb_height, y1 + 1)

            scrollbar.itemconfigure(thumb_id, state="normal")
            scrollbar.coords(thumb_id, 3, y1, 11, y2)

        canvas.configure(yscrollcommand=_set_scrollbar)

        inner = tk.Frame(canvas, background=MatrixTheme.panel)
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _sync_scrollregion(_event: tk.Event | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            _set_scrollbar(*canvas.yview())

        def _sync_inner_width(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=max(1, int(event.width)))
            _set_scrollbar(*canvas.yview())

        def _scrollbar_moveto_from_y(y_position: float) -> None:
            height = max(1, int(scrollbar.winfo_height()))
            first_value = float(scroll_state["first"])
            last_value = float(scroll_state["last"])
            visible_fraction = max(0.001, min(1.0, last_value - first_value))
            thumb_height = max(26, int(round(visible_fraction * height)))
            usable_height = max(1, height - thumb_height)
            fraction = (float(y_position) - (thumb_height / 2.0)) / float(usable_height)
            canvas.yview_moveto(max(0.0, min(1.0, fraction)))

        def _scrollbar_button(event: tk.Event) -> str:
            scroll_state["drag_y"] = float(event.y)
            scroll_state["drag_first"] = float(scroll_state["first"])
            _scrollbar_moveto_from_y(float(event.y))
            return "break"

        def _scrollbar_drag(event: tk.Event) -> str:
            height = max(1, int(scrollbar.winfo_height()))
            visible_fraction = max(
                0.001,
                min(1.0, float(scroll_state["last"]) - float(scroll_state["first"])),
            )
            thumb_height = max(26, int(round(visible_fraction * height)))
            usable_height = max(1, height - thumb_height)
            delta = float(event.y) - float(scroll_state["drag_y"])
            fraction = float(scroll_state["drag_first"]) + (delta / float(usable_height))
            canvas.yview_moveto(max(0.0, min(1.0, fraction)))
            return "break"

        def _on_mousewheel(event: tk.Event) -> str | None:
            bounds = canvas.bbox("all")
            if not bounds or bounds[3] <= canvas.winfo_height():
                return None

            delta = int(getattr(event, "delta", 0) or 0)
            if delta:
                canvas.yview_scroll(-1 * int(delta / 120), "units")
                return "break"
            return None

        def _bind_mousewheel(_event: tk.Event) -> None:
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(_event: tk.Event) -> None:
            canvas.unbind_all("<MouseWheel>")

        inner.bind("<Configure>", _sync_scrollregion)
        canvas.bind("<Configure>", _sync_inner_width)
        scrollbar.bind("<Button-1>", _scrollbar_button)
        scrollbar.bind("<B1-Motion>", _scrollbar_drag)
        scrollbar.bind("<Configure>", lambda _event: _set_scrollbar(*canvas.yview()))
        container.bind("<Enter>", _bind_mousewheel)
        container.bind("<Leave>", _unbind_mousewheel)

        return inner

    def _settings_help_wraplength(self, parent: tk.Misc) -> int:
        try:
            width = int(parent.winfo_width())
        except Exception:
            width = 0

        if width > 120:
            return max(320, min(560, width - 24))

        return 500

    def _render_general_settings_tab(self, parent: tk.Misc) -> None:
        columns = self._settings_columns(parent)
        left = columns["left"]
        right = columns["right"]

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
            self.tr("network.settings.reception_buffer.title"),
        )

        self._settings_scale_field(
            left,
            row=2,
            title=self.tr("network.settings.jitter_buffer.title"),
            help_text=self.tr("network.settings.jitter_buffer.help"),
            variable=self.jitter_buffer_var,
            minimum=250,
            maximum=5000,
            resolution=50,
            suffix="ms",
        )

        self._section_title(
            left,
            3,
            self.tr("network.settings.local_network_mode.title"),
        )

        network_toggles = tk.Frame(left, background=MatrixTheme.panel)
        network_toggles.grid(row=4, column=0, sticky="ew", pady=(8, 0))

        self._make_checkbutton(
            network_toggles,
            self.tr("network.settings.transmit_enabled"),
            self.transmit_enabled_var,
        ).pack(anchor="w")

        make_label(
            right,
            self.tr("network.settings.general.empty.title"),
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.panel,
        ).grid(row=0, column=0, sticky="w", pady=(2, 0))

        make_label(
            right,
            self.tr("network.settings.general.empty.help"),
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.panel,
            wraplength=self._settings_help_wraplength(right),
        ).grid(row=1, column=0, sticky="ew", pady=(2, 0))

    def _render_audio_settings_tab(self, parent: tk.Misc) -> None:
        columns = self._settings_columns(parent)
        left = columns["left"]
        right = columns["right"]

        self._section_title(
            left,
            0,
            self.tr("network.settings.audio_playback.title"),
        )

        self._settings_text_field(
            left,
            row=1,
            title=self.tr("network.settings.tone_frequency.title"),
            help_text=self.tr("network.settings.tone_frequency.help"),
            variable=self.frequency_var,
            width=16,
            suffix="Hz",
        )

        self._settings_scale_field(
            left,
            row=2,
            title=self.tr("network.settings.volume.title"),
            help_text=self.tr("network.settings.volume.help"),
            variable=self.volume_percent_var,
            minimum=0,
            maximum=100,
            resolution=1,
            suffix="%",
        )

        audio_toggles = tk.Frame(left, background=MatrixTheme.panel)
        audio_toggles.grid(row=3, column=0, sticky="ew", pady=(0, 14))

        self._make_checkbutton(
            audio_toggles,
            self.tr("network.settings.playback_enabled"),
            self.playback_enabled_var,
        ).pack(anchor="w")

        self._section_title(
            left,
            4,
            self.tr("network.settings.radio_noise.title"),
        )

        radio_noise_toggles = tk.Frame(left, background=MatrixTheme.panel)
        radio_noise_toggles.grid(row=5, column=0, sticky="ew", pady=(8, 8))

        self._make_checkbutton(
            radio_noise_toggles,
            self.tr("network.settings.radio_noise.enabled"),
            self.radio_noise_enabled_var,
        ).pack(anchor="w")

        self._settings_profile_field(
            left,
            row=6,
            title=self.tr("network.settings.radio_noise.profile.title"),
            help_text=self.tr("network.settings.radio_noise.profile.help"),
            variable=self.radio_noise_profile_var,
            options=(
                ("light", self.tr("network.settings.radio_noise.profile.light")),
                ("radio", self.tr("network.settings.radio_noise.profile.radio")),
                ("dx", self.tr("network.settings.radio_noise.profile.dx")),
            ),
        )

        self._settings_profile_field(
            left,
            row=7,
            title=self.tr("network.settings.radio_noise.tone.title"),
            help_text=self.tr("network.settings.radio_noise.tone.help"),
            variable=self.radio_noise_tone_var,
            options=(
                ("normal", self.tr("network.settings.radio_noise.tone.normal")),
                ("low", self.tr("network.settings.radio_noise.tone.low")),
                ("deep", self.tr("network.settings.radio_noise.tone.deep")),
            ),
        )

        self._settings_scale_field(
            left,
            row=8,
            title=self.tr("network.settings.radio_noise.volume.title"),
            help_text=self.tr("network.settings.radio_noise.volume.help"),
            variable=self.radio_noise_volume_percent_var,
            minimum=0,
            maximum=30,
            resolution=1,
            suffix="%",
        )

        self._section_title(
            right,
            0,
            self.tr("network.settings.radio_noise.tx_ducking.title"),
        )

        tx_toggles = tk.Frame(right, background=MatrixTheme.panel)
        tx_toggles.grid(row=1, column=0, sticky="ew", pady=(8, 8))

        self._make_checkbutton(
            tx_toggles,
            self.tr("network.settings.radio_noise.tx_ducking.enabled"),
            self.radio_noise_tx_ducking_enabled_var,
        ).pack(anchor="w")

        self._settings_scale_field(
            right,
            row=2,
            title=self.tr("network.settings.radio_noise.ducking.depth.title"),
            help_text=self.tr("network.settings.radio_noise.tx_ducking.depth.help"),
            variable=self.radio_noise_tx_ducking_depth_percent_var,
            minimum=0,
            maximum=95,
            resolution=1,
            suffix="%",
        )

        self._settings_scale_field(
            right,
            row=3,
            title=self.tr("network.settings.radio_noise.ducking.attack.title"),
            help_text=self.tr("network.settings.radio_noise.tx_ducking.attack.help"),
            variable=self.radio_noise_tx_ducking_attack_ms_var,
            minimum=1,
            maximum=500,
            resolution=1,
            suffix="ms",
        )

        self._settings_scale_field(
            right,
            row=4,
            title=self.tr("network.settings.radio_noise.ducking.hold.title"),
            help_text=self.tr("network.settings.radio_noise.tx_ducking.hold.help"),
            variable=self.radio_noise_tx_ducking_hold_ms_var,
            minimum=1,
            maximum=1500,
            resolution=1,
            suffix="ms",
        )

        self._settings_scale_field(
            right,
            row=5,
            title=self.tr("network.settings.radio_noise.ducking.release.title"),
            help_text=self.tr("network.settings.radio_noise.tx_ducking.release.help"),
            variable=self.radio_noise_tx_ducking_release_ms_var,
            minimum=1,
            maximum=2000,
            resolution=1,
            suffix="ms",
        )

        self._section_title(
            right,
            6,
            self.tr("network.settings.radio_noise.rx_ducking.title"),
        )

        rx_toggles = tk.Frame(right, background=MatrixTheme.panel)
        rx_toggles.grid(row=7, column=0, sticky="ew", pady=(8, 8))

        self._make_checkbutton(
            rx_toggles,
            self.tr("network.settings.radio_noise.rx_ducking.enabled"),
            self.radio_noise_rx_ducking_enabled_var,
        ).pack(anchor="w")

        self._settings_scale_field(
            right,
            row=8,
            title=self.tr("network.settings.radio_noise.ducking.depth.title"),
            help_text=self.tr("network.settings.radio_noise.rx_ducking.depth.help"),
            variable=self.radio_noise_rx_ducking_depth_percent_var,
            minimum=0,
            maximum=95,
            resolution=1,
            suffix="%",
        )

        self._settings_scale_field(
            right,
            row=9,
            title=self.tr("network.settings.radio_noise.ducking.attack.title"),
            help_text=self.tr("network.settings.radio_noise.rx_ducking.attack.help"),
            variable=self.radio_noise_rx_ducking_attack_ms_var,
            minimum=1,
            maximum=500,
            resolution=1,
            suffix="ms",
        )

        self._settings_scale_field(
            right,
            row=10,
            title=self.tr("network.settings.radio_noise.ducking.hold.title"),
            help_text=self.tr("network.settings.radio_noise.rx_ducking.hold.help"),
            variable=self.radio_noise_rx_ducking_hold_ms_var,
            minimum=1,
            maximum=1500,
            resolution=1,
            suffix="ms",
        )

        self._settings_scale_field(
            right,
            row=11,
            title=self.tr("network.settings.radio_noise.ducking.release.title"),
            help_text=self.tr("network.settings.radio_noise.rx_ducking.release.help"),
            variable=self.radio_noise_rx_ducking_release_ms_var,
            minimum=1,
            maximum=2000,
            resolution=1,
            suffix="ms",
        )

    def _settings_columns(self, parent: tk.Misc) -> dict[str, tk.Frame]:
        columns = tk.Frame(parent, background=MatrixTheme.panel)
        columns.grid(row=0, column=0, sticky="nsew")
        columns.columnconfigure(0, weight=1, uniform="settings_columns")
        columns.columnconfigure(1, weight=1, uniform="settings_columns")
        columns.rowconfigure(0, weight=1)

        left = tk.Frame(columns, background=MatrixTheme.panel)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        left.columnconfigure(0, weight=1)

        right = tk.Frame(columns, background=MatrixTheme.panel)
        right.grid(row=0, column=1, sticky="nsew", padx=(18, 0))
        right.columnconfigure(0, weight=1)

        return {"left": left, "right": right}

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
            wraplength=self._settings_help_wraplength(parent),
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
            wraplength=self._settings_help_wraplength(parent),
        ).grid(row=current_row, column=0, sticky="ew", pady=(2, 6))
        current_row += 1

        slider_row = tk.Frame(box, background=MatrixTheme.panel)
        slider_row.grid(row=current_row, column=0, sticky="w")

        value_var = tk.StringVar(value=f"{int(variable.get())} {suffix}")

        def _update_value_label(*_args: object) -> None:
            try:
                value_var.set(f"{int(variable.get())} {suffix}")
            except Exception:
                value_var.set(f"0 {suffix}")

        try:
            variable.trace_add("write", _update_value_label)
        except Exception:
            pass

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

    def _settings_profile_field(
        self,
        parent: tk.Misc,
        *,
        row: int,
        title: str,
        help_text: str,
        variable: tk.StringVar,
        options: tuple[tuple[str, str], ...],
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
            wraplength=self._settings_help_wraplength(parent),
        ).grid(row=1, column=0, sticky="ew", pady=(2, 6))

        options_row = tk.Frame(box, background=MatrixTheme.panel)
        options_row.grid(row=2, column=0, sticky="w")

        for index, (value, label) in enumerate(options):
            tk.Radiobutton(
                options_row,
                text=label,
                value=value,
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
            ).pack(side=tk.LEFT, padx=(0 if index == 0 else 12, 0))

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
        log_event(
            "network",
            "network.settings.defaults_reset",
            message="Network settings were reset to defaults from the UI.",
            context={"server_uri": self._server_uri()},
        )
        current_callsign = self.callsign_var.get()
        self.transmit_enabled_var.set(True)
        self.playback_enabled_var.set(True)
        self.frequency_var.set("650")
        self.volume_percent_var.set(100)
        self.jitter_buffer_var.set(750)

        self.radio_noise_enabled_var.set(bool(getattr(config, "NETWORK_RADIO_NOISE_ENABLED_DEFAULT", False)))
        self.radio_noise_volume_percent_var.set(int(getattr(config, "NETWORK_RADIO_NOISE_VOLUME_PERCENT_DEFAULT", 5)))
        self.radio_noise_profile_var.set(str(getattr(config, "NETWORK_RADIO_NOISE_PROFILE_DEFAULT", "radio")))
        self.radio_noise_tone_var.set(str(getattr(config, "NETWORK_RADIO_NOISE_TONE_DEFAULT", "low")))

        self.radio_noise_tx_ducking_enabled_var.set(bool(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_ENABLED", True)))
        self.radio_noise_tx_ducking_depth_percent_var.set(int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_DEPTH_PERCENT", 85)))
        self.radio_noise_tx_ducking_attack_ms_var.set(int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_ATTACK_MS", 60)))
        self.radio_noise_tx_ducking_hold_ms_var.set(int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_HOLD_MS", 350)))
        self.radio_noise_tx_ducking_release_ms_var.set(int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_RELEASE_MS", 500)))

        self.radio_noise_rx_ducking_enabled_var.set(bool(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_ENABLED", False)))
        self.radio_noise_rx_ducking_depth_percent_var.set(int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_DEPTH_PERCENT", 45)))
        self.radio_noise_rx_ducking_attack_ms_var.set(int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_ATTACK_MS", 80)))
        self.radio_noise_rx_ducking_hold_ms_var.set(int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_HOLD_MS", 250)))
        self.radio_noise_rx_ducking_release_ms_var.set(int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_RELEASE_MS", 450)))

        self.callsign_var.set(current_callsign)
        self.save_settings(last_room=self.connected_room_key or self.settings.last_room)
        self._show_notice(
            self.tr("network.settings.defaults_restored"),
            "success",
        )
