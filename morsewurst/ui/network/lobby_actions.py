# ============================================================
# morsewurst/ui/network/lobby_actions.py
# ============================================================

from __future__ import annotations

from datetime import datetime
import time
import tkinter as tk

import morsewurst.config as config
from morsewurst.core.logging_service import log_event, log_exception

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
from morsewurst.ui.network_matrix_theme import MatrixTheme

class LobbyActionsMixin:
    def join_public_room(self, room: PublicRoom) -> None:
        log_event(
            "network",
            "network.room.join_public_selected",
            message="Public room join selected.",
            context={
                "server_uri": self._server_uri(),
                "room_id": room.id,
                "room_name": room.name,
                "client_count": room.client_count,
                "max_clients": room.max_clients,
            },
        )
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
            log_event(
                "network",
                "network.room.join_private_validation_failed",
                level="warning",
                message="Private room join was blocked because the room name is empty.",
                context={"server_uri": self._server_uri()},
            )
            self._show_notice(self.tr("network.private_room.enter_name"), "warning")
            return

        if not password:
            log_event(
                "network",
                "network.room.join_private_validation_failed",
                level="warning",
                message="Private room join was blocked because the password is empty.",
                context={"server_uri": self._server_uri(), "room": room_key},
            )
            self._show_notice(self.tr("network.private_room.enter_password"), "warning")
            return

        self.private_room_var.set(display_name)

        log_event(
            "network",
            "network.room.join_private_selected",
            message="Private room join selected.",
            context={"server_uri": self._server_uri(), "room": room_key, "display_name": display_name},
        )

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
        log_event(
            "network",
            "network.room.connect_started",
            message="Network room connection started from UI.",
            context={
                "server_uri": self._server_uri(),
                "room": room_key,
                "title": title,
                "access": access,
            },
        )
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

        self.status_var.set(self.tr("network.status.connecting"))
        self.room_status_var.set(self.tr("network.room.connecting", room=title))

        try:
            self.app.network_manager.connect_to_room(settings)
        except Exception as exc:
            log_exception(
                "network",
                "network.room.connect_failed",
                exc,
                message="Network room connection failed before the manager accepted it.",
                context={
                    "server_uri": self._server_uri(),
                    "room": room_key,
                    "title": title,
                    "access": access,
                },
            )
            self._handle_connection_error(str(exc))

    def disconnect(self) -> None:
        room_title = self.connected_room_title or self.connected_room_id or self.tr("network.remembered_rooms.default_title")
        log_event(
            "network",
            "network.room.leave_started",
            message="Leaving network room.",
            context={
                "server_uri": self._server_uri(),
                "room_key": self.connected_room_key,
                "room_id": self.connected_room_id,
                "room_title": room_title,
                "room_access": self.connected_room_access,
            },
        )

        try:
            self.app.network_manager.stop()
        except Exception as exc:
            log_exception(
                "network",
                "network.room.leave_stop_failed",
                exc,
                level="warning",
                message="Network manager stop failed while leaving a room.",
                context={"server_uri": self._server_uri(), "room_title": room_title},
            )

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

        self.status_var.set(self.tr("network.status.standby"))
        self.room_status_var.set(self.tr("network.room.left", room=room_title))
        self._set_network_quality("standby", self.tr("network.quality.detail.idle"), force=True)
        self.show_lobby_view()
        log_event(
            "network",
            "network.room.left",
            message="Left network room.",
            context={"server_uri": self._server_uri(), "room_title": room_title},
        )

    def _radio_noise_profile_from_form(self) -> str:
        profile = str(self.radio_noise_profile_var.get() or "radio").strip().lower()
        return profile if profile in {"light", "radio", "dx"} else "radio"

    def _radio_noise_tone_from_form(self) -> str:
        tone = str(self.radio_noise_tone_var.get() or getattr(config, "NETWORK_RADIO_NOISE_TONE_DEFAULT", "low")).strip().lower()
        return tone if tone in {"normal", "low", "deep"} else str(getattr(config, "NETWORK_RADIO_NOISE_TONE_DEFAULT", "low"))

    def _playback_settings_from_form(self) -> PlaybackSettings:
        return PlaybackSettings(
            enabled=bool(self.playback_enabled_var.get()),
            jitter_buffer_ms=self._safe_int(self.jitter_buffer_var.get(), 750, 250, 5000),
            frequency_hz=float(self._safe_int(self.frequency_var.get(), 650, 80, 2400)),
            volume=float(self._safe_int(self.volume_percent_var.get(), 100, 0, 100)) / 100.0,
            waveform="sine",
            radio_noise_enabled=bool(self.radio_noise_enabled_var.get()),
            radio_noise_volume=float(self._safe_int(self.radio_noise_volume_percent_var.get(), 5, 0, 30)) / 100.0,
            radio_noise_profile=self._radio_noise_profile_from_form(),
            radio_noise_tone=self._radio_noise_tone_from_form(),
            radio_noise_tx_ducking_enabled=bool(self.radio_noise_tx_ducking_enabled_var.get()),
            radio_noise_tx_ducking_depth_percent=self._safe_int(
                self.radio_noise_tx_ducking_depth_percent_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_DEPTH_PERCENT", 85)),
                0,
                95,
            ),
            radio_noise_tx_ducking_attack_ms=self._safe_int(
                self.radio_noise_tx_ducking_attack_ms_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_ATTACK_MS", 60)),
                1,
                500,
            ),
            radio_noise_tx_ducking_hold_ms=self._safe_int(
                self.radio_noise_tx_ducking_hold_ms_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_HOLD_MS", 350)),
                1,
                1500,
            ),
            radio_noise_tx_ducking_release_ms=self._safe_int(
                self.radio_noise_tx_ducking_release_ms_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_RELEASE_MS", 500)),
                1,
                2000,
            ),
            radio_noise_rx_ducking_enabled=bool(self.radio_noise_rx_ducking_enabled_var.get()),
            radio_noise_rx_ducking_depth_percent=self._safe_int(
                self.radio_noise_rx_ducking_depth_percent_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_DEPTH_PERCENT", 45)),
                0,
                95,
            ),
            radio_noise_rx_ducking_attack_ms=self._safe_int(
                self.radio_noise_rx_ducking_attack_ms_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_ATTACK_MS", 80)),
                1,
                500,
            ),
            radio_noise_rx_ducking_hold_ms=self._safe_int(
                self.radio_noise_rx_ducking_hold_ms_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_HOLD_MS", 250)),
                1,
                1500,
            ),
            radio_noise_rx_ducking_release_ms=self._safe_int(
                self.radio_noise_rx_ducking_release_ms_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_RELEASE_MS", 450)),
                1,
                2000,
            ),
        )

    def _network_settings(self, *, room_name: str, password: str) -> NetworkSettings:
        playback = self._playback_settings_from_form()

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
        log_event(
            "network",
            "network.settings.ui_save_requested",
            message="Network settings save requested from UI.",
            context={"server_uri": self._server_uri(), "last_room": last_room or self.settings.last_room},
        )
        self._save_current_settings(last_room=last_room or self.settings.last_room)
        applied = self._apply_live_settings()

        if applied:
            self._show_notice(self.tr("network.settings.saved_and_applied"), "success")
        else:
            self._show_notice(self.tr("network.settings.saved"), "success")

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
            radio_noise_enabled=bool(self.radio_noise_enabled_var.get()),
            radio_noise_volume=float(self._safe_int(self.radio_noise_volume_percent_var.get(), 5, 0, 30)) / 100.0,
            radio_noise_profile=self._radio_noise_profile_from_form(),
            radio_noise_tone=self._radio_noise_tone_from_form(),
            radio_noise_tx_ducking_enabled=bool(self.radio_noise_tx_ducking_enabled_var.get()),
            radio_noise_tx_ducking_depth_percent=self._safe_int(
                self.radio_noise_tx_ducking_depth_percent_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_DEPTH_PERCENT", 85)),
                0,
                95,
            ),
            radio_noise_tx_ducking_attack_ms=self._safe_int(
                self.radio_noise_tx_ducking_attack_ms_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_ATTACK_MS", 60)),
                1,
                500,
            ),
            radio_noise_tx_ducking_hold_ms=self._safe_int(
                self.radio_noise_tx_ducking_hold_ms_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_HOLD_MS", 350)),
                1,
                1500,
            ),
            radio_noise_tx_ducking_release_ms=self._safe_int(
                self.radio_noise_tx_ducking_release_ms_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_RELEASE_MS", 500)),
                1,
                2000,
            ),
            radio_noise_rx_ducking_enabled=bool(self.radio_noise_rx_ducking_enabled_var.get()),
            radio_noise_rx_ducking_depth_percent=self._safe_int(
                self.radio_noise_rx_ducking_depth_percent_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_DEPTH_PERCENT", 45)),
                0,
                95,
            ),
            radio_noise_rx_ducking_attack_ms=self._safe_int(
                self.radio_noise_rx_ducking_attack_ms_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_ATTACK_MS", 80)),
                1,
                500,
            ),
            radio_noise_rx_ducking_hold_ms=self._safe_int(
                self.radio_noise_rx_ducking_hold_ms_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_HOLD_MS", 250)),
                1,
                1500,
            ),
            radio_noise_rx_ducking_release_ms=self._safe_int(
                self.radio_noise_rx_ducking_release_ms_var.get(),
                int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_RELEASE_MS", 450)),
                1,
                2000,
            ),
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
        self.radio_noise_enabled_var.set(bool(safe.radio_noise_enabled))
        self.radio_noise_volume_percent_var.set(int(round(safe.radio_noise_volume * 100)))
        self.radio_noise_profile_var.set(str(safe.radio_noise_profile or "radio"))
        self.radio_noise_tone_var.set(str(getattr(safe, "radio_noise_tone", "low") or "low"))
        self.radio_noise_tx_ducking_enabled_var.set(bool(safe.radio_noise_tx_ducking_enabled))
        self.radio_noise_tx_ducking_depth_percent_var.set(int(safe.radio_noise_tx_ducking_depth_percent))
        self.radio_noise_tx_ducking_attack_ms_var.set(int(safe.radio_noise_tx_ducking_attack_ms))
        self.radio_noise_tx_ducking_hold_ms_var.set(int(safe.radio_noise_tx_ducking_hold_ms))
        self.radio_noise_tx_ducking_release_ms_var.set(int(safe.radio_noise_tx_ducking_release_ms))
        self.radio_noise_rx_ducking_enabled_var.set(bool(safe.radio_noise_rx_ducking_enabled))
        self.radio_noise_rx_ducking_depth_percent_var.set(int(safe.radio_noise_rx_ducking_depth_percent))
        self.radio_noise_rx_ducking_attack_ms_var.set(int(safe.radio_noise_rx_ducking_attack_ms))
        self.radio_noise_rx_ducking_hold_ms_var.set(int(safe.radio_noise_rx_ducking_hold_ms))
        self.radio_noise_rx_ducking_release_ms_var.set(int(safe.radio_noise_rx_ducking_release_ms))

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
            playback = self._playback_settings_from_form()
            manager.update_playback_settings(playback)
            manager.set_transmit_enabled(bool(self.transmit_enabled_var.get()))
            log_event(
                "network",
                "network.settings.live_update_success",
                message="Live network settings were applied.",
                context={
                    "playback_enabled": playback.enabled,
                    "transmit_enabled": bool(self.transmit_enabled_var.get()),
                    "jitter_buffer_ms": playback.jitter_buffer_ms,
                    "frequency_hz": playback.frequency_hz,
                    "volume": playback.volume,
                    "radio_noise_enabled": playback.radio_noise_enabled,
                    "radio_noise_volume": playback.radio_noise_volume,
                    "radio_noise_profile": playback.radio_noise_profile,
                    "radio_noise_tx_ducking_enabled": playback.radio_noise_tx_ducking_enabled,
                    "radio_noise_tx_ducking_depth_percent": playback.radio_noise_tx_ducking_depth_percent,
                    "radio_noise_tx_ducking_attack_ms": playback.radio_noise_tx_ducking_attack_ms,
                    "radio_noise_tx_ducking_hold_ms": playback.radio_noise_tx_ducking_hold_ms,
                    "radio_noise_tx_ducking_release_ms": playback.radio_noise_tx_ducking_release_ms,
                    "radio_noise_rx_ducking_enabled": playback.radio_noise_rx_ducking_enabled,
                    "radio_noise_rx_ducking_depth_percent": playback.radio_noise_rx_ducking_depth_percent,
                    "radio_noise_rx_ducking_attack_ms": playback.radio_noise_rx_ducking_attack_ms,
                    "radio_noise_rx_ducking_hold_ms": playback.radio_noise_rx_ducking_hold_ms,
                    "radio_noise_rx_ducking_release_ms": playback.radio_noise_rx_ducking_release_ms,
                },
            )
            self._append_log("success", self.tr("network.settings.live_updated"))
            return True
        except Exception as exc:
            log_exception(
                "network",
                "network.settings.live_update_failed",
                exc,
                level="warning",
                message="Live network settings could not be applied.",
                context={"server_uri": self._server_uri()},
            )
            self._append_log("warning", self.tr("network.settings.live_update_failed", error=exc))
            return False
        
    def _set_network_quality(
        self,
        state: str,
        detail: str = "",
        *,
        force: bool = False,
        hold_seconds: float = 0.0,
    ) -> None:
        state_key = str(state or "standby").strip().lower()
        now = time.monotonic()

        current_state = str(getattr(self, "network_quality_state", "standby") or "standby")
        hold_until = float(getattr(self, "network_quality_hold_until_monotonic", 0.0) or 0.0)

        # Keep temporary buffer warnings visible long enough to be useful.
        if (
            not force
            and now < hold_until
            and current_state == "buffer_too_low"
            and state_key in {"good", "unstable", "checking"}
        ):
            return

        labels = {
            "standby": self.tr("network.quality.label.standby"),
            "checking": self.tr("network.quality.label.checking"),
            "good": self.tr("network.quality.label.good"),
            "unstable": self.tr("network.quality.label.unstable"),
            "buffer_too_low": self.tr("network.quality.label.buffer_too_low"),
            "server_not_responding": self.tr("network.quality.label.server_not_responding"),
            "reconnecting": self.tr("network.quality.label.reconnecting"),
        }

        default_details = {
            "standby": self.tr("network.quality.detail.idle"),
            "checking": self.tr("network.quality.detail.waiting_server_response"),
            "good": self.tr("network.quality.detail.good"),
            "unstable": self.tr("network.quality.detail.unstable"),
            "buffer_too_low": self.tr("network.quality.detail.buffer_too_low"),
            "server_not_responding": self.tr("network.quality.detail.server_not_responding"),
            "reconnecting": self.tr("network.quality.detail.reconnecting"),
        }

        warning_color = getattr(MatrixTheme, "warning", MatrixTheme.text_dim)
        error_color = getattr(MatrixTheme, "error", warning_color)

        colors = {
            "standby": MatrixTheme.text_dim,
            "checking": MatrixTheme.text_dim,
            "good": MatrixTheme.accent,
            "unstable": warning_color,
            "buffer_too_low": warning_color,
            "server_not_responding": error_color,
            "reconnecting": warning_color,
        }

        if state_key not in labels:
            state_key = "checking"

        if hold_seconds > 0:
            self.network_quality_hold_until_monotonic = max(
                hold_until,
                now + float(hold_seconds),
            )
        elif force:
            self.network_quality_hold_until_monotonic = 0.0

        self.network_quality_state = state_key

        label_text = labels[state_key]
        detail_text = detail or default_details[state_key]

        try:
            self.network_quality_var.set(label_text)
            self.network_quality_detail_var.set(detail_text)
        except Exception:
            pass

        label = getattr(self, "network_quality_label", None)
        if label is not None:
            try:
                label.configure(foreground=colors.get(state_key, MatrixTheme.text_dim))
            except Exception:
                pass

    def _network_quality_from_ping(self, ping_ms: int | None) -> tuple[str, str]:
        if ping_ms is None:
            return "checking", self.tr("network.quality.detail.waiting_server_ping")

        if ping_ms <= 250:
            return "good", self.tr("network.quality.detail.good_with_ping", ping_ms=ping_ms)

        if ping_ms <= 700:
            return "unstable", self.tr("network.quality.detail.latency_elevated", ping_ms=ping_ms)

        return "unstable", self.tr("network.quality.detail.high_latency", ping_ms=ping_ms)

    def _update_network_quality_from_server_pong(self) -> None:
        ping_ms = self._latest_server_ping_ms()
        state, detail = self._network_quality_from_ping(ping_ms)
        self._set_network_quality(state, detail)

    def _is_buffer_quality_warning(self, lowered_text: str) -> bool:
        patterns = (
            "myöhässä tullut tone",
            "liian myöhässä tullut tone",
            "nosta viivepuskuri",
            "viivepuskuri on jo maksimi",
        )
        return any(pattern in lowered_text for pattern in patterns)

    def _refresh_network_quality_indicator(self) -> None:
        manager = getattr(self.app, "network_manager", None)

        if manager is None:
            self._set_network_quality(
                "standby",
                self.tr("network.quality.detail.manager_missing"),
                force=True,
            )
            return

        try:
            is_running = bool(manager.is_running)
        except Exception:
            is_running = False

        if not is_running:
            self._set_network_quality(
                "standby",
                self.tr("network.quality.detail.idle"),
                force=True,
            )
            return

        try:
            control_ready = bool(getattr(manager, "control_channel_ready", False))
        except Exception:
            control_ready = False

        if not control_ready:
            if self.connected_room_key or self.connected_room_id:
                self._set_network_quality(
                    "reconnecting",
                    self.tr("network.quality.detail.control_not_ready"),
                    force=True,
                )
            else:
                self._set_network_quality(
                    "checking",
                    self.tr("network.quality.detail.waiting_lobby_control"),
                    force=True,
                )
            return

        if self.server_info_error_text:
            self._set_network_quality(
                "server_not_responding",
                self.tr(
                    "network.quality.detail.server_query_failed",
                    message=self.server_info_error_text,
                ),
                force=True,
            )
            return

        pong = self._latest_server_pong()
        if not pong:
            self._set_network_quality(
                "checking",
                self.tr("network.quality.detail.waiting_first_server_ping"),
            )
            return

        try:
            received_monotonic = float(pong.get("client_received_monotonic") or 0.0)
        except Exception:
            received_monotonic = 0.0

        if received_monotonic > 0:
            age_seconds = time.monotonic() - received_monotonic

            if age_seconds > 120.0:
                self._set_network_quality(
                    "server_not_responding",
                    self.tr(
                        "network.quality.detail.no_recent_ping",
                        seconds=f"{age_seconds:.0f}",
                    ),
                    force=True,
                )
                return

            if age_seconds > 75.0:
                self._set_network_quality(
                    "unstable",
                    self.tr(
                        "network.quality.detail.ping_getting_old",
                        seconds=f"{age_seconds:.0f}",
                    ),
                )
                return

        self._update_network_quality_from_server_pong()

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
            log_event(
                "network",
                "network.playback.reset_after_resume",
                level="warning",
                message="Receive playback reset after a long UI pause or sleep/resume.",
                context={"gap_seconds": round(gap_seconds, 3), "reset_gap_seconds": reset_gap_seconds},
            )
            self._append_log(
                "warning",
                self.tr(
                    "network.playback.reset_after_pause",
                    seconds=f"{gap_seconds:.1f}",
                ),
            )
        except Exception as exc:
            log_exception(
                "network",
                "network.playback.reset_after_resume_failed",
                exc,
                level="warning",
                message="Receive playback reset after pause failed.",
                context={"gap_seconds": round(gap_seconds, 3), "reset_gap_seconds": reset_gap_seconds},
            )
            self._append_log(
                "warning",
                self.tr(
                    "network.playback.reset_failed",
                    error=str(exc),
                ),
            )

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

            self._refresh_network_quality_indicator()

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
            self._update_network_quality_from_server_pong()
            return

    def _handle_status(self, level: str, text: str) -> None:
        if not text or self._should_hide_status(level, text):
            return

        level_key = str(level or "info").strip().lower()
        lowered = text.lower()

        if level_key == "server_pong" or lowered.startswith("server ping:"):
            self._append_log("success", text)
            return

        if self._is_buffer_quality_warning(lowered):
            self._set_network_quality(
                "buffer_too_low",
                text,
                hold_seconds=20.0,
            )

        if lowered.startswith("yhteys aulaan muodostettu") or lowered.startswith("lobby connected"):
            translated_text = self.tr("network.status.lobby_connected")

            if self.current_view == "lobby":
                self.status_var.set(self.tr("network.status.standby"))

            self._set_network_quality(
                "checking",
                self.tr("network.quality.detail.lobby_connected"),
                force=True,
            )

            self.room_status_var.set(translated_text)
            self._append_log("info", translated_text)
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
            self.status_var.set(self.tr("network.status.reconnecting"))
        elif self.current_view == "lobby":
            self.status_var.set(self.tr("network.status.retrying"))

        self._set_network_quality("reconnecting", text, force=True)

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

        self.status_var.set(self.tr("network.status.online"))
        self.room_status_var.set(self.tr("network.room.connected", room=title))
        self._set_network_quality(
            "checking",
            self.tr("network.quality.detail.connected_waiting_ping"),
            force=True,
        )

        self._remember_successful_private_room()

        self.show_room_view()
        log_event(
            "network",
            "network.room.ui_connected",
            message="UI switched to connected room state.",
            context={
                "server_uri": self._server_uri(),
                "room_key": room_key,
                "room_id": visible_room_id,
                "room_title": title,
                "room_access": self.connected_room_access,
            },
        )
        self._append_log("success", self.tr("network.room.connected", room=title))

    def _handle_connection_error(self, text: str) -> None:
        message = self._friendly_error_message(text)
        log_event(
            "network",
            "network.room.ui_connection_error",
            level="error",
            message=message,
            context={
                "server_uri": self._server_uri(),
                "raw_error": text,
                "pending_room_key": self.pending_room_key,
                "pending_room_title": self.pending_room_title,
                "pending_room_access": self.pending_room_access,
            },
        )

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

        self.status_var.set(self.tr("network.status.error"))
        self.room_status_var.set(message)
        self._set_network_quality(
            "server_not_responding",
            message,
            force=True,
        )

        if self.current_view != "lobby":
            self.show_lobby_view()

        self._show_notice(message, "error")
        self._append_log("error", message)

    def _friendly_error_message(self, text: str) -> str:
        room_name = (
            self.pending_room_title
            or self.private_room_var.get()
            or self.tr("network.remembered_rooms.default_title")
        )
        lowered = text.lower()

        if "salasana ei täsmää" in lowered or ("password" in lowered and "match" in lowered):
            return self.tr(
                "network.connection.error.password_mismatch",
                room=room_name,
            )

        if "winerror 1225" in lowered or "hylkäsi verkkoyhteyden" in lowered or "connection refused" in lowered:
            return self.tr("network.connection.error.relay_unreachable")

        if "reserved" in lowered or "varattu" in lowered:
            return self.tr(
                "network.connection.error.reserved_room",
                room=room_name,
            )

        if "getaddrinfo failed" in lowered or "errno 11002" in lowered:
            return self.tr("network.connection.error.dns_failed")

        return self.tr(
            "network.connection.error.generic",
            message=text,
        )

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

        level_labels = {
            "info": self.tr("network.log.level.info"),
            "success": self.tr("network.log.level.success"),
            "warning": self.tr("network.log.level.warning"),
            "error": self.tr("network.log.level.error"),
        }

        level_label = level_labels.get(tag, level_key.upper().replace(" ", "_"))
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
        log_event(
            "network",
            "network.window.close_started",
            message="Network window close started.",
            context={
                "server_uri": self._server_uri(),
                "connected_room_key": self.connected_room_key,
                "connected_room_id": self.connected_room_id,
                "connected_room_access": self.connected_room_access,
            },
        )
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
        except Exception as exc:
            log_exception(
                "network",
                "network.window.manager_stop_failed",
                exc,
                level="warning",
                message="Network manager stop failed while closing the network window.",
                context={
                    "server_uri": self._server_uri(),
                    "connected_room_key": self.connected_room_key,
                    "connected_room_id": self.connected_room_id,
                    "connected_room_access": self.connected_room_access,
                },
            )

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
            log_event(
                "network",
                "network.window.closed",
                message="Network window closed.",
                context={
                    "server_uri": self._server_uri(),
                    "connected_room_key": self.connected_room_key,
                    "connected_room_id": self.connected_room_id,
                    "connected_room_access": self.connected_room_access,
                },
            )
        except Exception as exc:
            log_exception(
                "network",
                "network.window.close_failed",
                exc,
                level="warning",
                message="Network window could not be destroyed cleanly.",
                context={"server_uri": self._server_uri()},
            )