# ============================================================
# morsewurst/ui/controllers/decoder_controller.py
# ============================================================

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import tkinter as tk

import morsewurst.config as config
from morsewurst.core.adaptive_decoder import decode_tone_events
from morsewurst.core.adaptive_timing import DecoderSettings
from morsewurst.core.live_decoder import LiveMorseDecoder
from morsewurst.core.scoring import telemetry_visible_text
from morsewurst.core.timing_profile import TimingProfile

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class DecoderController:
    """Owns timing profiles, adaptive decoding and telemetry display rendering."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def default_timing_profiles(self) -> dict[str, TimingProfile]:
        """Return empty timing profiles for supported input sources."""
        return {
            "straight": TimingProfile(source="straight"),
            "iambic": TimingProfile(source="iambic"),
        }

    def adaptive_current_device_time_us(self) -> Optional[int]:
        """Estimate the current device time using the latest tone event."""
        app = self.app

        tone_events = [
            event
            for event in app.round.events
            if event.get("type") == "tone" and isinstance(event.get("t1"), int)
        ]

        if not tone_events:
            return None

        last_event = tone_events[-1]
        host_received = last_event.get("_host_received_time")

        if not isinstance(host_received, (int, float)):
            return int(last_event["t1"])

        elapsed_us = max(
            0,
            int((time.time() - float(host_received)) * 1_000_000),
        )
        return int(last_event["t1"]) + elapsed_us

    def last_tone_event(self) -> Optional[Dict[str, Any]]:
        """Return the latest raw tone event from the current round."""
        for event in reversed(self.app.round.events):
            if (
                event.get("type") == "tone"
                and isinstance(event.get("t0"), int)
                and isinstance(event.get("t1"), int)
            ):
                return event

        return None

    def refresh_timing_profiles(self) -> None:
        """Load source-specific timing profiles from stored history."""
        app = self.app
        helpers = app.ui_helpers_controller

        try:
            use_profile = bool(app.use_timing_profile_var.get())
        except Exception:
            use_profile = bool(getattr(config, "DECODER_USE_TIMING_PROFILE_DEFAULT", True))

        if not use_profile:
            app.timing_profiles = self.default_timing_profiles()
            return

        try:
            recent_sessions = helpers.safe_int_var(
                app.decoder_profile_recent_rounds_var,
                default=int(getattr(config, "DECODER_PROFILE_RECENT_ROUNDS", 300)),
                minimum=int(getattr(config, "DECODER_PROFILE_MIN_ROUNDS_REQUIRED", 100)),
                maximum=100000,
            )
        except Exception:
            recent_sessions = int(getattr(config, "DECODER_PROFILE_RECENT_ROUNDS", 300))

        try:
            min_accuracy = float(app.decoder_profile_min_accuracy_var.get())
        except Exception:
            min_accuracy = float(getattr(config, "DECODER_PROFILE_MIN_ACCURACY", 90.0))

        try:
            min_cleanliness = float(app.decoder_profile_min_cleanliness_var.get())
        except Exception:
            min_cleanliness = float(getattr(config, "DECODER_PROFILE_MIN_CLEANLINESS", 85.0))

        min_timing_score = float(getattr(config, "DECODER_PROFILE_MIN_TIMING_SCORE", 30.0))

        try:
            app.timing_profiles = app.db.load_timing_profiles(
                recent_sessions=recent_sessions,
                min_accuracy=min_accuracy,
                min_cleanliness=min_cleanliness,
                min_timing_score=min_timing_score,
            )
        except Exception:
            app.timing_profiles = self.default_timing_profiles()

    def timing_profile_for_source(self, source: str) -> TimingProfile:
        """Return the timing profile for one input source."""
        try:
            return self.app.timing_profiles.get(source) or TimingProfile(source=source)
        except Exception:
            return TimingProfile(source=source)

    def adaptive_seed_unit_us(self) -> float:
        """Choose the initial unit length for adaptive decoding."""
        app = self.app
        helpers = app.ui_helpers_controller

        target_wpm = helpers.safe_int_var(
            app.target_wpm_var,
            default=config.DEFAULT_TARGET_WPM,
            minimum=5,
            maximum=80,
        )
        target_unit = max(20_000.0, 1_200_000.0 / float(target_wpm))

        try:
            if not bool(app.use_timing_profile_var.get()):
                return target_unit
        except Exception:
            return target_unit

        min_rounds = int(getattr(config, "DECODER_PROFILE_MIN_ROUNDS_REQUIRED", 100))
        min_confidence = float(getattr(config, "DECODER_PROFILE_MIN_CONFIDENCE_FOR_SEED", 0.30))

        straight = self.timing_profile_for_source("straight")

        try:
            if int(straight.sample_rounds or 0) >= min_rounds:
                if (
                    straight.element_unit_us is not None
                    and float(straight.element_confidence or 0.0) >= min_confidence
                ):
                    return float(straight.element_unit_us)

                if (
                    straight.gap_unit_us is not None
                    and float(straight.gap_confidence or 0.0) >= min_confidence
                ):
                    return float(straight.gap_unit_us)
        except Exception:
            pass

        iambic = self.timing_profile_for_source("iambic")

        try:
            if int(iambic.sample_rounds or 0) >= min_rounds:
                if (
                    iambic.gap_unit_us is not None
                    and float(iambic.gap_confidence or 0.0) >= min_confidence
                ):
                    return float(iambic.gap_unit_us)

                if (
                    iambic.element_unit_us is not None
                    and float(iambic.element_confidence or 0.0) >= min_confidence
                ):
                    return float(iambic.element_unit_us)
        except Exception:
            pass

        return target_unit

    def sync_adaptive_runtime_settings(self) -> None:
        """Kept for compatibility. Decoder settings are now passed as objects."""
        return None

    def decoder_settings_from_ui(self) -> DecoderSettings:
        """Build a DecoderSettings object from current UI values and trusted profiles."""
        app = self.app
        helpers = app.ui_helpers_controller

        straight = self.timing_profile_for_source("straight")
        iambic = self.timing_profile_for_source("iambic")

        min_rounds = int(getattr(config, "DECODER_PROFILE_MIN_ROUNDS_REQUIRED", 100))
        min_confidence = float(getattr(config, "DECODER_PROFILE_MIN_CONFIDENCE_FOR_SEED", 0.30))

        def trusted_profile(profile: TimingProfile) -> TimingProfile:
            try:
                if int(profile.sample_rounds or 0) < min_rounds:
                    return TimingProfile(source=profile.source)

                if max(
                    float(profile.element_confidence or 0.0),
                    float(profile.gap_confidence or 0.0),
                ) < min_confidence:
                    return TimingProfile(source=profile.source)

                return profile
            except Exception:
                return TimingProfile(source=getattr(profile, "source", "unknown"))

        straight = trusted_profile(straight)
        iambic = trusted_profile(iambic)

        try:
            use_profile = bool(app.use_timing_profile_var.get())
        except Exception:
            use_profile = bool(getattr(config, "DECODER_USE_TIMING_PROFILE_DEFAULT", True))

        kwargs: dict[str, Any] = {
            "target_wpm": helpers.safe_int_var(
                app.target_wpm_var,
                default=config.DEFAULT_TARGET_WPM,
                minimum=5,
                maximum=80,
            )
        }

        if use_profile:
            kwargs.update(
                profile_straight_element_unit_us=straight.element_unit_us,
                profile_straight_gap_unit_us=straight.gap_unit_us,
                profile_straight_letter_gap_us=straight.letter_gap_us,
                profile_straight_word_gap_us=straight.word_gap_us,
                profile_straight_element_confidence=straight.element_confidence,
                profile_straight_gap_confidence=straight.gap_confidence,
                profile_iambic_element_unit_us=iambic.element_unit_us,
                profile_iambic_letter_gap_us=iambic.letter_gap_us,
                profile_iambic_word_gap_us=iambic.word_gap_us,
                profile_iambic_gap_unit_us=iambic.gap_unit_us,
                profile_iambic_element_confidence=iambic.element_confidence,
                profile_iambic_gap_confidence=iambic.gap_confidence,
            )

        return DecoderSettings.from_config(**kwargs)

    def new_live_decoder(self, target_text: str = "") -> LiveMorseDecoder:
        """Create a fresh live decoder for the current round."""
        return LiveMorseDecoder(
            settings=self.decoder_settings_from_ui(),
            target_text=target_text,
            seed_unit_us=self.adaptive_seed_unit_us(),
        )

    def decode_tone_events(
        self,
        events: List[Dict[str, Any]],
        *,
        current_time_us: Optional[int] = None,
        flush_final: bool = False,
        seed_unit_us: Optional[float] = None,
        target_text: Optional[str] = None,
    ) -> Any:
        """Decode raw tone telemetry with the current decoder settings."""
        app = self.app

        if target_text is None:
            target_text = app.round.target or app.target_var.get()

        settings = self.decoder_settings_from_ui()

        if app.live_decoder is not None and events is app.round.events:
            # The current round feeds accepted tone events into LiveMorseDecoder
            # incrementally in InputController.record_tone_event(). Avoid copying
            # the whole growing round event list on every live refresh.
            return app.live_decoder.decode(
                current_time_us=current_time_us,
                flush_final=flush_final,
                settings=settings,
                seed_unit_us=seed_unit_us,
                target_text=target_text,
            )

        return decode_tone_events(
            events,
            current_time_us=current_time_us,
            flush_final=flush_final,
            seed_unit_us=seed_unit_us,
            settings=settings,
            target_text=target_text,
        )

    def clear_telemetry_display(self) -> None:
        """Clear decoded telemetry text from state and UI."""
        app = self.app

        app.round.telemetry_text = ""
        app.telemetry_display_var.set("")
        self.write_telemetry_text_widget("")

    def telemetry_char_tag(self, info: dict[str, Any]) -> Optional[str]:
        """Return the visual tag for one decoded telemetry character."""
        unknown_char = str(getattr(config, "DECODER_UNKNOWN_CHAR", "�"))
        ch = str(info.get("ch") or "")

        if ch == unknown_char:
            return "unknown"

        return None

    def write_telemetry_text_widget(
        self,
        text: str,
        char_infos: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """Write decoded telemetry text to the text widget with optional tags."""
        app = self.app

        app.telemetry_display_var.set(text)

        widget = getattr(app, "telemetry_text_widget", None)
        if widget is None:
            return

        try:
            widget.configure(state=tk.NORMAL)
            widget.delete("1.0", tk.END)

            infos = list(char_infos or [])

            if infos and len(infos) > len(text):
                infos = infos[-len(text):]

            for index, ch in enumerate(text):
                info = infos[index] if index < len(infos) else {}
                tag = self.telemetry_char_tag(info)

                if tag:
                    widget.insert(tk.END, ch, (tag,))
                else:
                    widget.insert(tk.END, ch)

            widget.configure(state=tk.DISABLED)

        except Exception:
            try:
                widget.configure(state=tk.DISABLED)
            except Exception:
                pass

    def update_telemetry_display_from_text(self, text: str) -> None:
        """Update telemetry display from already-decoded text."""
        app = self.app

        app.round.telemetry_text = text.upper()
        visible = telemetry_visible_text(
            app.round.telemetry_text,
            config.TELEMETRY_DISPLAY_MAX_CHARS,
        )
        self.write_telemetry_text_widget(visible)

    def update_telemetry_display_from_decoded(self, decoded: Any) -> None:
        """Update telemetry display from a decoder result object."""
        app = self.app

        app.round.telemetry_text = str(getattr(decoded, "text", "") or "").upper()
        visible = telemetry_visible_text(
            app.round.telemetry_text,
            config.TELEMETRY_DISPLAY_MAX_CHARS,
        )

        infos = list(getattr(decoded, "char_infos", []) or [])

        if visible and infos:
            visible_infos = infos[-len(visible):]
        else:
            visible_infos = []

        self.write_telemetry_text_widget(visible, visible_infos)

    def clear_raw_telemetry(self) -> None:
        """Clear the raw telemetry canvas."""
        app = self.app

        if not hasattr(app, "raw_canvas"):
            return

        try:
            width = max(1, int(app.raw_canvas.winfo_width()))
            height = max(1, int(app.raw_canvas.winfo_height()))
        except Exception:
            width = 1
            height = getattr(config, "UI_RAW_TELEMETRY_HEIGHT", 72)

        app.raw_telemetry_follow_latest = True
        app.raw_canvas.delete("all")
        app.raw_canvas.configure(scrollregion=(0, 0, width, height))
        app.raw_canvas.xview_moveto(0.0)
        app.raw_canvas.create_text(
            10,
            height // 2,
            text="Ei telemetriaa",
            anchor=tk.W,
            fill="#777777",
            font=("Segoe UI", 10),
        )

    def draw_raw_telemetry(
        self,
        *,
        events: Optional[List[Dict[str, Any]]] = None,
        freeze_time: bool = False,
    ) -> None:
        """Draw the current round or supplied history events on the raw telemetry canvas."""
        app = self.app

        if not hasattr(app, "raw_canvas"):
            return

        canvas = app.raw_canvas

        try:
            visible_width = max(1, int(canvas.winfo_width()))
            height = max(1, int(canvas.winfo_height()))
        except Exception:
            return

        canvas.delete("all")
        tones = self.raw_tone_events(events=events)

        if not tones:
            canvas.configure(scrollregion=(0, 0, visible_width, height))
            canvas.xview_moveto(0.0)
            canvas.create_text(
                10,
                height // 2,
                text="Ei telemetriaa",
                anchor=tk.W,
                fill="#777777",
                font=("Segoe UI", 10),
            )
            return

        self.draw_raw_tone_events(
            canvas,
            tones,
            visible_width,
            height,
            events=events,
            freeze_time=freeze_time,
        )

    def raw_tone_events(
        self,
        *,
        events: Optional[List[Dict[str, Any]]] = None,
    ) -> list[Dict[str, Any]]:
        """Return sorted tone events suitable for raw telemetry drawing."""
        source_events = self.app.round.events if events is None else events

        tones = [
            event
            for event in source_events
            if event.get("type") == "tone"
            and isinstance(event.get("t0"), int)
            and isinstance(event.get("t1"), int)
            and isinstance(event.get("dur"), (int, float))
        ]

        # Live serial/keyboard telemetry is appended in arrival order. Avoid an
        # unnecessary full-list sort during every live redraw. Historical or
        # externally supplied events are still sorted defensively.
        if events is not None:
            tones.sort(key=lambda event: int(event["t0"]))

        return tones

    def raw_telemetry_unit_us(
        self,
        current_time_us: Optional[int],
        *,
        events: Optional[List[Dict[str, Any]]] = None,
    ) -> float:
        """Return the unit length used for raw telemetry scaling."""
        source_events = self.app.round.events if events is None else events

        try:
            if events is None:
                live_decoder = getattr(self.app, "live_decoder", None)
                if live_decoder is not None:
                    live_state = live_decoder.current_state()
                    if live_state.decoded is not None:
                        return max(20_000.0, float(live_state.decoded.visual_unit_us))

            decoded_for_scale = self.decode_tone_events(
                source_events,
                current_time_us=current_time_us,
                flush_final=False,
                seed_unit_us=self.adaptive_seed_unit_us(),
            )
            return max(20_000.0, float(decoded_for_scale.visual_unit_us))
        except Exception:
            return 60_000.0

    def draw_raw_tone_events(
        self,
        canvas: tk.Canvas,
        tones: list[Dict[str, Any]],
        visible_width: int,
        height: int,
        *,
        events: Optional[List[Dict[str, Any]]] = None,
        freeze_time: bool = False,
    ) -> None:
        """Draw already-filtered tone events on the raw telemetry canvas."""
        app = self.app
        helpers = app.ui_helpers_controller

        first_t = int(tones[0]["t0"])
        last_t = int(tones[-1]["t1"])

        if freeze_time:
            current_time_us = None
        else:
            current_time_us = self.adaptive_current_device_time_us()

        if current_time_us is not None:
            last_t = max(last_t, int(current_time_us))

        unit_us = self.raw_telemetry_unit_us(
            current_time_us,
            events=events,
        )

        px_per_unit = helpers.safe_float_var(
            app.raw_telemetry_pixels_per_unit_var,
            default=float(getattr(config, "RAW_TELEMETRY_PIXELS_PER_UNIT", 8.0)),
            minimum=2.0,
            maximum=80.0,
        )

        px_per_us = px_per_unit / unit_us
        total_us = max(1, last_t - first_t)

        virtual_width = int(total_us * px_per_us) + 40
        virtual_width = max(
            visible_width,
            min(
                int(getattr(config, "RAW_TELEMETRY_MAX_CANVAS_WIDTH", 20000)),
                virtual_width,
            ),
        )

        canvas.configure(scrollregion=(0, 0, virtual_width, height))

        y_mid = height // 2
        y1 = y_mid - 12
        y2 = y_mid + 12

        canvas.create_line(
            0,
            y_mid,
            virtual_width,
            y_mid,
            fill="#d9d9d9",
            width=1,
        )

        for event in tones:
            x1 = int((int(event["t0"]) - first_t) * px_per_us) + 20
            x2 = int((int(event["t1"]) - first_t) * px_per_us) + 20

            if x2 <= x1:
                x2 = x1 + 1

            canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill="#111111",
                outline="#111111",
            )

        if getattr(app, "raw_telemetry_follow_latest", True):
            canvas.xview_moveto(1.0)
