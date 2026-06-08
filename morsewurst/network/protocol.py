# ============================================================
# morsewurst/network/protocol.py
# ============================================================

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

PROTOCOL_VERSION = 4
APP_ID = "morsewurst"

SUPPORTED_WAVEFORMS = {"sine", "square", "triangle", "saw"}
ROOM_ID_MAX_LENGTH = 64
CALLSIGN_MAX_LENGTH = 20
INSTALLATION_ID_MAX_LENGTH = 80
ROOM_ACCESS_PUBLIC = "public"
ROOM_ACCESS_PRIVATE = "private"

_ROOM_SAFE_RE = re.compile(r"[^a-z0-9._-]+")
_INSTALLATION_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9._:-]+")
_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ProtocolError(ValueError):
    pass


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id(prefix: str = "mw") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def new_nonce() -> str:
    return secrets.token_urlsafe(24)


def new_installation_id() -> str:
    """Return a privacy-friendly persistent installation identifier.

    This is random. It is not derived from hardware serial numbers,
    Windows identifiers, MAC addresses or other device fingerprints.
    """

    return f"mwinst-{uuid.uuid4().hex}"


def sanitize_installation_id(value: object) -> str:
    text = str(value or "").strip()
    text = text.replace("\r", "").replace("\n", "")
    text = _INSTALLATION_ID_SAFE_RE.sub("", text)
    return text[:INSTALLATION_ID_MAX_LENGTH]


def encode_message(message: Dict[str, Any]) -> str:
    return json.dumps(message, ensure_ascii=False, separators=(",", ":"))


def decode_message(raw: str | bytes) -> Dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ProtocolError("Message must be a JSON object.")

    return data


def base_message(message_type: str) -> Dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "app": APP_ID,
        "type": message_type,
        "ts_ms": now_ms(),
    }


def _ascii_fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii")


def normalize_room_id(room: object) -> str:
    """Return the canonical server-side room identifier.

    The returned value is intentionally strict and URL/config friendly.
    Display names are separate from this technical id.
    """

    value = str(room or "").strip().lower()
    value = _ascii_fold(value)
    value = value.replace(" ", "-")
    value = _ROOM_SAFE_RE.sub("-", value)
    value = re.sub(r"-+", "-", value).strip("-._")
    # Frequency-like display names such as "128.400 MHz" should become
    # "128.400mhz", not "128.400-mhz".
    value = value.replace("-mhz", "mhz")

    if not value:
        return "default"

    return value[:ROOM_ID_MAX_LENGTH]


def sanitize_room_display_name(value: object) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    text = "".join(ch for ch in text if ch.isprintable())
    text = text[:80].strip()

    if text:
        return text

    return normalize_room_id(value)


# Backwards-compatible name used by older network code.
def normalize_room(room: object) -> str:
    return normalize_room_id(room)


def normalize_callsign(callsign: object) -> str:
    value = str(callsign or "").replace("\r", " ").replace("\n", " ").strip()
    value = re.sub(r"\s+", " ", value)
    value = "".join(ch for ch in value if ch.isprintable())
    value = value[:CALLSIGN_MAX_LENGTH].strip()
    if not value:
        return "Morsewurst"
    return value


def is_valid_password_verifier(value: object) -> bool:
    return bool(_HEX_SHA256_RE.fullmatch(str(value or "")))


def room_password_verifier(*, password: str, room: str) -> str:
    """Derive a room verifier from the room password.

    This value is secret-equivalent for private rooms. Public internet use
    should move to wss:// before real deployment.
    """

    room_id = normalize_room_id(room)
    payload = f"morsewurst-room-v1|{room_id}|{password or ''}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def auth_proof(*, password: str, room: str, client_id: str, nonce: str) -> str:
    verifier = room_password_verifier(password=password, room=room)
    return auth_proof_from_verifier(
        password_verifier=verifier,
        room=room,
        client_id=client_id,
        nonce=nonce,
    )


