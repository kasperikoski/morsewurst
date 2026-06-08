from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from morsewurst.server.user_registry import installation_id_hash

import pytest


real_websockets = pytest.importorskip("websockets")

if getattr(real_websockets, "__file__", None) is None:
    pytest.skip(
        "Real websockets package is required for integration tests. "
        "The lightweight test stub from tests/conftest.py is not enough.",
        allow_module_level=True,
    )

try:
    from websockets.asyncio.client import connect
except ImportError:  # pragma: no cover
    from websockets import connect  # type: ignore[assignment]


from morsewurst.network.protocol import (
    decode_message,
    encode_message,
    make_auth,
    make_client_hello,
    make_client_ping,
    make_heartbeat,
    make_key_message,
    make_tone_message,
    normalize_callsign,
    validate_key_message,
    validate_tone_message,
)
from morsewurst.network.public_rooms import (
    _fetch_public_rooms_async,
    _fetch_server_info_async,
    _ping_server_async,
)
from morsewurst.server.models import (
    ROOM_ACCESS_PRIVATE,
    ROOM_ACCESS_PUBLIC,
    PrivateRoomsSection,
    RelayServerConfig,
    ReservedNamesSection,
    RoomDefinition,
    ServerInfoSection,
    ServerSection,
    UserRegistrySection,
)
from morsewurst.server.relay import RelayServer


pytestmark = pytest.mark.network_integration


DEFAULT_TIMEOUT = 3.0
SHORT_QUIET_TIMEOUT = 0.20


@dataclass(slots=True)
class RunningRelay:
    server: RelayServer
    task: asyncio.Task[None]
    uri: str
    port: int
    tmp_path: Path


@dataclass(slots=True)
class ConnectedClient:
    websocket: Any
    client_id: str
    callsign: str
    room: str
    challenge: dict[str, Any]
    welcome: dict[str, Any]

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self.websocket.close()


def run_async(coro: Any, *, timeout: float = 20.0) -> Any:
    return asyncio.run(asyncio.wait_for(coro, timeout=timeout))


async def send_json(websocket: Any, message: dict[str, Any]) -> None:
    await websocket.send(encode_message(message))


