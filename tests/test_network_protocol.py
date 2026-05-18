from __future__ import annotations

import pytest

from morsewurst.network.protocol import (
    ProtocolError,
    auth_proof,
    decode_message,
    encode_message,
    make_auth,
    make_client_hello,
    make_public_rooms_response,
    make_tone_message,
    normalize_callsign,
    normalize_room_id,
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
