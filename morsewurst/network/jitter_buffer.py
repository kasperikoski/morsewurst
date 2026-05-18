# ============================================================
# morsewurst/network/jitter_buffer.py
# ============================================================

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import morsewurst.config as config
from morsewurst.network.models import PlaybackSettings
from morsewurst.network.protocol import ProtocolError, validate_tone_message
from morsewurst.network.tone_player import TonePlayer


StatusCallback = Callable[[str, str], None]
JITTER_BUFFER_STEP_MS = 50
JITTER_BUFFER_SAFETY_MARGIN_MS = 50
JITTER_BUFFER_MAX_MS = 5000


@dataclass(slots=True)
class StreamPlaybackState:
    sender_id: str
    stream_id: str
    base_t0_us: int
    playback_base_monotonic: float
    last_t0_us: int
    last_seq: int = -1
    late_events: int = 0
    total_events: int = 0


class JitterBuffer:
    """Converts remote microsecond tone telemetry into scheduled local audio."""

    def __init__(
        self,
        tone_player: TonePlayer,
        *,
        playback_settings: Optional[PlaybackSettings] = None,
        late_grace_ms: int = 80,
        drop_late_ms: int = 2000,
        resync_idle_gap_ms: int = 3000,
        status_callback: Optional[StatusCallback] = None,
    ) -> None:
        self.tone_player = tone_player
        self.playback_settings = playback_settings or PlaybackSettings()
        self.late_grace_ms = int(late_grace_ms)
        self.drop_late_ms = int(drop_late_ms)
        self.resync_idle_gap_ms = int(resync_idle_gap_ms)
        self.status_callback = status_callback
        self._streams: Dict[tuple[str, str], StreamPlaybackState] = {}
        self._stale_drop_notice_sent = False

    def update_playback_settings(self, settings: PlaybackSettings) -> None:
        self.playback_settings = settings

    def clear(self) -> None:
        self._streams.clear()
        self._stale_drop_notice_sent = False
        self.tone_player.clear()

    def push_message(self, message: Dict[str, Any]) -> None:
        if not self.playback_settings.enabled:
            return

        try:
            tone = validate_tone_message(message)
        except ProtocolError as exc:
            self._status("warning", f"Virheellinen tone-viesti ohitettiin: {exc}")
            return

        sender_id = str(message.get("sender_id") or "unknown")
        stream_id = str(message.get("stream_id") or sender_id)
        seq = _as_int(message.get("seq"), default=-1)
        t0_us = int(tone["t0"])
        duration_seconds = max(0.0, float(tone["dur"]) / 1_000_000.0)

        if duration_seconds <= 0.0:
            return

        if not self.tone_player.started:
            try:
                self.tone_player.start()
            except Exception as exc:
                self._status("error", f"Audio playback could not be started: {exc}")
                return

        state = self._state_for(sender_id=sender_id, stream_id=stream_id, t0_us=t0_us, seq=seq)
        scheduled_start = state.playback_base_monotonic + ((t0_us - state.base_t0_us) / 1_000_000.0)

        now = time.monotonic()
        lateness = now - scheduled_start

        drop_late_seconds = self.drop_late_ms / 1000.0
        late_grace_seconds = self.late_grace_ms / 1000.0
        stale_drop_seconds = max(
            drop_late_seconds,
            float(getattr(config, "NETWORK_STALE_TONE_DROP_MS", 5000)) / 1000.0,
        )

        if lateness > stale_drop_seconds:
            self.tone_player.clear()
            state.late_events += 1
            state.total_events += 1
            state.last_t0_us = max(state.last_t0_us, t0_us)
            state.last_seq = max(state.last_seq, seq)

            if not self._stale_drop_notice_sent:
                self._stale_drop_notice_sent = True
                self._status(
                    "warning",
                    "Vanhat vastaanottoäänet ohitettiin tauon tai yhteyskatkon jälkeen.",
                )

            return

        if lateness > drop_late_seconds:
            self.tone_player.clear()
            state.late_events += 1
            state.total_events += 1
            state.last_t0_us = max(state.last_t0_us, t0_us)
            state.last_seq = max(state.last_seq, seq)

            lateness_ms = lateness * 1000.0
            self._status(
                "warning",
                (
                    f"Liian myöhässä tullut tone hylättiin. "
                    f"Myöhästyminen {lateness_ms:.0f} ms."
                    f"{self._jitter_buffer_hint(lateness_ms)}"
                ),
            )
            return

        if lateness > late_grace_seconds:
            state.late_events += 1
            scheduled_start = now + 0.010
            lateness_ms = lateness * 1000.0
            self._status(
                "warning",
                (
                    f"Myöhässä tullut tone ajoitettiin heti. "
                    f"Myöhästyminen {lateness_ms:.0f} ms."
                    f"{self._jitter_buffer_hint(lateness_ms)}"
                ),
            )

        state.total_events += 1
        state.last_t0_us = max(state.last_t0_us, t0_us)
        state.last_seq = max(state.last_seq, seq)
        self._stale_drop_notice_sent = False

        self.tone_player.schedule_tone(
            start_monotonic=scheduled_start,
            duration_seconds=duration_seconds,
            frequency_hz=self.playback_settings.frequency_hz,
            volume=self.playback_settings.volume,
            waveform=self.playback_settings.waveform,
        )

    def _state_for(self, *, sender_id: str, stream_id: str, t0_us: int, seq: int) -> StreamPlaybackState:
        key = (sender_id, stream_id)
        state = self._streams.get(key)

        should_reset = state is None
        if state is not None:
            gap_us = t0_us - state.last_t0_us
            if gap_us > self.resync_idle_gap_ms * 1000:
                should_reset = True
            if seq >= 0 and state.last_seq >= 0 and seq < state.last_seq:
                should_reset = True

        if should_reset:
            state = StreamPlaybackState(
                sender_id=sender_id,
                stream_id=stream_id,
                base_t0_us=t0_us,
                playback_base_monotonic=time.monotonic() + (self.playback_settings.jitter_buffer_ms / 1000.0),
                last_t0_us=t0_us,
                last_seq=seq,
            )
            self._streams[key] = state
            self._status(
                "info",
                f"Uusi vastaanottopuskuri: {sender_id}, buffer {self.playback_settings.jitter_buffer_ms} ms.",
            )

        return state
    

    def _jitter_buffer_hint(self, lateness_ms: float) -> str:
        current_ms = max(
            0,
            _as_int(self.playback_settings.jitter_buffer_ms, default=750),
        )

        if current_ms >= JITTER_BUFFER_MAX_MS:
            return " Viivepuskuri on jo maksimi."

        lateness_whole_ms = max(0, math.ceil(lateness_ms))
        target_ms = current_ms + lateness_whole_ms + JITTER_BUFFER_SAFETY_MARGIN_MS
        recommended_ms = _round_up_ms(target_ms, JITTER_BUFFER_STEP_MS)
        recommended_ms = min(recommended_ms, JITTER_BUFFER_MAX_MS)

        if recommended_ms <= current_ms:
            return ""

        return f" Nosta viivepuskuri arvoon {recommended_ms} ms."


    def _status(self, level: str, text: str) -> None:
        if self.status_callback is None:
            return
        try:
            self.status_callback(level, text)
        except Exception:
            pass


def _round_up_ms(value: int, step: int) -> int:
    step = max(1, int(step))
    value = max(0, int(value))
    return ((value + step - 1) // step) * step


def _as_int(value: Any, *, default: int) -> int:
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except Exception:
        return default
