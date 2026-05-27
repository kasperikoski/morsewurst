# ============================================================
# morsewurst/ui/panels/settings_panel.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import morsewurst.config as config


class CharacterMixBar:
    """Small canvas widget for editing the generated character group mix."""

    GROUP_ORDER = ("letters", "numbers", "punctuation")

    def __init__(self, app: tk.Misc, parent: ttk.Frame, *, width: int = 300) -> None:
        self.app = app
        self.width = width
        self.height = 48
        self.bar_left = 2
        self.bar_right = width - 2
        self.bar_top = 6
        self.bar_bottom = 30
        self.handle_radius = 5
        self._drag_boundary_index: int | None = None

        try:
            background = parent.cget("background")
        except tk.TclError:
            background = "#f0f0f0"

        self.canvas = tk.Canvas(
            parent,
            width=self.width,
            height=self.height,
            highlightthickness=0,
            background=background,
        )
        self.canvas.pack(fill=tk.X)

        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        self.refresh()

    def _on_configure(self, event: tk.Event) -> None:
        try:
            self.width = max(160, int(event.width))
            self.bar_right = self.width - 2
        except Exception:
            pass
        self.refresh()

    def _group_info(self) -> dict[str, dict[str, object]]:
        colors = getattr(config, "CHARACTER_MIX_COLORS", {})

        return {
            "letters": {
                "label": self.app.i18n.t("settings_panel.use_letters", "Letters A-Z"),
                "chars": config.LETTERS,
                "enabled_var": self.app.use_letters_var,
                "weight_var": self.app.character_mix_letters_var,
                "color": colors.get("letters", "#f2b8b5"),
            },
            "numbers": {
                "label": self.app.i18n.t("settings_panel.use_numbers", "Numbers 0-9"),
                "chars": config.NUMBERS,
                "enabled_var": self.app.use_numbers_var,
                "weight_var": self.app.character_mix_numbers_var,
                "color": colors.get("numbers", "#f7df8e"),
            },
            "punctuation": {
                "label": self.app.i18n.t("settings_panel.use_punctuation", "Punctuation"),
                "chars": config.PUNCTUATION,
                "enabled_var": self.app.use_punctuation_var,
                "weight_var": self.app.character_mix_punctuation_var,
                "color": colors.get("punctuation", "#a7c7e7"),
            },
        }

    def _active_groups(self) -> list[dict[str, object]]:
        info = self._group_info()
        active: list[dict[str, object]] = []

        for name in self.GROUP_ORDER:
            item = dict(info[name])
            item["name"] = name

            try:
                enabled = bool(item["enabled_var"].get())
            except Exception:
                enabled = False

            if enabled:
                active.append(item)

        if active:
            return active

        # Same safety fallback as the challenge generator: if the user disables
        # all groups, letters and numbers are still used instead of generating
        # an empty target.
        fallback: list[dict[str, object]] = []
        for name in ("letters", "numbers"):
            item = dict(info[name])
            item["name"] = name
            fallback.append(item)
        return fallback

    def _wxmor_enabled(self) -> bool:
        try:
            return bool(self.app.practice_wxmor_var.get())
        except Exception:
            return False

    def _enabled_for_dragging(self) -> bool:
        if self._wxmor_enabled():
            return False

        return len(self._active_groups()) > 1

    def _effective_percentages(self, active: list[dict[str, object]]) -> list[float]:
        if not active:
            return []

        weights: list[float] = []

        for item in active:
            try:
                weight = float(item["weight_var"].get())
            except Exception:
                weight = 0.0
            weights.append(max(0.0, weight))

        total = sum(weights)

        if total <= 0.0:
            return [100.0 / len(active) for _item in active]

        return [(weight / total) * 100.0 for weight in weights]

    def _set_effective_percentages(
        self,
        active: list[dict[str, object]],
        percentages: list[float],
    ) -> None:
        if not active or len(active) != len(percentages):
            return

        if len(percentages) == 1:
            rounded = [100]
        else:
            rounded = [max(1, int(value)) for value in percentages]
            remainder = 100 - sum(rounded)

            if remainder > 0:
                fractional_parts = sorted(
                    (
                        (percentages[index] - int(percentages[index]), index)
                        for index in range(len(percentages))
                    ),
                    reverse=True,
                )
                for _step in range(remainder):
                    _fraction, index = fractional_parts[_step % len(fractional_parts)]
                    rounded[index] += 1

            while sum(rounded) > 100:
                index = max(range(len(rounded)), key=lambda item_index: rounded[item_index])
                if rounded[index] <= 1:
                    break
                rounded[index] -= 1

        for item, value in zip(active, rounded):
            try:
                item["weight_var"].set(value)
            except Exception:
                pass

    def _segment_bounds(
        self,
        percentages: list[float],
    ) -> list[tuple[float, float]]:
        width = max(1.0, float(self.bar_right - self.bar_left))
        bounds: list[tuple[float, float]] = []
        x = float(self.bar_left)

        for index, percent in enumerate(percentages):
            if index == len(percentages) - 1:
                next_x = float(self.bar_right)
            else:
                next_x = x + width * (percent / 100.0)
            bounds.append((x, next_x))
            x = next_x

        return bounds

    def refresh(self) -> None:
        active = self._active_groups()
        percentages = self._effective_percentages(active)
        bounds = self._segment_bounds(percentages)
        disabled = self._wxmor_enabled()

        self.canvas.delete("all")

        if not active:
            return

        for item, percent, (left, right) in zip(active, percentages, bounds):
            color = "#d9d9d9" if disabled else str(item["color"])
            self.canvas.create_rectangle(
                left,
                self.bar_top,
                right,
                self.bar_bottom,
                fill=color,
                outline="#ffffff",
            )

            label = str(item["label"])
            if right - left < 88:
                label = self._short_label(str(item["name"]))

            self.canvas.create_text(
                (left + right) / 2.0,
                (self.bar_top + self.bar_bottom) / 2.0,
                text=f"{label} {percent:.0f} %",
                font=("Segoe UI", 8),
                fill="#222222" if not disabled else "#666666",
            )

        if len(active) > 1 and not disabled:
            for index, (_left, right) in enumerate(bounds[:-1]):
                self.canvas.create_oval(
                    right - self.handle_radius,
                    self.bar_bottom + 3,
                    right + self.handle_radius,
                    self.bar_bottom + 3 + self.handle_radius * 2,
                    fill="#444444",
                    outline="#222222",
                    tags=("handle", f"handle_{index}"),
                )
                self.canvas.create_line(
                    right,
                    self.bar_top,
                    right,
                    self.bar_bottom + 3,
                    fill="#444444",
                    width=2,
                )

    def _short_label(self, name: str) -> str:
        key = {
            "letters": "settings_panel.character_mix.short_letters",
            "numbers": "settings_panel.character_mix.short_numbers",
            "punctuation": "settings_panel.character_mix.short_punctuation",
        }.get(name)

        if key:
            return self.app.i18n.t(key)

        return name

    def _nearest_boundary_index(self, x: float) -> int | None:
        if not self._enabled_for_dragging():
            return None

        active = self._active_groups()
        if len(active) <= 1:
            return None

        percentages = self._effective_percentages(active)
        bounds = self._segment_bounds(percentages)
        boundary_positions = [right for _left, right in bounds[:-1]]

        nearest_index: int | None = None
        nearest_distance = 999999.0

        for index, boundary_x in enumerate(boundary_positions):
            distance = abs(boundary_x - x)
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_index = index

        if nearest_distance <= 14.0:
            return nearest_index

        return None

    def _on_press(self, event: tk.Event) -> None:
        self._drag_boundary_index = self._nearest_boundary_index(float(event.x))

    def _on_drag(self, event: tk.Event) -> None:
        if self._drag_boundary_index is None:
            return

        active = self._active_groups()
        index = self._drag_boundary_index

        if index < 0 or index >= len(active) - 1:
            return

        percentages = self._effective_percentages(active)
        bar_width = max(1.0, float(self.bar_right - self.bar_left))
        x_percent = ((float(event.x) - float(self.bar_left)) / bar_width) * 100.0
        x_percent = max(0.0, min(100.0, x_percent))

        before_pair = sum(percentages[:index])
        pair_total = percentages[index] + percentages[index + 1]

        min_percent = 1.0 if pair_total >= 2.0 else 0.0
        new_left = x_percent - before_pair
        new_left = max(min_percent, min(pair_total - min_percent, new_left))
        new_right = pair_total - new_left

        percentages[index] = new_left
        percentages[index + 1] = new_right

        self._set_effective_percentages(active, percentages)
        self.refresh()

    def _on_release(self, _event: tk.Event) -> None:
        self._drag_boundary_index = None
        self.refresh()