def auth_proof_from_verifier(*, password_verifier: str, room: str, client_id: str, nonce: str) -> str:
    if not is_valid_password_verifier(password_verifier):
        raise ProtocolError("Invalid room password verifier.")
    key = str(password_verifier).encode("utf-8")
    payload = f"{normalize_room_id(room)}|{client_id}|{nonce}".encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def legacy_auth_proof(*, password: str, room: str, client_id: str, nonce: str) -> str:
    key = str(password or "").encode("utf-8")
    payload = f"{normalize_room_id(room)}|{client_id}|{nonce}".encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def verify_auth(
    *,
    room: str,
    client_id: str,
    nonce: str,
    proof: str,
    password: Optional[str] = None,
    password_verifier: Optional[str] = None,
    allow_legacy_password_proof: bool = True,
) -> bool:
    received = str(proof or "")

    if password_verifier:
        try:
            expected = auth_proof_from_verifier(
                password_verifier=password_verifier,
                room=room,
                client_id=client_id,
                nonce=nonce,
            )
            if hmac.compare_digest(expected, received):
                return True
        except ProtocolError:
            return False

    if password is not None:
        verifier = room_password_verifier(password=password, room=room)
        expected = auth_proof_from_verifier(
            password_verifier=verifier,
            room=room,
            client_id=client_id,
            nonce=nonce,
        )
        if hmac.compare_digest(expected, received):
            return True

        # Compatibility for old direct host-mode tests.
        if allow_legacy_password_proof:
            legacy = legacy_auth_proof(password=password, room=room, client_id=client_id, nonce=nonce)
            if hmac.compare_digest(legacy, received):
                return True

    return False


def make_lobby_hello(
    *,
    callsign: str,
    client_id: str,
    installation_id: str,
    client_version: str = "",
) -> Dict[str, Any]:
    message = base_message("lobby_hello")
    message.update(
        {
            "callsign": normalize_callsign(callsign),
            "client_id": str(client_id or new_id("client"))[:80],
            "installation_id": sanitize_installation_id(installation_id),
            "client_version": str(client_version or "")[:40],
        }
    )
    return message


def make_client_hello(
    *,
    room: str,
    callsign: str,
    client_id: str,
    installation_id: str = "",
    client_version: str = "",
) -> Dict[str, Any]:
    message = base_message("client_hello")
    message.update(
        {
            "room": normalize_room_id(room),
            "room_name": sanitize_room_display_name(room),
            "callsign": normalize_callsign(callsign),
            "client_id": str(client_id)[:80],
            "installation_id": sanitize_installation_id(installation_id),
            "client_version": str(client_version or "")[:40],
            "capabilities": {
                "key_events": True,
                "tone_events": False,
                "decoded_text": False,
                "audio_playback": True,
                "dynamic_private_rooms": True,
                "public_rooms": True,
                "server_info": True,
                "server_ping": True,
            },
        }
    )
    return message


def make_server_challenge(
    *,
    room: str,
    server_id: str,
    nonce: str,
    room_exists: bool = True,
    can_create_private_room: bool = False,
    room_access: str = ROOM_ACCESS_PRIVATE,
    auth_required: bool = True,
) -> Dict[str, Any]:
    access = str(room_access or ROOM_ACCESS_PRIVATE).lower()
    if access not in {ROOM_ACCESS_PUBLIC, ROOM_ACCESS_PRIVATE}:
        access = ROOM_ACCESS_PRIVATE

    message = base_message("server_challenge")
    message.update(
        {
            "room": normalize_room_id(room),
            "server_id": str(server_id),
            "nonce": str(nonce),
            "auth": "none" if not auth_required else "hmac-sha256-room-verifier-v1",
            "auth_required": bool(auth_required),
            "room_access": access,
            "room_exists": bool(room_exists),
            "can_create_private_room": bool(can_create_private_room),
        }
    )
    return message


def make_auth(
    *,
    password: str,
    room: str,
    client_id: str,
    nonce: str,
    auth_required: bool = True,
    include_create_verifier: bool = False,
) -> Dict[str, Any]:
    room_id = normalize_room_id(room)
    message = base_message("auth")
    message.update(
        {
            "room": room_id,
            "client_id": str(client_id)[:80],
        }
    )

    if not auth_required:
        message["proof"] = ""
        return message

    verifier = room_password_verifier(password=password, room=room_id)
    message["proof"] = auth_proof_from_verifier(
        password_verifier=verifier,
        room=room_id,
        client_id=client_id,
        nonce=nonce,
    )
    if include_create_verifier:
        message["room_password_verifier"] = verifier
    return message


def make_welcome(
    *,
    room_key: str,
    server_id: str,
    client_id: str,
    peers: list[dict[str, Any]],
    room_name: Optional[str] = None,
    room_id: str = "",
    room_access: str = ROOM_ACCESS_PRIVATE,
) -> Dict[str, Any]:
    access = str(room_access or ROOM_ACCESS_PRIVATE).lower()
    if access not in {ROOM_ACCESS_PUBLIC, ROOM_ACCESS_PRIVATE}:
        access = ROOM_ACCESS_PRIVATE

    clean_room_key = normalize_room_id(room_key)

    message = base_message("welcome")
    message.update(
        {
            "room_key": clean_room_key,

            "room": clean_room_key,

            "room_name": room_name or clean_room_key,
            "room_id": str(room_id or "").strip().upper()[:20],

            "room_access": access,
            "server_id": str(server_id),
            "client_id": str(client_id),
            "peers": peers,
        }
    )
    return message


