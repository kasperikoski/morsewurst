# ============================================================
# morsewurst/server/models.py
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field


ROOM_ACCESS_PUBLIC = "public"
ROOM_ACCESS_PRIVATE = "private"
ROOM_ACCESS_VALUES = {ROOM_ACCESS_PUBLIC, ROOM_ACCESS_PRIVATE}


@dataclass(slots=True)
class ServerSection:
    host: str = "0.0.0.0"
    port: int = 8765
    server_name: str = "Morsewurst Relay"
    log_level: str = "INFO"


@dataclass(slots=True)
class PrivateRoomsSection:
    enabled: bool = True
    ttl_minutes: int = 30 * 24 * 60
    max_clients: int = 10
    min_name_length: int = 1
    max_name_length: int = 64
    require_password: bool = True
    storage_path: str = "data/private_rooms.json"


@dataclass(slots=True)
class ServerInfoSection:
    enabled: bool = True
    interval_seconds: int = 30
    allow_requests: bool = True


@dataclass(slots=True)
class UserRegistrySection:
    enabled: bool = True
    storage_path: str = "data/users.json"


@dataclass(slots=True)
class ReservedNamesSection:
    exact: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RoomDefinition:
    id: str
    name: str
    description: str = ""
    access: str = ROOM_ACCESS_PUBLIC
    password: str = ""
    listed: bool = True
    persistent: bool = True
    max_clients: int = 20


@dataclass(slots=True)
class RelayServerConfig:
    server: ServerSection = field(default_factory=ServerSection)
    private_rooms: PrivateRoomsSection = field(default_factory=PrivateRoomsSection)
    server_info: ServerInfoSection = field(default_factory=ServerInfoSection)
    user_registry: UserRegistrySection = field(default_factory=UserRegistrySection)
    reserved_names: ReservedNamesSection = field(default_factory=ReservedNamesSection)
    rooms: list[RoomDefinition] = field(default_factory=list)


class ConfigError(ValueError):
    pass
