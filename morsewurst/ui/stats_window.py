# ============================================================
# morsewurst/ui/stats_window.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk
from typing import Any, Iterable
from collections import defaultdict

import morsewurst.config as config

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
except Exception:
    FigureCanvasTkAgg = None
    Figure = None
    mdates = None


class StatsWindow(tk.Toplevel):
    def __init__(self, app: tk.Misc) -> None:
        super().__init__(app)

        self.app = app
        self.db = app.db

        self.title(self.app.i18n.t("stats_window.title"))
        self.transient(app)
        self.geometry("1180x830")
        self.minsize(980, 710)

        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()
        self.bucket_var = tk.StringVar(value=self.app.i18n.t("stats_window.bucket_auto"))
        self.status_var = tk.StringVar(value="")

        self.current_start_dt: datetime | None = None
        self.current_end_dt: datetime | None = None

        self.summary_vars: dict[str, tk.StringVar] = {
            "rounds": tk.StringVar(value="-"),
            "accuracy": tk.StringVar(value="-"),
            "cleanliness": tk.StringVar(value="-"),
            "score": tk.StringVar(value="-"),
            "gross_wpm": tk.StringVar(value="-"),
            "net_wpm": tk.StringVar(value="-"),
            "device_wpm": tk.StringVar(value="-"),
            "straight_ratio": tk.StringVar(value="-"),
            "dot_variation": tk.StringVar(value="-"),
            "dash_variation": tk.StringVar(value="-"),
            "errors": tk.StringVar(value="-"),
        }

        self._build_ui()
        self._set_quick_range(days=90)
        self.refresh()

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(5000, self._auto_refresh)

        self.update_idletasks()
        self._center_on_parent()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X)

        ttk.Label(
            header,
            text=self.app.i18n.t("stats_window.header"),
            font=("Segoe UI", 16, "bold"),
        ).pack(side=tk.LEFT)

        ttk.Label(
            header,
            textvariable=self.status_var,
            foreground="#666666",
        ).pack(side=tk.RIGHT)

        controls = ttk.LabelFrame(outer, text=self.app.i18n.t("stats_window.period_frame"))
        controls.pack(fill=tk.X, pady=(10, 0))

        row = ttk.Frame(controls)
        row.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(row, text=self.app.i18n.t("stats_window.start_date")).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.start_date_var, width=12).pack(side=tk.LEFT, padx=(6, 14))

        ttk.Label(row, text=self.app.i18n.t("stats_window.end_date")).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.end_date_var, width=12).pack(side=tk.LEFT, padx=(6, 18))

        ttk.Label(row, text=self.app.i18n.t("stats_window.bucket_label")).pack(side=tk.LEFT, padx=(4, 6))

        self.bucket_combo = ttk.Combobox(
            row,
            textvariable=self.bucket_var,
            state="readonly",
            width=14,
            values=[
                self.app.i18n.t("stats_window.bucket_auto"),
                self.app.i18n.t("stats_window.bucket_raw"),
                self.app.i18n.t("stats_window.bucket_15min"),
                self.app.i18n.t("stats_window.bucket_1hour"),
                self.app.i18n.t("stats_window.bucket_day"),
                self.app.i18n.t("stats_window.bucket_week"),
                self.app.i18n.t("stats_window.bucket_month"),
            ],
        )
        self.bucket_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.bucket_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh())

        ttk.Button(row, text=self.app.i18n.t("stats_window.refresh_button"), command=self.refresh).pack(side=tk.LEFT)

        ttk.Button(
            row,
            text=self.app.i18n.t("stats_window.quick_30d"),
            command=lambda: self._set_quick_range_and_refresh(30),
        ).pack(side=tk.LEFT, padx=(12, 0))

        ttk.Button(
            row,
            text=self.app.i18n.t("stats_window.quick_90d"),
            command=lambda: self._set_quick_range_and_refresh(90),
        ).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Button(
            row,
            text=self.app.i18n.t("stats_window.quick_1y"),
            command=lambda: self._set_quick_range_and_refresh(365),
        ).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Button(
            row,
            text=self.app.i18n.t("stats_window.quick_all"),
            command=self._set_all_range_and_refresh,
        ).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(
            controls,
            text=self.app.i18n.t("stats_window.date_format_hint"),
            foreground="#666666",
        ).pack(anchor=tk.W, padx=10, pady=(0, 8))

        summary = ttk.LabelFrame(outer, text=self.app.i18n.t("stats_window.summary_frame"))
        summary.pack(fill=tk.X, pady=(10, 0))

        grid = ttk.Frame(summary)
        grid.pack(fill=tk.X, padx=10, pady=8)

        self._summary_cell(grid, 0, 0, self.app.i18n.t("stats_window.summary_rounds"), self.summary_vars["rounds"])
        self._summary_cell(grid, 0, 1, self.app.i18n.t("stats_window.summary_accuracy"), self.summary_vars["accuracy"])
        self._summary_cell(grid, 0, 2, self.app.i18n.t("stats_window.summary_cleanliness"), self.summary_vars["cleanliness"])
        self._summary_cell(grid, 0, 3, self.app.i18n.t("stats_window.summary_score"), self.summary_vars["score"])

        self._summary_cell(grid, 1, 0, self.app.i18n.t("stats_window.summary_gross_wpm"), self.summary_vars["gross_wpm"])
        self._summary_cell(grid, 1, 1, self.app.i18n.t("stats_window.summary_net_wpm"), self.summary_vars["net_wpm"])
        self._summary_cell(grid, 1, 2, self.app.i18n.t("stats_window.summary_device_wpm"), self.summary_vars["device_wpm"])
        self._summary_cell(grid, 1, 3, self.app.i18n.t("stats_window.summary_errors"), self.summary_vars["errors"])

        self._summary_cell(grid, 2, 0, self.app.i18n.t("stats_window.summary_straight_ratio"), self.summary_vars["straight_ratio"])
        self._summary_cell(grid, 2, 1, self.app.i18n.t("stats_window.summary_dot_variation"), self.summary_vars["dot_variation"])
        self._summary_cell(grid, 2, 2, self.app.i18n.t("stats_window.summary_dash_variation"), self.summary_vars["dash_variation"])

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.wpm_tab = ttk.Frame(self.notebook)
        self.quality_tab = ttk.Frame(self.notebook)
        self.skill_tab = ttk.Frame(self.notebook)
        self.problem_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.wpm_tab, text=self.app.i18n.t("stats_window.tab_wpm"))
        self.notebook.add(self.quality_tab, text=self.app.i18n.t("stats_window.tab_quality"))
        self.notebook.add(self.skill_tab, text=self.app.i18n.t("stats_window.tab_skill"))
        self.notebook.add(self.problem_tab, text=self.app.i18n.t("stats_window.tab_problems"))

        self.figures: dict[str, Any] = {}
        self.axes: dict[str, Any] = {}
        self.canvases: dict[str, Any] = {}

        self._create_plot(self.wpm_tab, "wpm")
        self._create_plot(self.quality_tab, "quality")
        self._create_plot(self.skill_tab, "skill")
        self._create_plot(self.problem_tab, "problems")

    def _summary_cell(
        self,
        parent: ttk.Frame,
        row: int,
        column: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        cell = ttk.Frame(parent)
        cell.grid(row=row, column=column, sticky=tk.W, padx=(0, 36), pady=(0, 8))

        ttk.Label(
            cell,
            text=label,
            foreground="#666666",
            font=("Segoe UI", 8),
        ).pack(anchor=tk.W)

        ttk.Label(
            cell,
            textvariable=variable,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor=tk.W)

    def _create_plot(self, parent: ttk.Frame, key: str) -> None:
        if Figure is None or FigureCanvasTkAgg is None:
            ttk.Label(
                parent,
                text=self.app.i18n.t("stats_window.matplotlib_missing"),
                font=("Segoe UI", 12),
                justify=tk.LEFT,
            ).pack(anchor=tk.W, padx=12, pady=12)
            return

        figure = Figure(figsize=(9, 5), dpi=100)
        axis = figure.add_subplot(111)

        canvas = FigureCanvasTkAgg(figure, master=parent)
        widget = canvas.get_tk_widget()
        widget.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.figures[key] = figure
        self.axes[key] = axis
        self.canvases[key] = canvas

    def _set_quick_range(self, days: int) -> None:
        end = datetime.now()
        start = end - timedelta(days=days)

        self.start_date_var.set(start.strftime("%d.%m.%Y"))
        self.end_date_var.set(end.strftime("%d.%m.%Y"))

    def _set_quick_range_and_refresh(self, days: int) -> None:
        self._set_quick_range(days)
        self.refresh()

    def _set_all_range_and_refresh(self) -> None:
        try:
            bounds = self.db.stats_date_bounds()
        except Exception:
            bounds = None

        if not bounds or not bounds.get("first_finished_at"):
            self._set_quick_range(365)
            self.refresh()
            return

        try:
            start = datetime.fromisoformat(str(bounds["first_finished_at"]))
            end = datetime.fromisoformat(str(bounds["last_finished_at"]))
        except Exception:
            self._set_quick_range(365)
            self.refresh()
            return

        self.start_date_var.set(start.strftime("%d.%m.%Y"))
        self.end_date_var.set(end.strftime("%d.%m.%Y"))
        self.refresh()

    def _parse_date_range(self) -> tuple[str, str] | None:
        start_text = self.start_date_var.get().strip()
        end_text = self.end_date_var.get().strip()

        try:
            start = datetime.strptime(start_text, "%d.%m.%Y")
            end = datetime.strptime(end_text, "%d.%m.%Y")
        except ValueError:
            messagebox.showerror(
                config.APP_NAME,
                self.app.i18n.t("stats_window.error_invalid_date_range"),
                parent=self,
            )
            return None

        end = end.replace(hour=23, minute=59, second=59)

        if end < start:
            messagebox.showerror(
                config.APP_NAME,
                self.app.i18n.t("stats_window.error_end_before_start"),
                parent=self,
            )
            return None

        self.current_start_dt = start
        self.current_end_dt = end

        return start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")

    def refresh(self) -> None:
        parsed = self._parse_date_range()

        if parsed is None:
            return

        start_iso, end_iso = parsed

        try:
            sessions = self.db.stats_sessions_between(start_iso, end_iso)
            summary = self.db.stats_summary_between(start_iso, end_iso)
            key_sources = self.db.stats_key_source_wpm_between(start_iso, end_iso)
            skill_snapshots = self.db.stats_skill_snapshots_between(start_iso, end_iso)
            problems = self.db.stats_problem_characters_between(start_iso, end_iso, 100)
        except Exception as exc:
            self.status_var.set(self.app.i18n.t("stats_window.error_loading", error=exc))
            return

        self._update_summary(summary)
        self._draw_wpm_chart(sessions, key_sources)
        self._draw_quality_chart(sessions)
        self._draw_skill_chart(skill_snapshots)
        self._draw_problem_chart(problems)

        self.status_var.set(
            self.app.i18n.t("stats_window.refreshed_status", time=datetime.now().strftime("%H:%M:%S"), bucket=self._current_bucket_label())
        )

    def _update_summary(self, summary: dict[str, Any]) -> None:
        rounds = int(summary.get("rounds") or 0)
        results = self.app.results_controller

        self.summary_vars["rounds"].set(str(rounds))
        self.summary_vars["accuracy"].set(results.fmt_percent(summary.get("avg_accuracy")))
        self.summary_vars["cleanliness"].set(results.fmt_percent(summary.get("avg_cleanliness")))
        self.summary_vars["score"].set(results.fmt_number(summary.get("avg_overall_score")))
        self.summary_vars["gross_wpm"].set(results.fmt_number(summary.get("avg_gross_wpm")))
        self.summary_vars["net_wpm"].set(results.fmt_number(summary.get("avg_net_wpm")))
        self.summary_vars["device_wpm"].set(results.fmt_number(summary.get("avg_device_wpm")))

        errors = summary.get("total_errors")
        self.summary_vars["errors"].set("-" if errors is None else str(int(errors or 0)))

        self.summary_vars["straight_ratio"].set(
            results.fmt_straight_ratio(summary.get("avg_straight_dash_dot_ratio"))
        )
        self.summary_vars["dot_variation"].set(
            results.fmt_variation_percent(
                summary.get("avg_straight_dot_variation_percent")
            )
        )
        self.summary_vars["dash_variation"].set(
            results.fmt_variation_percent(
                summary.get("avg_straight_dash_variation_percent")
            )
        )

    def _row_get(self, row: Any, key: str, default: Any = None) -> Any:
        return self.app.history_controller.row_get(row, key, default)

    def _date_value(self, row: Any, key: str = "finished_at") -> datetime | None:
        value = self._row_get(row, key)

        if not value:
            return None

        try:
            return datetime.fromisoformat(str(value))
        except Exception:
            return None

    def _series(
        self,
        rows: Iterable[Any],
        value_key: str,
        date_key: str = "finished_at",
    ) -> tuple[list[datetime], list[float]]:
        points: list[tuple[datetime, float]] = []

        for row in rows:
            dt = self._date_value(row, date_key)
            value = self._row_get(row, value_key)

            if dt is None or value is None:
                continue

            try:
                points.append((dt, float(value)))
            except Exception:
                continue

        points.sort(key=lambda item: item[0])

        return [item[0] for item in points], [item[1] for item in points]

    def _selected_bucket(self) -> str:
        value = self.bucket_var.get().strip()
        if value:
            return value
        return self.app.i18n.t("stats_window.bucket_auto")

    def _auto_bucket(self) -> str:
        if self.current_start_dt is None or self.current_end_dt is None:
            return self.app.i18n.t("stats_window.bucket_raw")

        days = max(0.0, (self.current_end_dt - self.current_start_dt).total_seconds() / 86400.0)

        if days <= 2:
            return self.app.i18n.t("stats_window.bucket_raw")
        if days <= 14:
            return self.app.i18n.t("stats_window.bucket_1hour")
        if days <= 120:
            return self.app.i18n.t("stats_window.bucket_day")
        return self.app.i18n.t("stats_window.bucket_week")

    def _bucket_start(self, dt: datetime, bucket: str) -> datetime:
        if bucket == self.app.i18n.t("stats_window.bucket_15min"):
            minute = (dt.minute // 15) * 15
            return dt.replace(minute=minute, second=0, microsecond=0)
        if bucket == self.app.i18n.t("stats_window.bucket_1hour"):
            return dt.replace(minute=0, second=0, microsecond=0)
        if bucket == self.app.i18n.t("stats_window.bucket_day"):
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if bucket == self.app.i18n.t("stats_window.bucket_week"):
            day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            return day_start - timedelta(days=day_start.weekday())
        if bucket == self.app.i18n.t("stats_window.bucket_month"):
            return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return dt

    def _bucketed_series(
        self,
        rows: Iterable[Any],
        value_key: str,
        date_key: str = "finished_at",
    ) -> tuple[list[datetime], list[float]]:
        bucket = self._selected_bucket()

        if bucket == self.app.i18n.t("stats_window.bucket_auto"):
            bucket = self._auto_bucket()

        if bucket == self.app.i18n.t("stats_window.bucket_raw"):
            return self._series(rows, value_key, date_key)

        grouped: dict[datetime, list[float]] = defaultdict(list)

        for row in rows:
            dt = self._date_value(row, date_key)
            value = self._row_get(row, value_key)

            if dt is None or value is None:
                continue

            try:
                numeric_value = float(value)
            except Exception:
                continue

            grouped[self._bucket_start(dt, bucket)].append(numeric_value)

        points: list[tuple[datetime, float]] = []

        for bucket_dt, values in grouped.items():
            if not values:
                continue

            points.append((bucket_dt, sum(values) / len(values)))

        points.sort(key=lambda item: item[0])

        return [item[0] for item in points], [item[1] for item in points]

    def _apply_x_limits(self, axis: Any) -> None:
        if self.current_start_dt is None or self.current_end_dt is None:
            return
        axis.set_xlim(self.current_start_dt, self.current_end_dt)

    def _apply_dynamic_y_limits(
        self,
        axis: Any,
        values: Iterable[float],
        *,
        lower_floor: float = 0.0,
        upper_ceiling: float | None = None,
        margin_ratio: float = 0.12,
        min_margin: float = 1.0,
    ) -> None:
        numeric_values: list[float] = []

        for value in values:
            try:
                numeric_values.append(float(value))
            except Exception:
                continue

        if not numeric_values:
            return

        min_y = min(numeric_values)
        max_y = max(numeric_values)

        if min_y == max_y:
            margin = max(min_margin, abs(min_y) * margin_ratio)
        else:
            margin = max(min_margin, (max_y - min_y) * margin_ratio)

        lower = min_y - margin
        upper = max_y + margin

        if lower_floor is not None:
            lower = max(lower_floor, lower)

        if upper_ceiling is not None:
            upper = min(upper_ceiling, upper)

        if upper <= lower:
            upper = lower + max(1.0, min_margin)

        axis.set_ylim(lower, upper)

    def _current_bucket_label(self) -> str:
        bucket = self._selected_bucket()
        if bucket == self.app.i18n.t("stats_window.bucket_auto"):
            return self.app.i18n.t("stats_window.bucket_auto_active", active=self._auto_bucket())
        return bucket

    def _empty_axis(self, key: str, title: str, message: str) -> None:
        axis = self.axes.get(key)
        canvas = self.canvases.get(key)

        if axis is None or canvas is None:
            return

        axis.clear()
        axis.set_title(title)
        axis.text(
            0.5,
            0.5,
            message,
            ha="center",
            va="center",
            transform=axis.transAxes,
        )
        axis.grid(True, alpha=0.3)
        self._apply_x_limits(axis)
        self._format_time_axis(axis)
        canvas.draw_idle()

    def _format_time_axis(self, axis: Any) -> None:
        if mdates is None:
            return
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
        axis.figure.autofmt_xdate()

    def _draw_wpm_chart(self, sessions: list[Any], key_sources: list[dict[str, Any]]) -> None:
        axis = self.axes.get("wpm")
        canvas = self.canvases.get("wpm")

        if axis is None or canvas is None:
            return

        axis.clear()
        axis.set_title(self.app.i18n.t("stats_window.chart_wpm_title"))
        axis.set_xlabel(self.app.i18n.t("stats_window.chart_xlabel_time"))
        axis.set_ylabel("WPM")

        has_data = False

        for value_key, label in [
            ("gross_wpm", self.app.i18n.t("stats_window.series_gross_wpm")),
            ("net_wpm", self.app.i18n.t("stats_window.series_net_wpm")),
            ("avg_wpm", self.app.i18n.t("stats_window.series_device_wpm")),
        ]:
            x, y = self._bucketed_series(sessions, value_key)
            if x and y:
                axis.step(x, y, where="post", label=label)
                has_data = True

        for source_name, label in [
            ("straight", self.app.i18n.t("stats_window.series_straight_wpm")),
            ("iambic", self.app.i18n.t("stats_window.series_iambic_wpm")),
        ]:
            source_rows = [
                row for row in key_sources
                if str(row.get("key_source", "")).lower() == source_name
            ]
            x, y = self._bucketed_series(source_rows, "wpm")
            if x and y:
                axis.step(x, y, where="post", label=label)
                has_data = True

        if not has_data:
            self._empty_axis(
                "wpm",
                self.app.i18n.t("stats_window.chart_wpm_title"),
                self.app.i18n.t("stats_window.empty_wpm_data"),
            )
            return

        axis.grid(True, alpha=0.3)
        axis.legend(loc="best")
        self._format_time_axis(axis)
        self._apply_x_limits(axis)
        canvas.draw_idle()

    def _draw_quality_chart(self, sessions: list[Any]) -> None:
        axis = self.axes.get("quality")
        canvas = self.canvases.get("quality")

        if axis is None or canvas is None:
            return

        axis.clear()
        axis.set_title(self.app.i18n.t("stats_window.chart_quality_title"))
        axis.set_xlabel(self.app.i18n.t("stats_window.chart_xlabel_time"))
        axis.set_ylabel(self.app.i18n.t("stats_window.chart_ylabel_percent"))

        has_data = False
        all_values: list[float] = []

        for value_key, label in [
            ("accuracy", self.app.i18n.t("stats_window.series_accuracy")),
            ("cleanliness", self.app.i18n.t("stats_window.series_cleanliness")),
            ("overall_score", self.app.i18n.t("stats_window.series_score")),
            ("speed_score", self.app.i18n.t("stats_window.series_speed_score")),
        ]:
            x, y = self._bucketed_series(sessions, value_key)
            if x and y:
                axis.step(x, y, where="post", label=label)
                all_values.extend(y)
                has_data = True

        if not has_data:
            self._empty_axis(
                "quality",
                self.app.i18n.t("stats_window.chart_quality_title"),
                self.app.i18n.t("stats_window.empty_quality_data"),
            )
            return

        self._apply_dynamic_y_limits(
            axis,
            all_values,
            lower_floor=0.0,
            upper_ceiling=105.0,
            margin_ratio=0.12,
            min_margin=2.0,
        )

        axis.grid(True, alpha=0.3)
        axis.legend(loc="best")
        self._format_time_axis(axis)
        self._apply_x_limits(axis)
        canvas.draw_idle()
    def _draw_skill_chart(self, snapshots: list[Any]) -> None:
        axis = self.axes.get("skill")
        canvas = self.canvases.get("skill")

        if axis is None or canvas is None:
            return

        axis.clear()
        axis.set_title(self.app.i18n.t("stats_window.chart_skill_title"))
        axis.set_xlabel(self.app.i18n.t("stats_window.chart_xlabel_time"))
        axis.set_ylabel(self.app.i18n.t("stats_window.chart_ylabel_skill"))

        rated_snapshots = [
            row for row in snapshots
            if self._row_get(row, "raw_skill") is not None
        ]

        has_data = False
        all_values: list[float] = []

        for value_key, label, date_key in [
            ("raw_skill", self.app.i18n.t("stats_window.series_raw_skill"), "created_at"),
            ("effective_wpm", self.app.i18n.t("stats_window.series_effective_wpm"), "created_at"),
            ("level", self.app.i18n.t("stats_window.series_level"), "created_at"),
        ]:
            x, y = self._bucketed_series(rated_snapshots, value_key, date_key)
            if x and y:
                axis.step(x, y, where="post", label=label)
                all_values.extend(y)
                has_data = True

        if not has_data:
            self._empty_axis(
                "skill",
                self.app.i18n.t("stats_window.chart_skill_title"),
                self.app.i18n.t("stats_window.empty_skill_data"),
            )
            return

        if all_values:
            min_y = min(all_values)
            max_y = max(all_values)
            if min_y == max_y:
                margin = max(1.0, abs(min_y) * 0.10)
            else:
                margin = max(1.0, (max_y - min_y) * 0.12)
            axis.set_ylim(
                max(0.0, min_y - margin),
                max_y + margin,
            )

        axis.grid(True, alpha=0.3)
        axis.legend(loc="best")
        self._format_time_axis(axis)
        self._apply_x_limits(axis)
        canvas.draw_idle()

    def _draw_problem_chart(self, problems: list[Any]) -> None:
        axis = self.axes.get("problems")
        canvas = self.canvases.get("problems")

        if axis is None or canvas is None:
            return

        axis.clear()
        axis.set_title(self.app.i18n.t("stats_window.chart_problems_title"))
        axis.set_xlabel(self.app.i18n.t("stats_window.chart_xlabel_char"))
        axis.set_ylabel(self.app.i18n.t("stats_window.chart_ylabel_error_percent"))

        labels: list[str] = []
        values: list[float] = []

        for row in problems:
            char = str(self._row_get(row, "char", "") or "")
            rate = self._row_get(row, "error_rate")
            if not char or rate is None:
                continue
            labels.append(char)
            values.append(float(rate))

        if not labels:
            self._empty_axis(
                "problems",
                self.app.i18n.t("stats_window.chart_problems_title"),
                self.app.i18n.t("stats_window.empty_problems_data"),
            )
            return

        axis.bar(labels, values)
        axis.set_ylim(0, 100)
        axis.grid(True, axis="y", alpha=0.3)
        canvas.draw_idle()

    def _auto_refresh(self) -> None:
        if not self.winfo_exists():
            return
        try:
            self.refresh()
        except Exception:
            pass
        self.after(5000, self._auto_refresh)

    def _center_on_parent(self) -> None:
        parent = self.app
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")

    def _close(self) -> None:
        try:
            if getattr(self.app, "stats_window", None) is self:
                self.app.stats_window = None
        except Exception:
            pass
        self.destroy()