from __future__ import annotations

import time

import pytest

from morsewurst.network.tone_player import TonePlayer, np


def test_radio_noise_ducking_uses_attack_hold_and_release_durations() -> None:
    if np is None:
        pytest.skip("numpy is required for TonePlayer block rendering")

    player = TonePlayer(sample_rate=1_000, blocksize=64)
    player.configure_background_noise(
        enabled=True,
        volume=0.05,
        profile="radio",
        tx_ducking_enabled=True,
        tx_ducking_depth_percent=90,
        tx_ducking_attack_ms=10,
        tx_ducking_hold_ms=20,
        tx_ducking_release_ms=500,
        rx_ducking_enabled=False,
    )

    with player._lock:
        player._radio_noise_target_gain = 1.0
        player._radio_noise_gain = 1.0
        player._radio_noise_duck_gain = 1.0

    start = time.monotonic()
    player.duck_noise(kind="tx", start_monotonic=start, duration_seconds=0.05)

    attack_times = start + (np.arange(30, dtype=np.float64) / float(player.sample_rate))
    player._render_radio_noise_block(attack_times)

    with player._lock:
        after_attack = player._radio_noise_duck_gain

    assert after_attack < 0.35

    early_release_times = start + 0.09 + (np.arange(100, dtype=np.float64) / float(player.sample_rate))
    player._render_radio_noise_block(early_release_times)

    with player._lock:
        during_release = player._radio_noise_duck_gain

    assert during_release < 0.75


def test_radio_noise_ducking_values_are_clamped_to_ui_ranges() -> None:
    player = TonePlayer(sample_rate=1_000, blocksize=64)
    player.configure_background_noise(
        enabled=True,
        volume=0.05,
        profile="radio",
        tx_ducking_enabled=True,
        tx_ducking_depth_percent=200,
        tx_ducking_attack_ms=999,
        tx_ducking_hold_ms=0,
        tx_ducking_release_ms=9999,
        rx_ducking_enabled=True,
        rx_ducking_depth_percent=200,
        rx_ducking_attack_ms=999,
        rx_ducking_hold_ms=0,
        rx_ducking_release_ms=9999,
    )

    assert player._radio_noise_tx_ducking_depth_percent == pytest.approx(95)
    assert player._radio_noise_tx_ducking_attack_ms == pytest.approx(500)
    assert player._radio_noise_tx_ducking_hold_ms == pytest.approx(1)
    assert player._radio_noise_tx_ducking_release_ms == pytest.approx(2000)

    assert player._radio_noise_rx_ducking_depth_percent == pytest.approx(95)
    assert player._radio_noise_rx_ducking_attack_ms == pytest.approx(500)
    assert player._radio_noise_rx_ducking_hold_ms == pytest.approx(1)
    assert player._radio_noise_rx_ducking_release_ms == pytest.approx(2000)
