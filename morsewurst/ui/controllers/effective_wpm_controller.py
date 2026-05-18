# ============================================================
# morsewurst/ui/controllers/effective_wpm_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

from tkinter import messagebox

import morsewurst.config as config

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

        result = app.db.optimized_wpm_from_recent_sessions(
            recent_sessions=recent_rounds,
            min_accuracy=min_accuracy,
            min_cleanliness=min_cleanliness,
        )

        if not result.get("ok"):
            messagebox.showinfo(
                config.APP_NAME,
                "Harjoitusnopeutta ei voitu vielä arvioida.\n\n"
                f"{result.get('reason', '')}\n\n"
                "Tallenna ensin muutama riittävän tarkka ja puhdas kierros.",
            )
            return

        used_rounds = int(result["used_rounds"])
        minimum_required = int(getattr(config, "EFFECTIVE_WPM_MIN_ROUNDS_REQUIRED", 3))

        if used_rounds < minimum_required:
            messagebox.showinfo(
                config.APP_NAME,
                "Harjoitusnopeuden arviointiin on vielä liian vähän dataa.\n\n"
                f"Sopivia kierroksia löytyi: {used_rounds}\n"
                f"Tarvitaan vähintään: {minimum_required}",
            )
            return

        raw_wpm = float(result["wpm"])
        optimized_wpm = self._optimized_target_wpm(raw_wpm)

        app.target_wpm_var.set(optimized_wpm)
        app.history_controller.update_target_wpm_suggestion_indicator()
        app.settings_controller.save_ui_settings()

        app.status_var.set(
            f"Todistettu PARIS-mediaani {raw_wpm:.1f} WPM. "
            f"Tavoite-WPM asetettu arvoon {optimized_wpm} (+1 WPM)."
        )
        app.settings = app.challenge_settings_controller.settings_from_ui()
        app.timer_var.set(app.practice_controller.reference_time_label())

        messagebox.showinfo(
            config.APP_NAME,
            "Harjoitusnopeus arvioitu historian perusteella.\n\n"
            f"Käytettyjä kierroksia: {used_rounds}\n"
            f"Viimeisiä kierroksia tarkasteltu: {recent_rounds}\n"
            f"Minimitarkkuus: {min_accuracy} %\n"
            f"Minimipuhtaus: {min_cleanliness} %\n"
            f"Todistettu PARIS-mediaaninopeus: {raw_wpm:.1f} WPM\n"
            "Harjoitukseen lisätty nousuvara: +1 WPM\n\n"
            f"Asetettu tavoite-WPM: {optimized_wpm}",
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