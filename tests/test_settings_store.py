from __future__ import annotations

import json

from morsewurst.network.defaults import DEFAULT_RELAY_URI
from morsewurst.network.settings_store import (
    MAX_REMEMBERED_PRIVATE_ROOMS,
    NetworkClientSettings,
    RememberedPrivateRoom,
    forget_private_room,
    load_network_settings,
    remember_private_room,
    sanitize_host,
    sanitize_server_uri,
    save_network_settings,
    sanitize_remembered_private_rooms,
    settings_from_data,
)


def test_load_network_settings_returns_defaults_for_missing_or_invalid_file(tmp_path) -> None:
    missing = tmp_path / "missing.json"
    invalid = tmp_path / "invalid.json"
    invalid.write_text("not-json", encoding="utf-8")

    assert load_network_settings(missing).callsign == "Morsewurst"
    assert load_network_settings(invalid).last_server_uri == DEFAULT_RELAY_URI


def test_settings_from_data_sanitizes_ranges_and_legacy_server_uri() -> None:
    settings = settings_from_data(
        {
            "callsign": "  Tester\nName  ",
            "installation_id": "abc\nBAD!",
            "last_server_uri": "ws://localhost:8765",
            "last_port": 999999,
            "jitter_buffer_ms": -50,
            "frequency_hz": 999999,
            "volume": 5,
            "waveform": "invalid",
            "sample_rate": 100,
            "blocksize": 999999,
            "latency": "turbo",
            "remember_password": True,
            "saved_password": "secret\nvalue",
        }
    )

    assert settings.callsign == "Tester Name"
    assert settings.installation_id == "abcBAD"
    assert settings.last_server_uri == DEFAULT_RELAY_URI
    assert settings.last_port == 65535
    assert settings.jitter_buffer_ms == 0
    assert settings.frequency_hz == 2400.0
    assert settings.volume == 1.0
    assert settings.waveform == "sine"
    assert settings.sample_rate == 8000
    assert settings.blocksize == 16384
    assert settings.latency == "high"
    assert settings.saved_password == "secretvalue"


