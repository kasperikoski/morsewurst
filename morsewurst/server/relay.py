# ============================================================
# morsewurst/server/relay.py
# ============================================================

from __future__ import annotations

import asyncio
import contextlib
import logging
import ssl
import time
from typing import Any
from dataclasses import dataclass, field

from morsewurst.network.protocol import (
    ProtocolError,
    ROOM_ACCESS_PRIVATE,
    ROOM_ACCESS_PUBLIC,
    decode_message,
    encode_message,
    is_valid_password_verifier,
    make_peer_event,
    make_public_rooms_response,
    make_server_challenge,
    make_server_info,
    make_server_pong,
    make_status,
    make_welcome,
    new_id,
    new_nonce,
    normalize_callsign,
    normalize_room_id,
    sanitize_installation_id,
    sanitize_room_display_name,
    verify_auth,
)
from morsewurst.server.user_registry import UserRegistry, installation_id_hash
from morsewurst.server.models import RelayServerConfig
from morsewurst.server.rooms import ClientSession, RoomError, RoomRegistry, RoomState

try:
    from websockets.asyncio.server import serve
except ImportError:  # pragma: no cover
    from websockets import serve  # type: ignore[assignment]

LOGGER = logging.getLogger("morsewurst.relay")


@dataclass(slots=True)
class LobbySession:
    client_id: str
    callsign: str
    websocket: Any
    installation_id_hash: str = ""
    client_version: str = ""
    protocol_version: int = 0
    connected_at: float = field(default_factory=time.time)
    last_seen_at: float = field(default_factory=time.time)


SERVER_OUTBOUND_QUEUE_MAX_MESSAGES = 250
SERVER_SEND_TIMEOUT_SECONDS = 2.0


@dataclass(slots=True)
class ClientOutbound:
    client_id: str
    callsign: str
    websocket: Any
    queue: asyncio.Queue[str]
    task: asyncio.Task[None]
    dropped_messages: int = 0
    created_at: float = field(default_factory=time.time)


