from __future__ import annotations

import os
import queue
from dataclasses import dataclass
from typing import Any, Callable

import pytest

import morsewurst.ui.controllers.serial_controller as serial_controller_module
from morsewurst.ui.controllers.serial_controller import SerialController
from morsewurst.hardware.serial_reader import SerialReader


# ---------------------------------------------------------------------------
# Lightweight UI/controller fakes
# ---------------------------------------------------------------------------


class FakeVar:
    def __init__(self, value: Any = "") -> None:
        self.value = value

    def get(self) -> Any:
        return self.value

    def set(self, value: Any) -> None:
        self.value = value


class FakeCombo:
    def __init__(self) -> None:
        self.values: list[str] = []
        self.state: str | None = None

    def __setitem__(self, key: str, value: Any) -> None:
        if key == "values":
            self.values = list(value)
            return
        setattr(self, key, value)

    def configure(self, **kwargs: Any) -> None:
        if "state" in kwargs:
            self.state = str(kwargs["state"])


class FakeButton:
    def __init__(self) -> None:
        self.state: str | None = None

    def configure(self, **kwargs: Any) -> None:
        if "state" in kwargs:
            self.state = str(kwargs["state"])


class FakeI18n:
    def t(self, _key: str, default: str, **kwargs: Any) -> str:
        if kwargs:
            try:
                return default.format(**kwargs)
            except Exception:
                return default
        return default


class FakeStatusController:
    def __init__(self) -> None:
        self.serial_statuses: list[tuple[str, str]] = []
        self.main_statuses: list[tuple[str, str]] = []

    def set_serial_status(self, text: str, *, state: str = "normal") -> None:
        self.serial_statuses.append((text, state))

    def set_main_status(self, text: str, *, state: str = "normal") -> None:
        self.main_statuses.append((text, state))


class FakeAudioController:
    def __init__(self) -> None:
        self.played: list[str] = []

    def play_sound(self, name: str) -> None:
        self.played.append(name)


class FakeLifecycleController:
    def __init__(self) -> None:
        self.focus_calls: list[bool] = []

    def focus_input(self, *, force: bool = False) -> None:
        self.focus_calls.append(bool(force))


class FakeInputController:
    def __init__(self) -> None:
        self.keyboard_enabled = False
        self.drain_return = 0
        self.drain_calls = 0

    def keyboard_morse_enabled(self) -> bool:
        return self.keyboard_enabled

    def drain_serial_queue(self) -> int:
        self.drain_calls += 1
        return int(self.drain_return)


class FakeSerialReader:
    def __init__(self) -> None:
        self.connection_id = 0
        self.port_name: str | None = None
        self.connect_calls: list[tuple[str, int]] = []
        self.disconnect_calls = 0
        self.raise_on_connect: Exception | None = None

    def connect(self, port_name: str, baudrate: int) -> None:
        self.connect_calls.append((port_name, baudrate))
        self.connection_id += 1
        self.port_name = port_name
        if self.raise_on_connect is not None:
            raise self.raise_on_connect

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connection_id += 1


class FakeApp:
    def __init__(self) -> None:
        self.i18n = FakeI18n()
        self.status_controller = FakeStatusController()
        self.audio_controller = FakeAudioController()
        self.app_lifecycle_controller = FakeLifecycleController()
        self.input_controller = FakeInputController()
        self.serial_reader = FakeSerialReader()

        self.event_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.port_var = FakeVar("COM6")
        self.auto_connect_serial_var = FakeVar(True)
        self.last_event_var = FakeVar("")

        self.serial_connected = False
        self.auto_connect_running = False
        self.auto_connect_thread = None
        self.serial_connection_id = 0

        self.port_combo = FakeCombo()
        self.connect_serial_button = FakeButton()
        self.disconnect_serial_button = FakeButton()

        self.after_calls: list[tuple[int, Callable[..., Any], tuple[Any, ...]]] = []

    def after(self, delay_ms: int, callback: Callable[..., Any], *args: Any) -> Any:
        self.after_calls.append((int(delay_ms), callback, args))
        if int(delay_ms) == 0:
            return callback(*args)
        return f"after-{len(self.after_calls)}"


@pytest.fixture
def app() -> FakeApp:
    return FakeApp()


