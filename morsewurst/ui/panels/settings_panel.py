# ============================================================
# morsewurst/ui/panels/settings_panel.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def build_settings_panel(app: tk.Misc, parent: ttk.Frame) -> None:
    settings = ttk.LabelFrame(parent, text="Harjoituksen asetukset")
    settings.pack(fill=tk.X)

    if not hasattr(app, "wxmor_disabled_widgets"):
        app.wxmor_disabled_widgets = []

    # Merkkivalinnat
    options = ttk.Frame(settings)
    options.pack(fill=tk.X, padx=10, pady=(8, 4))

    app.use_letters_check = ttk.Checkbutton(
        options,
        text="Kirjaimet A-Z",
        variable=app.use_letters_var,
    )
    app.use_letters_check.grid(row=0, column=0, sticky=tk.W)

    app.use_numbers_check = ttk.Checkbutton(
        options,
        text="Numerot 0-9",
        variable=app.use_numbers_var,
    )
    app.use_numbers_check.grid(row=0, column=1, sticky=tk.W, padx=(18, 0))

    app.use_punctuation_check = ttk.Checkbutton(
        options,
        text="Erikoismerkit",
        variable=app.use_punctuation_var,
    )
    app.use_punctuation_check.grid(row=1, column=0, sticky=tk.W, pady=(4, 0))

    app.practice_wxmor_check = ttk.Checkbutton(
        options,
        text="Harjoittele WX-MOR-sanomaa",
        variable=app.practice_wxmor_var,
        command=app.wxmor_controller.update_practice_state,
    )
    app.practice_wxmor_check.grid(
        row=2,
        column=0,
        columnspan=2,
        sticky=tk.W,
        pady=(10, 0),
    )

    app.wxmor_profile_label = ttk.Label(
        options,
        text="WX-MOR-profiili",
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
        text="Harjoittele vaikeimpia merkkejä",
        variable=app.practice_problem_chars_var,
    )
    app.practice_problem_chars_check.grid(
        row=4,
        column=0,
        columnspan=2,
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

    app.practice_rounds_label = ttk.Label(counts, text="Kierroksia")
    app.practice_rounds_label.grid(row=0, column=0, sticky=tk.W)

    app.practice_rounds_spin = app.ui_helpers_controller.make_int_spinbox(
        counts,
        from_=1,
        to=1000,
        textvariable=app.practice_rounds_var,
        width=6,
    )
    app.practice_rounds_spin.grid(row=0, column=1, sticky=tk.W)

    app.min_groups_label = ttk.Label(counts, text="Ryhmiä min")
    app.min_groups_label.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))

    app.min_groups_spin = app.ui_helpers_controller.make_int_spinbox(
        counts,
        from_=1,
        to=100,
        textvariable=app.min_groups_var,
        width=6,
    )
    app.min_groups_spin.grid(row=1, column=1, sticky=tk.W, pady=(8, 0))

    app.max_groups_label = ttk.Label(counts, text="max")
    app.max_groups_label.grid(row=1, column=2, sticky=tk.W, pady=(8, 0))

    app.max_groups_spin = app.ui_helpers_controller.make_int_spinbox(
        counts,
        from_=1,
        to=100,
        textvariable=app.max_groups_var,
        width=6,
    )
    app.max_groups_spin.grid(row=1, column=3, sticky=tk.W, pady=(8, 0))

    app.min_chars_label = ttk.Label(counts, text="Merkkejä min")
    app.min_chars_label.grid(row=2, column=0, sticky=tk.W, pady=(8, 0))

    app.min_chars_spin = app.ui_helpers_controller.make_int_spinbox(
        counts,
        from_=1,
        to=100,
        textvariable=app.min_chars_var,
        width=6,
    )
    app.min_chars_spin.grid(row=2, column=1, sticky=tk.W, pady=(8, 0))

    app.max_chars_label = ttk.Label(counts, text="max")
    app.max_chars_label.grid(row=2, column=2, sticky=tk.W, pady=(8, 0))

    app.max_chars_spin = app.ui_helpers_controller.make_int_spinbox(
        counts,
        from_=1,
        to=100,
        textvariable=app.max_chars_var,
        width=6,
    )
    app.max_chars_spin.grid(row=2, column=3, sticky=tk.W, pady=(8, 0))

    # WX-MOR-tilassa nämä normaalin satunnaisharjoituksen asetukset poistetaan käytöstä.
    # Kierroksia-asetusta ei lisätä listaan, koska sen pitää jäädä käyttöön myös WX-MOR-harjoituksessa.
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

    # Harjoitusnopeus
    speed = ttk.LabelFrame(parent, text="Harjoitusnopeus")
    speed.pack(fill=tk.X, pady=(8, 0))

    speed_row = ttk.Frame(speed)
    speed_row.pack(fill=tk.X, padx=10, pady=8)

    ttk.Button(
        speed_row,
        text="Ehdota harjoitusnopeutta",
        command=app.effective_wpm_controller.optimize_timing_from_history,
    ).pack(side=tk.LEFT)

    ttk.Label(
        speed_row,
        text="Tavoite (WPM)",
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