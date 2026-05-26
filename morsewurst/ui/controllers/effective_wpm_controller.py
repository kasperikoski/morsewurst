# ============================================================
# morsewurst/ui/controllers/effective_wpm_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

from tkinter import messagebox

import morsewurst.config as config
from morsewurst.core.app_logging import log_app_event, log_app_exception

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class EffectiveWpmController:
    """Owns effective WPM estimation from practice history."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def optimize_timing_from_history(self) -> None:
        """Estimate a suitable target WPM from recent saved practice rounds."""
        app = self.app
        helpers = app.ui_helpers_controller

        recent_rounds = helpers.safe_int_var(
            app.effective_wpm_recent_rounds_var,
            default=getattr(config, "DEFAULT_EFFECTIVE_WPM_RECENT_ROUNDS", 1000),
            minimum=1,
            maximum=100000,
        )
        min_accuracy = helpers.safe_int_var(
            app.effective_wpm_min_accuracy_var,
            default=getattr(config, "DEFAULT_EFFECTIVE_WPM_MIN_ACCURACY", 90),
            minimum=0,
            maximum=100,
        )
        min_cleanliness = helpers.safe_int_var(
            app.effective_wpm_min_cleanliness_var,
            default=getattr(config, "DEFAULT_EFFECTIVE_WPM_MIN_CLEANLINESS", 85),
            minimum=0,
            maximum=100,
        )

        log_app_event(
            "app.effective_wpm.suggestion_started",
            message="Effective WPM suggestion calculation started.",
            context={
                "recent_rounds": recent_rounds,
                "min_accuracy": min_accuracy,
                "min_cleanliness": min_cleanliness,
            },
        )

        try:
            result = app.db.optimized_wpm_from_recent_sessions(
            recent_sessions=recent_rounds,
            min_accuracy=min_accuracy,
            min_cleanliness=min_cleanliness,
            )
        except Exception as exc:
            log_app_exception(
                "app.effective_wpm.failed",
                exc,
                message="Effective WPM suggestion calculation failed.",
                context={
                    "recent_rounds": recent_rounds,
                    "min_accuracy": min_accuracy,
                    "min_cleanliness": min_cleanliness,
                },
            )
            raise

        if not result.get("ok"):
            log_app_event(
                "app.effective_wpm.not_enough_data",
                level="warning",
                message="Effective WPM suggestion could not be calculated because data is insufficient.",
                context={
                    "recent_rounds": recent_rounds,
                    "min_accuracy": min_accuracy,
                    "min_cleanliness": min_cleanliness,
                    "reason": result.get("reason"),
                    "used_rounds": result.get("used_rounds"),
                },
            )
            messagebox.showinfo(
                config.APP_NAME,
                app.i18n.t(
                    "effective_wpm.not_enough_data",
                    "Practice speed could not be estimated yet.\n\n{reason}\n\nSave a few accurate and clean rounds first.",
                    reason=str(result.get("reason", "")),
                ),
            )
            return

        used_rounds = int(result["used_rounds"])
        minimum_required = int(getattr(config, "EFFECTIVE_WPM_MIN_ROUNDS_REQUIRED", 3))

        if used_rounds < minimum_required:
            log_app_event(
                "app.effective_wpm.too_few_rounds",
                level="warning",
                message="Effective WPM suggestion has too few qualified rounds.",
                context={
                    "used_rounds": used_rounds,
                    "minimum_required": minimum_required,
                    "recent_rounds": recent_rounds,
                },
            )
            messagebox.showinfo(
                config.APP_NAME,
                app.i18n.t(
                    "effective_wpm.too_few_rounds",
                    "Not enough data to estimate practice speed.\n\nSuitable rounds found: {used}\nMinimum required: {min_req}",
                    used=used_rounds,
                    min_req=minimum_required,
                ),
            )
            return

        raw_wpm = float(result["wpm"])
        optimized_wpm = self._optimized_target_wpm(raw_wpm)

        previous_wpm = app.target_wpm_var.get()
        app.target_wpm_var.set(optimized_wpm)
        app.history_controller.update_target_wpm_suggestion_indicator()
        app.settings_controller.save_ui_settings()

        app.status_var.set(
            app.i18n.t(
                "effective_wpm.result_message",
                "Proven PARIS median {raw_wpm} WPM. Target WPM set to {optimized_wpm} (+1 WPM).",
                raw_wpm=f"{raw_wpm:.1f}",
                optimized_wpm=optimized_wpm,
            )
        )
        app.settings = app.challenge_settings_controller.settings_from_ui()
        app.timer_var.set(app.practice_controller.reference_time_label())
        log_app_event(
            "app.effective_wpm.applied",
            message="Effective WPM suggestion was applied to target WPM.",
            context={
                "previous_wpm": previous_wpm,
                "raw_wpm": raw_wpm,
                "optimized_wpm": optimized_wpm,
                "used_rounds": used_rounds,
                "recent_rounds": recent_rounds,
                "min_accuracy": min_accuracy,
                "min_cleanliness": min_cleanliness,
            },
        )

        messagebox.showinfo(
            config.APP_NAME,
            app.i18n.t(
                "effective_wpm.detail_dialog",
                "Practice speed estimated from history.\n\n"
                "Rounds used: {used}\n"
                "Recent rounds examined: {recent}\n"
                "Minimum accuracy: {min_acc}%\n"
                "Minimum cleanliness: {min_clean}%\n"
                "Proven PARIS median speed: {raw_wpm} WPM\n"
                "Added challenge margin: +1 WPM\n\n"
                "Set target WPM: {optimized_wpm}",
                used=used_rounds,
                recent=recent_rounds,
                min_acc=min_accuracy,
                min_clean=min_cleanliness,
                raw_wpm=f"{raw_wpm:.1f}",
                optimized_wpm=optimized_wpm,
            ),
        )

    def _optimized_target_wpm(self, raw_wpm: float) -> int:
        """Add a small challenge margin and clamp the result to configured WPM limits."""
        minimum_wpm = int(getattr(config, "EFFECTIVE_WPM_MIN_WPM", 5))
        maximum_wpm = int(getattr(config, "EFFECTIVE_WPM_MAX_WPM", 80))

        return max(
            minimum_wpm,
            min(
                maximum_wpm,
                round(float(raw_wpm) + 1.0),
            ),
        )