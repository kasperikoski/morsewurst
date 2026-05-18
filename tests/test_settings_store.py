from __future__ import annotations

import json

from morsewurst.network.defaults import DEFAULT_RELAY_URI
from morsewurst.network.settings_store import (
    NetworkClientSettings,
    RememberedPrivateRoom,
    forget_private_room,
    load_network_settings,
    remember_private_room,
    sanitize_host,
    sanitize_server_uri,
    save_network_settings,
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
