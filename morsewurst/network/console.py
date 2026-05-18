# ============================================================
# morsewurst/network/console.py
# ============================================================

from __future__ import annotations

import argparse
import queue
import time
from typing import Any, Dict, Optional

from morsewurst.hardware.serial_reader import SerialReader
from morsewurst.network.settings_store import load_network_settings
from morsewurst.network.manager import NetworkManager
from morsewurst.network.models import NetworkSettings, PlaybackSettings
from morsewurst.network.defaults import DEFAULT_RELAY_URI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MorseWurst WebSocket network test tool")
    sub = parser.add_subparsers(dest="mode", required=True)

    host = sub.add_parser("host", help="hostaa huone suoraan tästä koneesta")
    host.add_argument("--host", default="0.0.0.0")
    host.add_argument("--port", type=int, default=8765)
    host.add_argument("--room", default="default")
    host.add_argument("--password", default="")
    host.add_argument("--callsign", default="Host")
    host.add_argument("--serial", default="", help="COM-portti, jos haluat lähettää omalla keyerillä")
    host.add_argument("--tls-certfile", default="", help="TLS-sertifikaatti suoraa wss://-testiä varten")
    host.add_argument("--tls-keyfile", default="", help="TLS-private key suoraa wss://-testiä varten")
    add_audio_args(host)

    join = sub.add_parser("join", help="liity huoneeseen")
    join.add_argument("--uri", default=DEFAULT_RELAY_URI)
    join.add_argument("--room", default="default")
    join.add_argument("--password", default="")
    join.add_argument("--callsign", default="Client")
    join.add_argument("--serial", default="", help="COM-portti, jos haluat lähettää omalla keyerillä")
    join.add_argument("--tls-cafile", default="", help="Oma CA-tiedosto wss://-testiä varten")
    add_audio_args(join)

    return parser


def add_audio_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--no-playback", action="store_true")
    parser.add_argument("--no-transmit", action="store_true")
    parser.add_argument("--jitter", type=int, default=750)
    parser.add_argument("--frequency", type=float, default=650.0)
    parser.add_argument("--volume", type=float, default=0.12)
    parser.add_argument("--waveform", choices=["sine", "square", "triangle", "saw"], default="sine")
    parser.add_argument("--output-device", type=int, default=None)
    parser.add_argument("--sample-rate", type=int, default=44_100)
    parser.add_argument("--blocksize", type=int, default=2048)
    parser.add_argument("--latency", default="high")


def make_settings(args: argparse.Namespace) -> NetworkSettings:
    stored_settings = load_network_settings()

    playback = PlaybackSettings(
        enabled=not bool(args.no_playback),
        jitter_buffer_ms=int(args.jitter),
        frequency_hz=float(args.frequency),
        volume=float(args.volume),
        waveform=str(args.waveform),
        output_device=args.output_device,
        sample_rate=int(args.sample_rate),
        blocksize=int(args.blocksize),
        latency=str(args.latency),
    )

    if args.mode == "host":
        return NetworkSettings(
            callsign=args.callsign,
            installation_id=stored_settings.installation_id,
            room=args.room,
            password=args.password,
            host=args.host,
            port=args.port,
            transmit_enabled=not bool(args.no_transmit),
            playback=playback,
            tls_certfile=str(getattr(args, "tls_certfile", "") or ""),
            tls_keyfile=str(getattr(args, "tls_keyfile", "") or ""),
        )

    return NetworkSettings(
        callsign=args.callsign,
        installation_id=stored_settings.installation_id,
        room=args.room,
        password=args.password,
        server_uri=args.uri,
        transmit_enabled=not bool(args.no_transmit),
        playback=playback,
        tls_cafile=str(getattr(args, "tls_cafile", "") or ""),
    )


def connect_serial(port: str) -> tuple[Optional[SerialReader], Optional["queue.Queue[Dict[str, Any]]"]]:
    if not port:
        return None, None

    event_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
    reader = SerialReader(event_queue)
    reader.connect(port)
    print(f"Serial connected: {port}")
    return reader, event_queue


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    manager = NetworkManager()
    settings = make_settings(args)

    if args.mode == "host":
        manager.start_host(settings)
    else:
        manager.connect_to_room(settings)

    serial_reader, serial_queue = connect_serial(str(getattr(args, "serial", "") or ""))

    print("Running. Press Ctrl+C to stop.")
    try:
        while True:
            for status in manager.drain_statuses():
                level = status.get("level", "info")
                text = status.get("text", "")
                if text and level != "debug":
                    print(f"[{level}] {text}", flush=True)

            if serial_queue is not None:
                while True:
                    try:
                        event = serial_queue.get_nowait()
                    except queue.Empty:
                        break
                    if event.get("type") == "tone":
                        manager.publish_local_tone(event)
                        print(f"sent tone {event.get('el', '')} dur={event.get('dur')}", flush=True)

            time.sleep(0.02)

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        if serial_reader is not None:
            serial_reader.disconnect()
        manager.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
