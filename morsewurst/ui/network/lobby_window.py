# ============================================================
# morsewurst/ui/network/lobby_window.py
# ============================================================

from __future__ import annotations

import queue
import time
import tkinter as tk

from morsewurst.network.defaults import DEFAULT_RELAY_URI
from morsewurst.network.public_rooms import PublicRoom
from morsewurst.network.settings_store import load_network_settings, network_settings_path
from morsewurst.ui.network.lobby_actions import LobbyActionsMixin
from morsewurst.ui.network.server_queries import NetworkServerQueriesMixin
from morsewurst.ui.network.startup_sequence import NetworkStartupSequenceMixin
from morsewurst.ui.network.views import (
    CallsignViewMixin,
    LobbyViewMixin,
    RoomViewMixin,
    ServerInfoViewMixin,
    SettingsViewMixin,
)
from morsewurst.ui.network.widgets import NetworkWidgetsMixin
from morsewurst.ui.network_matrix_theme import (
    MatrixTheme,
    apply_ttk_theme,
    configure_toplevel,
    make_button,
    make_label,
)

class NetworkLobbyWindow(
    tk.Toplevel,
    NetworkStartupSequenceMixin,
    NetworkWidgetsMixin,
    CallsignViewMixin,
    LobbyViewMixin,
    RoomViewMixin,
    SettingsViewMixin,
    ServerInfoViewMixin,
    NetworkServerQueriesMixin,
    LobbyActionsMixin,
):
    """Morsewurst Network lobby window."""

    def __init__(self, app: tk.Misc) -> None:
        super().__init__(app)
        self.withdraw()

        self.app = app
        self.settings = load_network_settings()
        self.settings_file_exists = network_settings_path().exists()

        self.current_view = ""
        self.connected_room_key = ""
        self.connected_room_id = ""

        self.connected_room_title = ""
        self.connected_room_password = ""
        self.connected_room_access = ""
        self.connected_room_description = ""

        self.pending_room_key = ""
        self.pending_room_title = ""
        self.pending_room_password = ""
        self.pending_room_access = ""
        self.pending_room_description = ""

        self.public_rooms: tuple[PublicRoom, ...] = ()
        self._public_rooms_loading = False
        self._public_room_refresh_after_id: str | None = None

        self._public_rooms_result_queue: queue.Queue[tuple[int, bool, object]] = queue.Queue()
        self._public_rooms_request_seq = 0
        self._public_rooms_queue_after_id: str | None = None

        self._server_query_result_queue: queue.Queue[tuple[str, bool, object, bool]] = queue.Queue()
        self._server_query_after_id: str | None = None
        self._server_info_refresh_after_id: str | None = None
        self._server_info_query_running = False
        self._server_ping_query_running = False
        self._server_info_refresh_seconds = 10
        self.server_info_error_text = ""

        # Public room refresh errors are intentionally hidden until several
        # consecutive attempts fail. This prevents one-off DNS/WLAN glitches
        # from spamming the footer status line.
        self._public_rooms_failed_attempts = 0
        self._public_rooms_error_threshold = 3
        self._public_rooms_error_visible = False

        self.log_text: tk.Text | None = None
        self.log_history: list[tuple[str, str]] = []
        self._poll_after_id: str | None = None
        self._last_poll_monotonic = time.monotonic()

        # Cached server information for future and current UI use.
        # These are updated from NetworkManager payload messages.
        self.last_server_info: dict[str, object] | None = None
        self.last_server_pong: dict[str, object] | None = None

        self.server_summary_var = tk.StringVar(value="SERVER: updating...")
        self.server_room_status_var = tk.StringVar(value="SERVER STATUS: updating...")

        self.server_info_window: tk.Toplevel | None = None
        self.server_info_value_vars: dict[str, tk.StringVar] = {}
        self._server_summary_after_id: str | None = None

        self._init_network_startup_state()

        self.title("Morsewurst Network")
        self.transient(app)
        self.geometry("1280x740")
        self.minsize(1180, 720)

        configure_toplevel(self)
        apply_ttk_theme(self)

        try:
            self.overrideredirect(False)
        except Exception:
            pass

        try:
            self.app.network_modal_active = True
        except Exception:
            pass

        self.callsign_var = tk.StringVar(value=self.settings.callsign)
        self.server_uri_var = tk.StringVar(value=self.settings.last_server_uri or DEFAULT_RELAY_URI)
        self.private_room_var = tk.StringVar(value="")
        self.private_password_var = tk.StringVar(value="")

        self.status_var = tk.StringVar(value="STANDBY")
        self.room_status_var = tk.StringVar(value="Ready.")
        self.public_rooms_status_var = tk.StringVar(value="Loading public rooms...")
        self.remembered_rooms_status_var = tk.StringVar(value="")

        self.playback_enabled_var = tk.BooleanVar(value=self.settings.playback_enabled)
        self.transmit_enabled_var = tk.BooleanVar(value=self.settings.transmit_enabled)
        self.frequency_var = tk.StringVar(value=str(int(round(self.settings.frequency_hz))))
        self.volume_percent_var = tk.IntVar(value=int(round(self.settings.volume * 100)))
        self.jitter_buffer_var = tk.IntVar(value=int(self.settings.jitter_buffer_ms))

        self.public_rooms_frame: tk.Frame | None = None
        self.remembered_rooms_frame: tk.Frame | None = None

        self._build_window_chrome()

        self.main = tk.Frame(self.window_body, background=MatrixTheme.background)
        self.main.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)
        self.main.columnconfigure(0, weight=1)
        self.main.rowconfigure(1, weight=1)

        self._build_header()

        self.content = tk.Frame(self.main, background=MatrixTheme.background)
        self.content.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.footer = tk.Frame(self.main, background=MatrixTheme.background)
        self.footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.footer.columnconfigure(0, weight=1)

        needs_first_callsign = self._needs_first_callsign()

        if needs_first_callsign:
            self._network_startup_complete = True
            self.show_callsign_view()
        else:
            self.show_lobby_view()

        self._poll_status()
        self._refresh_server_summary()

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close())

        if needs_first_callsign:
            self._show_network_window()
        else:
            self._start_network_startup_sequence()

    def _build_window_chrome(self) -> None:
        self.window_chrome = tk.Frame(
            self,
            background=MatrixTheme.border_dim,
            bd=0,
            highlightthickness=1,
            highlightbackground=MatrixTheme.border_dim,
            highlightcolor=MatrixTheme.border,
        )
        self.window_chrome.pack(fill=tk.BOTH, expand=True)

        self.window_titlebar = tk.Frame(
            self.window_chrome,
            background=MatrixTheme.input_bg,
            height=34,
            bd=0,
            highlightthickness=0,
        )
        self.window_titlebar.pack(fill=tk.X, padx=1, pady=(1, 0))
        self.window_titlebar.pack_propagate(False)

        title = tk.Label(
            self.window_titlebar,
            text="MORSEWURST NETWORK",
            font=MatrixTheme.small_font,
            fg=MatrixTheme.accent,
            bg=MatrixTheme.input_bg,
            bd=0,
            padx=10,
        )
        title.pack(side=tk.LEFT, fill=tk.Y)

        close_button = tk.Button(
            self.window_titlebar,
            text="×",
            command=self.close,
            font=MatrixTheme.heading_font,
            fg=MatrixTheme.text_dim,
            bg=MatrixTheme.input_bg,
            activeforeground=MatrixTheme.accent,
            activebackground=MatrixTheme.input_bg,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=10,
            cursor="hand2",
        )
        close_button.pack(side=tk.RIGHT, fill=tk.Y)

        self.window_body = tk.Frame(
            self.window_chrome,
            background=MatrixTheme.background,
            bd=0,
            highlightthickness=0,
        )
        self.window_body.pack(fill=tk.BOTH, expand=True, padx=1, pady=(0, 1))

    def _build_header(self) -> None:
        header = tk.Frame(self.main, background=MatrixTheme.background)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        make_label(
            header,
            "MORSEWURST NETWORK",
            font=("Consolas", 28, "bold"),
            foreground=MatrixTheme.accent,
            background=MatrixTheme.background,
        ).grid(row=0, column=0, sticky="w")

        make_label(
            header,
            "Morsewurst Network is still an actively developed prototype, so occasional glitches and unexpected behaviour may occur.",
            font=MatrixTheme.small_font,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.background,
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        status = make_label(
            header,
            variable=self.status_var,
            font=MatrixTheme.heading_font,
            foreground=MatrixTheme.accent,
            background=MatrixTheme.background,
        )
        status.grid(row=0, column=1, sticky="e")

    def _render_footer(self) -> None:
        for child in self.footer.winfo_children():
            child.destroy()

        make_label(
            self.footer,
            variable=self.room_status_var,
            font=MatrixTheme.small_font,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.background,
        ).grid(row=0, column=0, sticky="w")

        if self.current_view == "lobby":
            make_button(self.footer, "CLOSE", self.close).grid(row=0, column=1, sticky="e")

    def _clear_content(self) -> None:
        self.log_text = None
        self.public_rooms_frame = None
        self.remembered_rooms_frame = None

        for child in self.content.winfo_children():
            child.destroy()

    def _show_notice(self, text: str, level: str = "info") -> None:
        self.room_status_var.set(text)

    def _clear_notice(self) -> None:
        if self.connected_room_key or self.connected_room_id:
            self.room_status_var.set(f"Connected to {self.connected_room_title or self.connected_room_id}.")
        else:
            self.room_status_var.set("Ready.")