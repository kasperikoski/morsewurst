from __future__ import annotations

from morsewurst.network.models import PlaybackSettings
from morsewurst.network.protocol import make_key_message

from morsewurst.network.jitter_buffer import JitterBuffer, _as_int, _round_up_ms
from morsewurst.network.models import PlaybackSettings


class FakeTonePlayer:
    def __init__(self) -> None:
        self.started = False
        self.start_calls = 0
        self.clear_calls = 0
        self.scheduled: list[dict[str, float | str]] = []

    def start(self) -> None:
        self.started = True
        self.start_calls += 1

    def clear(self) -> None:
        self.clear_calls += 1
        self.scheduled.clear()

    def schedule_tone(self, **kwargs) -> None:
        self.scheduled.append(kwargs)


class FailingTonePlayer(FakeTonePlayer):
    def start(self) -> None:
        raise RuntimeError("audio unavailable")


def test_round_up_ms_and_as_int_helpers_are_defensive() -> None:
    assert _round_up_ms(101, 50) == 150
    assert _round_up_ms(-10, 50) == 0
    assert _round_up_ms(10, 0) == 10
    assert _as_int("12", default=0) == 12
    assert _as_int(True, default=7) == 7
    assert _as_int("bad", default=7) == 7


def test_jitter_buffer_schedules_valid_tone_message() -> None:
    player = FakeTonePlayer()
    statuses: list[tuple[str, str]] = []
    buffer = JitterBuffer(
        player,  # type: ignore[arg-type]
        playback_settings=PlaybackSettings(jitter_buffer_ms=50, frequency_hz=700.0, volume=0.5, waveform="square"),
        status_callback=lambda level, text: statuses.append((level, text)),
    )

    buffer.push_message(
        {
            "type": "tone",
            "sender_id": "client-1",
            "stream_id": "stream-1",
            "seq": 1,
            "tone": {"type": "tone", "t0": 0, "t1": 100_000, "dur": 100_000, "el": "."},
        }
    )

    assert player.start_calls == 1
    assert len(player.scheduled) == 1
    assert player.scheduled[0]["duration_seconds"] == 0.1
    assert player.scheduled[0]["frequency_hz"] == 700.0
    assert player.scheduled[0]["volume"] == 0.5
    assert player.scheduled[0]["waveform"] == "square"
    assert any(level == "info" and "Uusi vastaanottopuskuri" in text for level, text in statuses)


def test_jitter_buffer_ignores_disabled_playback_and_reports_invalid_messages() -> None:
    player = FakeTonePlayer()
    statuses: list[tuple[str, str]] = []
    disabled = JitterBuffer(player, playback_settings=PlaybackSettings(enabled=False))  # type: ignore[arg-type]
    disabled.push_message({"type": "tone", "tone": {"type": "tone", "t0": 0, "t1": 1, "dur": 1}})

    assert player.start_calls == 0
    assert player.scheduled == []

    enabled = JitterBuffer(player, playback_settings=PlaybackSettings(enabled=True), status_callback=lambda level, text: statuses.append((level, text)))  # type: ignore[arg-type]
    enabled.push_message({"type": "tone", "tone": {"type": "tone", "t0": 10, "t1": 1, "dur": 1}})

    assert player.scheduled == []
    assert statuses and statuses[-1][0] == "warning"



def test_jitter_buffer_resets_when_sequence_goes_backwards() -> None:
    player = FakeTonePlayer()
    statuses: list[tuple[str, str]] = []
    buffer = JitterBuffer(
        player,  # type: ignore[arg-type]
        playback_settings=PlaybackSettings(jitter_buffer_ms=10),
        status_callback=lambda level, text: statuses.append((level, text)),
    )

    first = {
        "type": "tone",
        "sender_id": "client-1",
        "stream_id": "stream-1",
        "seq": 10,
        "tone": {"type": "tone", "t0": 100_000, "t1": 150_000, "dur": 50_000},
    }
    second = {
        "type": "tone",
        "sender_id": "client-1",
        "stream_id": "stream-1",
        "seq": 2,
        "tone": {"type": "tone", "t0": 160_000, "t1": 210_000, "dur": 50_000},
    }

    buffer.push_message(first)
    buffer.push_message(second)

    assert len(player.scheduled) == 2
    reset_statuses = [
        text
        for level, text in statuses
        if level == "info" and "Uusi vastaanottopuskuri" in text
    ]
    assert len(reset_statuses) == 2


def test_jitter_buffer_drops_stale_tone_only_reports_first_stale_drop() -> None:
    player = FakeTonePlayer()
    statuses: list[tuple[str, str]] = []
    buffer = JitterBuffer(
        player,  # type: ignore[arg-type]
        playback_settings=PlaybackSettings(jitter_buffer_ms=0),
        drop_late_ms=1,
        late_grace_ms=0,
        status_callback=lambda level, text: statuses.append((level, text)),
    )

    message = {
        "type": "tone",
        "sender_id": "client-1",
        "stream_id": "stream-1",
        "seq": 1,
        "tone": {"type": "tone", "t0": 0, "t1": 100_000, "dur": 100_000},
    }
    buffer.push_message(message)

    state = next(iter(buffer._streams.values()))
    state.playback_base_monotonic -= 10.0

    stale_message = {
        "type": "tone",
        "sender_id": "client-1",
        "stream_id": "stream-1",
        "seq": 2,
        "tone": {"type": "tone", "t0": 100_000, "t1": 200_000, "dur": 100_000},
    }
    buffer.push_message(stale_message)
    buffer.push_message(
        {
            **stale_message,
            "seq": 3,
            "tone": {"type": "tone", "t0": 200_000, "t1": 300_000, "dur": 100_000},
        }
    )

    warning_statuses = [text for level, text in statuses if level == "warning"]
    stale_statuses = [text for text in warning_statuses if "Vanhat vastaanottoäänet ohitettiin" in text]
    assert len(stale_statuses) == 1
    assert player.clear_calls >= 2


