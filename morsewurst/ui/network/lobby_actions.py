# ============================================================
# morsewurst/ui/network/lobby_actions.py
# ============================================================

from __future__ import annotations

from datetime import datetime
import time
import tkinter as tk

import morsewurst.config as config

from morsewurst.network.defaults import DEFAULT_RELAY_URI
from morsewurst.network.models import NetworkSettings, PlaybackSettings
from morsewurst.network.public_rooms import PublicRoom
from morsewurst.network.settings_store import (
    NetworkClientSettings,
    sanitize_callsign,
    sanitize_room_display_name,
    sanitize_room_name,
    save_network_settings,
)

class LobbyActionsMixin:
    def join_public_room(self, room: PublicRoom) -> None:
        self._connect(
            room_key=room.id,
            password="",
            title=room.name,
            access="public",
            description=room.description,
        )

    def join_private_room(self) -> None:
        raw_room_name = str(self.private_room_var.get() or "")
        room_key = sanitize_room_name(raw_room_name)
        display_name = sanitize_room_display_name(raw_room_name) or room_key
        password = str(self.private_password_var.get() or "").replace("\r", "").replace("\n", "")[:256]

        if not room_key:
            self._show_notice("Enter a private room name.", "warning")
            return

        if not password:
            self._show_notice("Enter a private room password.", "warning")
            return

        self.private_room_var.set(display_name)

        self._connect(
            room_key=room_key,
            password=password,
            title=display_name,
            access="private",
            description="",
        )

    def _connect(
        self,
        *,
        room_key: str,
        password: str,
        title: str,
        access: str,
        description: str = "",
    ) -> None:
        self._clear_notice()
        self._save_current_settings(last_room=room_key)

        # For private rooms, send the display name to the network layer so that
        # the protocol can preserve the intended room_name. The server still
        # normalizes it into the technical room_key.
        room_for_network = title if access == "private" else room_key
        settings = self._network_settings(room_name=room_for_network, password=password)

        self.pending_room_key = room_key
        self.pending_room_title = title
        self.pending_room_password = password
        self.pending_room_access = access
        self.pending_room_description = description

        self.status_var.set("CONNECTING")
        self.room_status_var.set(f"Connecting to {title}...")

        try:
            self.app.network_manager.connect_to_room(settings)
        except Exception as exc:
            self._handle_connection_error(str(exc))

    def disconnect(self) -> None:
        room_title = self.connected_room_title or self.connected_room_id or "room"

        try:
            self.app.network_manager.stop()
        except Exception:
            pass

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

        self.status_var.set("STANDBY")
        self.room_status_var.set(f"Left {room_title}.")
        self.show_lobby_view()

    def _network_settings(self, *, room_name: str, password: str) -> NetworkSettings:
        playback = PlaybackSettings(
            enabled=bool(self.playback_enabled_var.get()),
            jitter_buffer_ms=self._safe_int(self.jitter_buffer_var.get(), 750, 250, 5000),
            frequency_hz=float(self._safe_int(self.frequency_var.get(), 650, 80, 2400)),
            volume=float(self._safe_int(self.volume_percent_var.get(), 100, 0, 100)) / 100.0,
            waveform="sine",
        )

        return NetworkSettings(
            callsign=sanitize_callsign(self.callsign_var.get()),
            installation_id=self.settings.installation_id,
            room=str(room_name or "").strip(),
            password=password,
            server_uri=self._server_uri(),
            transmit_enabled=bool(self.transmit_enabled_var.get()),
            playback=playback,
        )

    def save_settings(self, *, last_room: str | None = None) -> None:
        self._save_current_settings(last_room=last_room or self.settings.last_room)
        applied = self._apply_live_settings()

        if applied:
            self._show_notice("Settings saved and applied.", "success")
        else:
            self._show_notice("Settings saved.", "success")

    def _save_current_settings(self, *, last_room: str) -> None:
        remembered_private_rooms = list(getattr(self.settings, "remembered_private_rooms", []) or [])

        safe = NetworkClientSettings(
            callsign=sanitize_callsign(self.callsign_var.get()),
            installation_id=self.settings.installation_id,
            last_server_uri=self._server_uri(),
            last_room=sanitize_room_name(last_room),
            playback_enabled=bool(self.playback_enabled_var.get()),
            transmit_enabled=bool(self.transmit_enabled_var.get()),
            jitter_buffer_ms=self._safe_int(self.jitter_buffer_var.get(), 750, 250, 5000),
            frequency_hz=float(self._safe_int(self.frequency_var.get(), 650, 80, 2400)),
            volume=float(self._safe_int(self.volume_percent_var.get(), 100, 0, 100)) / 100.0,
            waveform="sine",
            remember_password=False,
            saved_password="",
            remembered_private_rooms=remembered_private_rooms,
        )

        save_network_settings(safe)
        self.settings = safe

        self.callsign_var.set(safe.callsign)
        self.server_uri_var.set(safe.last_server_uri or DEFAULT_RELAY_URI)
        self.frequency_var.set(str(int(round(safe.frequency_hz))))
        self.volume_percent_var.set(int(round(safe.volume * 100)))
        self.jitter_buffer_var.set(int(safe.jitter_buffer_ms))

    def _apply_live_settings(self) -> bool:
        manager = getattr(self.app, "network_manager", None)
        if manager is None:
            return False

        try:
            if not manager.is_running:
                return False
        except Exception:
            return False

        try:
            playback = PlaybackSettings(
                enabled=bool(self.playback_enabled_var.get()),
                jitter_buffer_ms=self._safe_int(self.jitter_buffer_var.get(), 750, 250, 5000),
                frequency_hz=float(self._safe_int(self.frequency_var.get(), 650, 80, 2400)),
                volume=float(self._safe_int(self.volume_percent_var.get(), 100, 0, 100)) / 100.0,
                waveform="sine",
            )
            manager.update_playback_settings(playback)
            manager.set_transmit_enabled(bool(self.transmit_enabled_var.get()))
            self._append_log("success", "Playback and transmit settings updated.")
            return True
        except Exception as exc:
            self._append_log("warning", f"Live settings update failed: {exc}")
            return False

    def _reset_receive_playback_after_resume_if_needed(self) -> None:
        now = time.monotonic()
        previous = getattr(self, "_last_poll_monotonic", now)
        self._last_poll_monotonic = now

        gap_seconds = now - previous
        reset_gap_seconds = max(
            1.0,
            float(getattr(config, "NETWORK_RESUME_RESET_GAP_SECONDS", 2.0)),
        )

        if gap_seconds <= reset_gap_seconds:
            return

        manager = getattr(self.app, "network_manager", None)
        if manager is None:
            return

        try:
            if not manager.is_running:
                return
        except Exception:
            return

        try:
            manager.reset_receive_playback()
            self._append_log(
                "warning",
                f"Playback reset after {gap_seconds:.1f} s application pause.",
            )
        except Exception as exc:
            self._append_log("warning", f"Playback reset failed: {exc}")

    def _poll_status(self) -> None:
        try:
            self._reset_receive_playback_after_resume_if_needed()
            manager = self.app.network_manager

            for item in manager.drain_statuses():
                level = str(item.get("level") or "info")
                text = str(item.get("text") or "")
                payload = item.get("payload")

                if isinstance(payload, dict):
                    self._handle_status_payload(level, text, payload)

                    # server_info is intentionally textless. It updates cached
                    # server data, but should not spam the footer or status log.
                    if not text:
                        continue

                self._handle_status(level, text)

        except Exception:
            pass

        try:
            if self.winfo_exists():
                self._poll_after_id = self.after(250, self._poll_status)
        except Exception:
            pass

    def _handle_status_payload(self, level: str, text: str, payload: dict[str, object]) -> None:
        message_type = str(payload.get("type") or "")

        if level == "server_info" or message_type == "server_info":
            self.last_server_info = payload
            self._update_server_info_views()
            return

        if level == "server_pong" or message_type == "server_pong":
            self.last_server_pong = payload
            self._update_server_info_views()
            return

    def _handle_status(self, level: str, text: str) -> None:
        if not text or self._should_hide_status(level, text):
            return

        level_key = str(level or "info").strip().lower()
        lowered = text.lower()

        if lowered.startswith("yhteys aulaan muodostettu"):
            if self.current_view == "lobby":
                self.status_var.set("STANDBY")
            self.room_status_var.set(text)
            self._append_log("info", text)
            return

        if self._is_transient_connection_status(level_key, lowered):
            self._handle_transient_connection_status(text)
            return

        if level_key == "error":
            self._handle_connection_error(text)
            return

        if self._is_connection_success(text):
            self._handle_connection_success(text)
            return

        if "katkesi" in lowered:
            self._handle_transient_connection_status(text)
            return

        self.room_status_var.set(text)
        self._append_log(level_key, text)

    def _is_transient_connection_status(self, level: str, lowered_text: str) -> bool:
        if level == "debug":
            return False

        transient_prefixes = (
            "yhteys aulaan katkesi",
            "lobby-yhteyttä yritetään uudelleen",
            "yhteys katkesi:",
        )

        return lowered_text.startswith(transient_prefixes)

    def _handle_transient_connection_status(self, text: str) -> None:
        if self.connected_room_key or self.connected_room_id:
            self.status_var.set("RECONNECTING")
        elif self.current_view == "lobby":
            self.status_var.set("RETRYING")

        self.room_status_var.set(text)
        self._append_log("warning", text)

    def _is_connection_success(self, text: str) -> bool:
        lowered = text.lower()
        return "yhdistetty huoneeseen" in lowered or "connected to room" in lowered

    def _handle_connection_success(self, text: str) -> None:
        manager = getattr(self.app, "network_manager", None)

        server_room_key = ""
        server_room_name = ""
        server_room_id = ""
        server_room_access = ""

        if manager is not None:
            server_room_key = str(getattr(manager, "last_joined_room_key", "") or "")
            server_room_name = str(getattr(manager, "last_joined_room_name", "") or "")
            server_room_id = str(getattr(manager, "last_joined_room_id", "") or "")
            server_room_access = str(getattr(manager, "last_joined_room_access", "") or "")

        room_key = server_room_key or self.pending_room_key or self.connected_room_key or self.settings.last_room
        title = server_room_name or self.pending_room_title or room_key
        visible_room_id = server_room_id

        self.connected_room_key = room_key
        self.connected_room_id = visible_room_id
        self.connected_room_title = title
        self.connected_room_password = self.pending_room_password
        self.connected_room_access = server_room_access or self.pending_room_access or "public"
        self.connected_room_description = self.pending_room_description

        self.pending_room_key = ""
        self.pending_room_title = ""
        self.pending_room_password = ""
        self.pending_room_access = ""
        self.pending_room_description = ""

        self.status_var.set("ONLINE")
        self.room_status_var.set(f"Connected to {title}.")

        self._remember_successful_private_room()

        self.show_room_view()
        self._append_log("success", f"Connected to room {title}.")

    def _handle_connection_error(self, text: str) -> None:
        message = self._friendly_error_message(text)

        try:
            self.app.network_manager.stop()
        except Exception:
            pass

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

        self.status_var.set("ERROR")
        self.room_status_var.set(message)

        if self.current_view != "lobby":
            self.show_lobby_view()

        self._show_notice(message, "error")
        self._append_log("error", message)

    def _friendly_error_message(self, text: str) -> str:
        room_name = self.pending_room_title or self.private_room_var.get() or "the requested room"
        lowered = text.lower()

        if "salasana ei täsmää" in lowered or ("password" in lowered and "match" in lowered):
            return f"Room '{room_name}' already exists, but the password you entered does not match. You can forget the remembered room and enter a new password."

        if "winerror 1225" in lowered or "hylkäsi verkkoyhteyden" in lowered or "connection refused" in lowered:
            return "Could not connect to the Morsewurst relay server. Make sure the relay is running and the port is open."

        if "reserved" in lowered or "varattu" in lowered:
            return f"Room name '{room_name}' is reserved and cannot be created as a private room."
        
        if "getaddrinfo failed" in lowered or "errno 11002" in lowered:
            return (
                "Server address could not be resolved. "
                "Check the network connection or DNS, then try again."
            )

        return text

    def _should_hide_status(self, level: str, text: str) -> bool:
        lowered = text.lower()

        if level == "debug":
            return True

        hidden_phrases = (
            "toneplayer pysäytetty",
            "toneplayer käynnissä",
            "uusi vastaanottopuskuri",
            "verkkoyhteys pysäytetty",
        )

        return any(phrase in lowered for phrase in hidden_phrases)

    def _append_log(self, level: str, text: str) -> None:
        if not text or self._should_hide_status(level, text):
            return

        level_key = str(level or "info").strip().lower()
        tag = level_key if level_key in {"info", "success", "warning", "error"} else "info"

        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        level_label = level_key.upper().replace(" ", "_")
        level_label = level_label[:11]

        line = f"{timestamp}  {level_label:<11}   {text}\n"

        self.log_history.append((tag, line))
        if len(self.log_history) > 200:
            self.log_history = self.log_history[-200:]

        log = self.log_text
        if log is None:
            return

        try:
            log.configure(state=tk.NORMAL)
            log.insert(tk.END, line, tag)
            log.see(tk.END)
            log.configure(state=tk.DISABLED)
        except Exception:
            pass    

    def _replay_log_history(self) -> None:
        log = self.log_text
        if log is None:
            return

        try:
            log.configure(state=tk.NORMAL)
            log.delete("1.0", tk.END)
            for tag, line in self.log_history:
                log.insert(tk.END, line, tag)
            log.see(tk.END)
            log.configure(state=tk.DISABLED)
        except Exception:
            pass

    def bring_to_front(self) -> None:
        try:
            if not self.winfo_exists():
                return

            self.deiconify()
            self.lift()
            self.focus_force()

            try:
                self.attributes("-topmost", True)
                self.after(200, lambda: self.attributes("-topmost", False))
            except Exception:
                pass
        except Exception:
            pass

    def notify_local_tone(self, event: dict) -> None:
        """Compatibility hook for app-level local tone notifications."""

        return

    def _server_uri(self) -> str:
        value = str(self.server_uri_var.get() or "").strip()
        return value or DEFAULT_RELAY_URI

    def _safe_int(self, value: object, default: int, minimum: int, maximum: int) -> int:
        try:
            if isinstance(value, bool):
                raise ValueError
            number = int(str(value).strip())
        except Exception:
            number = default
        return max(minimum, min(maximum, number))

    def _center_on_parent(self) -> None:
        parent = self.app

        try:
            self.update_idletasks()
            x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
            y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def close(self) -> None:
        try:
            self._cancel_network_startup_sequence()
        except Exception:
            pass
        
        try:
            if self._poll_after_id is not None:
                self.after_cancel(self._poll_after_id)
        except Exception:
            pass

        try:
            if self._server_summary_after_id is not None:
                self.after_cancel(self._server_summary_after_id)
        except Exception:
            pass

        try:
            if self._server_info_refresh_after_id is not None:
                self.after_cancel(self._server_info_refresh_after_id)
        except Exception:
            pass

        try:
            self._close_server_info_window()
        except Exception:
            pass

        try:
            if self._public_room_refresh_after_id is not None:
                self.after_cancel(self._public_room_refresh_after_id)
        except Exception:
            pass

        try:
            self.app.network_manager.stop()
        except Exception:
            pass

        try:
            if getattr(self.app, "network_window", None) is self:
                self.app.network_window = None
        except Exception:
            pass

        try:
            self.grab_release()
        except Exception:
            pass

        try:
            self.app.network_modal_active = False
        except Exception:
            pass

        try:
            if self._public_rooms_queue_after_id is not None:
                self.after_cancel(self._public_rooms_queue_after_id)
        except Exception:
            pass

        try:
            if self._server_query_after_id is not None:
                self.after_cancel(self._server_query_after_id)
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass