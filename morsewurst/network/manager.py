# ============================================================
# morsewurst/network/manager.py
# ============================================================

from __future__ import annotations

import asyncio
from concurrent.futures import CancelledError as FutureCancelledError
from concurrent.futures import TimeoutError as FutureTimeoutError
import queue
import ssl
import threading
import time
from typing import Any, Dict, Optional

import morsewurst.config as config
from morsewurst.core.logging_service import log_event, log_exception

from morsewurst.network.identity import (
    OperatorIdentity,
    OperatorIdentityError,
    load_or_create_operator_identity,
    sign_operator_challenge,
)
from morsewurst.network.jitter_buffer import JitterBuffer
from morsewurst.network.models import NetworkSettings, PlaybackSettings
from morsewurst.network.protocol import (
    ProtocolError,
    decode_message,
    encode_message,
    make_auth,
    make_client_hello,
    make_client_ping,
    make_lobby_hello,
    make_server_info_request,
    make_key_message,
    make_tone_message,
    new_id,
)
from morsewurst.network.room_server import RoomServer
from morsewurst.network.tone_player import TonePlayer

try:
    from websockets.asyncio.client import connect
except ImportError:  # pragma: no cover
    from websockets import connect  # type: ignore[assignment]


class NetworkManager:
    """Thread-safe facade for Morsewurst WebSocket networking.

    Tkinter stays in the main thread. This manager owns an asyncio event loop in
    a background thread and exposes synchronous methods for the UI.
    """

    def __init__(self) -> None:
        self.client_id = new_id("client")
        self.stream_id = new_id("stream")
        self.status_queue: "queue.Queue[dict[str, Any]]" = queue.Queue()

        self.last_server_info: dict[str, Any] | None = None
        self.last_server_pong: dict[str, Any] | None = None

        self.last_joined_room_key: str = ""
        self.last_joined_room_name: str = ""
        self.last_joined_room_id: str = ""
        self.last_joined_room_access: str = ""
        self.last_operator_id: str = ""
        self.last_operator_verified: bool = False

        self._lobby_websocket = None

        self.playback_settings = PlaybackSettings()
        self.tone_player = self._create_tone_player(self.playback_settings)
        self.jitter_buffer = JitterBuffer(
            self.tone_player,
            playback_settings=self.playback_settings,
            status_callback=self._status,
        )

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._server: Optional[RoomServer] = None
        self._client_send_queue: Optional[asyncio.Queue[dict[str, Any]]] = None
        self._client_websocket = None
        self._settings = NetworkSettings()
        self._mode = "stopped"
        self._seq = 0
        self._closed = threading.Event()
        self._closed.set()
        self._control_ready_event = threading.Event()
        self._room_noise_active = False
        self._active_local_key_duck_keys: set[str] = set()

        log_event(
            "network",
            "network.manager.initialized",
            message="NetworkManager initialized.",
            context={
                "mode": self._mode,
                "client_id": self.client_id,
                "stream_id": self.stream_id,
            },
        )

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_running(self) -> bool:
        return self._mode in {"host", "client"}
    
    @property
    def control_channel_ready(self) -> bool:
        """True when server info and ping messages can be sent safely."""
        return self._control_ready_event.is_set()

    def _create_tone_player(self, playback_settings: PlaybackSettings) -> TonePlayer:
        player = TonePlayer(
            frequency_hz=playback_settings.frequency_hz,
            volume=playback_settings.volume,
            waveform=playback_settings.waveform,
            sample_rate=playback_settings.sample_rate,
            blocksize=playback_settings.blocksize,
            latency=playback_settings.latency,
            output_device=playback_settings.output_device,
            status_callback=self._tone_player_status,
        )
        self._configure_tone_player_background_noise(player, playback_settings)
        return player

    def start_host(self, settings: NetworkSettings) -> None:
        log_event(
            "network",
            "network.manager.start_host",
            message="Starting network host mode.",
            context=_settings_log_context(settings, mode="host"),
        )
        self.stop()
        self._control_ready_event.clear()
        self._settings = settings
        self.playback_settings = settings.playback
        self.tone_player.stop()
        self.tone_player = self._create_tone_player(settings.playback)
        self.jitter_buffer = JitterBuffer(
            self.tone_player,
            playback_settings=settings.playback,
            status_callback=self._status,
        )
        self._set_mode("host", event="network.manager.mode_changed")
        self._start_loop()
        assert self._loop is not None
        asyncio.run_coroutine_threadsafe(self._host_main(settings), self._loop)

    def connect_to_room(self, settings: NetworkSettings) -> None:
        access = "private" if settings.password else "public"
        log_event(
            "network",
            f"network.room.join_{access}_started",
            message=f"Joining {access} room.",
            context={**_settings_log_context(settings, mode="client"), "room_access": access},
        )
        self.stop()
        self._control_ready_event.clear()
        self._settings = settings
        self.playback_settings = settings.playback
        self.tone_player.stop()
        self.tone_player = self._create_tone_player(settings.playback)
        self.jitter_buffer = JitterBuffer(
            self.tone_player,
            playback_settings=settings.playback,
            status_callback=self._status,
        )
        self._set_mode("client", event="network.manager.mode_changed")
        self._start_loop()
        assert self._loop is not None
        asyncio.run_coroutine_threadsafe(self._client_main(settings), self._loop)

    def connect_lobby_presence(self, settings: NetworkSettings) -> None:
        if self.is_running:
            log_event(
                "network",
                "network.lobby.presence_skipped",
                message="Lobby presence was not started because networking is already running.",
                context=_settings_log_context(settings, mode=self._mode),
            )
            return

        log_event(
            "network",
            "network.lobby.presence_starting",
            message="Starting lobby presence connection.",
            context=_settings_log_context(settings, mode="client"),
        )
        self.stop()
        self._control_ready_event.clear()
        self._settings = settings
        self._set_mode("client", event="network.manager.mode_changed")
        self._start_loop()

        assert self._loop is not None
        asyncio.run_coroutine_threadsafe(self._lobby_presence_main(settings), self._loop)

    async def _lobby_presence_main(self, settings: NetworkSettings) -> None:
        ssl_context = self._client_ssl_context(settings)
        reconnect_delay = 1.0

        while self._stop_event is not None and not self._stop_event.is_set():
            try:
                log_event(
                    "network",
                    "network.lobby.connecting",
                    message="Connecting lobby presence WebSocket.",
                    context={**_settings_log_context(settings, mode=self._mode), "reconnect_delay_seconds": reconnect_delay},
                )
                async with connect(
                    settings.server_uri,
                    ssl=ssl_context,
                    max_size=512_000,
                    ping_interval=20,
                    ping_timeout=60,
                    open_timeout=15,
                    close_timeout=5,
                ) as websocket:
                    self._lobby_websocket = websocket

                    await websocket.send(
                        encode_message(
                            make_lobby_hello(
                                callsign=settings.callsign,
                                client_id=self.client_id,
                                installation_id=settings.installation_id,
                                client_version=getattr(config, "APP_VERSION", ""),
                            )
                        )
                    )

                    self._control_ready_event.set()
                    log_event(
                        "network",
                        "network.control_channel.ready",
                        message="Control channel is ready for lobby presence.",
                        context=_settings_log_context(settings, mode=self._mode),
                    )

                    reconnect_delay = 1.0

                    log_event(
                        "network",
                        "network.lobby.connected",
                        message="Lobby presence WebSocket connected.",
                        context=_settings_log_context(settings, mode=self._mode),
                    )
                    self._status("info", "Yhteys aulaan muodostettu.")

                    keepalive = asyncio.create_task(self._lobby_keepalive_loop(websocket))
                    receiver = asyncio.create_task(self._lobby_receiver_loop(websocket))

                    done, pending = await asyncio.wait(
                        {keepalive, receiver},
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    for task in pending:
                        task.cancel()

                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)

                    results = await asyncio.gather(*done, return_exceptions=True)

                    for result in results:
                        if isinstance(result, asyncio.CancelledError):
                            raise result
                        if isinstance(result, Exception):
                            raise result

                    if self._stop_event is not None and self._stop_event.is_set():
                        break

                    raise ConnectionError("Lobby connection closed.")

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                self._lobby_websocket = None
                self._control_ready_event.clear()
                log_exception(
                    "network",
                    "network.lobby.connection_failed",
                    exc,
                    level="warning",
                    message="Lobby presence connection failed.",
                    context={
                        **_settings_log_context(settings, mode=self._mode),
                        **_exception_context(exc),
                        "reconnect_delay_seconds": reconnect_delay,
                    },
                )

                if self._stop_event is not None and self._stop_event.is_set():
                    break

                error_text = self._format_connection_error(exc)
                log_event(
                    "network",
                    "network.lobby.reconnecting",
                    level="warning",
                    message="Lobby presence will reconnect after delay.",
                    context={
                        **_settings_log_context(settings, mode=self._mode),
                        **_exception_context(exc),
                        "reconnect_delay_seconds": reconnect_delay,
                    },
                )
                self._status(
                    "warning",
                    (
                        f"Lobby-yhteyttä yritetään uudelleen: {error_text} "
                        f"Uusi yritys {reconnect_delay:.0f} s kuluttua."
                    ),
                )

                if self._stop_event is None:
                    break

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=reconnect_delay)
                    break
                except asyncio.TimeoutError:
                    pass

                reconnect_delay = min(reconnect_delay * 2.0, 30.0)

        self._lobby_websocket = None
        self._control_ready_event.clear()
        log_event(
            "network",
            "network.lobby.disconnected",
            message="Lobby presence connection stopped.",
            context=_settings_log_context(settings, mode=self._mode),
        )

    async def _lobby_receiver_loop(self, websocket: Any) -> None:
        async for raw in websocket:
            message = decode_message(raw)
            message_type = str(message.get("type") or "")

            if message_type == "server_info":
                message["client_received_monotonic"] = time.monotonic()
                message["client_received_time"] = time.time()
                self.last_server_info = message
                log_event(
                    "network",
                    "network.server_info.response_success",
                    message="Server info response received.",
                    context=_server_info_log_context(message),
                )
                self._queue_payload("server_info", "", message)
                continue

            if message_type == "server_pong":
                now_ms = int(time.time() * 1000)

                try:
                    client_sent_ms = int(message.get("client_sent_ms") or 0)
                except Exception:
                    client_sent_ms = 0

                if client_sent_ms > 0:
                    message["round_trip_ms"] = max(0, now_ms - client_sent_ms)

                message["client_received_monotonic"] = time.monotonic()
                message["client_received_time"] = time.time()
                self.last_server_pong = message

                ping_id = str(message.get("ping_id") or "")
                is_keepalive = ping_id.startswith("lobby-keepalive")

                if is_keepalive:
                    self._queue_payload("server_pong", "", message)
                else:
                    rtt = message.get("round_trip_ms")
                    log_event(
                        "network",
                        "network.server_ping.response_success",
                        message="Server ping response received.",
                        context=_server_pong_log_context(message),
                    )
                    text = f"Server ping: {rtt} ms." if rtt is not None else "Server ping received."
                    self._queue_payload("server_pong", text, message)

                continue

            if message_type == "status":
                self._handle_status_message(message, source="lobby")
                continue

            log_event(
                "network",
                "network.lobby.unhandled_message",
                level="debug",
                message="Unhandled lobby message received.",
                context={"message_type": message_type or "unknown"},
            )

    async def _lobby_keepalive_loop(self, websocket: Any) -> None:
        while True:
            await asyncio.sleep(25.0)

            await asyncio.wait_for(
                websocket.send(
                    encode_message(
                        make_client_ping(
                            sender_id=self.client_id,
                            ping_id=new_id("lobby-keepalive"),
                        )
                    )
                ),
                timeout=float(config.CLIENT_SEND_TIMEOUT_SECONDS),
            )

    def stop(self) -> None:
        previous_mode = self._mode
        self._room_noise_active = False
        log_event(
            "network",
            "network.manager.stop_started",
            message="Stopping network manager.",
            context={
                "previous_mode": previous_mode,
                "control_channel_ready": self.control_channel_ready,
                "has_loop": self._loop is not None,
            },
        )

        if self._loop is None:
            self._set_mode("stopped", event="network.manager.mode_changed")
            self._control_ready_event.clear()
            self.jitter_buffer.clear()
            self.tone_player.stop()
            self._lobby_websocket = None
            log_event(
                "network",
                "network.manager.stopped",
                message="Network manager stopped.",
                context={"previous_mode": previous_mode, "mode": self._mode},
            )
            return

        loop = self._loop
        stop_event = self._stop_event

        if stop_event is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(stop_event.set)
            except RuntimeError as exc:
                log_exception(
                    "network",
                    "network.manager.stop_signal_failed",
                    exc,
                    level="debug",
                    message="Network stop signal could not be scheduled.",
                    context={"previous_mode": previous_mode},
                )

        futures = []

        if not loop.is_closed():
            if self._server is not None:
                try:
                    futures.append(asyncio.run_coroutine_threadsafe(self._server.stop(), loop))
                except Exception as exc:
                    log_exception(
                        "network",
                        "network.manager.server_stop_schedule_failed",
                        exc,
                        level="debug",
                        message="Hosted room server stop could not be scheduled.",
                        context={"previous_mode": previous_mode},
                    )

            if self._client_websocket is not None:
                try:
                    futures.append(asyncio.run_coroutine_threadsafe(self._client_websocket.close(), loop))
                except Exception as exc:
                    log_exception(
                        "network",
                        "network.manager.client_close_schedule_failed",
                        exc,
                        level="debug",
                        message="Client WebSocket close could not be scheduled.",
                        context={"previous_mode": previous_mode},
                    )

            if self._lobby_websocket is not None:
                try:
                    futures.append(asyncio.run_coroutine_threadsafe(self._lobby_websocket.close(), loop))
                except Exception as exc:
                    log_exception(
                        "network",
                        "network.manager.lobby_close_schedule_failed",
                        exc,
                        level="debug",
                        message="Lobby WebSocket close could not be scheduled.",
                        context={"previous_mode": previous_mode},
                    )

            for future in futures:
                try:
                    future.result(timeout=0.8)
                except FutureCancelledError:
                    # A cancellation here is expected during normal shutdown:
                    # stop() has already requested the network loop and active
                    # WebSocket tasks to stop. Do not log it as a failed close.
                    pass
                except FutureTimeoutError as exc:
                    log_exception(
                        "network",
                        "network.manager.close_wait_timeout",
                        exc,
                        level="debug",
                        message="Network close future timed out while stopping.",
                        context={"previous_mode": previous_mode},
                    )
                except Exception as exc:
                    log_exception(
                        "network",
                        "network.manager.close_wait_failed",
                        exc,
                        level="debug",
                        message="Network close future did not finish cleanly.",
                        context={"previous_mode": previous_mode},
                    )

        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)

        self._loop = None
        self._thread = None
        self._stop_event = None
        self._server = None
        self._client_send_queue = None
        self._client_websocket = None
        self._lobby_websocket = None
        self._control_ready_event.clear()
        self._set_mode("stopped", event="network.manager.mode_changed")
        self._active_local_key_duck_keys.clear()
        self.jitter_buffer.clear()
        self.tone_player.stop()
        log_event(
            "network",
            "network.manager.stopped",
            message="Network manager stopped.",
            context={"previous_mode": previous_mode, "mode": self._mode},
        )
        self._status("info", "Verkkoyhteys pysäytetty.")

    def publish_local_key(self, event: Dict[str, Any]) -> None:
        if not self.is_running:
            return
        if not self._settings.transmit_enabled:
            return
        if event.get("type") != "key":
            return
        if self._loop is None:
            return

        self._seq += 1
        try:
            message = make_key_message(
                key_event=event,
                sender_id=self.client_id,
                sender_name=self._settings.callsign,
                seq=self._seq,
                stream_id=self.stream_id,
            )
        except ProtocolError as exc:
            log_exception(
                "network",
                "network.key.send_failed",
                exc,
                level="warning",
                message="Local V1 key message could not be created.",
                context={"mode": self._mode, "event_type": event.get("type")},
            )
            self._status("warning", f"Key-viestiä ei lähetetty: {exc}")
            return

        self._duck_room_noise_for_local_key(message.get("key", event))
        asyncio.run_coroutine_threadsafe(self._send_tone_message(message), self._loop)

    def publish_local_tone(self, event: Dict[str, Any]) -> None:
        if not self.is_running:
            return
        if not self._settings.transmit_enabled:
            return
        if event.get("type") != "tone":
            return
        if self._loop is None:
            return

        self._seq += 1
        try:
            message = make_tone_message(
                tone_event=event,
                sender_id=self.client_id,
                sender_name=self._settings.callsign,
                seq=self._seq,
                stream_id=self.stream_id,
            )
        except ProtocolError as exc:
            log_exception(
                "network",
                "network.telemetry.send_failed",
                exc,
                level="warning",
                message="Local tone message could not be created.",
                context={"mode": self._mode, "event_type": event.get("type")},
            )
            self._status("warning", f"Tone-viestiä ei lähetetty: {exc}")
            return

        self._duck_room_noise_for_local_tone(event)
        asyncio.run_coroutine_threadsafe(self._send_tone_message(message), self._loop)

    def update_playback_settings(self, settings: PlaybackSettings) -> None:
        log_event(
            "network",
            "network.playback.settings_updated",
            message="Network playback settings updated.",
            context={
                "enabled": settings.enabled,
                "jitter_buffer_ms": settings.jitter_buffer_ms,
                "frequency_hz": settings.frequency_hz,
                "volume": settings.volume,
                "waveform": settings.waveform,
                "radio_noise_enabled": settings.radio_noise_enabled,
                "radio_noise_volume": settings.radio_noise_volume,
                "radio_noise_profile": settings.radio_noise_profile,
                "radio_noise_tone": settings.radio_noise_tone,
                "radio_noise_tx_ducking_enabled": settings.radio_noise_tx_ducking_enabled,
                "radio_noise_tx_ducking_depth_percent": settings.radio_noise_tx_ducking_depth_percent,
                "radio_noise_tx_ducking_attack_ms": settings.radio_noise_tx_ducking_attack_ms,
                "radio_noise_tx_ducking_hold_ms": settings.radio_noise_tx_ducking_hold_ms,
                "radio_noise_tx_ducking_release_ms": settings.radio_noise_tx_ducking_release_ms,
                "radio_noise_rx_ducking_enabled": settings.radio_noise_rx_ducking_enabled,
                "radio_noise_rx_ducking_depth_percent": settings.radio_noise_rx_ducking_depth_percent,
                "radio_noise_rx_ducking_attack_ms": settings.radio_noise_rx_ducking_attack_ms,
                "radio_noise_rx_ducking_hold_ms": settings.radio_noise_rx_ducking_hold_ms,
                "radio_noise_rx_ducking_release_ms": settings.radio_noise_rx_ducking_release_ms,
            },
        )
        room_noise_active = self._room_noise_active
        self.playback_settings = settings
        self.tone_player.stop()
        self.tone_player = self._create_tone_player(settings)
        self.jitter_buffer = JitterBuffer(
            self.tone_player,
            playback_settings=settings,
            status_callback=self._status,
        )
        self._room_noise_active = room_noise_active
        if room_noise_active:
            self._start_room_background_noise()

    def reset_receive_playback(self) -> None:
        log_event(
            "network",
            "network.playback.reset_started",
            level="warning",
            message="Receive playback reset started.",
            context={"mode": self._mode, "control_channel_ready": self.control_channel_ready},
        )
        self.jitter_buffer.clear()

        try:
            self.tone_player.reset_clock()
        except AttributeError:
            self.tone_player.clear()

        log_event(
            "network",
            "network.playback.reset_success",
            level="warning",
            message="Receive playback was resynchronized.",
            context={"mode": self._mode},
        )
        self._status("warning", "Vastaanoton äänentoisto synkronoitiin uudelleen.")

    def set_transmit_enabled(self, enabled: bool) -> None:
        self._settings.transmit_enabled = bool(enabled)
        log_event(
            "network",
            "network.transmit.enabled_changed",
            message="Network transmit setting changed.",
            context={"enabled": bool(enabled), "mode": self._mode},
        )

    def _configure_tone_player_background_noise(self, player: TonePlayer, settings: PlaybackSettings) -> None:
        player.configure_background_noise(
            enabled=bool(settings.radio_noise_enabled),
            volume=float(settings.radio_noise_volume),
            profile=settings.radio_noise_profile,
            tone=settings.radio_noise_tone,
            tx_ducking_enabled=bool(settings.radio_noise_tx_ducking_enabled),
            tx_ducking_depth_percent=settings.radio_noise_tx_ducking_depth_percent,
            tx_ducking_attack_ms=settings.radio_noise_tx_ducking_attack_ms,
            tx_ducking_hold_ms=settings.radio_noise_tx_ducking_hold_ms,
            tx_ducking_release_ms=settings.radio_noise_tx_ducking_release_ms,
            rx_ducking_enabled=bool(settings.radio_noise_rx_ducking_enabled),
            rx_ducking_depth_percent=settings.radio_noise_rx_ducking_depth_percent,
            rx_ducking_attack_ms=settings.radio_noise_rx_ducking_attack_ms,
            rx_ducking_hold_ms=settings.radio_noise_rx_ducking_hold_ms,
            rx_ducking_release_ms=settings.radio_noise_rx_ducking_release_ms,
        )

    def _start_room_background_noise(self) -> None:
        self._room_noise_active = True
        self._configure_tone_player_background_noise(self.tone_player, self.playback_settings)
        if not self.playback_settings.radio_noise_enabled:
            return
        try:
            self.tone_player.start_background_noise()
            log_event(
                "network",
                "network.radio_noise.started",
                message="Network room radio noise started.",
                context={
                    "mode": self._mode,
                    "room_key": self.last_joined_room_key,
                    "volume": self.playback_settings.radio_noise_volume,
                    "profile": self.playback_settings.radio_noise_profile,
                    "tone": self.playback_settings.radio_noise_tone,
                },
            )
        except Exception as exc:
            log_exception(
                "network",
                "network.radio_noise.start_failed",
                exc,
                level="warning",
                message="Network room radio noise could not be started.",
                context={"mode": self._mode},
            )

    def _duck_room_noise_for_local_key(self, event: Dict[str, Any]) -> None:
        if not self._room_noise_active or not self.playback_settings.radio_noise_enabled:
            return

        state = str(event.get("state") or "").strip().lower()
        if state not in {"down", "up"}:
            return

        duck_key = self._local_key_duck_key(event)

        try:
            if state == "down":
                self._active_local_key_duck_keys.add(duck_key)
                self.tone_player.start_live_noise_duck(kind="tx", key=duck_key)
            else:
                if duck_key in self._active_local_key_duck_keys:
                    self._active_local_key_duck_keys.discard(duck_key)
                    self.tone_player.stop_live_noise_duck(kind="tx", key=duck_key)
        except Exception as exc:
            log_exception(
                "network",
                "network.radio_noise.tx_key_duck_failed",
                exc,
                level="debug",
                message="Network room radio noise TX key ducking failed.",
                context={"mode": self._mode, "key_state": state},
            )

    def _local_key_duck_key(self, event: Dict[str, Any]) -> str:
        return ":".join(
            [
                str(event.get("src") or "unknown"),
                str(event.get("device") or ""),
                str(event.get("mode") or ""),
                str(event.get("key") or event.get("pin") or ""),
                str(event.get("el") or ""),
            ]
        )

    def _duck_room_noise_for_local_tone(self, event: Dict[str, Any]) -> None:
        if not self._room_noise_active or not self.playback_settings.radio_noise_enabled:
            return

        duration_seconds = 0.0
        try:
            duration_seconds = max(0.0, float(event.get("dur") or 0.0) / 1_000_000.0)
        except Exception:
            duration_seconds = 0.0

        if duration_seconds <= 0.0:
            return

        try:
            self.tone_player.duck_noise(kind="tx", duration_seconds=duration_seconds)
        except Exception as exc:
            log_exception(
                "network",
                "network.radio_noise.tx_duck_failed",
                exc,
                level="debug",
                message="Network room radio noise TX ducking failed.",
                context={"mode": self._mode},
            )

    def request_server_info(self) -> None:
        if not self.is_running:
            log_event(
                "network",
                "network.server_info.request_skipped",
                level="warning",
                message="Server info request skipped because networking is not running.",
                context={"mode": self._mode},
            )
            return
        if self._loop is None:
            log_event(
                "network",
                "network.server_info.request_skipped",
                level="warning",
                message="Server info request skipped because event loop is not ready.",
                context={"mode": self._mode},
            )
            return
        if not self.control_channel_ready:
            log_event(
                "network",
                "network.control_channel.not_ready",
                level="warning",
                message="Server info request could not be sent because the control channel is not ready.",
                context={"request": "server_info", "mode": self._mode},
            )
            return

        message = make_server_info_request(sender_id=self.client_id)

        log_event(
            "network",
            "network.server_info.request_started",
            message="Server info request queued.",
            context={"mode": self._mode, "via": "client_queue" if self._client_send_queue is not None else "lobby_websocket"},
        )

        if self._client_send_queue is not None:
            asyncio.run_coroutine_threadsafe(self._send_client_message(message), self._loop)
            return

        if self._lobby_websocket is not None:
            asyncio.run_coroutine_threadsafe(self._send_lobby_message(message), self._loop)
            return

        log_event(
            "network",
            "network.server_info.request_failed",
            level="warning",
            message="Server info request had no available send channel.",
            context={"mode": self._mode, "control_channel_ready": self.control_channel_ready},
        )


    def request_server_ping(self) -> None:
        if not self.is_running:
            log_event(
                "network",
                "network.server_ping.request_skipped",
                level="warning",
                message="Server ping request skipped because networking is not running.",
                context={"mode": self._mode},
            )
            return
        if self._loop is None:
            log_event(
                "network",
                "network.server_ping.request_skipped",
                level="warning",
                message="Server ping request skipped because event loop is not ready.",
                context={"mode": self._mode},
            )
            return
        if not self.control_channel_ready:
            log_event(
                "network",
                "network.control_channel.not_ready",
                level="warning",
                message="Server ping request could not be sent because the control channel is not ready.",
                context={"request": "server_ping", "mode": self._mode},
            )
            return

        message = make_client_ping(sender_id=self.client_id)
        log_event(
            "network",
            "network.server_ping.request_started",
            message="Server ping request queued.",
            context={"mode": self._mode, "via": "client_queue" if self._client_send_queue is not None else "lobby_websocket"},
        )

        if self._client_send_queue is not None:
            asyncio.run_coroutine_threadsafe(self._send_client_message(message), self._loop)
            return

        if self._lobby_websocket is not None:
            asyncio.run_coroutine_threadsafe(self._send_lobby_message(message), self._loop)
            return

        log_event(
            "network",
            "network.server_ping.request_failed",
            level="warning",
            message="Server ping request had no available send channel.",
            context={"mode": self._mode, "control_channel_ready": self.control_channel_ready},
        )


    async def _enqueue_client_message(self, message: Dict[str, Any]) -> bool:
        if self._mode != "client":
            return False

        send_queue = self._client_send_queue
        if send_queue is None:
            return False

        try:
            send_queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            return False


    async def _send_client_message(self, message: Dict[str, Any]) -> None:
        sent = await self._enqueue_client_message(message)

        if not sent:
            log_event(
                "network",
                "network.client.send_queue_failed",
                level="warning",
                message="Network message could not be queued.",
                context={"mode": self._mode, "message_type": _message_type(message)},
            )
            self._status("warning", "Verkkoviestiä ei voitu lähettää, koska yhteys ei ole valmis tai lähetysjono on täynnä.")


    async def _send_lobby_message(self, message: Dict[str, Any]) -> bool:
        websocket = self._lobby_websocket
        if websocket is None:
            log_event(
                "network",
                "network.lobby.send_skipped",
                level="warning",
                message="Lobby message could not be sent because the lobby websocket is missing.",
                context={"mode": self._mode, "message_type": _message_type(message)},
            )
            return False

        try:
            await asyncio.wait_for(
                websocket.send(encode_message(message)),
                timeout=float(config.CLIENT_SEND_TIMEOUT_SECONDS),
            )
            return True
        except Exception as exc:
            log_exception(
                "network",
                "network.lobby.send_failed",
                exc,
                level="warning",
                message="Lobby message send failed.",
                context={"mode": self._mode, "message_type": _message_type(message)},
            )
            return False


    def drain_statuses(self) -> list[dict[str, Any]]:
        statuses: list[dict[str, Any]] = []
        while True:
            try:
                statuses.append(self.status_queue.get_nowait())
            except queue.Empty:
                break
        return statuses


    def _start_loop(self) -> None:
        self._closed.clear()
        self._thread = threading.Thread(target=self._run_loop_thread, daemon=True)
        self._thread.start()
        deadline = time.time() + 3.0
        while self._loop is None and time.time() < deadline:
            time.sleep(0.01)
        if self._loop is None:
            exc = RuntimeError("Verkon asyncio-loopin käynnistys epäonnistui.")
            log_exception(
                "network",
                "network.manager.loop_start_failed",
                exc,
                message="Network asyncio loop failed to start.",
                context={"mode": self._mode},
            )
            raise exc


    def _run_loop_thread(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._stop_event = asyncio.Event()
        try:
            loop.run_until_complete(self._wait_until_stopped())
        finally:
            pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                try:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
            loop.close()
            self._closed.set()

    async def _wait_until_stopped(self) -> None:
        assert self._stop_event is not None
        await self._stop_event.wait()


    async def _host_main(self, settings: NetworkSettings) -> None:
        try:
            log_event(
                "network",
                "network.host.starting",
                message="Starting hosted room server.",
                context=_settings_log_context(settings, mode="host"),
            )
            ssl_context = self._server_ssl_context(settings)
            self._server = RoomServer(
                room=settings.room,
                password=settings.password,
                host_callsign=settings.callsign,
                status_callback=self._status,
                remote_tone_callback=self._handle_remote_tone,
            )
            await self._server.start(host=settings.host, port=settings.port, ssl_context=ssl_context)
            log_event(
                "network",
                "network.host.started",
                message="Hosted room server started.",
                context=_settings_log_context(settings, mode="host"),
            )
            self._start_room_background_noise()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log_exception(
                "network",
                "network.host.start_failed",
                exc,
                message="Hosted room server could not be started.",
                context={**_settings_log_context(settings, mode="host"), **_exception_context(exc)},
            )
            self._status("error", f"Huoneen käynnistys epäonnistui: {exc}")
            self._signal_stop()


    async def _client_main(self, settings: NetworkSettings) -> None:
        ssl_context = self._client_ssl_context(settings)
        reconnect_delay = 1.0

        while self._stop_event is not None and not self._stop_event.is_set():
            self._client_send_queue = None
            self._control_ready_event.clear()

            try:
                log_event(
                    "network",
                    "network.client.connecting",
                    message="Connecting room WebSocket.",
                    context={**_settings_log_context(settings, mode=self._mode), "reconnect_delay_seconds": reconnect_delay},
                )
                async with connect(
                    settings.server_uri,
                    ssl=ssl_context,
                    max_size=512_000,
                    ping_interval=20,
                    ping_timeout=60,
                    open_timeout=15,
                    close_timeout=5,
                ) as websocket:
                    self._client_websocket = websocket
                    welcome = await self._client_authenticate(websocket, settings)
                    self.jitter_buffer.clear()
                    reconnect_delay = 1.0

                    self._client_send_queue = asyncio.Queue(
                        maxsize=int(config.CLIENT_SEND_QUEUE_MAX_MESSAGES)
                    )
                    self._control_ready_event.set()
                    log_event(
                        "network",
                        "network.control_channel.ready",
                        message="Control channel is ready for room connection.",
                        context=_settings_log_context(settings, mode=self._mode),
                    )

                    room_name = str(welcome.get("room_name") or settings.room)
                    room_id = str(welcome.get("room_id") or "")

                    room_payload = {
                        "type": "room_connected",
                        "room_key": str(welcome.get("room_key") or welcome.get("room") or settings.room),
                        "room_name": room_name,
                        "room_id": room_id,
                        "room_access": str(welcome.get("room_access") or ""),
                    }
                    log_event(
                        "network",
                        "network.room.join_success",
                        message="Room connection established.",
                        context={**_settings_log_context(settings, mode=self._mode), **room_payload},
                    )
                    self._queue_payload(
                        "success",
                        f"Connected to room {room_name}.",
                        room_payload,
                    )
                    self._start_room_background_noise()

                    sender = asyncio.create_task(self._client_sender_loop(websocket))
                    receiver = asyncio.create_task(self._client_receiver_loop(websocket))
                    keepalive = asyncio.create_task(self._client_keepalive_loop())

                    done, pending = await asyncio.wait(
                        {sender, receiver, keepalive},
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    for task in pending:
                        task.cancel()

                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)

                    results = await asyncio.gather(*done, return_exceptions=True)

                    for result in results:
                        if isinstance(result, asyncio.CancelledError):
                            raise result
                        if isinstance(result, Exception):
                            raise result

                    if self._stop_event is not None and self._stop_event.is_set():
                        break

                    raise ConnectionError("Connection closed.")

            except asyncio.CancelledError:
                raise

            except ProtocolError as exc:
                log_exception(
                    "network",
                    "network.room.join_failed",
                    exc,
                    message="Room connection failed because of a protocol error.",
                    context={**_settings_log_context(settings, mode=self._mode), **_exception_context(exc)},
                )
                self._status("error", f"Yhteyttä ei voitu muodostaa: {exc}")
                self._signal_stop()
                return

            except Exception as exc:
                self._client_websocket = None
                self._client_send_queue = None
                self._control_ready_event.clear()
                log_exception(
                    "network",
                    "network.client.connection_failed",
                    exc,
                    level="warning",
                    message="Room WebSocket connection failed or disconnected.",
                    context={
                        **_settings_log_context(settings, mode=self._mode),
                        **_exception_context(exc),
                        "reconnect_delay_seconds": reconnect_delay,
                    },
                )

                if self._stop_event is not None and self._stop_event.is_set():
                    break

                error_text = self._format_connection_error(exc)
                log_event(
                    "network",
                    "network.client.reconnecting",
                    level="warning",
                    message="Room WebSocket will reconnect after delay.",
                    context={
                        **_settings_log_context(settings, mode=self._mode),
                        **_exception_context(exc),
                        "reconnect_delay_seconds": reconnect_delay,
                    },
                )
                self._status(
                    "warning",
                    (
                        f"Yhteys katkesi: {error_text} "
                        f"Yhdistetään uudelleen {reconnect_delay:.0f} s kuluttua."
                    ),
                )

                if self._stop_event is None:
                    break

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=reconnect_delay)
                    break
                except asyncio.TimeoutError:
                    pass

                reconnect_delay = min(reconnect_delay * 2.0, 30.0)

        self._client_websocket = None
        self._client_send_queue = None
        self._control_ready_event.clear()
        log_event(
            "network",
            "network.client.disconnected",
            message="Room WebSocket connection stopped.",
            context=_settings_log_context(settings, mode=self._mode),
        )

    def _operator_identity_for_settings(self, settings: NetworkSettings) -> OperatorIdentity | None:
        identity = getattr(settings, "operator_identity", None)
        if isinstance(identity, OperatorIdentity):
            return identity

        try:
            return load_or_create_operator_identity()
        except OperatorIdentityError as exc:
            log_exception(
                "network",
                "network.operator_identity.load_failed",
                exc,
                level="warning",
                message="Operator identity could not be loaded; connecting without verified operator identity.",
                context={"room": getattr(settings, "room", "")},
            )
            self._status("warning", f"Operator Identity ei ole käytettävissä: {exc}")
            return None

    async def _client_authenticate(self, websocket: Any, settings: NetworkSettings) -> dict[str, Any]:
        log_event(
            "network",
            "network.client.auth_started",
            message="Room authentication handshake started.",
            context=_settings_log_context(settings, mode=self._mode),
        )
        operator_identity = self._operator_identity_for_settings(settings)
        operator_id = operator_identity.operator_id if operator_identity is not None else ""
        operator_public_key = operator_identity.operator_public_key if operator_identity is not None else ""

        await websocket.send(
            encode_message(
                make_client_hello(
                    room=settings.room,
                    callsign=settings.callsign,
                    client_id=self.client_id,
                    installation_id=settings.installation_id,
                    client_version=getattr(config, "APP_VERSION", ""),
                    client_mode=getattr(settings, "client_mode", "operator"),
                    operator_id=operator_id,
                    operator_public_key=operator_public_key,
                )
            )
        )

        challenge = decode_message(
            await asyncio.wait_for(websocket.recv(), timeout=10.0)
        )
        if challenge.get("type") != "server_challenge":
            if challenge.get("type") == "status":
                raise ProtocolError(str(challenge.get("text") or "Palvelin ei hyväksynyt yhteyttä."))
            raise ProtocolError("Palvelin ei lähettänyt server_challenge-viestiä.")
        
        nonce = str(challenge.get("nonce") or "")
        auth_required = bool(challenge.get("auth_required", True))
        include_create_verifier = bool(
            auth_required
            and challenge.get("can_create_private_room")
            and not challenge.get("room_exists", True)
        )
        operator_auth = None
        if operator_identity is not None:
            try:
                operator_auth = sign_operator_challenge(
                    operator_identity,
                    server_id=str(challenge.get("server_id") or ""),
                    server_nonce=nonce,
                    room=str(challenge.get("room") or settings.room),
                    client_id=self.client_id,
                )
            except OperatorIdentityError as exc:
                log_exception(
                    "network",
                    "network.operator_identity.sign_failed",
                    exc,
                    level="warning",
                    message="Operator identity could not sign the server challenge; connecting without verified operator identity.",
                    context={"room": settings.room},
                )
                self._status("warning", f"Operator Identity -todennus ohitettiin: {exc}")

        await websocket.send(
            encode_message(
                make_auth(
                    password=settings.password,
                    room=settings.room,
                    client_id=self.client_id,
                    nonce=nonce,
                    auth_required=auth_required,
                    include_create_verifier=include_create_verifier,
                    operator_auth=operator_auth,
                )
            )
        )

        welcome = decode_message(
            await asyncio.wait_for(websocket.recv(), timeout=10.0)
        )
        if welcome.get("type") != "welcome":
            if welcome.get("type") == "status":
                raise ProtocolError(str(welcome.get("text") or "Palvelin ei hyväksynyt yhteyttä."))
            raise ProtocolError("Palvelin ei hyväksynyt yhteyttä.")
        
        self.last_joined_room_key = str(welcome.get("room_key") or welcome.get("room") or settings.room)
        self.last_joined_room_name = str(welcome.get("room_name") or settings.room)
        self.last_joined_room_id = str(welcome.get("room_id") or "")
        self.last_joined_room_access = str(welcome.get("room_access") or "")
        self.last_operator_id = str(welcome.get("operator_id") or "")
        self.last_operator_verified = bool(welcome.get("operator_verified"))

        log_event(
            "network",
            "network.client.auth_success",
            message="Room authentication handshake completed.",
            context={
                **_settings_log_context(settings, mode=self._mode),
                "room_key": self.last_joined_room_key,
                "room_name": self.last_joined_room_name,
                "room_id": self.last_joined_room_id,
                "room_access": self.last_joined_room_access,
                "operator_id": self.last_operator_id,
                "operator_verified": self.last_operator_verified,
            },
        )
        return welcome

    async def _client_sender_loop(self, websocket: Any) -> None:
        assert self._client_send_queue is not None

        while True:
            message = await self._client_send_queue.get()

            await asyncio.wait_for(
                websocket.send(encode_message(message)),
                timeout=float(config.CLIENT_SEND_TIMEOUT_SECONDS),
            )

    async def _client_receiver_loop(self, websocket: Any) -> None:
        async for raw in websocket:
            message = decode_message(raw)
            message_type = str(message.get("type") or "")

            if message_type == "key":
                self._handle_remote_key(message)
                continue

            if message_type == "tone":
                self._handle_remote_tone(message)
                continue

            if message_type == "peer_joined":
                log_event(
                    "network",
                    "network.peer.joined",
                    message="Remote peer joined the room.",
                    context={
                        "callsign": message.get("callsign") or "",
                        "client_id": message.get("client_id") or "",
                        "room_key": self.last_joined_room_key,
                        "room_id": self.last_joined_room_id,
                    },
                )
                self._status("info", f"{message.get('callsign', 'Käyttäjä')} liittyi.")
                continue

            if message_type == "peer_left":
                log_event(
                    "network",
                    "network.peer.left",
                    message="Remote peer left the room.",
                    context={
                        "callsign": message.get("callsign") or "",
                        "client_id": message.get("client_id") or "",
                        "room_key": self.last_joined_room_key,
                        "room_id": self.last_joined_room_id,
                    },
                )
                self._status("info", f"{message.get('callsign', 'Käyttäjä')} poistui.")
                continue

            if message_type == "server_info":
                message["client_received_monotonic"] = time.monotonic()
                message["client_received_time"] = time.time()
                self.last_server_info = message
                log_event(
                    "network",
                    "network.server_info.response_success",
                    message="Server info response received.",
                    context=_server_info_log_context(message),
                )
                self._queue_payload("server_info", "", message)
                continue

            if message_type == "server_pong":
                now_ms = int(time.time() * 1000)

                try:
                    client_sent_ms = int(message.get("client_sent_ms") or 0)
                except Exception:
                    client_sent_ms = 0

                if client_sent_ms > 0:
                    message["round_trip_ms"] = max(0, now_ms - client_sent_ms)

                message["client_received_monotonic"] = time.monotonic()
                message["client_received_time"] = time.time()
                self.last_server_pong = message

                ping_id = str(message.get("ping_id") or "")
                is_keepalive = ping_id.startswith("keepalive-")

                if is_keepalive:
                    self._queue_payload("server_pong", "", message)
                else:
                    rtt = message.get("round_trip_ms")
                    log_event(
                        "network",
                        "network.server_ping.response_success",
                        message="Server ping response received.",
                        context=_server_pong_log_context(message),
                    )
                    text = f"Server ping: {rtt} ms." if rtt is not None else "Server ping received."
                    self._queue_payload("server_pong", text, message)

                continue

            if message_type == "status":
                self._handle_status_message(message, source="room")
                continue

            log_event(
                "network",
                "network.client.unhandled_message",
                level="debug",
                message="Unhandled room message received.",
                context={"message_type": message_type or "unknown"},
            )

    async def _client_keepalive_loop(self) -> None:
        while True:
            await asyncio.sleep(25.0)

            send_queue = self._client_send_queue
            if send_queue is None:
                return

            try:
                send_queue.put_nowait(
                    make_client_ping(
                        sender_id=self.client_id,
                        ping_id=new_id("keepalive"),
                    )
                )
            except asyncio.QueueFull:
                log_event(
                    "network",
                    "network.keepalive.queue_full",
                    level="warning",
                    message="Keepalive ping could not be queued because the send queue is full.",
                    context={"mode": self._mode},
                )

    async def _send_tone_message(self, message: Dict[str, Any]) -> None:
        try:
            if self._mode == "host" and self._server is not None:
                await self._server.broadcast_local_tone(message)
                return

            if self._mode == "client":
                sent = await self._enqueue_client_message(message)
                if not sent:
                    log_event(
                        "network",
                        "network.telemetry.send_queue_failed",
                        level="warning",
                        message="Local telemetry message could not be queued for sending.",
                        context={"mode": self._mode, "message_type": _message_type(message)},
                    )
                return

            log_event(
                "network",
                "network.telemetry.send_skipped",
                level="debug",
                message="Local telemetry message was not sent because networking is not in a sending mode.",
                context={"mode": self._mode, "message_type": _message_type(message)},
            )
        except Exception as exc:
            log_exception(
                "network",
                "network.telemetry.send_failed",
                exc,
                level="warning",
                message="Local telemetry message send failed.",
                context={"mode": self._mode, "message_type": _message_type(message)},
            )

    def _handle_remote_tone(self, message: Dict[str, Any]) -> None:
        if str(message.get("sender_id") or "") == self.client_id:
            return
        self.jitter_buffer.push_message(message)

    def _handle_remote_key(self, message: Dict[str, Any]) -> None:
        if str(message.get("sender_id") or "") == self.client_id:
            return
        self.jitter_buffer.push_message(message)

    def _set_mode(self, mode: str, *, event: str) -> None:
        previous = self._mode
        self._mode = str(mode)
        if previous != self._mode:
            log_event(
                "network",
                event,
                message="Network manager mode changed.",
                context={"previous_mode": previous, "mode": self._mode},
            )


    def _signal_stop(self) -> None:
        if self._loop is None or self._stop_event is None:
            return
        self._loop.call_soon_threadsafe(self._stop_event.set)

    def _server_ssl_context(self, settings: NetworkSettings) -> Optional[ssl.SSLContext]:
        if not settings.tls_certfile or not settings.tls_keyfile:
            return None
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(settings.tls_certfile, settings.tls_keyfile)
        return context

    def _client_ssl_context(self, settings: NetworkSettings) -> Optional[ssl.SSLContext]:
        if not settings.server_uri.lower().startswith("wss://"):
            return None
        context = ssl.create_default_context(cafile=settings.tls_cafile or None)
        return context

    def _tone_player_status(self, level: str, text: str) -> None:
        self._status(level, text)

    def _handle_status_message(self, message: Dict[str, Any], *, source: str) -> None:
        source_key = str(source or "room").strip().lower()
        if source_key not in {"lobby", "room"}:
            source_key = "room"

        status_level = str(message.get("level") or "info").strip().lower()
        if status_level not in {"debug", "info", "warning", "error", "critical"}:
            status_level = "info"

        status_text = str(message.get("text") or "")
        status_code = str(message.get("code") or "")

        log_event(
            "network",
            f"network.{source_key}.status_received",
            level="debug" if status_level == "debug" else status_level,
            message=f"{source_key.capitalize()} status message received.",
            context={
                "status_level": status_level,
                "status_code": status_code,
                "status_text": status_text,
                "mode": self._mode,
                "control_channel_ready": self.control_channel_ready,
            },
        )

        if status_level != "debug":
            self._status(status_level, status_text)

    def _format_connection_error(self, exc: Exception) -> str:
        raw_text = str(exc) or exc.__class__.__name__
        lower_text = raw_text.lower()

        if "no close frame received or sent" in lower_text:
            return (
                "Yhteys katkesi odottamatta. "
                "Todennäköinen syy on valmiustila, heikko Wi-Fi tai hetkellinen verkkokatkos."
            )

        if "timed out during opening handshake" in lower_text:
            return (
                "Yhteyden avaaminen palvelimeen aikakatkaistiin. "
                "Tarkista verkkoyhteys ja palvelimen saavutettavuus."
            )

        if "ping timeout" in lower_text or "keepalive" in lower_text:
            return (
                "Yhteys ei vastannut ajoissa. "
                "Todennäköinen syy on hidas tai katkeileva verkkoyhteys."
            )

        if "connection closed" in lower_text:
            return "Yhteys sulkeutui odottamatta."

        return raw_text

    def _status(self, level: str, text: str) -> None:
        level_key = str(level or "info").strip().lower()
        if level_key in {"warning", "error"}:
            log_event(
                "network",
                f"network.status.{level_key}",
                level=level_key,
                message=str(text),
                context={
                    "mode": self._mode,
                    "control_channel_ready": self.control_channel_ready,
                },
            )
        self.status_queue.put({"level": str(level), "text": str(text), "time": time.time()})

    def _queue_payload(self, level: str, text: str, payload: Dict[str, Any]) -> None:
        self.status_queue.put(
            {
                "level": str(level),
                "text": str(text),
                "payload": payload,
                "time": time.time(),
            }
        )