@pytest.fixture
def controller(app: FakeApp) -> SerialController:
    return SerialController(app)  # type: ignore[arg-type]


@pytest.fixture
def captured_logs(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []

    def fake_log_event(
        event: str,
        *,
        level: str = "info",
        message: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        logs.append(
            {
                "kind": "event",
                "event": event,
                "level": level,
                "message": message,
                "context": context or {},
            }
        )

    def fake_log_exception(
        event: str,
        exc: BaseException,
        *,
        level: str = "error",
        message: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        logs.append(
            {
                "kind": "exception",
                "event": event,
                "level": level,
                "message": message,
                "context": context or {},
                "exception_type": exc.__class__.__name__,
                "exception_message": str(exc),
            }
        )

    monkeypatch.setattr(serial_controller_module, "log_app_event", fake_log_event)
    monkeypatch.setattr(serial_controller_module, "log_app_exception", fake_log_exception)
    return logs


@pytest.fixture
def captured_messageboxes(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[tuple[Any, ...]]]:
    calls: dict[str, list[tuple[Any, ...]]] = {"warning": [], "error": []}

    monkeypatch.setattr(
        serial_controller_module.messagebox,
        "showwarning",
        lambda *args, **_kwargs: calls["warning"].append(args),
    )
    monkeypatch.setattr(
        serial_controller_module.messagebox,
        "showerror",
        lambda *args, **_kwargs: calls["error"].append(args),
    )
    return calls


# ---------------------------------------------------------------------------
# Port refresh and UI state
# ---------------------------------------------------------------------------


def test_refresh_ports_replaces_missing_selected_port(
    controller: SerialController,
    app: FakeApp,
    monkeypatch: pytest.MonkeyPatch,
    captured_logs: list[dict[str, Any]],
) -> None:
    app.port_var.set("COM6")

    monkeypatch.setattr(SerialReader, "available_ports", staticmethod(lambda: ["COM1", "COM7"]))
    monkeypatch.setattr(
        SerialReader,
        "available_port_details",
        staticmethod(lambda: [{"device": "COM1"}, {"device": "COM7"}]),
    )
    monkeypatch.setattr(SerialReader, "serial_available", staticmethod(lambda: True))

    controller.refresh_ports()

    assert app.port_var.get() == "COM1"
    assert app.port_combo.values == ["COM1", "COM7"]
    assert app.connect_serial_button.state == serial_controller_module.tk.NORMAL
    assert app.disconnect_serial_button.state == serial_controller_module.tk.DISABLED
    assert any(log["event"] == "app.serial.selected_port_missing" for log in captured_logs)


def test_refresh_ports_keeps_existing_selected_port(
    controller: SerialController,
    app: FakeApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.port_var.set("COM6")

    monkeypatch.setattr(SerialReader, "available_ports", staticmethod(lambda: ["COM5", "COM6"]))
    monkeypatch.setattr(SerialReader, "available_port_details", staticmethod(lambda: []))
    monkeypatch.setattr(SerialReader, "serial_available", staticmethod(lambda: True))

    controller.refresh_ports()

    assert app.port_var.get() == "COM6"
    assert app.port_combo.values == ["COM5", "COM6"]


def test_refresh_ports_clears_selection_when_no_ports(
    controller: SerialController,
    app: FakeApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.port_var.set("COM6")

    monkeypatch.setattr(SerialReader, "available_ports", staticmethod(lambda: []))
    monkeypatch.setattr(SerialReader, "available_port_details", staticmethod(lambda: []))
    monkeypatch.setattr(SerialReader, "serial_available", staticmethod(lambda: True))

    controller.refresh_ports()

    assert app.port_var.get() == ""
    assert app.port_combo.values == []


def test_refresh_ports_reports_pyserial_missing(
    controller: SerialController,
    app: FakeApp,
    monkeypatch: pytest.MonkeyPatch,
    captured_logs: list[dict[str, Any]],
) -> None:
    monkeypatch.setattr(SerialReader, "available_ports", staticmethod(lambda: []))
    monkeypatch.setattr(SerialReader, "available_port_details", staticmethod(lambda: []))
    monkeypatch.setattr(SerialReader, "serial_available", staticmethod(lambda: False))

    controller.refresh_ports()

    assert app.status_controller.serial_statuses[-1] == ("pyserial missing", "disconnected")
    assert any(log["event"] == "app.serial.pyserial_missing" for log in captured_logs)


# ---------------------------------------------------------------------------
# Probe summaries and busy-port detection
# ---------------------------------------------------------------------------


def test_compact_probe_result_summarises_event_without_raw_payload(
    controller: SerialController,
) -> None:
    summary = controller.compact_probe_result(
        {
            "port": "COM6",
            "status": "matched",
            "match_reason": "app",
            "lines_seen": 3,
            "json_events_seen": 2,
            "candidate_events_seen": 1,
            "last_event_type": "hello",
            "error": "",
            "exception_type": "",
            "event": {
                "type": "hello",
                "app": "morsewurst",
                "device": "Morsewurst",
                "fw": "0.1.0",
                "mode": "raw_timing",
                "src": "iambic",
                "secret_should_not_leak": "hidden",
                "large_raw_payload": "x" * 1000,
            },
        }
    )

    assert summary["status"] == "matched"
    assert summary["event"] == {
        "type": "hello",
        "app": "morsewurst",
        "device": "Morsewurst",
        "fw": "0.1.0",
        "mode": "raw_timing",
        "src": "iambic",
    }


def test_compact_probe_result_handles_invalid_input(controller: SerialController) -> None:
    assert controller.compact_probe_result(None) == {"status": "invalid_result"}


@pytest.mark.parametrize(
    "message",
    [
        "PermissionError(13, 'Access is denied.', None, 5)",
        "could not open port 'COM6': PermissionError(13, 'Käyttö estetty.', None, 5)",
        "could not open port COM6: access is denied",
        "could not open port COM6: käyttö estetty",
    ],
)
def test_is_serial_port_busy_error_detects_windows_access_denied(
    controller: SerialController,
    message: str,
) -> None:
    assert controller.is_serial_port_busy_error(Exception(message)) is True


def test_is_serial_port_busy_error_ignores_unrelated_errors(controller: SerialController) -> None:
    assert controller.is_serial_port_busy_error(Exception("device sent invalid json")) is False


# ---------------------------------------------------------------------------
# Manual connect/disconnect lifecycle
# ---------------------------------------------------------------------------


def test_connect_serial_port_success_sets_connected_state_and_syncs_connection_id(
    controller: SerialController,
    app: FakeApp,
    captured_logs: list[dict[str, Any]],
) -> None:
    app.input_controller.drain_return = 2

    controller.connect_serial_port("COM6", automatic=False)

    assert app.serial_reader.connect_calls == [("COM6", serial_controller_module.config.SERIAL_BAUDRATE)]
    assert app.serial_connected is True
    assert app.auto_connect_running is False
    assert app.port_var.get() == "COM6"
    assert app.serial_connection_id == app.serial_reader.connection_id
    assert app.input_controller.drain_calls == 1
    assert app.status_controller.serial_statuses[-1][0].startswith("COM6 @")
    assert app.status_controller.serial_statuses[-1][1] == "connected"
    assert app.status_controller.main_statuses[-1] == ("Serial device connected.", "normal")
    assert app.audio_controller.played == ["serial_connected"]
    assert app.app_lifecycle_controller.focus_calls == [True]
    assert any(log["event"] == "app.serial.event_queue_drained" for log in captured_logs)
    assert any(log["event"] == "app.serial.connect_success" for log in captured_logs)


def test_connect_serial_port_empty_manual_shows_warning(
    controller: SerialController,
    app: FakeApp,
    captured_messageboxes: dict[str, list[tuple[Any, ...]]],
) -> None:
    controller.connect_serial_port("", automatic=False)

    assert app.serial_reader.connect_calls == []
    assert captured_messageboxes["warning"]
    assert captured_messageboxes["error"] == []


def test_connect_serial_port_empty_automatic_does_not_show_dialog(
    controller: SerialController,
    app: FakeApp,
    captured_messageboxes: dict[str, list[tuple[Any, ...]]],
) -> None:
    controller.connect_serial_port("", automatic=True)

    assert app.serial_reader.connect_calls == []
    assert captured_messageboxes == {"warning": [], "error": []}


def test_manual_connect_is_blocked_during_auto_scan(
    controller: SerialController,
    app: FakeApp,
) -> None:
    app.auto_connect_running = True

    controller.connect_serial()

    assert app.serial_reader.connect_calls == []
    assert app.status_controller.serial_statuses[-1] == ("Searching for device...", "busy")
    assert app.status_controller.main_statuses[-1][1] == "warning"
    assert app.connect_serial_button.state == serial_controller_module.tk.DISABLED


def test_connect_serial_port_busy_manual_sets_warning_and_does_not_connect(
    controller: SerialController,
    app: FakeApp,
    captured_messageboxes: dict[str, list[tuple[Any, ...]]],
    captured_logs: list[dict[str, Any]],
) -> None:
    app.serial_reader.raise_on_connect = Exception(
        "could not open port 'COM6': PermissionError(13, 'Käyttö estetty.', None, 5)"
    )

    controller.connect_serial_port("COM6", automatic=False)

    assert app.serial_connected is False
    assert app.status_controller.serial_statuses[-1] == ("Port is busy", "warning")
    assert app.status_controller.main_statuses[-1][1] == "warning"
    assert "COM6" in app.status_controller.main_statuses[-1][0]
    assert captured_messageboxes["warning"]
    assert captured_messageboxes["error"] == []
    assert any(log["event"] == "app.serial.port_busy" for log in captured_logs)


def test_connect_serial_port_busy_automatic_schedules_retry_without_dialog(
    controller: SerialController,
    app: FakeApp,
    captured_messageboxes: dict[str, list[tuple[Any, ...]]],
) -> None:
    app.serial_reader.raise_on_connect = Exception("could not open port COM6: access is denied")

    controller.connect_serial_port("COM6", automatic=True)

    assert app.serial_connected is False
    assert captured_messageboxes == {"warning": [], "error": []}
    assert app.after_calls
    delay_ms, callback, _args = app.after_calls[-1]
    assert delay_ms == 800
    assert callback == controller.request_auto_connect_scan


def test_connect_serial_port_non_busy_error_manual_shows_error(
    controller: SerialController,
    app: FakeApp,
    captured_messageboxes: dict[str, list[tuple[Any, ...]]],
    captured_logs: list[dict[str, Any]],
) -> None:
    app.serial_reader.raise_on_connect = RuntimeError("boom")

    controller.connect_serial_port("COM6", automatic=False)

    assert app.serial_connected is False
    assert captured_messageboxes["error"]
    assert app.status_controller.serial_statuses[-1] == ("Connection failed", "disconnected")
    assert any(log["event"] == "app.serial.connect_failed" for log in captured_logs)


def test_disconnect_serial_updates_state_drains_queue_and_plays_sound(
    controller: SerialController,
    app: FakeApp,
) -> None:
    app.serial_connected = True
    app.serial_reader.connection_id = 10
    app.input_controller.drain_return = 3

    controller.disconnect_serial()

    assert app.serial_reader.disconnect_calls == 1
    assert app.serial_connection_id == app.serial_reader.connection_id
    assert app.input_controller.drain_calls == 1
    assert app.serial_connected is False
    assert app.status_controller.serial_statuses[-1] == ("No connection", "disconnected")
    assert app.audio_controller.played == ["serial_disconnected"]


def test_disconnect_serial_is_blocked_during_auto_scan(
    controller: SerialController,
    app: FakeApp,
) -> None:
    app.serial_connected = True
    app.auto_connect_running = True

    controller.disconnect_serial()

    assert app.serial_reader.disconnect_calls == 0
    assert app.serial_connected is True
    assert app.status_controller.serial_statuses[-1] == ("Searching for device...", "busy")
    assert app.status_controller.main_statuses[-1][1] == "warning"


# ---------------------------------------------------------------------------
# Connection lost and auto-connect flow
# ---------------------------------------------------------------------------


def test_handle_serial_disconnect_event_resets_state_and_schedules_scan(
    controller: SerialController,
    app: FakeApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.serial_connected = True
    app.auto_connect_running = True
    app.serial_reader.connection_id = 5
    app.input_controller.drain_return = 2

    refresh_calls = 0

    def fake_refresh_ports() -> None:
        nonlocal refresh_calls
        refresh_calls += 1

    monkeypatch.setattr(controller, "refresh_ports", fake_refresh_ports)

    controller.handle_serial_disconnect_event(
        {
            "type": "serial_error",
            "message": "read failed",
            "_serial_port": "COM6",
            "_serial_connection_id": 4,
        }
    )

    assert app.serial_connected is False
    assert app.auto_connect_running is False
    assert app.serial_reader.disconnect_calls == 1
    assert app.serial_connection_id == app.serial_reader.connection_id
    assert app.input_controller.drain_calls == 1
    assert app.last_event_var.get() == "Event: connection lost"
    assert app.audio_controller.played == ["serial_disconnected"]
    assert app.status_controller.main_statuses[-1] == ("Serial device disconnected.", "error")
    assert refresh_calls == 1
    assert app.after_calls[-1][0] == 500
    assert app.after_calls[-1][1] == controller.request_auto_connect_scan


def test_request_auto_connect_scan_starts_when_allowed(
    controller: SerialController,
    app: FakeApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = False

    def fake_start_auto_connect_scan() -> None:
        nonlocal started
        started = True

    monkeypatch.setattr(SerialReader, "serial_available", staticmethod(lambda: True))
    monkeypatch.setattr(controller, "start_auto_connect_scan", fake_start_auto_connect_scan)

    controller.request_auto_connect_scan()

    assert started is True


def test_request_auto_connect_scan_skips_when_keyboard_morse_enabled(
    controller: SerialController,
    app: FakeApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.input_controller.keyboard_enabled = True
    started = False

    def fake_start_auto_connect_scan() -> None:
        nonlocal started
        started = True

    monkeypatch.setattr(SerialReader, "serial_available", staticmethod(lambda: True))
    monkeypatch.setattr(controller, "start_auto_connect_scan", fake_start_auto_connect_scan)

    controller.request_auto_connect_scan()

    assert started is False


def test_start_auto_connect_scan_no_ports_sets_disconnected(
    controller: SerialController,
    app: FakeApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(SerialReader, "available_ports", staticmethod(lambda: []))

    controller.start_auto_connect_scan()

    assert app.auto_connect_running is False
    assert app.status_controller.serial_statuses[-1] == ("No connection", "disconnected")


def test_auto_connect_worker_uses_detailed_probe_and_connects_first_match(
    controller: SerialController,
    app: FakeApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probed: list[str] = []
    connect_calls: list[tuple[str, bool]] = []

    def fake_probe(port: str, _baudrate: int, *, timeout_seconds: float) -> dict[str, Any]:
        probed.append(port)
        if port == "COM6":
            return {
                "port": port,
                "status": "matched",
                "match_reason": "app",
                "event": {"type": "hello", "app": "morsewurst", "device": "Morsewurst"},
            }
        return {"port": port, "status": "not_found", "event": None}

    def fake_connect(port: str, *, automatic: bool = False) -> None:
        connect_calls.append((port, automatic))

    monkeypatch.setattr(SerialReader, "probe_port_detailed", staticmethod(fake_probe))
    monkeypatch.setattr(controller, "connect_serial_port", fake_connect)

    app.auto_connect_running = True
    controller.auto_connect_worker(["COM1", "COM6", "COM7"])

    assert probed == ["COM1", "COM6"]
    assert app.auto_connect_running is False
    assert connect_calls == [("COM6", True)]


def test_finish_auto_connect_scan_not_found_sets_disconnected(
    controller: SerialController,
    app: FakeApp,
    captured_logs: list[dict[str, Any]],
) -> None:
    app.auto_connect_running = True

    controller.finish_auto_connect_scan(
        None,
        probe_results=[{"port": "COM1", "status": "not_found"}],
    )

    assert app.auto_connect_running is False
    assert app.serial_connected is False
    assert app.status_controller.serial_statuses[-1] == ("No connection", "disconnected")
    assert any(
        log["event"] == "app.serial.auto_scan_not_found"
        and log["context"]["probe_results"] == [{"port": "COM1", "status": "not_found"}]
        for log in captured_logs
    )


def test_finish_auto_connect_scan_skips_when_keyboard_morse_enabled(
    controller: SerialController,
    app: FakeApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.auto_connect_running = True
    app.input_controller.keyboard_enabled = True
    connected: list[str] = []

    monkeypatch.setattr(
        controller,
        "connect_serial_port",
        lambda port, *, automatic=False: connected.append(port),
    )

    controller.finish_auto_connect_scan("COM6")

    assert app.auto_connect_running is False
    assert connected == []


def test_update_serial_buttons_reflects_connected_and_scanning_state(
    controller: SerialController,
    app: FakeApp,
) -> None:
    app.serial_connected = False
    app.auto_connect_running = False
    controller.update_serial_buttons()
    assert app.connect_serial_button.state == serial_controller_module.tk.NORMAL
    assert app.disconnect_serial_button.state == serial_controller_module.tk.DISABLED
    assert app.port_combo.state == "readonly"

    app.serial_connected = True
    controller.update_serial_buttons()
    assert app.connect_serial_button.state == serial_controller_module.tk.DISABLED
    assert app.disconnect_serial_button.state == serial_controller_module.tk.NORMAL

    app.auto_connect_running = True
    controller.update_serial_buttons()
    assert app.connect_serial_button.state == serial_controller_module.tk.DISABLED
    assert app.disconnect_serial_button.state == serial_controller_module.tk.DISABLED
    assert app.port_combo.state == serial_controller_module.tk.DISABLED


# ---------------------------------------------------------------------------
# Optional hardware smoke test
# ---------------------------------------------------------------------------


def _format_probe_report(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No serial ports were probed."

    lines = ["Serial probe report:"]
    for item in results:
        event = item.get("event")
        if isinstance(event, dict):
            event_text = (
                f"event_type={event.get('type')!r}, "
                f"app={event.get('app')!r}, "
                f"device={event.get('device')!r}, "
                f"mode={event.get('mode')!r}, "
                f"fw={event.get('fw')!r}"
            )
        else:
            event_text = "event=None"

        lines.append(
            "  "
            f"port={item.get('port')!r}, "
            f"status={item.get('status')!r}, "
            f"match_reason={item.get('match_reason')!r}, "
            f"lines_seen={item.get('lines_seen')!r}, "
            f"json_events_seen={item.get('json_events_seen')!r}, "
            f"candidate_events_seen={item.get('candidate_events_seen')!r}, "
            f"last_event_type={item.get('last_event_type')!r}, "
            f"error={item.get('error')!r}, "
            f"exception_type={item.get('exception_type')!r}, "
            f"{event_text}"
        )
    return "\n".join(lines)


def test_live_morsewurst_device_can_be_discovered_when_enabled() -> None:
    r"""Optional real-device smoke test.

    This test is deliberately skipped by default so the normal regression suite
    works on CI machines and development machines without the keyer attached.

    To run it on Windows PowerShell:

        $env:MORSEWURST_SERIAL_LIVE = "1"
        python -m pytest tests/test_serial_controller.py -k live_morsewurst_device -s
        Remove-Item Env:\MORSEWURST_SERIAL_LIVE

    To restrict the scan to one port, for example COM6:

        $env:MORSEWURST_SERIAL_LIVE = "1"
        $env:MORSEWURST_SERIAL_PORT = "COM6"
        python -m pytest tests/test_serial_controller.py -k live_morsewurst_device -s
    """

    if os.environ.get("MORSEWURST_SERIAL_LIVE") != "1":
        pytest.skip("Set MORSEWURST_SERIAL_LIVE=1 to run the real serial hardware probe.")

    if not SerialReader.serial_available():
        pytest.fail("pyserial is not available. Install it with: python -m pip install pyserial")

    requested_port = os.environ.get("MORSEWURST_SERIAL_PORT", "").strip()
    probe_seconds = float(os.environ.get("MORSEWURST_SERIAL_PROBE_SECONDS", "6.0"))

    ports = [requested_port] if requested_port else SerialReader.available_ports()
    if not ports:
        pytest.fail("No serial ports are visible to pyserial.")

    results = [
        SerialReader.probe_port_detailed(port, timeout_seconds=probe_seconds)
        for port in ports
    ]
    matches = [item for item in results if item.get("status") == "matched"]

    assert matches, _format_probe_report(results)

    # Keep this fairly broad. The firmware may identify itself by app, device,
    # a plain heartbeat or a tone event depending on timing and firmware version.
    first = matches[0]
    event = first.get("event")
    assert isinstance(event, dict), _format_probe_report(results)
    assert event.get("type") in {"hello", "heartbeat", "tone"}
