# ============================================================
# morsewurst/network/models.py
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field

import morsewurst.config as config
from morsewurst.network.defaults import DEFAULT_RELAY_URI


@dataclass(slots=True)
class PlaybackSettings:
    enabled: bool = True
    jitter_buffer_ms: int = 750
    frequency_hz: float = 650.0
    volume: float = 0.12
    waveform: str = "sine"
    output_device: int | None = None
    sample_rate: int = 44_100
    blocksize: int = 2048
    latency: str = "high"
    radio_noise_enabled: bool = bool(getattr(config, "NETWORK_RADIO_NOISE_ENABLED_DEFAULT", False))
    radio_noise_volume: float = float(getattr(config, "NETWORK_RADIO_NOISE_VOLUME_PERCENT_DEFAULT", 5)) / 100.0
    radio_noise_profile: str = str(getattr(config, "NETWORK_RADIO_NOISE_PROFILE_DEFAULT", "radio"))
    radio_noise_tone: str = str(getattr(config, "NETWORK_RADIO_NOISE_TONE_DEFAULT", "low"))
    radio_noise_tx_ducking_enabled: bool = bool(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_ENABLED", True))
    radio_noise_tx_ducking_depth_percent: int = int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_DEPTH_PERCENT", 85))
    radio_noise_tx_ducking_attack_ms: int = int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_ATTACK_MS", 60))
    radio_noise_tx_ducking_hold_ms: int = int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_HOLD_MS", 350))
    radio_noise_tx_ducking_release_ms: int = int(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_RELEASE_MS", 500))
    radio_noise_rx_ducking_enabled: bool = bool(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_ENABLED", False))
    radio_noise_rx_ducking_depth_percent: int = int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_DEPTH_PERCENT", 45))
    radio_noise_rx_ducking_attack_ms: int = int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_ATTACK_MS", 80))
    radio_noise_rx_ducking_hold_ms: int = int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_HOLD_MS", 250))
    radio_noise_rx_ducking_release_ms: int = int(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_RELEASE_MS", 450))


@dataclass(slots=True)
class NetworkSettings:
    callsign: str = "Morsewurst"
    installation_id: str = ""
    room: str = "default"
    password: str = ""
    host: str = "0.0.0.0"
    port: int = 8765
    server_uri: str = DEFAULT_RELAY_URI
    transmit_enabled: bool = True
    playback: PlaybackSettings = field(default_factory=PlaybackSettings)

    # Optional TLS support. Leave empty for normal ws:// testing.
    # For real public internet, prefer WSS through a proper reverse proxy or use VPN.
    tls_certfile: str = ""
    tls_keyfile: str = ""
    tls_cafile: str = ""
