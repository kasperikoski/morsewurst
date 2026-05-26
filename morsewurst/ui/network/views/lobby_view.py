# ============================================================
# morsewurst/ui/network/views/lobby_view.py
# ============================================================

from __future__ import annotations

import tkinter as tk

from morsewurst.core.logging_service import log_event, log_exception
from morsewurst.network.public_rooms import PublicRoom
from morsewurst.network.settings_store import (
    RememberedPrivateRoom,
    forget_private_room,
    remember_private_room,
    sanitize_callsign,
    save_network_settings,
)
from morsewurst.ui.network_matrix_theme import (
    MatrixTheme,
    make_button,
    make_entry,
    make_label,
    make_panel,
)

class LobbyViewMixin:
    def show_lobby_view(self) -> None:
        self.current_view = "lobby"
        self._clear_content()
        self._render_footer()

        wrapper = tk.Frame(self.content, background=MatrixTheme.background)
        wrapper.grid(row=0, column=0, sticky="nsew")
        wrapper.columnconfigure(0, weight=1, uniform="lobby_columns")
        wrapper.columnconfigure(1, weight=1, uniform="lobby_columns")
        wrapper.columnconfigure(2, weight=1, uniform="lobby_columns")
        wrapper.rowconfigure(1, weight=1)

        self._build_connection_panel(wrapper).grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="ew",
        )

        self._build_public_rooms_panel(wrapper).grid(
            row=1,
            column=0,
            sticky="nsew",
            pady=(14, 0),
            padx=(0, 12),
        )

        self._build_remembered_private_rooms_panel(wrapper).grid(
            row=1,
            column=1,
            sticky="nsew",
            pady=(14, 0),
            padx=(0, 12),
        )

        self._build_private_panel(wrapper).grid(
            row=1,
            column=2,
            sticky="nsew",
            pady=(14, 0),
        )

        self._render_public_rooms()
        self._render_remembered_private_rooms()

        startup_complete = bool(getattr(self, "_network_startup_complete", True))

        if startup_complete and not self.public_rooms:
            self._refresh_public_rooms_async()

        self._update_server_info_views()

        if startup_complete:
            self.after(100, lambda: self._request_server_info(silent=True))
            self.after(150, self._ensure_lobby_presence)

    def _count_key(self, base_key: str, count: int) -> str:
        return f"{base_key}_one" if int(count) == 1 else f"{base_key}_many"

    def _public_room_i18n_key(self, room: PublicRoom, part: str) -> str:
        room_id = str(room.id or room.name or "").strip().lower()
        room_id = room_id.replace(" ", "_").replace("-", "").replace(".", "")
        return f"network.public_room.{room_id}.{part}"

    def _localized_public_room_name(self, room: PublicRoom) -> str:
        return self.tr(
            self._public_room_i18n_key(room, "name"),
            default=room.name,
        )

    def _localized_public_room_description(self, room: PublicRoom) -> str:
        fallback = room.description or self.tr("network.public_rooms.default_description")
        return self.tr(
            self._public_room_i18n_key(room, "description"),
            default=fallback,
        )

    def _ensure_lobby_presence(self) -> None:
        if self.connected_room_key or self.connected_room_id:
            return

        manager = getattr(self.app, "network_manager", None)
        if manager is None:
            return

        try:
            if manager.is_running:
                return
        except Exception:
            return

        try:
            settings = self._network_settings(room_name="", password="")
            log_event(
                "network",
                "network.lobby.presence_requested",
                message="Lobby presence connection requested from lobby view.",
                context={"server_uri": self._server_uri()},
            )
            manager.connect_lobby_presence(settings)
        except Exception as exc:
            log_exception(
                "network",
                "network.lobby.presence_request_failed",
                exc,
                level="warning",
                message="Lobby presence could not be started.",
                context={"server_uri": self._server_uri()},
            )
            self._append_log("warning", f"Lobby presence could not be started: {exc}")

    def _build_connection_panel(self, parent: tk.Misc) -> tk.Frame:
        panel = make_panel(parent, padx=16, pady=12)
        panel.columnconfigure(0, weight=0)
        panel.columnconfigure(1, weight=1)

        make_label(
            panel,
            self.tr("network.lobby.callsign", callsign=sanitize_callsign(self.callsign_var.get())),
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.accent,
        ).grid(row=0, column=0, sticky="w")

        make_label(
            panel,
            variable=self.server_summary_var,
            font=MatrixTheme.small_font,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.panel,
        ).grid(row=0, column=1, sticky="e", padx=(18, 12))

        make_button(panel, self.tr("network.button.server_info"), self.show_server_info_window).grid(
            row=0,
            column=2,
            sticky="e",
            padx=(0, 8),
        )

        make_button(panel, self.tr("network.button.ping"), self._request_server_ping).grid(
            row=0,
            column=3,
            sticky="e",
            padx=(0, 8),
        )

        make_button(panel, self.tr("network.button.settings"), self.show_settings_view).grid(
            row=0,
            column=4,
            sticky="e",
        )

        return panel

    def _build_public_rooms_panel(self, parent: tk.Misc) -> tk.Frame:
        panel = make_panel(parent)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(3, weight=1)

        make_label(
            panel,
            self.tr("network.public_rooms.title"),
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.accent,
        ).grid(row=0, column=0, sticky="w")

        make_label(
            panel,
            self.tr("network.public_rooms.description"),
            foreground=MatrixTheme.text_dim,
            wraplength=340,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 8))

        status_row = tk.Frame(panel, background=MatrixTheme.panel)
        status_row.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        status_row.columnconfigure(0, weight=1)

        make_label(
            status_row,
            variable=self.public_rooms_status_var,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.panel,
        ).grid(row=0, column=0, sticky="w")

        make_button(
            status_row,
            self.tr("network.button.refresh"),
            lambda: self._refresh_public_rooms_async(force=True),
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

        scroll_outer, scroll_inner = self._make_scrollable_list(panel, height=410)
        scroll_outer.grid(row=3, column=0, sticky="nsew")
        self.public_rooms_frame = scroll_inner

        return panel

    def _build_remembered_private_rooms_panel(self, parent: tk.Misc) -> tk.Frame:
        panel = make_panel(parent)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(3, weight=1)

        make_label(
            panel,
            self.tr("network.remembered_rooms.title"),
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.accent,
        ).grid(row=0, column=0, sticky="w")

        make_label(
            panel,
            self.tr("network.remembered_rooms.description"),
            foreground=MatrixTheme.text_dim,
            wraplength=340,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 8))

        make_label(
            panel,
            variable=self.remembered_rooms_status_var,
            foreground=MatrixTheme.text_dim,
        ).grid(row=2, column=0, sticky="w", pady=(0, 10))

        scroll_outer, scroll_inner = self._make_scrollable_list(panel, height=410)
        scroll_outer.grid(row=3, column=0, sticky="nsew")
        self.remembered_rooms_frame = scroll_inner

        return panel

    def _build_private_panel(self, parent: tk.Misc) -> tk.Frame:
        panel = make_panel(parent)
        panel.columnconfigure(0, weight=1)

        make_label(
            panel,
            self.tr("network.private_room.title"),
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.accent,
        ).grid(row=0, column=0, sticky="w")

        make_label(
            panel,
            self.tr("network.private_room.description"),
            foreground=MatrixTheme.text_dim,
            wraplength=340,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 14))

        make_label(
            panel,
            self.tr("network.private_room.room_name"),
            foreground=MatrixTheme.text_dim,
        ).grid(row=2, column=0, sticky="w")

        room_entry = make_entry(panel, self.private_room_var, width=32)
        room_entry.grid(row=3, column=0, sticky="ew", pady=(4, 10))

        make_label(
            panel,
            self.tr("network.private_room.password"),
            foreground=MatrixTheme.text_dim,
        ).grid(row=4, column=0, sticky="w")

        password_entry = make_entry(panel, self.private_password_var, show="*", width=32)
        password_entry.grid(row=5, column=0, sticky="ew", pady=(4, 14))

        make_button(
            panel,
            self.tr("network.button.create_or_join"),
            self.join_private_room,
        ).grid(row=6, column=0, sticky="w")

        help_box = tk.Frame(panel, background=MatrixTheme.panel_alt, padx=12, pady=10)
        help_box.grid(row=7, column=0, sticky="ew", pady=(18, 0))
        help_box.columnconfigure(0, weight=1)

        make_label(
            help_box,
            self.tr("network.private_room.tip_title"),
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.accent,
            background=MatrixTheme.panel_alt,
        ).grid(row=0, column=0, sticky="w")

        make_label(
            help_box,
            self.tr("network.private_room.tip_text"),
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.panel_alt,
            wraplength=300,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))

        room_entry.bind("<Return>", lambda _event: password_entry.focus_set())
        password_entry.bind("<Return>", lambda _event: self.join_private_room())

        return panel

    def _render_public_rooms(self) -> None:
        frame = self.public_rooms_frame
        if frame is None:
            return

        for child in frame.winfo_children():
            child.destroy()

        if self._public_rooms_loading:
            self.public_rooms_status_var.set(self.tr("network.public_rooms.loading"))
            self._empty_row(frame, self.tr("network.public_rooms.please_wait")).grid(row=0, column=0, sticky="ew")
            return

        if not self.public_rooms:
            self.public_rooms_status_var.set(self.tr("network.public_rooms.none_loaded"))
            self._empty_row(
                frame,
                self.tr("network.public_rooms.none_available"),
            ).grid(row=0, column=0, sticky="ew")
            return

        count = len(self.public_rooms)
        self.public_rooms_status_var.set(
            self.tr(self._count_key("network.public_rooms.count", count), count=count)
        )

        for index, room in enumerate(self.public_rooms):
            self._public_room_row(frame, room).grid(row=index, column=0, sticky="ew", pady=(0, 10))

        self._bind_scrollwheel_to_tree(frame)

    def _public_room_row(self, parent: tk.Misc, room: PublicRoom) -> tk.Frame:
        row = tk.Frame(parent, background=MatrixTheme.panel_alt, padx=12, pady=10)
        row.columnconfigure(0, weight=1)

        make_label(
            row,
            self._localized_public_room_name(room).upper(),
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.text,
            background=MatrixTheme.panel_alt,
        ).grid(row=0, column=0, sticky="w")

        description = self._localized_public_room_description(room)
        if room.max_clients > 0:
            description = (
                f"{description} "
                f"{self.tr('network.public_rooms.users', current=room.client_count, max=room.max_clients)}"
            )

        make_label(
            row,
            description,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.panel_alt,
            wraplength=260,
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        make_button(
            row,
            self.tr("network.button.join"),
            lambda selected_room=room: self.join_public_room(selected_room),
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))

        return row

    def _public_rooms_signature(self, rooms: tuple[PublicRoom, ...] | list[PublicRoom]) -> tuple[tuple[str, str, str, int, int], ...]:
        return tuple(
            (
                str(room.id),
                str(room.name),
                str(room.description),
                int(room.client_count),
                int(room.max_clients),
            )
            for room in rooms
        )

    def _remembered_private_rooms(self) -> list[RememberedPrivateRoom]:
        rooms = getattr(self.settings, "remembered_private_rooms", [])
        return list(rooms or [])

    def _render_remembered_private_rooms(self) -> None:
        frame = self.remembered_rooms_frame
        if frame is None:
            return

        for child in frame.winfo_children():
            child.destroy()

        rooms = self._remembered_private_rooms()
        log_event(
            "network",
            "network.remembered_private_rooms.loaded",
            message="Remembered private rooms loaded for lobby view.",
            context={"server_uri": self._server_uri(), "count": len(rooms)},
        )

        if not rooms:
            self.remembered_rooms_status_var.set(self.tr("network.remembered_rooms.none"))
            self._empty_row(
                frame,
                self.tr("network.remembered_rooms.none_help"),
            ).grid(row=0, column=0, sticky="ew")
            return

        count = len(rooms)
        self.remembered_rooms_status_var.set(
            self.tr(self._count_key("network.remembered_rooms.count", count), count=count)
        )

        for index, room in enumerate(rooms):
            self._remembered_private_room_row(frame, room).grid(
                row=index,
                column=0,
                sticky="ew",
                pady=(0, 10),
            )
        
        self._bind_scrollwheel_to_tree(frame)

    def _remembered_private_room_row(self, parent: tk.Misc, room: RememberedPrivateRoom) -> tk.Frame:
        row = tk.Frame(parent, background=MatrixTheme.panel_alt, padx=12, pady=10)
        row.columnconfigure(0, weight=1)

        title = room.display_name or room.room_id or self.tr("network.remembered_rooms.default_title")

        title_label = make_label(
            row,
            title,
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.text,
            background=MatrixTheme.panel_alt,
        )
        title_label.grid(row=0, column=0, sticky="w")

        join_button = make_button(
            row,
            self.tr("network.button.join"),
            lambda selected_room=room: self._join_remembered_private_room(selected_room),
        )
        join_button.grid(row=0, column=1, sticky="e", padx=(10, 0))

        forget_button = make_button(
            row,
            self.tr("network.button.forget"),
            lambda selected_room=room: self._forget_remembered_private_room(selected_room),
        )
        forget_button.grid(row=0, column=2, sticky="e", padx=(8, 0))

        for widget in (row, title_label):
            widget.bind(
                "<Button-1>",
                lambda _event, selected_room=room: self._select_remembered_private_room(selected_room),
            )
            widget.bind(
                "<Double-Button-1>",
                lambda _event, selected_room=room: self._join_remembered_private_room(selected_room),
            )

        return row

    def _select_remembered_private_room(self, room: RememberedPrivateRoom) -> None:
        display_name = room.display_name or room.room_id
        self.private_room_var.set(display_name)
        self.private_password_var.set(room.saved_password or "")
        self.server_uri_var.set(room.server_uri or self._server_uri())
        log_event(
            "network",
            "network.remembered_private_room.selected",
            message="Remembered private room selected.",
            context={"server_uri": room.server_uri or self._server_uri(), "room_id": room.room_id, "display_name": display_name},
        )
        self._show_notice(self.tr("network.room.loaded_remembered", room=display_name), "info")

    def _join_remembered_private_room(self, room: RememberedPrivateRoom) -> None:
        log_event(
            "network",
            "network.remembered_private_room.join_started",
            message="Joining remembered private room.",
            context={"server_uri": room.server_uri or self._server_uri(), "room_id": room.room_id, "display_name": room.display_name},
        )
        self._select_remembered_private_room(room)
        self.join_private_room()

    def _forget_remembered_private_room(self, room: RememberedPrivateRoom) -> None:
        display_name = room.display_name or room.room_id
        server_uri = room.server_uri or self._server_uri()

        log_event(
            "network",
            "network.remembered_private_room.forget_started",
            message="Forgetting remembered private room.",
            context={
                "server_uri": server_uri,
                "room_id": room.room_id,
                "display_name": display_name,
            },
        )

        self.settings = forget_private_room(
            self.settings,
            server_uri=server_uri,
            room_id=room.room_id,
        )
        save_network_settings(self.settings)

        self._render_remembered_private_rooms()
        self._show_notice(self.tr("network.room.forgot_remembered", room=display_name), "success")

    def _remember_successful_private_room(self) -> None:
        if self.connected_room_access != "private":
            return

        if not self.connected_room_key or not self.connected_room_password:
            return

        self.settings = remember_private_room(
            self.settings,
            server_uri=self._server_uri(),
            room_name=self.connected_room_title or self.connected_room_id,
            password=self.connected_room_password,
        )
        save_network_settings(self.settings)