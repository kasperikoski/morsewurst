from __future__ import annotations

import time

import pytest

from morsewurst.audio.noise import RadioNoiseGenerator, RadioNoiseSettings
from morsewurst.network.models import PlaybackSettings
from morsewurst.network.settings_store import NetworkClientSettings, load_network_settings, save_network_settings, settings_from_data
from morsewurst.network.tone_player import TonePlayer, np


def test_continuous_radio_noise_generator_works_without_total_samples() -> None:
    generator = RadioNoiseGenerator(
        sample_rate=8_000,
        total_samples=0,
        settings=RadioNoiseSettings(
            enabled=True,
            continuous=True,
            volume_percent=5,
            flutter_percent=10,
            drift_percent=10,
            burst_chance_per_second=1.0,
            crackle_chance_per_second=1.0,
            dropout_chance_per_second=0.5,
            seed=123,
        ),
    )

    samples = [generator.sample(index) for index in range(512)]

    assert generator.enabled is True
    assert any(sample != 0 for sample in samples)
    assert all(-32768 <= sample <= 32767 for sample in samples)


def test_network_settings_persist_radio_noise_fields(tmp_path) -> None:
    path = tmp_path / "network_settings.json"
    settings = NetworkClientSettings(
        radio_noise_enabled=True,
        radio_noise_volume=0.11,
        radio_noise_profile="dx",
        radio_noise_tx_ducking_enabled=False,
        radio_noise_rx_ducking_enabled=True,
    )

    save_network_settings(settings, path)
    loaded = load_network_settings(path)

    assert loaded.radio_noise_enabled is True
    assert loaded.radio_noise_volume == pytest.approx(0.11)
    assert loaded.radio_noise_profile == "dx"
    assert loaded.radio_noise_tx_ducking_enabled is False
    assert loaded.radio_noise_rx_ducking_enabled is True


def test_settings_from_data_sanitizes_radio_noise_fields() -> None:
    settings = settings_from_data(
        {
            "radio_noise_enabled": True,
            "radio_noise_volume": 99,
            "radio_noise_profile": "invalid",
            "radio_noise_tx_ducking_enabled": "false",
            "radio_noise_rx_ducking_enabled": False,
        }
    )

    assert settings.radio_noise_enabled is True
    assert settings.radio_noise_volume == pytest.approx(0.30)
    assert settings.radio_noise_profile == "radio"
    # Only real booleans are accepted by the settings store.
    assert settings.radio_noise_tx_ducking_enabled is True
    assert settings.radio_noise_rx_ducking_enabled is False


def test_playback_settings_carries_radio_noise_values() -> None:
    playback = PlaybackSettings(
        radio_noise_enabled=True,
        radio_noise_volume=0.07,
        radio_noise_profile="light",
        radio_noise_tx_ducking_enabled=True,
        radio_noise_rx_ducking_enabled=False,
    )

    assert playback.radio_noise_enabled is True
    assert playback.radio_noise_volume == pytest.approx(0.07)
    assert playback.radio_noise_profile == "light"
    assert playback.radio_noise_tx_ducking_enabled is True
    assert playback.radio_noise_rx_ducking_enabled is False


def test_tone_player_can_render_local_radio_noise_block_without_audio_device() -> None:
    if np is None:
        pytest.skip("numpy is required for TonePlayer block rendering")

    player = TonePlayer(sample_rate=8_000, blocksize=64)
    player.configure_background_noise(
        enabled=True,
        volume=0.06,
        profile="radio",
        tx_ducking_enabled=True,
        rx_ducking_enabled=True,
    )

    with player._lock:  # The audio callback normally raises this target during room entry.
        player._radio_noise_target_gain = 1.0

    times = time.monotonic() + (np.arange(256, dtype=np.float64) / float(player.sample_rate))
    first = player._render_radio_noise_block(times)

    player.duck_noise(kind="tx", start_monotonic=float(times[0]), duration_seconds=0.2)
    second = player._render_radio_noise_block(times)

    assert first is not None
    assert second is not None
    assert first.shape == (256,)
    assert second.shape == (256,)
    assert float(abs(first).max()) <= 1.0
    assert float(abs(second).max()) <= 1.0
    assert player._radio_noise_ducks
