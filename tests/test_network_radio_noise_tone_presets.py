from __future__ import annotations

from types import SimpleNamespace

import morsewurst.config as config
from morsewurst.network.models import PlaybackSettings
from morsewurst.network.settings_store import (
    NetworkClientSettings,
    sanitize_radio_noise_tone,
    settings_from_data,
)
from morsewurst.network.tone_player import TonePlayer
from morsewurst.ui.network.views.callsign_view import CallsignViewMixin


def test_radio_noise_tone_is_sanitized_and_persisted() -> None:
    settings = settings_from_data({"radio_noise_tone": "deep"})

    assert settings.radio_noise_tone == "deep"
    assert sanitize_radio_noise_tone("normal") == "normal"
    assert sanitize_radio_noise_tone("low") == "low"
    assert sanitize_radio_noise_tone("deep") == "deep"
    assert sanitize_radio_noise_tone("nonsense") == getattr(config, "NETWORK_RADIO_NOISE_TONE_DEFAULT", "low")


def test_playback_settings_has_radio_noise_tone_default() -> None:
    settings = PlaybackSettings()

    assert settings.radio_noise_tone in {"normal", "low", "deep"}


def test_tone_player_uses_different_filters_for_noise_tone_presets() -> None:
    player = TonePlayer()

    player.configure_background_noise(enabled=True, volume=0.05, profile="radio", tone="normal")
    normal = player._radio_noise_settings_for_profile("radio")

    player.configure_background_noise(enabled=True, volume=0.05, profile="radio", tone="low")
    low = player._radio_noise_settings_for_profile("radio")

    player.configure_background_noise(enabled=True, volume=0.05, profile="radio", tone="deep")
    deep = player._radio_noise_settings_for_profile("radio")

    assert normal.low_pass_hz > low.low_pass_hz > deep.low_pass_hz
    assert normal.high_pass_hz > low.high_pass_hz > deep.high_pass_hz


def test_existing_settings_file_does_not_force_first_callsign_prompt() -> None:
    view = CallsignViewMixin()
    view.settings_file_exists = True
    view.settings = SimpleNamespace(callsign="Morsewurst")

    assert view._needs_first_callsign() is False
