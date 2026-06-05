# ============================================================
# morsewurst/ui/controllers/challenge_settings_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

import morsewurst.config as config
from morsewurst.core.app_logging import log_app_event
from morsewurst.models import ChallengeSettings

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class ChallengeSettingsController:
    """Owns default challenge settings and settings collected from the UI."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def default_settings(self) -> ChallengeSettings:
        return ChallengeSettings(
            min_groups=config.DEFAULT_MIN_GROUPS,
            max_groups=config.DEFAULT_MAX_GROUPS,
            min_chars_per_group=config.DEFAULT_MIN_CHARS_PER_GROUP,
            max_chars_per_group=config.DEFAULT_MAX_CHARS_PER_GROUP,
            target_wpm=config.DEFAULT_TARGET_WPM,
            practice_rounds=config.DEFAULT_PRACTICE_ROUNDS,
            countdown_seconds=0,
            sound_enabled=config.DEFAULT_SOUND_ENABLED,
            character_mix_letters_percent=int(
                getattr(config, "DEFAULT_CHARACTER_MIX_LETTERS_PERCENT", 70)
            ),
            character_mix_numbers_percent=int(
                getattr(config, "DEFAULT_CHARACTER_MIX_NUMBERS_PERCENT", 25)
            ),
            character_mix_punctuation_percent=int(
                getattr(config, "DEFAULT_CHARACTER_MIX_PUNCTUATION_PERCENT", 5)
            ),
            problem_recent_rounds=config.DEFAULT_PROBLEM_RECENT_ROUNDS,
            problem_char_weight_percent=getattr(
                config,
                "DEFAULT_PROBLEM_CHAR_WEIGHT_PERCENT",
                30,
            ),
            problem_char_limit=getattr(
                config,
                "DEFAULT_PROBLEM_CHAR_LIMIT",
                12,
            ),
        )

    def settings_from_ui(self) -> ChallengeSettings:
        app = self.app
        helpers = app.ui_helpers_controller

        min_groups = helpers.safe_int_var(
            app.min_groups_var,
            default=config.DEFAULT_MIN_GROUPS,
            minimum=1,
            maximum=100,
        )
        max_groups = helpers.safe_int_var(
            app.max_groups_var,
            default=config.DEFAULT_MAX_GROUPS,
            minimum=1,
            maximum=100,
        )
        min_chars = helpers.safe_int_var(
            app.min_chars_var,
            default=config.DEFAULT_MIN_CHARS_PER_GROUP,
            minimum=1,
            maximum=100,
        )
        max_chars = helpers.safe_int_var(
            app.max_chars_var,
            default=config.DEFAULT_MAX_CHARS_PER_GROUP,
            minimum=1,
            maximum=100,
        )

        original_min_groups = min_groups
        original_max_groups = max_groups
        original_min_chars = min_chars
        original_max_chars = max_chars
        bounds_corrected = False

        if min_groups > max_groups:
            max_groups = min_groups
            app.max_groups_var.set(max_groups)
            bounds_corrected = True

        if min_chars > max_chars:
            max_chars = min_chars
            app.max_chars_var.set(max_chars)
            bounds_corrected = True

        if bounds_corrected:
            log_app_event(
                "app.settings.challenge_bounds_corrected",
                level="warning",
                message="Invalid challenge min/max bounds were corrected.",
                context={
                    "old_min_groups": original_min_groups,
                    "old_max_groups": original_max_groups,
                    "new_min_groups": min_groups,
                    "new_max_groups": max_groups,
                    "old_min_chars_per_group": original_min_chars,
                    "old_max_chars_per_group": original_max_chars,
                    "new_min_chars_per_group": min_chars,
                    "new_max_chars_per_group": max_chars,
                },
            )

        return ChallengeSettings(
            use_letters=app.use_letters_var.get(),
            use_numbers=app.use_numbers_var.get(),
            use_punctuation=app.use_punctuation_var.get(),
            character_mix_letters_percent=helpers.safe_int_var(
                app.character_mix_letters_var,
                default=int(getattr(config, "DEFAULT_CHARACTER_MIX_LETTERS_PERCENT", 70)),
                minimum=0,
                maximum=100,
            ),
            character_mix_numbers_percent=helpers.safe_int_var(
                app.character_mix_numbers_var,
                default=int(getattr(config, "DEFAULT_CHARACTER_MIX_NUMBERS_PERCENT", 25)),
                minimum=0,
                maximum=100,
            ),
            character_mix_punctuation_percent=helpers.safe_int_var(
                app.character_mix_punctuation_var,
                default=int(getattr(config, "DEFAULT_CHARACTER_MIX_PUNCTUATION_PERCENT", 5)),
                minimum=0,
                maximum=100,
            ),
            min_groups=min_groups,
            max_groups=max_groups,
            min_chars_per_group=min_chars,
            max_chars_per_group=max_chars,
            target_wpm=helpers.safe_int_var(
                app.target_wpm_var,
                default=config.DEFAULT_TARGET_WPM,
                minimum=5,
                maximum=80,
            ),
            practice_problem_chars=app.practice_problem_chars_var.get(),
            practice_rounds=helpers.safe_int_var(
                app.practice_rounds_var,
                default=config.DEFAULT_PRACTICE_ROUNDS,
                minimum=1,
                maximum=1000,
            ),
            countdown_seconds=0,
            sound_enabled=app.sound_enabled_var.get(),
            problem_recent_rounds=helpers.safe_int_var(
                app.problem_recent_rounds_var,
                default=config.DEFAULT_PROBLEM_RECENT_ROUNDS,
                minimum=1,
                maximum=100000,
            ),
            problem_char_weight_percent=helpers.safe_int_var(
                app.problem_char_weight_percent_var,
                default=getattr(config, "DEFAULT_PROBLEM_CHAR_WEIGHT_PERCENT", 30),
                minimum=0,
                maximum=100,
            ),
            problem_char_limit=helpers.safe_int_var(
                app.problem_char_limit_var,
                default=getattr(config, "DEFAULT_PROBLEM_CHAR_LIMIT", 12),
                minimum=1,
                maximum=100,
            ),
            auto_optimize_recent_rounds=helpers.safe_int_var(
                app.effective_wpm_recent_rounds_var,
                default=getattr(config, "DEFAULT_EFFECTIVE_WPM_RECENT_ROUNDS", 300),
                minimum=1,
                maximum=100000,
            ),
            auto_optimize_min_accuracy=helpers.safe_int_var(
                app.effective_wpm_min_accuracy_var,
                default=getattr(config, "DEFAULT_EFFECTIVE_WPM_MIN_ACCURACY", 90),
                minimum=0,
                maximum=100,
            ),
        )