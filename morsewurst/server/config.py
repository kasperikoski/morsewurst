# ============================================================
# morsewurst/server/config.py
# ============================================================

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover, Python < 3.11 only
    import tomli as tomllib  # type: ignore[no-redef]

from morsewurst.network.protocol import normalize_room_id
from morsewurst.server.models import (
    ConfigError,
    PrivateRoomsSection,
    RelayServerConfig,
    ReservedNamesSection,
    RoomDefinition,
    ServerInfoSection,
    ServerSection,
    UserRegistrySection,
    ROOM_ACCESS_PRIVATE,
    ROOM_ACCESS_PUBLIC,
    ROOM_ACCESS_VALUES,
)


def load_relay_config(path: str | Path) -> RelayServerConfig:
    target = Path(path)
    try:
        raw = tomllib.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {target}") from exc
    except Exception as exc:
        raise ConfigError(f"Config file could not be read: {target}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Config root must be a TOML table.")

    config = RelayServerConfig(
        server=_parse_server(raw.get("server", {})),
        private_rooms=_parse_private_rooms(raw.get("private_rooms", {})),
        server_info=_parse_server_info(raw.get("server_info", {})),
        user_registry=_parse_user_registry(raw.get("user_registry", {})),
        reserved_names=_parse_reserved_names(raw.get("reserved_names", {})),
        rooms=_parse_rooms(raw.get("rooms", [])),
    )
    validate_config(config)
    return config


def _parse_server(data: Any) -> ServerSection:
    data = data if isinstance(data, dict) else {}
    return ServerSection(
        host=_safe_str(data.get("host"), "0.0.0.0", 253),
        port=_safe_int(data.get("port"), 8765, 1, 65535),
        server_name=_safe_str(data.get("server_name"), "Morsewurst Relay", 80),
        log_level=_safe_str(data.get("log_level"), "INFO", 16).upper(),
    )


def _parse_private_rooms(data: Any) -> PrivateRoomsSection:
    data = data if isinstance(data, dict) else {}
    return PrivateRoomsSection(
        enabled=_safe_bool(data.get("enabled"), True),
        ttl_minutes=_safe_int(data.get("ttl_minutes"), 30 * 24 * 60, 1, 365 * 24 * 60),
        max_clients=_safe_int(data.get("max_clients"), 10, 1, 500),
        min_name_length=_safe_int(data.get("min_name_length"), 1, 1, 64),
        max_name_length=_safe_int(data.get("max_name_length"), 64, 1, 64),
        require_password=_safe_bool(data.get("require_password"), True),
        storage_path=_safe_str(data.get("storage_path"), "data/private_rooms.json", 512),
    )


def _parse_server_info(data: Any) -> ServerInfoSection:
    data = data if isinstance(data, dict) else {}
    return ServerInfoSection(
        enabled=_safe_bool(data.get("enabled"), True),
        interval_seconds=_safe_int(data.get("interval_seconds"), 30, 5, 3600),
        allow_requests=_safe_bool(data.get("allow_requests"), True),
    )


def _parse_user_registry(data: Any) -> UserRegistrySection:
    data = data if isinstance(data, dict) else {}
    return UserRegistrySection(
        enabled=_safe_bool(data.get("enabled"), True),
        storage_path=_safe_str(data.get("storage_path"), "data/users.json", 512),
    )


def _parse_reserved_names(data: Any) -> ReservedNamesSection:
    data = data if isinstance(data, dict) else {}
    exact = data.get("exact", [])
    patterns = data.get("patterns", [])
    return ReservedNamesSection(
        exact=[_safe_str(item, "", 64) for item in exact if _safe_str(item, "", 64)],
        patterns=[_safe_str(item, "", 200) for item in patterns if _safe_str(item, "", 200)],
    )


def _parse_rooms(data: Any) -> list[RoomDefinition]:
    if data is None:
        return []
    if not isinstance(data, list):
        raise ConfigError("[[rooms]] must be an array of room tables.")

    rooms: list[RoomDefinition] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"Room #{index} must be a TOML table.")

        raw_id = _safe_str(item.get("id"), "", 64)
        room_id = normalize_room_id(raw_id)
        if not room_id:
            raise ConfigError(f"Room #{index} has an invalid id.")

        access = _safe_str(item.get("access"), ROOM_ACCESS_PUBLIC, 16).lower()
        if access not in ROOM_ACCESS_VALUES:
            raise ConfigError(f"Room '{room_id}' has invalid access '{access}'. Use 'public' or 'private'.")

        name = _safe_str(item.get("name"), raw_id or room_id, 80)
        description = _safe_str(item.get("description"), "", 200)
        password = _safe_str(item.get("password"), "", 256)

        if access == ROOM_ACCESS_PUBLIC and password:
            raise ConfigError(f"Public room '{room_id}' must not define a password. Use access = 'private' for protected rooms.")

        if access == ROOM_ACCESS_PRIVATE and password == "":
            raise ConfigError(f"Private configured room '{room_id}' must have a password.")

        rooms.append(
            RoomDefinition(
                id=room_id,
                name=name or room_id,
                description=description,
                access=access,
                password=password,
                listed=_safe_bool(item.get("listed"), True),
                persistent=_safe_bool(item.get("persistent"), True),
                max_clients=_safe_int(item.get("max_clients"), 20, 1, 500),
            )
        )
    return rooms


def validate_config(config: RelayServerConfig) -> None:
    seen: dict[str, str] = {}
    for room in config.rooms:
        room_id = normalize_room_id(room.id)
        if room_id in seen:
            raise ConfigError(f"Duplicate configured room id '{room_id}'.")
        seen[room_id] = room.name

        if room.access not in ROOM_ACCESS_VALUES:
            raise ConfigError(f"Room '{room_id}' has invalid access '{room.access}'.")
        if room.access == ROOM_ACCESS_PUBLIC and room.password:
            raise ConfigError(f"Public room '{room_id}' must not define a password.")
        if room.access == ROOM_ACCESS_PRIVATE and not room.password:
            raise ConfigError(f"Private room '{room_id}' must define a password.")

    if config.private_rooms.min_name_length > config.private_rooms.max_name_length:
        raise ConfigError("private_rooms.min_name_length cannot exceed max_name_length.")


def _safe_str(value: Any, default: str, maximum: int) -> str:
    if value is None:
        value = default
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return text[:maximum]


def _safe_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        number = int(value)
    except Exception:
        number = default
    return max(minimum, min(maximum, number))
