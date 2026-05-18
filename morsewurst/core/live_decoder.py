# ============================================================
# morsewurst/core/live_decoder.py
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from morsewurst.core.adaptive_decoder import DecodedTelemetry, decode_tone_events
from morsewurst.core.adaptive_timing import DecoderSettings


@dataclass
class LiveDecoderState:
    text: str = ""
    pending_symbol: str = ""
    source: str = ""
    event_count: int = 0
    tone_count: int = 0
    decoded: Optional[DecodedTelemetry] = None


@dataclass
class LiveMorseDecoder:
    """Small stateful wrapper around the profile-aware decoder.

    The decoder keeps raw events for the current round and exposes one stable
    place for live UI updates. It deliberately does not learn permanently.
    Long-term learning happens through TimingProfile, which is rebuilt from
    saved high-quality sessions.
    """

    settings: DecoderSettings
    target_text: str = ""
    seed_unit_us: Optional[float] = None
    events: list[dict[str, Any]] = field(default_factory=list)
    last_state: LiveDecoderState = field(default_factory=LiveDecoderState)

    def reset(self, *, target_text: str = "", seed_unit_us: Optional[float] = None) -> None:
        self.target_text = target_text
        self.seed_unit_us = seed_unit_us
        self.events.clear()
        self.last_state = LiveDecoderState()

    def feed_event(self, event: dict[str, Any]) -> None:
        if event.get("type") == "tone":
            self.events.append(dict(event))

    def replace_events(self, events: list[dict[str, Any]]) -> None:
        self.events = [dict(event) for event in events if event.get("type") == "tone"]

    def decode(
        self,
        *,
        current_time_us: Optional[int] = None,
        flush_final: bool = False,
        settings: Optional[DecoderSettings] = None,
        seed_unit_us: Optional[float] = None,
        target_text: Optional[str] = None,
    ) -> DecodedTelemetry:
        if settings is not None:
            self.settings = settings
        if seed_unit_us is not None:
            self.seed_unit_us = seed_unit_us
        if target_text is not None:
            self.target_text = target_text

        decoded = decode_tone_events(
            self.events,
            current_time_us=current_time_us,
            flush_final=flush_final,
            seed_unit_us=self.seed_unit_us,
            settings=self.settings,
            target_text=self.target_text,
        )

        self.last_state = LiveDecoderState(
            text=decoded.text,
            pending_symbol=getattr(decoded, "pending_symbol", ""),
            source=getattr(decoded, "source", ""),
            event_count=len(self.events),
            tone_count=len(self.events),
            decoded=decoded,
        )
        return decoded

    def current_state(self) -> LiveDecoderState:
        return self.last_state
