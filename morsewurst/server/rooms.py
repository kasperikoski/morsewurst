# ============================================================
# morsewurst/server/rooms.py
# ============================================================

from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from morsewurst.network.protocol import (
    is_valid_password_verifier,
    normalize_room_id,
    room_password_verifier,
)
from morsewurst.server.models import (
    ConfigError,
    RelayServerConfig,
    RoomDefinition,
    ROOM_ACCESS_PRIVATE,
    ROOM_ACCESS_PUBLIC,
)


ROOM_ID_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"


class RoomError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class ClientSession:
    client_id: str
    callsign: str
    websocket: Any
    room_key: str
    room_id: str = ""
    installation_id_hash: str = ""
    client_version: str = ""
    protocol_version: int = 0
    connected_at: float = field(default_factory=time.time)
    last_seen_at: float = field(default_factory=time.time)
    last_tone_at: float | None = None
    message_count: int = 0
    tone_count: int = 0


@dataclass(slots=True)
class RoomState:
    room_key: str
    name: str
    room_id: str = ""
    description: str = ""
    access: str = ROOM_ACCESS_PRIVATE
    password_verifier: str | None = None
    listed: bool = True
    persistent: bool = False
    max_clients: int = 20
    created_at: float = field(default_factory=time.time)
    empty_since: float | None = None
    clients: dict[Any, ClientSession] = field(default_factory=dict)

    @property
    def client_count(self) -> int:
        return len(self.clients)

    @property
    def auth_required(self) -> bool:
        return self.access != ROOM_ACCESS_PUBLIC


