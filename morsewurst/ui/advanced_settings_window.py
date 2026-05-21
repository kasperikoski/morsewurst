# ============================================================
# morsewurst/ui/advanced_settings_window.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import morsewurst.config as config


class AdvancedSettingsWindow(tk.Toplevel):
    def __init__(self, app: tk.Misc) -> None:
        super().__init__(app)

        self.app = app

        self.title(self.app.i18n.t("settings.window.title"))
        self.transient(app)
        self.grab_set()
        self.geometry("780x680")
        self.minsize(780, 680)

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(outer)
        notebook.pack(fill=tk.BOTH, expand=True)

        self._build_language_tab(notebook)
        self._build_speed_tab(notebook)
        self._build_adaptive_tab(notebook)
        self._build_problem_chars_tab(notebook)
        self._build_sound_tab(notebook)
        self._build_input_tab(notebook)
        self._build_effective_wpm_tab(notebook)
        self._build_skill_tab(notebook)
        self._build_stats_tab(notebook)
        self._build_debug_tab(notebook)

        button_row = ttk.Frame(outer)
        button_row.pack(fill=tk.X, pady=(12, 0))

        ttk.Button(
            button_row,
            text=self.app.i18n.t("settings.button.close"),
            command=self.close,
        ).pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self.close)

        self.update_idletasks()
        self._center_on_parent(app)

    def _open_debug_window_from_settings(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass

        self.app.window_controller.open_debug_window()

    def close(self) -> None:
        try:
            self.app.audio_controller.stop_morse_speed_preview()
        except Exception:
            pass

        try:
            self.app.settings_controller.save_ui_settings()
        except Exception:
            pass

        try:
            self.grab_release()
        except tk.TclError:
            pass

        self.destroy()

        try:
            self.app.after_idle(self.app.history_controller.load_tables)
        except Exception:
            pass

    def _center_on_parent(self, app: tk.Misc) -> None:
        x = app.winfo_rootx() + max(0, (app.winfo_width() - self.winfo_width()) // 2)
        y = app.winfo_rooty() + max(0, (app.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")

    def _make_scrollable_tab(self, notebook: ttk.Notebook, title: str) -> ttk.Frame:
        outer = ttk.Frame(notebook)
        notebook.add(outer, text=title)

        canvas = tk.Canvas(
            outer,
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(
            outer,
            orient=tk.VERTICAL,
            command=canvas.yview,
        )

        content = ttk.Frame(canvas, padding=12)
        window_id = canvas.create_window(
            (0, 0),
            window=content,
            anchor=tk.NW,
        )

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def update_scrollregion(_event: tk.Event | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def update_content_width(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        def on_mousewheel(event: tk.Event) -> None:
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def on_linux_scroll_up(_event: tk.Event) -> None:
            canvas.yview_scroll(-3, "units")

        def on_linux_scroll_down(_event: tk.Event) -> None:
            canvas.yview_scroll(3, "units")

        def bind_mousewheel(_event: tk.Event) -> None:
            canvas.bind_all("<MouseWheel>", on_mousewheel)
            canvas.bind_all("<Button-4>", on_linux_scroll_up)
            canvas.bind_all("<Button-5>", on_linux_scroll_down)

        def unbind_mousewheel(_event: tk.Event) -> None:
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        content.bind("<Configure>", update_scrollregion)
        canvas.bind("<Configure>", update_content_width)

        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)

        return content

    def _build_language_tab(self, notebook: ttk.Notebook) -> None:
        frame = self._make_scrollable_tab(
            notebook,
            self.app.i18n.t("settings.language.tab"),
        )

        ttk.Label(
            frame,
            text=self.app.i18n.t("settings.language.title"),
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=self.app.i18n.t("settings.language.description"),
            wraplength=620,
        ).pack(anchor=tk.W, pady=(4, 12))

        language_options = self.app.i18n.language_options()
        code_to_label = {
            code: label
            for code, label in language_options.items()
        }
        label_to_code = {
            label: code
            for code, label in language_options.items()
        }

        selected_label_var = tk.StringVar(
            value=code_to_label.get(self.app.i18n.language, "English")
        )

        combo = ttk.Combobox(
            frame,
            textvariable=selected_label_var,
            values=tuple(language_options.values()),
            state="readonly",
            width=28,
        )
        combo.pack(anchor=tk.W)

        restart_label = ttk.Label(
            frame,
            text=self.app.i18n.t("settings.language.restart_required"),
            wraplength=620,
        )
        restart_label.pack(anchor=tk.W, pady=(12, 0))

        def on_language_selected(_event: tk.Event | None = None) -> None:
            selected_label = selected_label_var.get()
            language = label_to_code.get(selected_label, "en")

            self.app.language_var.set(language)
            self.app.i18n.set_language(language)

        combo.bind("<<ComboboxSelected>>", on_language_selected)

    def _build_problem_chars_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text=self.app.i18n.t("advanced.tab.problem_chars"))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.problem_chars.title"),
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.problem_chars.description"),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        row_1 = ttk.Frame(frame)
        row_1.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_1,
            text=self.app.i18n.t("advanced.problem_chars.weight_percent"),
            width=28,
        ).pack(side=tk.LEFT)

        self.app.ui_helpers_controller.make_int_spinbox(
            row_1,
            from_=0,
            to=100,
            textvariable=self.app.problem_char_weight_percent_var,
            width=8,
        ).pack(side=tk.LEFT)

        row_2 = ttk.Frame(frame)
        row_2.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_2,
            text=self.app.i18n.t("advanced.problem_chars.limit"),
            width=28,
        ).pack(side=tk.LEFT)

        self.app.ui_helpers_controller.make_int_spinbox(
            row_2,
            from_=1,
            to=100,
            textvariable=self.app.problem_char_limit_var,
            width=8,
        ).pack(side=tk.LEFT)

        row_3 = ttk.Frame(frame)
        row_3.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_3,
            text=self.app.i18n.t("advanced.problem_chars.recent_rounds"),
            width=28,
        ).pack(side=tk.LEFT)

        self.app.ui_helpers_controller.make_int_spinbox(
            row_3,
            from_=1,
            to=100000,
            textvariable=self.app.problem_recent_rounds_var,
            width=8,
        ).pack(side=tk.LEFT)

    def _build_input_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text=self.app.i18n.t("advanced.tab.input"))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.input.title"),
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.input.description"),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        ttk.Checkbutton(
            frame,
            text=self.app.i18n.t("advanced.input.use_telemetry_as_truth"),
            variable=self.app.use_telemetry_as_truth_var,
            command=self.app.input_controller.on_use_telemetry_as_truth_changed,
        ).pack(anchor=tk.W, pady=(0, 2))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.input.use_telemetry_as_truth_hint"),
            wraplength=420,
            foreground="#666666",
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Checkbutton(
            frame,
            text=self.app.i18n.t("advanced.input.keep_focus"),
            variable=self.app.keep_focus_var,
        ).pack(anchor=tk.W, pady=(0, 6))

        ttk.Checkbutton(
            frame,
            text=self.app.i18n.t("advanced.input.auto_connect_serial"),
            variable=self.app.auto_connect_serial_var,
            command=self.app.input_controller.on_auto_connect_serial_changed,
        ).pack(anchor=tk.W, pady=(0, 14))

        ttk.Separator(frame).pack(fill=tk.X, pady=(4, 14))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.input.keyboard_title"),
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.input.keyboard_description"),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 10))

        ttk.Checkbutton(
            frame,
            text=self.app.i18n.t("advanced.input.keyboard_enabled"),
            variable=self.app.keyboard_morse_enabled_var,
            command=self.app.input_controller.on_keyboard_morse_enabled_changed,
        ).pack(anchor=tk.W, pady=(0, 8))

        key_row = ttk.Frame(frame)
        key_row.pack(anchor=tk.W, fill=tk.X, pady=(0, 8))

        ttk.Label(
            key_row,
            text=self.app.i18n.t("advanced.input.keyboard_key_label"),
        ).pack(side=tk.LEFT, padx=(0, 8))

        keyboard_key_combo = ttk.Combobox(
            key_row,
            textvariable=self.app.keyboard_morse_key_label_var,
            values=self.app.input_controller.keyboard_morse_key_labels(),
            state="readonly",
            width=22,
        )
        keyboard_key_combo.pack(side=tk.LEFT)
        keyboard_key_combo.bind("<<ComboboxSelected>>", self.app.input_controller.on_keyboard_morse_key_changed)

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.input.keyboard_note"),
            wraplength=420,
            foreground="#666666",
        ).pack(anchor=tk.W, pady=(0, 14))

        ttk.Separator(frame).pack(fill=tk.X, pady=(4, 14))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.input.auto_finish_title"),
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.input.auto_finish_description"),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 10))

        ttk.Checkbutton(
            frame,
            text=self.app.i18n.t("advanced.input.auto_finish_enabled"),
            variable=self.app.auto_finish_on_idle_var,
        ).pack(anchor=tk.W, pady=(0, 8))

        row_1 = ttk.Frame(frame)
        row_1.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_1,
            text=self.app.i18n.t("advanced.input.idle_units"),
            width=28,
        ).pack(side=tk.LEFT)

        self.app.ui_helpers_controller.make_int_spinbox(
            row_1,
            from_=3,
            to=100,
            textvariable=self.app.auto_finish_idle_units_var,
            width=8,
        ).pack(side=tk.LEFT)

        row_2 = ttk.Frame(frame)
        row_2.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_2,
            text=self.app.i18n.t("advanced.input.min_seconds"),
            width=28,
        ).pack(side=tk.LEFT)

        self.app.ui_helpers_controller.make_int_spinbox(
            row_2,
            from_=1,
            to=30,
            textvariable=self.app.auto_finish_min_seconds_var,
            width=8,
        ).pack(side=tk.LEFT)

    def _adaptive_float_row(
        self,
        parent: ttk.Frame,
        *,
        label: str,
        description: str,
        variable: tk.DoubleVar,
        from_: float,
        to: float,
        increment: float,
    ) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row,
            text=label,
            width=32,
        ).pack(side=tk.LEFT)

        self.app.ui_helpers_controller.make_float_spinbox(
            row,
            from_=from_,
            to=to,
            increment=increment,
            textvariable=variable,
            width=8,
        ).pack(side=tk.LEFT)

        ttk.Label(
            parent,
            text=description,
            wraplength=560,
            foreground="#666666",
        ).pack(anchor=tk.W, pady=(0, 10))

    def _adaptive_int_row(
        self,
        parent: ttk.Frame,
        *,
        label: str,
        description: str,
        variable: tk.IntVar,
        from_: int,
        to: int,
    ) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row,
            text=label,
            width=32,
        ).pack(side=tk.LEFT)

        self.app.ui_helpers_controller.make_int_spinbox(
            row,
            from_=from_,
            to=to,
            textvariable=variable,
            width=8,
        ).pack(side=tk.LEFT)

        ttk.Label(
            parent,
            text=description,
            wraplength=560,
            foreground="#666666",
        ).pack(anchor=tk.W, pady=(0, 10))

    def _build_adaptive_tab(self, notebook: ttk.Notebook) -> None:
        frame = self._make_scrollable_tab(notebook, self.app.i18n.t("advanced.tab.adaptive"))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.adaptive.title"),
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.adaptive.description"),
            wraplength=660,
        ).pack(anchor=tk.W, pady=(4, 12))

        profile_box = ttk.LabelFrame(frame, text=self.app.i18n.t("advanced.adaptive.profile_box"))
        profile_box.pack(fill=tk.X, pady=(0, 12))

        self.profile_summary_vars: dict[str, dict[str, tk.StringVar]] = {}
        self.profile_progress_bars: dict[str, tk.Canvas] = {}

        def add_profile_row(row: int, title: str, source: str) -> None:
            self.profile_summary_vars[source] = {
                "element": tk.StringVar(value=f"{self.app.i18n.t('advanced.adaptive.element_label')} -"),
                "gap": tk.StringVar(value=f"{self.app.i18n.t('advanced.adaptive.gap_label')} -"),
                "confidence": tk.StringVar(value=f"{self.app.i18n.t('advanced.adaptive.confidence_label')} {self.app.i18n.t('advanced.adaptive.confidence_low')}"),
                "rounds": tk.StringVar(value=f"{self.app.i18n.t('advanced.adaptive.rounds_label')} 0"),
                "progress": tk.StringVar(value=f"{self.app.i18n.t('advanced.adaptive.rounds_label')} 0/100"),
            }

            vars_for_source = self.profile_summary_vars[source]

            ttk.Label(
                profile_box,
                text=title,
                font=("Segoe UI", 9, "bold"),
            ).grid(row=row * 2, column=0, sticky=tk.W, padx=10, pady=(8, 2))

            ttk.Label(
                profile_box,
                textvariable=vars_for_source["element"],
            ).grid(row=row * 2, column=1, sticky=tk.W, padx=10, pady=(8, 2))

            ttk.Label(
                profile_box,
                textvariable=vars_for_source["gap"],
            ).grid(row=row * 2, column=2, sticky=tk.W, padx=10, pady=(8, 2))

            ttk.Label(
                profile_box,
                textvariable=vars_for_source["confidence"],
                width=42,
            ).grid(row=row * 2, column=3, sticky=tk.W, padx=10, pady=(8, 2))

            ttk.Label(
                profile_box,
                textvariable=vars_for_source["rounds"],
            ).grid(row=row * 2, column=4, sticky=tk.W, padx=10, pady=(8, 2))

            progress = tk.Canvas(
                profile_box,
                height=22,
                highlightthickness=0,
                background="#eeeeee",
            )

            progress._profile_bar_state = None  # type: ignore[attr-defined]

            progress.bind(
                "<Configure>",
                lambda event: self._redraw_profile_progress_bar(event.widget),
            )

            progress.grid(
                row=row * 2 + 1,
                column=1,
                columnspan=3,
                sticky=tk.EW,
                padx=10,
                pady=(0, 8),
            )

            self.profile_progress_bars[source] = progress

            ttk.Label(
                profile_box,
                textvariable=vars_for_source["progress"],
                width=22,
                anchor=tk.W,
            ).grid(row=row * 2 + 1, column=4, sticky=tk.W, padx=10, pady=(0, 8))

        profile_box.columnconfigure(1, weight=1)
        profile_box.columnconfigure(2, weight=1)
        profile_box.columnconfigure(3, weight=1)

        add_profile_row(0, self.app.i18n.t("advanced.adaptive.straight"), "straight")
        add_profile_row(1, self.app.i18n.t("advanced.adaptive.iambic"), "iambic")

        profile_controls = ttk.LabelFrame(frame, text=self.app.i18n.t("advanced.adaptive.learning_title"))
        profile_controls.pack(fill=tk.X, pady=(0, 12))

        ttk.Checkbutton(
            profile_controls,
            text=self.app.i18n.t("advanced.adaptive.use_profile"),
            variable=self.app.use_timing_profile_var,
            command=self.app.decoder_controller.refresh_timing_profiles,
        ).pack(anchor=tk.W, padx=10, pady=(8, 6))

        grid = ttk.Frame(profile_controls)
        grid.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(grid, text=self.app.i18n.t("advanced.adaptive.recent_rounds")).grid(row=0, column=0, sticky=tk.W, pady=4)
        self.app.ui_helpers_controller.make_int_spinbox(
            grid,
            from_=10,
            to=100000,
            textvariable=self.app.decoder_profile_recent_rounds_var,
            width=8,
        ).grid(row=0, column=1, sticky=tk.W, padx=(8, 22), pady=4)

        ttk.Label(grid, text=self.app.i18n.t("advanced.adaptive.min_accuracy")).grid(row=0, column=2, sticky=tk.W, pady=4)
        self.app.ui_helpers_controller.make_int_spinbox(
            grid,
            from_=0,
            to=100,
            textvariable=self.app.decoder_profile_min_accuracy_var,
            width=6,
        ).grid(row=0, column=3, sticky=tk.W, padx=(8, 22), pady=4)

        ttk.Label(grid, text=self.app.i18n.t("advanced.adaptive.min_cleanliness")).grid(row=1, column=0, sticky=tk.W, pady=4)
        self.app.ui_helpers_controller.make_int_spinbox(
            grid,
            from_=0,
            to=100,
            textvariable=self.app.decoder_profile_min_cleanliness_var,
            width=6,
        ).grid(row=1, column=1, sticky=tk.W, padx=(8, 22), pady=4)

        ttk.Button(
            grid,
            text=self.app.i18n.t("advanced.adaptive.refresh_profile"),
            command=self._refresh_profile_summary,
        ).grid(row=1, column=2, columnspan=2, sticky=tk.W, pady=4)

        finish_box = ttk.LabelFrame(frame, text=self.app.i18n.t("advanced.adaptive.finish_box"))
        finish_box.pack(fill=tk.X, pady=(0, 12))

        ttk.Checkbutton(
            finish_box,
            text=self.app.i18n.t("advanced.adaptive.auto_finish"),
            variable=self.app.auto_finish_on_idle_var,
        ).pack(anchor=tk.W, padx=10, pady=(8, 6))

        finish_grid = ttk.Frame(finish_box)
        finish_grid.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(finish_grid, text=self.app.i18n.t("advanced.adaptive.idle_units")).grid(row=0, column=0, sticky=tk.W, pady=4)
        self.app.ui_helpers_controller.make_int_spinbox(
            finish_grid,
            from_=3,
            to=100,
            textvariable=self.app.auto_finish_idle_units_var,
            width=8,
        ).grid(row=0, column=1, sticky=tk.W, padx=(8, 22), pady=4)

        ttk.Label(finish_grid, text=self.app.i18n.t("advanced.adaptive.min_wait")).grid(row=0, column=2, sticky=tk.W, pady=4)
        self.app.ui_helpers_controller.make_int_spinbox(
            finish_grid,
            from_=1,
            to=30,
            textvariable=self.app.auto_finish_min_seconds_var,
            width=8,
        ).grid(row=0, column=3, sticky=tk.W, padx=(8, 22), pady=4)

        telemetry_box = ttk.LabelFrame(frame, text=self.app.i18n.t("advanced.adaptive.telemetry_box"))
        telemetry_box.pack(fill=tk.X, pady=(0, 12))

        row = ttk.Frame(telemetry_box)
        row.pack(fill=tk.X, padx=10, pady=8)
        ttk.Label(row, text=self.app.i18n.t("advanced.adaptive.pixels_per_unit")).pack(side=tk.LEFT)
        self.app.ui_helpers_controller.make_float_spinbox(
            row,
            from_=2.0,
            to=80.0,
            increment=0.5,
            textvariable=self.app.raw_telemetry_pixels_per_unit_var,
            width=8,
        ).pack(side=tk.LEFT, padx=(8, 0))

        self._refresh_profile_summary()

    def _redraw_profile_progress_bar(self, canvas: tk.Canvas) -> None:
        state = getattr(canvas, "_profile_bar_state", None)
        if state is None:
            return

        percent, state_text, fill_color = state

        self._draw_profile_progress_bar(
            canvas,
            percent=percent,
            state_text=state_text,
            fill_color=fill_color,
        )

    def _draw_profile_progress_bar(
        self,
        canvas: tk.Canvas,
        *,
        percent: float,
        state_text: str,
        fill_color: str,
    ) -> None:
        percent = max(0.0, min(100.0, float(percent)))

        canvas._profile_bar_state = (percent, state_text, fill_color)  # type: ignore[attr-defined]

        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())

        canvas.delete("all")

        fill_width = int(width * (percent / 100.0))
        label = f"{state_text} ({percent:.0f} %)"

        canvas.create_rectangle(
            0,
            0,
            width,
            height,
            fill="#eeeeee",
            outline="#cccccc",
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
            text=label,
            fill="#000000",
            font=("Segoe UI", 9, "bold"),
        )

    def _refresh_profile_summary(self) -> None:
        self.app.decoder_controller.refresh_timing_profiles()

        try:
            required_rounds = int(getattr(config, "DECODER_PROFILE_MIN_ROUNDS_REQUIRED", 100))
        except Exception:
            required_rounds = 100

        try:
            recent_sessions = self.app.ui_helpers_controller.safe_int_var(
                self.app.decoder_profile_recent_rounds_var,
                default=int(getattr(config, "DECODER_PROFILE_RECENT_ROUNDS", 300)),
                minimum=required_rounds,
                maximum=100000,
            )
        except Exception:
            recent_sessions = int(getattr(config, "DECODER_PROFILE_RECENT_ROUNDS", 300))

        try:
            min_accuracy = float(self.app.decoder_profile_min_accuracy_var.get())
        except Exception:
            min_accuracy = float(getattr(config, "DECODER_PROFILE_MIN_ACCURACY", 90.0))

        try:
            min_cleanliness = float(self.app.decoder_profile_min_cleanliness_var.get())
        except Exception:
            min_cleanliness = float(getattr(config, "DECODER_PROFILE_MIN_CLEANLINESS", 85.0))

        def ms(value: object) -> str:
            try:
                if value is None:
                    return "-"
                return f"{float(value) / 1000.0:.0f}"
            except Exception:
                return "-"

        ms_unit = self.app.i18n.t("advanced.adaptive.ms_unit")

        for source in ("straight", "iambic"):
            profile = self.app.decoder_controller.timing_profile_for_source(source)

            try:
                progress = self.app.db.timing_profile_progress(
                    source,
                    recent_sessions=recent_sessions,
                    min_accuracy=min_accuracy,
                    min_cleanliness=min_cleanliness,
                )
                good_rounds = int(progress.get("good_rounds") or 0)
            except Exception:
                good_rounds = int(getattr(profile, "sample_rounds", 0) or 0)

            confidence_full_rounds = int(
                getattr(config, "DECODER_PROFILE_CONFIDENCE_FULL_ROUNDS", 300)
            )

            confidence_value = (
                0.0
                if confidence_full_rounds <= 0
                else min(1.0, good_rounds / confidence_full_rounds)
            )

            try:
                min_seed_confidence = float(
                    getattr(config, "DECODER_PROFILE_MIN_CONFIDENCE_FOR_SEED", 0.30)
                )
            except Exception:
                min_seed_confidence = 0.30

            round_gate = (
                0.0
                if required_rounds <= 0
                else min(1.0, good_rounds / required_rounds)
            )

            confidence_gate = (
                0.0
                if min_seed_confidence <= 0
                else min(1.0, confidence_value / min_seed_confidence)
            )

            rounds_ready = good_rounds >= required_rounds
            confidence_ready = confidence_value >= min_seed_confidence
            profile_ready = rounds_ready and confidence_ready

            if source == "iambic":
                profile_has_values = (
                    getattr(profile, "element_unit_us", None) is not None
                    and getattr(profile, "letter_gap_us", None) is not None
                    and getattr(profile, "word_gap_us", None) is not None
                    and getattr(profile, "gap_unit_us", None) is not None
                )

                profile_ready = profile_ready and profile_has_values

            bar_percent = 100.0 if profile_ready else min(round_gate, confidence_gate) * 100.0

            if profile_ready:
                bar_state_text = self.app.i18n.t("advanced.adaptive.status_active")
                bar_color = "#42b883"
            elif rounds_ready or confidence_ready:
                bar_state_text = self.app.i18n.t("advanced.adaptive.status_almost")
                bar_color = "#f2c94c"
            else:
                bar_state_text = self.app.i18n.t("advanced.adaptive.status_gathering")
                bar_color = "#eb5757"

            confidence_text = self.app.history_controller.confidence_label(
                confidence_value,
                accepted_count=good_rounds,
            )

            vars_for_source = self.profile_summary_vars.get(source)
            if vars_for_source is None:
                continue

            element_val = ms(getattr(profile, "element_unit_us", None))
            vars_for_source["element"].set(
                f"{self.app.i18n.t('advanced.adaptive.element_label')} {element_val}{ms_unit if element_val != '-' else ''}"
            )

            if source == "iambic":
                lg_val = ms(getattr(profile, "letter_gap_us", None))
                wg_val = ms(getattr(profile, "word_gap_us", None))
                vars_for_source["gap"].set(
                    f"{self.app.i18n.t('advanced.adaptive.letter_gap_abbr')} {lg_val}{ms_unit if lg_val != '-' else ''} / "
                    f"{self.app.i18n.t('advanced.adaptive.word_gap_abbr')} {wg_val}{ms_unit if wg_val != '-' else ''}"
                )
            else:
                gap_val = ms(getattr(profile, "gap_unit_us", None))
                vars_for_source["gap"].set(
                    f"{self.app.i18n.t('advanced.adaptive.gap_label')} {gap_val}{ms_unit if gap_val != '-' else ''}"
                )

            vars_for_source["confidence"].set(
                f"{self.app.i18n.t('advanced.adaptive.confidence_label')} {confidence_text}"
            )
            vars_for_source["rounds"].set(
                f"{self.app.i18n.t('advanced.adaptive.rounds_label')} {good_rounds}"
            )

            if profile_ready:
                progress_text = self.app.i18n.t("advanced.adaptive.status_active")
            elif not rounds_ready:
                progress_text = self.app.i18n.t(
                    "advanced.adaptive.rounds_progress",
                    current=good_rounds,
                    required=required_rounds,
                )
            else:
                progress_text = self.app.i18n.t(
                    "advanced.adaptive.confidence_progress",
                    confidence=int(confidence_value * 100),
                )

            vars_for_source["progress"].set(progress_text)

            progress_bar = self.profile_progress_bars.get(source)
            if progress_bar is not None:
                self._draw_profile_progress_bar(
                    progress_bar,
                    percent=bar_percent,
                    state_text=bar_state_text,
                    fill_color=bar_color,
                )

    def _build_sound_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text=self.app.i18n.t("advanced.tab.sound"))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.sound.title"),
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.sound.description"),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        ttk.Checkbutton(
            frame,
            text=self.app.i18n.t("advanced.sound.enabled"),
            variable=self.app.sound_enabled_var,
        ).pack(anchor=tk.W, pady=(0, 10))

        sound_events = [
            ("practice_complete", self.app.i18n.t("advanced.sound.practice_complete")),
            ("serial_connected", self.app.i18n.t("advanced.sound.serial_connected")),
            ("serial_disconnected", self.app.i18n.t("advanced.sound.serial_disconnected")),
            ("level_up", self.app.i18n.t("advanced.sound.level_up")),
        ]

        for event_name, label in sound_events:
            event_var = self.app.sound_event_vars.get(event_name)

            if event_var is None:
                continue

            ttk.Checkbutton(
                frame,
                text=label,
                variable=event_var,
            ).pack(anchor=tk.W, pady=(0, 6))

    def _build_speed_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text=self.app.i18n.t("advanced.tab.speed"))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.speed.title"),
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.speed.description"),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        row_1 = ttk.Frame(frame)
        row_1.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            row_1,
            text=self.app.i18n.t("advanced.speed.target_wpm"),
            width=28,
        ).pack(side=tk.LEFT)

        self.app.ui_helpers_controller.make_int_spinbox(
            row_1,
            from_=5,
            to=80,
            textvariable=self.app.target_wpm_var,
            width=8,
        ).pack(side=tk.LEFT)

        ttk.Button(
            row_1,
            textvariable=self.app.morse_preview_button_var,
            command=self.app.audio_controller.toggle_morse_speed_preview,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            frame,
            text=self.app.i18n.t("settings_panel.suggest_speed"),
            command=self.app.effective_wpm_controller.optimize_timing_from_history,
        ).pack(anchor=tk.W, pady=(4, 0))

    def _build_skill_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text=self.app.i18n.t("advanced.tab.skill"))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.skill.title"),
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.skill.description").format(
                min_chars=getattr(config, "SKILL_RATING_MIN_TARGET_CHARS", 12)
            ),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        row_1 = ttk.Frame(frame)
        row_1.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_1,
            text=self.app.i18n.t("advanced.skill.recent_rounds"),
            width=28,
        ).pack(side=tk.LEFT)

        self.app.ui_helpers_controller.make_int_spinbox(
            row_1,
            from_=1,
            to=100000,
            textvariable=self.app.skill_recent_rounds_var,
            width=8,
        ).pack(side=tk.LEFT)

    def _build_effective_wpm_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text=self.app.i18n.t("advanced.tab.effective_wpm"))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.effective_wpm.title"),
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.effective_wpm.description"),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        row_1 = ttk.Frame(frame)
        row_1.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_1,
            text=self.app.i18n.t("advanced.effective_wpm.recent_rounds"),
            width=28,
        ).pack(side=tk.LEFT)

        self.app.ui_helpers_controller.make_int_spinbox(
            row_1,
            from_=1,
            to=100000,
            textvariable=self.app.effective_wpm_recent_rounds_var,
            width=8,
        ).pack(side=tk.LEFT)

        row_2 = ttk.Frame(frame)
        row_2.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_2,
            text=self.app.i18n.t("advanced.effective_wpm.min_accuracy"),
            width=28,
        ).pack(side=tk.LEFT)

        self.app.ui_helpers_controller.make_int_spinbox(
            row_2,
            from_=50,
            to=100,
            textvariable=self.app.effective_wpm_min_accuracy_var,
            width=8,
        ).pack(side=tk.LEFT)

        row_3 = ttk.Frame(frame)
        row_3.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_3,
            text=self.app.i18n.t("advanced.effective_wpm.min_cleanliness"),
            width=28,
        ).pack(side=tk.LEFT)

        self.app.ui_helpers_controller.make_int_spinbox(
            row_3,
            from_=50,
            to=100,
            textvariable=self.app.effective_wpm_min_cleanliness_var,
            width=8,
        ).pack(side=tk.LEFT)

    def _build_stats_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text=self.app.i18n.t("advanced.tab.stats"))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.stats.title"),
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.stats.description"),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        row_1 = ttk.Frame(frame)
        row_1.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_1,
            text=self.app.i18n.t("advanced.stats.recent_rounds"),
            width=28,
        ).pack(side=tk.LEFT)

        self.app.ui_helpers_controller.make_int_spinbox(
            row_1,
            from_=1,
            to=100000,
            textvariable=self.app.stats_recent_rounds_var,
            width=8,
        ).pack(side=tk.LEFT)

    def _build_debug_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text=self.app.i18n.t("advanced.tab.debug"))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.debug.title"),
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.debug.description"),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        ttk.Checkbutton(
            frame,
            text=self.app.i18n.t("advanced.debug.save_snapshot"),
            variable=self.app.debug_snapshot_enabled_var,
            command=self.app.settings_controller.save_ui_settings,
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.debug.save_snapshot_hint"),
            wraplength=590,
            foreground="#666666",
        ).pack(anchor=tk.W, pady=(0, 12))

        ttk.Checkbutton(
            frame,
            text=self.app.i18n.t("advanced.debug.save_history"),
            variable=self.app.debug_snapshot_save_history_var,
            command=self.app.settings_controller.save_ui_settings,
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.debug.save_history_hint"),
            wraplength=590,
            foreground="#666666",
        ).pack(anchor=tk.W, pady=(0, 14))

        ttk.Separator(frame).pack(fill=tk.X, pady=(4, 14))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.debug.tools_title"),
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        button_row_1 = ttk.Frame(frame)
        button_row_1.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(
            button_row_1,
            text=self.app.i18n.t("advanced.debug.open_window"),
            command=self._open_debug_window_from_settings,
        ).pack(side=tk.LEFT)

        ttk.Button(
            button_row_1,
            text=self.app.i18n.t("advanced.debug.copy_latest"),
            command=self.app.debug_controller.copy_latest_snapshot,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            button_row_1,
            text=self.app.i18n.t("advanced.debug.clear_data"),
            command=self.app.debug_controller.clear_snapshots,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(
            frame,
            text=self.app.i18n.t("advanced.debug.window_hint"),
            wraplength=590,
            foreground="#666666",
        ).pack(anchor=tk.W, pady=(6, 0))