# ============================================================
# morsewurst/network/manager.py
# ============================================================

from __future__ import annotations

import asyncio
import queue
import ssl
import threading
import time
from typing import Any, Dict, Optional

import morsewurst.config as config

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
    """Thread-safe facade for MorseWurst WebSocket networking.

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

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_running(self) -> bool:
        return self._mode in {"host", "client"}

    def _create_tone_player(self, playback_settings: PlaybackSettings) -> TonePlayer:
        return TonePlayer(
            frequency_hz=playback_settings.frequency_hz,
            volume=playback_settings.volume,
            waveform=playback_settings.waveform,
            sample_rate=playback_settings.sample_rate,
            blocksize=playback_settings.blocksize,
            latency=playback_settings.latency,
            output_device=playback_settings.output_device,
            status_callback=self._tone_player_status,
        )

    def start_host(self, settings: NetworkSettings) -> None:
        self.stop()
        self._settings = settings
        self.playback_settings = settings.playback
        self.tone_player.stop()
        self.tone_player = self._create_tone_player(settings.playback)
        self.jitter_buffer = JitterBuffer(
            self.tone_player,
            playback_settings=settings.playback,
            status_callback=self._status,
        )
        self._mode = "host"
        self._start_loop()
        assert self._loop is not None
        asyncio.run_coroutine_threadsafe(self._host_main(settings), self._loop)

    def connect_to_room(self, settings: NetworkSettings) -> None:
        self.stop()
        self._settings = settings
        self.playback_settings = settings.playback
        self.tone_player.stop()
        self.tone_player = self._create_tone_player(settings.playback)
        self.jitter_buffer = JitterBuffer(
            self.tone_player,
            playback_settings=settings.playback,
            status_callback=self._status,
        )
        self._mode = "client"
        self._start_loop()
        assert self._loop is not None
        asyncio.run_coroutine_threadsafe(self._client_main(settings), self._loop)

    def connect_lobby_presence(self, settings: NetworkSettings) -> None:
        if self.is_running:
            return

        self.stop()
        self._settings = settings
        self._mode = "client"
        self._start_loop()

        assert self._loop is not None
        asyncio.run_coroutine_threadsafe(self._lobby_presence_main(settings), self._loop)

    async def _lobby_presence_main(self, settings: NetworkSettings) -> None:
        ssl_context = self._client_ssl_context(settings)
        reconnect_delay = 1.0

        while self._stop_event is not None and not self._stop_event.is_set():
            try:
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

                    reconnect_delay = 1.0

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

                if self._stop_event is not None and self._stop_event.is_set():
                    break

                error_text = self._format_connection_error(exc)
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

    async def _lobby_receiver_loop(self, websocket: Any) -> None:
        async for raw in websocket:
            message = decode_message(raw)
            message_type = str(message.get("type") or "")

            if message_type == "server_info":
                message["client_received_monotonic"] = time.monotonic()
                message["client_received_time"] = time.time()
                self.last_server_info = message
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
                    text = f"Server ping: {rtt} ms." if rtt is not None else "Server ping received."
                    self._queue_payload("server_pong", text, message)

                continue

            if message_type == "status" and message.get("level") != "debug":
                self._status(str(message.get("level") or "info"), str(message.get("text") or ""))
                continue

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
        if self._loop is None:
            self._mode = "stopped"
            self.jitter_buffer.clear()
            self.tone_player.stop()
            self._lobby_websocket = None
            return

        loop = self._loop
        stop_event = self._stop_event

        if stop_event is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(stop_event.set)
            except RuntimeError:
                pass

        futures = []

        if not loop.is_closed():
            if self._server is not None:
                try:
                    futures.append(asyncio.run_coroutine_threadsafe(self._server.stop(), loop))
                except Exception:
                    pass

            if self._client_websocket is not None:
                try:
                    futures.append(asyncio.run_coroutine_threadsafe(self._client_websocket.close(), loop))
                except Exception:
                    pass

            if self._lobby_websocket is not None:
                try:
                    futures.append(asyncio.run_coroutine_threadsafe(self._lobby_websocket.close(), loop))
                except Exception:
                    pass

            for future in futures:
                try:
                    future.result(timeout=0.8)
                except Exception:
                    pass

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
        self._mode = "stopped"
        self.jitter_buffer.clear()
        self.tone_player.stop()
        self._status("info", "Verkkoyhteys pysäytetty.")

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
            self._status("warning", f"Tone-viestiä ei lähetetty: {exc}")
            return

        asyncio.run_coroutine_threadsafe(self._send_tone_message(message), self._loop)

    def update_playback_settings(self, settings: PlaybackSettings) -> None:
        self.playback_settings = settings
        self.tone_player.stop()
        self.tone_player = self._create_tone_player(settings)
        self.jitter_buffer = JitterBuffer(
            self.tone_player,
            playback_settings=settings,
            status_callback=self._status,
        )

    def reset_receive_playback(self) -> None:
        self.jitter_buffer.clear()

        try:
            self.tone_player.reset_clock()
        except AttributeError:
            self.tone_player.clear()

        self._status("warning", "Vastaanoton äänentoisto synkronoitiin uudelleen.")

    def set_transmit_enabled(self, enabled: bool) -> None:
        self._settings.transmit_enabled = bool(enabled)

    def request_server_info(self) -> None:
        if not self.is_running:
            return
        if self._loop is None:
            return

        message = {
            "v": 4,
            "app": "morsewurst",
            "type": "server_info_request",
            "sender_id": self.client_id,
        }

        if self._client_send_queue is not None:
            asyncio.run_coroutine_threadsafe(self._send_client_message(message), self._loop)
            return

        if self._lobby_websocket is not None:
            asyncio.run_coroutine_threadsafe(self._send_lobby_message(message), self._loop)
            return

        self._status("warning", "Server info -pyyntöä ei voitu lähettää, koska yhteys ei ole valmis.")


    def request_server_ping(self) -> None:
        if not self.is_running:
            return
        if self._loop is None:
            return

        message = make_client_ping(sender_id=self.client_id)

        if self._client_send_queue is not None:
            asyncio.run_coroutine_threadsafe(self._send_client_message(message), self._loop)
            return

        if self._lobby_websocket is not None:
            asyncio.run_coroutine_threadsafe(self._send_lobby_message(message), self._loop)
            return

        self._status("warning", "Server pingiä ei voitu lähettää, koska yhteys ei ole valmis.")


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
            self._status("warning", "Verkkoviestiä ei voitu lähettää, koska yhteys ei ole valmis tai lähetysjono on täynnä.")


    async def _send_lobby_message(self, message: Dict[str, Any]) -> bool:
        websocket = self._lobby_websocket
        if websocket is None:
            return False

        await asyncio.wait_for(
            websocket.send(encode_message(message)),
            timeout=float(config.CLIENT_SEND_TIMEOUT_SECONDS),
        )
        return True


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
            raise RuntimeError("Verkon asyncio-loopin käynnistys epäonnistui.")


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
            ssl_context = self._server_ssl_context(settings)
            self._server = RoomServer(
                room=settings.room,
                password=settings.password,
                host_callsign=settings.callsign,
                status_callback=self._status,
                remote_tone_callback=self._handle_remote_tone,
            )
            await self._server.start(host=settings.host, port=settings.port, ssl_context=ssl_context)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._status("error", f"Huoneen käynnistys epäonnistui: {exc}")
            self._signal_stop()


    async def _client_main(self, settings: NetworkSettings) -> None:
        ssl_context = self._client_ssl_context(settings)
        reconnect_delay = 1.0

        while self._stop_event is not None and not self._stop_event.is_set():
            self._client_send_queue = None

            try:
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

                    room_name = str(welcome.get("room_name") or settings.room)
                    room_id = str(welcome.get("room_id") or "")

                    self._queue_payload(
                        "success",
                        f"Connected to room {room_name}.",
                        {
                            "type": "room_connected",
                            "room_key": str(welcome.get("room_key") or welcome.get("room") or settings.room),
                            "room_name": room_name,
                            "room_id": room_id,
                            "room_access": str(welcome.get("room_access") or ""),
                        },
                    )

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
                self._status("error", f"Yhteyttä ei voitu muodostaa: {exc}")
                self._signal_stop()
                return

            except Exception as exc:
                self._client_websocket = None
                self._client_send_queue = None

                if self._stop_event is not None and self._stop_event.is_set():
                    break

                error_text = self._format_connection_error(exc)
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

    async def _client_authenticate(self, websocket: Any, settings: NetworkSettings) -> dict[str, Any]:
        await websocket.send(
            encode_message(
                make_client_hello(
                    room=settings.room,
                    callsign=settings.callsign,
                    client_id=self.client_id,
                    installation_id=settings.installation_id,
                    client_version=getattr(config, "APP_VERSION", ""),
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
        await websocket.send(
            encode_message(
                make_auth(
                    password=settings.password,
                    room=settings.room,
                    client_id=self.client_id,
                    nonce=nonce,
                    auth_required=auth_required,
                    include_create_verifier=include_create_verifier,
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

            if message_type == "tone":
                self._handle_remote_tone(message)
                continue

            if message_type == "peer_joined":
                self._status("info", f"{message.get('callsign', 'Käyttäjä')} liittyi.")
                continue

            if message_type == "peer_left":
                self._status("info", f"{message.get('callsign', 'Käyttäjä')} poistui.")
                continue

            if message_type == "server_info":
                message["client_received_monotonic"] = time.monotonic()
                message["client_received_time"] = time.time()
                self.last_server_info = message
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
                    text = f"Server ping: {rtt} ms." if rtt is not None else "Server ping received."
                    self._queue_payload("server_pong", text, message)

                continue

            if message_type == "status" and message.get("level") != "debug":
                self._status(str(message.get("level") or "info"), str(message.get("text") or ""))
                continue

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
                pass

    async def _send_tone_message(self, message: Dict[str, Any]) -> None:
        if self._mode == "host" and self._server is not None:
            await self._server.broadcast_local_tone(message)
            return

        if self._mode == "client":
            await self._enqueue_client_message(message)

    def _handle_remote_tone(self, message: Dict[str, Any]) -> None:
        if str(message.get("sender_id") or "") == self.client_id:
            return
        self.jitter_buffer.push_message(message)

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