# ============================================================
# morsewurst/core/debug_snapshot.py
# ============================================================

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import morsewurst.config as config


def debug_dir_path() -> Path:
    return Path(getattr(config, "DEBUG_DIR", config.DATA_DIR / "debug"))


def latest_debug_path() -> Path:
    return Path(
        getattr(
            config,
            "DEBUG_LATEST_SNAPSHOT_PATH",
            debug_dir_path() / "latest_round_debug.json",
        )
    )


def history_debug_path() -> Path:
    return Path(
        getattr(
            config,
            "DEBUG_HISTORY_PATH",
            debug_dir_path() / "debug_history.jsonl",
        )
    )


def _iso_datetime(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")

    return None


def _jsonable(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")

    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))

    if isinstance(value, dict):
        return {
            str(key): _jsonable(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]

    if isinstance(value, set):
        return sorted(_jsonable(item) for item in value)

    try:
        json.dumps(value)
        return value
    except Exception:
        return repr(value)


def _safe_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    try:
        return int(value)
    except Exception:
        return None


def _safe_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    try:
        return float(value)
    except Exception:
        return None


def _event_sort_key(event: dict[str, Any]) -> tuple[int, int]:
    t0 = _safe_int(event.get("t0")) or 0
    t1 = _safe_int(event.get("t1")) or t0
    return t0, t1


def _tone_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tones: list[dict[str, Any]] = []

    for event in events:
        if not isinstance(event, dict):
            continue

        if event.get("type") != "tone":
            continue

        t0 = _safe_int(event.get("t0"))
        t1 = _safe_int(event.get("t1"))
        dur = _safe_float(event.get("dur"))

        if t0 is None or t1 is None or dur is None:
            continue

        if t1 < t0:
            continue

        copied = dict(event)
        copied["t0"] = t0
        copied["t1"] = t1
        copied["dur"] = dur

        tones.append(copied)

    tones.sort(key=_event_sort_key)
    return tones


def _gap_lookup(decoded: Any) -> dict[tuple[int, int], dict[str, Any]]:
    lookup: dict[tuple[int, int], dict[str, Any]] = {}

    for gap in list(getattr(decoded, "gap_infos", []) or []):
        if not isinstance(gap, dict):
            continue

        from_t1 = _safe_int(gap.get("from_t1"))
        to_t0 = _safe_int(gap.get("to_t0"))

        if from_t1 is None or to_t0 is None:
            continue

        lookup[(from_t1, to_t0)] = gap

    return lookup


def _build_presses(
    tones: list[dict[str, Any]],
    decoded: Any,
) -> list[dict[str, Any]]:
    gap_infos = _gap_lookup(decoded)
    presses: list[dict[str, Any]] = []

    for index, event in enumerate(tones):
        previous_event = tones[index - 1] if index > 0 else None
        next_event = tones[index + 1] if index + 1 < len(tones) else None

        t0 = int(event["t0"])
        t1 = int(event["t1"])
        duration = float(event["dur"])

        gap_before_us: Optional[int] = None
        gap_before_info: Optional[dict[str, Any]] = None

        if previous_event is not None:
            previous_t1 = int(previous_event["t1"])
            gap_before_us = max(0, t0 - previous_t1)
            gap_before_info = gap_infos.get((previous_t1, t0))

        gap_after_us: Optional[int] = None

        if next_event is not None:
            gap_after_us = max(0, int(next_event["t0"]) - t1)

        host_received = _safe_float(event.get("_host_received_time"))

        presses.append(
            {
                "index": index,
                "source": event.get("src"),
                "element_hint": event.get("el"),
                "t0_us": t0,
                "t1_us": t1,
                "duration_us": duration,
                "duration_ms": round(duration / 1000.0, 3),
                "gap_before_us": gap_before_us,
                "gap_before_ms": (
                    None
                    if gap_before_us is None
                    else round(gap_before_us / 1000.0, 3)
                ),
                "gap_after_us": gap_after_us,
                "gap_after_ms": (
                    None
                    if gap_after_us is None
                    else round(gap_after_us / 1000.0, 3)
                ),
                "decoded_gap_before": _jsonable(gap_before_info),
                "firmware_unit_us": event.get("unit"),
                "firmware_dit_us": event.get("dit"),
                "firmware_wpm": event.get("wpm"),
                "host_received_time": host_received,
                "raw_event": _jsonable(event),
            }
        )

    return presses


def _build_timeline(
    tones: list[dict[str, Any]],
    decoded: Any,
    *,
    current_time_us: Optional[int],
) -> list[dict[str, Any]]:
    gap_infos = _gap_lookup(decoded)
    timeline: list[dict[str, Any]] = []

    for index, event in enumerate(tones):
        if index > 0:
            previous = tones[index - 1]
            previous_t1 = int(previous["t1"])
            current_t0 = int(event["t0"])
            gap_us = max(0, current_t0 - previous_t1)

            timeline.append(
                {
                    "type": "gap",
                    "index": index - 1,
                    "from_t1_us": previous_t1,
                    "to_t0_us": current_t0,
                    "duration_us": gap_us,
                    "duration_ms": round(gap_us / 1000.0, 3),
                    "decoded": _jsonable(gap_infos.get((previous_t1, current_t0))),
                }
            )

        duration = float(event["dur"])

        timeline.append(
            {
                "type": "tone",
                "index": index,
                "source": event.get("src"),
                "element_hint": event.get("el"),
                "t0_us": int(event["t0"]),
                "t1_us": int(event["t1"]),
                "duration_us": duration,
                "duration_ms": round(duration / 1000.0, 3),
            }
        )

    if tones and current_time_us is not None:
        last_t1 = int(tones[-1]["t1"])
        final_silence_us = max(0, int(current_time_us) - last_t1)

        timeline.append(
            {
                "type": "final_silence",
                "from_t1_us": last_t1,
                "to_current_time_us": int(current_time_us),
                "duration_us": final_silence_us,
                "duration_ms": round(final_silence_us / 1000.0, 3),
            }
        )

    return timeline


def _source_timing_summary(decoded: Any) -> dict[str, Any]:
    timing = getattr(decoded, "timing", None)

    if timing is None:
        return {}

    return _jsonable(timing)


def _settings_snapshot(app: Any) -> dict[str, Any]:
    ui_settings: dict[str, Any] = {}
    decoder_settings: dict[str, Any] = {}
    challenge_settings: dict[str, Any] = {}

    try:
        ui_settings = dict(app.settings_controller.ui_settings_data())
    except Exception:
        ui_settings = {}

    try:
        decoder_settings = asdict(app.decoder_controller.decoder_settings_from_ui())
    except Exception:
        decoder_settings = {}

    try:
        challenge_settings = asdict(app.settings)
    except Exception:
        challenge_settings = {}

    decoder_config = {
        name: _jsonable(getattr(config, name))
        for name in dir(config)
        if name.startswith("DECODER_")
    }

    timing_profiles: dict[str, Any] = {}
    try:
        timing_profiles = dict(getattr(app, "timing_profiles", {}) or {})
    except Exception:
        timing_profiles = {}

    return {
        "ui_settings": _jsonable(ui_settings),
        "decoder_settings": _jsonable(decoder_settings),
        "challenge_settings": _jsonable(challenge_settings),
        "decoder_config": decoder_config,
        "timing_profiles": _jsonable(timing_profiles),
    }


def build_round_debug_snapshot(
    *,
    app: Any,
    round_state: Any,
    decoded: Any,
    summary: Any = None,
    char_results: Optional[list[Any]] = None,
    current_time_us: Optional[int] = None,
) -> dict[str, Any]:
    events = list(getattr(round_state, "events", []) or [])
    tones = _tone_events(events)
    key_events = [event for event in events if isinstance(event, dict) and event.get("type") == "key"]

    first_t0 = int(tones[0]["t0"]) if tones else None
    last_t1 = int(tones[-1]["t1"]) if tones else None

    device_end_us = current_time_us

    if device_end_us is None:
        device_end_us = last_t1

    device_duration_us: Optional[int] = None

    if first_t0 is not None and device_end_us is not None:
        device_duration_us = max(0, int(device_end_us) - first_t0)

    snapshot = {
        "schema": {
            "name": "morsewurst_round_debug_snapshot",
            "version": 1,
        },
        "created_at": datetime.now().isoformat(timespec="microseconds"),
        "app": {
            "name": getattr(config, "APP_NAME", "Morsewurst"),
            "version": getattr(config, "APP_VERSION", ""),
        },
        "round": {
            "target": getattr(round_state, "target", ""),
            "telemetry_text": getattr(round_state, "telemetry_text", ""),
            "hid_text": getattr(round_state, "hid_text", ""),
            "decoded_text": getattr(decoded, "text", ""),
            "pending_symbol": getattr(decoded, "pending_symbol", ""),
            "finish_reason": getattr(round_state, "finish_reason", ""),
            "round_number": getattr(round_state, "round_number", None),
            "total_rounds": getattr(round_state, "total_rounds", None),
            "started_at": _iso_datetime(getattr(round_state, "started_at", None)),
            "finished_at": _iso_datetime(getattr(round_state, "finished_at", None)),
            "host_start_time": getattr(round_state, "host_start_time", None),
            "host_finished_time": getattr(round_state, "host_finished_time", None),
        },
        "device_time": {
            "first_tone_t0_us": first_t0,
            "last_tone_t1_us": last_t1,
            "current_time_us": device_end_us,
            "duration_from_first_tone_us": device_duration_us,
            "duration_from_first_tone_ms": (
                None
                if device_duration_us is None
                else round(device_duration_us / 1000.0, 3)
            ),
        },
        "counts": {
            "raw_event_count": len(events),
            "key_event_count": len(key_events),
            "derived_tone_count": len([event for event in tones if event.get("_derived_from") == "v1_key_down_up"]),
            "tone_count": len(tones),
            "decoded_char_count": len(getattr(decoded, "char_infos", []) or []),
            "decoded_element_count": len(getattr(decoded, "element_infos", []) or []),
            "decoded_gap_count": len(getattr(decoded, "gap_infos", []) or []),
        },
        "settings": _settings_snapshot(app),
        "timing": {
            "element_unit_us": getattr(decoded, "element_unit_us", None),
            "gap_unit_us": getattr(decoded, "gap_unit_us", None),
            "visual_unit_us": getattr(decoded, "visual_unit_us", None),
            "full_timing_estimate": _source_timing_summary(decoded),
        },
        "score_summary": _jsonable(summary),
        "character_results": _jsonable(char_results or []),
        "decoded": {
            "text": getattr(decoded, "text", ""),
            "symbols": _jsonable(getattr(decoded, "symbols", []) or []),
            "pending_symbol": getattr(decoded, "pending_symbol", ""),
            "char_infos": _jsonable(getattr(decoded, "char_infos", []) or []),
            "element_infos": _jsonable(getattr(decoded, "element_infos", []) or []),
            "gap_infos": _jsonable(getattr(decoded, "gap_infos", []) or []),
        },
        "presses": _build_presses(tones, decoded),
        "timeline": _build_timeline(
            tones,
            decoded,
            current_time_us=current_time_us,
        ),
        "raw_events": _jsonable(events),
    }

    return _jsonable(snapshot)


def write_debug_snapshot(
    snapshot: dict[str, Any],
    *,
    save_latest: bool = True,
    save_history: bool = False,
) -> None:
    debug_dir = debug_dir_path()
    debug_dir.mkdir(parents=True, exist_ok=True)

    if save_latest:
        latest_path = latest_debug_path()
        tmp_path = latest_path.with_suffix(latest_path.suffix + ".tmp")

        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(snapshot, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

        tmp_path.replace(latest_path)

    if save_history:
        history_path = history_debug_path()

        with history_path.open("a", encoding="utf-8") as handle:
            json.dump(snapshot, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")


def read_latest_debug_snapshot() -> Optional[dict[str, Any]]:
    latest_path = latest_debug_path()

    if latest_path.exists():
        try:
            with latest_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)

            if isinstance(data, dict):
                return data
        except Exception:
            pass

    history_path = history_debug_path()

    if not history_path.exists():
        return None

    try:
        lines = history_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None

    for line in reversed(lines):
        line = line.strip()

        if not line:
            continue

        try:
            data = json.loads(line)
        except Exception:
            continue

        if isinstance(data, dict):
            return data

    return None


def read_latest_debug_text() -> str:
    snapshot = read_latest_debug_snapshot()

    if snapshot is None:
        return ""

    return json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"


def read_history_debug_text(*, pretty: bool = True) -> str:
    path = history_debug_path()

    if not path.exists():
        return ""

    try:
        raw_text = path.read_text(encoding="utf-8")
    except Exception:
        return ""

    if not pretty:
        return raw_text

    blocks: list[str] = []

    for index, line in enumerate(raw_text.splitlines(), start=1):
        line = line.strip()

        if not line:
            continue

        try:
            data = json.loads(line)
        except Exception:
            blocks.append(f"===== Invalid JSONL row {index} =====\n{line}")
            continue

        blocks.append(
            f"===== Debug snapshot {index} =====\n"
            + json.dumps(data, ensure_ascii=False, indent=2)
        )

    return "\n\n".join(blocks) + ("\n" if blocks else "")


def clear_debug_files() -> int:
    deleted = 0

    for path in [latest_debug_path(), history_debug_path()]:
        try:
            if path.exists():
                path.unlink()
                deleted += 1
        except Exception:
            pass

    return deleted