from __future__ import annotations

import pytest

from morsewurst.network.protocol import (
    ProtocolError,
    auth_proof,
    decode_message,
    encode_message,
    make_auth,
    make_client_hello,
    make_client_ping,
    make_lobby_hello,
    make_peer_event,
    make_public_rooms_response,
    make_server_challenge,
    make_server_info,
    make_server_pong,
    make_status,
    make_tone_message,
    make_welcome,
    normalize_callsign,
    normalize_room_id,
    ROOM_ACCESS_PRIVATE,
    ROOM_ACCESS_PUBLIC,
    room_password_verifier,
    sanitize_installation_id,
    sanitize_tone_event,
    validate_public_rooms_response,
    validate_tone_message,
    verify_auth,
)


def test_encode_decode_round_trip_and_invalid_payloads() -> None:
    raw = encode_message({"type": "status", "text": "åäö"})

    assert decode_message(raw) == {"type": "status", "text": "åäö"}

    with pytest.raises(ProtocolError):
        decode_message("not-json")
    with pytest.raises(ProtocolError):
        decode_message("[]")


def test_normalizers_keep_protocol_identifiers_safe() -> None:
    assert normalize_room_id("  128.400 MHz!! ") == "128.400mhz"
    assert normalize_room_id("Ääkkös huone") == "aakkos-huone"
    assert normalize_callsign("  Kasperi\nKoski  ") == "Kasperi Koski"
    assert sanitize_installation_id("abc\n!?._:-XYZ") == "abc._:-XYZ"


def test_auth_proof_matches_and_wrong_password_fails() -> None:
    proof = auth_proof(password="secret", room="Test Room", client_id="client-1", nonce="nonce")
    verifier = room_password_verifier(password="secret", room="test-room")

    assert verify_auth(room="test-room", client_id="client-1", nonce="nonce", proof=proof, password="secret") is True
    assert verify_auth(room="test-room", client_id="client-1", nonce="nonce", proof=proof, password_verifier=verifier) is True
    assert verify_auth(room="test-room", client_id="client-1", nonce="nonce", proof=proof, password="wrong") is False


def test_make_auth_can_include_create_verifier() -> None:
    message = make_auth(
        password="secret",
        room="My Room",
        client_id="client-1",
        nonce="nonce",
        include_create_verifier=True,
    )

    assert message["type"] == "auth"
    assert message["room"] == "my-room"
    assert "proof" in message
    assert "room_password_verifier" in message


def test_tone_event_sanitization_and_validation() -> None:
    clean = sanitize_tone_event(
        {
            "type": "tone",
            "t0": "10",
            "t1": "30",
            "dur": "20",
            "src": "STRAIGHT",
            "el": "invalid",
            "ignored": object(),
        }
    )

    assert clean == {"type": "tone", "t0": 10, "t1": 30, "dur": 20.0, "src": "straight"}

    message = make_tone_message(
        tone_event={"type": "tone", "t0": 10, "t1": 30, "dur": 20, "el": "."},
        sender_id="client-1",
        sender_name="Tester",
        seq=7,
        stream_id="stream-1",
    )

    assert validate_tone_message(message)["el"] == "."

    with pytest.raises(ProtocolError):
        sanitize_tone_event({"type": "tone", "t0": 30, "t1": 10, "dur": 20})


def test_public_rooms_response_is_sanitized() -> None:
    response = make_public_rooms_response(
        server_id="server-1",
        server_name="Relay",
        rooms=[
            {"id": "Room One", "name": "Room\nOne", "description": "Test\rRoom", "client_count": "2", "max_clients": "8"},
        ],
    )
    response["rooms"].append("invalid")

    rooms = validate_public_rooms_response(response)

    assert rooms == [
        {
            "id": "room-one",
            "name": "Room One",
            "description": "Test Room",
            "access": "public",
            "listed": True,
            "client_count": 2,
            "max_clients": 8,
        }
    ]


def test_client_hello_contains_sanitized_room_and_capabilities() -> None:
    message = make_client_hello(room="My Room", callsign="Tester", client_id="client-1", installation_id="inst-1")

    assert message["type"] == "client_hello"
    assert message["room"] == "my-room"
    assert message["room_name"] == "My Room"
    assert message["capabilities"]["tone_events"] is True



def test_lobby_hello_ping_pong_status_and_server_info_are_sanitized() -> None:
    lobby = make_lobby_hello(
        callsign="  Very Long Callsign Name That Is Cut  ",
        client_id="client-" + "x" * 100,
        installation_id="inst\n!?._:-XYZ",
        client_version="v" * 100,
    )

    assert lobby["type"] == "lobby_hello"
    assert lobby["callsign"] == "Very Long Callsign N"
    assert len(lobby["client_id"]) == 80
    assert lobby["installation_id"] == "inst._:-XYZ"
    assert len(lobby["client_version"]) == 40

    ping = make_client_ping(sender_id="client-1", ping_id="p" * 200)
    assert ping["type"] == "client_ping"
    assert len(ping["ping_id"]) == 80
    assert ping["client_sent_ms"] > 0

    pong = make_server_pong(server_id="server-1", ping_id=ping["ping_id"], client_sent_ms=ping["client_sent_ms"])
    assert pong["type"] == "server_pong"
    assert pong["ping_id"] == ping["ping_id"]
    assert pong["server_received_ms"] >= ping["client_sent_ms"]

    status = make_status("hello", level="warning", code="TEST_CODE")
    assert status["type"] == "status"
    assert status["level"] == "warning"
    assert status["code"] == "TEST_CODE"

    info = make_server_info(
        server_id="server-1",
        server_name="Relay" * 50,
        started_at=999999999999.0,
        rooms_total=-5,
        clients_total=-3,
        room_key="Ääkkös Room",
        room_id="room-id-that-is-way-too-long-for-display",
        room_name="R" * 100,
        room_clients=-1,
        known_installations=-2,
        seen_24h=-3,
        seen_7d=-4,
    )
    assert info["type"] == "server_info"
    assert len(info["server_name"]) == 80
    assert info["rooms_total"] == 0
    assert info["clients_total"] == 0
    assert info["room_key"] == "aakkos-room"
    assert info["room_id"] == "ROOM-ID-THAT-IS-WAY-"
    assert len(info["room_name"]) == 80
    assert info["room_clients"] == 0
    assert info["known_installations"] == 0
    assert info["seen_24h"] == 0
    assert info["seen_7d"] == 0


