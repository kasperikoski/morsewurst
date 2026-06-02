# ============================================================
# morsewurst/ui/koch/views/skill_view.py
# ============================================================

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk

from morsewurst.koch.models import KochSkillSummary


class KochSkillView(ttk.LabelFrame):
    """Koch receive-skill summary panel."""

    def __init__(self, parent: tk.Misc, window: Any) -> None:
        super().__init__(parent, text=window.tr("koch.skill.title", "Koch receive skill"))
        self.window = window
        self.level_var = tk.StringVar(
            value=window.tr("koch.skill.title.no_level", "No copy level yet")
        )
        self.metric_vars: dict[str, tk.StringVar] = {
            "sessions": tk.StringVar(value="0"),
            "accuracy": tk.StringVar(value="0.0 %"),
            "cleanliness": tk.StringVar(value="0.0 %"),
            "avg_wpm": tk.StringVar(value="0.0/0.0"),
            "target_length": tk.StringVar(value="0"),
            "confidence": tk.StringVar(value="0 %"),
        }
        self._progress_items: list[dict[str, Any]] = []
        self._progress_canvases: list[tk.Canvas] = []
        self._build()

    def _build(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=(10, 4))

        ttk.Label(
            top,
            textvariable=self.level_var,
            font=("Segoe UI", 12, "bold"),
        ).pack(side=tk.LEFT)

        self.metrics_frame = ttk.Frame(self)
        self.metrics_frame.pack(fill=tk.X, padx=10, pady=(2, 8))
        self.metrics_frame.columnconfigure(0, weight=1)
        self.metrics_frame.columnconfigure(1, weight=0)

        metric_rows = [
            ("sessions", self.window.tr("koch.skill.metric.sessions", "Sessions")),
            ("accuracy", self.window.tr("koch.skill.metric.accuracy", "Average accuracy")),
            ("cleanliness", self.window.tr("koch.skill.metric.cleanliness", "Average cleanliness")),
            ("avg_wpm", self.window.tr("koch.skill.metric.avg_wpm", "Average WPM")),
            ("target_length", self.window.tr("koch.skill.metric.target_length", "Average length")),
            ("confidence", self.window.tr("koch.skill.metric.confidence", "Confidence")),
        ]

        for row_index, (key, label_text) in enumerate(metric_rows):
            ttk.Label(
                self.metrics_frame,
                text=label_text,
                anchor=tk.W,
            ).grid(row=row_index, column=0, sticky=tk.W, pady=1)
            ttk.Label(
                self.metrics_frame,
                textvariable=self.metric_vars[key],
                anchor=tk.E,
            ).grid(row=row_index, column=1, sticky=tk.E, padx=(12, 0), pady=1)

        self.notice_var = tk.StringVar(value="")
        self.notice_label = tk.Label(
            self.metrics_frame,
            textvariable=self.notice_var,
            anchor=tk.W,
            justify=tk.LEFT,
            fg="#8a5a00",
            wraplength=300,
        )
        self.notice_label.grid(
            row=len(metric_rows),
            column=0,
            columnspan=2,
            sticky=tk.EW,
            pady=(6, 0),
        )

        self.progress_frame = ttk.Frame(self)
        self.progress_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.progress_frame.columnconfigure(0, weight=1)

    def update_summary(
        self,
        summary: KochSkillSummary,
        progress_items: list[dict[str, Any]] | None = None,
    ) -> None:
        displayable = bool(getattr(summary, "displayable", False))
        title = self.window.tr(summary.title_key, summary.title_default)
        if displayable:
            level_value = int(round(float(summary.level or 0.0)))
            self.level_var.set(
                self.window.tr(
                    "koch.skill.level_line",
                    "Level {level} - {title}",
                    level=level_value,
                    title=title,
                )
            )
        else:
            self.level_var.set(title)

        sessions_used = max(0, int(summary.sessions_used or 0))
        total_sessions = max(0, int(getattr(summary, "total_sessions", sessions_used) or 0))
        required_sessions = max(1, int(getattr(summary, "required_sessions", 30) or 30))
        self.metric_vars["sessions"].set(str(total_sessions))
        self.metric_vars["accuracy"].set(f"{float(summary.average_accuracy or 0.0):.1f} %")
        self.metric_vars["cleanliness"].set(f"{float(summary.average_cleanliness or 0.0):.1f} %")
        self.metric_vars["avg_wpm"].set(
            f"{float(getattr(summary, 'average_effective_wpm', 0.0) or 0.0):.1f}/"
            f"{float(getattr(summary, 'average_character_wpm', 0.0) or 0.0):.1f}"
        )
        self.metric_vars["target_length"].set(f"{float(getattr(summary, 'average_target_length', 0.0) or 0.0):.0f}")
        self.metric_vars["confidence"].set(f"{float(summary.confidence or 0.0):.0f} %")

        if displayable:
            self.notice_var.set("")
            self.notice_label.grid_remove()
        else:
            self.notice_var.set(
                self.window.tr(
                    "koch.skill.minimum_sessions_notice",
                    "Showing the skill level requires at least {required} practice sessions.",
                    required=required_sessions,
                )
            )
            self.notice_label.grid()

        self._set_progress_items(progress_items or [])

    def _set_progress_items(self, progress_items: list[dict[str, Any]]) -> None:
        self._progress_items = [dict(item) for item in progress_items]
        self._ensure_progress_canvases(len(self._progress_items))
        self._redraw_progress_bars()

    def _ensure_progress_canvases(self, count: int) -> None:
        while len(self._progress_canvases) < count:
            canvas = tk.Canvas(
                self.progress_frame,
                height=26,
                highlightthickness=0,
                bd=0,
            )
            canvas.grid(
                row=len(self._progress_canvases),
                column=0,
                sticky=tk.EW,
                pady=(4 if self._progress_canvases else 0, 0),
            )
            canvas.bind("<Configure>", lambda _event, c=canvas: self._draw_progress_canvas(c))
            self._progress_canvases.append(canvas)

        for index, canvas in enumerate(self._progress_canvases):
            if index < count:
                canvas.grid()
            else:
                canvas.grid_remove()
                canvas.delete("all")

    def _redraw_progress_bars(self) -> None:
        for canvas in self._progress_canvases[: len(self._progress_items)]:
            self._draw_progress_canvas(canvas)

    def _draw_progress_canvas(self, canvas: tk.Canvas) -> None:
        try:
            index = self._progress_canvases.index(canvas)
        except ValueError:
            return

        if index >= len(self._progress_items):
            canvas.delete("all")
            return

        self._draw_progress_bar(canvas, self._progress_items[index])

    def _draw_progress_bar(self, canvas: tk.Canvas, item: dict[str, Any]) -> None:
        canvas.delete("all")

        width = max(1, int(canvas.winfo_width()))
        height = max(1, int(canvas.winfo_height()))
        border_color = "#b6b6b6"
        background_color = "#f4f4f4"

        current = max(0, int(item.get("current", 0) or 0))
        total = max(1, int(item.get("total", 1) or 1))
        all_unlocked = bool(item.get("all_unlocked", False))
        label = str(item.get("label", "") or "")

        if all_unlocked:
            ratio = 1.0
            fill_color = "#bfe8bf"
            all_unlocked_text = self.window.tr(
                "koch.skill.progress.all_unlocked",
                "kaikki merkit avattu",
            )
            text = f"{label} - {all_unlocked_text}" if label else all_unlocked_text
        else:
            current = min(current, total)
            ratio = max(0.0, min(1.0, current / float(total)))
            fill_color = self._progress_color(ratio)
            text = f"{label} ({current}/{total})" if label else f"{current}/{total}"

        fill_width = int(round(width * ratio))

        canvas.create_rectangle(
            0,
            0,
            width,
            height,
            fill=background_color,
            outline=border_color,
        )

        if fill_width > 0:
            canvas.create_rectangle(
                0,
                0,
                fill_width,
                height,
                fill=fill_color,
                outline="",
            )

        canvas.create_text(
            width // 2,
            height // 2,
            text=text,
            font=("Segoe UI", 9, "bold"),
            fill="#202020",
            anchor=tk.CENTER,
        )

    def _progress_color(self, ratio: float) -> str:
        ratio = max(0.0, min(1.0, float(ratio)))

        if ratio < 0.20:
            return "#f2aaa5"
        if ratio < 0.40:
            return "#f5c07a"
        if ratio < 0.60:
            return "#f3df7a"
        if ratio < 0.80:
            return "#bfe6a8"
        return "#7fd08a"
