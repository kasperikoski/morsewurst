# ============================================================
# morsewurst/network/__init__.py
# ============================================================

from __future__ import annotations

from typing import Any

from morsewurst.network.defaults import DEFAULT_RELAY_URI

__all__ = [
    "DEFAULT_RELAY_URI",
    "NetworkManager",
    "OperatorIdentity",
    "load_or_create_operator_identity",
    "NetworkSettings",
    "PlaybackSettings",
    "PublicRoom",
    "fetch_public_rooms",
]


def __getattr__(name: str) -> Any:
    """Load optional network components only when they are explicitly requested.

    Server-side tools often need only protocol, identity, rooms or relay modules.
    Keeping these imports lazy avoids pulling desktop-client dependencies into
    minimal relay installations merely because the package itself was imported.
    """

    if name in {"OperatorIdentity", "load_or_create_operator_identity"}:
        from morsewurst.network.identity import OperatorIdentity, load_or_create_operator_identity

        values = {
            "OperatorIdentity": OperatorIdentity,
            "load_or_create_operator_identity": load_or_create_operator_identity,
        }
        return values[name]

    if name == "NetworkManager":
        from morsewurst.network.manager import NetworkManager

        return NetworkManager

    if name in {"NetworkSettings", "PlaybackSettings"}:
        from morsewurst.network.models import NetworkSettings, PlaybackSettings

        values = {
            "NetworkSettings": NetworkSettings,
            "PlaybackSettings": PlaybackSettings,
        }
        return values[name]

    if name in {"PublicRoom", "fetch_public_rooms"}:
        from morsewurst.network.public_rooms import PublicRoom, fetch_public_rooms

        values = {
            "PublicRoom": PublicRoom,
            "fetch_public_rooms": fetch_public_rooms,
        }
        return values[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