def build_settings_panel(app: tk.Misc, parent: ttk.Frame) -> None:
    settings = ttk.LabelFrame(parent, text=app.i18n.t("settings_panel.title"))
    settings.pack(fill=tk.X)

    if not hasattr(app, "wxmor_disabled_widgets"):
        app.wxmor_disabled_widgets = []

    def refresh_character_mix_bar() -> None:
        if hasattr(app, "character_mix_bar"):
            try:
                app.character_mix_bar.refresh()
            except Exception:
                pass

    # Merkkivalinnat
    options = ttk.Frame(settings)
    options.pack(fill=tk.X, padx=10, pady=(8, 4))

    app.use_letters_check = ttk.Checkbutton(
        options,
        text=app.i18n.t("settings_panel.use_letters"),
        variable=app.use_letters_var,
        command=refresh_character_mix_bar,
    )
    app.use_letters_check.grid(row=0, column=0, sticky=tk.W)

    app.use_numbers_check = ttk.Checkbutton(
        options,
        text=app.i18n.t("settings_panel.use_numbers"),
        variable=app.use_numbers_var,
        command=refresh_character_mix_bar,
    )
    app.use_numbers_check.grid(row=0, column=1, sticky=tk.W, padx=(18, 0))

    app.use_punctuation_check = ttk.Checkbutton(
        options,
        text=app.i18n.t("settings_panel.use_punctuation"),
        variable=app.use_punctuation_var,
        command=refresh_character_mix_bar,
    )
    app.use_punctuation_check.grid(row=0, column=2, sticky=tk.W, padx=(18, 0))

    mix_frame = ttk.Frame(options)
    mix_frame.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=(8, 0))
    mix_frame.columnconfigure(0, weight=1)

    ttk.Label(
        mix_frame,
        text=app.i18n.t("settings_panel.character_mix_title"),
        font=("Segoe UI", 9, "bold"),
    ).pack(anchor=tk.W)

    app.character_mix_bar = CharacterMixBar(app, mix_frame)

    ttk.Label(
        mix_frame,
        text=app.i18n.t("settings_panel.character_mix_hint"),
        foreground="#666666",
        wraplength=300,
        font=("Segoe UI", 8),
    ).pack(anchor=tk.W, pady=(2, 0))

    def update_wxmor_state() -> None:
        app.wxmor_controller.update_practice_state()
        refresh_character_mix_bar()

    app.practice_wxmor_check = ttk.Checkbutton(
        options,
        text=app.i18n.t("settings_panel.practice_wxmor"),
        variable=app.practice_wxmor_var,
        command=update_wxmor_state,
    )
    app.practice_wxmor_check.grid(
        row=2,
        column=0,
        columnspan=3,
        sticky=tk.W,
        pady=(10, 0),
    )

    app.wxmor_profile_label = ttk.Label(
        options,
        text=app.i18n.t("settings_panel.wxmor_profile"),
    )
    app.wxmor_profile_label.grid(
        row=3,
        column=0,
        sticky=tk.W,
        pady=(6, 0),
    )

    app.wxmor_profile_combo = ttk.Combobox(
        options,
        textvariable=app.wxmor_profile_var,
        values=tuple(app.wxmor_controller.profile_labels().values()),
        state=tk.DISABLED,
        width=14,
    )
    app.wxmor_profile_combo.grid(
        row=3,
        column=1,
        sticky=tk.W,
        padx=(18, 0),
        pady=(6, 0),
    )

    app.practice_problem_chars_check = ttk.Checkbutton(
        options,
        text=app.i18n.t("settings_panel.practice_problem_chars"),
        variable=app.practice_problem_chars_var,
    )
    app.practice_problem_chars_check.grid(
        row=4,
        column=0,
        columnspan=3,
        sticky=tk.W,
        pady=(10, 0),
    )

    # Määräasetukset tasattuna
    counts = ttk.Frame(settings)
    counts.pack(fill=tk.X, padx=10, pady=(12, 8))

    counts.columnconfigure(0, minsize=95)
    counts.columnconfigure(1, minsize=55)
    counts.columnconfigure(2, minsize=35)
    counts.columnconfigure(3, minsize=55)

    app.practice_rounds_label = ttk.Label(counts, text=app.i18n.t("settings_panel.rounds"))
    app.practice_rounds_label.grid(row=0, column=0, sticky=tk.W)

    app.practice_rounds_spin = app.ui_helpers_controller.make_int_spinbox(
        counts,
        from_=1,
        to=1000,
        textvariable=app.practice_rounds_var,
        width=6,
    )
    app.practice_rounds_spin.grid(row=0, column=1, sticky=tk.W)

    app.min_groups_label = ttk.Label(counts, text=app.i18n.t("settings_panel.groups_min"))
    app.min_groups_label.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))

    app.min_groups_spin = app.ui_helpers_controller.make_int_spinbox(
        counts,
        from_=1,
        to=100,
        textvariable=app.min_groups_var,
        width=6,
    )
    app.min_groups_spin.grid(row=1, column=1, sticky=tk.W, pady=(8, 0))

    app.max_groups_label = ttk.Label(counts, text=app.i18n.t("settings_panel.groups_max"))
    app.max_groups_label.grid(row=1, column=2, sticky=tk.W, pady=(8, 0))

    app.max_groups_spin = app.ui_helpers_controller.make_int_spinbox(
        counts,
        from_=1,
        to=100,
        textvariable=app.max_groups_var,
        width=6,
    )
    app.max_groups_spin.grid(row=1, column=3, sticky=tk.W, pady=(8, 0))

    app.min_chars_label = ttk.Label(counts, text=app.i18n.t("settings_panel.chars_min"))
    app.min_chars_label.grid(row=2, column=0, sticky=tk.W, pady=(8, 0))

    app.min_chars_spin = app.ui_helpers_controller.make_int_spinbox(
        counts,
        from_=1,
        to=100,
        textvariable=app.min_chars_var,
        width=6,
    )
    app.min_chars_spin.grid(row=2, column=1, sticky=tk.W, pady=(8, 0))

    app.max_chars_label = ttk.Label(counts, text=app.i18n.t("settings_panel.chars_max"))
    app.max_chars_label.grid(row=2, column=2, sticky=tk.W, pady=(8, 0))

    app.max_chars_spin = app.ui_helpers_controller.make_int_spinbox(
        counts,
        from_=1,
        to=100,
        textvariable=app.max_chars_var,
        width=6,
    )
    app.max_chars_spin.grid(row=2, column=3, sticky=tk.W, pady=(8, 0))

    wxmor_disabled_widgets = [
        app.use_letters_check,
        app.use_numbers_check,
        app.use_punctuation_check,
        app.practice_problem_chars_check,
        app.min_groups_label,
        app.min_groups_spin,
        app.max_groups_label,
        app.max_groups_spin,
        app.min_chars_label,
        app.min_chars_spin,
        app.max_chars_label,
        app.max_chars_spin,
    ]

    for widget in wxmor_disabled_widgets:
        if widget not in app.wxmor_disabled_widgets:
            app.wxmor_disabled_widgets.append(widget)

    speed = ttk.LabelFrame(parent, text=app.i18n.t("settings_panel.speed_title"))
    speed.pack(fill=tk.X, pady=(8, 0))

    speed_row = ttk.Frame(speed)
    speed_row.pack(fill=tk.X, padx=10, pady=8)

    ttk.Button(
        speed_row,
        text=app.i18n.t("settings_panel.suggest_speed"),
        command=app.effective_wpm_controller.optimize_timing_from_history,
    ).pack(side=tk.LEFT)

    ttk.Label(
        speed_row,
        text=app.i18n.t("settings_panel.target_wpm"),
    ).pack(side=tk.LEFT, padx=(22, 6))

    ttk.Label(
        speed_row,
        textvariable=app.target_wpm_var,
        font=("Segoe UI", 9, "bold"),
    ).pack(side=tk.LEFT)

    app.target_wpm_delta_label = ttk.Label(
        speed_row,
        textvariable=app.target_wpm_suggestion_delta_var,
        font=("Segoe UI", 9, "bold"),
        foreground="#666666",
    )
    app.target_wpm_delta_label.pack(side=tk.LEFT, padx=(6, 0))

    app.wxmor_controller.update_practice_state()
    refresh_character_mix_bar()