def test_public_room_auth_and_private_room_auth_shapes_are_distinct() -> None:
    public_auth = make_auth(
        password="",
        room="General",
        client_id="client-1",
        nonce="nonce",
        auth_required=False,
    )
    private_auth = make_auth(
        password="secret",
        room="Secret Room",
        client_id="client-1",
        nonce="nonce",
        include_create_verifier=True,
    )

    assert public_auth["type"] == "auth"
    assert public_auth["room"] == "general"
    assert public_auth["proof"] == ""
    assert "room_password_verifier" not in public_auth

    assert private_auth["room"] == "secret-room"
    assert private_auth["proof"]
    assert private_auth["room_password_verifier"]
    assert private_auth["proof"] != private_auth["room_password_verifier"]


def test_server_challenge_welcome_and_peer_events_normalize_room_metadata() -> None:
    challenge = make_server_challenge(
        room="Ääkkös Room",
        server_id="server-1",
        nonce="nonce",
        room_access="invalid",
        auth_required=False,
    )
    assert challenge["type"] == "server_challenge"
    assert challenge["room"] == "aakkos-room"
    assert challenge["auth"] == "none"
    assert challenge["room_access"] == ROOM_ACCESS_PRIVATE

    welcome = make_welcome(
        room_key="My Room",
        room_name="Display Room",
        room_id="abc-123-long-room-id-that-is-clipped",
        room_access=ROOM_ACCESS_PUBLIC,
        server_id="server-1",
        client_id="client-1",
        peers=[{"client_id": "peer-1", "callsign": "Peer"}],
    )
    assert welcome["type"] == "welcome"
    assert welcome["room_key"] == "my-room"
    assert welcome["room"] == "my-room"
    assert welcome["room_name"] == "Display Room"
    assert welcome["room_id"] == "ABC-123-LONG-ROOM-ID"
    assert welcome["room_access"] == ROOM_ACCESS_PUBLIC
    assert welcome["peers"] == [{"client_id": "peer-1", "callsign": "Peer"}]

    joined = make_peer_event(event_type="peer_joined", client_id="client-2", callsign="  Peer\nTwo  ")
    assert joined["type"] == "peer_joined"
    assert joined["callsign"] == "Peer Two"

    with pytest.raises(ValueError):
        make_peer_event(event_type="invalid", client_id="client-2", callsign="Peer")


def test_public_rooms_response_rejects_wrong_shape_and_clamps_counts() -> None:
    with pytest.raises(ProtocolError):
        validate_public_rooms_response({"type": "status", "rooms": []})

    with pytest.raises(ProtocolError):
        validate_public_rooms_response({"type": "public_rooms", "rooms": {}})

    rooms = validate_public_rooms_response(
        {
            "type": "public_rooms",
            "rooms": [
                {
                    "id": "Overflow Room",
                    "name": "",
                    "description": "x" * 300,
                    "client_count": -5,
                    "max_clients": "bad",
                    "access": "private",
                    "listed": False,
                }
            ],
        }
    )

    assert rooms == [
        {
            "id": "overflow-room",
            "name": "overflow-room",
            "description": "x" * 200,
            "access": "public",
            "listed": True,
            "client_count": 0,
            "max_clients": 0,
        }
    ]


def test_tone_message_validation_requires_tone_payload_and_strips_complex_values() -> None:
    with pytest.raises(ProtocolError):
        validate_tone_message({"type": "status", "tone": {}})

    with pytest.raises(ProtocolError):
        validate_tone_message({"type": "tone", "tone": "not-an-object"})

    with pytest.raises(ProtocolError):
        sanitize_tone_event({"type": "tone", "t0": True, "t1": 10, "dur": 10})

    clean = sanitize_tone_event(
        {
            "type": "tone",
            "t0": 10,
            "t1": 30,
            "dur": 20,
            "src": "StraightKeyerWithVeryLongSourceName",
            "el": "-",
            "unit": 123,
            "wpm": 20.5,
            "device": ["not", "serializable"],
            "pin": 5,
            "nested": {"not": "allowed"},
        }
    )
    assert clean["src"] == "straightkeyerwithverylongsourcen"
    assert clean["el"] == "-"
    assert clean["unit"] == 123
    assert clean["wpm"] == 20.5
    assert "device" not in clean
    assert "nested" not in clean
