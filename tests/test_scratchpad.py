from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import importlib.util
import sys
from pathlib import Path


def _project_root() -> Path:
    candidates = [Path.cwd(), *Path(__file__).resolve().parents]
    for candidate in candidates:
        path = candidate / "morsewurst" / "ui" / "controllers" / "scratchpad_controller.py"
        if path.exists():
            return candidate
    raise RuntimeError("Could not locate the Morsewurst project root.")


PROJECT_ROOT = _project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRATCHPAD_CONTROLLER_PATH = (
    PROJECT_ROOT / "morsewurst" / "ui" / "controllers" / "scratchpad_controller.py"
)
spec = importlib.util.spec_from_file_location(
    "scratchpad_controller_under_test",
    SCRATCHPAD_CONTROLLER_PATH,
)
assert spec is not None
assert spec.loader is not None
scratchpad_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scratchpad_module)
ScratchpadController = scratchpad_module.ScratchpadController

class DummyVar:
    def __init__(self, value: Any = None) -> None:
        self.value = value

    def get(self) -> Any:
        return self.value

    def set(self, value: Any) -> None:
        self.value = value


class DummyI18n:
    def t(self, _key: str, default: str = "", **kwargs: Any) -> str:
        try:
            return str(default).format(**kwargs)
        except Exception:
            return str(default)


class DummyStatusController:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def set_main_status(self, message: str, *, state: str = "normal") -> None:
        self.messages.append((message, state))


class DummyPracticeController:
    def __init__(self) -> None:
        self.update_count = 0

    def update_practice_buttons(self) -> None:
        self.update_count += 1


class DummyInputController:
    def __init__(self) -> None:
        self.cancel_count = 0

    def cancel_keyboard_morse_press(self) -> None:
        self.cancel_count += 1

    def is_keyboard_morse_tone_event(self, event: dict[str, Any]) -> bool:
        return event.get("device") == "keyboard" or event.get("mode") == "keyboard_straight"


class DummySettingsController:
    def __init__(self) -> None:
        self.save_count = 0

    def save_ui_settings_async(self) -> None:
        self.save_count += 1


