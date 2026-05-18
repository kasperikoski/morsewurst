# ============================================================
# morsewurst/network/room_server.py
# ============================================================

from __future__ import annotations

import time
import asyncio
import ssl
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from morsewurst.network.protocol import (
    ProtocolError,
    decode_message,
    encode_message,
    make_peer_event,
    make_server_challenge,
    make_status,
    make_welcome,
    new_id,
    new_nonce,
    normalize_callsign,
    normalize_room,
    room_password_verifier,
    verify_auth,
    make_server_info,
    make_server_pong,
    sanitize_installation_id,
)

try:
    from websockets.asyncio.server import serve
except ImportError:  # pragma: no cover
    from websockets import serve  # type: ignore[assignment]


StatusCallback = Callable[[str, str], None]
ToneCallback = Callable[[Dict[str, Any]], None]


@dataclass(slots=True)
class ClientInfo:
    client_id: str
    callsign: str
    websocket: Any
    installation_id: str = ""
    client_version: str = ""


class RoomServer:
    """Small single-room WebSocket server for local MorseWurst testing.

    The Raspberry Pi deployment uses morsewurst.server.relay instead. This class
    remains for the older console host mode and local tests.
    """

    def __init__(
        self,
        *,
        room: str,
        password: str,
        host_callsign: str,
        server_id: Optional[str] = None,
        status_callback: Optional[StatusCallback] = None,
        remote_tone_callback: Optional[ToneCallback] = None,
    ) -> None:
        self.room = normalize_room(room)
        self.password = password or ""
        self.password_verifier = room_password_verifier(password=self.password, room=self.room)
        self.host_callsign = normalize_callsign(host_callsign)
        self.server_id = server_id or new_id("server")
        self.started_at = time.time()
        self.status_callback = status_callback
        self.remote_tone_callback = remote_tone_callback

        self._clients: Dict[Any, ClientInfo] = {}
        self._server = None
        self._lock = asyncio.Lock()

    async def start(
        self,
        *,
        host: str,
        port: int,
        ssl_context: Optional[ssl.SSLContext] = None,
    ) -> None:
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
        self._status("info", f"Huone '{self.room}' kuuntelee osoitteessa {scheme}://{host}:{port}")
        await self._server.wait_closed()

    async def stop(self) -> None:
        async with self._lock:
            clients = list(self._clients.keys())
            self._clients.clear()

        for websocket in clients:
            try:
                await websocket.close()
            except Exception:
                pass

        if self._server is not None:
            self._server.close()
            try:
                await self._server.wait_closed()
            except Exception:
                pass
            self._server = None

    async def broadcast_local_tone(self, message: Dict[str, Any]) -> None:
        await self._broadcast(message, exclude=None)

    async def _handler_compatible(self, websocket: Any, *args: Any) -> None:
        await self._handle_client(websocket)

    async def _handle_client(self, websocket: Any) -> None:
        info: Optional[ClientInfo] = None
        try:
            info = await self._authenticate(websocket)
            await self._register_client(info)

            async for raw in websocket:
                try:
                    message = decode_message(raw)
                except ProtocolError as exc:
                    await self._send(websocket, make_status(f"Virheellinen viesti: {exc}", level="warning"))
                    continue

                message_type = str(message.get("type") or "")

                if message_type == "tone":
                    message["via_server_id"] = self.server_id
                    if self.remote_tone_callback is not None:
                        self.remote_tone_callback(message)
                    await self._broadcast(message, exclude=websocket)
                    continue

                if message_type == "heartbeat":
                    await self._send(websocket, make_status("heartbeat_ok", level="debug"))
                    continue

                if message_type == "server_info_request":
                    await self._send(
                        websocket,
                        make_server_info(
                            server_id=self.server_id,
                            server_name="Morsewurst Host",
                            started_at=self.started_at,
                            rooms_total=1,
                            clients_total=len(self._clients),
                            room_key=self.room,
                            room_id="",
                            room_name=self.room,
                            room_clients=len(self._clients),
                        ),
                    )
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

        except Exception as exc:
            self._status("warning", f"Asiakasyhteys päättyi: {exc}")
        finally:
            if info is not None:
                await self._unregister_client(info)

    async def _authenticate(self, websocket: Any) -> ClientInfo:
        raw_hello = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        hello = decode_message(raw_hello)

        if hello.get("type") != "client_hello":
            raise ProtocolError("Ensimmäisen viestin pitää olla client_hello.")

        client_room = normalize_room(str(hello.get("room") or ""))
        if client_room != self.room:
            raise ProtocolError("Väärä huone.")

        client_id = str(hello.get("client_id") or new_id("client"))
        callsign = normalize_callsign(str(hello.get("callsign") or "Morsewurst"))
        installation_id = sanitize_installation_id(hello.get("installation_id"))
        client_version = str(hello.get("client_version") or "")[:40]
        nonce = new_nonce()

        await self._send(
            websocket,
            make_server_challenge(room=self.room, server_id=self.server_id, nonce=nonce, room_exists=True, room_access="private", auth_required=True),
        )

        raw_auth = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        auth = decode_message(raw_auth)

        if auth.get("type") != "auth":
            raise ProtocolError("Toisen viestin pitää olla auth.")

        proof = str(auth.get("proof") or "")
        auth_client_id = str(auth.get("client_id") or "")

        if auth_client_id != client_id:
            raise ProtocolError("Auth-viestin client_id ei täsmää.")

        if not verify_auth(
            room=self.room,
            client_id=client_id,
            nonce=nonce,
            proof=proof,
            password=self.password,
            password_verifier=self.password_verifier,
        ):
            raise ProtocolError("Huoneen salasana ei täsmää.")

        return ClientInfo(
            client_id=client_id,
            callsign=callsign,
            websocket=websocket,
            installation_id=installation_id,
            client_version=client_version,
        )

    async def _register_client(self, info: ClientInfo) -> None:
        async with self._lock:
            peers = [
                {"client_id": client.client_id, "callsign": client.callsign}
                for client in self._clients.values()
            ]
            self._clients[info.websocket] = info

        await self._send(
            info.websocket,
            make_welcome(
                room_key=self.room,
                server_id=self.server_id,
                client_id=info.client_id,
                peers=peers,
                room_name=self.room,
                room_id="",
            )
        )
        await self._broadcast(
            make_peer_event(event_type="peer_joined", client_id=info.client_id, callsign=info.callsign),
            exclude=info.websocket,
        )
        self._status("info", f"{info.callsign} liittyi huoneeseen.")

    async def _unregister_client(self, info: ClientInfo) -> None:
        async with self._lock:
            self._clients.pop(info.websocket, None)

        await self._broadcast(
            make_peer_event(event_type="peer_left", client_id=info.client_id, callsign=info.callsign),
            exclude=info.websocket,
        )
        self._status("info", f"{info.callsign} poistui huoneesta.")

    async def _broadcast(self, message: Dict[str, Any], *, exclude: Any = None) -> None:
        async with self._lock:
            targets = [websocket for websocket in self._clients.keys() if websocket is not exclude]

        if not targets:
            return

        encoded = encode_message(message)
        stale = []

        for websocket in targets:
            try:
                await websocket.send(encoded)
            except Exception:
                stale.append(websocket)

        if stale:
            async with self._lock:
                for websocket in stale:
                    self._clients.pop(websocket, None)

    async def _send(self, websocket: Any, message: Dict[str, Any]) -> None:
        await websocket.send(encode_message(message))

    def _status(self, level: str, text: str) -> None:
        if self.status_callback is None:
            return
        try:
            self.status_callback(level, text)
        except Exception:
            pass
