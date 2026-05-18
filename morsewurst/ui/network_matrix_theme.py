# ============================================================
# morsewurst/ui/network_matrix_theme.py
# ============================================================

from __future__ import annotations

from typing import Callable

import tkinter as tk


class MatrixTheme:
    """Local visual constants for the Morsewurst Network lobby.

    This module intentionally avoids global ttk theme changes. The Network
    lobby must not alter the appearance of the main Morsewurst application.
    """

    background = "#030704"
    panel = "#07130a"
    panel_alt = "#0b1d10"
    border = "#1a6f39"
    border_dim = "#0d3d22"
    text = "#b8ffd0"
    text_dim = "#63a878"
    accent = "#39ff88"
    accent_dim = "#1ea85b"
    warning = "#ffd166"
    error = "#ff5c7a"
    muted = "#344d3b"
    input_bg = "#010301"

    title_font = ("Consolas", 18, "bold")
    heading_font = ("Consolas", 12, "bold")
    body_font = ("Consolas", 10)
    small_font = ("Consolas", 9)
    button_font = ("Consolas", 10, "bold")
    mono_font = ("Consolas", 10)


def configure_toplevel(window: tk.Toplevel) -> None:
    """Apply only local toplevel styling to the Network window."""

    window.configure(background=MatrixTheme.background)


def apply_ttk_theme(window: tk.Misc) -> None:
    """Compatibility hook for older Network lobby code.

    Do not call ttk.Style.theme_use() here. Changing the active ttk theme is a
    global Tk operation and would also affect the main application window.
    """

    return


def make_panel(parent: tk.Misc, *, padx: int = 14, pady: int = 12) -> tk.Frame:
    return tk.Frame(
        parent,
        background=MatrixTheme.panel,
        highlightbackground=MatrixTheme.border_dim,
        highlightcolor=MatrixTheme.border,
        highlightthickness=1,
        bd=0,
        padx=padx,
        pady=pady,
    )


def make_label(
    parent: tk.Misc,
    text: str = "",
    *,
    variable: tk.StringVar | None = None,
    font: tuple | None = None,
    foreground: str | None = None,
    background: str | None = None,
    wraplength: int | None = None,
    justify: str = tk.LEFT,
) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        textvariable=variable,
        font=font or MatrixTheme.body_font,
        fg=foreground or MatrixTheme.text,
        bg=background or MatrixTheme.panel,
        wraplength=wraplength or 0,
        justify=justify,
        anchor=tk.W,
        bd=0,
        highlightthickness=0,
    )


def make_button(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None],
    *,
    width: int | None = None,
    danger: bool = False,
) -> tk.Button:
    foreground = MatrixTheme.error if danger else MatrixTheme.accent
    active_background = "#1f0710" if danger else "#0f2c18"

    button = tk.Button(
        parent,
        text=text,
        command=command,
        font=MatrixTheme.button_font,
        fg=foreground,
        bg=MatrixTheme.input_bg,
        activeforeground=MatrixTheme.text,
        activebackground=active_background,
        disabledforeground=MatrixTheme.muted,
        relief=tk.FLAT,
        bd=0,
        highlightbackground=MatrixTheme.border,
        highlightcolor=MatrixTheme.border,
        highlightthickness=1,
        padx=10,
        pady=6,
        cursor="hand2",
        takefocus=True,
    )

    if width is not None:
        button.configure(width=width)

    return button


def make_entry(
    parent: tk.Misc,
    variable: tk.StringVar,
    *,
    show: str = "",
    width: int = 34,
) -> tk.Entry:
    return tk.Entry(
        parent,
        textvariable=variable,
        show=show,
        width=width,
        font=MatrixTheme.mono_font,
        fg=MatrixTheme.text,
        bg=MatrixTheme.input_bg,
        insertbackground=MatrixTheme.accent,
        selectforeground=MatrixTheme.background,
        selectbackground=MatrixTheme.accent,
        relief=tk.FLAT,
        bd=0,
        highlightbackground=MatrixTheme.border_dim,
        highlightcolor=MatrixTheme.border,
        highlightthickness=1,
    )


def make_checkbutton(
    parent: tk.Misc,
    text: str,
    variable: tk.BooleanVar,
) -> tk.Checkbutton:
    return tk.Checkbutton(
        parent,
        text=text,
        variable=variable,
        font=MatrixTheme.body_font,
        fg=MatrixTheme.text,
        bg=MatrixTheme.panel,
        activeforeground=MatrixTheme.accent,
        activebackground=MatrixTheme.panel,
        selectcolor=MatrixTheme.input_bg,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )


def make_text_log(parent: tk.Misc, *, height: int = 8) -> tk.Text:
    text = tk.Text(
        parent,
        height=height,
        font=MatrixTheme.small_font,
        fg=MatrixTheme.text_dim,
        bg=MatrixTheme.input_bg,
        insertbackground=MatrixTheme.accent,
        relief=tk.FLAT,
        bd=0,
        highlightbackground=MatrixTheme.border_dim,
        highlightcolor=MatrixTheme.border,
        highlightthickness=1,
        wrap=tk.WORD,
    )

    text.tag_configure("info", foreground=MatrixTheme.text_dim)
    text.tag_configure("success", foreground=MatrixTheme.accent)
    text.tag_configure("warning", foreground=MatrixTheme.warning)
    text.tag_configure("error", foreground=MatrixTheme.error)
    text.configure(state=tk.DISABLED)

    return text