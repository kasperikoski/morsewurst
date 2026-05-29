# ============================================================
# morsewurst/ui/controllers/runtime_controller.py
# ============================================================

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any

import tkinter as tk

import morsewurst.config as config
from morsewurst.models import CharacterResult, RoundState, ScoreSummary
from morsewurst.network.manager import NetworkManager

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class RuntimeController:
    """Owns app runtime state, Tk variables, static bindings and repeating timers."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def init_runtime_state(self) -> None:
        """Initialise non-widget runtime attributes used by the application."""
        app = self.app

        app.settings = app.challenge_settings_controller.default_settings()
        app.round = RoundState()

        app.practice_running = False
        app.current_round_number = 0
        app.total_rounds = config.DEFAULT_PRACTICE_ROUNDS
        app.practice_summaries: list[ScoreSummary] = []

        app.last_summary: ScoreSummary | None = None
        app.last_char_results: list[CharacterResult] = []
        app.last_tone_event_key: tuple[str, int, int] | None = None
        app.viewing_history_session_id: int | None = None

        app.stats_window: tk.Toplevel | None = None
        app.debug_window: tk.Toplevel | None = None
        app.live_decoder: Any | None = None
        app.live_ui_dirty = False
        app.live_result_dirty = False
        app.last_live_ui_refresh_monotonic = 0.0
        app.last_live_score_refresh_monotonic = 0.0

        app.network_manager = NetworkManager()
        app.network_window: tk.Toplevel | None = None
        app.network_modal_active = False

        app.timing_profiles: dict[str, Any] = (
            app.decoder_controller.default_timing_profiles()
        )

        app.serial_connected = False
        app.auto_connect_running = False
        app.auto_connect_thread: threading.Thread | None = None

        app.keyboard_morse_pressed = False
        app.keyboard_morse_press_t0_us: int | None = None
        app.keyboard_morse_press_key = ""
        app.keyboard_morse_time_base = time.monotonic()
        app.keyboard_morse_monitor_controls: list[tk.Widget] = []

        app.start_trigger_timestamps: list[float] = []
        app.start_trigger_count = 7
        app.start_trigger_window_seconds = 3.0

        app.start_countdown_running = False
        app.start_countdown_after_id: str | None = None
        app.start_countdown_started_at: float | None = None
        app.start_countdown_duration_seconds = 3.0
        app.start_countdown_generation = 0
        app.start_countdown_bar_height = 18
        app.latest_result_reset_for_current_round = False

        app.wxmor_disabled_widgets: list[tk.Widget] = []

    def bind_static_events(self) -> None:
        """Bind application-level events after the main widgets have been built."""
        app = self.app

        if hasattr(app, "stop_button"):
            app.stop_button.bind("<space>", lambda _event: "break")
            app.stop_button.bind("<Return>", lambda _event: "break")

        app.bind_all(
            "<KeyPress>",
            app.input_controller.on_global_keyboard_morse_key_press,
        )
        app.bind_all(
            "<KeyRelease>",
            app.input_controller.on_global_keyboard_morse_key_release,
        )

        app.bind(
            "<FocusIn>",
            lambda _event: app.app_lifecycle_controller.focus_input(force=False),
        )
        app.bind(
            "<FocusOut>",
            lambda _event: app.input_controller.cancel_keyboard_morse_press(),
        )

    def start_timers(self) -> None:
        """Start repeating UI timers for serial polling, round timer and auto-connect."""
        app = self.app

        app.after(
            config.UI_POLL_INTERVAL_MS,
            app.input_controller.poll_serial_events,
        )
        app.after(
            config.TIMER_TICK_MS,
            app.practice_controller.tick_timer,
        )
        app.after(
            300,
            app.serial_controller.auto_connect_tick,
        )

    def init_variables(self) -> None:
        """Initialise all Tkinter variables used by the UI."""
        app = self.app

        app.target_var = tk.StringVar(value=app.i18n.t("runtime.target_placeholder"))
        app.input_var = tk.StringVar(value="")
        app.telemetry_display_var = tk.StringVar(value="")

        app.status_var = tk.StringVar(value=app.i18n.t("runtime.status_ready"))
        app.morse_preview_button_var = tk.StringVar(value=app.i18n.t("runtime.morse_preview_button"))
        app.serial_status_var = tk.StringVar(value=app.i18n.t("runtime.serial_disconnected"))
        app.last_event_var = tk.StringVar(value=app.i18n.t("runtime.last_event_placeholder"))

        self.init_result_vars()
        self.init_skill_vars()
        self.init_setting_vars()

    def init_result_vars(self) -> None:
        """Initialise result, timer and round-state display variables."""
        app = self.app

        app.result_practice_rounds_var = tk.StringVar(value="-")
        app.result_practice_accuracy_var = tk.StringVar(value="-")
        app.result_practice_cleanliness_var = tk.StringVar(value="-")
        app.result_practice_score_var = tk.StringVar(value="-")
        app.result_practice_timing_var = tk.StringVar(value="-")
        app.result_practice_gross_wpm_var = tk.StringVar(value="-")
        app.result_practice_net_wpm_var = tk.StringVar(value="-")
        app.result_practice_device_wpm_var = tk.StringVar(value="-")
        app.result_practice_straight_ratio_var = tk.StringVar(value="-")
        app.result_practice_dot_variation_var = tk.StringVar(value="-")
        app.result_practice_dash_variation_var = tk.StringVar(value="-")
        app.result_practice_element_variation_var = tk.StringVar(value="-")

        app.result_latest_title_var = tk.StringVar(value=app.i18n.t("runtime.latest_round_title"))
        app.result_latest_accuracy_var = tk.StringVar(value="-")
        app.result_latest_cleanliness_var = tk.StringVar(value="-")
        app.result_latest_score_var = tk.StringVar(value="-")
        app.result_latest_timing_var = tk.StringVar(value="-")
        app.result_latest_errors_var = tk.StringVar(value="-")
        app.result_latest_substitutions_var = tk.StringVar(value="-")
        app.result_latest_insertions_var = tk.StringVar(value="-")
        app.result_latest_deletions_var = tk.StringVar(value="-")
        app.result_latest_extra_missing_var = tk.StringVar(value="-")
        app.result_latest_straight_ratio_var = tk.StringVar(value="-")
        app.result_latest_dot_variation_var = tk.StringVar(value="-")
        app.result_latest_dash_variation_var = tk.StringVar(value="-")

        app.result_history_rounds_var = tk.StringVar(value="-")
        app.result_history_accuracy_var = tk.StringVar(value="-")
        app.result_history_cleanliness_var = tk.StringVar(value="-")
        app.result_history_score_var = tk.StringVar(value="-")
        app.result_history_gross_wpm_var = tk.StringVar(value="-")
        app.result_history_net_wpm_var = tk.StringVar(value="-")
        app.result_history_device_wpm_var = tk.StringVar(value="-")
        app.result_history_straight_ratio_var = tk.StringVar(value="-")
        app.result_history_dot_variation_var = tk.StringVar(value="-")
        app.result_history_dash_variation_var = tk.StringVar(value="-")

        app.general_straight_presses_var = tk.StringVar(value="-")
        app.general_iambic_elements_var = tk.StringVar(value="-")
        app.general_tone_total_var = tk.StringVar(value="-")
        app.general_straight_chars_var = tk.StringVar(value="-")
        app.general_iambic_chars_var = tk.StringVar(value="-")

        app.keying_event_summary = {
            "straight_presses": 0,
            "iambic_elements": 0,
            "tone_total": 0,
            "straight_chars": 0,
            "iambic_chars": 0,
            "produced_chars_total": 0,
        }
        app.keying_event_summary_loaded = False
        app.keying_event_summary_loading = False
        app.keying_event_summary_startup_scheduled = False

        app.timer_var = tk.StringVar(value=app.i18n.t("runtime.timer_placeholder"))
        app.round_state_var = tk.StringVar(value=app.i18n.t("runtime.round_state_inactive"))

    def init_skill_vars(self) -> None:
        """Initialise skill rating display variables."""
        app = self.app

        app.skill_title_var = tk.StringVar(value="-")

        app.skill_overall_wpm_value_var = tk.StringVar(value="-")
        app.skill_both_wpm_value_var = tk.StringVar(value="-")
        app.skill_next_level_value_var = tk.StringVar(value="-")
        app.skill_straight_wpm_value_var = tk.StringVar(value="-")
        app.skill_iambic_wpm_value_var = tk.StringVar(value="-")

        app.skill_accuracy_value_var = tk.StringVar(value="-")
        app.skill_cleanliness_value_var = tk.StringVar(value="-")
        app.skill_timing_value_var = tk.StringVar(value="-")
        app.skill_adjustment_value_var = tk.StringVar(value="-")
        app.skill_confidence_value_var = tk.StringVar(value="-")
        app.skill_mastery_value_var = tk.StringVar(value="-")
        app.skill_coverage_value_var = tk.StringVar(value="-")
        app.skill_used_rounds_value_var = tk.StringVar(value="-")
        app.skill_total_used_rounds_value_var = tk.StringVar(value="-")
        app.skill_charset_coverage_value_var = tk.StringVar(value="-")
        app.skill_charset_scope_value_var = tk.StringVar(value="-")
        app.skill_warning_var = tk.StringVar(value="")

    def init_setting_vars(self) -> None:
        """Initialise settings and option variables."""
        app = self.app

        app.port_var = tk.StringVar(value="")
        app.language_var = tk.StringVar(value=app.i18n.language)

        app.use_letters_var = tk.BooleanVar(value=True)
        app.use_numbers_var = tk.BooleanVar(value=True)
        app.use_punctuation_var = tk.BooleanVar(value=False)
        app.character_mix_letters_var = tk.IntVar(
            value=int(getattr(config, "DEFAULT_CHARACTER_MIX_LETTERS_PERCENT", 70))
        )
        app.character_mix_numbers_var = tk.IntVar(
            value=int(getattr(config, "DEFAULT_CHARACTER_MIX_NUMBERS_PERCENT", 25))
        )
        app.character_mix_punctuation_var = tk.IntVar(
            value=int(getattr(config, "DEFAULT_CHARACTER_MIX_PUNCTUATION_PERCENT", 5))
        )
        app.use_telemetry_as_truth_var = tk.BooleanVar(value=True)
        app.keep_focus_var = tk.BooleanVar(value=True)
        app.auto_connect_serial_var = tk.BooleanVar(
            value=getattr(config, "SERIAL_AUTO_CONNECT_DEFAULT", True)
        )

        app.keyboard_morse_enabled_var = tk.BooleanVar(
            value=bool(getattr(config, "KEYBOARD_MORSE_DEFAULT_ENABLED", False))
        )
        app.keyboard_morse_key_var = tk.StringVar(
            value=str(getattr(config, "KEYBOARD_MORSE_DEFAULT_KEY", "space"))
        )
        app.keyboard_morse_key_label_var = tk.StringVar(
            value=app.input_controller.keyboard_morse_label_from_key(
                str(getattr(config, "KEYBOARD_MORSE_DEFAULT_KEY", "space"))
            )
        )

        app.keyboard_morse_monitor_sound_var = tk.BooleanVar(
            value=bool(getattr(config, "DEFAULT_KEYBOARD_MORSE_MONITOR_SOUND", True))
        )
        app.keyboard_morse_monitor_frequency_hz_var = tk.IntVar(
            value=int(getattr(config, "DEFAULT_KEYBOARD_MORSE_MONITOR_FREQUENCY_HZ", 750))
        )
        app.keyboard_morse_monitor_volume_percent_var = tk.IntVar(
            value=int(getattr(config, "DEFAULT_KEYBOARD_MORSE_MONITOR_VOLUME_PERCENT", 35))
        )
        app.keyboard_morse_monitor_waveform_var = tk.StringVar(
            value=str(getattr(config, "DEFAULT_KEYBOARD_MORSE_MONITOR_WAVEFORM", "sine"))
        )
        

        app.use_timing_profile_var = tk.BooleanVar(
            value=bool(getattr(config, "DECODER_USE_TIMING_PROFILE_DEFAULT", True))
        )
        app.decoder_profile_recent_rounds_var = tk.IntVar(
            value=int(getattr(config, "DECODER_PROFILE_RECENT_ROUNDS", 300))
        )
        app.decoder_profile_min_accuracy_var = tk.IntVar(
            value=int(getattr(config, "DECODER_PROFILE_MIN_ACCURACY", 90.0))
        )
        app.decoder_profile_min_cleanliness_var = tk.IntVar(
            value=int(getattr(config, "DECODER_PROFILE_MIN_CLEANLINESS", 85.0))
        )

        app.auto_finish_on_idle_var = tk.BooleanVar(
            value=getattr(config, "DECODER_AUTO_FINISH_ON_IDLE", True)
        )
        app.auto_finish_idle_units_var = tk.IntVar(
            value=int(getattr(config, "DECODER_AUTO_FINISH_IDLE_UNITS", 14.0))
        )
        app.auto_finish_min_seconds_var = tk.IntVar(
            value=int(getattr(config, "DECODER_AUTO_FINISH_MIN_SECONDS", 2.0))
        )
        app.raw_telemetry_pixels_per_unit_var = tk.DoubleVar(
            value=float(getattr(config, "RAW_TELEMETRY_PIXELS_PER_UNIT", 8.0))
        )

        app.debug_snapshot_enabled_var = tk.BooleanVar(
            value=getattr(config, "DEBUG_SNAPSHOT_ENABLED_DEFAULT", False)
        )
        app.debug_snapshot_save_history_var = tk.BooleanVar(
            value=getattr(config, "DEBUG_SNAPSHOT_SAVE_HISTORY_DEFAULT", True)
        )

        app.practice_problem_chars_var = tk.BooleanVar(value=False)

        app.practice_wxmor_var = tk.BooleanVar(
            value=bool(getattr(config, "DEFAULT_PRACTICE_WXMOR", False))
        )
        app.wxmor_profile_var = tk.StringVar(
            value=app.wxmor_controller.profile_label_from_value(
                str(getattr(config, "DEFAULT_WXMOR_PROFILE", "auto"))
            )
        )

        app.sound_enabled_var = tk.BooleanVar(value=config.DEFAULT_SOUND_ENABLED)
        app.sound_event_vars: dict[str, tk.BooleanVar] = {
            "practice_complete": tk.BooleanVar(
                value=getattr(config, "DEFAULT_SOUND_PRACTICE_COMPLETE", True)
            ),
            "serial_connected": tk.BooleanVar(
                value=getattr(config, "DEFAULT_SOUND_SERIAL_CONNECTED", False)
            ),
            "serial_disconnected": tk.BooleanVar(
                value=getattr(config, "DEFAULT_SOUND_SERIAL_DISCONNECTED", True)
            ),
            "level_up": tk.BooleanVar(
                value=getattr(config, "DEFAULT_SOUND_LEVEL_UP", True)
            ),
        }

        app.problem_recent_rounds_var = tk.IntVar(value=config.DEFAULT_PROBLEM_RECENT_ROUNDS)
        app.problem_char_weight_percent_var = tk.IntVar(
            value=getattr(config, "DEFAULT_PROBLEM_CHAR_WEIGHT_PERCENT", 30)
        )
        app.problem_char_limit_var = tk.IntVar(
            value=getattr(config, "DEFAULT_PROBLEM_CHAR_LIMIT", 12)
        )

        app.stats_recent_rounds_var = tk.IntVar(value=1000)
        app.skill_recent_rounds_var = tk.IntVar(
            value=getattr(config, "DEFAULT_SKILL_RATING_RECENT_ROUNDS", 1000)
        )
        app.effective_wpm_recent_rounds_var = tk.IntVar(
            value=getattr(config, "DEFAULT_EFFECTIVE_WPM_RECENT_ROUNDS", 1000)
        )
        app.effective_wpm_min_accuracy_var = tk.IntVar(
            value=getattr(config, "DEFAULT_EFFECTIVE_WPM_MIN_ACCURACY", 90)
        )
        app.effective_wpm_min_cleanliness_var = tk.IntVar(
            value=getattr(config, "DEFAULT_EFFECTIVE_WPM_MIN_CLEANLINESS", 85)
        )

        app.min_groups_var = tk.IntVar(value=config.DEFAULT_MIN_GROUPS)
        app.max_groups_var = tk.IntVar(value=config.DEFAULT_MAX_GROUPS)
        app.min_chars_var = tk.IntVar(value=config.DEFAULT_MIN_CHARS_PER_GROUP)
        app.max_chars_var = tk.IntVar(value=config.DEFAULT_MAX_CHARS_PER_GROUP)
        app.practice_rounds_var = tk.IntVar(value=config.DEFAULT_PRACTICE_ROUNDS)
        app.target_wpm_var = tk.IntVar(value=config.DEFAULT_TARGET_WPM)
        app.target_wpm_suggestion_delta_var = tk.StringVar(value="")
        app.target_wpm_var.trace_add(
            "write",
            lambda *_args: app.history_controller.update_target_wpm_suggestion_indicator(),
        )