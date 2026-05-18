# ============================================================
# morsewurst/network/models.py
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field

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
