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

        self.title("Asetukset")
        self.transient(app)
        self.grab_set()
        self.geometry("760x660")
        self.minsize(700, 560)

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(outer)
        notebook.pack(fill=tk.BOTH, expand=True)

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
            text="Sulje",
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
            # Windows/macOS: event.delta. Linux handled separately below.
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

    def _build_problem_chars_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Vaikeimmat merkit")

        ttk.Label(
            frame,
            text="Vaikeimmat merkit",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=(
                "Vaikeimmat merkit eivät korvaa koko merkkivalikoimaa. "
                "Ne painottavat niitä sallittuja merkkejä, joissa on ollut eniten virheitä."
            ),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        row_1 = ttk.Frame(frame)
        row_1.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_1,
            text="Vaikeimpien painotus %",
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
            text="Vaikeimpien määrä",
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
            text="Viimeisiä kierroksia",
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
        notebook.add(frame, text="Syöte ja yhteys")

        ttk.Label(
            frame,
            text="Syöte ja yhteys",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=(
                "Näillä asetuksilla valitaan, mistä syöte luetaan, yrittääkö ohjelma "
                "löytää Morsewurst-laitteen automaattisesti sarjaporteista ja "
                "päätetäänkö keskeneräinen kierros pitkän tauon jälkeen."
            ),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        ttk.Checkbutton(
            frame,
            text="Käytä telemetriaa totuutena",
            variable=self.app.use_telemetry_as_truth_var,
            command=self.app.input_controller.on_use_telemetry_as_truth_changed,
        ).pack(anchor=tk.W, pady=(0, 2))

        ttk.Label(
            frame,
            text=(
                "Suositus: pidä päällä. Tällöin harjoitus arvioidaan raakatelemetriasta "
                "eli painallusten todellisista ajoituksista. Jos asetus poistetaan käytöstä, "
                "ohjelma käyttää laitteen USB HID -näppäimistösyötettä, joka ei ole riittävän "
                "tarkka luotettavaan pisteytykseen."
            ),
            wraplength=420,
            foreground="#666666",
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Checkbutton(
            frame,
            text="Pidä syötekenttä aktiivisena",
            variable=self.app.keep_focus_var,
        ).pack(anchor=tk.W, pady=(0, 6))

        ttk.Checkbutton(
            frame,
            text="Yritä yhdistää sarjaporttiin automaattisesti",
            variable=self.app.auto_connect_serial_var,
            command=self.app.input_controller.on_auto_connect_serial_changed,
        ).pack(anchor=tk.W, pady=(0, 14))

        ttk.Separator(frame).pack(fill=tk.X, pady=(4, 14))

        ttk.Label(
            frame,
            text="Näppäimistön käyttö",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=(
                "Tällä asetuksella tietokoneen näppäimistö toimii virtuaalisena straight keynä. "
                "Painalluksista muodostetaan samaa raakatelemetriaa kuin fyysisestä Morsewurst-laitteesta."
            ),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 10))

        ttk.Checkbutton(
            frame,
            text="Morseta tietokoneen näppäimistöllä",
            variable=self.app.keyboard_morse_enabled_var,
            command=self.app.input_controller.on_keyboard_morse_enabled_changed,
        ).pack(anchor=tk.W, pady=(0, 8))

        key_row = ttk.Frame(frame)
        key_row.pack(anchor=tk.W, fill=tk.X, pady=(0, 8))

        ttk.Label(
            key_row,
            text="Käytettävä näppäin:",
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
            text=(
                "Kun tämä on päällä, ohjelma käyttää valittua näppäintä virtuaalisena straight keynä, "
                "pakottaa telemetrian totuudeksi ja poistaa sarjaportin automaattihaun käytöstä."
                "Huomioi, että näppäimistö ei ole luotettava ja tarkka morse-avain."
            ),
            wraplength=420,
            foreground="#666666",
        ).pack(anchor=tk.W, pady=(0, 14))

        ttk.Separator(frame).pack(fill=tk.X, pady=(4, 14))

        ttk.Label(
            frame,
            text="Automaattinen lopetus pitkän tauon jälkeen",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=(
                "Tämä päättää kierroksen, jos telemetriaa on tullut mutta syöte jäi "
                "liian lyhyeksi esimerkiksi puuttuvien merkkivälien takia."
            ),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 10))

        ttk.Checkbutton(
            frame,
            text="Päätä keskeneräinen kierros pitkän tauon jälkeen",
            variable=self.app.auto_finish_on_idle_var,
        ).pack(anchor=tk.W, pady=(0, 8))

        row_1 = ttk.Frame(frame)
        row_1.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_1,
            text="Tauko yksikköinä",
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
            text="Vähimmäistauko sekunteina",
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
        frame = self._make_scrollable_tab(notebook, "Tunnistus")

        ttk.Label(
            frame,
            text="Tunnistus ja ajoitusprofiili",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=(
                "Morsewurst käyttää tavoite-WPM:ää vain aloitusarviona ja oppii "
                "käyttäjän todellista rytmiä viimeisistä hyvistä kierroksista. "
                "Pisteen, viivan ja välien sisäisiä raja-arvoja ei säädetä käsin."
            ),
            wraplength=660,
        ).pack(anchor=tk.W, pady=(4, 12))

        profile_box = ttk.LabelFrame(frame, text="Opittu rytmiprofiili")
        profile_box.pack(fill=tk.X, pady=(0, 12))

        self.profile_summary_vars: dict[str, dict[str, tk.StringVar]] = {}
        self.profile_progress_bars: dict[str, tk.Canvas] = {}

        def add_profile_row(row: int, title: str, source: str) -> None:
            self.profile_summary_vars[source] = {
                "element": tk.StringVar(value="Elementti -"),
                "gap": tk.StringVar(value="Tauko -"),
                "confidence": tk.StringVar(value="Luottamus matala"),
                "rounds": tk.StringVar(value="Kierroksia 0"),
                "progress": tk.StringVar(value="Kierroksia 0/100"),
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

        add_profile_row(0, "Straight", "straight")
        add_profile_row(1, "Iambic", "iambic")

        profile_controls = ttk.LabelFrame(frame, text="Oppiminen")
        profile_controls.pack(fill=tk.X, pady=(0, 12))

        ttk.Checkbutton(
            profile_controls,
            text="Käytä opittua ajoitusprofiilia",
            variable=self.app.use_timing_profile_var,
            command=self.app.decoder_controller.refresh_timing_profiles,
        ).pack(anchor=tk.W, padx=10, pady=(8, 6))

        grid = ttk.Frame(profile_controls)
        grid.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(grid, text="Viimeisiä kierroksia").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.app.ui_helpers_controller.make_int_spinbox(
            grid,
            from_=10,
            to=100000,
            textvariable=self.app.decoder_profile_recent_rounds_var,
            width=8,
        ).grid(row=0, column=1, sticky=tk.W, padx=(8, 22), pady=4)

        ttk.Label(grid, text="Minimitarkkuus %").grid(row=0, column=2, sticky=tk.W, pady=4)
        self.app.ui_helpers_controller.make_int_spinbox(
            grid,
            from_=0,
            to=100,
            textvariable=self.app.decoder_profile_min_accuracy_var,
            width=6,
        ).grid(row=0, column=3, sticky=tk.W, padx=(8, 22), pady=4)

        ttk.Label(grid, text="Minimipuhtaus %").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.app.ui_helpers_controller.make_int_spinbox(
            grid,
            from_=0,
            to=100,
            textvariable=self.app.decoder_profile_min_cleanliness_var,
            width=6,
        ).grid(row=1, column=1, sticky=tk.W, padx=(8, 22), pady=4)

        ttk.Button(
            grid,
            text="Päivitä profiili",
            command=self._refresh_profile_summary,
        ).grid(row=1, column=2, columnspan=2, sticky=tk.W, pady=4)

        finish_box = ttk.LabelFrame(frame, text="Automaattinen kierroksen päättäminen")
        finish_box.pack(fill=tk.X, pady=(0, 12))

        ttk.Checkbutton(
            finish_box,
            text="Päätä kierros automaattisesti hiljaisuuden jälkeen",
            variable=self.app.auto_finish_on_idle_var,
        ).pack(anchor=tk.W, padx=10, pady=(8, 6))

        finish_grid = ttk.Frame(finish_box)
        finish_grid.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(finish_grid, text="Hiljaisuusyksiköt").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.app.ui_helpers_controller.make_int_spinbox(
            finish_grid,
            from_=3,
            to=100,
            textvariable=self.app.auto_finish_idle_units_var,
            width=8,
        ).grid(row=0, column=1, sticky=tk.W, padx=(8, 22), pady=4)

        ttk.Label(finish_grid, text="Minimiodotus s").grid(row=0, column=2, sticky=tk.W, pady=4)
        self.app.ui_helpers_controller.make_int_spinbox(
            finish_grid,
            from_=1,
            to=30,
            textvariable=self.app.auto_finish_min_seconds_var,
            width=8,
        ).grid(row=0, column=3, sticky=tk.W, padx=(8, 22), pady=4)

        telemetry_box = ttk.LabelFrame(frame, text="Raakatelemetrian näyttö")
        telemetry_box.pack(fill=tk.X, pady=(0, 12))

        row = ttk.Frame(telemetry_box)
        row.pack(fill=tk.X, padx=10, pady=8)
        ttk.Label(row, text="Pikseleitä / ajoitusyksikkö").pack(side=tk.LEFT)
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
                return "-" if value is None else f"{float(value) / 1000.0:.0f} ms"
            except Exception:
                return "-"

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
                bar_state_text = "Käytössä"
                bar_color = "#42b883"
            elif rounds_ready or confidence_ready:
                bar_state_text = "Melkein valmis"
                bar_color = "#f2c94c"
            else:
                bar_state_text = "Kerätään dataa"
                bar_color = "#eb5757"

            confidence_text = self.app.history_controller.confidence_label(
                confidence_value,
                accepted_count=good_rounds,
            )

            vars_for_source = self.profile_summary_vars.get(source)
            if vars_for_source is None:
                continue

            vars_for_source["element"].set(
                f"Elementti {ms(getattr(profile, 'element_unit_us', None))}"
            )

            if source == "iambic":
                vars_for_source["gap"].set(
                    "LG "
                    f"{ms(getattr(profile, 'letter_gap_us', None))} / "
                    "WG "
                    f"{ms(getattr(profile, 'word_gap_us', None))}"
                )
            else:
                vars_for_source["gap"].set(
                    f"Tauko {ms(getattr(profile, 'gap_unit_us', None))}"
                )
            vars_for_source["confidence"].set(
                f"Luottamus {confidence_text}"
            )
            vars_for_source["rounds"].set(
                f"Kierroksia {good_rounds}"
            )
            if profile_ready:
                progress_text = "Käytössä"
            elif not rounds_ready:
                progress_text = f"Kierroksia {good_rounds}/{required_rounds}"
            else:
                progress_text = (
                    f"Luottamus {confidence_value * 100:.0f}/"
                    f"{min_seed_confidence * 100:.0f} %"
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
        notebook.add(frame, text="Äänet")

        ttk.Label(
            frame,
            text="Äänet",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=(
                "Näillä asetuksilla hallitaan Morsewurstin ääniä. Yleinen äänikytkin "
                "toimii pääkytkimenä. Lisäksi yksittäisiä tapahtumaääniä voi ottaa "
                "käyttöön tai poistaa käytöstä erikseen."
            ),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        ttk.Checkbutton(
            frame,
            text="Äänet käytössä",
            variable=self.app.sound_enabled_var,
        ).pack(anchor=tk.W, pady=(0, 10))

        sound_events = [
            ("practice_complete", "Soita ääni, kun harjoitussarja valmistuu"),
            ("serial_connected", "Soita ääni, kun sarjalaite yhdistetään"),
            ("serial_disconnected", "Soita ääni, kun sarjalaite irrotetaan"),
            ("level_up", "Soita ääni, kun level nousee"),
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
        notebook.add(frame, text="Nopeus")

        ttk.Label(
            frame,
            text="Harjoitusnopeus",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=(
                "Tavoite-WPM määrittää standardiajan, johon suorituksen "
                "nopeuspisteitä verrataan."
            ),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        row_1 = ttk.Frame(frame)
        row_1.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            row_1,
            text="Tavoite WPM",
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
            text="Ehdota harjoitusnopeutta",
            command=self.app.effective_wpm_controller.optimize_timing_from_history,
        ).pack(anchor=tk.W, pady=(4, 0))

    def _build_skill_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Taitotaso")

        ttk.Label(
            frame,
            text="Taitotason laskenta",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=(
                "Taitotaso lasketaan viimeisistä riittävän pitkistä kierroksista. "
                f"Riittävän pitkä tarkoittaa vähintään "
                f"{getattr(config, 'SKILL_RATING_MIN_TARGET_CHARS', 12)} tavoitemerkkiä "
                "ilman välilyöntejä. Malli huomioi tehokkaan WPM:n, tarkkuuden, "
                "puhtauden, merkkien hallinnan, merkkien kattavuuden ja ajoituksen."
            ),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        row_1 = ttk.Frame(frame)
        row_1.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_1,
            text="Viimeisiä kierroksia",
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
        notebook.add(frame, text="Tehokas WPM")

        ttk.Label(
            frame,
            text="Tehokkaan WPM:n laskenta",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=(
                "Tehokas WPM lasketaan viimeisistä kierroksista, jotka ylittävät "
                "valitut tarkkuus- ja puhtausrajat. Varsinainen WPM lasketaan "
                "tavoitetekstin Morse-yksiköistä PARIS-standardin mukaan ja kierroksen kestosta."
            ),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        row_1 = ttk.Frame(frame)
        row_1.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_1,
            text="Viimeisiä kierroksia",
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
            text="Minimitarkkuus %",
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
            text="Minimipuhtaus %",
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
        notebook.add(frame, text="Tilastot")

        ttk.Label(
            frame,
            text="Yhteenvetotilastot",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text="Kuinka monesta viimeisimmästä kierroksesta etusivun keskiarvot lasketaan.",
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        row_1 = ttk.Frame(frame)
        row_1.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            row_1,
            text="Viimeisiä kierroksia",
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
        notebook.add(frame, text="Debug")

        ttk.Label(
            frame,
            text="Debug-data",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text=(
                "Debug-snapshot tallennetaan vasta kierroksen päätyttyä. "
                "Se ei kirjoita tiedostoon live-morsetuksen aikana, joten se ei "
                "käytännössä häiritse ajoituksen mittausta."
            ),
            wraplength=590,
        ).pack(anchor=tk.W, pady=(4, 14))

        ttk.Checkbutton(
            frame,
            text="Tallenna debug-snapshot kierroksen jälkeen",
            variable=self.app.debug_snapshot_enabled_var,
            command=self.app.settings_controller.save_ui_settings,
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(
            frame,
            text=(
                "Kun tämä on käytössä, viimeisin kierros tallennetaan aina tiedostoon "
                "latest_round_debug.json. Tiedosto korvataan jokaisen uuden debug-kierroksen jälkeen."
            ),
            wraplength=590,
            foreground="#666666",
        ).pack(anchor=tk.W, pady=(0, 12))

        ttk.Checkbutton(
            frame,
            text="Tallenna myös koko debug-historia",
            variable=self.app.debug_snapshot_save_history_var,
            command=self.app.settings_controller.save_ui_settings,
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(
            frame,
            text=(
                "Kun historia on käytössä, jokainen debug-snapshot lisätään "
                "debug_history.jsonl-tiedostoon. Näin yksittäisiä kierroksia voidaan "
                "verrata myöhemmin."
            ),
            wraplength=590,
            foreground="#666666",
        ).pack(anchor=tk.W, pady=(0, 14))

        ttk.Separator(frame).pack(fill=tk.X, pady=(4, 14))

        ttk.Label(
            frame,
            text="Debug-työkalut",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        button_row_1 = ttk.Frame(frame)
        button_row_1.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(
            button_row_1,
            text="Avaa debug-ikkuna",
            command=self._open_debug_window_from_settings,
        ).pack(side=tk.LEFT)

        ttk.Button(
            button_row_1,
            text="Kopioi viimeisin kierros",
            command=self.app.debug_controller.copy_latest_snapshot,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            button_row_1,
            text="Tyhjennä debug-data",
            command=self.app.debug_controller.clear_snapshots,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(
            frame,
            text=(
                "Debug-ikkunassa voit näyttää viimeisimmän kierroksen, koko historian "
                "siistissä muodossa tai raakana JSONL-datana."
            ),
            wraplength=590,
            foreground="#666666",
        ).pack(anchor=tk.W, pady=(6, 0))