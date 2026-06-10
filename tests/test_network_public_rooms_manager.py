from __future__ import annotations

import asyncio
from typing import Any

import pytest

from morsewurst.network import public_rooms as public_rooms_module
from morsewurst.network.manager import NetworkManager
from morsewurst.network.models import NetworkSettings
from morsewurst.network.protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    decode_message,
    encode_message,
    make_server_pong,
)


class FakeConnect:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.sent_messages: list[dict[str, Any]] = []
        self.kwargs: dict[str, Any] = {}

    async def __aenter__(self) -> "FakeConnect":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def send(self, raw: str) -> None:
        self.sent_messages.append(decode_message(raw))

    async def recv(self) -> str:
        return encode_message(self.response)


def _patch_public_rooms_connect(monkeypatch: pytest.MonkeyPatch, fake: FakeConnect) -> None:
    def connect(_server_uri: str, **kwargs: Any) -> FakeConnect:
        fake.kwargs = kwargs
        return fake

    monkeypatch.setattr(public_rooms_module, "connect", connect)


def test_public_room_display_label_shows_capacity_only_when_max_is_known() -> None:
    assert public_rooms_module.PublicRoom(id="default", name="General").display_label == "General"
    assert (
        public_rooms_module.PublicRoom(
            id="default",
            name="General",
            client_count=2,
            max_clients=8,
        ).display_label
        == "General (2/8)"
    )


def test_fetch_public_rooms_once_sends_request_and_maps_sanitized_rooms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeConnect(
        {
            "type": "public_rooms",
            "rooms": [
                {
                    "id": "Room One",
                    "name": "Room\nOne",
                    "description": "Line\rBreak",
                    "client_count": "2",
                    "max_clients": "8",
                },
                {
                    "id": "Fallback Name",
                    "name": "",
                    "description": None,
                    "client_count": "bad",
                    "max_clients": False,
                },
                "ignored",
            ],
        }
    )
    _patch_public_rooms_connect(monkeypatch, fake)

    rooms = asyncio.run(
        public_rooms_module._fetch_public_rooms_once(server_uri="ws://relay.example.test")
    )

    assert len(fake.sent_messages) == 1
    request = fake.sent_messages[0]
    assert request["v"] == PROTOCOL_VERSION
    assert request["app"] == "morsewurst"
    assert request["type"] == "public_rooms_request"
    assert request["capabilities"] == {"public_rooms": True}
    assert request["ts_ms"] > 0
    assert fake.kwargs["max_size"] == 512_000
    assert rooms == [
        public_rooms_module.PublicRoom(
            id="room-one",
            name="Room One",
            description="Line Break",
            client_count=2,
            max_clients=8,
        ),
        public_rooms_module.PublicRoom(
            id="fallback-name",
            name="fallback-name",
            description="",
            client_count=0,
            max_clients=0,
        ),
    ]


def test_fetch_public_rooms_once_rejects_empty_or_wrong_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = FakeConnect({"type": "public_rooms", "rooms": []})
    _patch_public_rooms_connect(monkeypatch, empty)

    with pytest.raises(ProtocolError, match="no public rooms"):
        asyncio.run(public_rooms_module._fetch_public_rooms_once(server_uri="ws://relay"))

    wrong = FakeConnect({"type": "status", "text": "not rooms"})
    _patch_public_rooms_connect(monkeypatch, wrong)

    with pytest.raises(ProtocolError, match="public_rooms"):
        asyncio.run(public_rooms_module._fetch_public_rooms_once(server_uri="ws://relay"))


def test_fetch_server_info_once_requires_server_info_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeConnect(
        {
            "type": "server_info",
            "server_name": "Relay",
            "rooms_total": 2,
            "clients_total": 5,
        }
    )
    _patch_public_rooms_connect(monkeypatch, fake)

    info = asyncio.run(public_rooms_module._fetch_server_info_once(server_uri="ws://relay"))

    assert len(fake.sent_messages) == 1
    request = fake.sent_messages[0]
    assert request["v"] == PROTOCOL_VERSION
    assert request["app"] == "morsewurst"
    assert request["type"] == "server_info_request"
    assert request["sender_id"] == "lobby"
    assert info["server_name"] == "Relay"
    assert info["rooms_total"] == 2

    wrong = FakeConnect({"type": "public_rooms", "rooms": []})
    _patch_public_rooms_connect(monkeypatch, wrong)

    with pytest.raises(ProtocolError, match="unexpected response"):
        asyncio.run(public_rooms_module._fetch_server_info_once(server_uri="ws://relay"))


