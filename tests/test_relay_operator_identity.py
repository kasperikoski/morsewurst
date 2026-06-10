from __future__ import annotations

import asyncio
from typing import Any

import pytest

from morsewurst.network.identity import generate_operator_identity, sign_operator_challenge
from morsewurst.network.protocol import (
    attach_server_operator_fields,
    decode_message,
    encode_message,
    make_auth,
    make_client_hello,
    make_key_message,
)
from morsewurst.server.models import RelayServerConfig, RoomDefinition
from morsewurst.server.relay import RelayServer
from morsewurst.server.rooms import RoomError


class DynamicAuthWebSocket:
    def __init__(self, *, server: RelayServer, room: str, client_id: str, password: str = "", identity: Any = None, client_mode: str = "operator") -> None:
        self.server = server
        self.room = room
        self.client_id = client_id
        self.password = password
        self.identity = identity
        self.client_mode = client_mode
        self.sent: list[str] = []

    async def send(self, raw: str) -> None:
        self.sent.append(raw)

    async def recv(self) -> str:
        challenge = decode_message(self.sent[-1])
        operator_auth = None
        if self.identity is not None:
            operator_auth = sign_operator_challenge(
                self.identity,
                server_id=self.server.server_id,
                server_nonce=str(challenge.get("nonce") or ""),
                room=str(challenge.get("room") or self.room),
                client_id=self.client_id,
            )
        return encode_message(
            make_auth(
                password=self.password,
                room=str(challenge.get("room") or self.room),
                client_id=self.client_id,
                nonce=str(challenge.get("nonce") or ""),
                auth_required=bool(challenge.get("auth_required", True)),
                operator_auth=operator_auth,
            )
        )


@pytest.mark.asyncio
async def test_relay_marks_session_verified_only_after_operator_auth() -> None:
    identity = generate_operator_identity()
    server = RelayServer(
        RelayServerConfig(
            rooms=[RoomDefinition(id="default", name="Default", access="public")]
        )
    )
    client_id = "client-verified"
    websocket = DynamicAuthWebSocket(server=server, room="default", client_id=client_id, identity=identity)
    hello = make_client_hello(
        room="default",
        callsign="Tester",
        client_id=client_id,
        client_mode="operator",
        operator_id=identity.operator_id,
        operator_public_key=identity.operator_public_key,
    )

    session, _room = await server._authenticate(websocket, hello)

    assert session.operator_verified is True
    assert session.operator_id == identity.operator_id


@pytest.mark.asyncio
async def test_old_client_without_operator_identity_still_joins_public_room() -> None:
    server = RelayServer(
        RelayServerConfig(
            rooms=[RoomDefinition(id="default", name="Default", access="public")]
        )
    )
    client_id = "client-old"
    websocket = DynamicAuthWebSocket(server=server, room="default", client_id=client_id)
    hello = make_client_hello(room="default", callsign="Old", client_id=client_id)

    session, _room = await server._authenticate(websocket, hello)

    assert session.operator_verified is False
    assert session.operator_id == ""


@pytest.mark.asyncio
async def test_listener_mode_can_join_public_room() -> None:
    server = RelayServer(
        RelayServerConfig(
            rooms=[RoomDefinition(id="default", name="Default", access="public")]
        )
    )
    client_id = "listener-1"
    websocket = DynamicAuthWebSocket(server=server, room="default", client_id=client_id, client_mode="listener")
    hello = make_client_hello(room="default", callsign="Listener", client_id=client_id, client_mode="listener")

    session, _room = await server._authenticate(websocket, hello)

    assert session.client_mode == "listener"
    assert session.operator_verified is False


def test_server_operator_fields_override_client_spoofing() -> None:
    message = make_key_message(
        key_event={"type": "key", "state": "down", "t": 123, "src": "straight"},
        sender_id="client-1",
        sender_name="Tester",
        seq=1,
        stream_id="stream-1",
    )
    message["operator_id"] = "MWOP-0000-0000-0000-0000-0000"
    message["operator_verified"] = True

    clean = attach_server_operator_fields(
        message,
        operator_id="MWOP-1111-1111-1111-1111-1111",
        operator_verified=False,
    )

    assert clean["operator_id"] == "MWOP-1111-1111-1111-1111-1111"
    assert clean["operator_verified"] is False


@pytest.mark.asyncio
async def test_private_room_access_is_not_granted_by_operator_id() -> None:
    identity = generate_operator_identity()
    server = RelayServer(
        RelayServerConfig(
            rooms=[RoomDefinition(id="secret", name="Secret", access="private", password="correct")]
        )
    )
    client_id = "client-private"
    websocket = DynamicAuthWebSocket(server=server, room="secret", client_id=client_id, password="wrong", identity=identity)
    hello = make_client_hello(
        room="secret",
        callsign="Tester",
        client_id=client_id,
        operator_id=identity.operator_id,
        operator_public_key=identity.operator_public_key,
    )

    with pytest.raises(RoomError):
        await server._authenticate(websocket, hello)
