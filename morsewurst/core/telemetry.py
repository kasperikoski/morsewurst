# ============================================================
# morsewurst/core/telemetry.py
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional


KeyIdentity = tuple[str, str, str, str, str]


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


def _clean_text(value: Any, *, default: str = "", limit: int = 80, lower: bool = False) -> str:
    text = str(default if value is None else value)
    text = text.replace("\r", " ").replace("\n", " ").strip()
    if lower:
        text = text.lower()
    return text[:limit]


def normalize_key_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Return the canonical internal key down/up event.

    This is the normal telemetry model. It is intentionally not a separate V2 event.
    Private host/serial metadata is preserved for live UI timing but is not part
    of the network protocol.
    """

    if not isinstance(event, dict):
        raise ValueError("key event must be an object.")

    if event.get("type") != "key":
        raise ValueError("key event type must be key.")

    t = _as_int(event.get("t"))
    if t is None:
        raise ValueError("key event must include integer t.")

    state = _clean_text(event.get("state"), lower=True, limit=16)
    if state not in {"down", "up"}:
        raise ValueError("key event state must be down or up.")

    clean: Dict[str, Any] = {
        "v": 1,
        "type": "key",
        "src": _clean_text(event.get("src") or "unknown", lower=True, limit=32),
        "state": state,
        "t": int(t),
    }

    for key in ("el", "unit", "wpm", "dit", "device", "mode", "key", "pin"):
        if key not in event:
            continue
        value = event.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            clean[key] = value

    if clean.get("el") not in {".", "-", None}:
        clean.pop("el", None)

    # Internal metadata used for live extrapolation, duplicate filtering and
    # debug inspection. These keys must not be sent as network payload fields.
    for key in (
        "_host_received_time",
        "_host_processed_time",
        "_serial_connection_id",
        "_serial_port",
        "_raw_line",
    ):
        if key in event:
            clean[key] = event.get(key)

    return clean


def key_event_identity(event: Dict[str, Any]) -> KeyIdentity:
    """Return the identity used to pair one down event with one up event."""

    clean = normalize_key_event(event)
    return (
        _clean_text(clean.get("src") or "unknown", lower=True, limit=32),
        _clean_text(clean.get("device") or "", limit=80),
        _clean_text(clean.get("mode") or "", limit=80),
        _clean_text(clean.get("key") or "", limit=80),
        _clean_text(clean.get("pin") or "", limit=80),
    )


def _copy_optional_scalar(target: Dict[str, Any], key: str, *sources: Dict[str, Any]) -> None:
    for source in sources:
        if key not in source:
            continue
        value = source.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            target[key] = value
            return


def derive_tone_from_key_pair(
    down_event: Dict[str, Any],
    up_event: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Derive the completed tone from one matching V1 key down/up pair.

    The returned tone is derived data for the existing decoder, scoring and
    history code. The source of truth remains the original V1 down/up stream.
    """

    try:
        down = normalize_key_event(down_event)
        up = normalize_key_event(up_event)
    except Exception:
        return None

    if down.get("state") != "down" or up.get("state") != "up":
        return None

    if key_event_identity(down) != key_event_identity(up):
        return None

    t0 = _as_int(down.get("t"))
    t1 = _as_int(up.get("t"))
    if t0 is None or t1 is None:
        return None
    if t1 <= t0:
        return None

    tone: Dict[str, Any] = {
        "v": 1,
        "type": "tone",
        "src": _clean_text(down.get("src") or up.get("src") or "unknown", lower=True, limit=32),
        "t0": int(t0),
        "t1": int(t1),
        "dur": float(int(t1) - int(t0)),
        "_derived_from": "v1_key_down_up",
    }

    for key in ("el", "unit", "wpm", "dit", "device", "mode", "key", "pin"):
        _copy_optional_scalar(tone, key, down, up)

    if tone.get("el") not in {".", "-", None}:
        tone.pop("el", None)

    for key in (
        "_host_received_time",
        "_host_processed_time",
        "_serial_connection_id",
        "_serial_port",
        "_raw_line",
    ):
        if key in up:
            tone[key] = up.get(key)
        elif key in down:
            tone[key] = down.get(key)

    return tone
