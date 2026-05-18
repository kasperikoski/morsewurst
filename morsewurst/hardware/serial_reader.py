# ============================================================
# morsewurst/hardware/serial_reader.py
# ============================================================

from __future__ import annotations

import json
import queue
import threading
import time
from typing import Any, Dict, List, Optional

import morsewurst.config as config

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


class SerialReader:
    def __init__(self, event_queue: "queue.Queue[Dict[str, Any]]") -> None:
        self.event_queue = event_queue
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.ser = None
        self.port_name: Optional[str] = None

    @staticmethod
    def available_ports() -> List[str]:
        if list_ports is None:
            return []
        return [port.device for port in list_ports.comports()]

    @staticmethod
    def serial_available() -> bool:
        return serial is not None
    
    @staticmethod
    def probe_port(
        port_name: str,
        baudrate: int = config.SERIAL_BAUDRATE,
        timeout_seconds: float = 1.5,
    ) -> dict[str, Any] | None:
        """Open a serial port briefly and check whether it looks like a Morsewurst device."""

        if serial is None:
            return None

        timeout_seconds = max(0.5, float(timeout_seconds))
        deadline = time.time() + timeout_seconds

        expected_app = str(
            getattr(config, "SERIAL_AUTO_CONNECT_DEVICE_APP", "morsewurst")
        ).lower()

        expected_device = str(
            getattr(config, "SERIAL_AUTO_CONNECT_DEVICE_NAME", "Morsewurst")
        )

        expected_mode = str(
            getattr(config, "SERIAL_AUTO_CONNECT_MODE", "raw_timing")
        )

        accept_plain_heartbeat = bool(
            getattr(config, "SERIAL_AUTO_CONNECT_ACCEPT_PLAIN_HEARTBEAT", True)
        )

        try:
            with serial.Serial(
                port_name,
                baudrate,
                timeout=0.2,
                rtscts=False,
                dsrdtr=False,
            ) as probe:

                # Tärkeä muutos:
                # Älä pakota DTR:ää pois päältä ESP32-S3:n USB-serialilla.
                # Monilla levyillä Serial-ulostulo näkyy luotettavammin, kun DTR on aktiivinen.
                try:
                    probe.dtr = True
                    probe.rts = False
                except Exception:
                    pass

                # Anna ESP32:lle pieni hetki reagoida portin avaukseen.
                time.sleep(0.15)

                try:
                    probe.reset_input_buffer()
                except Exception:
                    pass

                while time.time() < deadline:
                    raw = probe.readline()

                    if not raw:
                        continue

                    line = raw.decode("utf-8", errors="replace").strip()

                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if not isinstance(event, dict):
                        continue

                    event_type = str(event.get("type", ""))

                    if event_type not in {"hello", "heartbeat", "tone"}:
                        continue

                    app_name = str(event.get("app", "")).lower()
                    device_name = str(event.get("device", ""))
                    mode = str(event.get("mode", ""))

                    if app_name == expected_app:
                        return event

                    if device_name == expected_device:
                        if not expected_mode or mode in {"", expected_mode}:
                            return event

                    if event_type == "heartbeat" and accept_plain_heartbeat:
                        return event

                    if event_type == "tone":
                        return event

        except Exception:
            return None

        return None

    def connect(self, port_name: str, baudrate: int = config.SERIAL_BAUDRATE) -> None:
        if serial is None:
            raise RuntimeError("pyserial-pakettia ei ole asennettu. Asenna: python -m pip install pyserial")
        self.disconnect()
        self.port_name = port_name
        self.stop_event.clear()
        self.ser = serial.Serial(port_name, baudrate, timeout=config.SERIAL_READ_TIMEOUT_SECONDS)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def disconnect(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.thread = None
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None

    def _run(self) -> None:
        assert self.ser is not None
        while not self.stop_event.is_set():
            try:
                raw = self.ser.readline()
            except Exception as exc:
                self.event_queue.put({"type": "serial_error", "message": str(exc)})
                break

            if not raw:
                continue

            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                self.event_queue.put({"type": "serial_non_json", "line": line})
                continue

            if not isinstance(event, dict):
                self.event_queue.put({"type": "serial_non_object", "line": line})
                continue

            event["_host_received_time"] = time.time()
            self.event_queue.put(event)