def _settings_log_context(settings: NetworkSettings, *, mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "server_uri": settings.server_uri,
        "room": settings.room,
        "callsign": settings.callsign,
        "host": settings.host,
        "port": settings.port,
        "transmit_enabled": settings.transmit_enabled,
        "playback_enabled": settings.playback.enabled,
        "jitter_buffer_ms": settings.playback.jitter_buffer_ms,
        "radio_noise_enabled": settings.playback.radio_noise_enabled,
        "radio_noise_volume": settings.playback.radio_noise_volume,
        "radio_noise_profile": settings.playback.radio_noise_profile,
        "radio_noise_tone": settings.playback.radio_noise_tone,
        "radio_noise_tx_ducking_enabled": settings.playback.radio_noise_tx_ducking_enabled,
        "radio_noise_tx_ducking_depth_percent": settings.playback.radio_noise_tx_ducking_depth_percent,
        "radio_noise_tx_ducking_attack_ms": settings.playback.radio_noise_tx_ducking_attack_ms,
        "radio_noise_tx_ducking_hold_ms": settings.playback.radio_noise_tx_ducking_hold_ms,
        "radio_noise_tx_ducking_release_ms": settings.playback.radio_noise_tx_ducking_release_ms,
        "radio_noise_rx_ducking_enabled": settings.playback.radio_noise_rx_ducking_enabled,
        "radio_noise_rx_ducking_depth_percent": settings.playback.radio_noise_rx_ducking_depth_percent,
        "radio_noise_rx_ducking_attack_ms": settings.playback.radio_noise_rx_ducking_attack_ms,
        "radio_noise_rx_ducking_hold_ms": settings.playback.radio_noise_rx_ducking_hold_ms,
        "radio_noise_rx_ducking_release_ms": settings.playback.radio_noise_rx_ducking_release_ms,
    }


