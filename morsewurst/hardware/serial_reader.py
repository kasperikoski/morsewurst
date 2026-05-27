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
        self.connection_id = 0

    @staticmethod
    def available_ports() -> List[str]:
        if list_ports is None:
            return []
        return [port.device for port in list_ports.comports()]

    @staticmethod
    def available_port_details() -> List[Dict[str, Any]]:
        """Return diagnostic information about currently visible serial ports."""

        if list_ports is None:
            return []

        details: List[Dict[str, Any]] = []

        for port in list_ports.comports():
            details.append(
                {
                    "device": getattr(port, "device", ""),
                    "description": getattr(port, "description", ""),
                    "hwid": getattr(port, "hwid", ""),
                    "manufacturer": getattr(port, "manufacturer", ""),
                    "product": getattr(port, "product", ""),
                    "serial_number": getattr(port, "serial_number", ""),
                    "vid": getattr(port, "vid", None),
                    "pid": getattr(port, "pid", None),
                }
            )

        return details

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

        result = SerialReader.probe_port_detailed(
            port_name,
            baudrate=baudrate,
            timeout_seconds=timeout_seconds,
        )

        if result.get("status") == "matched" and isinstance(result.get("event"), dict):
            return result["event"]

        return None

    @staticmethod
    def probe_port_detailed(
        port_name: str,
        baudrate: int = config.SERIAL_BAUDRATE,
        timeout_seconds: float = 1.5,
    ) -> Dict[str, Any]:
        """Probe a serial port and return a structured diagnostic result.

        This is intentionally more verbose than probe_port(). Auto-connect can
        use it to explain whether a port was busy, unavailable, silent or simply
        not a Morsewurst-compatible device.
        """

        result: Dict[str, Any] = {
            "port": str(port_name or ""),
            "baudrate": int(baudrate),
            "timeout_seconds": float(timeout_seconds),
            "status": "not_found",
            "match_reason": "",
            "event": None,
            "lines_seen": 0,
            "json_events_seen": 0,
            "candidate_events_seen": 0,
            "last_event_type": "",
            "last_line": "",
            "error": "",
            "exception_type": "",
        }

        if serial is None:
            result["status"] = "pyserial_missing"
            result["error"] = "pyserial is not available"
            return result

        port_name = str(port_name or "").strip()
        if not port_name:
            result["status"] = "missing_port"
            result["error"] = "No serial port name was provided"
            return result

        timeout_seconds = max(0.5, float(timeout_seconds))
        result["timeout_seconds"] = timeout_seconds
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

                    result["lines_seen"] = int(result["lines_seen"]) + 1
                    result["last_line"] = line[:200]

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if not isinstance(event, dict):
                        continue

                    result["json_events_seen"] = int(result["json_events_seen"]) + 1

                    event_type = str(event.get("type", ""))
                    result["last_event_type"] = event_type

                    if event_type not in {"hello", "heartbeat", "tone"}:
                        continue

                    result["candidate_events_seen"] = int(result["candidate_events_seen"]) + 1

                    app_name = str(event.get("app", "")).lower()
                    device_name = str(event.get("device", ""))
                    mode = str(event.get("mode", ""))

                    if app_name == expected_app:
                        return SerialReader._matched_probe_result(
                            result,
                            event,
                            "app",
                        )

                    if device_name == expected_device:
                        if not expected_mode or mode in {"", expected_mode}:
                            return SerialReader._matched_probe_result(
                                result,
                                event,
                                "device",
                            )

                    if event_type == "heartbeat" and accept_plain_heartbeat:
                        return SerialReader._matched_probe_result(
                            result,
                            event,
                            "plain_heartbeat",
                        )

                    if event_type == "tone":
                        return SerialReader._matched_probe_result(
                            result,
                            event,
                            "tone",
                        )

        except Exception as exc:
            result["status"] = SerialReader._probe_exception_status(exc)
            result["error"] = str(exc)
            result["exception_type"] = exc.__class__.__name__
            return result

        return result

    @staticmethod
    def _matched_probe_result(
        result: Dict[str, Any],
        event: Dict[str, Any],
        reason: str,
    ) -> Dict[str, Any]:
        result["status"] = "matched"
        result["match_reason"] = reason
        result["event"] = event
        return result

    @staticmethod
    def _probe_exception_status(exc: Exception) -> str:
        text = str(exc or "").casefold()
        name = exc.__class__.__name__.casefold()

        if (
            "permissionerror" in name
            or "permissionerror" in text
            or "access is denied" in text
            or "käyttö estetty" in text
            or (
                "could not open port" in text
                and ("denied" in text or "estetty" in text)
            )
        ):
            return "busy"

        if "file not found" in text or "cannot find" in text or "järjestelmä ei löydä" in text:
            return "missing_port"

        return "open_failed"

    def connect(self, port_name: str, baudrate: int = config.SERIAL_BAUDRATE) -> None:
        if serial is None:
            raise RuntimeError("pyserial-pakettia ei ole asennettu. Asenna: python -m pip install pyserial")
        self.disconnect()
        self.connection_id += 1
        connection_id = self.connection_id
        self.port_name = port_name
        self.stop_event.clear()
        self.ser = serial.Serial(port_name, baudrate, timeout=config.SERIAL_READ_TIMEOUT_SECONDS)
        self.thread = threading.Thread(target=self._run, args=(connection_id,), daemon=True)
        self.thread.start()

    def disconnect(self) -> None:
        self.connection_id += 1
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

    def _run(self, connection_id: int) -> None:
        assert self.ser is not None
        while not self.stop_event.is_set():
            try:
                raw = self.ser.readline()
            except Exception as exc:
                self.event_queue.put(
                    {
                        "type": "serial_error",
                        "message": str(exc),
                        "_serial_connection_id": connection_id,
                        "_serial_port": self.port_name,
                        "_host_received_time": time.time(),
                    }
                )
                break

            if not raw:
                continue

            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                self.event_queue.put(
                    {
                        "type": "serial_non_json",
                        "line": line,
                        "_serial_connection_id": connection_id,
                        "_serial_port": self.port_name,
                        "_host_received_time": time.time(),
                    }
                )
                continue

            if not isinstance(event, dict):
                self.event_queue.put(
                    {
                        "type": "serial_non_object",
                        "line": line,
                        "_serial_connection_id": connection_id,
                        "_serial_port": self.port_name,
                        "_host_received_time": time.time(),
                    }
                )
                continue

            event["_host_received_time"] = time.time()
            event["_serial_connection_id"] = connection_id
            event["_serial_port"] = self.port_name
            self.event_queue.put(event)
