# ============================================================
# morsewurst/ui/scratchpad_window.py
# ============================================================

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk

import morsewurst.config as config


class ScratchpadWindow(tk.Toplevel):
    """Free-copy Morse Scratchpad window."""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.app = app
        self.tr = app.i18n.t
        self._closing = False

        self.title(self.tr("scratchpad.window.title", "Scratchpad"))
        self.geometry(self.app.scratchpad_controller.window_geometry())
        self.minsize(
            int(getattr(config, "UI_SCRATCHPAD_WINDOW_MIN_WIDTH", 560)),
            int(getattr(config, "UI_SCRATCHPAD_WINDOW_MIN_HEIGHT", 420)),
        )
        self.transient(app)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Configure>", self._on_configure, add="+")

        self.stats_vars: dict[str, tk.StringVar] = {
            "chars": tk.StringVar(value="0"),
            "words": tk.StringVar(value="0"),
            "time": tk.StringVar(value="00:00"),
            "avg_wpm": tk.StringVar(value="-"),
            "current_wpm": tk.StringVar(value="-"),
            "source": tk.StringVar(value="-"),
            "pending": tk.StringVar(value="-"),
            "unknown": tk.StringVar(value="0"),
        }
        self.pause_button_var = tk.StringVar(value=self.tr("scratchpad.action.pause", "Pause input"))
        self.status_var = tk.StringVar(value=self.tr("scratchpad.status.ready", "Ready."))
        self.raw_panel_visible_var = tk.BooleanVar(
            value=bool(self.app.scratchpad_raw_panel_visible_var.get())
        )
        self.raw_telemetry_follow_latest = True

        self._build_ui()
        self.app.scratchpad_controller.enter_mode()
        self.refresh_from_controller()
        self.after(100, self.text.focus_set)

    # ------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=0)
        root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(root)
        toolbar.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))

        ttk.Button(
            toolbar,
            text=self.tr("scratchpad.action.clear", "Clear"),
            command=self.clear_all,
        ).pack(side=tk.LEFT)
        ttk.Button(
            toolbar,
            text=self.tr("scratchpad.action.copy_all", "Copy all"),
            command=self.copy_all,
        ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(
            toolbar,
            text=self.tr("scratchpad.action.reset_stats", "Reset stats"),
            command=self.app.scratchpad_controller.reset_stats_only,
        ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(
            toolbar,
            textvariable=self.pause_button_var,
            command=self.app.scratchpad_controller.toggle_paused,
        ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Checkbutton(
            toolbar,
            text=self.tr("scratchpad.option.show_raw", "Raw telemetry"),
            variable=self.raw_panel_visible_var,
            command=self.on_raw_panel_toggled,
        ).pack(side=tk.LEFT, padx=(12, 0))

        stats = ttk.LabelFrame(root, text=self.tr("scratchpad.stats.title", "Session"))
        stats.grid(row=0, column=1, rowspan=2, sticky=tk.NE, padx=(10, 0))
        self._build_stats_grid(stats)

        text_frame = ttk.Frame(root)
        text_frame.grid(row=1, column=0, sticky=tk.NSEW)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            undo=True,
            autoseparators=True,
            maxundo=-1,
            font=(
                str(getattr(config, "UI_SCRATCHPAD_FONT_FAMILY", "Segoe UI")),
                int(getattr(config, "UI_SCRATCHPAD_FONT_SIZE", 16)),
            ),
            background="white",
            foreground="black",
            insertbackground="black",
            padx=10,
            pady=8,
        )
        self.text.grid(row=0, column=0, sticky=tk.NSEW)

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text.yview)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.text.configure(yscrollcommand=scrollbar.set)
        # Handle the selected Keyboard Morse key before Tk Text inserts it as
        # normal editable text. Other keys fall through to the normal Text
        # widget bindings, so Ctrl+A, Ctrl+C and Ctrl+Z keep working.
        self.text.bind("<KeyPress>", self.on_text_key_press)
        self.text.bind("<KeyRelease>", self.on_text_key_release)
        self.text.bind("<Control-a>", self.select_all)
        self.text.bind("<Control-A>", self.select_all)

        self.raw_frame = ttk.LabelFrame(root, text=self.tr("scratchpad.raw.title", "Raw telemetry"))
        self.raw_frame.columnconfigure(0, weight=1)
        self.raw_canvas = tk.Canvas(
            self.raw_frame,
            height=int(getattr(config, "UI_RAW_TELEMETRY_HEIGHT", 72)),
            background="#ffffff",
            highlightthickness=1,
            highlightbackground="#d0d0d0",
        )
        self.raw_canvas.grid(row=0, column=0, sticky=tk.EW)
        self.raw_scrollbar = ttk.Scrollbar(
            self.raw_frame,
            orient=tk.HORIZONTAL,
            command=self.raw_canvas.xview,
        )
        self.raw_scrollbar.grid(row=1, column=0, sticky=tk.EW)
        self.raw_canvas.configure(xscrollcommand=self.raw_scrollbar.set)
        self.raw_canvas.bind("<Configure>", self._on_raw_canvas_configure, add="+")

        self.status_label = ttk.Label(root, textvariable=self.status_var, anchor=tk.W)
        self.status_label.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0))

        self.apply_raw_panel_visibility()

    def _build_stats_grid(self, parent: ttk.Frame) -> None:
        rows = [
            ("scratchpad.stats.characters", "Chars", "chars"),
            ("scratchpad.stats.words", "Words", "words"),
            ("scratchpad.stats.time", "Time", "time"),
            ("scratchpad.stats.avg_wpm", "Avg WPM", "avg_wpm"),
            ("scratchpad.stats.current_wpm", "Now WPM", "current_wpm"),
            ("scratchpad.stats.source", "Source", "source"),
            ("scratchpad.stats.pending", "Pending", "pending"),
            ("scratchpad.stats.unknown", "Unknown", "unknown"),
        ]
        label_size = int(getattr(config, "UI_SCRATCHPAD_STATS_LABEL_FONT_SIZE", 7))
        value_size = int(getattr(config, "UI_SCRATCHPAD_STATS_VALUE_FONT_SIZE", 8))

        for row, (key, default, var_name) in enumerate(rows):
            ttk.Label(
                parent,
                text=self.tr(key, default),
                font=("Segoe UI", label_size),
                foreground="#666666",
            ).grid(row=row, column=0, sticky=tk.W, padx=(6, 6), pady=(2, 0))
            ttk.Label(
                parent,
                textvariable=self.stats_vars[var_name],
                font=("Segoe UI", value_size, "bold"),
                anchor=tk.E,
                width=10,
            ).grid(row=row, column=1, sticky=tk.E, padx=(0, 6), pady=(2, 0))

    # ------------------------------------------------------------
    # Window actions
    # ------------------------------------------------------------

    def clear_all(self) -> None:
        self.app.scratchpad_controller.clear_text_and_session()
        self.status_var.set(self.tr("scratchpad.status.cleared", "Scratchpad cleared."))

    def clear_text(self, *, keep_session: bool = False) -> None:
        del keep_session
        self.text.delete("1.0", tk.END)
        self.text.edit_reset()
        self.refresh_from_controller()

    def copy_all(self) -> None:
        content = self.text_content()
        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_var.set(self.tr("scratchpad.status.copied", "Copied to clipboard."))

    def select_all(self, _event: tk.Event | None = None) -> str:
        self.text.tag_add(tk.SEL, "1.0", tk.END)
        self.text.mark_set(tk.INSERT, "1.0")
        self.text.see(tk.INSERT)
        return "break"

    def on_text_key_press(self, event: tk.Event) -> str | None:
        if self.app.input_controller.handle_keyboard_morse_key_press(event):
            return "break"
        return None

    def on_text_key_release(self, event: tk.Event) -> str | None:
        if self.app.input_controller.handle_keyboard_morse_key_release(event):
            return "break"
        self.after_idle(self.refresh_from_controller)
        return None

    def on_raw_panel_toggled(self) -> None:
        self.app.scratchpad_controller.remember_raw_panel_visible(
            bool(self.raw_panel_visible_var.get())
        )
        self.raw_telemetry_follow_latest = True
        self.apply_raw_panel_visibility()

    def apply_raw_panel_visibility(self) -> None:
        if bool(self.raw_panel_visible_var.get()):
            self.raw_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(8, 0))
            self._draw_raw_telemetry()
        else:
            self.raw_frame.grid_forget()

    # ------------------------------------------------------------
    # Controller updates
    # ------------------------------------------------------------

    def insert_decoded_text(self, text: str) -> None:
        if not text:
            return

        try:
            focused_widget = self.focus_get()
        except Exception:
            focused_widget = None

        insert_index = tk.INSERT if focused_widget is self.text else tk.END
        self.text.insert(insert_index, text)
        self.text.edit_separator()
        self.text.see(tk.INSERT if insert_index == tk.INSERT else tk.END)

    def refresh_from_controller(self) -> None:
        stats = self.app.scratchpad_controller.stats()
        self.stats_vars["chars"].set(str(stats.get("chars", 0)))
        self.stats_vars["words"].set(str(stats.get("words", 0)))
        self.stats_vars["time"].set(self._format_elapsed(float(stats.get("elapsed_seconds") or 0.0)))
        self.stats_vars["avg_wpm"].set(self._format_wpm(stats.get("avg_wpm")))
        self.stats_vars["current_wpm"].set(self._format_wpm(stats.get("current_wpm")))
        self.stats_vars["source"].set(self._localized_source(str(stats.get("source") or "-")))
        self.stats_vars["pending"].set(str(stats.get("pending") or "-"))
        self.stats_vars["unknown"].set(str(stats.get("unknown", 0)))

        paused = bool(stats.get("paused"))
        self.pause_button_var.set(
            self.tr("scratchpad.action.resume", "Resume input")
            if paused
            else self.tr("scratchpad.action.pause", "Pause input")
        )
        if paused:
            self.status_var.set(self.tr("scratchpad.status.paused", "Scratchpad input paused."))
        elif int(stats.get("tones") or 0) > 0:
            self.status_var.set(self.tr("scratchpad.status.receiving", "Scratchpad receiving Morse input."))
        else:
            self.status_var.set(self.tr("scratchpad.status.ready", "Ready."))

        if bool(self.raw_panel_visible_var.get()):
            self._draw_raw_telemetry()

    def _draw_raw_telemetry(self) -> None:
        canvas = self.raw_canvas

        try:
            visible_width = max(1, int(canvas.winfo_width()))
            height = max(1, int(canvas.winfo_height()))
        except Exception:
            return

        canvas.delete("all")
        tones = self.app.scratchpad_controller.raw_tone_events()

        if not tones:
            canvas.configure(scrollregion=(0, 0, visible_width, height))
            canvas.xview_moveto(0.0)
            canvas.create_text(
                10,
                height // 2,
                text=self.tr("scratchpad.raw.empty", "No telemetry yet."),
                anchor=tk.W,
                fill="#777777",
                font=("Segoe UI", 10),
            )
            return

        first_t = int(tones[0]["t0"])
        last_t = int(tones[-1]["t1"])
        current_time_us = self.app.scratchpad_controller.current_device_time_us()
        if current_time_us is not None:
            last_t = max(last_t, int(current_time_us))

        unit_us = self.app.scratchpad_controller.raw_telemetry_unit_us(current_time_us)

        try:
            px_per_unit = self.app.ui_helpers_controller.safe_float_var(
                self.app.raw_telemetry_pixels_per_unit_var,
                default=float(getattr(config, "RAW_TELEMETRY_PIXELS_PER_UNIT", 8.0)),
                minimum=2.0,
                maximum=80.0,
            )
        except Exception:
            px_per_unit = float(getattr(config, "RAW_TELEMETRY_PIXELS_PER_UNIT", 8.0))

        px_per_us = float(px_per_unit) / max(1.0, float(unit_us))
        total_us = max(1, last_t - first_t)

        virtual_width = int(total_us * px_per_us) + 40
        virtual_width = max(
            visible_width,
            min(
                int(getattr(config, "RAW_TELEMETRY_MAX_CANVAS_WIDTH", 20000)),
                virtual_width,
            ),
        )

        canvas.configure(scrollregion=(0, 0, virtual_width, height))

        y_mid = height // 2
        y1 = y_mid - 12
        y2 = y_mid + 12

        canvas.create_line(
            0,
            y_mid,
            virtual_width,
            y_mid,
            fill="#d9d9d9",
            width=1,
        )

        for event in tones:
            x1 = int((int(event["t0"]) - first_t) * px_per_us) + 20
            x2 = int((int(event["t1"]) - first_t) * px_per_us) + 20

            if x2 <= x1:
                x2 = x1 + 1

            is_open = bool(event.get("_open"))
            canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill="#666666" if is_open else "#111111",
                outline="#111111",
            )

        if self.raw_telemetry_follow_latest:
            canvas.xview_moveto(1.0)

    def _on_raw_canvas_configure(self, _event: tk.Event) -> None:
        if bool(self.raw_panel_visible_var.get()):
            self.after_idle(self._draw_raw_telemetry)

    def text_content(self) -> str:
        return self.text.get("1.0", "end-1c")

    def _format_elapsed(self, seconds: float) -> str:
        seconds = max(0, int(seconds))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _format_wpm(self, value: Any) -> str:
        try:
            number = float(value)
        except Exception:
            return "-"
        if number <= 0:
            return "-"
        return f"{number:.1f}"

    def _localized_source(self, source: str) -> str:
        source = source.strip().lower()
        if source in {"straight", "iambic", "keyboard", "mixed", "unknown"}:
            return self.tr(f"scratchpad.source.{source}", source)
        if not source or source == "-":
            return "-"
        return source

    def _on_configure(self, event: tk.Event) -> None:
        if getattr(event, "widget", None) is not self or self._closing:
            return
        try:
            self.app.scratchpad_controller.remember_window_geometry(self.geometry())
        except Exception:
            pass

    def on_close(self) -> None:
        self._closing = True
        try:
            self.app.scratchpad_controller.remember_window_geometry(self.geometry())
        except Exception:
            pass
        try:
            self.app.settings_controller.save_ui_settings_async()
        except Exception:
            pass
        self.app.scratchpad_controller.leave_mode()
        self.app.scratchpad_window = None
        self.destroy()
