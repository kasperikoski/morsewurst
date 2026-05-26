from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

import pytest


real_websockets = pytest.importorskip("websockets")

if getattr(real_websockets, "__file__", None) is None:
    pytest.skip(
        "Real websockets package is required for integration tests. "
        "The lightweight test stub from tests/conftest.py is not enough.",
        allow_module_level=True,
    )


from morsewurst.network.protocol import make_client_hello

from tests.test_network_relay_integration import (
    DEFAULT_TIMEOUT,
    RunningRelay,
    _fetch_public_rooms_async,
    _fetch_server_info_async,
    connect_room,
    drain_messages,
    open_raw_websocket,
    run_async,
    send_json,
    with_relay,
)


pytestmark = pytest.mark.network_integration


def test_server_info_snapshot_does_not_disclose_private_room_names_or_ids(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        private_client = await connect_room(
            relay.uri,
            room="Very Secret Dynamic Room",
            password="dynamic-password",
            callsign="Private User",
            client_id="client-private-snapshot",
            include_create_verifier=True,
        )

        try:
            info = await _fetch_server_info_async(
                server_uri=relay.uri,
                timeout_seconds=DEFAULT_TIMEOUT,
            )

            encoded = json.dumps(info, ensure_ascii=False).lower()
            assert info["type"] == "server_info"
            assert info["rooms_total"] >= 4
            assert info["room_key"] == ""
            assert info["room_id"] == ""
            assert info["room_name"] == ""
            assert "secret-base" not in encoded
            assert "very-secret-dynamic-room" not in encoded
            assert "very secret dynamic room" not in encoded
        finally:
            await private_client.close()

    run_async(with_relay(tmp_path, body))


def test_public_room_list_does_not_expose_dynamic_private_rooms_after_creation(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        private_client = await connect_room(
            relay.uri,
            room="Unlisted Dynamic Room",
            password="dynamic-password",
            callsign="Private User",
            client_id="client-private-list",
            include_create_verifier=True,
        )

        try:
            rooms = await _fetch_public_rooms_async(
                server_uri=relay.uri,
                timeout_seconds=DEFAULT_TIMEOUT,
            )
            room_ids = {room.id for room in rooms}
            room_names = {room.name for room in rooms}

            assert "default" in room_ids
            assert "tiny" in room_ids
            assert "secret-base" not in room_ids
            assert "unlisted-dynamic-room" not in room_ids
            assert "Unlisted Dynamic Room" not in room_names
        finally:
            await private_client.close()

    run_async(with_relay(tmp_path, body))


def test_dynamic_private_room_creation_can_be_disabled(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        websocket = await open_raw_websocket(relay.uri)
        messages: list[dict[str, Any]] = []

        try:
            await send_json(
                websocket,
                make_client_hello(
                    room="Should Not Be Created",
                    callsign="Blocked User",
                    client_id="client-private-disabled",
                    installation_id="installation-private-disabled",
                ),
            )
            messages = await drain_messages(websocket, timeout_per_message=0.75, limit=5)
        finally:
            with contextlib.suppress(Exception):
                await websocket.close()

        encoded = json.dumps(messages, ensure_ascii=False).lower()
        assert not messages or "not found" in encoded or "huonetta ei ole olemassa" in encoded
        assert "should-not-be-created" not in relay.server.registry.rooms

        rooms = await _fetch_public_rooms_async(
            server_uri=relay.uri,
            timeout_seconds=DEFAULT_TIMEOUT,
        )
        assert "should-not-be-created" not in {room.id for room in rooms}

    run_async(with_relay(tmp_path, body, private_rooms_enabled=False))
