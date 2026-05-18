# ============================================================
# morsewurst/ui/network/lobby_state.py
# ============================================================

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RoomSelectionState:
    key: str = ""
    title: str = ""
    password: str = ""
    access: str = ""
    description: str = ""


@dataclass(slots=True)
class ServerQueryState:
    info_running: bool = False
    ping_running: bool = False
    error_text: str = ""