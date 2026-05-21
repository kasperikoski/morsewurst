# ============================================================
# morsewurst/ui/controllers/results_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Tuple

import morsewurst.config as config

SOURCE_ADAPTIVE_TELEMETRY = "adaptive_telemetry"
SOURCE_HID = "hid"

if TYPE_CHECKING:
    from morsewurst.models import ScoreSummary
    from morsewurst.ui.app import MorsewurstApp


class ResultsController:
    """Owns result formatting and result panel value updates."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def fmt_percent(self, value: Any, digits: int = 1) -> str:
        """Format a numeric value as a percentage label."""
        try:
            return "-" if value is None else f"{float(value):.{digits}f} %"
        except Exception:
            return "-"

    def fmt_number(self, value: Any, digits: int = 1) -> str:
        """Format a numeric value with a fixed number of decimals."""
        try:
            return "-" if value is None else f"{float(value):.{digits}f}"
        except Exception:
            return "-"

    def fmt_seconds_from_us(self, value: Any, digits: int = 1) -> str:
        """Format microseconds as seconds."""
        try:
            return "-" if value is None else f"{float(value) / 1_000_000.0:.{digits}f} s"
        except Exception:
            return "-"

    def format_seconds_label(self, elapsed_us: Any) -> str:
        """Return the standard seconds label used in result and timer views."""
        return self.fmt_seconds_from_us(elapsed_us, digits=1)

    def practice_total_elapsed_us(self) -> Optional[int]:
        """Return total elapsed time for the current practice series."""
        app = self.app
        values = [
            int(summary.elapsed_us)
            for summary in app.practice_summaries
            if summary.elapsed_us is not None
        ]
        return sum(values) if values else None

    def practice_total_standard_us(self) -> Optional[int]:
        """Return total reference time for the current practice series."""
        app = self.app
        values = [
            int(summary.standard_time_us)
            for summary in app.practice_summaries
            if summary.standard_time_us is not None
        ]
        return sum(values) if values else None

    def set_practice_total_time_label(self) -> None:
        """Update the timer label with the finished practice series total time."""
        app = self.app
        elapsed_us = self.practice_total_elapsed_us()
        standard_us = self.practice_total_standard_us()

        if elapsed_us is None:
            app.timer_var.set("Kokonaisaika: -")
            return

        elapsed_text = self.format_seconds_label(elapsed_us)

        if standard_us is None:
            app.timer_var.set(f"Kokonaisaika: {elapsed_text}")
            return

        app.timer_var.set(
            f"Kokonaisaika: {elapsed_text} | Vertailuaika {self.format_seconds_label(standard_us)}"
        )

    def straight_ratio_quality_percent(self, ratio: Any) -> Optional[float]:
        """Convert a dash-dot ratio into a quality percentage."""
        try:
            value = float(ratio)
        except Exception:
            return None

        if value <= 0:
            return None

        target = float(getattr(config, "STRAIGHT_RATIO_TARGET", 3.0))
        zero_at = float(getattr(config, "STRAIGHT_RATIO_ERROR_AT_ZERO", 1.50))

        if target <= 0 or zero_at <= 0:
            return None

        return max(0.0, min(100.0, 100.0 * (1.0 - (abs(value - target) / zero_at))))

    def fmt_straight_ratio(self, ratio: Any) -> str:
        """Format dash-dot ratio as quality percent plus raw ratio."""
        quality = self.straight_ratio_quality_percent(ratio)

        if quality is None:
            return "-"

        try:
            return f"{quality:.0f} % ({float(ratio):.2f})"
        except Exception:
            return "-"

    def variation_percent(self, average: Any, stdev: Any) -> Optional[float]:
        """Calculate coefficient of variation as a percentage."""
        try:
            avg = float(average)
            sd = float(stdev)
        except Exception:
            return None

        if avg <= 0:
            return None

        return max(0.0, (sd / avg) * 100.0)

    def fmt_variation_percent(self, value: Any) -> str:
        """Format variation percentage with a capped over-100 display."""
        try:
            numeric = float(value)
        except Exception:
            return "-"

        return "100 %+" if numeric > 100.0 else f"{numeric:.0f} %"

    def summary_dot_variation(self, summary: "ScoreSummary") -> Optional[float]:
        """Return dot duration variation for one round summary."""
        return self.variation_percent(summary.straight_dot_us, summary.straight_dot_sd_us)

    def summary_dash_variation(self, summary: "ScoreSummary") -> Optional[float]:
        """Return dash duration variation for one round summary."""
        return self.variation_percent(summary.straight_dash_us, summary.straight_dash_sd_us)

    def reset_latest_result_values(self) -> None:
        """Reset the latest round result panel values."""
        app = self.app

        app.result_latest_title_var.set("Viimeisin kierros")
        app.result_latest_accuracy_var.set("-")
        app.result_latest_cleanliness_var.set("-")
        app.result_latest_score_var.set("-")
        app.result_latest_timing_var.set("-")
        app.result_latest_errors_var.set("-")
        app.result_latest_substitutions_var.set("-")
        app.result_latest_insertions_var.set("-")
        app.result_latest_deletions_var.set("-")
        app.result_latest_extra_missing_var.set("-")
        app.result_latest_straight_ratio_var.set("-")
        app.result_latest_dot_variation_var.set("-")
        app.result_latest_dash_variation_var.set("-")

    def reset_latest_result_values_when_round_starts(self) -> None:
        """Reset latest result values once when a new round starts."""
        app = self.app

        if app.latest_result_reset_for_current_round:
            return

        self.reset_latest_result_values()
        app.latest_result_reset_for_current_round = True

    def update_latest_result_values(self, summary: "ScoreSummary") -> None:
        """Update the latest round result panel from a score summary."""
        app = self.app

        if summary.finish_reason != "kesken" and summary.elapsed_us is not None:
            title = f"Viimeisin kierros ({self.format_seconds_label(summary.elapsed_us)})"
        else:
            title = "Viimeisin kierros"

        app.result_latest_title_var.set(title)
        app.result_latest_accuracy_var.set(
            f"{summary.accuracy:.1f} % ({summary.correct_count}/{summary.length_target})"
        )
        app.result_latest_cleanliness_var.set(self.fmt_percent(summary.cleanliness))
        app.result_latest_score_var.set(self.fmt_number(summary.overall_score))
        app.result_latest_timing_var.set(self.fmt_percent(summary.timing_score))
        app.result_latest_errors_var.set(str(summary.error_count))
        app.result_latest_substitutions_var.set(str(summary.substitutions))
        app.result_latest_insertions_var.set(str(summary.insertions))
        app.result_latest_deletions_var.set(str(summary.deletions))
        app.result_latest_extra_missing_var.set(f"{summary.insertions}/{summary.deletions}")
        app.result_latest_straight_ratio_var.set(
            self.fmt_straight_ratio(summary.straight_dash_dot_ratio)
        )
        app.result_latest_dot_variation_var.set(
            self.fmt_variation_percent(self.summary_dot_variation(summary))
        )
        app.result_latest_dash_variation_var.set(
            self.fmt_variation_percent(self.summary_dash_variation(summary))
        )

    def update_practice_series_summary(self) -> None:
        """Update the current practice series result panel values."""
        app = self.app
        summaries = list(app.practice_summaries)

        if not summaries:
            self.reset_practice_series_summary()
            return

        total_correct = sum(int(summary.correct_count or 0) for summary in summaries)
        total_target = sum(int(summary.length_target or 0) for summary in summaries)
        accuracy = (
            max(0.0, min(100.0, (total_correct / total_target) * 100.0))
            if total_target > 0
            else 0.0
        )

        app.result_practice_rounds_var.set(f"{len(summaries)}/{app.total_rounds}")
        app.result_practice_accuracy_var.set(f"{accuracy:.1f} %")
        app.result_practice_cleanliness_var.set(
            f"{self.average_summary_value(summaries, 'cleanliness', fallback=0.0):.1f} %"
        )
        app.result_practice_score_var.set(
            self.summary_average_text(summaries, "overall_score")
        )
        app.result_practice_timing_var.set(
            self.fmt_percent(self.average_summary_value(summaries, "timing_score"))
        )
        app.result_practice_gross_wpm_var.set(
            self.summary_average_text(summaries, "gross_wpm")
        )
        app.result_practice_net_wpm_var.set(
            self.summary_average_text(summaries, "net_wpm")
        )
        app.result_practice_device_wpm_var.set(
            self.summary_average_text(summaries, "avg_wpm")
        )
        app.result_practice_straight_ratio_var.set(
            self.fmt_straight_ratio(
                self.average_summary_value(summaries, "straight_dash_dot_ratio")
            )
        )

        dot_variation = self.average_values(
            [self.summary_dot_variation(summary) for summary in summaries]
        )
        dash_variation = self.average_values(
            [self.summary_dash_variation(summary) for summary in summaries]
        )

        app.result_practice_dot_variation_var.set(
            self.fmt_variation_percent(dot_variation)
        )
        app.result_practice_dash_variation_var.set(
            self.fmt_variation_percent(dash_variation)
        )
        app.result_practice_element_variation_var.set(
            f"{self.fmt_variation_percent(dot_variation)} / {self.fmt_variation_percent(dash_variation)}"
        )

    def reset_practice_series_summary(self) -> None:
        """Reset the practice series summary panel values."""
        app = self.app

        app.result_practice_rounds_var.set(
            f"0/{app.total_rounds}" if app.practice_running else "-"
        )
        app.result_practice_accuracy_var.set("-")
        app.result_practice_cleanliness_var.set("-")
        app.result_practice_score_var.set("-")
        app.result_practice_timing_var.set("-")
        app.result_practice_gross_wpm_var.set("-")
        app.result_practice_net_wpm_var.set("-")
        app.result_practice_device_wpm_var.set("-")
        app.result_practice_straight_ratio_var.set("-")
        app.result_practice_dot_variation_var.set("-")
        app.result_practice_dash_variation_var.set("-")
        app.result_practice_element_variation_var.set("-")

    def average_values(
        self,
        values: list[Any],
        fallback: Optional[float] = None,
    ) -> Optional[float]:
        """Average numeric values while ignoring missing and invalid values."""
        numeric_values: list[float] = []

        for value in values:
            if value is None:
                continue

            try:
                numeric_values.append(float(value))
            except Exception:
                pass

        return sum(numeric_values) / len(numeric_values) if numeric_values else fallback

    def average_summary_value(
        self,
        summaries: list["ScoreSummary"],
        attribute: str,
        fallback: Optional[float] = None,
    ) -> Optional[float]:
        """Average one numeric attribute from a list of score summaries."""
        return self.average_values(
            [getattr(summary, attribute, None) for summary in summaries],
            fallback=fallback,
        )

    def summary_average_text(self, summaries: list["ScoreSummary"], attribute: str) -> str:
        """Format an averaged score summary attribute for display."""
        value = self.average_summary_value(summaries, attribute)
        return "-" if value is None else f"{value:.1f}"

    def selected_source_text(self) -> Tuple[str, str]:
        """Return the current source text and its stable source identifier for scoring."""
        app = self.app

        if app.use_telemetry_as_truth_var.get():
            return app.round.telemetry_text, SOURCE_ADAPTIVE_TELEMETRY

        return app.input_var.get(), SOURCE_HID