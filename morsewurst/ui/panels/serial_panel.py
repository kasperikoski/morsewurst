# ============================================================
# morsewurst/ui/panels/serial_panel.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def build_serial_panel(app: tk.Misc, parent: ttk.Frame) -> None:
    """Build serial telemetry connection controls."""

    serial_frame = ttk.LabelFrame(parent, text=app.i18n.t("serial_panel.title"))
    serial_frame.pack(fill=tk.X, pady=(10, 0))

    inner = ttk.Frame(serial_frame)
    inner.pack(fill=tk.X, padx=8, pady=8)

    inner.columnconfigure(0, weight=1)
    inner.columnconfigure(1, weight=0)

    # Row 0: port selector and refresh button.
    app.port_combo = ttk.Combobox(
        inner,
        textvariable=app.port_var,
        state="readonly",
        values=[],
    )
    app.port_combo.grid(
        row=0,
        column=0,
        sticky="ew",
        padx=(0, 8),
        pady=(0, 8),
    )

    ttk.Button(
        inner,
        text=app.i18n.t("serial_panel.refresh"),
        command=app.serial_controller.refresh_ports,
    ).grid(
        row=0,
        column=1,
        sticky="e",
        pady=(0, 8),
    )

    # Row 1: buttons on the left and connection status on the right.
    button_row = ttk.Frame(inner)
    button_row.grid(
        row=1,
        column=0,
        sticky="w",
    )

    app.connect_serial_button = ttk.Button(
        button_row,
        text=app.i18n.t("serial_panel.connect"),
        command=app.serial_controller.connect_serial,
    )
    app.connect_serial_button.pack(side=tk.LEFT)

    app.disconnect_serial_button = ttk.Button(
        button_row,
        text=app.i18n.t("serial_panel.disconnect"),
        command=app.serial_controller.disconnect_serial,
    )
    app.disconnect_serial_button.pack(side=tk.LEFT, padx=(6, 0))

    app.serial_status_label = ttk.Label(
        inner,
        textvariable=app.serial_status_var,
        anchor=tk.E,
        justify=tk.RIGHT,
        font=("Segoe UI", 9, "bold"),
    )

    app.serial_status_label.grid(
        row=1,
        column=1,
        sticky="e",
    )

    # Row 2: latest serial event.
    ttk.Label(
        inner,
        textvariable=app.last_event_var,
        foreground="#444444",
    ).grid(
        row=2,
        column=0,
        columnspan=2,
        sticky="w",
        pady=(8, 0),
    )

    app.serial_controller.update_serial_buttons()