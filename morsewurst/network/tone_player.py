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
from morsewurst.audio.noise import RadioNoiseGenerator, RadioNoiseSettings
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


@dataclass(slots=True)
class ScheduledNoiseDuck:
    start_monotonic: float
    end_monotonic: float
    depth: float
    attack_seconds: float
    release_seconds: float
    kind: str


@dataclass(slots=True)
class LiveTone:
    key: str
    start_monotonic: float
    end_monotonic: Optional[float]
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
        self._live_tones: dict[str, LiveTone] = {}
        self._stream: Any = None
        self._started = False
        self._audio_clock_start_monotonic: Optional[float] = None
        self._frames_rendered = 0

        self._radio_noise_enabled = False
        self._radio_noise_volume_percent = 0.0
        self._radio_noise_profile = str(getattr(config, "NETWORK_RADIO_NOISE_PROFILE_DEFAULT", "radio"))
        self._radio_noise_tone = str(getattr(config, "NETWORK_RADIO_NOISE_TONE_DEFAULT", "low"))
        self._radio_noise_tx_ducking_enabled = bool(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_ENABLED", True))
        self._radio_noise_tx_ducking_depth_percent = float(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_DEPTH_PERCENT", 85))
        self._radio_noise_tx_ducking_attack_ms = float(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_ATTACK_MS", 60))
        self._radio_noise_tx_ducking_hold_ms = float(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_HOLD_MS", 350))
        self._radio_noise_tx_ducking_release_ms = float(getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_RELEASE_MS", 500))
        self._radio_noise_rx_ducking_enabled = bool(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_ENABLED", False))
        self._radio_noise_rx_ducking_depth_percent = float(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_DEPTH_PERCENT", 45))
        self._radio_noise_rx_ducking_attack_ms = float(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_ATTACK_MS", 80))
        self._radio_noise_rx_ducking_hold_ms = float(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_HOLD_MS", 250))
        self._radio_noise_rx_ducking_release_ms = float(getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_RELEASE_MS", 450))
        self._radio_noise: RadioNoiseGenerator | None = None
        self._radio_noise_sample_index = 0
        self._radio_noise_gain = 0.0
        self._radio_noise_target_gain = 0.0
        self._radio_noise_stop_after_fade = False
        self._radio_noise_duck_gain = 1.0
        self._radio_noise_ducks: list[ScheduledNoiseDuck] = []

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

    def stop(self, *, fade_radio_noise: bool = True) -> None:
        if fade_radio_noise:
            self.stop_background_noise(fade=True)
            self._wait_for_radio_noise_fade_out()

        with self._lock:
            self._tones.clear()
            self._live_tones.clear()
            self._radio_noise_ducks.clear()
            self._radio_noise = None
            self._radio_noise_gain = 0.0
            self._radio_noise_target_gain = 0.0
            self._radio_noise_stop_after_fade = False
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
            self._live_tones.clear()

    def reset_clock(self) -> None:
        with self._lock:
            self._tones.clear()
            self._live_tones.clear()
            self._audio_clock_start_monotonic = time.monotonic()
            self._frames_rendered = 0

    def configure_background_noise(
        self,
        *,
        enabled: bool,
        volume: float,
        profile: str = "radio",
        tone: str = "low",
        tx_ducking_enabled: bool = True,
        tx_ducking_depth_percent: int | float | None = None,
        tx_ducking_attack_ms: int | float | None = None,
        tx_ducking_hold_ms: int | float | None = None,
        tx_ducking_release_ms: int | float | None = None,
        rx_ducking_enabled: bool = False,
        rx_ducking_depth_percent: int | float | None = None,
        rx_ducking_attack_ms: int | float | None = None,
        rx_ducking_hold_ms: int | float | None = None,
        rx_ducking_release_ms: int | float | None = None,
    ) -> None:
        """Configure local room background noise without starting it yet."""

        volume_percent = self._clamp_radio_noise_volume_percent(float(volume) * 100.0)
        profile_key = self._normalize_radio_noise_profile(profile)
        tone_key = self._normalize_radio_noise_tone(tone)

        with self._lock:
            changed = (
                self._radio_noise_volume_percent != volume_percent
                or self._radio_noise_profile != profile_key
                or self._radio_noise_tone != tone_key
            )
            self._radio_noise_enabled = bool(enabled)
            self._radio_noise_volume_percent = volume_percent
            self._radio_noise_profile = profile_key
            self._radio_noise_tone = tone_key
            self._radio_noise_tx_ducking_enabled = bool(tx_ducking_enabled)
            self._radio_noise_tx_ducking_depth_percent = self._clamp_percent(
                tx_ducking_depth_percent,
                getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_DEPTH_PERCENT", 85),
                maximum=95.0,
            )
            self._radio_noise_tx_ducking_attack_ms = self._clamp_ms(
                tx_ducking_attack_ms,
                getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_ATTACK_MS", 60),
                minimum=1.0,
                maximum=500.0,
            )
            self._radio_noise_tx_ducking_hold_ms = self._clamp_ms(
                tx_ducking_hold_ms,
                getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_HOLD_MS", 350),
                minimum=1.0,
                maximum=1500.0,
            )
            self._radio_noise_tx_ducking_release_ms = self._clamp_ms(
                tx_ducking_release_ms,
                getattr(config, "NETWORK_RADIO_NOISE_TX_DUCKING_RELEASE_MS", 500),
                minimum=1.0,
                maximum=2000.0,
            )
            self._radio_noise_rx_ducking_enabled = bool(rx_ducking_enabled)
            self._radio_noise_rx_ducking_depth_percent = self._clamp_percent(
                rx_ducking_depth_percent,
                getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_DEPTH_PERCENT", 45),
                maximum=95.0,
            )
            self._radio_noise_rx_ducking_attack_ms = self._clamp_ms(
                rx_ducking_attack_ms,
                getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_ATTACK_MS", 80),
                minimum=1.0,
                maximum=500.0,
            )
            self._radio_noise_rx_ducking_hold_ms = self._clamp_ms(
                rx_ducking_hold_ms,
                getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_HOLD_MS", 250),
                minimum=1.0,
                maximum=1500.0,
            )
            self._radio_noise_rx_ducking_release_ms = self._clamp_ms(
                rx_ducking_release_ms,
                getattr(config, "NETWORK_RADIO_NOISE_RX_DUCKING_RELEASE_MS", 450),
                minimum=1.0,
                maximum=2000.0,
            )

            if not self._radio_noise_enabled:
                self._radio_noise_target_gain = 0.0
                self._radio_noise_stop_after_fade = True
                return

            if self._radio_noise is not None and not changed:
                return

            self._radio_noise = self._make_radio_noise_generator_locked()
            self._radio_noise_sample_index = 0
            self._radio_noise_duck_gain = 1.0

    def start_background_noise(self) -> None:
        """Fade in local radio-channel noise for an active network room."""

        with self._lock:
            if not self._radio_noise_enabled or self._radio_noise_volume_percent <= 0.0:
                return

            if self._radio_noise is None:
                self._radio_noise = self._make_radio_noise_generator_locked()
                self._radio_noise_sample_index = 0

            self._radio_noise_stop_after_fade = False
            self._radio_noise_target_gain = 1.0

        if not self._started:
            self.start()

    def stop_background_noise(self, *, fade: bool = True) -> None:
        """Fade out local radio-channel noise. The audio stream may keep running."""

        with self._lock:
            self._radio_noise_target_gain = 0.0
            self._radio_noise_stop_after_fade = bool(fade)
            if not fade:
                self._radio_noise = None
                self._radio_noise_gain = 0.0
                self._radio_noise_ducks.clear()

    def duck_noise(
        self,
        *,
        kind: str,
        start_monotonic: float | None = None,
        duration_seconds: float = 0.0,
    ) -> None:
        """Temporarily reduce room noise during local TX or remote RX tones."""

        kind_key = str(kind or "rx").strip().lower()
        if kind_key not in {"tx", "rx"}:
            kind_key = "rx"

        if kind_key == "tx" and not self._radio_noise_tx_ducking_enabled:
            return
        if kind_key == "rx" and not self._radio_noise_rx_ducking_enabled:
            return

        start = time.monotonic() if start_monotonic is None else float(start_monotonic)
        duration = max(0.0, float(duration_seconds))
        hold_ms = self._radio_noise_duck_config(kind_key, "hold_ms")
        end = start + duration + (hold_ms / 1000.0)

        with self._lock:
            if not self._radio_noise_enabled:
                return

            self._radio_noise_ducks.append(
                ScheduledNoiseDuck(
                    start_monotonic=start,
                    end_monotonic=end,
                    depth=self._radio_noise_duck_config(kind_key, "depth_percent") / 100.0,
                    attack_seconds=max(0.001, self._radio_noise_duck_config(kind_key, "attack_ms") / 1000.0),
                    release_seconds=max(0.001, self._radio_noise_duck_config(kind_key, "release_ms") / 1000.0),
                    kind=kind_key,
                )
            )

    def start_live_tone(
        self,
        *,
        key: str,
        start_monotonic: float,
        frequency_hz: Optional[float] = None,
        volume: Optional[float] = None,
        waveform: Optional[str] = None,
    ) -> None:
        """Start a network receive tone whose duration is not known yet."""
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

        with self._lock:
            self._live_tones[str(key)] = LiveTone(
                key=str(key),
                start_monotonic=float(start_monotonic),
                end_monotonic=None,
                frequency_hz=tone_frequency,
                volume=tone_volume,
                waveform=tone_waveform,
            )

    def stop_live_tone(self, *, key: str, end_monotonic: Optional[float] = None) -> None:
        """Close a network receive tone that was opened by a V1 key down event."""
        with self._lock:
            tone = self._live_tones.get(str(key))
            if tone is None:
                return
            tone.end_monotonic = time.monotonic() if end_monotonic is None else float(end_monotonic)

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

        self.duck_noise(kind="rx", start_monotonic=start, duration_seconds=duration_seconds)

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
            active_live_tones = list(self._live_tones.values())

            # Remove tones that are definitely over. The small grace period keeps
            # the list stable around callback boundary timing.
            self._tones = [
                tone
                for tone in self._tones
                if tone.end_monotonic >= block_start - 0.25
            ]

            # Live tones are opened by V1 key/down and closed by V1 key/up.
            # Keep an ended live tone briefly so the callback can render the
            # release envelope after the up event, then remove it.
            self._live_tones = {
                key: tone
                for key, tone in self._live_tones.items()
                if tone.end_monotonic is None
                or tone.end_monotonic + self.release_seconds >= block_start - 0.25
            }

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

        for tone in active_live_tones:
            if tone.start_monotonic > block_end:
                continue

            if tone.end_monotonic is None:
                if block_end < tone.start_monotonic:
                    continue
                mask = times >= tone.start_monotonic
                if not np.any(mask):
                    continue
                rel = times[mask] - tone.start_monotonic
                remaining = np.full_like(rel, 1_000_000.0, dtype=np.float64)
            else:
                release_end = tone.end_monotonic + self.release_seconds
                if release_end < block_start:
                    continue
                mask = (times >= tone.start_monotonic) & (times < release_end)
                if not np.any(mask):
                    continue
                rel = times[mask] - tone.start_monotonic
                remaining = release_end - times[mask]

            phase = 2.0 * math.pi * tone.frequency_hz * rel
            wave = self._waveform(phase, tone.waveform)
            envelope = self._envelope(rel, remaining)

            output[mask] += (wave * envelope * tone.volume).astype(np.float32)

        noise = self._render_radio_noise_block(times)
        if noise is not None:
            output += noise

        output = np.clip(output, -1.0, 1.0)

        if outdata.ndim == 1:
            outdata[:] = output
            return

        outdata[:, :] = output.reshape(-1, 1)

    def _render_radio_noise_block(self, times):  # type: ignore[no-untyped-def]
        assert np is not None

        with self._lock:
            noise = self._radio_noise
            enabled = bool(self._radio_noise_enabled and noise is not None)

        if not enabled or noise is None:
            return None

        values = np.zeros(len(times), dtype=np.float32)

        for index, moment in enumerate(times):
            with self._lock:
                duck_target, attack_seconds, release_seconds = self._radio_noise_duck_target_locked(float(moment))
                base_gain = self._advance_gain_locked(
                    current=self._radio_noise_gain,
                    target=self._radio_noise_target_gain,
                    attack_ms=float(getattr(config, "NETWORK_RADIO_NOISE_FADE_IN_MS", 700)),
                    release_ms=float(getattr(config, "NETWORK_RADIO_NOISE_FADE_OUT_MS", 700)),
                )
                self._radio_noise_gain = base_gain

                duck_gain = self._advance_duck_gain_seconds_locked(
                    current=self._radio_noise_duck_gain,
                    target=duck_target,
                    attack_seconds=attack_seconds,
                    release_seconds=release_seconds,
                )
                self._radio_noise_duck_gain = duck_gain

                sample_index = self._radio_noise_sample_index
                self._radio_noise_sample_index += 1
                should_stop = (
                    self._radio_noise_stop_after_fade
                    and self._radio_noise_target_gain <= 0.0
                    and self._radio_noise_gain <= 0.001
                )

            sample = noise.sample(sample_index) / 32768.0
            values[index] = float(sample * base_gain * duck_gain)

            if should_stop:
                with self._lock:
                    self._radio_noise = None
                    self._radio_noise_gain = 0.0
                    self._radio_noise_duck_gain = 1.0
                    self._radio_noise_ducks.clear()
                if index + 1 < len(values):
                    values[index + 1:] = 0.0
                break

        return values

    def _radio_noise_duck_target_locked(self, moment: float) -> tuple[float, float, float]:
        active: list[ScheduledNoiseDuck] = []
        release_tail: list[ScheduledNoiseDuck] = []
        keep: list[ScheduledNoiseDuck] = []

        for event in self._radio_noise_ducks:
            release_until = event.end_monotonic + event.release_seconds + 0.25
            if release_until >= moment:
                keep.append(event)
            if event.start_monotonic <= moment <= event.end_monotonic:
                active.append(event)
            elif event.end_monotonic < moment <= release_until:
                release_tail.append(event)

        self._radio_noise_ducks = keep

        if active:
            strongest = max(active, key=lambda event: event.depth)
            target = max(0.05, 1.0 - max(0.0, min(0.95, strongest.depth)))
            return target, strongest.attack_seconds, strongest.release_seconds

        if release_tail:
            strongest_recent = max(release_tail, key=lambda event: event.depth)
            return 1.0, strongest_recent.attack_seconds, strongest_recent.release_seconds

        return 1.0, 0.08, 0.45

    def _advance_gain_locked(self, *, current: float, target: float, attack_ms: float, release_ms: float) -> float:
        return self._advance_gain_seconds_locked(
            current=current,
            target=target,
            attack_seconds=max(0.001, attack_ms / 1000.0),
            release_seconds=max(0.001, release_ms / 1000.0),
        )

    def _advance_duck_gain_seconds_locked(
        self,
        *,
        current: float,
        target: float,
        attack_seconds: float,
        release_seconds: float,
    ) -> float:
        """Advance duck gain using ducking semantics.

        For ducking, a downward gain movement is the attack phase and an upward
        gain movement is the release phase. This is the opposite of the generic
        fade helper used for the main background-noise fade-in/fade-out.
        """

        current_value = max(0.0, min(1.0, float(current)))
        target_value = max(0.0, min(1.0, float(target)))
        if abs(current_value - target_value) <= 0.00001:
            return target_value

        duration = attack_seconds if target_value < current_value else release_seconds
        samples = max(1.0, duration * float(self.sample_rate))
        step = 1.0 / samples

        if target_value > current_value:
            return min(target_value, current_value + step)

        return max(target_value, current_value - step)

    def _advance_gain_seconds_locked(
        self,
        *,
        current: float,
        target: float,
        attack_seconds: float,
        release_seconds: float,
    ) -> float:
        current_value = max(0.0, min(1.0, float(current)))
        target_value = max(0.0, min(1.0, float(target)))
        if abs(current_value - target_value) <= 0.00001:
            return target_value

        duration = attack_seconds if target_value > current_value else release_seconds
        samples = max(1.0, duration * float(self.sample_rate))
        step = 1.0 / samples

        if target_value > current_value:
            return min(target_value, current_value + step)

        return max(target_value, current_value - step)

    def _wait_for_radio_noise_fade_out(self) -> None:
        with self._lock:
            should_wait = bool(self._started and self._radio_noise is not None and self._radio_noise_gain > 0.001)

        if not should_wait:
            return

        timeout = max(0.0, min(2.0, float(getattr(config, "NETWORK_RADIO_NOISE_FADE_OUT_MS", 700)) / 1000.0 + 0.10))
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            with self._lock:
                if self._radio_noise is None or self._radio_noise_gain <= 0.001:
                    return
            time.sleep(0.02)

    def _make_radio_noise_generator_locked(self) -> RadioNoiseGenerator:
        settings = self._radio_noise_settings_for_profile(self._radio_noise_profile)
        return RadioNoiseGenerator(
            sample_rate=self.sample_rate,
            total_samples=0,
            settings=settings,
        )

    def _radio_noise_settings_for_profile(self, profile: str) -> RadioNoiseSettings:
        profile_key = self._normalize_radio_noise_profile(profile)

        profile_values = {
            "light": {
                "movement": 0.55,
                "burst_chance": 0.45,
                "burst_strength": 0.55,
                "crackle_chance": 0.45,
                "crackle_strength": 0.55,
                "dropout_chance": 0.45,
                "dropout_depth": 0.45,
            },
            "radio": {
                "movement": 0.90,
                "burst_chance": 0.75,
                "burst_strength": 0.80,
                "crackle_chance": 0.75,
                "crackle_strength": 0.80,
                "dropout_chance": 0.70,
                "dropout_depth": 0.70,
            },
            "dx": {
                "movement": 1.35,
                "burst_chance": 1.80,
                "burst_strength": 1.65,
                "crackle_chance": 1.90,
                "crackle_strength": 1.55,
                "dropout_chance": 1.35,
                "dropout_depth": 1.35,
            },
        }

        values = profile_values.get(profile_key, profile_values["radio"])

        low_pass_hz, high_pass_hz = self._radio_noise_filter_for_tone(self._radio_noise_tone)

        return RadioNoiseSettings(
            enabled=True,
            volume_percent=self._radio_noise_volume_percent,
            fade_ms=0.0,
            low_pass_hz=low_pass_hz,
            high_pass_hz=high_pass_hz,
            seed=getattr(config, "NETWORK_RADIO_NOISE_SEED", None),
            continuous=True,
            flutter_percent=float(getattr(config, "NETWORK_RADIO_NOISE_FLUTTER_PERCENT", 8)) * values["movement"],
            flutter_speed_hz=float(getattr(config, "NETWORK_RADIO_NOISE_FLUTTER_SPEED_HZ", 0.38)),
            drift_percent=float(getattr(config, "NETWORK_RADIO_NOISE_DRIFT_PERCENT", 14)) * values["movement"],
            drift_speed_hz=float(getattr(config, "NETWORK_RADIO_NOISE_DRIFT_SPEED_HZ", 0.14)),

            burst_chance_per_second=(
                float(getattr(config, "NETWORK_RADIO_NOISE_BURST_CHANCE_PER_SECOND", 0.12))
                * values["burst_chance"]
            ),
            burst_strength_percent=(
                float(getattr(config, "NETWORK_RADIO_NOISE_BURST_STRENGTH_PERCENT", 45))
                * values["burst_strength"]
            ),
            burst_decay_ms=float(getattr(config, "NETWORK_RADIO_NOISE_BURST_DECAY_MS", 190)),

            crackle_chance_per_second=(
                float(getattr(config, "NETWORK_RADIO_NOISE_CRACKLE_CHANCE_PER_SECOND", 0.65))
                * values["crackle_chance"]
            ),
            crackle_strength_percent=(
                float(getattr(config, "NETWORK_RADIO_NOISE_CRACKLE_STRENGTH_PERCENT", 11))
                * values["crackle_strength"]
            ),

            dropout_chance_per_second=(
                float(getattr(config, "NETWORK_RADIO_NOISE_DROPOUT_CHANCE_PER_SECOND", 0.04))
                * values["dropout_chance"]
            ),
            dropout_depth_percent=(
                float(getattr(config, "NETWORK_RADIO_NOISE_DROPOUT_DEPTH_PERCENT", 22))
                * values["dropout_depth"]
            ),
            dropout_decay_ms=float(getattr(config, "NETWORK_RADIO_NOISE_DROPOUT_DECAY_MS", 700)),
        ).normalized()

    def _radio_noise_filter_for_tone(self, tone: object) -> tuple[float, float]:
        tone_key = self._normalize_radio_noise_tone(tone)

        if tone_key == "deep":
            return (
                float(getattr(config, "NETWORK_RADIO_NOISE_TONE_DEEP_LOW_PASS_HZ", 950)),
                float(getattr(config, "NETWORK_RADIO_NOISE_TONE_DEEP_HIGH_PASS_HZ", 40)),
            )

        if tone_key == "normal":
            return (
                float(getattr(config, "NETWORK_RADIO_NOISE_TONE_NORMAL_LOW_PASS_HZ", 3200)),
                float(getattr(config, "NETWORK_RADIO_NOISE_TONE_NORMAL_HIGH_PASS_HZ", 250)),
            )

        return (
            float(getattr(config, "NETWORK_RADIO_NOISE_TONE_LOW_LOW_PASS_HZ", 1800)),
            float(getattr(config, "NETWORK_RADIO_NOISE_TONE_LOW_HIGH_PASS_HZ", 100)),
        )

    def _radio_noise_duck_config(self, kind: str, field: str) -> float:
        kind_key = "tx" if kind == "tx" else "rx"

        values = {
            "tx": {
                "depth_percent": self._radio_noise_tx_ducking_depth_percent,
                "attack_ms": self._radio_noise_tx_ducking_attack_ms,
                "release_ms": self._radio_noise_tx_ducking_release_ms,
                "hold_ms": self._radio_noise_tx_ducking_hold_ms,
            },
            "rx": {
                "depth_percent": self._radio_noise_rx_ducking_depth_percent,
                "attack_ms": self._radio_noise_rx_ducking_attack_ms,
                "release_ms": self._radio_noise_rx_ducking_release_ms,
                "hold_ms": self._radio_noise_rx_ducking_hold_ms,
            },
        }

        value = float(values[kind_key].get(field, 0.0))

        if field == "depth_percent":
            return max(0.0, min(95.0, value))
        if field == "attack_ms":
            return max(1.0, min(500.0, value))
        if field == "release_ms":
            return max(1.0, min(2000.0, value))
        return max(1.0, min(1500.0, value))

    def _clamp_percent(self, value: object, default: object, *, maximum: float = 100.0) -> float:
        try:
            if value is None:
                raise ValueError
            number = float(value)
        except Exception:
            number = float(default)
        return max(0.0, min(float(maximum), number))

    def _clamp_ms(self, value: object, default: object, *, minimum: float = 0.0, maximum: float = 5000.0) -> float:
        try:
            if value is None:
                raise ValueError
            number = float(value)
        except Exception:
            number = float(default)
        return max(float(minimum), min(float(maximum), number))

    def _normalize_radio_noise_profile(self, profile: object) -> str:
        value = str(profile or "radio").strip().lower()
        return value if value in {"light", "radio", "dx"} else "radio"

    def _normalize_radio_noise_tone(self, tone: object) -> str:
        value = str(tone or getattr(config, "NETWORK_RADIO_NOISE_TONE_DEFAULT", "low")).strip().lower()
        return value if value in {"normal", "low", "deep"} else str(getattr(config, "NETWORK_RADIO_NOISE_TONE_DEFAULT", "low"))

    def _clamp_radio_noise_volume_percent(self, volume_percent: object) -> float:
        try:
            value = float(volume_percent)
        except Exception:
            value = float(getattr(config, "NETWORK_RADIO_NOISE_VOLUME_PERCENT_DEFAULT", 5))
        return max(0.0, min(30.0, value))

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