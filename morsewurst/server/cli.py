# ============================================================
# morsewurst/server/cli.py
# ============================================================

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Optional

from morsewurst.server.config import load_relay_config
from morsewurst.server.models import ConfigError
from morsewurst.server.relay import RelayServer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Morsewurst headless relay server")
    parser.add_argument("--config", default="/etc/morsewurst/relay.toml")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--log-level", default=None)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_relay_config(Path(args.config))
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2

    if args.host is not None:
        config.server.host = args.host
    if args.port is not None:
        config.server.port = int(args.port)
    if args.log_level is not None:
        config.server.log_level = str(args.log_level).upper()

    logging.basicConfig(
        level=getattr(logging, config.server.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    server = RelayServer(config)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
