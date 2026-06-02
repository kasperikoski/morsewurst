# ============================================================
# morsewurst/ui/controllers/settings_controller.py
# ============================================================

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tkinter as tk

import morsewurst.config as config
from morsewurst.core.app_logging import log_app_event, log_app_exception, summarize_ui_settings

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class SettingsController:
    """Owns loading, validating and saving Morsewurst UI settings."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def ui_settings_path(self) -> Path:
        """Return the path used for persistent UI settings."""
        return config.DATA_DIR / "ui_settings.json"

    def load_ui_settings(self) -> None:
        """Load all saved UI settings into the current Tk variables."""
        log_app_event(
            "app.settings.load_started",
            message="UI settings load started.",
            context={"path": str(self.ui_settings_path())},
        )
        data = self.read_ui_settings_file()

        self.load_language_setting(data)

        if not data:
            log_app_event(
                "app.settings.applied",
                message="Default UI settings applied.",
                context={"source": "defaults"},
            )
            return

        self.load_main_training_settings(data)
        self.load_input_and_serial_settings(data)
        self.load_advanced_stat_settings(data)
        self.load_koch_settings(data)
        self.load_window_settings(data)
        log_app_event(
            "app.settings.applied",
            message="Saved UI settings applied.",
            context=summarize_ui_settings(data),
        )

    def load_language_setting(self, data: dict[str, Any]) -> None:
        """Load the saved language setting and apply it to the i18n service."""
        language = self.language_from_data(data)

        old_language = getattr(self.app.i18n, "language", "")
        self.app.i18n.set_language(language)
        if old_language != self.app.i18n.language:
            log_app_event(
                "app.i18n.language_loaded",
                message="Application language loaded.",
                context={
                    "requested_language": language,
                    "active_language": self.app.i18n.language,
                    "previous_language": old_language,
                },
            )

        try:
            self.app.language_var.set(self.app.i18n.language)
        except Exception:
            pass

    def language_from_data(self, data: dict[str, Any]) -> str:
        """Return a normalized language code from saved UI settings data."""
        return self.app.i18n.normalize_language(data.get("language"))
    
    def current_language(self) -> str:
        """Return the currently selected normalized UI language code."""
        try:
            return self.app.i18n.normalize_language(self.app.language_var.get())
        except Exception:
            return self.app.i18n.language

    def read_ui_settings_file(self) -> dict[str, Any]:
        """Read ui_settings.json and return a dictionary, or an empty dict on failure."""
        path = self.ui_settings_path()

        if not path.exists():
            log_app_event(
                "app.settings.file_missing",
                message="UI settings file does not exist; defaults will be used.",
                context={"path": str(path)},
            )
            return {}

        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            log_app_exception(
                "app.settings.load_failed",
                exc,
                level="warning",
                message="UI settings file could not be read.",
                context={"path": str(path)},
            )
            return {}

        if not isinstance(data, dict):
            log_app_event(
                "app.settings.invalid_json",
                level="warning",
                message="UI settings file did not contain a JSON object.",
                context={"path": str(path), "data_type": type(data).__name__},
            )
            return {}

        log_app_event(
            "app.settings.load_success",
            message="UI settings file loaded.",
            context={"path": str(path), **summarize_ui_settings(data)},
        )
        return data

    def load_main_training_settings(self, data: dict[str, Any]) -> None:
        """Load main practice, target generation, WX-MOR and sound settings."""
        app = self.app

        self.set_int_from_data(data, "target_wpm", app.target_wpm_var, 5, 80)
        self.set_int_from_data(data, "practice_rounds", app.practice_rounds_var, 1, 1000)
        self.set_int_from_data(data, "min_groups", app.min_groups_var, 1, 100)
        self.set_int_from_data(data, "max_groups", app.max_groups_var, 1, 100)
        self.set_int_from_data(data, "min_chars", app.min_chars_var, 1, 100)
        self.set_int_from_data(data, "max_chars", app.max_chars_var, 1, 100)

        self.set_bool_from_data(data, "use_letters", app.use_letters_var)
        self.set_bool_from_data(data, "use_numbers", app.use_numbers_var)
        self.set_bool_from_data(data, "use_punctuation", app.use_punctuation_var)
        self.set_int_from_data(
            data,
            "character_mix_letters_percent",
            app.character_mix_letters_var,
            0,
            100,
        )
        self.set_int_from_data(
            data,
            "character_mix_numbers_percent",
            app.character_mix_numbers_var,
            0,
            100,
        )
        self.set_int_from_data(
            data,
            "character_mix_punctuation_percent",
            app.character_mix_punctuation_var,
            0,
            100,
        )
        self.set_bool_from_data(
            data,
            "practice_problem_chars",
            app.practice_problem_chars_var,
        )
        self.set_bool_from_data(data, "practice_wxmor", app.practice_wxmor_var)

        saved_wxmor_profile = str(
            data.get(
                "wxmor_profile",
                getattr(config, "DEFAULT_WXMOR_PROFILE", "auto"),
            )
        )

        app.wxmor_profile_var.set(
            app.wxmor_controller.profile_label_from_value(
                app.wxmor_controller.profile_value_from_label(saved_wxmor_profile)
            )
        )

        self.set_bool_from_data(data, "sound_enabled", app.sound_enabled_var)

        sound_keys = {
            "sound_practice_complete": "practice_complete",
            "sound_serial_connected": "serial_connected",
            "sound_serial_disconnected": "serial_disconnected",
            "sound_level_up": "level_up",
        }

        for data_key, event_key in sound_keys.items():
            self.set_bool_from_data(data, data_key, app.sound_event_vars[event_key])

    def load_input_and_serial_settings(self, data: dict[str, Any]) -> None:
        """Load telemetry, serial, keyboard Morse, decoder, debug and raw display settings."""
        app = self.app

        self.set_bool_from_data(
            data,
            "use_telemetry_as_truth",
            app.use_telemetry_as_truth_var,
        )
        self.set_bool_from_data(data, "keep_focus", app.keep_focus_var)
        self.set_bool_from_data(
            data,
            "auto_connect_serial",
            app.auto_connect_serial_var,
        )

        self.set_bool_from_data(
            data,
            "keyboard_morse_enabled",
            app.keyboard_morse_enabled_var,
        )
        self.set_string_from_data(
            data,
            "keyboard_morse_key",
            app.keyboard_morse_key_var,
        )

        app.keyboard_morse_key_label_var.set(
            app.input_controller.keyboard_morse_label_from_key(
                app.keyboard_morse_key_var.get()
            )
        )

        app.input_controller.apply_keyboard_morse_setting_constraints(
            show_status=False,
        )

        self.set_bool_from_data(
            data,
            "use_timing_profile",
            app.use_timing_profile_var,
        )

        self.set_int_from_data(
            data,
            "decoder_profile_recent_rounds",
            app.decoder_profile_recent_rounds_var,
            int(getattr(config, "DECODER_PROFILE_MIN_ROUNDS_REQUIRED", 100)),
            100000,
        )

        self.set_int_from_data(
            data,
            "decoder_profile_min_accuracy",
            app.decoder_profile_min_accuracy_var,
            0,
            100,
        )

        self.set_int_from_data(
            data,
            "decoder_profile_min_cleanliness",
            app.decoder_profile_min_cleanliness_var,
            0,
            100,
        )

        self.set_bool_from_data(
            data,
            "auto_finish_on_idle",
            app.auto_finish_on_idle_var,
        )

        self.set_int_from_data(
            data,
            "auto_finish_idle_units",
            app.auto_finish_idle_units_var,
            3,
            100,
        )

        self.set_int_from_data(
            data,
            "auto_finish_min_seconds",
            app.auto_finish_min_seconds_var,
            1,
            30,
        )

        self.set_bool_from_data(
            data,
            "debug_snapshot_enabled",
            app.debug_snapshot_enabled_var,
        )
        self.set_bool_from_data(
            data,
            "debug_snapshot_save_history",
            app.debug_snapshot_save_history_var,
        )

        self.set_float_from_data(
            data,
            "raw_telemetry_pixels_per_unit",
            app.raw_telemetry_pixels_per_unit_var,
            2.0,
            80.0,
        )

        self.set_string_from_data(data, "selected_port", app.port_var)

    def load_advanced_stat_settings(self, data: dict[str, Any]) -> None:
        """Load advanced statistics, skill rating and effective WPM settings."""
        app = self.app

        self.set_int_from_data(
            data,
            "problem_recent_rounds",
            app.problem_recent_rounds_var,
            1,
            100000,
        )
        self.set_int_from_data(
            data,
            "problem_char_weight_percent",
            app.problem_char_weight_percent_var,
            0,
            100,
        )
        self.set_int_from_data(
            data,
            "problem_char_limit",
            app.problem_char_limit_var,
            1,
            100,
        )

        self.set_int_from_data(
            data,
            "stats_recent_rounds",
            app.stats_recent_rounds_var,
            1,
            100000,
        )
        self.set_int_from_data(
            data,
            "skill_recent_rounds",
            app.skill_recent_rounds_var,
            1,
            100000,
        )

        self.set_int_from_data(
            data,
            "effective_wpm_recent_rounds",
            app.effective_wpm_recent_rounds_var,
            1,
            100000,
        )

        self.set_int_from_data(
            data,
            "effective_wpm_min_accuracy",
            app.effective_wpm_min_accuracy_var,
            0,
            100,
        )

        self.set_int_from_data(
            data,
            "effective_wpm_min_cleanliness",
            app.effective_wpm_min_cleanliness_var,
            0,
            100,
        )

    def load_koch_settings(self, data: dict[str, Any]) -> None:
        """Load Koch receive-practice settings."""
        app = self.app

        self.set_string_from_data(
            data,
            "koch_mode",
            app.koch_controller.mode_var,
        )
        self.set_string_from_data(
            data,
            "koch_sequence_key",
            app.koch_controller.sequence_key_var,
        )
        self.set_int_from_data(
            data,
            "koch_stage_index",
            app.koch_controller.stage_index_var,
            1,
            1000,
        )
        self.set_int_from_data(
            data,
            "koch_target_chars",
            app.koch_controller.target_chars_var,
            30,
            5000,
        )
        self.set_int_from_data(
            data,
            "koch_character_wpm",
            app.koch_controller.character_wpm_var,
            5,
            80,
        )
        self.set_int_from_data(
            data,
            "koch_effective_wpm",
            app.koch_controller.effective_wpm_var,
            5,
            80,
        )
        self.set_int_from_data(
            data,
            "koch_tone_hz",
            app.koch_controller.tone_hz_var,
            100,
            2000,
        )
        self.set_int_from_data(
            data,
            "koch_volume_percent",
            app.koch_controller.volume_percent_var,
            0,
            100,
        )
        self.set_string_from_data(
            data,
            "koch_window_geometry",
            app.koch_controller.window_geometry_var,
        )

        self.set_int_from_data(
            data,
            "koch_auto_score_delay_ms",
            app.koch_controller.auto_score_delay_ms_var,
            0,
            10000,
        )

    def load_window_settings(self, data: dict[str, Any]) -> None:
        """Restore main window geometry when a valid saved value exists."""
        geometry = data.get("window_geometry")

        if isinstance(geometry, str) and geometry:
            try:
                self.app.geometry(geometry)
            except Exception:
                pass

    def set_int_from_data(
        self,
        data: dict[str, Any],
        name: str,
        variable: tk.IntVar,
        minimum: int,
        maximum: int,
    ) -> None:
        """Load an integer setting into a Tk variable with min and max bounds."""
        try:
            value = int(data.get(name))
        except Exception:
            return

        variable.set(max(minimum, min(maximum, value)))

    def set_float_from_data(
        self,
        data: dict[str, Any],
        name: str,
        variable: tk.DoubleVar,
        minimum: float,
        maximum: float,
    ) -> None:
        """Load a float setting into a Tk variable with min and max bounds."""
        try:
            value = float(data.get(name))
        except Exception:
            return

        variable.set(max(minimum, min(maximum, value)))

    def set_bool_from_data(
        self,
        data: dict[str, Any],
        name: str,
        variable: tk.BooleanVar,
    ) -> None:
        """Load a boolean setting into a Tk variable when the stored value is valid."""
        value = data.get(name)

        if isinstance(value, bool):
            variable.set(value)

    def set_string_from_data(
        self,
        data: dict[str, Any],
        name: str,
        variable: tk.StringVar,
    ) -> None:
        """Load a string setting into a Tk variable when the stored value is valid."""
        value = data.get(name)

        if isinstance(value, str):
            variable.set(value)

    def save_ui_settings(self) -> None:
        """Persist current UI settings to ui_settings.json."""
        path = self.ui_settings_path()
        data = self.ui_settings_data()
        self._write_ui_settings_file(path, data)

    def save_ui_settings_async(self) -> None:
        """Persist current UI settings without blocking the Tk event loop.

        Tk variables must be read on the UI thread. Only the disk write runs in
        the background thread.
        """
        path = self.ui_settings_path()

        try:
            data = self.ui_settings_data()
        except Exception as exc:
            log_app_exception(
                "app.settings.save_collect_failed",
                exc,
                level="warning",
                message="Collecting UI settings before async save failed.",
                context={"path": str(path)},
            )
            self._show_save_failed_status(exc)
            return

        worker = threading.Thread(
            target=self._write_ui_settings_file,
            args=(path, data),
            daemon=True,
        )
        worker.start()

    def _write_ui_settings_file(self, path: Path, data: dict[str, Any]) -> None:
        """Write already collected UI settings to disk.

        This method must not read Tk variables. It is safe to run in a worker
        thread because all UI data has already been collected.
        """
        log_app_event(
            "app.settings.save_started",
            message="UI settings save started.",
            context={"path": str(path), **summarize_ui_settings(data)},
        )

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            with path.open("w", encoding="utf-8") as handle:
                json.dump(
                    data,
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )

            log_app_event(
                "app.settings.save_success",
                message="UI settings saved.",
                context={"path": str(path), **summarize_ui_settings(data)},
            )
        except Exception as exc:
            log_app_exception(
                "app.settings.save_failed",
                exc,
                message="UI settings save failed.",
                context={"path": str(path)},
            )
            self._show_save_failed_status(exc)

    def _show_save_failed_status(self, exc: Exception) -> None:
        """Show a save error in the UI from either the UI thread or a worker."""
        def update_status() -> None:
            try:
                self.app.status_var.set(f"Asetusten tallennus epäonnistui: {exc}")
            except Exception:
                pass

        try:
            self.app.after(0, update_status)
        except Exception:
            pass

    def ui_settings_data(self) -> dict[str, Any]:
        """Build the serializable dictionary stored in ui_settings.json."""
        app = self.app
        helpers = app.ui_helpers_controller

        return {
            "language": self.current_language(),
            "target_wpm": helpers.safe_int_var(
                app.target_wpm_var,
                default=config.DEFAULT_TARGET_WPM,
                minimum=5,
                maximum=80,
            ),
            "practice_rounds": helpers.safe_int_var(
                app.practice_rounds_var,
                default=config.DEFAULT_PRACTICE_ROUNDS,
                minimum=1,
                maximum=1000,
            ),
            "min_groups": helpers.safe_int_var(
                app.min_groups_var,
                default=config.DEFAULT_MIN_GROUPS,
                minimum=1,
                maximum=100,
            ),
            "max_groups": helpers.safe_int_var(
                app.max_groups_var,
                default=config.DEFAULT_MAX_GROUPS,
                minimum=1,
                maximum=100,
            ),
            "min_chars": helpers.safe_int_var(
                app.min_chars_var,
                default=config.DEFAULT_MIN_CHARS_PER_GROUP,
                minimum=1,
                maximum=100,
            ),
            "max_chars": helpers.safe_int_var(
                app.max_chars_var,
                default=config.DEFAULT_MAX_CHARS_PER_GROUP,
                minimum=1,
                maximum=100,
            ),
            "use_letters": bool(app.use_letters_var.get()),
            "use_numbers": bool(app.use_numbers_var.get()),
            "use_punctuation": bool(app.use_punctuation_var.get()),
            "character_mix_letters_percent": helpers.safe_int_var(
                app.character_mix_letters_var,
                default=int(getattr(config, "DEFAULT_CHARACTER_MIX_LETTERS_PERCENT", 70)),
                minimum=0,
                maximum=100,
            ),
            "character_mix_numbers_percent": helpers.safe_int_var(
                app.character_mix_numbers_var,
                default=int(getattr(config, "DEFAULT_CHARACTER_MIX_NUMBERS_PERCENT", 25)),
                minimum=0,
                maximum=100,
            ),
            "character_mix_punctuation_percent": helpers.safe_int_var(
                app.character_mix_punctuation_var,
                default=int(getattr(config, "DEFAULT_CHARACTER_MIX_PUNCTUATION_PERCENT", 5)),
                minimum=0,
                maximum=100,
            ),
            "practice_problem_chars": bool(app.practice_problem_chars_var.get()),
            "practice_wxmor": bool(app.practice_wxmor_var.get()),
            "wxmor_profile": app.wxmor_controller.profile(),
            "sound_enabled": bool(app.sound_enabled_var.get()),
            "sound_practice_complete": bool(
                app.sound_event_vars["practice_complete"].get()
            ),
            "sound_serial_connected": bool(
                app.sound_event_vars["serial_connected"].get()
            ),
            "sound_serial_disconnected": bool(
                app.sound_event_vars["serial_disconnected"].get()
            ),
            "sound_level_up": bool(app.sound_event_vars["level_up"].get()),
            "use_telemetry_as_truth": bool(app.use_telemetry_as_truth_var.get()),
            "keep_focus": bool(app.keep_focus_var.get()),
            "auto_connect_serial": bool(app.auto_connect_serial_var.get()),
            "keyboard_morse_enabled": bool(app.keyboard_morse_enabled_var.get()),
            "keyboard_morse_key": str(app.keyboard_morse_key_var.get() or "space"),
            "use_timing_profile": bool(app.use_timing_profile_var.get()),
            "decoder_profile_recent_rounds": helpers.safe_int_var(
                app.decoder_profile_recent_rounds_var,
                default=int(getattr(config, "DECODER_PROFILE_RECENT_ROUNDS", 300)),
                minimum=int(getattr(config, "DECODER_PROFILE_MIN_ROUNDS_REQUIRED", 100)),
                maximum=100000,
            ),
            "decoder_profile_min_accuracy": helpers.safe_int_var(
                app.decoder_profile_min_accuracy_var,
                default=int(getattr(config, "DECODER_PROFILE_MIN_ACCURACY", 90)),
                minimum=0,
                maximum=100,
            ),
            "decoder_profile_min_cleanliness": helpers.safe_int_var(
                app.decoder_profile_min_cleanliness_var,
                default=int(getattr(config, "DECODER_PROFILE_MIN_CLEANLINESS", 85)),
                minimum=0,
                maximum=100,
            ),
            "auto_finish_on_idle": bool(app.auto_finish_on_idle_var.get()),
            "auto_finish_idle_units": helpers.safe_int_var(
                app.auto_finish_idle_units_var,
                default=int(getattr(config, "DECODER_AUTO_FINISH_IDLE_UNITS", 14.0)),
                minimum=3,
                maximum=100,
            ),
            "auto_finish_min_seconds": helpers.safe_int_var(
                app.auto_finish_min_seconds_var,
                default=int(getattr(config, "DECODER_AUTO_FINISH_MIN_SECONDS", 2.0)),
                minimum=1,
                maximum=30,
            ),
            "debug_snapshot_enabled": bool(app.debug_snapshot_enabled_var.get()),
            "debug_snapshot_save_history": bool(
                app.debug_snapshot_save_history_var.get()
            ),
            "raw_telemetry_pixels_per_unit": helpers.safe_float_var(
                app.raw_telemetry_pixels_per_unit_var,
                default=float(getattr(config, "RAW_TELEMETRY_PIXELS_PER_UNIT", 8.0)),
                minimum=2.0,
                maximum=80.0,
            ),
            "selected_port": str(app.port_var.get()),
            "problem_recent_rounds": helpers.safe_int_var(
                app.problem_recent_rounds_var,
                default=config.DEFAULT_PROBLEM_RECENT_ROUNDS,
                minimum=1,
                maximum=100000,
            ),
            "problem_char_weight_percent": helpers.safe_int_var(
                app.problem_char_weight_percent_var,
                default=getattr(config, "DEFAULT_PROBLEM_CHAR_WEIGHT_PERCENT", 30),
                minimum=0,
                maximum=100,
            ),
            "problem_char_limit": helpers.safe_int_var(
                app.problem_char_limit_var,
                default=getattr(config, "DEFAULT_PROBLEM_CHAR_LIMIT", 12),
                minimum=1,
                maximum=100,
            ),
            "stats_recent_rounds": helpers.safe_int_var(
                app.stats_recent_rounds_var,
                default=1000,
                minimum=1,
                maximum=100000,
            ),
            "skill_recent_rounds": helpers.safe_int_var(
                app.skill_recent_rounds_var,
                default=getattr(config, "DEFAULT_SKILL_RATING_RECENT_ROUNDS", 1000),
                minimum=1,
                maximum=100000,
            ),
            "effective_wpm_recent_rounds": helpers.safe_int_var(
                app.effective_wpm_recent_rounds_var,
                default=getattr(config, "DEFAULT_EFFECTIVE_WPM_RECENT_ROUNDS", 1000),
                minimum=1,
                maximum=100000,
            ),
            "effective_wpm_min_accuracy": helpers.safe_int_var(
                app.effective_wpm_min_accuracy_var,
                default=getattr(config, "DEFAULT_EFFECTIVE_WPM_MIN_ACCURACY", 90),
                minimum=0,
                maximum=100,
            ),
            "effective_wpm_min_cleanliness": helpers.safe_int_var(
                app.effective_wpm_min_cleanliness_var,
                default=getattr(config, "DEFAULT_EFFECTIVE_WPM_MIN_CLEANLINESS", 85),
                minimum=0,
                maximum=100,
            ),
            "koch_mode": str(
                app.koch_controller.mode_var.get()
                or getattr(config, "DEFAULT_KOCH_MODE", "guided")
            ),
            "koch_sequence_key": str(
                app.koch_controller.sequence_key_var.get()
                or getattr(config, "DEFAULT_KOCH_SEQUENCE", "classic")
            ),
            "koch_stage_index": helpers.safe_int_var(
                app.koch_controller.stage_index_var,
                default=getattr(config, "DEFAULT_KOCH_STAGE_INDEX", 2),
                minimum=1,
                maximum=1000,
            ),
            "koch_target_chars": helpers.safe_int_var(
                app.koch_controller.target_chars_var,
                default=getattr(config, "DEFAULT_KOCH_TARGET_CHARS", 30),
                minimum=30,
                maximum=5000,
            ),
            "koch_character_wpm": helpers.safe_int_var(
                app.koch_controller.character_wpm_var,
                default=getattr(config, "DEFAULT_KOCH_CHARACTER_WPM", 20),
                minimum=5,
                maximum=80,
            ),
            "koch_effective_wpm": helpers.safe_int_var(
                app.koch_controller.effective_wpm_var,
                default=getattr(config, "DEFAULT_KOCH_EFFECTIVE_WPM", 15),
                minimum=5,
                maximum=80,
            ),
            "koch_tone_hz": helpers.safe_int_var(
                app.koch_controller.tone_hz_var,
                default=getattr(config, "DEFAULT_KOCH_TONE_HZ", 600),
                minimum=100,
                maximum=2000,
            ),
            "koch_volume_percent": helpers.safe_int_var(
                app.koch_controller.volume_percent_var,
                default=getattr(config, "DEFAULT_KOCH_VOLUME_PERCENT", 70),
                minimum=0,
                maximum=100,
            ),
            "koch_window_geometry": str(
                app.koch_controller.window_geometry_var.get()
                or getattr(config, "UI_KOCH_WINDOW_GEOMETRY", "1260x1000")
            ),
            "koch_auto_score_delay_ms": helpers.safe_int_var(
                app.koch_controller.auto_score_delay_ms_var,
                default=getattr(config, "DEFAULT_KOCH_AUTO_SCORE_DELAY_MS", 1500),
                minimum=0,
                maximum=10000,
            ),
            "window_geometry": app.geometry(),
        }