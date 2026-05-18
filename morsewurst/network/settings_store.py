# ============================================================
# morsewurst/network/settings_store.py
# ============================================================

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import morsewurst.config as config
from morsewurst.network.protocol import (
    new_installation_id,
    normalize_callsign,
    normalize_room_id,
    sanitize_installation_id,
)

from morsewurst.network.defaults import DEFAULT_RELAY_URI

DEFAULT_NETWORK_SETTINGS_FILENAME = "network_settings.json"
MAX_REMEMBERED_PRIVATE_ROOMS = 50


@dataclass(slots=True)
class RememberedPrivateRoom:
    server_uri: str = DEFAULT_RELAY_URI
    room_id: str = ""
    display_name: str = ""
    saved_password: str = ""
    last_used_ts: float = 0.0

    @property
    def display_label(self) -> str:
        name = self.display_name or self.room_id
        return f"{name} · {self.server_uri}"


@dataclass(slots=True)
class NetworkClientSettings:
    callsign: str = "Morsewurst"
    installation_id: str = field(default_factory=new_installation_id)
    last_server_uri: str = DEFAULT_RELAY_URI
    last_room: str = "default"
    last_host: str = "0.0.0.0"
    last_port: int = 8765
    playback_enabled: bool = True
    transmit_enabled: bool = True
    jitter_buffer_ms: int = 750
    frequency_hz: float = 650.0
    volume: float = 1.0
    waveform: str = "sine"
    output_device: int | None = None
    sample_rate: int = 44_100
    blocksize: int = 2048
    latency: str = "high"
    remember_password: bool = False
    saved_password: str = ""
    remembered_private_rooms: list[RememberedPrivateRoom] = field(default_factory=list)


def network_settings_path() -> Path:
    return config.DATA_DIR / DEFAULT_NETWORK_SETTINGS_FILENAME


def load_network_settings(path: Path | None = None) -> NetworkClientSettings:
    target = path or network_settings_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return settings_from_data({})

    if not isinstance(data, dict):
        return settings_from_data({})

    return settings_from_data(data)


def save_network_settings(settings: NetworkClientSettings, path: Path | None = None) -> Path:
    target = path or network_settings_path()
    safe = settings_from_data(asdict(settings))

    # This old single-password option remains opt-in.
    # Remembered private rooms intentionally keep their own saved_password values.
    if not safe.remember_password:
        safe.saved_password = ""

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(asdict(safe), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)
    return target


def settings_from_data(data: dict[str, Any]) -> NetworkClientSettings:
    remembered = _safe_bool(data.get("remember_password"), False)

    installation_id = sanitize_installation_id(data.get("installation_id"))
    if not installation_id:
        installation_id = new_installation_id()

    return NetworkClientSettings(
        callsign=sanitize_callsign(data.get("callsign") or data.get("nickname")),
        installation_id=installation_id,
        last_server_uri=sanitize_server_uri(data.get("last_server_uri")),
        last_room=sanitize_room_name(data.get("last_room")),
        last_host=sanitize_host(data.get("last_host")),
        last_port=_safe_int(data.get("last_port"), 8765, 1, 65535),
        playback_enabled=_safe_bool(data.get("playback_enabled"), True),
        transmit_enabled=_safe_bool(data.get("transmit_enabled"), True),
        jitter_buffer_ms=_safe_int(data.get("jitter_buffer_ms"), 750, 0, 10_000),
        frequency_hz=_safe_float(data.get("frequency_hz"), 650.0, 80.0, 2400.0),
        volume=_safe_float(data.get("volume"), 1.0, 0.0, 1.0),
        waveform=sanitize_waveform(data.get("waveform")),
        output_device=_safe_optional_int(data.get("output_device"), None, -1, 10_000),
        sample_rate=_safe_int(data.get("sample_rate"), 44_100, 8_000, 192_000),
        blocksize=_safe_int(data.get("blocksize"), 2048, 64, 16_384),
        latency=sanitize_latency(data.get("latency")),
        remember_password=remembered,
        saved_password=sanitize_password_for_storage(data.get("saved_password")) if remembered else "",
        remembered_private_rooms=sanitize_remembered_private_rooms(data.get("remembered_private_rooms")),
    )


