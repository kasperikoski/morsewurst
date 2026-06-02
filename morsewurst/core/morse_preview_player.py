# ============================================================
# morsewurst/core/morse_preview_player.py
# ============================================================

from __future__ import annotations

import threading
from typing import Any, Optional

try:
    import numpy as np
except ImportError:
    np = None

try:
    import sounddevice as sd
except ImportError:
    sd = None


MORSE_PREVIEW_CODE: dict[str, str] = {
    "A": ".-",
    "B": "-...",
    "C": "-.-.",
    "D": "-..",
    "E": ".",
    "F": "..-.",
    "G": "--.",
    "H": "....",
    "I": "..",
    "J": ".---",
    "K": "-.-",
    "L": ".-..",
    "M": "--",
    "N": "-.",
    "O": "---",
    "P": ".--.",
    "Q": "--.-",
    "R": ".-.",
    "S": "...",
    "T": "-",
    "U": "..-",
    "V": "...-",
    "W": ".--",
    "X": "-..-",
    "Y": "-.--",
    "Z": "--..",
    "0": "-----",
    "1": ".----",
    "2": "..---",
    "3": "...--",
    "4": "....-",
    "5": ".....",
    "6": "-....",
    "7": "--...",
    "8": "---..",
    "9": "----.",
}


class MorsePreviewPlayer:
    """Smooth looping Morse speed preview.

    This renderer builds the whole preview phrase as one float32 audio buffer
    and plays that buffer in a loop. This avoids short real-time scheduled tone
    fragments, which can sound buzzy or unstable on some Windows audio devices.
    """

    def __init__(
        self,
        *,
        text: str = "SOS CONNECTING PEOPLE",
        frequency_hz: float = 600.0,
        volume: float = 0.42,
        samplerate: int = 48_000,
        blocksize: int = 2048,
    ) -> None:
        self.text = text
        self.frequency_hz = float(frequency_hz)
        self.volume = max(0.0, min(0.95, float(volume)))
        self.samplerate = int(samplerate)
        self.blocksize = int(blocksize)

        self._stream: Optional[Any] = None
        self._audio: Optional[Any] = None
        self._position = 0
        self._lock = threading.RLock()

    @property
    def running(self) -> bool:
        stream = self._stream
        return stream is not None and bool(stream.active)

    def start(self, *, wpm: int) -> None:

        if np is None:
            raise RuntimeError("numpy is missing. Install: python -m pip install numpy")

        if sd is None:
            raise RuntimeError("sounddevice is missing. Install: python -m pip install sounddevice")

        with self._lock:
            self.stop()

            safe_wpm = max(5, min(80, int(wpm)))
            self._audio = self._render_loop_buffer(wpm=safe_wpm)
            self._position = 0

            self._stream = sd.OutputStream(
                samplerate=self.samplerate,
                channels=1,
                dtype="float32",
                blocksize=self.blocksize,
                latency="high",
                callback=self._callback,
            )
            self._stream.start()

    def stop(self) -> None:
        with self._lock:
            stream = self._stream
            self._stream = None

            if stream is not None:
                try:
                    stream.stop()
                except Exception:
                    pass
                try:
                    stream.close()
                except Exception:
                    pass

            self._audio = None
            self._position = 0

    def _callback(self, outdata, frames, _time_info, status) -> None:
        del status

        with self._lock:
            audio = self._audio

            if audio is None or len(audio) == 0:
                outdata.fill(0)
                return

            output = np.empty(frames, dtype=np.float32)
            written = 0

            while written < frames:
                remaining_output = frames - written
                remaining_audio = len(audio) - self._position
                take = min(remaining_output, remaining_audio)

                output[written:written + take] = audio[self._position:self._position + take]

                self._position += take
                written += take

                if self._position >= len(audio):
                    self._position = 0

            outdata[:, 0] = output

    def _render_loop_buffer(self, *, wpm: int) -> np.ndarray:
        unit_seconds = 1.2 / float(wpm)
        chunks: list[np.ndarray] = []

        words = self.text.upper().split()

        for word_index, word in enumerate(words):
            for char_index, char in enumerate(word):
                code = MORSE_PREVIEW_CODE.get(char)
                if not code:
                    continue

                self._append_character(chunks, code, unit_seconds)

                # Letter gap is 3 units total. _append_character already
                # leaves a 1-unit element gap after the final element, so add 2.
                if char_index < len(word) - 1:
                    chunks.append(self._silence(unit_seconds * 2.0))

            # Word gap is 7 units total. Last element already leaves 1 unit.
            if word_index < len(words) - 1:
                chunks.append(self._silence(unit_seconds * 6.0))

        # Pause before repeating.
        chunks.append(self._silence(unit_seconds * 10.0))

        if not chunks:
            return np.zeros(int(self.samplerate * 0.5), dtype=np.float32)

        audio = np.concatenate(chunks).astype(np.float32, copy=False)

        # Safety limiter.
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if peak > 0.98:
            audio = audio * (0.98 / peak)

        return audio

    def _append_character(
        self,
        chunks: list[np.ndarray],
        code: str,
        unit_seconds: float,
    ) -> None:
        for element in code:
            duration = unit_seconds if element == "." else unit_seconds * 3.0
            chunks.append(self._tone(duration))
            chunks.append(self._silence(unit_seconds))

    def _tone(self, duration_seconds: float) -> np.ndarray:
        samples = max(1, int(round(duration_seconds * self.samplerate)))
        t = np.arange(samples, dtype=np.float32) / float(self.samplerate)

        tone = np.sin(2.0 * np.pi * self.frequency_hz * t).astype(np.float32)
        tone *= self.volume

        # Smooth attack/release. This removes clicks and harsh edges.
        attack_samples = int(round(0.008 * self.samplerate))
        release_samples = int(round(0.012 * self.samplerate))
        fade_samples = max(1, min(attack_samples, release_samples, samples // 3))

        if fade_samples > 1:
            attack = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
            release = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
            tone[:fade_samples] *= attack
            tone[-fade_samples:] *= release

        return tone

    def _silence(self, duration_seconds: float) -> np.ndarray:
        samples = max(1, int(round(duration_seconds * self.samplerate)))
        return np.zeros(samples, dtype=np.float32)