class DummyUiHelpersController:
    def safe_float_var(
        self,
        var: Any,
        *,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            value = float(var.get())
        except Exception:
            value = float(default)
        return max(float(minimum), min(float(maximum), value))


class DummyDecoded:
    def __init__(
        self,
        text: str = "",
        *,
        pending_symbol: str = "",
        char_infos: list[dict[str, Any]] | None = None,
        element_infos: list[dict[str, Any]] | None = None,
        visual_unit_us: float = 100_000.0,
    ) -> None:
        self.text = text
        self.pending_symbol = pending_symbol
        self.char_infos = char_infos if char_infos is not None else []
        self.element_infos = element_infos if element_infos is not None else []
        self.visual_unit_us = visual_unit_us


class DummyLiveDecoder:
    def __init__(self, results: list[DummyDecoded] | None = None) -> None:
        self.results = list(results or [])
        self.events: list[dict[str, Any]] = []
        self.last_state = SimpleNamespace(decoded=None)

    def feed_event(self, event: dict[str, Any]) -> None:
        self.events.append(dict(event))

    def replace_events(self, events: list[dict[str, Any]]) -> None:
        self.events = [dict(event) for event in events]

    def decode(self, **_kwargs: Any) -> DummyDecoded:
        decoded = self.results.pop(0) if self.results else DummyDecoded()
        self.last_state = SimpleNamespace(decoded=decoded)
        return decoded

    def current_state(self) -> Any:
        return self.last_state


class DummyDecoderController:
    def __init__(self, live_decoder: DummyLiveDecoder | None = None) -> None:
        self.live_decoder = live_decoder or DummyLiveDecoder()

    def new_live_decoder(self, *, target_text: str = "") -> DummyLiveDecoder:
        del target_text
        return DummyLiveDecoder()

    def decoder_settings_from_ui(self) -> None:
        return None

    def adaptive_seed_unit_us(self) -> None:
        return None

    def decode_tone_events(self, *_args: Any, **_kwargs: Any) -> DummyDecoded:
        return DummyDecoded(visual_unit_us=100_000.0)


class DummyWindow:
    def __init__(self) -> None:
        self.text = ""
        self.inserted_chunks: list[str] = []
        self.refresh_count = 0
        self.clear_count = 0
        self.exists = True

    def winfo_exists(self) -> bool:
        return self.exists

    def text_content(self) -> str:
        return self.text

    def insert_decoded_text(self, text: str) -> None:
        self.inserted_chunks.append(text)
        self.text += text

    def clear_text(self, *, keep_session: bool = False) -> None:
        del keep_session
        self.clear_count += 1
        self.text = ""

    def refresh_from_controller(self) -> None:
        self.refresh_count += 1


class DummyApp:
    scratchpad_controller: Any

    def __init__(self) -> None:
        self.active_mode = "main"
        self.start_trigger_timestamps: list[float] = []
        self.i18n = DummyI18n()
        self.status_controller = DummyStatusController()
        self.practice_controller = DummyPracticeController()
        self.input_controller = DummyInputController()
        self.settings_controller = DummySettingsController()
        self.ui_helpers_controller = DummyUiHelpersController()
        self.decoder_controller = DummyDecoderController()
        self.scratchpad_window_geometry_var = DummyVar("800x600")
        self.scratchpad_raw_panel_visible_var = DummyVar(False)
        self.raw_telemetry_pixels_per_unit_var = DummyVar(8.0)
        self.scratchpad_window = DummyWindow()
        self.after_calls: list[tuple[int, Any]] = []
        self.cancelled_after_ids: list[str] = []

    def after(self, delay_ms: int, callback: Any) -> str:
        self.after_calls.append((delay_ms, callback))
        return f"after-{len(self.after_calls)}"

    def after_cancel(self, after_id: str) -> None:
        self.cancelled_after_ids.append(after_id)


def _new_controller() -> ScratchpadController:
    app = DummyApp()
    controller = ScratchpadController(app)  # type: ignore[arg-type]
    app.scratchpad_controller = controller
    controller.live_decoder = DummyLiveDecoder()
    return controller


def _char_infos(text: str, *, source: str = "iambic", wpm: float = 20.0) -> list[dict[str, Any]]:
    return [{"ch": ch, "source": source, "wpm": wpm} for ch in text]


@pytest.fixture(autouse=True)
def _silence_scratchpad_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scratchpad_module, "log_app_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(scratchpad_module, "log_app_exception", lambda *args, **kwargs: None)


def test_scratchpad_commits_only_new_decoded_char_infos() -> None:
    controller = _new_controller()
    window = controller.app.scratchpad_window
    controller.live_decoder = DummyLiveDecoder(
        [
            DummyDecoded("HE", char_infos=_char_infos("HE")),
            # Simulate a live adaptive re-segmentation where the full decoded
            # text changes but no new final character has been added yet.
            # The old string-delta implementation appended this whole text again.
            DummyDecoded("EH", char_infos=_char_infos("EH")),
            DummyDecoded("EHI", char_infos=_char_infos("EHI")),
        ]
    )

    controller.decode_and_append(force=True)
    controller.decode_and_append(force=True)
    controller.decode_and_append(force=True)

    assert window.inserted_chunks == ["HE", "I"]
    assert window.text == "HEI"
    assert controller.committed_char_info_count == 3
    assert controller.committed_decoded_text == "EHI"


def test_scratchpad_deduplicates_identical_tone_events() -> None:
    controller = _new_controller()
    tone = {
        "type": "tone",
        "src": "iambic",
        "t0": 100_000,
        "t1": 200_000,
        "dur": 100_000.0,
        "el": ".",
        "unit": 100_000,
    }

    controller.handle_tone_event(tone)
    controller.handle_tone_event(dict(tone))

    assert len(controller.events) == 1
    assert controller.source_counts["iambic"] == 1
    assert len(controller.accepted_tone_keys) == 1


def test_repeated_key_down_does_not_replace_original_press_start() -> None:
    controller = _new_controller()

    controller.handle_key_event(
        {"type": "key", "src": "straight", "state": "down", "t": 100_000, "pin": "D2"}
    )
    controller.handle_key_event(
        {"type": "key", "src": "straight", "state": "down", "t": 200_000, "pin": "D2"}
    )
    controller.handle_key_event(
        {"type": "key", "src": "straight", "state": "up", "t": 500_000, "pin": "D2"}
    )

    assert len(controller.events) == 1
    assert controller.events[0]["t0"] == 100_000
    assert controller.events[0]["t1"] == 500_000
    assert controller.events[0]["dur"] == 400_000.0


def test_average_wpm_uses_active_tone_span_not_idle_wall_clock() -> None:
    controller = _new_controller()
    controller.session_started_monotonic = -999_999.0
    controller.first_tone_t0_us = 1_000_000
    controller.last_activity_t1_us = 2_000_000
    controller.committed_decoded_text = "PARIS"

    elapsed_before = controller.elapsed_seconds()
    avg_before = controller.average_wpm(elapsed_before)
    elapsed_after = controller.elapsed_seconds()
    avg_after = controller.average_wpm(elapsed_after)

    assert elapsed_before == 1.0
    assert elapsed_after == 1.0
    assert avg_before == avg_after
    assert avg_before is not None
    assert avg_before > 0


def test_raw_tone_events_include_current_open_key_press() -> None:
    controller = _new_controller()

    controller.handle_key_event(
        {"type": "key", "src": "straight", "state": "down", "t": 100_000, "pin": "D2"}
    )

    tones = controller.raw_tone_events()

    assert len(tones) == 1
    assert tones[0]["type"] == "tone"
    assert tones[0]["src"] == "straight"
    assert tones[0]["t0"] == 100_000
    assert tones[0]["t1"] > tones[0]["t0"]
    assert tones[0]["_open"] is True


def test_reset_stats_only_keeps_visible_note_text_but_clears_session_data() -> None:
    controller = _new_controller()
    window = controller.app.scratchpad_window
    window.text = "KEEP THIS NOTE"

    controller.handle_tone_event(
        {
            "type": "tone",
            "src": "iambic",
            "t0": 100_000,
            "t1": 200_000,
            "dur": 100_000.0,
            "el": ".",
            "unit": 100_000,
        }
    )
    assert controller.events

    controller.reset_stats_only()

    assert window.text == "KEEP THIS NOTE"
    assert controller.events == []
    assert controller.source_counts == {}
    assert controller.accepted_tone_keys == set()


def test_paused_scratchpad_ignores_new_input_and_cancels_open_keyboard_press() -> None:
    controller = _new_controller()

    controller.toggle_paused()
    controller.handle_tone_event(
        {
            "type": "tone",
            "src": "iambic",
            "t0": 100_000,
            "t1": 200_000,
            "dur": 100_000.0,
        }
    )

    assert controller.paused is True
    assert controller.events == []
    assert controller.app.input_controller.cancel_count == 1
