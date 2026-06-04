# ============================================================
# morsewurst/koch/tone_renderer.py
# ============================================================

from __future__ import annotations

import io
import math
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

import morsewurst.config as config
from morsewurst.audio.noise import RadioNoiseGenerator, RadioNoiseSettings, clamp_int16
from morsewurst.core.scoring import CHAR_TO_MORSE
from morsewurst.koch.models import KochSettings
from morsewurst.koch.schedule import koch_timing_ms

_FALLBACK_SAMPLE_RATE = 8_000
_SAMPLE_WIDTH_BYTES = 2
_CHANNELS = 1
_TONE_RAMP_MS = 4.0
_CHUNK_SAMPLES = 4096
_TAIL_MS = 120.0


def _koch_audio_sample_rate() -> int:
    """Return the sample rate used for rendered Koch playback WAV files."""

    raw_value = getattr(config, "DEFAULT_KOCH_AUDIO_SAMPLE_RATE", _FALLBACK_SAMPLE_RATE)
    try:
        sample_rate = int(raw_value)
    except (TypeError, ValueError):
        sample_rate = _FALLBACK_SAMPLE_RATE

    return max(8_000, min(48_000, sample_rate))


@dataclass
class _RenderContext:
    noise: RadioNoiseGenerator | None = None
    sample_index: int = 0


def _sample_count(duration_ms: float, *, sample_rate: int) -> int:
    return max(0, int(round((max(0.0, float(duration_ms)) / 1000.0) * float(sample_rate))))


