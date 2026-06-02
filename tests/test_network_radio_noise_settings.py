from __future__ import annotations

import pytest

from morsewurst.network.models import PlaybackSettings
from morsewurst.network.settings_store import (
    NetworkClientSettings,
    settings_from_data,
    load_network_settings,
    save_network_settings,
)
from morsewurst.network.tone_player import TonePlayer


def test_network_radio_noise_profile_and_ducking_settings_round_trip(tmp_path) -> None:
    path = tmp_path / "network_settings.json"
    settings = NetworkClientSettings(
        radio_noise_enabled=True,
        radio_noise_volume=0.12,
        radio_noise_profile="dx",
        radio_noise_tx_ducking_enabled=True,
        radio_noise_tx_ducking_depth_percent=80,
        radio_noise_tx_ducking_attack_ms=25,
        radio_noise_tx_ducking_hold_ms=300,
        radio_noise_tx_ducking_release_ms=650,
        radio_noise_rx_ducking_enabled=True,
        radio_noise_rx_ducking_depth_percent=35,
        radio_noise_rx_ducking_attack_ms=90,
        radio_noise_rx_ducking_hold_ms=180,
        radio_noise_rx_ducking_release_ms=520,
    )

    save_network_settings(settings, path)
    loaded = load_network_settings(path)

    assert loaded.radio_noise_enabled is True
    assert loaded.radio_noise_volume == pytest.approx(0.12)
    assert loaded.radio_noise_profile == "dx"
    assert loaded.radio_noise_tx_ducking_enabled is True
    assert loaded.radio_noise_tx_ducking_depth_percent == 80
    assert loaded.radio_noise_tx_ducking_attack_ms == 25
    assert loaded.radio_noise_tx_ducking_hold_ms == 300
    assert loaded.radio_noise_tx_ducking_release_ms == 650
    assert loaded.radio_noise_rx_ducking_enabled is True
    assert loaded.radio_noise_rx_ducking_depth_percent == 35
    assert loaded.radio_noise_rx_ducking_attack_ms == 90
    assert loaded.radio_noise_rx_ducking_hold_ms == 180
    assert loaded.radio_noise_rx_ducking_release_ms == 520


def test_network_radio_noise_settings_are_sanitized() -> None:
    settings = settings_from_data(
        {
            "radio_noise_enabled": True,
            "radio_noise_volume": 99,
            "radio_noise_profile": "invalid",
            "radio_noise_tx_ducking_enabled": True,
            "radio_noise_tx_ducking_depth_percent": 999,
            "radio_noise_tx_ducking_attack_ms": -1,
            "radio_noise_tx_ducking_hold_ms": -10,
            "radio_noise_tx_ducking_release_ms": 99999,
            "radio_noise_rx_ducking_enabled": True,
            "radio_noise_rx_ducking_depth_percent": -5,
            "radio_noise_rx_ducking_attack_ms": 99999,
            "radio_noise_rx_ducking_hold_ms": 99999,
            "radio_noise_rx_ducking_release_ms": 0,
        }
    )

    assert settings.radio_noise_volume == pytest.approx(0.30)
    assert settings.radio_noise_profile == "radio"
    assert settings.radio_noise_tx_ducking_depth_percent == 95
    assert settings.radio_noise_tx_ducking_attack_ms == 1
    assert settings.radio_noise_tx_ducking_hold_ms == 0
    assert settings.radio_noise_tx_ducking_release_ms == 5000
    assert settings.radio_noise_rx_ducking_depth_percent == 0
    assert settings.radio_noise_rx_ducking_attack_ms == 5000
    assert settings.radio_noise_rx_ducking_hold_ms == 5000
    assert settings.radio_noise_rx_ducking_release_ms == 1


def test_playback_settings_carries_user_adjustable_radio_noise_values() -> None:
    playback = PlaybackSettings(
        radio_noise_enabled=True,
        radio_noise_volume=0.08,
        radio_noise_profile="light",
        radio_noise_tx_ducking_enabled=True,
        radio_noise_tx_ducking_depth_percent=75,
        radio_noise_tx_ducking_attack_ms=30,
        radio_noise_tx_ducking_hold_ms=260,
        radio_noise_tx_ducking_release_ms=700,
        radio_noise_rx_ducking_enabled=False,
        radio_noise_rx_ducking_depth_percent=40,
        radio_noise_rx_ducking_attack_ms=70,
        radio_noise_rx_ducking_hold_ms=200,
        radio_noise_rx_ducking_release_ms=480,
    )

    assert playback.radio_noise_profile == "light"
    assert playback.radio_noise_tx_ducking_depth_percent == 75
    assert playback.radio_noise_tx_ducking_attack_ms == 30
    assert playback.radio_noise_tx_ducking_hold_ms == 260
    assert playback.radio_noise_tx_ducking_release_ms == 700
    assert playback.radio_noise_rx_ducking_enabled is False
    assert playback.radio_noise_rx_ducking_depth_percent == 40


def test_tone_player_uses_runtime_ducking_values() -> None:
    player = TonePlayer(sample_rate=8_000, blocksize=64)
    player.configure_background_noise(
        enabled=True,
        volume=0.05,
        profile="dx",
        tx_ducking_enabled=True,
        tx_ducking_depth_percent=72,
        tx_ducking_attack_ms=33,
        tx_ducking_hold_ms=222,
        tx_ducking_release_ms=777,
        rx_ducking_enabled=True,
        rx_ducking_depth_percent=31,
        rx_ducking_attack_ms=44,
        rx_ducking_hold_ms=155,
        rx_ducking_release_ms=666,
    )

    assert player._radio_noise_profile == "dx"
    assert player._radio_noise_duck_config("tx", "depth_percent") == pytest.approx(72.0)
    assert player._radio_noise_duck_config("tx", "attack_ms") == pytest.approx(33.0)
    assert player._radio_noise_duck_config("tx", "hold_ms") == pytest.approx(222.0)
    assert player._radio_noise_duck_config("tx", "release_ms") == pytest.approx(777.0)
    assert player._radio_noise_duck_config("rx", "depth_percent") == pytest.approx(31.0)
    assert player._radio_noise_duck_config("rx", "attack_ms") == pytest.approx(44.0)
    assert player._radio_noise_duck_config("rx", "hold_ms") == pytest.approx(155.0)
    assert player._radio_noise_duck_config("rx", "release_ms") == pytest.approx(666.0)