def remember_private_room(
    settings: NetworkClientSettings,
    *,
    server_uri: object,
    room_name: object,
    password: object,
) -> NetworkClientSettings:
    clean_server_uri = sanitize_server_uri(server_uri)
    room_id = sanitize_room_name(room_name)
    display_name = sanitize_room_display_name(room_name)
    saved_password = sanitize_password_for_storage(password)

    if not room_id or not saved_password:
        return settings

    new_room = RememberedPrivateRoom(
        server_uri=clean_server_uri,
        room_id=room_id,
        display_name=display_name or room_id,
        saved_password=saved_password,
        last_used_ts=time.time(),
    )

    existing = [
        room for room in settings.remembered_private_rooms
        if not (
            room.server_uri.lower() == clean_server_uri.lower()
            and room.room_id == room_id
        )
    ]

    settings.remembered_private_rooms = [new_room, *existing][:MAX_REMEMBERED_PRIVATE_ROOMS]
    settings.last_server_uri = clean_server_uri
    settings.last_room = room_id
    return settings


def forget_private_room(
    settings: NetworkClientSettings,
    *,
    server_uri: object,
    room_id: object,
) -> NetworkClientSettings:
    clean_server_uri = sanitize_server_uri(server_uri)
    clean_room_id = sanitize_room_name(room_id)

    settings.remembered_private_rooms = [
        room for room in settings.remembered_private_rooms
        if not (
            room.server_uri.lower() == clean_server_uri.lower()
            and room.room_id == clean_room_id
        )
    ]

    return settings


def sanitize_remembered_private_rooms(value: object) -> list[RememberedPrivateRoom]:
    if not isinstance(value, list):
        return []

    rooms: list[RememberedPrivateRoom] = []
    seen: set[tuple[str, str]] = set()

    for item in value:
        if not isinstance(item, dict):
            continue

        server_uri = sanitize_server_uri(item.get("server_uri"))
        room_id = sanitize_room_name(item.get("room_id") or item.get("id") or item.get("room"))
        display_name = sanitize_room_display_name(item.get("display_name") or room_id)
        saved_password = sanitize_password_for_storage(item.get("saved_password") or item.get("password"))

        if not room_id or not saved_password:
            continue

        key = (server_uri.lower(), room_id)
        if key in seen:
            continue
        seen.add(key)

        rooms.append(
            RememberedPrivateRoom(
                server_uri=server_uri,
                room_id=room_id,
                display_name=display_name or room_id,
                saved_password=saved_password,
                last_used_ts=_safe_float(item.get("last_used_ts"), 0.0, 0.0, 99_999_999_999.0),
            )
        )

    rooms.sort(key=lambda room: room.last_used_ts, reverse=True)
    return rooms[:MAX_REMEMBERED_PRIVATE_ROOMS]


def sanitize_callsign(value: object) -> str:
    return normalize_callsign(value)


def sanitize_room_name(value: object) -> str:
    return normalize_room_id(value)


def sanitize_room_display_name(value: object) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    text = "".join(ch for ch in text if ch.isprintable())
    return text[:80].strip()


def sanitize_server_uri(value: object) -> str:
    text = str(value or "").strip()[:256]
    text = text.replace("\r", "").replace("\n", "")

    legacy_local_uris = {
        "",
        "ws://127.0.0.1:8765",
        "ws://localhost:8765",
        "ws://0.0.0.0:8765",
        "ws://morsewurst.duckdns.org:8765",
        "ws://morsewurst.duckdns.org",
    }

    if text.lower() in legacy_local_uris:
        return DEFAULT_RELAY_URI

    parsed = urlparse(text)
    if parsed.scheme not in {"ws", "wss"}:
        return DEFAULT_RELAY_URI
    if not parsed.hostname:
        return DEFAULT_RELAY_URI
    if parsed.port is not None and not (1 <= int(parsed.port) <= 65535):
        return DEFAULT_RELAY_URI

    return text


def sanitize_host(value: object) -> str:
    text = str(value or "0.0.0.0").strip()[:253]
    text = text.replace("\r", "").replace("\n", "")
    if not text:
        return "0.0.0.0"
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", text):
        return "0.0.0.0"
    return text


def sanitize_waveform(value: object) -> str:
    text = str(value or "sine").strip().lower()
    return text if text in {"sine", "square", "triangle", "saw"} else "sine"


def sanitize_latency(value: object) -> str:
    text = str(value or "high").strip().lower()[:16]
    return text if text in {"low", "high", "medium"} else "high"


def sanitize_password_for_storage(value: object) -> str:
    text = str(value or "")[:256]
    return text.replace("\r", "").replace("\n", "")


def _safe_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _safe_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        number = int(value)
    except Exception:
        number = default
    return max(minimum, min(maximum, number))


def _safe_optional_int(value: object, default: int | None, minimum: int, maximum: int) -> int | None:
    if value is None or value == "":
        return default
    return _safe_int(value, default if default is not None else minimum, minimum, maximum)


def _safe_float(value: object, default: float, minimum: float, maximum: float) -> float:
    try:
        if isinstance(value, bool):
            raise ValueError
        number = float(str(value).replace(",", "."))
    except Exception:
        number = default
    return max(minimum, min(maximum, number))