def test_save_network_settings_strips_single_saved_password_unless_enabled(tmp_path) -> None:
    path = tmp_path / "settings.json"
    settings = NetworkClientSettings(remember_password=False, saved_password="secret")

    save_network_settings(settings, path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["saved_password"] == ""


def test_save_and_load_network_settings_round_trip_private_rooms(tmp_path) -> None:
    path = tmp_path / "settings.json"
    settings = NetworkClientSettings(
        callsign="Tester",
        remember_password=True,
        saved_password="secret",
        remembered_private_rooms=[
            RememberedPrivateRoom(server_uri="wss://example.com", room_id="alpha", display_name="Alpha", saved_password="pw", last_used_ts=2.0),
        ],
    )

    save_network_settings(settings, path)
    loaded = load_network_settings(path)

    assert loaded.callsign == "Tester"
    assert loaded.saved_password == "secret"
    assert len(loaded.remembered_private_rooms) == 1
    assert loaded.remembered_private_rooms[0].display_label == "Alpha · wss://example.com"


def test_remember_private_room_deduplicates_and_forget_removes() -> None:
    settings = NetworkClientSettings()
    remember_private_room(settings, server_uri="wss://example.com", room_name="Alpha Room", password="one")
    remember_private_room(settings, server_uri="wss://example.com", room_name="Alpha Room", password="two")

    assert len(settings.remembered_private_rooms) == 1
    assert settings.remembered_private_rooms[0].room_id == "alpha-room"
    assert settings.remembered_private_rooms[0].saved_password == "two"

    forget_private_room(settings, server_uri="wss://example.com", room_id="alpha-room")

    assert settings.remembered_private_rooms == []


def test_uri_and_host_sanitizers_have_safe_fallbacks() -> None:
    assert sanitize_server_uri("https://example.com") == DEFAULT_RELAY_URI
    assert sanitize_server_uri("wss://example.com/ws") == "wss://example.com/ws"
    assert sanitize_host("bad host!") == "0.0.0.0"
    assert sanitize_host("127.0.0.1") == "127.0.0.1"



def test_remembered_private_rooms_are_sanitized_deduped_sorted_and_limited() -> None:
    raw_rooms = []
    for index in range(MAX_REMEMBERED_PRIVATE_ROOMS + 5):
        raw_rooms.append(
            {
                "server_uri": "ws://localhost:8765" if index % 2 == 0 else "wss://example.com/ws",
                "room_id": f"Room {index}",
                "display_name": f" Display\nName {index} ",
                "saved_password": f"pw\n{index}",
                "last_used_ts": float(index),
            }
        )

    raw_rooms.extend(
        [
            "not-a-room",
            {"room_id": "missing password", "saved_password": ""},
            {"room_id": "Room 54", "saved_password": "newer duplicate", "last_used_ts": 9999.0},
        ]
    )

    rooms = sanitize_remembered_private_rooms(raw_rooms)

    assert len(rooms) == MAX_REMEMBERED_PRIVATE_ROOMS
    assert rooms[0].room_id == "room-54"
    assert rooms[0].saved_password == "pw54"
    assert rooms[0].display_name == "Display Name 54"
    assert rooms[0].server_uri == DEFAULT_RELAY_URI
    assert all("\n" not in room.saved_password for room in rooms)
    assert rooms == sorted(rooms, key=lambda room: room.last_used_ts, reverse=True)


def test_settings_from_data_only_accepts_real_booleans_and_clamps_optional_output_device() -> None:
    settings = settings_from_data(
        {
            "playback_enabled": "false",
            "transmit_enabled": 0,
            "remember_password": "true",
            "saved_password": "should-not-survive",
            "output_device": 999999,
        }
    )

    assert settings.playback_enabled is True
    assert settings.transmit_enabled is True
    assert settings.remember_password is False
    assert settings.saved_password == ""
    assert settings.output_device == 10_000

    empty_device = settings_from_data({"output_device": ""})
    assert empty_device.output_device is None


def test_save_network_settings_preserves_remembered_room_passwords_but_strips_legacy_password(tmp_path) -> None:
    path = tmp_path / "settings.json"
    settings = NetworkClientSettings(
        remember_password=False,
        saved_password="legacy-secret",
        remembered_private_rooms=[
            RememberedPrivateRoom(
                server_uri="wss://example.com",
                room_id="private-room",
                display_name="Private Room",
                saved_password="room-secret",
                last_used_ts=10.0,
            )
        ],
    )

    save_network_settings(settings, path)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["saved_password"] == ""
    assert data["remembered_private_rooms"][0]["saved_password"] == "room-secret"


def test_remember_private_room_skips_empty_password_and_keeps_existing_rooms() -> None:
    settings = NetworkClientSettings(
        remembered_private_rooms=[
            RememberedPrivateRoom(
                server_uri="wss://example.com",
                room_id="alpha",
                display_name="Alpha",
                saved_password="pw",
                last_used_ts=1.0,
            )
        ]
    )

    remember_private_room(settings, server_uri="wss://example.com", room_name="Beta", password="")

    assert len(settings.remembered_private_rooms) == 1
    assert settings.remembered_private_rooms[0].room_id == "alpha"


def test_remember_private_room_empty_room_name_uses_default_room_id() -> None:
    settings = NetworkClientSettings()

    remember_private_room(settings, server_uri="wss://example.com", room_name="", password="pw")

    assert len(settings.remembered_private_rooms) == 1
    assert settings.remembered_private_rooms[0].room_id == "default"
    assert settings.last_room == "default"


def test_forget_private_room_is_case_insensitive_for_server_uri_and_safe_for_missing_room() -> None:
    settings = NetworkClientSettings()
    remember_private_room(settings, server_uri="WSS://EXAMPLE.COM/ws", room_name="Alpha", password="pw")

    forget_private_room(settings, server_uri="wss://example.com/ws", room_id="missing")
    assert len(settings.remembered_private_rooms) == 1

    forget_private_room(settings, server_uri="wss://example.com/ws", room_id="Alpha")
    assert settings.remembered_private_rooms == []
