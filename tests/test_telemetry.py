from __future__ import annotations

import pytest

from morsewurst.core.telemetry import (
    derive_tone_from_key_pair,
    key_event_identity,
    normalize_key_event,
)


def test_normalize_key_event_preserves_version_and_live_metadata() -> None:
    event = normalize_key_event(
        {
            "v": 1,
            "type": "key",
            "src": "Straight",
            "state": "DOWN",
            "t": "123",
            "dit": 60000,
            "_host_received_time": 10.5,
        }
    )

    assert event["v"] == 1
    assert event["type"] == "key"
    assert event["src"] == "straight"
    assert event["state"] == "down"
    assert event["t"] == 123
    assert event["_host_received_time"] == 10.5


def test_key_event_identity_pairs_down_and_up_without_element_hint() -> None:
    down = {"v": 1, "type": "key", "src": "straight", "state": "down", "t": 100}
    up = {"v": 1, "type": "key", "src": "straight", "state": "up", "t": 200}

    assert key_event_identity(down) == key_event_identity(up)


def test_derive_tone_from_v1_down_up_keeps_microsecond_timing() -> None:
    tone = derive_tone_from_key_pair(
        {
            "v": 1,
            "type": "key",
            "src": "straight",
            "state": "down",
            "t": 100_000,
            "_host_received_time": 1.0,
        },
        {
            "v": 1,
            "type": "key",
            "src": "straight",
            "state": "up",
            "t": 160_000,
            "_host_received_time": 1.1,
        },
    )

    assert tone is not None
    assert tone["v"] == 1
    assert tone["type"] == "tone"
    assert tone["src"] == "straight"
    assert tone["t0"] == 100_000
    assert tone["t1"] == 160_000
    assert tone["dur"] == 60_000.0
    assert tone["_derived_from"] == "v1_key_down_up"
    assert tone["_host_received_time"] == 1.1


def test_derive_iambic_tone_preserves_element_hint() -> None:
    tone = derive_tone_from_key_pair(
        {"v": 1, "type": "key", "src": "iambic", "el": "-", "state": "down", "t": 1000, "unit": 500},
        {"v": 1, "type": "key", "src": "iambic", "el": "-", "state": "up", "t": 2500, "unit": 500},
    )

    assert tone is not None
    assert tone["el"] == "-"
    assert tone["unit"] == 500


def test_derive_tone_rejects_mismatched_or_negative_pairs() -> None:
    assert derive_tone_from_key_pair(
        {"v": 1, "type": "key", "src": "straight", "state": "down", "t": 200},
        {"v": 1, "type": "key", "src": "iambic", "state": "up", "t": 300},
    ) is None

    assert derive_tone_from_key_pair(
        {"v": 1, "type": "key", "src": "straight", "state": "down", "t": 300},
        {"v": 1, "type": "key", "src": "straight", "state": "up", "t": 200},
    ) is None


def test_normalize_key_event_rejects_invalid_state() -> None:
    with pytest.raises(ValueError):
        normalize_key_event({"v": 1, "type": "key", "src": "straight", "state": "pressed", "t": 1})
