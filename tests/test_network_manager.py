from __future__ import annotations

import asyncio

from morsewurst.network.manager import NetworkManager


class FakeJitterBuffer:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    def push_message(self, message: dict[str, object]) -> None:
        self.messages.append(message)


async def _enqueue(manager: NetworkManager, message: dict[str, object]) -> bool:
    return await manager._enqueue_client_message(message)


async def _send_client_message(manager: NetworkManager, message: dict[str, object]) -> None:
    await manager._send_client_message(message)


def test_debug_status_messages_are_logged_but_not_queued_for_ui() -> None:
    manager = NetworkManager()

    manager._handle_status_message(
        {"type": "status", "level": "debug", "text": "heartbeat_ok", "code": "HEARTBEAT"},
        source="lobby",
    )

    assert manager.drain_statuses() == []


def test_non_debug_status_messages_are_queued_for_ui() -> None:
    manager = NetworkManager()

    manager._handle_status_message(
        {"type": "status", "level": "warning", "text": "Something happened.", "code": "WARN"},
        source="room",
    )

    [status] = manager.drain_statuses()
    assert status["level"] == "warning"
    assert status["text"] == "Something happened."


def test_status_handler_normalizes_unknown_source_and_level() -> None:
    manager = NetworkManager()

    manager._handle_status_message(
        {"type": "status", "level": "very-strange", "text": "Fallback level."},
        source="not-a-source",
    )

    [status] = manager.drain_statuses()
    assert status["level"] == "info"
    assert status["text"] == "Fallback level."


def test_client_message_queue_only_accepts_messages_in_client_mode() -> None:
    manager = NetworkManager()
    manager._client_send_queue = asyncio.Queue(maxsize=1)

    assert asyncio.run(_enqueue(manager, {"type": "client_ping"})) is False
    assert manager._client_send_queue.empty()

    manager._mode = "client"
    assert asyncio.run(_enqueue(manager, {"type": "client_ping"})) is True
    assert manager._client_send_queue.qsize() == 1


def test_send_client_message_reports_full_queue() -> None:
    manager = NetworkManager()
    manager._mode = "client"
    manager._client_send_queue = asyncio.Queue(maxsize=1)
    manager._client_send_queue.put_nowait({"type": "already-full"})

    asyncio.run(_send_client_message(manager, {"type": "client_ping"}))

    [status] = manager.drain_statuses()
    assert status["level"] == "warning"
    assert "lähetysjono" in status["text"]


def test_remote_tone_ignores_own_echo_and_pushes_other_clients_to_jitter_buffer() -> None:
    manager = NetworkManager()
    fake = FakeJitterBuffer()
    manager.jitter_buffer = fake  # type: ignore[assignment]

    manager._handle_remote_tone({"type": "tone", "sender_id": manager.client_id})
    manager._handle_remote_tone({"type": "tone", "sender_id": "other-client"})

    assert fake.messages == [{"type": "tone", "sender_id": "other-client"}]


def test_format_connection_error_returns_user_friendly_messages() -> None:
    manager = NetworkManager()

    assert "valmiustila" in manager._format_connection_error(RuntimeError("no close frame received or sent"))
    assert "aikakatkaistiin" in manager._format_connection_error(RuntimeError("timed out during opening handshake"))
    assert "ei vastannut ajoissa" in manager._format_connection_error(RuntimeError("keepalive ping timeout"))
    assert "sulkeutui" in manager._format_connection_error(RuntimeError("connection closed"))
    assert manager._format_connection_error(RuntimeError("plain error")) == "plain error"