def test_jitter_buffer_reports_audio_start_failure_without_scheduling() -> None:
    player = FailingTonePlayer()
    statuses: list[tuple[str, str]] = []
    buffer = JitterBuffer(
        player,  # type: ignore[arg-type]
        playback_settings=PlaybackSettings(enabled=True),
        status_callback=lambda level, text: statuses.append((level, text)),
    )

    buffer.push_message(
        {
            "type": "tone",
            "sender_id": "client-1",
            "stream_id": "stream-1",
            "seq": 1,
            "tone": {"type": "tone", "t0": 0, "t1": 100_000, "dur": 100_000},
        }
    )

    assert player.scheduled == []
    assert statuses[-1][0] == "error"
    assert "Audio playback could not be started" in statuses[-1][1]


def test_jitter_buffer_ignores_zero_duration_tone_without_starting_player() -> None:
    player = FakeTonePlayer()
    buffer = JitterBuffer(player, playback_settings=PlaybackSettings(enabled=True))  # type: ignore[arg-type]

    buffer.push_message(
        {
            "type": "tone",
            "sender_id": "client-1",
            "stream_id": "stream-1",
            "seq": 1,
            "tone": {"type": "tone", "t0": 0, "t1": 0, "dur": 0},
        }
    )

    assert player.start_calls == 0
    assert player.scheduled == []


class FakeLiveTonePlayerForKeyStream:
    def __init__(self) -> None:
        self.started = False
        self.start_calls = 0
        self.clear_calls = 0
        self.scheduled: list[dict[str, object]] = []
        self.live_starts: list[dict[str, object]] = []
        self.live_stops: list[dict[str, object]] = []

    def start(self) -> None:
        self.started = True
        self.start_calls += 1

    def clear(self) -> None:
        self.clear_calls += 1
        self.scheduled.clear()
        self.live_starts.clear()
        self.live_stops.clear()

    def schedule_tone(self, **kwargs: object) -> None:
        self.scheduled.append(kwargs)

    def start_live_tone(self, **kwargs: object) -> None:
        self.live_starts.append(kwargs)

    def stop_live_tone(self, **kwargs: object) -> None:
        self.live_stops.append(kwargs)


def test_jitter_buffer_plays_key_down_up_as_live_tone() -> None:
    player = FakeLiveTonePlayerForKeyStream()
    buffer = JitterBuffer(
        player,  # type: ignore[arg-type]
        playback_settings=PlaybackSettings(
            enabled=True,
            jitter_buffer_ms=0,
            frequency_hz=700.0,
            volume=0.5,
            waveform="square",
        ),
        late_grace_ms=10_000,
        drop_late_ms=20_000,
    )

    down_message = make_key_message(
        key_event={"v": 1, "type": "key", "src": "straight", "state": "down", "t": 1_000_000},
        sender_id="client-1",
        sender_name="Tester",
        seq=1,
        stream_id="stream-1",
    )
    up_message = make_key_message(
        key_event={"v": 1, "type": "key", "src": "straight", "state": "up", "t": 1_100_000},
        sender_id="client-1",
        sender_name="Tester",
        seq=2,
        stream_id="stream-1",
    )

    buffer.push_message(down_message)
    buffer.push_message(up_message)

    assert player.start_calls == 1
    assert player.scheduled == []
    assert len(player.live_starts) == 1
    assert len(player.live_stops) == 1
    assert player.live_starts[0]["key"] == player.live_stops[0]["key"]
    assert player.live_starts[0]["frequency_hz"] == 700.0
    assert player.live_starts[0]["volume"] == 0.5
    assert player.live_starts[0]["waveform"] == "square"


def test_jitter_buffer_does_not_collapse_repeated_straight_key_taps() -> None:
    player = FakeLiveTonePlayerForKeyStream()
    buffer = JitterBuffer(
        player,  # type: ignore[arg-type]
        playback_settings=PlaybackSettings(
            enabled=True,
            jitter_buffer_ms=750,
            frequency_hz=700.0,
            volume=0.5,
            waveform="square",
        ),
        late_grace_ms=10_000,
        drop_late_ms=20_000,
    )

    messages = [
        make_key_message(
            key_event={"v": 1, "type": "key", "src": "straight", "state": "down", "t": 1_000_000},
            sender_id="client-1",
            sender_name="Tester",
            seq=1,
            stream_id="stream-1",
        ),
        make_key_message(
            key_event={"v": 1, "type": "key", "src": "straight", "state": "up", "t": 1_080_000},
            sender_id="client-1",
            sender_name="Tester",
            seq=2,
            stream_id="stream-1",
        ),
        make_key_message(
            key_event={"v": 1, "type": "key", "src": "straight", "state": "down", "t": 1_180_000},
            sender_id="client-1",
            sender_name="Tester",
            seq=3,
            stream_id="stream-1",
        ),
        make_key_message(
            key_event={"v": 1, "type": "key", "src": "straight", "state": "up", "t": 1_260_000},
            sender_id="client-1",
            sender_name="Tester",
            seq=4,
            stream_id="stream-1",
        ),
    ]

    for message in messages:
        buffer.push_message(message)

    assert player.scheduled == []
    assert len(player.live_starts) == 2
    assert len(player.live_stops) == 2

    first_key = player.live_starts[0]["key"]
    second_key = player.live_starts[1]["key"]

    assert first_key != second_key
    assert player.live_stops[0]["key"] == first_key
    assert player.live_stops[1]["key"] == second_key
