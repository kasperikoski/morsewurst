# ============================================================
# morsewurst/ui/network/views/server_info_view.py
# ============================================================

from __future__ import annotations

from datetime import datetime
import time
import tkinter as tk

from morsewurst.ui.network_matrix_theme import (
    MatrixTheme,
    configure_toplevel,
    make_button,
    make_label,
    make_panel,
)

class ServerInfoViewMixin:
    def _estimated_uptime_seconds(self) -> int | None:
        info = self._latest_server_info()
        if not info:
            return None

        uptime = self._safe_payload_int(info, "uptime_seconds")
        if uptime is None:
            return None

        try:
            raw_received_monotonic = info.get("client_received_monotonic")

            if isinstance(raw_received_monotonic, bool):
                received_monotonic = 0.0
            elif isinstance(raw_received_monotonic, (int, float, str)):
                received_monotonic = float(raw_received_monotonic)
            else:
                received_monotonic = 0.0

        except Exception:
            received_monotonic = 0.0

        if received_monotonic <= 0.0:
            return uptime

        elapsed_seconds = int(time.monotonic() - received_monotonic)
        return max(0, uptime + max(0, elapsed_seconds))

    def _latest_server_info(self) -> dict[str, object] | None:
        manager = getattr(self.app, "network_manager", None)

        if manager is not None:
            info = getattr(manager, "last_server_info", None)
            if isinstance(info, dict):
                return info

        return self.last_server_info

    def _latest_server_pong(self) -> dict[str, object] | None:
        manager = getattr(self.app, "network_manager", None)

        if manager is not None:
            pong = getattr(manager, "last_server_pong", None)
            if isinstance(pong, dict):
                return pong

        return self.last_server_pong

    def _estimated_server_time_unix_ms(self) -> int | None:
        info = self._latest_server_info()
        if not info:
            return None

        try:
            server_time_ms = int(info.get("server_time_unix_ms") or 0)
        except Exception:
            return None

        if server_time_ms <= 0:
            return None

        try:
            received_monotonic = float(info.get("client_received_monotonic") or 0.0)
        except Exception:
            received_monotonic = 0.0

        if received_monotonic <= 0.0:
            return server_time_ms

        elapsed_ms = int((time.monotonic() - received_monotonic) * 1000.0)
        return server_time_ms + max(0, elapsed_ms)

    def _latest_server_ping_ms(self) -> int | None:
        pong = self._latest_server_pong()
        if not pong:
            return None

        try:
            return int(pong.get("round_trip_ms"))
        except Exception:
            return None

    def _server_is_connected(self) -> bool:
        manager = getattr(self.app, "network_manager", None)
        if manager is None:
            return False

        try:
            return bool(manager.is_running)
        except Exception:
            return False

    def _format_server_summary(self) -> str:
        info = self._latest_server_info()

        if not info:
            if self.server_info_error_text:
                return "SERVER: unavailable"
            return "SERVER: updating..."

        parts: list[str] = []

        server_time_ms = self._estimated_server_time_unix_ms()
        if server_time_ms is not None:
            parts.append(f"SERVER {self._format_time_from_unix_ms(server_time_ms)}")

        uptime = self._estimated_uptime_seconds()
        if uptime is not None:
            parts.append(f"UP {self._format_duration(uptime, compact=True)}")

        clients_total = self._safe_payload_int(info, "clients_total")
        if clients_total is not None:
            parts.append(f"ONLINE {clients_total}")

        ping_ms = self._latest_server_ping_ms()
        if ping_ms is not None:
            parts.append(f"PING {ping_ms} ms")

        if not parts:
            return "SERVER: waiting for data"

        return " | ".join(parts)

    def _format_server_room_status(self) -> str:
        info = self._latest_server_info()

        if not info:
            if self.server_info_error_text:
                return f"SERVER STATUS: {self.server_info_error_text}"
            return "SERVER STATUS: updating..."

        parts: list[str] = []

        server_time_ms = self._estimated_server_time_unix_ms()
        if server_time_ms is not None:
            parts.append(f"Time {self._format_time_from_unix_ms(server_time_ms)}")

        uptime = self._estimated_uptime_seconds()
        if uptime is not None:
            parts.append(f"Uptime {self._format_duration(uptime, compact=False)}")

        clients_total = self._safe_payload_int(info, "clients_total")
        if clients_total is not None:
            parts.append(f"Online {clients_total}")

        room_clients = self._safe_payload_int(info, "room_clients")
        if room_clients is not None:
            parts.append(f"This room {room_clients}")

        ping_ms = self._latest_server_ping_ms()
        if ping_ms is not None:
            parts.append(f"Ping {ping_ms} ms")

        if not parts:
            return "SERVER STATUS: waiting for server info"

        return "SERVER STATUS  " + " | ".join(parts)

    def _safe_payload_int(self, payload: dict[str, object], key: str) -> int | None:
        try:
            value = int(payload.get(key))  # type: ignore[arg-type]
        except Exception:
            return None

        return value

    def _format_time_from_unix_ms(self, unix_ms: int) -> str:
        try:
            return datetime.fromtimestamp(unix_ms / 1000.0).strftime("%H:%M:%S")
        except Exception:
            return "-"

    def _format_datetime_from_unix_seconds(self, unix_seconds: float) -> str:
        try:
            return datetime.fromtimestamp(float(unix_seconds)).strftime("%d.%m.%Y %H:%M:%S")
        except Exception:
            return "-"

    def _format_duration(self, seconds: int, *, compact: bool) -> str:
        seconds = max(0, int(seconds))

        days, seconds = divmod(seconds, 86_400)
        hours, seconds = divmod(seconds, 3_600)
        minutes, seconds = divmod(seconds, 60)

        if compact:
            if days:
                return f"{days}d {hours}h"
            if hours:
                return f"{hours}h {minutes}m"
            if minutes:
                return f"{minutes}m {seconds}s"
            return f"{seconds}s"

        if days:
            return f"{days} d {hours} h {minutes} min"
        if hours:
            return f"{hours} h {minutes} min {seconds} s"
        if minutes:
            return f"{minutes} min {seconds} s"
        return f"{seconds} s"

    def show_server_info_window(self) -> None:
        if self.server_info_window is not None:
            try:
                if self.server_info_window.winfo_exists():
                    self.server_info_window.lift()
                    self.server_info_window.focus_force()
                    self._update_server_info_window_values()
                    return
            except Exception:
                pass

        window = tk.Toplevel(self)
        self.server_info_window = window
        self.server_info_value_vars = {}

        window.title("Morsewurst Server Info")
        window.transient(self)
        window.geometry("560x460")
        window.minsize(520, 420)

        configure_toplevel(window)

        outer = tk.Frame(
            window,
            background=MatrixTheme.border_dim,
            bd=0,
            highlightthickness=1,
            highlightbackground=MatrixTheme.border_dim,
            highlightcolor=MatrixTheme.border,
        )
        outer.pack(fill=tk.BOTH, expand=True)

        body = tk.Frame(
            outer,
            background=MatrixTheme.background,
            bd=0,
            highlightthickness=0,
        )
        body.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        header = tk.Frame(body, background=MatrixTheme.background)
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        header.columnconfigure(0, weight=1)

        make_label(
            header,
            "SERVER INFO",
            font=("Consolas", 22, "bold"),
            foreground=MatrixTheme.accent,
            background=MatrixTheme.background,
        ).grid(row=0, column=0, sticky="w")

        make_label(
            header,
            "Live relay information received from the Morsewurst server.",
            font=MatrixTheme.small_font,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.background,
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        panel = make_panel(body, padx=14, pady=12)
        panel.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 12))
        panel.columnconfigure(1, weight=1)

        rows = [
            ("Server name", "server_name"),
            ("Server time", "server_time"),
            ("Uptime", "uptime"),
            ("Online users", "clients_total"),
            ("Rooms total", "rooms_total"),
            ("Current room", "room"),
            ("Users in room", "room_clients"),
            ("Known installs", "known_installations"),
            ("Seen in 24h", "seen_24h"),
            ("Seen in 7d", "seen_7d"),
            ("Last ping", "ping"),
            ("Last update", "last_update"),
        ]

        for row_index, (label, key) in enumerate(rows):
            self._server_info_row(panel, row_index, label, key)

        buttons = tk.Frame(body, background=MatrixTheme.background)
        buttons.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
        buttons.columnconfigure(0, weight=1)

        make_button(buttons, "REFRESH INFO", self._request_server_info).grid(row=0, column=1, sticky="e")
        make_button(buttons, "PING SERVER", self._request_server_ping).grid(row=0, column=2, sticky="e", padx=(10, 0))
        make_button(buttons, "CLOSE", self._close_server_info_window).grid(row=0, column=3, sticky="e", padx=(10, 0))

        window.protocol("WM_DELETE_WINDOW", self._close_server_info_window)

        self._update_server_info_window_values()
        self._request_server_info(silent=True)

        try:
            window.lift()
            window.focus_force()
        except Exception:
            pass

    def _server_info_row(self, parent: tk.Misc, row: int, label: str, key: str) -> None:
        make_label(
            parent,
            label.upper(),
            font=MatrixTheme.small_font,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.panel,
        ).grid(row=row, column=0, sticky="w", padx=(0, 18), pady=(0, 8))

        value_var = tk.StringVar(value="-")
        self.server_info_value_vars[key] = value_var

        make_label(
            parent,
            variable=value_var,
            font=MatrixTheme.mono_font,
            foreground=MatrixTheme.text,
            background=MatrixTheme.panel,
            wraplength=340,
        ).grid(row=row, column=1, sticky="w", pady=(0, 8))

    def _update_server_info_window_values(self) -> None:
        if not self.server_info_value_vars:
            return

        info = self._latest_server_info()
        ping_ms = self._latest_server_ping_ms()

        def set_value(key: str, value: object) -> None:
            variable = self.server_info_value_vars.get(key)
            if variable is not None:
                variable.set(str(value) if value not in {None, ""} else "-")

        if not info:
            for key in self.server_info_value_vars:
                set_value(key, "-")

            if self.server_info_error_text:
                set_value("server_name", "Server info unavailable")
                set_value("last_update", self.server_info_error_text)
            elif self._server_is_connected():
                set_value("server_name", "Waiting for server info")
            else:
                set_value("server_name", "Updating...")

            return

        server_name = str(info.get("server_name") or "Morsewurst Relay")
        set_value("server_name", server_name)

        server_time_ms = self._estimated_server_time_unix_ms()
        if server_time_ms is not None:
            try:
                set_value(
                    "server_time",
                    datetime.fromtimestamp(server_time_ms / 1000.0).strftime("%d.%m.%Y %H:%M:%S"),
                )
            except Exception:
                set_value("server_time", "-")
        else:
            set_value("server_time", "-")

        uptime = self._estimated_uptime_seconds()
        set_value("uptime", self._format_duration(uptime, compact=False) if uptime is not None else "-")

        for key in (
            "clients_total",
            "rooms_total",
            "room_clients",
            "known_installations",
            "seen_24h",
            "seen_7d",
        ):
            value = self._safe_payload_int(info, key)
            set_value(key, value if value is not None else "-")

        room_name = str(info.get("room_name") or "")
        room_id = str(info.get("room_id") or "")
        if room_name and room_id and room_name != room_id:
            set_value("room", f"{room_name} ({room_id})")
        else:
            set_value("room", room_name or room_id or "-")

        set_value("ping", f"{ping_ms} ms" if ping_ms is not None else "-")

        try:
            raw_received_time = info.get("client_received_time")

            if isinstance(raw_received_time, bool):
                received_time = 0.0
            elif isinstance(raw_received_time, (int, float, str)):
                received_time = float(raw_received_time)
            else:
                received_time = 0.0

        except Exception:
            received_time = 0.0

        if received_time > 0.0:
            set_value("last_update", self._format_datetime_from_unix_seconds(received_time))
        else:
            set_value("last_update", "-")

    def _close_server_info_window(self) -> None:
        window = self.server_info_window
        self.server_info_window = None
        self.server_info_value_vars = {}

        if window is None:
            return

        try:
            if window.winfo_exists():
                window.destroy()
        except Exception:
            pass