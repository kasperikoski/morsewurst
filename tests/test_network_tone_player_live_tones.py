from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")

from morsewurst.network.tone_player import TonePlayer


def _make_player() -> TonePlayer:
    player = TonePlayer(
        frequency_hz=700.0,
        volume=0.5,
        waveform="sine",
        sample_rate=48_000,
        channels=1,
        blocksize=512,
        attack_seconds=0.0005,
        release_seconds=0.002,
    )
    # Avoid opening a real audio device. _audio_callback can be exercised directly.
    player._started = True
    player._audio_clock_start_monotonic = 100.0
    player._frames_rendered = 0
    return player


def test_live_v1_key_tone_is_rendered_without_completed_duration() -> None:
    player = _make_player()

    player.start_live_tone(
        key="remote:straight",
        start_monotonic=100.0,
        frequency_hz=800.0,
        volume=0.5,
        waveform="sine",
    )

    out = np.zeros(512, dtype=np.float32)
    player._audio_callback(out, 512, None, None)

    assert float(np.max(np.abs(out))) > 0.01


def test_live_v1_key_tone_stops_and_is_cleaned_after_release() -> None:
    player = _make_player()

    player.start_live_tone(
        key="remote:straight",
        start_monotonic=100.0,
        frequency_hz=800.0,
        volume=0.5,
        waveform="sine",
    )
    player.stop_live_tone(key="remote:straight", end_monotonic=100.005)

    # Jump well past the release tail and cleanup grace.
    player._frames_rendered = int(0.5 * player.sample_rate)

    out = np.zeros(512, dtype=np.float32)
    player._audio_callback(out, 512, None, None)

    assert "remote:straight" not in player._live_tones