def _exception_context(exc: BaseException) -> dict[str, Any]:
    text = str(exc)
    lowered = text.lower()
    return {
        "error_type": exc.__class__.__name__,
        "error_message": text,
        "is_dns_error": "getaddrinfo failed" in lowered or "errno 11002" in lowered,
        "is_timeout": "timed out" in lowered or "timeout" in lowered,
        "is_websocket_error": "websocket" in exc.__class__.__name__.lower() or "handshake" in lowered,
    }


def _server_info_log_context(info: dict[str, Any]) -> dict[str, Any]:
    rooms = info.get("rooms")
    room_clients: dict[str, int] = {}

    if isinstance(rooms, list):
        for room in rooms:
            if not isinstance(room, dict):
                continue
            room_id = str(room.get("id") or room.get("room") or room.get("name") or "")
            if not room_id:
                continue
            room_clients[room_id] = _safe_int(room.get("client_count"), 0)

    return {
        "server_name": info.get("server_name") or info.get("name") or "",
        "rooms_total": _safe_int(info.get("rooms_total") or info.get("room_count"), 0),
        "clients_total": _safe_int(info.get("clients_total") or info.get("client_count"), 0),
        "room_clients": room_clients,
        "uptime_seconds": _safe_int(info.get("uptime_seconds"), 0),
    }


def _server_pong_log_context(pong: dict[str, Any]) -> dict[str, Any]:
    return {
        "round_trip_ms": _safe_int(pong.get("round_trip_ms"), 0),
        "server_time_unix_ms": _safe_int(pong.get("server_time_unix_ms"), 0),
        "ping_id": pong.get("ping_id") or "",
    }


def _message_type(message: Dict[str, Any]) -> str:
    return str(message.get("type") or "")


def _safe_int(value: Any, default: int) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        return max(0, int(value))
    except Exception:
        return default
