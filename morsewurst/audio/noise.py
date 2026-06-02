# ============================================================
# morsewurst/audio/noise.py
# ============================================================

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any


def _safe_float(value: Any, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)

    if not math.isfinite(result):
        return float(default)

    return result


@dataclass(frozen=True)
class RadioNoiseSettings:
    """Settings for quiet, radio-like background noise.

    The generated signal is intentionally lightweight and deterministic enough
    for rendering into an existing PCM stream. It is not a separate playback
    engine and does not depend on external audio files.

    The advanced fields model the kinds of small imperfections that make radio
    noise feel less static: slow flutter, fading drift, short noise bursts,
    small crackle impulses and occasional noise dropouts. These affect only the
    background noise bed, not the Morse tone itself.
    """

    enabled: bool = False
    volume_percent: float = 4.0
    fade_ms: float = 750.0
    low_pass_hz: float = 3200.0
    high_pass_hz: float = 250.0
    seed: int | None = None
    continuous: bool = False

    # Slow periodic amplitude movement, similar to receiver flutter.
    flutter_percent: float = 0.0
    flutter_speed_hz: float = 0.0

    # Slow smoothed random amplitude movement, similar to changing conditions.
    drift_percent: float = 0.0
    drift_speed_hz: float = 0.0

    # Short stronger noise swells.
    burst_chance_per_second: float = 0.0
    burst_strength_percent: float = 0.0
    burst_decay_ms: float = 180.0

    # Tiny impulse-like clicks and scratches mixed into the noise.
    crackle_chance_per_second: float = 0.0
    crackle_strength_percent: float = 0.0

    # Occasional brief dips in the noise floor.
    dropout_chance_per_second: float = 0.0
    dropout_depth_percent: float = 0.0
    dropout_decay_ms: float = 650.0

    def normalized(self) -> "RadioNoiseSettings":
        low_pass = max(200.0, min(12_000.0, _safe_float(self.low_pass_hz, 3200.0)))
        high_pass = max(0.0, min(low_pass - 1.0, _safe_float(self.high_pass_hz, 250.0)))

        return RadioNoiseSettings(
            enabled=bool(self.enabled),
            volume_percent=max(0.0, min(30.0, _safe_float(self.volume_percent, 4.0))),
            fade_ms=max(0.0, min(10_000.0, _safe_float(self.fade_ms, 750.0))),
            low_pass_hz=low_pass,
            high_pass_hz=high_pass,
            seed=self.seed,
            continuous=bool(self.continuous),
            flutter_percent=max(0.0, min(100.0, _safe_float(self.flutter_percent, 0.0))),
            flutter_speed_hz=max(0.0, min(20.0, _safe_float(self.flutter_speed_hz, 0.0))),
            drift_percent=max(0.0, min(100.0, _safe_float(self.drift_percent, 0.0))),
            drift_speed_hz=max(0.0, min(20.0, _safe_float(self.drift_speed_hz, 0.0))),
            burst_chance_per_second=max(
                0.0,
                min(20.0, _safe_float(self.burst_chance_per_second, 0.0)),
            ),
            burst_strength_percent=max(
                0.0,
                min(400.0, _safe_float(self.burst_strength_percent, 0.0)),
            ),
            burst_decay_ms=max(5.0, min(5000.0, _safe_float(self.burst_decay_ms, 180.0))),
            crackle_chance_per_second=max(
                0.0,
                min(100.0, _safe_float(self.crackle_chance_per_second, 0.0)),
            ),
            crackle_strength_percent=max(
                0.0,
                min(400.0, _safe_float(self.crackle_strength_percent, 0.0)),
            ),
            dropout_chance_per_second=max(
                0.0,
                min(20.0, _safe_float(self.dropout_chance_per_second, 0.0)),
            ),
            dropout_depth_percent=max(
                0.0,
                min(95.0, _safe_float(self.dropout_depth_percent, 0.0)),
            ),
            dropout_decay_ms=max(5.0, min(5000.0, _safe_float(self.dropout_decay_ms, 650.0))),
        )


