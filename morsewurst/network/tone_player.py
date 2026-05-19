# ============================================================
# morsewurst/network/tone_player.py
# ============================================================

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import morsewurst.config as config
from morsewurst.network.protocol import SUPPORTED_WAVEFORMS

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover
    sd = None  # type: ignore[assignment]



StatusCallback = Callable[[str, str], None]


@dataclass(slots=True)
class ScheduledTone:
    start_monotonic: float
    end_monotonic: float
    frequency_hz: float
    volume: float
    waveform: str


class TonePlayer:
    """Sample-based scheduled tone player for remote Morse telemetry.

    The jitter buffer gives this player absolute monotonic start and end times.
    The audio callback then generates the requested waveform inside each output
    buffer. This keeps Morse rhythm stable even when network packets arrive with
    uneven timing.
    """

    def __init__(
        self,
        *,
        frequency_hz: float = 650.0,
        volume: float = 0.12,
        waveform: str = "sine",
        sample_rate: int = 48_000,
        channels: int = 2,
        blocksize: int = 2048,
        latency: str = "high",
        attack_seconds: float = 0.008,
        release_seconds: float = 0.008,
        output_device: Optional[int] = None,
        status_callback: Optional[StatusCallback] = None,
    ) -> None:
        self.frequency_hz = self._clamp_frequency(frequency_hz)
        self.volume = self._clamp_volume(volume)
        self.waveform = self._normalize_waveform(waveform)

        self.sample_rate = int(sample_rate)
        self.channels = max(1, int(channels))
        self.blocksize = int(blocksize)
        self.latency = latency

        self.attack_seconds = max(0.0005, float(attack_seconds))
        self.release_seconds = max(0.0005, float(release_seconds))

        self.output_device = output_device
        self.status_callback = status_callback

        self._lock = threading.RLock()
        self._tones: list[ScheduledTone] = []
        self._stream: Any = None
        self._started = False
        self._audio_clock_start_monotonic: Optional[float] = None
        self._frames_rendered = 0

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> None:
        with self._lock:
            if self._started:
                return

            if np is None:
                raise RuntimeError("numpy puuttuu. Asenna: python -m pip install numpy")

            if sd is None:
                raise RuntimeError("sounddevice puuttuu. Asenna: python -m pip install sounddevice")

            self._audio_clock_start_monotonic = None
            self._frames_rendered = 0

            self._stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                device=self.output_device,
                blocksize=self.blocksize,
                latency=self.latency,
                callback=self._audio_callback,
            )

            self._stream.start()
            self._started = True

        device_text = f", laite {self.output_device}" if self.output_device is not None else ""
        self._status("info", f"TonePlayer käynnissä{device_text}.")

    def stop(self) -> None:
        with self._lock:
            self._tones.clear()
            stream = self._stream
            self._stream = None
            self._started = False

        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass

            try:
                stream.close()
            except Exception:
                pass

        self._status("info", "TonePlayer pysäytetty.")

    def clear(self) -> None:
        with self._lock:
            self._tones.clear()

    def reset_clock(self) -> None:
        with self._lock:
            self._tones.clear()
            self._audio_clock_start_monotonic = time.monotonic()
            self._frames_rendered = 0

    def schedule_tone(
        self,
        *,
        start_monotonic: float,
        duration_seconds: float,
        frequency_hz: Optional[float] = None,
        volume: Optional[float] = None,
        waveform: Optional[str] = None,
    ) -> None:
        duration_seconds = float(duration_seconds)
        if duration_seconds <= 0.0:
            return

        tone_frequency = self._clamp_frequency(
            self.frequency_hz if frequency_hz is None else frequency_hz
        )
        tone_volume = self._clamp_volume(
            self.volume if volume is None else volume
        )
        tone_waveform = self._normalize_waveform(
            self.waveform if waveform is None else waveform
        )

        if tone_volume <= 0.0:
            return

        if not self._started:
            self.start()

        start = float(start_monotonic)
        end = start + duration_seconds

        with self._lock:
            self._tones.append(
                ScheduledTone(
                    start_monotonic=start,
                    end_monotonic=end,
                    frequency_hz=tone_frequency,
                    volume=tone_volume,
                    waveform=tone_waveform,
                )
            )

    def _audio_callback(self, outdata, frames: int, time_info, status) -> None:  # type: ignore[no-untyped-def]
        if np is None:
            outdata.fill(0)
            return

        if status:
            self._status("warning", f"Äänilaitteen huomautus: {status}")

        if frames <= 0:
            outdata.fill(0)
            return

        real_now = time.monotonic()
        drift_warning: str | None = None

        with self._lock:
            if self._audio_clock_start_monotonic is None:
                self._audio_clock_start_monotonic = real_now
                self._frames_rendered = 0

            block_start = (
                self._audio_clock_start_monotonic
                + (self._frames_rendered / float(self.sample_rate))
            )

            drift_seconds = real_now - block_start
            drift_limit_seconds = max(
                0.25,
                float(getattr(config, "NETWORK_AUDIO_CLOCK_DRIFT_RESET_SECONDS", 2.0)),
            )

            if abs(drift_seconds) > drift_limit_seconds:
                self._tones = [
                    tone
                    for tone in self._tones
                    if tone.end_monotonic >= real_now
                ]

                self._audio_clock_start_monotonic = real_now
                self._frames_rendered = 0
                block_start = real_now

                drift_warning = (
                    f"Äänikello synkronoitiin uudelleen. "
                    f"Poikkeama {drift_seconds:.1f} s."
                )

            self._frames_rendered += int(frames)

        if drift_warning is not None:
            self._status("warning", drift_warning)

        sample_offsets = np.arange(frames, dtype=np.float64) / float(self.sample_rate)
        times = block_start + sample_offsets
        block_end = float(times[-1])

        output = np.zeros(frames, dtype=np.float32)

        with self._lock:
            active_tones = list(self._tones)

            # Remove tones that are definitely over. The small grace period keeps
            # the list stable around callback boundary timing.
            self._tones = [
                tone
                for tone in self._tones
                if tone.end_monotonic >= block_start - 0.25
            ]

        for tone in active_tones:
            if tone.end_monotonic < block_start:
                continue

            if tone.start_monotonic > block_end:
                continue

            mask = (times >= tone.start_monotonic) & (times < tone.end_monotonic)
            if not np.any(mask):
                continue

            rel = times[mask] - tone.start_monotonic
            remaining = tone.end_monotonic - times[mask]

            phase = 2.0 * math.pi * tone.frequency_hz * rel
            wave = self._waveform(phase, tone.waveform)
            envelope = self._envelope(rel, remaining)

            output[mask] += (wave * envelope * tone.volume).astype(np.float32)

        output = np.clip(output, -1.0, 1.0)

        if outdata.ndim == 1:
            outdata[:] = output
            return

        outdata[:, :] = output.reshape(-1, 1)

    def _waveform(self, phase, waveform: str):  # type: ignore[no-untyped-def]
        assert np is not None

        sine = np.sin(phase)

        if waveform == "square":
            return np.where(sine >= 0.0, 1.0, -1.0)

        if waveform == "triangle":
            return (2.0 / math.pi) * np.arcsin(sine)

        if waveform == "saw":
            cycles = phase / (2.0 * math.pi)
            return 2.0 * (cycles - np.floor(cycles + 0.5))

        return sine

    def _envelope(self, rel, remaining):  # type: ignore[no-untyped-def]
        assert np is not None

        attack = np.minimum(1.0, rel / self.attack_seconds)
        release = np.minimum(1.0, remaining / self.release_seconds)

        return np.maximum(0.0, np.minimum(attack, release))

    def _normalize_waveform(self, waveform: object) -> str:
        value = str(waveform or "sine").strip().lower()

        if value not in SUPPORTED_WAVEFORMS:
            return "sine"

        return value

    def _clamp_volume(self, volume: object) -> float:
        try:
            value = float(volume)
        except Exception:
            value = 0.12

        return max(0.0, min(1.0, value))

    def _clamp_frequency(self, frequency_hz: object) -> float:
        try:
            value = float(frequency_hz)
        except Exception:
            value = 650.0

        return max(80.0, min(2400.0, value))

    def _status(self, level: str, text: str) -> None:
        if self.status_callback is None:
            return

        try:
            self.status_callback(level, text)
        except Exception:
            pass