def make_peer_event(*, event_type: str, client_id: str, callsign: str) -> Dict[str, Any]:
    if event_type not in {"peer_joined", "peer_left"}:
        raise ValueError("event_type must be peer_joined or peer_left")
    message = base_message(event_type)
    message.update({"client_id": str(client_id), "callsign": normalize_callsign(callsign)})
    return message


def make_status(text: str, *, level: str = "info", code: str = "") -> Dict[str, Any]:
    message = base_message("status")
    message.update({"level": str(level), "text": str(text)})
    if code:
        message["code"] = str(code)
    return message


def make_heartbeat(*, sender_id: str) -> Dict[str, Any]:
    message = base_message("heartbeat")
    message.update({"sender_id": str(sender_id)})
    return message


def make_client_ping(*, sender_id: str, ping_id: str = "") -> Dict[str, Any]:
    message = base_message("client_ping")
    message.update(
        {
            "sender_id": str(sender_id),
            "ping_id": str(ping_id or new_id("ping"))[:80],
            "client_sent_ms": now_ms(),
        }
    )
    return message


def make_server_pong(
    *,
    server_id: str,
    ping_id: str,
    client_sent_ms: int,
) -> Dict[str, Any]:
    message = base_message("server_pong")
    message.update(
        {
            "server_id": str(server_id),
            "ping_id": str(ping_id or "")[:80],
            "client_sent_ms": int(client_sent_ms or 0),
            "server_received_ms": now_ms(),
        }
    )
    return message


def make_server_info(
    *,
    server_id: str,
    server_name: str,
    started_at: float,
    rooms_total: int,
    clients_total: int,
    room_key: str = "",
    room_id: str = "",
    room_name: str = "",
    room_clients: int = 0,
    known_installations: int = 0,
    seen_24h: int = 0,
    seen_7d: int = 0,
) -> Dict[str, Any]:
    now_seconds = time.time()
    uptime_seconds = max(0, int(now_seconds - float(started_at)))

    message = base_message("server_info")
    message.update(
        {
            "server_id": str(server_id),
            "server_name": str(server_name or "Morsewurst Relay")[:80],
            "server_time_unix_ms": now_ms(),
            "server_time_iso_utc": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": uptime_seconds,
            "rooms_total": max(0, int(rooms_total)),
            "clients_total": max(0, int(clients_total)),
            "room_key": normalize_room_id(room_key) if room_key else "",
            "room_id": str(room_id or "").strip().upper()[:20],
            "room_name": str(room_name or "")[:80],
            "room_clients": max(0, int(room_clients)),
            "known_installations": max(0, int(known_installations)),
            "seen_24h": max(0, int(seen_24h)),
            "seen_7d": max(0, int(seen_7d)),
        }
    )
    return message


def make_public_rooms_request() -> Dict[str, Any]:
    message = base_message("public_rooms_request")
    message.update(
        {
            "capabilities": {
                "public_rooms": True,
            }
        }
    )
    return message


def make_public_rooms_response(
    *,
    server_id: str,
    server_name: str,
    rooms: list[dict[str, Any]],
) -> Dict[str, Any]:
    message = base_message("public_rooms")
    message.update(
        {
            "server_id": str(server_id),
            "server_name": str(server_name or "Morsewurst Relay")[:80],
            "rooms": [_sanitize_public_room(room) for room in rooms],
        }
    )
    return message


def validate_public_rooms_response(message: Dict[str, Any]) -> list[dict[str, Any]]:
    if message.get("type") != "public_rooms":
        raise ProtocolError("Message is not a public_rooms response.")

    rooms = message.get("rooms")
    if not isinstance(rooms, list):
        raise ProtocolError("public_rooms response does not contain a room list.")

    clean: list[dict[str, Any]] = []
    for room in rooms:
        if not isinstance(room, dict):
            continue
        clean_room = _sanitize_public_room(room)
        if clean_room["id"]:
            clean.append(clean_room)

    return clean