async def recv_json(websocket: Any, *, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    raw = await asyncio.wait_for(websocket.recv(), timeout=timeout)
    message = decode_message(raw)
    assert isinstance(message, dict)
    return message


async def recv_until(
    websocket: Any,
    predicate: Callable[[dict[str, Any]], bool],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    label: str = "matching message",
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    seen: list[dict[str, Any]] = []

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(f"Timed out waiting for {label}. Seen messages: {seen!r}")

        message = await recv_json(websocket, timeout=remaining)
        seen.append(message)

        if predicate(message):
            return message


async def recv_type(
    websocket: Any,
    message_type: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    return await recv_until(
        websocket,
        lambda message: message.get("type") == message_type,
        timeout=timeout,
        label=f"type={message_type!r}",
    )


async def drain_messages(
    websocket: Any,
    *,
    timeout_per_message: float = SHORT_QUIET_TIMEOUT,
    limit: int = 20,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    for _ in range(limit):
        try:
            messages.append(await recv_json(websocket, timeout=timeout_per_message))
        except asyncio.TimeoutError:
            break
        except Exception:
            break

    return messages


async def assert_no_message(
    websocket: Any,
    *,
    timeout: float = SHORT_QUIET_TIMEOUT,
) -> None:
    try:
        message = await recv_json(websocket, timeout=timeout)
    except asyncio.TimeoutError:
        return

    raise AssertionError(f"Expected no message, but received: {message!r}")


def message_text(message: dict[str, Any]) -> str:
    return str(message.get("text") or message.get("message") or "")


def is_status(message: dict[str, Any], *, level: str | None = None) -> bool:
    if message.get("type") != "status":
        return False

    if level is None:
        return True

    return str(message.get("level") or "").lower() == level.lower()


def is_peer_join(message: dict[str, Any], *, client_id: str | None = None) -> bool:
    text = json.dumps(message, ensure_ascii=False).lower()
    message_type = str(message.get("type") or "").lower()

    if "peer" not in message_type and "peer" not in text:
        return False

    if "join" not in text and "connected" not in text and "entered" not in text:
        return False

    if client_id is not None and client_id.lower() not in text:
        return False

    return True


def is_peer_leave(message: dict[str, Any], *, client_id: str | None = None) -> bool:
    text = json.dumps(message, ensure_ascii=False).lower()
    message_type = str(message.get("type") or "").lower()

    if "peer" not in message_type and "peer" not in text:
        return False

    if "leave" not in text and "disconnect" not in text and "left" not in text:
        return False

    if client_id is not None and client_id.lower() not in text:
        return False

    return True


def make_lobby_hello(
    *,
    client_id: str = "lobby-test-client",
    callsign: str = "Lobby Tester",
    installation_id: str = "pytest-lobby-installation",
) -> dict[str, Any]:
    return {
        "v": 4,
        "app": "morsewurst",
        "type": "lobby_hello",
        "client_id": client_id,
        "callsign": callsign,
        "installation_id": installation_id,
        "client_version": "pytest",
        "capabilities": {
            "lobby_presence": True,
            "server_info": True,
            "ping": True,
        },
    }


async def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    label: str = "condition",
    task: asyncio.Task[Any] | None = None,
) -> None:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            return

        if task is not None and task.done():
            await task

        await asyncio.sleep(0.01)

    raise AssertionError(f"Timed out waiting for {label}.")


async def start_local_relay(
    tmp_path: Path,
    *,
    public_default_max_clients: int = 20,
    tiny_max_clients: int = 1,
    private_max_clients: int = 4,
    dynamic_private_max_clients: int = 10,
    private_rooms_enabled: bool = True,
) -> RunningRelay:
    config = RelayServerConfig(
        server=ServerSection(
            host="127.0.0.1",
            port=0,
            server_name="Morsewurst Pytest Relay",
            log_level="WARNING",
        ),
        private_rooms=PrivateRoomsSection(
            enabled=private_rooms_enabled,
            ttl_minutes=60,
            max_clients=dynamic_private_max_clients,
            min_name_length=1,
            max_name_length=64,
            require_password=True,
            storage_path=str(tmp_path / "private_rooms.json"),
        ),
        server_info=ServerInfoSection(
            enabled=False,
            interval_seconds=3600,
            allow_requests=True,
        ),
        user_registry=UserRegistrySection(
            enabled=True,
            storage_path=str(tmp_path / "users.json"),
        ),
        reserved_names=ReservedNamesSection(
            exact=["admin", "root", "server", "system"],
            patterns=[r"^\d{1,4}\.\d{1,6}mhz$", r"^\d{1,4}mhz$"],
        ),
        rooms=[
            RoomDefinition(
                id="default",
                name="General",
                description="Open public test room.",
                access=ROOM_ACCESS_PUBLIC,
                listed=True,
                persistent=True,
                max_clients=public_default_max_clients,
            ),
            RoomDefinition(
                id="tiny",
                name="Tiny Room",
                description="Capacity test room.",
                access=ROOM_ACCESS_PUBLIC,
                listed=True,
                persistent=True,
                max_clients=tiny_max_clients,
            ),
            RoomDefinition(
                id="secret-base",
                name="Secret Base",
                description="Configured private test room.",
                access=ROOM_ACCESS_PRIVATE,
                password="swordfish",
                listed=False,
                persistent=True,
                max_clients=private_max_clients,
            ),
        ],
    )

    server = RelayServer(config)
    task: asyncio.Task[None] = asyncio.create_task(server.start())

    await wait_until(
        lambda: getattr(server, "_server", None) is not None
        and bool(getattr(getattr(server, "_server", None), "sockets", None)),
        timeout=DEFAULT_TIMEOUT,
        label="local relay server socket",
        task=task,
    )

    raw_server = getattr(server, "_server")
    sockets = getattr(raw_server, "sockets", None)
    assert sockets, "Relay server did not expose listening sockets."

    port = int(sockets[0].getsockname()[1])
    uri = f"ws://127.0.0.1:{port}"

    return RunningRelay(
        server=server,
        task=task,
        uri=uri,
        port=port,
        tmp_path=tmp_path,
    )


async def stop_local_relay(relay: RunningRelay) -> None:
    server = relay.server

    for attr_name in ("_server_info_task", "_cleanup_task"):
        task = getattr(server, attr_name, None)
        if task is not None:
            task.cancel()
            with contextlib.suppress(BaseException):
                await task
            with contextlib.suppress(Exception):
                setattr(server, attr_name, None)

    with contextlib.suppress(BaseException):
        await server.stop()

    raw_server = getattr(server, "_server", None)
    if raw_server is not None:
        with contextlib.suppress(Exception):
            raw_server.close()
        with contextlib.suppress(BaseException):
            await raw_server.wait_closed()
        with contextlib.suppress(Exception):
            setattr(server, "_server", None)

    if not relay.task.done():
        relay.task.cancel()

    with contextlib.suppress(BaseException):
        await relay.task


async def with_relay(tmp_path: Path, test_body: Callable[[RunningRelay], Any], **kwargs: Any) -> None:
    relay = await start_local_relay(tmp_path, **kwargs)
    try:
        await test_body(relay)
    finally:
        await stop_local_relay(relay)


async def open_raw_websocket(uri: str) -> Any:
    return await connect(
        uri,
        max_size=512_000,
        ping_interval=None,
        open_timeout=DEFAULT_TIMEOUT,
        close_timeout=1,
    )


async def connect_room(
    uri: str,
    *,
    room: str = "default",
    password: str = "",
    callsign: str = "Test Client",
    client_id: str = "client-test",
    installation_id: str | None = None,
    include_create_verifier: bool = False,
) -> ConnectedClient:
    websocket = await open_raw_websocket(uri)

    try:
        hello = make_client_hello(
            room=room,
            callsign=callsign,
            client_id=client_id,
            installation_id=installation_id or f"installation-{client_id}",
        )

        await send_json(websocket, hello)

        challenge = await recv_type(websocket, "server_challenge")
        nonce = str(challenge.get("nonce") or "")
        challenged_room = str(challenge.get("room") or room)

        auth = make_auth(
            password=password,
            room=challenged_room,
            client_id=client_id,
            nonce=nonce,
            include_create_verifier=include_create_verifier,
        )

        await send_json(websocket, auth)

        welcome = await recv_type(websocket, "welcome")

        return ConnectedClient(
            websocket=websocket,
            client_id=client_id,
            callsign=callsign,
            room=challenged_room,
            challenge=challenge,
            welcome=welcome,
        )

    except Exception:
        with contextlib.suppress(Exception):
            await websocket.close()
        raise


async def expect_join_failure(
    uri: str,
    *,
    room: str,
    password: str,
    callsign: str = "Bad Client",
    client_id: str = "client-bad",
    include_create_verifier: bool = False,
) -> list[dict[str, Any]]:
    websocket = await open_raw_websocket(uri)
    messages: list[dict[str, Any]] = []

    try:
        hello = make_client_hello(
            room=room,
            callsign=callsign,
            client_id=client_id,
            installation_id=f"installation-{client_id}",
        )
        await send_json(websocket, hello)

        challenge = await recv_type(websocket, "server_challenge")
        messages.append(challenge)

        auth = make_auth(
            password=password,
            room=str(challenge.get("room") or room),
            client_id=client_id,
            nonce=str(challenge.get("nonce") or ""),
            include_create_verifier=include_create_verifier,
        )
        await send_json(websocket, auth)

        try:
            while True:
                messages.append(await recv_json(websocket, timeout=0.75))
        except Exception:
            pass

    finally:
        with contextlib.suppress(Exception):
            await websocket.close()

    assert any(
        is_status(message, level="error")
        or "password" in json.dumps(message, ensure_ascii=False).lower()
        or "room_full" in json.dumps(message, ensure_ascii=False).lower()
        or "not found" in json.dumps(message, ensure_ascii=False).lower()
        or "huone" in json.dumps(message, ensure_ascii=False).lower()
        for message in messages
    ), f"Expected join failure status, got messages: {messages!r}"

    return messages


def _room_client_ids(relay: RunningRelay, room_key: str = "default") -> set[str]:
    room = relay.server.registry.rooms.get(room_key)
    if room is None:
        return set()

    return {
        session.client_id
        for session in room.clients.values()
    }


def _outbound_for_client_id(relay: RunningRelay, client_id: str) -> Any | None:
    for outbound in relay.server._outbound_clients.values():
        if outbound.client_id == client_id:
            return outbound

    return None


async def wait_for_outbound_client(
    relay: RunningRelay,
    client_id: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    await wait_until(
        lambda: _outbound_for_client_id(relay, client_id) is not None,
        timeout=timeout,
        label=f"outbound sender for {client_id}",
    )

    outbound = _outbound_for_client_id(relay, client_id)
    assert outbound is not None
    return outbound


async def make_outbound_queue_full_and_paused(
    relay: RunningRelay,
    client_id: str,
) -> Any:
    outbound = await wait_for_outbound_client(relay, client_id)

    old_task = outbound.task
    if not old_task.done():
        old_task.cancel()
        with contextlib.suppress(BaseException):
            await old_task

    full_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
    full_queue.put_nowait("already-full")

    parked_task = asyncio.create_task(asyncio.sleep(3600.0))

    outbound.queue = full_queue
    outbound.task = parked_task

    return outbound


def test_public_room_queries_server_info_and_ping_use_real_websockets(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        rooms = await _fetch_public_rooms_async(
            server_uri=relay.uri,
            timeout_seconds=DEFAULT_TIMEOUT,
        )

        room_ids = {room.id for room in rooms}
        assert "default" in room_ids
        assert "tiny" in room_ids
        assert "secret-base" not in room_ids

        default = next(room for room in rooms if room.id == "default")
        assert default.name == "General"
        assert default.max_clients >= 1

        info = await _fetch_server_info_async(
            server_uri=relay.uri,
            timeout_seconds=DEFAULT_TIMEOUT,
        )
        assert info["type"] == "server_info"
        assert info["server_name"] == "Morsewurst Pytest Relay"
        assert info["rooms_total"] >= 3
        assert info["clients_total"] >= 0

        pong = await _ping_server_async(
            server_uri=relay.uri,
            timeout_seconds=DEFAULT_TIMEOUT,
        )
        assert pong["type"] == "server_pong"
        assert int(pong["round_trip_ms"]) >= 0
        assert "server_received_ms" in pong

    run_async(with_relay(tmp_path, body))


def test_public_room_join_peer_join_peer_leave_and_clean_disconnect(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        alpha = await connect_room(
            relay.uri,
            room="default",
            callsign="Alpha",
            client_id="client-alpha",
        )

        assert alpha.challenge["auth_required"] is False
        assert alpha.welcome["type"] == "welcome"

        bravo = await connect_room(
            relay.uri,
            room="default",
            callsign="Bravo",
            client_id="client-bravo",
        )

        peer_join = await recv_until(
            alpha.websocket,
            lambda message: is_peer_join(message, client_id="client-bravo"),
            label="peer join event for Bravo",
        )
        assert "bravo" in json.dumps(peer_join, ensure_ascii=False).lower()

        await bravo.close()

        peer_leave = await recv_until(
            alpha.websocket,
            lambda message: is_peer_leave(message, client_id="client-bravo"),
            label="peer leave event for Bravo",
        )
        assert "bravo" in json.dumps(peer_leave, ensure_ascii=False).lower()

        await alpha.close()

    run_async(with_relay(tmp_path, body))


def test_tone_broadcast_reaches_other_clients_but_not_sender(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        alpha = await connect_room(
            relay.uri,
            room="default",
            callsign="Alpha",
            client_id="client-alpha-tone",
        )
        bravo = await connect_room(
            relay.uri,
            room="default",
            callsign="Bravo",
            client_id="client-bravo-tone",
        )

        await drain_messages(alpha.websocket)
        await drain_messages(bravo.websocket)

        tone_message = make_tone_message(
            tone_event={
                "type": "tone",
                "t0": 100_000,
                "t1": 200_000,
                "dur": 100_000,
                "src": "IAMBIC",
                "el": ".",
                "ignored_object": object(),
            },
            sender_id=alpha.client_id,
            sender_name=alpha.callsign,
            seq=1,
            stream_id="stream-alpha-test",
        )

        await send_json(alpha.websocket, tone_message)

        received = await recv_type(bravo.websocket, "tone")
        assert received["sender_id"] == alpha.client_id
        assert received["sender_name"] == "Alpha"
        assert received["seq"] == 1
        assert received["stream_id"] == "stream-alpha-test"
        assert "via_server_id" in received

        clean_tone = validate_tone_message(received)
        assert clean_tone["t0"] == 100_000
        assert clean_tone["t1"] == 200_000
        assert clean_tone["dur"] == 100_000.0
        assert clean_tone["src"] == "iambic"
        assert clean_tone["el"] == "."

        await assert_no_message(alpha.websocket)

        await bravo.close()
        await alpha.close()

    run_async(with_relay(tmp_path, body))



def test_key_broadcast_reaches_other_clients_but_not_sender(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        alpha = await connect_room(
            relay.uri,
            room="default",
            callsign="Alpha",
            client_id="client-alpha-key",
        )
        bravo = await connect_room(
            relay.uri,
            room="default",
            callsign="Bravo",
            client_id="client-bravo-key",
        )

        await drain_messages(alpha.websocket)
        await drain_messages(bravo.websocket)

        key_message = make_key_message(
            key_event={
                "v": 1,
                "type": "key",
                "src": "straight",
                "state": "down",
                "t": 123_456,
                "dit": 60_000,
                "wpm": 20.0,
            },
            sender_id=alpha.client_id,
            sender_name=alpha.callsign,
            seq=11,
            stream_id="stream-alpha-key-test",
        )

        await send_json(alpha.websocket, key_message)

        received = await recv_type(bravo.websocket, "key")
        assert received["sender_id"] == alpha.client_id
        assert received["sender_name"] == "Alpha"
        assert received["seq"] == 11
        assert received["stream_id"] == "stream-alpha-key-test"
        assert "via_server_id" in received

        clean_key = validate_key_message(received)
        assert clean_key["v"] == 1
        assert clean_key["type"] == "key"
        assert clean_key["src"] == "straight"
        assert clean_key["state"] == "down"
        assert clean_key["t"] == 123_456

        await assert_no_message(alpha.websocket)

        await bravo.close()
        await alpha.close()



def test_invalid_runtime_messages_warn_but_connection_survives(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        client = await connect_room(
            relay.uri,
            room="default",
            callsign="Runtime Tester",
            client_id="client-runtime",
        )

        await drain_messages(client.websocket)

        await client.websocket.send("this is not json")
        invalid_status = await recv_until(
            client.websocket,
            lambda message: is_status(message, level="warning"),
            label="warning status for invalid json",
        )
        assert "virheellinen" in message_text(invalid_status).lower() or "invalid" in message_text(invalid_status).lower()

        await send_json(
            client.websocket,
            {
                "v": 4,
                "app": "morsewurst",
                "type": "unknown_runtime_test_message",
            },
        )
        unknown_status = await recv_until(
            client.websocket,
            lambda message: is_status(message, level="warning"),
            label="warning status for unknown message",
        )
        assert "tuntematon" in message_text(unknown_status).lower() or "unknown" in message_text(unknown_status).lower()

        await send_json(client.websocket, make_heartbeat(sender_id=client.client_id))
        heartbeat_status = await recv_until(
            client.websocket,
            lambda message: is_status(message),
            label="heartbeat status",
        )
        assert "heartbeat" in message_text(heartbeat_status).lower()

        ping = make_client_ping(sender_id=client.client_id)
        await send_json(client.websocket, ping)
        pong = await recv_type(client.websocket, "server_pong")

        assert pong["ping_id"] == ping["ping_id"]
        assert int(pong["client_sent_ms"]) == int(ping["client_sent_ms"])

        await client.close()

    run_async(with_relay(tmp_path, body))


def test_configured_private_room_accepts_correct_password_and_rejects_wrong_password(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        await expect_join_failure(
            relay.uri,
            room="secret-base",
            password="wrong-password",
            callsign="Wrong Password",
            client_id="client-wrong-secret",
        )

        client = await connect_room(
            relay.uri,
            room="secret-base",
            password="swordfish",
            callsign="Private Correct",
            client_id="client-private-correct",
        )

        assert client.challenge["auth_required"] is True
        assert str(client.challenge.get("room_access") or "").lower() == ROOM_ACCESS_PRIVATE
        assert client.welcome["type"] == "welcome"

        await client.close()

    run_async(with_relay(tmp_path, body))


def test_dynamic_private_room_create_join_and_stays_unlisted(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        creator = await connect_room(
            relay.uri,
            room="My Secret Test Room",
            password="super-secret",
            callsign="Creator",
            client_id="client-private-creator",
            include_create_verifier=True,
        )

        assert creator.challenge["room_exists"] is False
        assert creator.challenge["can_create_private_room"] is True
        assert creator.challenge["auth_required"] is True
        assert str(creator.challenge.get("room_access") or "").lower() == ROOM_ACCESS_PRIVATE

        rooms = await _fetch_public_rooms_async(
            server_uri=relay.uri,
            timeout_seconds=DEFAULT_TIMEOUT,
        )
        assert "my-secret-test-room" not in {room.id for room in rooms}

        joiner = await connect_room(
            relay.uri,
            room="My Secret Test Room",
            password="super-secret",
            callsign="Joiner",
            client_id="client-private-joiner",
        )

        assert joiner.challenge["room_exists"] is True
        assert joiner.welcome["type"] == "welcome"

        await expect_join_failure(
            relay.uri,
            room="My Secret Test Room",
            password="wrong",
            callsign="Wrong Joiner",
            client_id="client-private-wrong",
        )

        await joiner.close()
        await creator.close()

        private_room_file = tmp_path / "private_rooms.json"
        assert private_room_file.exists()

        persisted = json.loads(private_room_file.read_text(encoding="utf-8"))
        persisted_text = json.dumps(persisted, ensure_ascii=False).lower()
        assert "my-secret-test-room" in persisted_text

    run_async(with_relay(tmp_path, body))


def test_room_capacity_limit_is_enforced_and_releases_after_disconnect(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        first = await connect_room(
            relay.uri,
            room="tiny",
            callsign="Tiny One",
            client_id="client-tiny-one",
        )

        await expect_join_failure(
            relay.uri,
            room="tiny",
            password="",
            callsign="Tiny Two",
            client_id="client-tiny-two",
        )

        await first.close()
        await asyncio.sleep(0.10)

        third = await connect_room(
            relay.uri,
            room="tiny",
            callsign="Tiny Three",
            client_id="client-tiny-three",
        )
        assert third.welcome["type"] == "welcome"

        await third.close()

    run_async(with_relay(tmp_path, body))


def test_lobby_presence_control_channel_handles_info_ping_heartbeat_and_unknown(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        websocket = await open_raw_websocket(relay.uri)

        try:
            await send_json(
                websocket,
                make_lobby_hello(
                    client_id="lobby-client-1",
                    callsign="Lobby Client",
                    installation_id="lobby-installation-1",
                ),
            )

            lobby_status = await recv_until(
                websocket,
                lambda message: is_status(message),
                label="lobby registration status",
            )
            assert "lobby" in message_text(lobby_status).lower()

            await send_json(
                websocket,
                {
                    "v": 4,
                    "app": "morsewurst",
                    "type": "server_info_request",
                    "sender_id": "lobby-client-1",
                },
            )
            info = await recv_type(websocket, "server_info")
            assert info["server_name"] == "Morsewurst Pytest Relay"

            ping = make_client_ping(sender_id="lobby-client-1")
            await send_json(websocket, ping)
            pong = await recv_type(websocket, "server_pong")
            assert pong["ping_id"] == ping["ping_id"]

            await send_json(websocket, make_heartbeat(sender_id="lobby-client-1"))
            heartbeat_status = await recv_until(
                websocket,
                lambda message: is_status(message),
                label="lobby heartbeat status",
            )
            assert "heartbeat" in message_text(heartbeat_status).lower()

            await send_json(
                websocket,
                {
                    "v": 4,
                    "app": "morsewurst",
                    "type": "strange_lobby_message",
                },
            )
            warning = await recv_until(
                websocket,
                lambda message: is_status(message, level="warning"),
                label="lobby unknown message warning",
            )
            assert "tuntematon" in message_text(warning).lower() or "unknown" in message_text(warning).lower()

        finally:
            with contextlib.suppress(Exception):
                await websocket.close()

    run_async(with_relay(tmp_path, body))


def test_first_message_public_room_server_info_and_ping_shortcuts_close_cleanly(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        public_rooms_ws = await open_raw_websocket(relay.uri)
        try:
            await send_json(
                public_rooms_ws,
                {
                    "v": 4,
                    "app": "morsewurst",
                    "type": "public_rooms_request",
                    "capabilities": {"public_rooms": True},
                },
            )
            public_rooms = await recv_type(public_rooms_ws, "public_rooms")
            assert any(room.get("id") == "default" for room in public_rooms.get("rooms", []))
        finally:
            with contextlib.suppress(Exception):
                await public_rooms_ws.close()

        server_info_ws = await open_raw_websocket(relay.uri)
        try:
            await send_json(
                server_info_ws,
                {
                    "v": 4,
                    "app": "morsewurst",
                    "type": "server_info_request",
                    "sender_id": "one-shot-info",
                },
            )
            info = await recv_type(server_info_ws, "server_info")
            assert info["server_name"] == "Morsewurst Pytest Relay"
        finally:
            with contextlib.suppress(Exception):
                await server_info_ws.close()

        ping_ws = await open_raw_websocket(relay.uri)
        try:
            ping = make_client_ping(sender_id="one-shot-ping")
            await send_json(ping_ws, ping)
            pong = await recv_type(ping_ws, "server_pong")
            assert pong["ping_id"] == ping["ping_id"]
        finally:
            with contextlib.suppress(Exception):
                await ping_ws.close()

    run_async(with_relay(tmp_path, body))


def test_malformed_first_message_does_not_crash_server(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        websocket = await open_raw_websocket(relay.uri)

        try:
            await send_json(
                websocket,
                {
                    "v": 4,
                    "app": "morsewurst",
                    "type": "not_a_valid_first_message",
                },
            )

            with contextlib.suppress(Exception):
                await recv_json(websocket, timeout=0.50)

        finally:
            with contextlib.suppress(Exception):
                await websocket.close()

        pong = await _ping_server_async(
            server_uri=relay.uri,
            timeout_seconds=DEFAULT_TIMEOUT,
        )
        assert pong["type"] == "server_pong"

    run_async(with_relay(tmp_path, body))


def test_user_registry_records_room_and_lobby_connections(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        room_installation_id = "registry-room-installation"
        lobby_installation_id = "registry-lobby-installation"

        room_callsign = "Registry Room Client"
        lobby_callsign = "Registry Lobby Client"

        expected_room_callsign = normalize_callsign(room_callsign)
        expected_lobby_callsign = normalize_callsign(lobby_callsign)

        client = await connect_room(
            relay.uri,
            room="default",
            callsign=room_callsign,
            client_id="client-registry-room",
            installation_id=room_installation_id,
        )

        lobby_ws = await open_raw_websocket(relay.uri)
        try:
            await send_json(
                lobby_ws,
                make_lobby_hello(
                    client_id="lobby-registry-client",
                    callsign=lobby_callsign,
                    installation_id=lobby_installation_id,
                ),
            )
            await recv_until(
                lobby_ws,
                lambda message: is_status(message),
                label="lobby registry status",
            )
        finally:
            with contextlib.suppress(Exception):
                await lobby_ws.close()

        await client.close()
        await asyncio.sleep(0.10)

        users_path = tmp_path / "users.json"
        assert users_path.exists()

        data = json.loads(users_path.read_text(encoding="utf-8"))
        users = data.get("users")

        assert isinstance(users, dict)
        assert len(users) >= 2

        room_hash = installation_id_hash(room_installation_id)
        lobby_hash = installation_id_hash(lobby_installation_id)

        assert room_hash in users
        assert lobby_hash in users

        room_user = users[room_hash]
        lobby_user = users[lobby_hash]

        assert isinstance(room_user, dict)
        assert isinstance(lobby_user, dict)

        assert room_user["installation_id_hash"] == room_hash
        assert lobby_user["installation_id_hash"] == lobby_hash

        assert room_user["last_callsign"] == expected_room_callsign
        assert room_user["last_room_key"] == "default"
        assert room_user["last_room_id"]
        assert room_user["connect_count"] >= 1
        assert room_user["last_protocol_version"] == 4

        assert lobby_user["last_callsign"] == expected_lobby_callsign
        assert lobby_user["last_room_key"] == ""
        assert lobby_user["last_room_id"] == ""
        assert lobby_user["connect_count"] >= 1
        assert lobby_user["last_protocol_version"] == 4

        assert expected_room_callsign in room_user.get("callsigns_seen", [])
        assert expected_lobby_callsign in lobby_user.get("callsigns_seen", [])

    run_async(with_relay(tmp_path, body))


@pytest.mark.stress
def test_many_clients_receive_broadcast_from_one_sender(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        clients: list[ConnectedClient] = []

        try:
            for index in range(8):
                clients.append(
                    await connect_room(
                        relay.uri,
                        room="default",
                        callsign=f"Stress {index}",
                        client_id=f"client-stress-{index}",
                    )
                )

            for client in clients:
                await drain_messages(client.websocket, timeout_per_message=0.05)

            sender = clients[0]
            receivers = clients[1:]

            tone_message = make_tone_message(
                tone_event={
                    "type": "tone",
                    "t0": 0,
                    "t1": 80_000,
                    "dur": 80_000,
                    "src": "straight",
                    "el": ".",
                },
                sender_id=sender.client_id,
                sender_name=sender.callsign,
                seq=99,
                stream_id="stress-stream",
            )

            await send_json(sender.websocket, tone_message)

            for receiver in receivers:
                received = await recv_type(receiver.websocket, "tone")
                assert received["sender_id"] == sender.client_id
                assert received["seq"] == 99
                assert received["stream_id"] == "stress-stream"

            await assert_no_message(sender.websocket)

        finally:
            for client in reversed(clients):
                await client.close()

    run_async(with_relay(tmp_path, body), timeout=30.0)


@pytest.mark.stress
def test_repeated_connect_send_disconnect_cycles_keep_relay_usable(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        for index in range(10):
            alpha = await connect_room(
                relay.uri,
                room="default",
                callsign=f"Cycle Alpha {index}",
                client_id=f"client-cycle-alpha-{index}",
            )
            bravo = await connect_room(
                relay.uri,
                room="default",
                callsign=f"Cycle Bravo {index}",
                client_id=f"client-cycle-bravo-{index}",
            )

            await drain_messages(alpha.websocket)
            await drain_messages(bravo.websocket)

            tone_message = make_tone_message(
                tone_event={
                    "type": "tone",
                    "t0": index * 100_000,
                    "t1": index * 100_000 + 60_000,
                    "dur": 60_000,
                    "src": "iambic",
                    "el": ".",
                },
                sender_id=alpha.client_id,
                sender_name=alpha.callsign,
                seq=index + 1,
                stream_id=f"cycle-stream-{index}",
            )

            await send_json(alpha.websocket, tone_message)
            received = await recv_type(bravo.websocket, "tone")

            assert received["sender_id"] == alpha.client_id
            assert received["seq"] == index + 1

            await bravo.close()
            await alpha.close()

        pong = await _ping_server_async(
            server_uri=relay.uri,
            timeout_seconds=DEFAULT_TIMEOUT,
        )
        assert pong["type"] == "server_pong"

    run_async(with_relay(tmp_path, body), timeout=40.0)


def test_full_outbound_queue_drops_only_slow_client_and_keeps_broadcast_fast(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        sender = await connect_room(
            relay.uri,
            room="default",
            callsign="Queue Sender",
            client_id="client-queue-sender",
        )

        slow = await connect_room(
            relay.uri,
            room="default",
            callsign="Queue Slow",
            client_id="client-queue-slow",
        )

        healthy = await connect_room(
            relay.uri,
            room="default",
            callsign="Queue Healthy",
            client_id="client-queue-healthy",
        )

        await wait_for_outbound_client(relay, sender.client_id)
        await wait_for_outbound_client(relay, slow.client_id)
        await wait_for_outbound_client(relay, healthy.client_id)

        await drain_messages(sender.websocket, timeout_per_message=0.05)
        await drain_messages(slow.websocket, timeout_per_message=0.05)
        await drain_messages(healthy.websocket, timeout_per_message=0.05)

        await make_outbound_queue_full_and_paused(relay, slow.client_id)

        tone_message = make_tone_message(
            tone_event={
                "type": "tone",
                "t0": 0,
                "t1": 80_000,
                "dur": 80_000,
                "src": "straight",
                "el": ".",
            },
            sender_id=sender.client_id,
            sender_name=sender.callsign,
            seq=123,
            stream_id="queue-full-test",
        )

        started = time.monotonic()
        await send_json(sender.websocket, tone_message)

        received_tone = await recv_type(healthy.websocket, "tone")
        elapsed = time.monotonic() - started

        assert elapsed < 0.75
        assert received_tone["sender_id"] == sender.client_id
        assert received_tone["seq"] == 123
        assert received_tone["stream_id"] == "queue-full-test"

        peer_left = await recv_until(
            healthy.websocket,
            lambda message: is_peer_leave(message, client_id=slow.client_id),
            timeout=DEFAULT_TIMEOUT,
            label="peer_left for dropped slow client",
        )

        assert slow.client_id in json.dumps(peer_left, ensure_ascii=False)

        await wait_until(
            lambda: slow.client_id not in _room_client_ids(relay),
            timeout=DEFAULT_TIMEOUT,
            label="slow client removed from room",
        )

        assert sender.client_id in _room_client_ids(relay)
        assert healthy.client_id in _room_client_ids(relay)
        assert slow.client_id not in _room_client_ids(relay)
        assert _outbound_for_client_id(relay, slow.client_id) is None

        await healthy.close()
        await sender.close()

    run_async(with_relay(tmp_path, body), timeout=30.0)


def test_stop_cleans_outbound_sender_tasks(tmp_path: Path) -> None:
    async def body(relay: RunningRelay) -> None:
        clients: list[ConnectedClient] = []

        try:
            for index in range(3):
                clients.append(
                    await connect_room(
                        relay.uri,
                        room="default",
                        callsign=f"Stop Client {index}",
                        client_id=f"client-stop-{index}",
                    )
                )

            outbound_tasks: list[asyncio.Task[Any]] = []

            for client in clients:
                outbound = await wait_for_outbound_client(relay, client.client_id)
                outbound_tasks.append(outbound.task)

            assert outbound_tasks
            assert relay.server._outbound_clients

            await relay.server.stop()

            await wait_until(
                lambda: all(task.done() for task in outbound_tasks),
                timeout=DEFAULT_TIMEOUT,
                label="all outbound sender tasks done after relay stop",
            )

            assert relay.server._outbound_clients == {}

        finally:
            for client in clients:
                with contextlib.suppress(Exception):
                    await client.close()

    run_async(with_relay(tmp_path, body), timeout=30.0)