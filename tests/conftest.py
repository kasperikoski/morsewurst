from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_optional_websockets_stub() -> None:
    """Let pure protocol tests import the network package without websockets installed."""
    if importlib.util.find_spec("websockets") is not None:
        return

    async def _missing_connect(*_args, **_kwargs):
        raise RuntimeError("websockets is required for live network connections")

    async def _missing_serve(*_args, **_kwargs):
        raise RuntimeError("websockets is required for live network servers")

    websockets = types.ModuleType("websockets")
    websockets.connect = _missing_connect
    websockets.serve = _missing_serve

    asyncio_pkg = types.ModuleType("websockets.asyncio")
    client_mod = types.ModuleType("websockets.asyncio.client")
    server_mod = types.ModuleType("websockets.asyncio.server")
    client_mod.connect = _missing_connect
    server_mod.serve = _missing_serve

    sys.modules.setdefault("websockets", websockets)
    sys.modules.setdefault("websockets.asyncio", asyncio_pkg)
    sys.modules.setdefault("websockets.asyncio.client", client_mod)
    sys.modules.setdefault("websockets.asyncio.server", server_mod)


_install_optional_websockets_stub()


MORSE_BY_CHAR = {
    "A": ".-",
    "B": "-...",
    "C": "-.-.",
    "D": "-..",
    "E": ".",
    "F": "..-.",
    "G": "--.",
    "H": "....",
    "I": "..",
    "J": ".---",
    "K": "-.-",
    "L": ".-..",
    "M": "--",
    "N": "-.",
    "O": "---",
    "P": ".--.",
    "Q": "--.-",
    "R": ".-.",
    "S": "...",
    "T": "-",
    "U": "..-",
    "V": "...-",
    "W": ".--",
    "X": "-..-",
    "Y": "-.--",
    "Z": "--..",
    "0": "-----",
    "1": ".----",
    "2": "..---",
    "3": "...--",
    "4": "....-",
    "5": ".....",
    "6": "-....",
    "7": "--...",
    "8": "---..",
    "9": "----.",
}


def make_tone_events(
    text: str,
    *,
    unit_us: int = 100_000,
    source: str = "iambic",
    include_hints: bool = True,
) -> list[dict[str, object]]:
    """Build deterministic Morse tone telemetry for decoder and scoring tests."""
    events: list[dict[str, object]] = []
    t = 0
    pending_gap_us = 0
    has_previous_character = False

    for char in text.upper():
        if char.isspace():
            if has_previous_character:
                pending_gap_us = max(pending_gap_us, 7 * unit_us)
            continue

        code = MORSE_BY_CHAR[char]
        if has_previous_character:
            t += pending_gap_us or 3 * unit_us
        pending_gap_us = 0

        for index, element in enumerate(code):
            if index > 0:
                t += unit_us

            duration = unit_us if element == "." else 3 * unit_us
            event: dict[str, object] = {
                "type": "tone",
                "t0": t,
                "t1": t + duration,
                "dur": float(duration),
                "src": source,
                "unit": unit_us,
                "wpm": 1_200_000.0 / unit_us,
            }
            if include_hints:
                event["el"] = element
            events.append(event)
            t += duration

        has_previous_character = True

    return events
