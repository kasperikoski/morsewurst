# ============================================================
# morsewurst/network/public_rooms.py
# ============================================================

from __future__ import annotations

import time
import asyncio
from dataclasses import dataclass
from typing import Any

from morsewurst.network.defaults import DEFAULT_RELAY_URI, PUBLIC_ROOMS_FETCH_TIMEOUT_SECONDS
from morsewurst.network.protocol import (
    ProtocolError,
    decode_message,
    encode_message,
    make_client_ping,
    make_public_rooms_request,
    validate_public_rooms_response,
)

try:
    from websockets.asyncio.client import connect
except ImportError:  # pragma: no cover
    from websockets import connect  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class PublicRoom:
    id: str
    name: str
    description: str = ""
    client_count: int = 0
    max_clients: int = 0

    @property
    def display_label(self) -> str:
        if self.max_clients > 0:
            return f"{self.name} ({self.client_count}/{self.max_clients})"
        return self.name


def fetch_public_rooms(
    *,
    server_uri: str = DEFAULT_RELAY_URI,
    timeout_seconds: float = PUBLIC_ROOMS_FETCH_TIMEOUT_SECONDS,
) -> list[PublicRoom]:
    return asyncio.run(
        _fetch_public_rooms_async(
            server_uri=server_uri,
            timeout_seconds=timeout_seconds,
        )
    )


async def _fetch_public_rooms_async(
    *,
    server_uri: str,
    timeout_seconds: float,
) -> list[PublicRoom]:
    try:
        return await asyncio.wait_for(
            _fetch_public_rooms_once(server_uri=server_uri),
            timeout=float(timeout_seconds),
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError("Public room list request timed out.") from exc


async def _fetch_public_rooms_once(*, server_uri: str) -> list[PublicRoom]:
    async with connect(
        server_uri,
        max_size=512_000,
        ping_interval=20,
        ping_timeout=60,
        open_timeout=15,
        close_timeout=5,
    ) as websocket:
        await websocket.send(encode_message(make_public_rooms_request()))
        response = decode_message(await websocket.recv())
        rooms = validate_public_rooms_response(response)

    public_rooms: list[PublicRoom] = []
    for room in rooms:
        public_rooms.append(
            PublicRoom(
                id=str(room.get("id") or "default"),
                name=str(room.get("name") or room.get("id") or "Yleinen"),
                description=str(room.get("description") or ""),
                client_count=_safe_int(room.get("client_count"), 0),
                max_clients=_safe_int(room.get("max_clients"), 0),
            )
        )

    if not public_rooms:
        raise ProtocolError("Server returned no public rooms.")

    return public_rooms


def fetch_server_info(
    *,
    server_uri: str = DEFAULT_RELAY_URI,
    timeout_seconds: float = PUBLIC_ROOMS_FETCH_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    return asyncio.run(
        _fetch_server_info_async(
            server_uri=server_uri,
            timeout_seconds=timeout_seconds,
        )
    )


async def _fetch_server_info_async(
    *,
    server_uri: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        return await asyncio.wait_for(
            _fetch_server_info_once(server_uri=server_uri),
            timeout=float(timeout_seconds),
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError("Server info request timed out.") from exc


async def _fetch_server_info_once(*, server_uri: str) -> dict[str, Any]:
    request = {
        "v": 4,
        "app": "morsewurst",
        "type": "server_info_request",
        "sender_id": "lobby",
    }

    async with connect(
        server_uri,
        max_size=512_000,
        ping_interval=20,
        ping_timeout=60,
        open_timeout=15,
        close_timeout=5,
    ) as websocket:
        await websocket.send(encode_message(request))
        response = decode_message(await websocket.recv())

    if response.get("type") != "server_info":
        raise ProtocolError(f"Server returned unexpected response: {response.get('type')}")

    return response


def ping_server(
    *,
    server_uri: str = DEFAULT_RELAY_URI,
    timeout_seconds: float = PUBLIC_ROOMS_FETCH_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    return asyncio.run(
        _ping_server_async(
            server_uri=server_uri,
            timeout_seconds=timeout_seconds,
        )
    )


async def _ping_server_async(
    *,
    server_uri: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        return await asyncio.wait_for(
            _ping_server_once(server_uri=server_uri),
            timeout=float(timeout_seconds),
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError("Server ping request timed out.") from exc


async def _ping_server_once(*, server_uri: str) -> dict[str, Any]:
    request = make_client_ping(sender_id="lobby")
    client_sent_ms = int(request.get("client_sent_ms") or int(time.time() * 1000))

    async with connect(
        server_uri,
        max_size=512_000,
        ping_interval=20,
        ping_timeout=60,
        open_timeout=15,
        close_timeout=5,
    ) as websocket:
        await websocket.send(encode_message(request))
        response = decode_message(await websocket.recv())

    if response.get("type") != "server_pong":
        raise ProtocolError(f"Server returned unexpected response: {response.get('type')}")

    response["round_trip_ms"] = max(0, int(time.time() * 1000) - client_sent_ms)
    response["client_received_time"] = time.time()
    response["client_received_monotonic"] = time.monotonic()

    return response


def _safe_int(value: Any, default: int) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        return max(0, int(value))
    except Exception:
        return default