class RoomRegistry:
    def __init__(self, config: RelayServerConfig) -> None:
        self.config = config
        self.rooms: dict[str, RoomState] = {}
        self._reserved_exact = {normalize_room_id(name) for name in config.reserved_names.exact}
        self._reserved_patterns = self._compile_patterns(config.reserved_names.patterns)
        self._load_configured_rooms(config.rooms)
        self._load_persisted_private_rooms()

        if self.cleanup_expired_private_rooms():
            self.save_persisted_private_rooms()

    def _compile_patterns(self, patterns: list[str]) -> list[re.Pattern[str]]:
        compiled: list[re.Pattern[str]] = []
        for pattern in patterns:
            try:
                compiled.append(re.compile(pattern))
            except re.error as exc:
                raise ConfigError(f"Invalid reserved room name pattern '{pattern}': {exc}") from exc
        return compiled

    def _load_configured_rooms(self, definitions: list[RoomDefinition]) -> None:
        for definition in definitions:
            room_key = normalize_room_id(definition.id)
            if room_key in self.rooms:
                raise ConfigError(f"Duplicate configured room id '{room_key}'.")

            verifier = None
            if definition.access == ROOM_ACCESS_PRIVATE:
                verifier = room_password_verifier(password=definition.password, room=room_key)

            self.rooms[room_key] = RoomState(
                room_key=room_key,
                name=definition.name,
                room_id=_clean_room_id(definition.id) or room_key.upper(),
                description=definition.description,
                access=definition.access,
                password_verifier=verifier,
                listed=definition.listed,
                persistent=True,
                max_clients=definition.max_clients,
            )

    def private_room_storage_path(self) -> Path | None:
        raw = str(getattr(self.config.private_rooms, "storage_path", "") or "").strip()
        if not raw:
            return None
        return Path(raw).expanduser()

    def _load_persisted_private_rooms(self) -> None:
        path = self.private_room_storage_path()
        if path is None or not path.exists():
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return

        if not isinstance(data, dict):
            return

        if int(data.get("version") or 0) != 2:
            return

        items = data.get("rooms", [])
        if not isinstance(items, list):
            return

        now = time.time()
        used_room_ids: set[str] = {
            str(room.room_id or "").upper()
            for room in self.rooms.values()
            if str(room.room_id or "")
        }

        for item in items:
            if not isinstance(item, dict):
                continue

            room_key = normalize_room_id(item.get("room_key"))
            if not room_key:
                continue

            if room_key in self.rooms:
                continue

            if self.is_reserved_for_private_creation(room_key):
                continue

            room_id = _clean_room_id(item.get("room_id"))
            if not room_id:
                continue

            if room_id in used_room_ids:
                continue

            verifier = str(item.get("password_verifier") or "")
            if not is_valid_password_verifier(verifier):
                continue

            created_at = _safe_float(item.get("created_at"), now)
            empty_since = _safe_optional_float(item.get("empty_since"))

            if empty_since is None:
                empty_since = now

            self.rooms[room_key] = RoomState(
                room_key=room_key,
                name=_clean_display_name(item.get("name"), room_key),
                room_id=room_id,
                access=ROOM_ACCESS_PRIVATE,
                password_verifier=verifier,
                listed=False,
                persistent=False,
                max_clients=_safe_int(
                    item.get("max_clients"),
                    self.config.private_rooms.max_clients,
                    1,
                    500,
                ),
                created_at=created_at,
                empty_since=empty_since,
            )
            used_room_ids.add(room_id)

    def save_persisted_private_rooms(self) -> None:
        path = self.private_room_storage_path()
        if path is None:
            return

        rooms: list[dict[str, Any]] = []

        for room in self.rooms.values():
            if room.access != ROOM_ACCESS_PRIVATE:
                continue
            if room.persistent:
                continue
            if not room.password_verifier:
                continue

            rooms.append(
                {
                    "room_key": room.room_key,
                    "room_id": room.room_id,
                    "name": room.name,
                    "password_verifier": room.password_verifier,
                    "max_clients": room.max_clients,
                    "created_at": room.created_at,
                    "empty_since": room.empty_since,
                }
            )

        payload = {
            "version": 2,
            "saved_at": time.time(),
            "rooms": sorted(rooms, key=lambda item: str(item["room_key"])),
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def room_for_join(self, requested_room: object) -> tuple[str, RoomState | None, bool]:
        room_key = normalize_room_id(requested_room)
        self._validate_room_key(room_key)

        existing = self.rooms.get(room_key)
        if existing is not None:
            return room_key, existing, False

        if not self.config.private_rooms.enabled:
            raise RoomError("ROOM_NOT_FOUND", "Huonetta ei ole olemassa.")

        if self.is_reserved_for_private_creation(room_key):
            raise RoomError("ROOM_NAME_RESERVED", "Tämä huonenimi on varattu.")

        return room_key, None, True

    def create_private_room(
        self,
        *,
        room_key: str,
        password_verifier: str,
        display_name: str | None = None,
    ) -> RoomState:
        room_key = normalize_room_id(room_key)
        self._validate_room_key(room_key)

        if room_key in self.rooms:
            raise RoomError("ROOM_ALREADY_EXISTS", "Huone on jo olemassa.")

        if self.is_reserved_for_private_creation(room_key):
            raise RoomError("ROOM_NAME_RESERVED", "Tämä huonenimi on varattu.")

        if not is_valid_password_verifier(password_verifier):
            raise RoomError("INVALID_ROOM_PASSWORD", "Huoneen salasana ei kelpaa.")

        if self.config.private_rooms.require_password:
            empty_password_verifier = room_password_verifier(password="", room=room_key)
            if password_verifier == empty_password_verifier:
                raise RoomError("INVALID_ROOM_PASSWORD", "Yksityishuone tarvitsee salasanan.")

        clean_display_name = _clean_display_name(display_name, room_key)

        room = RoomState(
            room_key=room_key,
            name=clean_display_name,
            room_id=self._new_unique_room_id(),
            access=ROOM_ACCESS_PRIVATE,
            password_verifier=password_verifier,
            listed=False,
            persistent=False,
            max_clients=self.config.private_rooms.max_clients,
        )
        self.rooms[room_key] = room
        return room

    def _new_unique_room_id(self) -> str:
        existing = {
            str(room.room_id or "").upper()
            for room in self.rooms.values()
            if str(room.room_id or "")
        }

        for _ in range(100):
            room_id = _new_room_id()
            if room_id not in existing:
                return room_id

        raise RoomError("ROOM_ID_GENERATION_FAILED", "Room ID generation failed.")

    def is_reserved_for_private_creation(self, room_key: str) -> bool:
        normalized = normalize_room_id(room_key)
        if normalized in self._reserved_exact:
            return True
        return any(pattern.fullmatch(normalized) for pattern in self._reserved_patterns)

    def add_client(self, room: RoomState, session: ClientSession) -> None:
        if room.client_count >= room.max_clients:
            raise RoomError("ROOM_FULL", "Huone on täynnä.")
        room.clients[session.websocket] = session
        room.empty_since = None

    def remove_client(self, session: ClientSession) -> None:
        room = self.rooms.get(session.room_key)
        if room is None:
            return
        room.clients.pop(session.websocket, None)
        if room.client_count == 0:
            room.empty_since = time.time()

    def list_peers(self, room: RoomState) -> list[dict[str, Any]]:
        return [
            {"client_id": client.client_id, "callsign": client.callsign}
            for client in room.clients.values()
        ]

    def list_public_rooms(self) -> list[dict[str, Any]]:
        rooms: list[dict[str, Any]] = []

        for room in self.rooms.values():
            if room.access != ROOM_ACCESS_PUBLIC:
                continue
            if not room.listed:
                continue

            rooms.append(
                {
                    "id": room.room_key,
                    "name": room.name,
                    "description": room.description,
                    "access": room.access,
                    "listed": room.listed,
                    "client_count": room.client_count,
                    "max_clients": room.max_clients,
                }
            )

        return rooms

    def cleanup_expired_private_rooms(self) -> int:
        ttl_seconds = self.config.private_rooms.ttl_minutes * 60
        now = time.time()
        expired: list[str] = []

        for room_key, room in self.rooms.items():
            if room.persistent or room.client_count > 0 or room.empty_since is None:
                continue
            if now - room.empty_since >= ttl_seconds:
                expired.append(room_key)

        for room_key in expired:
            self.rooms.pop(room_key, None)

        return len(expired)

    def _validate_room_key(self, room_key: str) -> None:
        minimum = self.config.private_rooms.min_name_length
        maximum = self.config.private_rooms.max_name_length
        if len(room_key) < minimum:
            raise RoomError("INVALID_ROOM_NAME", "Huoneen nimi on liian lyhyt.")
        if len(room_key) > maximum:
            raise RoomError("INVALID_ROOM_NAME", "Huoneen nimi on liian pitkä.")


def _new_room_id() -> str:
    raw = "".join(secrets.choice(ROOM_ID_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def _clean_room_id(value: object) -> str:
    text = str(value or "").replace("\r", "").replace("\n", "").strip().upper()
    compact = re.sub(r"[^A-Z0-9]", "", text)

    if len(compact) == 8:
        candidate = f"{compact[:4]}-{compact[4:]}"
    else:
        candidate = text

    if not re.fullmatch(r"[A-Z0-9]{4}-[A-Z0-9]{4}", candidate):
        return ""

    allowed = set(ROOM_ID_ALPHABET + "-")
    if any(ch not in allowed for ch in candidate):
        return ""

    return candidate


def _clean_display_name(value: object, fallback: str) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    text = "".join(ch for ch in text if ch.isprintable())
    text = text[:80].strip()
    return text or fallback


def _safe_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        number = int(value)
    except Exception:
        number = default
    return max(minimum, min(maximum, number))


def _safe_float(value: object, default: float) -> float:
    try:
        if isinstance(value, bool):
            raise ValueError
        return float(value)
    except Exception:
        return default


def _safe_optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, bool):
            raise ValueError
        return float(value)
    except Exception:
        return None