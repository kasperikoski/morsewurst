# ============================================================
# morsewurst/server/__init__.py
# ============================================================

from __future__ import annotations

from morsewurst.server.config import load_relay_config
from morsewurst.server.relay import RelayServer

__all__ = ["RelayServer", "load_relay_config"]