def _sanitize_public_room(room: dict[str, Any]) -> dict[str, Any]:
    room_id = normalize_room_id(room.get("id"))
    name = str(room.get("name") or room_id).replace("\r", " ").replace("\n", " ").strip()[:80]
    description = str(room.get("description") or "").replace("\r", " ").replace("\n", " ").strip()[:200]

    try:
        client_count = int(room.get("client_count") or 0)
    except Exception:
        client_count = 0

    try:
        max_clients = int(room.get("max_clients") or 0)
    except Exception:
        max_clients = 0

    return {
        "id": room_id,
        "name": name or room_id,
        "description": description,
        "access": ROOM_ACCESS_PUBLIC,
        "listed": True,
        "client_count": max(0, client_count),
        "max_clients": max(0, max_clients),
    }


def _as_int(value: Any) -> Optional[int]:
    try:
        if isinstance(value, bool):
            return None
        return int(value)
    except Exception:
        return None


def _as_float(value: Any) -> Optional[float]:
    try:
        if isinstance(value, bool):
            return None
        return float(value)
    except Exception:
        return None


def sanitize_tone_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Return a network-safe copy of a Morsewurst tone event."""

    if not isinstance(event, dict):
        raise ProtocolError("Tone event must be an object.")

    if event.get("type") != "tone":
        raise ProtocolError("Only tone events can be sent as tone telemetry.")

    t0 = _as_int(event.get("t0"))
    t1 = _as_int(event.get("t1"))
    dur = _as_float(event.get("dur"))

    if t0 is None or t1 is None or dur is None:
        raise ProtocolError("Tone event must include integer t0, integer t1 and numeric dur.")

    if t1 < t0:
        raise ProtocolError("Tone event t1 must be greater than or equal to t0.")

    clean: Dict[str, Any] = {
        "type": "tone",
        "t0": t0,
        "t1": t1,
        "dur": float(dur),
    }

    optional_keys = (
        "src",
        "el",
        "unit",
        "wpm",
        "device",
        "mode",
        "key",
        "pin",
    )

    for key in optional_keys:
        if key in event:
            value = event.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                clean[key] = value

    if clean.get("el") not in {".", "-", None}:
        clean.pop("el", None)

    if "src" in clean:
        clean["src"] = str(clean["src"] or "unknown").lower()[:32]

    return clean


def sanitize_key_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Return a network-safe V1 key down/up event."""

    if not isinstance(event, dict):
        raise ProtocolError("Key event must be an object.")

    if event.get("type") != "key":
        raise ProtocolError("Only V1 key events can be sent as key telemetry.")

    t = _as_int(event.get("t"))
    if t is None:
        raise ProtocolError("V1 key event must include integer t.")

    state = str(event.get("state") or "").strip().lower()
    if state not in {"down", "up"}:
        raise ProtocolError("V1 key event state must be down or up.")

    clean: Dict[str, Any] = {
        "v": 1,
        "type": "key",
        "src": str(event.get("src") or "unknown").lower()[:32],
        "state": state,
        "t": int(t),
    }

    optional_keys = (
        "el",
        "unit",
        "wpm",
        "dit",
        "device",
        "mode",
        "key",
        "pin",
    )

    for key in optional_keys:
        if key in event:
            value = event.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                clean[key] = value

    if clean.get("el") not in {".", "-", None}:
        clean.pop("el", None)

    return clean


def make_key_message(
    *,
    key_event: Dict[str, Any],
    sender_id: str,
    sender_name: str,
    seq: int,
    stream_id: str,
) -> Dict[str, Any]:
    message = base_message("key")
    message.update(
        {
            "sender_id": str(sender_id),
            "sender_name": normalize_callsign(sender_name),
            "seq": int(seq),
            "stream_id": str(stream_id),
            "key": sanitize_key_event(key_event),
        }
    )
    return message


def validate_key_message(message: Dict[str, Any]) -> Dict[str, Any]:
    if message.get("type") != "key":
        raise ProtocolError("Message is not a key message.")

    key = message.get("key")
    if not isinstance(key, dict):
        raise ProtocolError("Key message does not contain key object.")

    return sanitize_key_event(key)


def make_tone_message(
    *,
    tone_event: Dict[str, Any],
    sender_id: str,
    sender_name: str,
    seq: int,
    stream_id: str,
) -> Dict[str, Any]:
    message = base_message("tone")
    message.update(
        {
            "sender_id": str(sender_id),
            "sender_name": normalize_callsign(sender_name),
            "seq": int(seq),
            "stream_id": str(stream_id),
            "tone": sanitize_tone_event(tone_event),
        }
    )
    return message


def validate_tone_message(message: Dict[str, Any]) -> Dict[str, Any]:
    if message.get("type") != "tone":
        raise ProtocolError("Message is not a tone message.")

    tone = message.get("tone")
    if not isinstance(tone, dict):
        raise ProtocolError("Tone message does not contain tone object.")

    return sanitize_tone_event(tone)