def _koch_radio_noise_settings() -> RadioNoiseSettings:
    return RadioNoiseSettings(
        enabled=bool(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_ENABLED", True)),
        volume_percent=float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_VOLUME_PERCENT", 5.0)),
        fade_ms=float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_FADE_MS", 750.0)),
        low_pass_hz=float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_LOW_PASS_HZ", 3200.0)),
        high_pass_hz=float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_HIGH_PASS_HZ", 250.0)),
        seed=getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_SEED", None),
        flutter_percent=float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_FLUTTER_PERCENT", 0.0)),
        flutter_speed_hz=float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_FLUTTER_SPEED_HZ", 0.0)),
        drift_percent=float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_DRIFT_PERCENT", 0.0)),
        drift_speed_hz=float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_DRIFT_SPEED_HZ", 0.0)),
        burst_chance_per_second=float(
            getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_BURST_CHANCE_PER_SECOND", 0.0)
        ),
        burst_strength_percent=float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_BURST_STRENGTH_PERCENT", 0.0)),
        burst_decay_ms=float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_BURST_DECAY_MS", 180.0)),
        crackle_chance_per_second=float(
            getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_CRACKLE_CHANCE_PER_SECOND", 0.0)
        ),
        crackle_strength_percent=float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_CRACKLE_STRENGTH_PERCENT", 0.0)),
        dropout_chance_per_second=float(
            getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_DROPOUT_CHANCE_PER_SECOND", 0.0)
        ),
        dropout_depth_percent=float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_DROPOUT_DEPTH_PERCENT", 0.0)),
        dropout_decay_ms=float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_DROPOUT_DECAY_MS", 650.0)),
    )


def koch_background_noise_lead_in_ms() -> float:
    """Return the rendered noise-only lead-in before the first Morse tone."""

    noise_settings = _koch_radio_noise_settings().normalized()
    if not noise_settings.enabled or noise_settings.volume_percent <= 0.0:
        return 0.0

    return max(
        0.0,
        min(
            10_000.0,
            float(getattr(config, "DEFAULT_KOCH_BACKGROUND_NOISE_LEAD_IN_MS", 750.0)),
        ),
    )


def _render_sample_count(target: str, settings: KochSettings, *, sample_rate: int) -> int:
    timing = koch_timing_ms(settings)
    element_unit_ms = timing["element_unit_ms"]
    element_gap_ms = timing["element_gap_ms"]
    char_gap_ms = timing["char_gap_ms"]
    word_gap_ms = timing["word_gap_ms"]

    total = _sample_count(koch_background_noise_lead_in_ms(), sample_rate=sample_rate)
    previous_symbol = False
    pending_word_gap = False

    for raw_char in str(target or "").upper():
        if raw_char.isspace():
            if previous_symbol:
                pending_word_gap = True
            continue

        code = CHAR_TO_MORSE.get(raw_char)
        if not code:
            continue

        if previous_symbol:
            total += _sample_count(word_gap_ms if pending_word_gap else char_gap_ms, sample_rate=sample_rate)

        for index, element in enumerate(code):
            if index > 0:
                total += _sample_count(element_gap_ms, sample_rate=sample_rate)
            total += _sample_count(element_unit_ms if element == "." else 3.0 * element_unit_ms, sample_rate=sample_rate)

        previous_symbol = True
        pending_word_gap = False

    total += _sample_count(_TAIL_MS, sample_rate=sample_rate)
    return total


def _make_render_context(target: str, settings: KochSettings, *, sample_rate: int) -> _RenderContext:
    noise_settings = _koch_radio_noise_settings().normalized()
    if not noise_settings.enabled or noise_settings.volume_percent <= 0.0:
        return _RenderContext()

    return _RenderContext(
        noise=RadioNoiseGenerator(
            sample_rate=sample_rate,
            total_samples=_render_sample_count(target, settings, sample_rate=sample_rate),
            settings=noise_settings,
        )
    )


def _write_segment(
    wav: wave.Wave_write,
    duration_ms: float,
    *,
    context: _RenderContext,
    sample_rate: int,
    frequency_hz: int | None = None,
    volume_percent: int = 0,
) -> None:
    total = _sample_count(duration_ms, sample_rate=sample_rate)
    if total <= 0:
        return

    noise = context.noise

    # Fast path for silent gaps when background noise is disabled. This keeps
    # rendering cost essentially identical to the old implementation.
    if frequency_hz is None and (noise is None or not noise.enabled):
        silence = array("h", [0]) * min(_CHUNK_SAMPLES, total)
        remaining = total
        while remaining > 0:
            n = min(len(silence), remaining)
            wav.writeframes(silence[:n].tobytes())
            remaining -= n
            context.sample_index += n
        return

    tone_enabled = frequency_hz is not None and volume_percent > 0
    frequency = max(50.0, float(frequency_hz or 0))
    volume = max(0.0, min(1.0, float(volume_percent) / 100.0))
    amplitude = int(32767 * 0.85 * volume) if tone_enabled else 0

    ramp_samples = _sample_count(_TONE_RAMP_MS, sample_rate=sample_rate)
    ramp_samples = min(ramp_samples, max(1, total // 2)) if total > 1 else 0

    written = 0

    while written < total:
        n = min(_CHUNK_SAMPLES, total - written)
        frames = array("h")

        for offset in range(n):
            local_index = written + offset
            mixed = 0

            if tone_enabled:
                envelope = 1.0
                if ramp_samples > 0:
                    if local_index < ramp_samples:
                        envelope = local_index / float(ramp_samples)
                    elif local_index >= total - ramp_samples:
                        envelope = max(0.0, (total - local_index - 1) / float(ramp_samples))

                angle = (2.0 * math.pi * frequency * local_index) / float(sample_rate)
                mixed += int(math.sin(angle) * amplitude * envelope)

            if noise is not None and noise.enabled:
                mixed += noise.sample(context.sample_index)

            frames.append(clamp_int16(mixed))
            context.sample_index += 1

        wav.writeframes(frames.tobytes())
        written += n


def _write_koch_wave(wav: wave.Wave_write, target: str, settings: KochSettings, *, sample_rate: int) -> None:
    normalized = settings.normalized()
    timing = koch_timing_ms(normalized)
    element_unit_ms = timing["element_unit_ms"]
    element_gap_ms = timing["element_gap_ms"]
    char_gap_ms = timing["char_gap_ms"]
    word_gap_ms = timing["word_gap_ms"]

    context = _make_render_context(target, normalized, sample_rate=sample_rate)

    wav.setnchannels(_CHANNELS)
    wav.setsampwidth(_SAMPLE_WIDTH_BYTES)
    wav.setframerate(sample_rate)

    previous_symbol = False
    pending_word_gap = False

    lead_in_ms = koch_background_noise_lead_in_ms()
    if lead_in_ms > 0.0:
        _write_segment(wav, lead_in_ms, context=context, sample_rate=sample_rate)

    for raw_char in str(target or "").upper():
        if raw_char.isspace():
            if previous_symbol:
                pending_word_gap = True
            continue

        code = CHAR_TO_MORSE.get(raw_char)
        if not code:
            continue

        if previous_symbol:
            _write_segment(wav, word_gap_ms if pending_word_gap else char_gap_ms, context=context, sample_rate=sample_rate)

        for index, element in enumerate(code):
            if index > 0:
                _write_segment(wav, element_gap_ms, context=context, sample_rate=sample_rate)

            duration_ms = element_unit_ms if element == "." else 3.0 * element_unit_ms
            _write_segment(
                wav,
                duration_ms,
                context=context,
                sample_rate=sample_rate,
                frequency_hz=normalized.tone_hz,
                volume_percent=normalized.volume_percent,
            )

        previous_symbol = True
        pending_word_gap = False

    # A short tail prevents some devices from clipping the final fade-out
    # and gives the optional background noise a natural fade-out endpoint.
    _write_segment(wav, _TAIL_MS, context=context, sample_rate=sample_rate)


def render_koch_wave_file(path: str | Path, target: str, settings: KochSettings) -> Path:
    """Render the whole Koch drill with optional quiet radio background noise."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = _koch_audio_sample_rate()

    with wave.open(str(output_path), "wb") as wav:
        _write_koch_wave(wav, target, settings, sample_rate=sample_rate)

    return output_path


def render_koch_wave_bytes(target: str, settings: KochSettings) -> bytes:
    """Render the whole Koch drill to WAV bytes for tests and in-memory callers."""

    buffer = io.BytesIO()
    sample_rate = _koch_audio_sample_rate()

    with wave.open(buffer, "wb") as wav:
        _write_koch_wave(wav, target, settings, sample_rate=sample_rate)

    return buffer.getvalue()