class RelayServer:
    """Headless multi-room WebSocket relay for Morsewurst V1 key and tone telemetry."""

    def __init__(self, config: RelayServerConfig) -> None:
        self.config = config
        self.server_id = new_id("server")
        self.started_at = time.time()
        self.registry = RoomRegistry(config)
        self.user_registry = UserRegistry(
            config.user_registry.storage_path,
            enabled=config.user_registry.enabled,
        )
        self._server: Any = None
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None
        self._server_info_task: asyncio.Task[None] | None = None
        self._lobby_clients: dict[Any, LobbySession] = {}
        self._outbound_clients: dict[Any, ClientOutbound] = {}

    async def start(self, *, ssl_context: ssl.SSLContext | None = None) -> None:
        host = self.config.server.host
        port = self.config.server.port
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        if self.config.server_info.enabled:
            self._server_info_task = asyncio.create_task(self._server_info_loop())

        self._server = await serve(
            self._handler_compatible,
            host,
            int(port),
            ssl=ssl_context,
            max_size=512_000,
            ping_interval=20,
            ping_timeout=60,
            close_timeout=5,
        )
        scheme = "wss" if ssl_context is not None else "ws"
        LOGGER.info("Starting Morsewurst relay on %s://%s:%s", scheme, host, port)
        LOGGER.info("Configured rooms: %s", ", ".join(sorted(self.registry.rooms)) or "none")
        await self._server.wait_closed()

    async def stop(self) -> None:
        if self._server_info_task is not None:
            self._server_info_task.cancel()
            with contextlib.suppress(BaseException):
                await self._server_info_task
            self._server_info_task = None

        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            with contextlib.suppress(BaseException):
                await self._cleanup_task
            self._cleanup_task = None

        for session in list(self._lobby_clients.values()):
            try:
                await session.websocket.close()
            except Exception:
                pass
        self._lobby_clients.clear()

        for websocket in list(self._outbound_clients):
            await self._stop_outbound_sender(websocket)

        for room in list(self.registry.rooms.values()):
            for session in list(room.clients.values()):
                try:
                    await session.websocket.close()
                except Exception:
                    pass
            room.clients.clear()

        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handler_compatible(self, websocket: Any, *args: Any) -> None:
        await self._handle_client(websocket)

    async def _handle_client(self, websocket: Any) -> None:
        session: ClientSession | None = None
        try:
            raw_first = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            first_message = decode_message(raw_first)

            first_message_type = str(first_message.get("type") or "")

            if first_message_type == "public_rooms_request":
                await self._send_public_rooms(websocket)
                return

            if first_message_type == "server_info_request":
                if self.config.server_info.allow_requests:
                    await self._send(websocket, self._make_server_info_snapshot_message())
                else:
                    await self._send(websocket, make_status("Server info requests are disabled.", level="warning"))
                return

            if first_message_type == "client_ping":
                await self._send(
                    websocket,
                    make_server_pong(
                        server_id=self.server_id,
                        ping_id=str(first_message.get("ping_id") or ""),
                        client_sent_ms=int(first_message.get("client_sent_ms") or 0),
                    ),
                )
                return
            
            if first_message_type == "lobby_hello":
                await self._handle_lobby_client(websocket, first_message)
                return

            session, room = await self._authenticate(websocket, first_message)
            await self._register_client(room, session)

            async for raw in websocket:
                try:
                    message = decode_message(raw)
                except ProtocolError as exc:
                    await self._send(websocket, make_status(f"Virheellinen viesti: {exc}", level="warning"))
                    continue

                message_type = str(message.get("type") or "")

                session.last_seen_at = time.time()
                session.message_count += 1

                if message_type in {"key", "tone"}:
                    session.tone_count += 1
                    session.last_tone_at = time.time()
                    message["via_server_id"] = self.server_id
                    await self._broadcast(room, message, exclude=websocket)
                    continue

                if message_type == "heartbeat":
                    await self._send(websocket, make_status("heartbeat_ok", level="debug"))
                    continue

                if message_type == "server_info_request":
                    if self.config.server_info.allow_requests:
                        await self._send(websocket, self._make_server_info_message(room))
                    continue

                if message_type == "client_ping":
                    await self._send(
                        websocket,
                        make_server_pong(
                            server_id=self.server_id,
                            ping_id=str(message.get("ping_id") or ""),
                            client_sent_ms=int(message.get("client_sent_ms") or 0),
                        ),
                    )
                    continue

                await self._send(websocket, make_status(f"Tuntematon viestityyppi: {message_type}", level="warning"))

        except RoomError as exc:
            LOGGER.warning("Room error: %s %s", exc.code, exc.message)
            try:
                await self._send(websocket, make_status(exc.message, level="error", code=exc.code))
                await websocket.close()
            except Exception:
                pass
        except Exception as exc:
            LOGGER.warning("Client connection ended: %s", exc)
        finally:
            if session is not None:
                await self._unregister_client(session)

    async def _send_public_rooms(self, websocket: Any) -> None:
        async with self._lock:
            rooms = self.registry.list_public_rooms()

        await self._send(
            websocket,
            make_public_rooms_response(
                server_id=self.server_id,
                server_name=self.config.server.server_name,
                rooms=rooms,
            ),
        )

        try:
            await websocket.close(code=1000, reason="public rooms sent")
        except Exception:
            pass


    async def _handle_lobby_client(self, websocket: Any, hello: dict[str, Any]) -> None:
        session = self._make_lobby_session(websocket, hello)

        async with self._lock:
            self._lobby_clients[websocket] = session

        try:
            self.user_registry.record_connect(session)
        except Exception:
            pass

        await self._send(websocket, make_status("Lobby presence registered.", level="debug"))

        if self.config.server_info.enabled:
            await self._send(websocket, self._make_server_info_snapshot_message())

        try:
            async for raw in websocket:
                try:
                    message = decode_message(raw)
                except ProtocolError as exc:
                    await self._send(websocket, make_status(f"Virheellinen viesti: {exc}", level="warning"))
                    continue

                message_type = str(message.get("type") or "")
                session.last_seen_at = time.time()

                if message_type == "client_ping":
                    await self._send(
                        websocket,
                        make_server_pong(
                            server_id=self.server_id,
                            ping_id=str(message.get("ping_id") or ""),
                            client_sent_ms=int(message.get("client_sent_ms") or 0),
                        ),
                    )
                    continue

                if message_type == "server_info_request":
                    if self.config.server_info.allow_requests:
                        await self._send(websocket, self._make_server_info_snapshot_message())
                    continue

                if message_type == "heartbeat":
                    await self._send(websocket, make_status("heartbeat_ok", level="debug"))
                    continue

                await self._send(websocket, make_status(f"Tuntematon viestityyppi: {message_type}", level="warning"))

        finally:
            async with self._lock:
                self._lobby_clients.pop(websocket, None)


    def _make_lobby_session(self, websocket: Any, hello: dict[str, Any]) -> LobbySession:
        callsign = normalize_callsign(hello.get("callsign"))
        installation_id = sanitize_installation_id(hello.get("installation_id"))
        installation_hash = installation_id_hash(installation_id)
        client_version = str(hello.get("client_version") or "")[:40]

        try:
            protocol_version = int(hello.get("v") or 0)
        except Exception:
            protocol_version = 0

        return LobbySession(
            client_id=str(hello.get("client_id") or new_id("lobby"))[:80],
            callsign=callsign,
            websocket=websocket,
            installation_id_hash=installation_hash,
            client_version=client_version,
            protocol_version=protocol_version,
        )

    async def _authenticate(self, websocket: Any, hello: dict[str, Any]) -> tuple[ClientSession, RoomState]:

        if hello.get("type") != "client_hello":
            raise ProtocolError("Ensimmäisen viestin pitää olla client_hello.")

        requested_room_key = normalize_room_id(hello.get("room"))
        requested_room_name = sanitize_room_display_name(
            hello.get("room_name") or hello.get("room") or requested_room_key
        )
        client_id = str(hello.get("client_id") or new_id("client"))[:80]
        callsign = normalize_callsign(hello.get("callsign"))
        installation_id = sanitize_installation_id(hello.get("installation_id"))
        installation_hash = installation_id_hash(installation_id)
        client_version = str(hello.get("client_version") or "")[:40]

        try:
            protocol_version = int(hello.get("v") or 0)
        except Exception:
            protocol_version = 0

        async with self._lock:
            room_key, room, can_create = self.registry.room_for_join(requested_room_key)

        room_access = room.access if room is not None else ROOM_ACCESS_PRIVATE
        auth_required = bool(room.auth_required) if room is not None else True

        nonce = new_nonce()
        await self._send(
            websocket,
            make_server_challenge(
                room=room_key,
                server_id=self.server_id,
                nonce=nonce,
                room_exists=room is not None,
                can_create_private_room=can_create,
                room_access=room_access,
                auth_required=auth_required,
            ),
        )

        raw_auth = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        auth = decode_message(raw_auth)
        if auth.get("type") != "auth":
            raise ProtocolError("Toisen viestin pitää olla auth.")

        auth_client_id = str(auth.get("client_id") or "")
        if auth_client_id != client_id:
            raise ProtocolError("Auth-viestin client_id ei täsmää.")

        proof = str(auth.get("proof") or "")

        async with self._lock:
            current = self.registry.rooms.get(room_key)

            if current is None:
                if not can_create:
                    raise RoomError("ROOM_NOT_FOUND", "Huonetta ei ole olemassa.")

                verifier = str(auth.get("room_password_verifier") or "")
                if not is_valid_password_verifier(verifier):
                    raise RoomError("INVALID_ROOM_PASSWORD", "Huoneen salasana ei kelpaa.")

                current = self.registry.create_private_room(
                    room_key=room_key,
                    password_verifier=verifier,
                    display_name=requested_room_name,
                )
                self.registry.save_persisted_private_rooms()
                LOGGER.info(
                    "Created private room key='%s' room_id='%s' name='%s'.",
                    current.room_key,
                    current.room_id,
                    current.name,
                )

            if current.access == ROOM_ACCESS_PUBLIC:
                pass
            else:
                if current.password_verifier is None:
                    raise RoomError("INVALID_ROOM_CONFIGURATION", "Huoneen salasana-asetus puuttuu.")

                if not verify_auth(
                    room=room_key,
                    client_id=client_id,
                    nonce=nonce,
                    proof=proof,
                    password_verifier=current.password_verifier,
                    allow_legacy_password_proof=False,
                ):
                    raise RoomError("BAD_ROOM_PASSWORD", "Huoneen salasana ei täsmää.")

            session = ClientSession(
                client_id=client_id,
                callsign=callsign,
                websocket=websocket,
                room_key=current.room_key,
                room_id=current.room_id,
                installation_id_hash=installation_hash,
                client_version=client_version,
                protocol_version=protocol_version,
            )
            self.registry.add_client(current, session)

        return session, current

    async def _register_client(self, room: RoomState, session: ClientSession) -> None:
        peers = [
            {"client_id": peer.client_id, "callsign": peer.callsign}
            for peer in room.clients.values()
            if peer.websocket is not session.websocket
        ]

        await self._send(
            session.websocket,
            make_welcome(
                room_key=room.room_key,
                room_name=room.name,
                room_id=room.room_id,
                room_access=room.access,
                server_id=self.server_id,
                client_id=session.client_id,
                peers=peers,
            ),
        )

        self._start_outbound_sender(session)

        await self._broadcast(
            room,
            make_peer_event(event_type="peer_joined", client_id=session.client_id, callsign=session.callsign),
            exclude=session.websocket,
        )

        self.user_registry.record_connect(session)

        LOGGER.info(
            "%s joined %s room key='%s' room_id='%s' name='%s'.",
            session.callsign,
            room.access,
            room.room_key,
            room.room_id,
            room.name,
        )

    async def _unregister_client(self, session: ClientSession) -> None:
        await self._stop_outbound_sender(session.websocket)

        async with self._lock:
            room = self.registry.rooms.get(session.room_key)
            if room is None:
                return

            current_session = room.clients.get(session.websocket)
            if current_session is None:
                return

            self.registry.remove_client(session)

            should_save_private_rooms = (
                room.access == ROOM_ACCESS_PRIVATE
                and not room.persistent
                and room.client_count == 0
            )

            if should_save_private_rooms:
                self.registry.save_persisted_private_rooms()

        self.user_registry.record_disconnect(session)

        await self._broadcast(
            room,
            make_peer_event(event_type="peer_left", client_id=session.client_id, callsign=session.callsign),
            exclude=session.websocket,
        )

        LOGGER.info(
            "%s left room key='%s' room_id='%s'.",
            session.callsign,
            session.room_key,
            session.room_id,
        )

    def _start_outbound_sender(self, session: ClientSession) -> None:
        if session.websocket in self._outbound_clients:
            return

        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=SERVER_OUTBOUND_QUEUE_MAX_MESSAGES)

        outbound = ClientOutbound(
            client_id=session.client_id,
            callsign=session.callsign,
            websocket=session.websocket,
            queue=queue,
            task=asyncio.create_task(
                self._outbound_sender_loop(
                    websocket=session.websocket,
                    client_id=session.client_id,
                    callsign=session.callsign,
                    queue=queue,
                )
            ),
        )

        self._outbound_clients[session.websocket] = outbound

    async def _stop_outbound_sender(self, websocket: Any) -> None:
        outbound = self._outbound_clients.pop(websocket, None)
        if outbound is None:
            return

        task = outbound.task
        current_task = asyncio.current_task()

        if task is current_task:
            return

        task.cancel()
        with contextlib.suppress(BaseException):
            await task


    async def _outbound_sender_loop(
        self,
        *,
        websocket: Any,
        client_id: str,
        callsign: str,
        queue: asyncio.Queue[str],
    ) -> None:
        try:
            while True:
                encoded = await queue.get()

                try:
                    await asyncio.wait_for(
                        websocket.send(encoded),
                        timeout=SERVER_SEND_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    LOGGER.warning(
                        "Dropping slow client %s (%s): send timed out after %.1f s.",
                        callsign,
                        client_id,
                        SERVER_SEND_TIMEOUT_SECONDS,
                    )
                    await self._drop_stale_websockets([websocket])
                    return
                except Exception as exc:
                    LOGGER.warning(
                        "Dropping client %s (%s): send failed: %s",
                        callsign,
                        client_id,
                        exc,
                    )
                    await self._drop_stale_websockets([websocket])
                    return

        except asyncio.CancelledError:
            raise


    async def _queue_outbound_message(self, session: ClientSession, encoded: str) -> bool:
        outbound = self._outbound_clients.get(session.websocket)
        if outbound is None:
            return False

        try:
            outbound.queue.put_nowait(encoded)
            return True
        except asyncio.QueueFull:
            outbound.dropped_messages += 1

            LOGGER.warning(
                "Dropping slow client %s (%s): outbound queue full (%s messages).",
                session.callsign,
                session.client_id,
                SERVER_OUTBOUND_QUEUE_MAX_MESSAGES,
            )

            return False

    async def _broadcast(self, room: RoomState, message: dict[str, Any], *, exclude: Any = None) -> None:
        async with self._lock:
            targets = [
                session
                for session in room.clients.values()
                if session.websocket is not exclude
            ]

        if not targets:
            return

        encoded = encode_message(message)
        stale: list[Any] = []

        for session in targets:
            queued = await self._queue_outbound_message(session, encoded)
            if not queued:
                stale.append(session.websocket)

        if stale:
            await self._drop_stale_websockets(stale)

    async def _drop_stale_websockets(self, websockets: list[Any]) -> None:
        removed: list[tuple[RoomState, ClientSession]] = []
        seen: set[int] = set()
        should_save_private_rooms = False

        async with self._lock:
            for websocket in websockets:
                websocket_key = id(websocket)
                if websocket_key in seen:
                    continue

                seen.add(websocket_key)

                for room in self.registry.rooms.values():
                    session = room.clients.get(websocket)
                    if session is None:
                        continue

                    self.registry.remove_client(session)
                    removed.append((room, session))

                    if (
                        room.access == ROOM_ACCESS_PRIVATE
                        and not room.persistent
                        and room.client_count == 0
                    ):
                        should_save_private_rooms = True

                    break

            if should_save_private_rooms:
                self.registry.save_persisted_private_rooms()

        for room, session in removed:
            await self._stop_outbound_sender(session.websocket)

            self.user_registry.record_disconnect(session)

            LOGGER.warning(
                "Dropped stale client %s from room key='%s' room_id='%s'.",
                session.callsign,
                session.room_key,
                session.room_id,
            )

            try:
                await session.websocket.close()
            except Exception:
                pass

            await self._broadcast(
                room,
                make_peer_event(
                    event_type="peer_left",
                    client_id=session.client_id,
                    callsign=session.callsign,
                ),
                exclude=session.websocket,
            )

    async def _send(self, websocket: Any, message: dict[str, Any]) -> None:
        await websocket.send(encode_message(message))

    def _server_info_stats(self) -> dict[str, int]:
        users = self.user_registry.stats()

        rooms_total = len(self.registry.rooms)
        room_clients_total = sum(room.client_count for room in self.registry.rooms.values())
        lobby_clients_total = len(self._lobby_clients)
        clients_total = room_clients_total + lobby_clients_total

        return {
            "rooms_total": rooms_total,
            "clients_total": clients_total,
            "known_installations": int(users.get("known_installations", 0)),
            "seen_24h": int(users.get("seen_24h", 0)),
            "seen_7d": int(users.get("seen_7d", 0)),
        }


    def _make_server_info_message(self, room: RoomState) -> dict[str, Any]:
        stats = self._server_info_stats()

        return make_server_info(
            server_id=self.server_id,
            server_name=self.config.server.server_name,
            started_at=self.started_at,
            rooms_total=stats["rooms_total"],
            clients_total=stats["clients_total"],
            room_key=room.room_key,
            room_id=room.room_id,
            room_name=room.name,
            room_clients=room.client_count,
            known_installations=stats["known_installations"],
            seen_24h=stats["seen_24h"],
            seen_7d=stats["seen_7d"],
        )
    

    def _make_server_info_snapshot_message(self) -> dict[str, Any]:
        stats = self._server_info_stats()

        return make_server_info(
            server_id=self.server_id,
            server_name=self.config.server.server_name,
            started_at=self.started_at,
            rooms_total=stats["rooms_total"],
            clients_total=stats["clients_total"],
            room_key="",
            room_id="",
            room_name="",
            room_clients=0,
            known_installations=stats["known_installations"],
            seen_24h=stats["seen_24h"],
            seen_7d=stats["seen_7d"],
        )


    async def _broadcast_server_info_all(self) -> None:
        async with self._lock:
            rooms = list(self.registry.rooms.values())

        for room in rooms:
            if room.client_count <= 0:
                continue
            await self._broadcast(room, self._make_server_info_message(room))


    async def _server_info_loop(self) -> None:
        interval = max(5, int(self.config.server_info.interval_seconds))

        while True:
            await asyncio.sleep(float(interval))
            try:
                await self._broadcast_server_info_all()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOGGER.warning("Server info broadcast failed: %s", exc)

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(60.0)
            try:
                async with self._lock:
                    deleted = self.registry.cleanup_expired_private_rooms()
                    if deleted:
                        self.registry.save_persisted_private_rooms()

                if deleted:
                    LOGGER.info("Cleaned up %s expired private room(s).", deleted)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOGGER.warning("Private room cleanup failed: %s", exc)
