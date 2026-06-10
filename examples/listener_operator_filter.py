#!/usr/bin/env python3
"""Minimal Morsewurst Network listener example.

This file is intentionally self-contained. It does not import Morsewurst
internals, so it can be used as a starting point for external tools, hardware
listeners, ESP32 prototypes, dashboards, bots, or other custom integrations.

What this example does:
    1. Opens a WebSocket connection to the Morsewurst relay.
    2. Joins one room as a read-only listener.
    3. Authenticates to the room if a room password is configured.
    4. Receives Morse key/tone traffic.
    5. Optionally filters traffic to one verified Operator Identity listener code.

Install dependency:
    python -m pip install websockets

Run from the project root:
    python examples/listener_operator_filter.py

Stop with Ctrl+C.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

try:
    from websockets.asyncio.client import connect
except ImportError:  # websockets < 12 fallback
    from websockets import connect  # type: ignore[assignment]


# ============================================================
# User-editable example configuration
# ============================================================

# Public Morsewurst relay.
RELAY_URI = "wss://morsewurst.duckdns.org"

# Example private test room.
#
# Use the room name/key here, not the displayed room ID.
# In the Morsewurst UI this room may show:
#
#     Room:    test
#     Room ID: G944-66NZ
#
# The listener joins by room name/key. The room ID is shown for reference.
ROOM = "test"
ROOM_PASSWORD = "test"

# Optional verified operator filter.
#
# This is a public listener code, not a private key. Replace it with your own
# listener code or set it to "" to print verified traffic from anyone in the
# joined room.
OPERATOR_FILTER = "MWOP-0TWQ-2DEV-G71N-1VMK-68WM"

# Listener identity shown to the relay.
CALLSIGN = "Python Listener Example"
CLIENT_ID_PREFIX = "listener-python-example"

# Output controls.
PRINT_KEY_MESSAGES = True
PRINT_TONE_MESSAGES = True
PRINT_RAW_JSON = False

# Connection behavior.
CONNECT_TIMEOUT_SECONDS = 15
RECONNECT_DELAY_SECONDS = 3


# ============================================================
# Protocol helpers
# ============================================================

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def normalize_room_id(room: object) -> str:
    """Return the simple room-id form expected by the relay auth proof.

    This small external-client normalizer is intentionally conservative. For
    normal room IDs such as "default", "test" and "G944-66NZ" it matches the
    practical relay behavior.
    """

    text = str(room or "").strip().lower()
    text = text.replace(" ", "-").replace("_", "-")
    text = "".join(ch for ch in text if ch.isalnum() or ch in {"-", "."})
    return text[:40] or "default"


def normalize_operator_id(value: object) -> str:
    """Normalize a public MWOP listener code.

    The code is public and safe to share. It identifies a public key. It is not
    the exported Operator Identity file and does not contain a private key.
    """

    text = str(value or "").strip().upper()
    text = text.replace(" ", "").replace("_", "-")

    if not text:
        return ""

    if text.startswith("MWOP"):
        text = text[4:]

    body = text.replace("-", "")
    body = body.translate(str.maketrans({"I": "1", "L": "1", "O": "0"}))

    if len(body) != 20:
        raise ValueError(f"Invalid operator listener code length: {value!r}")

    invalid = [ch for ch in body if ch not in CROCKFORD_ALPHABET]
    if invalid:
        raise ValueError(f"Invalid operator listener code characters: {sorted(set(invalid))!r}")

    groups = [body[index:index + 4] for index in range(0, len(body), 4)]
    return "MWOP-" + "-".join(groups)


def room_password_verifier(password: str, room: str) -> str:
    """Derive the private-room password verifier used by Morsewurst V5 auth."""

    room_id = normalize_room_id(room)
    payload = f"morsewurst-room-v1|{room_id}|{password or ''}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def auth_proof(password: str, room: str, client_id: str, nonce: str) -> str:
    """Return the HMAC proof for a private room challenge."""

    room_id = normalize_room_id(room)
    verifier = room_password_verifier(password, room_id)
    payload = f"{room_id}|{client_id}|{nonce}".encode("utf-8")
    return hmac.new(verifier.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def make_client_id() -> str:
    """Return a short unique client id for this process."""

    suffix = uuid.uuid4().hex[:10]
    return f"{CLIENT_ID_PREFIX}-{suffix}"


def make_client_hello(*, room: str, client_id: str) -> dict[str, Any]:
    """Build the first message sent to the relay."""

    return {
        "v": 5,
        "app": "morsewurst",
        "type": "client_hello",
        "room": room,
        "room_name": room,
        "callsign": CALLSIGN,
        "client_id": client_id,
        "client_mode": "listener",
        "client_version": "python-listener-example-0.99.17",
        "capabilities": {
            "listener_mode": True,
            "operator_identity": True,
            "operator_filter": True,
            "server_ping": True,
        },
    }


def make_auth(
    *,
    password: str,
    room: str,
    client_id: str,
    nonce: str,
    auth_required: bool,
) -> dict[str, Any]:
    """Build the room authentication message."""

    proof = ""
    if auth_required:
        proof = auth_proof(password, room, client_id, nonce)

    return {
        "v": 5,
        "app": "morsewurst",
        "type": "auth",
        "room": room,
        "client_id": client_id,
        "proof": proof,
    }


def dumps(message: dict[str, Any]) -> str:
    """Encode compact JSON for WebSocket transport."""

    return json.dumps(message, ensure_ascii=False, separators=(",", ":"))


def loads(raw: str | bytes) -> dict[str, Any]:
    """Decode a WebSocket JSON object."""

    message = json.loads(raw)
    if not isinstance(message, dict):
        raise ValueError(f"Expected JSON object, got {type(message).__name__}")
    return message


# ============================================================
# Message display helpers
# ============================================================

def message_operator_label(message: dict[str, Any]) -> str:
    operator_id = str(message.get("operator_id") or "unknown")
    verified = "verified" if message.get("operator_verified") is True else "unverified"
    sender = str(message.get("sender_name") or message.get("sender_id") or "unknown")
    return f"{sender} | {operator_id} | {verified}"


def print_key_message(message: dict[str, Any]) -> None:
    key = message.get("key")
    if not isinstance(key, dict):
        key = message

    state = str(key.get("state") or "?")
    source = str(key.get("src") or "?")
    device = str(key.get("device") or "")
    t_us = key.get("t")

    print(
        f"[KEY] {message_operator_label(message)} | "
        f"state={state} src={source} device={device} t={t_us}"
    )


def print_tone_message(message: dict[str, Any]) -> None:
    tone = message.get("tone")
    if not isinstance(tone, dict):
        tone = message

    source = str(tone.get("src") or "?")
    duration_raw = tone.get("dur")
    t0 = tone.get("t0")
    t1 = tone.get("t1")

    if duration_raw is None:
        duration_text = "?"
    else:
        try:
            duration_ms = float(str(duration_raw)) / 1000.0
            duration_text = f"{duration_ms:.1f} ms"
        except (TypeError, ValueError, OverflowError):
            duration_text = str(duration_raw)

    print(
        f"[TONE] {message_operator_label(message)} | "
        f"src={source} dur={duration_text} t0={t0} t1={t1}"
    )


def should_accept_message(message: dict[str, Any], operator_filter: str) -> bool:
    """Return True when the incoming key/tone message should be displayed."""

    if message.get("type") not in {"key", "tone"}:
        return False

    # If an operator filter is configured, only trust server-verified operator
    # metadata. This prevents spoofed runtime fields from matching the filter.
    if operator_filter:
        if message.get("operator_verified") is not True:
            return False
        if str(message.get("operator_id") or "") != operator_filter:
            return False

    return True


# ============================================================
# Listener loop
# ============================================================

async def listen_once() -> None:
    """Connect once, join the configured room, and print matching traffic."""

    client_id = make_client_id()
    operator_filter = normalize_operator_id(OPERATOR_FILTER)

    print("Morsewurst listener example")
    print(f"relay:           {RELAY_URI}")
    print(f"room:            {ROOM}")
    print(f"room password:   {'yes' if ROOM_PASSWORD else 'no'}")
    print(f"operator filter: {operator_filter or 'none'}")
    print()

    async with connect(
        RELAY_URI,
        max_size=512_000,
        ping_interval=20,
        ping_timeout=60,
        open_timeout=CONNECT_TIMEOUT_SECONDS,
    ) as websocket:
        await websocket.send(dumps(make_client_hello(room=ROOM, client_id=client_id)))

        challenge = loads(await websocket.recv())
        if challenge.get("type") != "server_challenge":
            raise RuntimeError(f"Expected server_challenge, got {challenge!r}")

        room_for_auth = str(challenge.get("room") or ROOM)
        nonce = str(challenge.get("nonce") or "")
        auth_required = bool(challenge.get("auth_required", True))

        await websocket.send(
            dumps(
                make_auth(
                    password=ROOM_PASSWORD,
                    room=room_for_auth,
                    client_id=client_id,
                    nonce=nonce,
                    auth_required=auth_required,
                )
            )
        )

        welcome = loads(await websocket.recv())
        if welcome.get("type") != "welcome":
            raise RuntimeError(f"Join failed: {welcome!r}")

        joined_room = welcome.get("room_name") or welcome.get("room") or room_for_auth
        print(f"Joined room: {joined_room}")
        print("Listening. Press Ctrl+C to stop.")
        print()

        async for raw in websocket:
            message = loads(raw)

            if PRINT_RAW_JSON:
                print(dumps(message))
                continue

            if not should_accept_message(message, operator_filter):
                continue

            if message.get("type") == "key" and PRINT_KEY_MESSAGES:
                print_key_message(message)
            elif message.get("type") == "tone" and PRINT_TONE_MESSAGES:
                print_tone_message(message)


async def main() -> None:
    """Run the listener and reconnect after ordinary connection failures."""

    while True:
        try:
            await listen_once()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[ERROR] {exc}")
            print(f"Reconnecting in {RECONNECT_DELAY_SECONDS} seconds...")
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")