def test_ping_server_once_sends_client_ping_and_adds_local_receive_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pong = make_server_pong(server_id="server-1", ping_id="ping-1", client_sent_ms=123)
    fake = FakeConnect(pong)
    _patch_public_rooms_connect(monkeypatch, fake)

    result = asyncio.run(public_rooms_module._ping_server_once(server_uri="ws://relay"))

    assert fake.sent_messages[0]["type"] == "client_ping"
    assert fake.sent_messages[0]["sender_id"] == "lobby"
    assert result["type"] == "server_pong"
    assert result["round_trip_ms"] >= 0
    assert result["client_received_time"] > 0
    assert result["client_received_monotonic"] > 0


def test_fetch_async_wrappers_convert_timeouts_to_clear_timeout_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def never_returns(*, server_uri: str) -> list[Any]:
        await asyncio.sleep(1)
        return []

    monkeypatch.setattr(public_rooms_module, "_fetch_public_rooms_once", never_returns)

    with pytest.raises(TimeoutError, match="Public room list request timed out"):
        asyncio.run(
            public_rooms_module._fetch_public_rooms_async(
                server_uri="ws://relay",
                timeout_seconds=0.001,
            )
        )


def test_public_room_log_context_helpers_are_defensive() -> None:
    info_context = public_rooms_module._server_info_log_context(
        {
            "name": "Fallback Relay",
            "room_count": "bad",
            "client_count": -5,
            "uptime_seconds": True,
            "rooms": [
                {"id": "default", "client_count": 2},
                {"room": "alpha", "client_count": "3"},
                {"name": "beta", "client_count": "bad"},
                "ignored",
            ],
        }
    )

    assert info_context == {
        "server_name": "Fallback Relay",
        "rooms_total": 0,
        "clients_total": 0,
        "room_clients": {"default": 2, "alpha": 3, "beta": 0},
        "uptime_seconds": 0,
    }

    error_context = public_rooms_module._exception_context(
        RuntimeError("getaddrinfo failed after timeout during WebSocket handshake")
    )
    assert error_context["is_dns_error"] is True
    assert error_context["is_timeout"] is True
    assert error_context["is_websocket_error"] is True


def _run_submitted_coroutine(coro: Any, _loop: Any) -> object:
    try:
        asyncio.run(coro)
    finally:
        if hasattr(coro, "close"):
            coro.close()
    return object()


def test_network_manager_server_queries_use_client_queue_when_control_channel_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = NetworkManager()
    manager._mode = "client"
    manager._loop = object()  # type: ignore[assignment]
    manager._client_send_queue = asyncio.Queue(maxsize=10)
    manager._control_ready_event.set()
    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", _run_submitted_coroutine)

    manager.request_server_info()
    manager.request_server_ping()

    first = manager._client_send_queue.get_nowait()
    second = manager._client_send_queue.get_nowait()
    assert first["v"] == PROTOCOL_VERSION
    assert first["type"] == "server_info_request"
    assert first["sender_id"] == manager.client_id
    assert second["v"] == PROTOCOL_VERSION
    assert second["type"] == "client_ping"
    assert second["sender_id"] == manager.client_id


def test_network_manager_server_queries_do_not_queue_before_control_channel_is_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = NetworkManager()
    manager._mode = "client"
    manager._loop = object()  # type: ignore[assignment]
    manager._client_send_queue = asyncio.Queue(maxsize=10)
    manager._control_ready_event.clear()
    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", _run_submitted_coroutine)

    manager.request_server_info()
    manager.request_server_ping()

    assert manager._client_send_queue.empty()


def test_network_manager_publish_local_tone_respects_transmit_and_message_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = NetworkManager()
    manager._mode = "client"
    manager._loop = object()  # type: ignore[assignment]
    manager._client_send_queue = asyncio.Queue(maxsize=10)
    manager._settings = NetworkSettings(callsign="Tester", transmit_enabled=False)
    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", _run_submitted_coroutine)

    event = {"type": "tone", "t0": 10, "t1": 30, "dur": 20, "src": "straight", "el": "."}
    manager.publish_local_tone(event)
    assert manager._client_send_queue.empty()
    assert manager._seq == 0

    manager._settings.transmit_enabled = True
    manager.publish_local_tone({"type": "status", "text": "ignore"})
    assert manager._client_send_queue.empty()
    assert manager._seq == 0

    manager.publish_local_tone(event)
    message = manager._client_send_queue.get_nowait()
    assert message["type"] == "tone"
    assert message["sender_id"] == manager.client_id
    assert message["sender_name"] == "Tester"
    assert message["seq"] == 1
    assert message["stream_id"] == manager.stream_id
    assert message["tone"] == event

    manager.publish_local_tone({"type": "tone", "t0": 30, "t1": 10, "dur": 20})
    [status] = manager.drain_statuses()
    assert status["level"] == "warning"
    assert "Tone-viesti" in status["text"]
