# ============================================================
# morsewurst/ui/panels/training_panel.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import morsewurst.config as config


def build_training_panel(app: tk.Misc, parent: ttk.Frame) -> None:
    """Build the active training panel.

    This panel contains the current target, raw telemetry visualization,
    hidden HID fallback input and decoded telemetry text.
    """

    target_frame = ttk.LabelFrame(parent, text=app.i18n.t("training.target_title"))
    target_frame.pack(fill=tk.X)

    ttk.Label(
        target_frame,
        textvariable=app.target_var,
        font=("Consolas", 30, "bold"),
        wraplength=getattr(config, "UI_TARGET_WRAP_LENGTH", 820),
    ).pack(anchor=tk.W, padx=12, pady=12)

    raw_frame = ttk.LabelFrame(parent, text=app.i18n.t("training.raw_telemetry_title"))
    raw_frame.pack(fill=tk.X, pady=(10, 0))

    raw_canvas_frame = ttk.Frame(raw_frame)
    raw_canvas_frame.pack(fill=tk.X, padx=12, pady=(10, 0))

    app.raw_canvas = tk.Canvas(
        raw_canvas_frame,
        height=getattr(config, "UI_RAW_TELEMETRY_HEIGHT", 72),
        background="#ffffff",
        highlightthickness=1,
        highlightbackground="#cccccc",
        xscrollincrement=1,
    )
    app.raw_canvas.pack(fill=tk.X, expand=True)

    app.raw_scrollbar = ttk.Scrollbar(
        raw_frame,
        orient=tk.HORIZONTAL,
        command=app.raw_canvas.xview,
    )
    app.raw_scrollbar.pack(fill=tk.X, padx=12, pady=(0, 10))

    app.raw_canvas.configure(
        xscrollcommand=app.raw_scrollbar.set,
    )

    app.raw_telemetry_follow_latest = True

    def disable_raw_follow_latest() -> None:
        app.raw_telemetry_follow_latest = False

    def enable_raw_follow_latest() -> None:
        app.raw_telemetry_follow_latest = True
        app.raw_canvas.xview_moveto(1.0)

    def on_raw_scrollbar_press(_event: tk.Event) -> None:
        disable_raw_follow_latest()

    def on_raw_mousewheel(event: tk.Event) -> str:
        disable_raw_follow_latest()

        if event.delta > 0:
            app.raw_canvas.xview_scroll(-3, "units")
        else:
            app.raw_canvas.xview_scroll(3, "units")

        return "break"

    def on_raw_button_press(event: tk.Event) -> None:
        disable_raw_follow_latest()
        app.raw_canvas.scan_mark(event.x, event.y)

    def on_raw_drag(event: tk.Event) -> None:
        app.raw_canvas.scan_dragto(event.x, event.y, gain=1)

    def on_raw_double_click(_event: tk.Event) -> None:
        enable_raw_follow_latest()

    app.raw_scrollbar.bind("<ButtonPress-1>", on_raw_scrollbar_press)

    app.raw_canvas.bind("<MouseWheel>", on_raw_mousewheel)
    app.raw_canvas.bind("<Shift-MouseWheel>", on_raw_mousewheel)

    app.raw_canvas.bind("<ButtonPress-1>", on_raw_button_press)
    app.raw_canvas.bind("<B1-Motion>", on_raw_drag)
    app.raw_canvas.bind("<Double-Button-1>", on_raw_double_click)

    app.input_entry = ttk.Entry(parent, textvariable=app.input_var)
    app.input_entry.place(x=-10000, y=-10000, width=1, height=1)
    app.input_entry.bind("<KeyPress>", app.input_controller.on_input_key_press)
    app.input_entry.bind("<KeyRelease>", app.input_controller.on_input_key_release)

    telemetry_frame = ttk.LabelFrame(parent, text=app.i18n.t("training.decoded_title"))
    telemetry_frame.pack(fill=tk.X, pady=(10, 0))

    app.telemetry_text_widget = tk.Text(
        telemetry_frame,
        height=2,
        font=("Consolas", 17),
        wrap=tk.WORD,
        borderwidth=0,
        highlightthickness=0,
        background="#f0f0f0",
        padx=0,
        pady=0,
    )
    app.telemetry_text_widget.pack(fill=tk.X, anchor=tk.W, padx=12, pady=8)

    app.telemetry_text_widget.tag_configure(
        "rescued",
        foreground="#9a6b00",
        font=("Consolas", 17, "bold"),
    )
    app.telemetry_text_widget.tag_configure(
        "unknown",
        foreground="#b00020",
        font=("Consolas", 17, "bold"),
    )
    app.telemetry_text_widget.configure(state=tk.DISABLED)