# ============================================================
# morsewurst/ui/network/views/room_view.py
# ============================================================

from __future__ import annotations

import tkinter as tk

from morsewurst.core.logging_service import log_event
from morsewurst.ui.network_matrix_theme import (
    MatrixTheme,
    make_button,
    make_label,
    make_panel,
    make_text_log,
)

class RoomViewMixin:
    def show_room_view(self) -> None:
        log_event(
            "network",
            "network.room.view_opened",
            message="Network room view opened.",
            context={
                "server_uri": self._server_uri(),
                "room_key": self.connected_room_key,
                "room_id": self.connected_room_id,
                "room_title": self.connected_room_title,
                "room_access": self.connected_room_access,
            },
        )
        self.current_view = "room"
        self._clear_content()
        self._render_footer()

        panel = make_panel(self.content, padx=22, pady=20)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(6, weight=1)

        make_label(
            panel,
            self.tr("network.room.view.connected"),
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.accent,
        ).grid(row=0, column=0, sticky="w")

        make_label(
            panel,
            self.connected_room_title or self.connected_room_id,
            font=("Consolas", 22, "bold"),
            foreground=MatrixTheme.text,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        details = make_panel(panel, padx=12, pady=10)
        details.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        details.columnconfigure(0, weight=1)
        details.columnconfigure(1, weight=1)

        self._room_detail_with_description(
            details,
            0,
            0,
            self.tr("network.room.view.room"),
            self.connected_room_title or self.connected_room_id or "-",
            self.connected_room_description,
        )

        self._detail_field(
            details,
            0,
            1,
            self.tr("network.room.view.access"),
            self.tr("network.room.view.access_private")
            if self.connected_room_access == "private"
            else self.tr("network.room.view.access_public"),
        )

        if self.connected_room_access == "private":
            self._detail_field(
                details,
                1,
                0,
                self.tr("network.room.view.room_id"),
                self.connected_room_id or "-",
            )
            self._detail_field(
                details,
                1,
                1,
                self.tr("network.room.view.room_password"),
                self.connected_room_password,
            )
        else:
            make_label(
                details,
                self.tr("network.room.view.public_no_password"),
                font=MatrixTheme.mono_font,
                foreground=MatrixTheme.text,
                background=MatrixTheme.panel,
                wraplength=360,
            ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(0, 8))

        controls = tk.Frame(panel, background=MatrixTheme.panel)
        controls.grid(row=3, column=0, sticky="ew", pady=(18, 12))

        make_button(
            controls,
            self.tr("network.button.leave_room"),
            self.disconnect,
        ).pack(side=tk.LEFT)

        make_button(
            controls,
            self.tr("network.button.server_info"),
            self.show_server_info_window,
        ).pack(side=tk.LEFT, padx=(10, 0))

        make_button(
            controls,
            self.tr("network.button.ping"),
            self._request_server_ping,
        ).pack(side=tk.LEFT, padx=(10, 0))

        make_button(
            controls,
            self.tr("network.button.settings"),
            self.show_settings_view,
        ).pack(side=tk.LEFT, padx=(10, 0))

        server_status_panel = make_panel(panel, padx=10, pady=8)
        server_status_panel.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        server_status_panel.columnconfigure(0, weight=1)

        make_label(
            server_status_panel,
            variable=self.server_room_status_var,
            font=MatrixTheme.small_font,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.panel,
        ).grid(row=0, column=0, sticky="w")

        log_panel = make_panel(panel, padx=10, pady=10)
        log_panel.grid(row=6, column=0, sticky="nsew")
        log_panel.columnconfigure(0, weight=1)
        log_panel.rowconfigure(1, weight=1)

        make_label(
            log_panel,
            self.tr("network.room.view.status_log"),
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.accent,
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.log_text = make_text_log(log_panel, height=12)
        self.log_text.grid(row=1, column=0, sticky="nsew")
        self._replay_log_history()

    def _detail_field(self, parent: tk.Misc, row: int, column: int, label: str, value: str) -> None:
        cell = tk.Frame(parent, background=MatrixTheme.panel)
        cell.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 12, 0), pady=(0, 8))

        make_label(
            cell,
            label.upper(),
            font=MatrixTheme.small_font,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.panel,
        ).pack(anchor="w")

        make_label(
            cell,
            value,
            font=MatrixTheme.mono_font,
            foreground=MatrixTheme.text,
            background=MatrixTheme.panel,
            wraplength=360,
        ).pack(anchor="w", pady=(2, 0))

    def _room_detail_with_description(
        self,
        parent: tk.Misc,
        row: int,
        column: int,
        label: str,
        value: str,
        description: str,
    ) -> None:
        cell = tk.Frame(parent, background=MatrixTheme.panel)
        cell.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 12, 0), pady=(0, 8))

        make_label(
            cell,
            label.upper(),
            font=MatrixTheme.small_font,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.panel,
        ).pack(anchor="w")

        make_label(
            cell,
            value,
            font=MatrixTheme.mono_font,
            foreground=MatrixTheme.text,
            background=MatrixTheme.panel,
            wraplength=360,
        ).pack(anchor="w", pady=(2, 0))

        if description:
            make_label(
                cell,
                description,
                font=MatrixTheme.small_font,
                foreground=MatrixTheme.text_dim,
                background=MatrixTheme.panel,
                wraplength=420,
            ).pack(anchor="w", pady=(6, 0))