class RadioNoiseGenerator:
    """Generate low-level band-limited noise for mono 16-bit PCM mixing.

    A one-pole low-pass plus optional high-pass filter produces a softer
    radio-static texture than raw white noise. Slow modulation, transient
    bursts, crackle and dropouts can be layered on top to make the noise feel
    more like a living radio channel while keeping rendering cheap enough for
    temporary WAV generation.
    """

    def __init__(
        self,
        *,
        sample_rate: int,
        total_samples: int,
        settings: RadioNoiseSettings,
    ) -> None:
        self.sample_rate = max(1, int(sample_rate))
        self.total_samples = max(0, int(total_samples))
        self.settings = settings.normalized()

        self._rng = random.Random(self.settings.seed)
        self._lp_value = 0.0
        self._hp_value = 0.0
        self._prev_lp_value = 0.0

        self._amplitude = 32767.0 * 0.85 * (self.settings.volume_percent / 100.0)
        self._fade_samples = int(round((self.settings.fade_ms / 1000.0) * float(self.sample_rate)))
        self._low_pass_alpha = self._one_pole_low_pass_alpha(self.settings.low_pass_hz)
        self._high_pass_alpha = self._one_pole_high_pass_alpha(self.settings.high_pass_hz)

        self._flutter_depth = self.settings.flutter_percent / 100.0
        self._flutter_phase = self._rng.random() * 2.0 * math.pi
        self._flutter_step = (2.0 * math.pi * self.settings.flutter_speed_hz) / float(self.sample_rate)

        self._drift_depth = self.settings.drift_percent / 100.0
        self._drift_value = 0.0
        self._drift_target = self._random_modulation_target()
        self._drift_change_interval = self._samples_for_rate(self.settings.drift_speed_hz)
        self._next_drift_change_sample = self._drift_change_interval
        self._drift_alpha = self._smoothing_alpha(self.settings.drift_speed_hz)

        self._burst_level = 0.0
        self._burst_probability = self._probability_per_sample(self.settings.burst_chance_per_second)
        self._burst_strength = self.settings.burst_strength_percent / 100.0
        self._burst_decay_factor = self._decay_factor(self.settings.burst_decay_ms)

        self._crackle_probability = self._probability_per_sample(self.settings.crackle_chance_per_second)
        self._crackle_strength = self.settings.crackle_strength_percent / 100.0

        self._dropout_level = 0.0
        self._dropout_probability = self._probability_per_sample(self.settings.dropout_chance_per_second)
        self._dropout_depth = self.settings.dropout_depth_percent / 100.0
        self._dropout_decay_factor = self._decay_factor(self.settings.dropout_decay_ms)

    @property
    def enabled(self) -> bool:
        return bool(
            self.settings.enabled
            and self._amplitude > 0.0
            and (self.settings.continuous or self.total_samples > 0)
        )

    def sample(self, sample_index: int) -> int:
        if not self.enabled:
            return 0

        white = (self._rng.random() * 2.0) - 1.0

        self._lp_value += self._low_pass_alpha * (white - self._lp_value)

        if self.settings.high_pass_hz > 0.0:
            self._hp_value = self._high_pass_alpha * (self._hp_value + self._lp_value - self._prev_lp_value)
            self._prev_lp_value = self._lp_value
            shaped = self._hp_value
        else:
            shaped = self._lp_value

        self._advance_transients()
        envelope = self._fade_envelope(sample_index) * self._radio_envelope(sample_index)
        mixed = shaped * self._amplitude * envelope
        mixed += self._crackle_impulse()

        return clamp_int16(mixed)

    def _fade_envelope(self, sample_index: int) -> float:
        if self._fade_samples <= 0:
            return 1.0

        index = max(0, int(sample_index))
        envelope = 1.0

        if index < self._fade_samples:
            envelope = min(envelope, index / float(self._fade_samples))

        if not self.settings.continuous:
            remaining = self.total_samples - index - 1
            if remaining < self._fade_samples:
                envelope = min(envelope, max(0.0, remaining / float(self._fade_samples)))

        return max(0.0, min(1.0, envelope))

    def _radio_envelope(self, sample_index: int) -> float:
        envelope = 1.0

        if self._flutter_depth > 0.0 and self._flutter_step > 0.0:
            envelope += math.sin(self._flutter_phase) * self._flutter_depth
            self._flutter_phase += self._flutter_step
            if self._flutter_phase >= 2.0 * math.pi:
                self._flutter_phase -= 2.0 * math.pi

        if self._drift_depth > 0.0 and self._drift_change_interval > 0:
            if sample_index >= self._next_drift_change_sample:
                self._drift_target = self._random_modulation_target()
                self._next_drift_change_sample = sample_index + self._drift_change_interval

            self._drift_value += (self._drift_target - self._drift_value) * self._drift_alpha
            envelope += self._drift_value * self._drift_depth

        if self._burst_level > 0.0:
            envelope += self._burst_level

        if self._dropout_level > 0.0:
            envelope *= max(0.05, 1.0 - self._dropout_level)

        return max(0.0, min(4.0, envelope))

    def _advance_transients(self) -> None:
        if self._burst_level > 0.0:
            self._burst_level *= self._burst_decay_factor
            if self._burst_level < 0.0001:
                self._burst_level = 0.0

        if self._dropout_level > 0.0:
            self._dropout_level *= self._dropout_decay_factor
            if self._dropout_level < 0.0001:
                self._dropout_level = 0.0

        if self._burst_probability > 0.0 and self._rng.random() < self._burst_probability:
            strength = self._burst_strength * (0.50 + self._rng.random())
            self._burst_level = min(3.0, self._burst_level + strength)

        if self._dropout_probability > 0.0 and self._rng.random() < self._dropout_probability:
            depth = self._dropout_depth * (0.65 + (0.35 * self._rng.random()))
            self._dropout_level = min(0.95, max(self._dropout_level, depth))

    def _crackle_impulse(self) -> float:
        if self._crackle_probability <= 0.0 or self._rng.random() >= self._crackle_probability:
            return 0.0

        polarity = -1.0 if self._rng.random() < 0.5 else 1.0
        strength = self._crackle_strength * (0.25 + (0.75 * self._rng.random()))
        return polarity * self._amplitude * strength

    def _random_modulation_target(self) -> float:
        # Bias toward small changes, with occasional larger movement.
        return (self._rng.random() - self._rng.random())

    def _samples_for_rate(self, rate_hz: float) -> int:
        if rate_hz <= 0.0:
            return 0

        return max(1, int(round(float(self.sample_rate) / rate_hz)))

    def _probability_per_sample(self, chance_per_second: float) -> float:
        if chance_per_second <= 0.0:
            return 0.0

        return max(0.0, min(1.0, chance_per_second / float(self.sample_rate)))

    def _decay_factor(self, duration_ms: float) -> float:
        duration_seconds = max(0.001, duration_ms / 1000.0)
        return math.exp(-1.0 / (duration_seconds * float(self.sample_rate)))

    def _smoothing_alpha(self, speed_hz: float) -> float:
        if speed_hz <= 0.0:
            return 0.0

        # This is intentionally slower than the target-change rate. That makes
        # the drift feel like changing reception rather than tremolo.
        return max(0.000001, min(1.0, speed_hz / float(self.sample_rate)))

    def _one_pole_low_pass_alpha(self, cutoff_hz: float) -> float:
        cutoff = max(1.0, float(cutoff_hz))
        dt = 1.0 / float(self.sample_rate)
        rc = 1.0 / (2.0 * math.pi * cutoff)
        return max(0.0, min(1.0, dt / (rc + dt)))

    def _one_pole_high_pass_alpha(self, cutoff_hz: float) -> float:
        cutoff = max(0.0, float(cutoff_hz))
        if cutoff <= 0.0:
            return 0.0

        dt = 1.0 / float(self.sample_rate)
        rc = 1.0 / (2.0 * math.pi * cutoff)
        return max(0.0, min(1.0, rc / (rc + dt)))


def clamp_int16(value: int | float) -> int:
    return max(-32768, min(32767, int(value)))
