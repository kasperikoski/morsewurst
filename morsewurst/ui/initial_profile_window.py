# ============================================================
# morsewurst/ui/initial_profile_window.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from morsewurst.storage.profile_store import DuplicateProfileError, ProfileError

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class InitialProfileWindow(tk.Toplevel):
    """First-run window for creating the first Morsewurst user profile."""

    def __init__(self, app: "MorsewurstApp") -> None:
        super().__init__(app)

        self.withdraw()

        self.app = app
        self.name_var = tk.StringVar(value="")

        self.title(app.i18n.t("profiles.initial_setup.title"))

        self.window_width = 460
        self.window_height = 180

        self.geometry(f"{self.window_width}x{self.window_height}")
        self.minsize(self.window_width, self.window_height)
        self.maxsize(self.window_width, self.window_height)
        self.resizable(False, False)

        self.transient(app)

        self.protocol("WM_DELETE_WINDOW", self.block_close)

        self._build_ui()
        self._center_on_parent()

        self.deiconify()
        self.lift()
        self.focus_force()

        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=18)
        root.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            root,
            text=self.app.i18n.t("profiles.initial_setup.description"),
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 14))

        ttk.Label(
            root,
            text=self.app.i18n.t("profiles.initial_setup.name_label"),
        ).pack(anchor=tk.W)

        entry_frame = tk.Frame(
            root,
            background="white",
            relief=tk.SOLID,
            borderwidth=1,
        )
        entry_frame.pack(fill=tk.X, pady=(6, 16))

        entry = tk.Entry(
            entry_frame,
            textvariable=self.name_var,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            background="white",
            font=("TkDefaultFont", 11),
        )
        entry.pack(fill=tk.X, padx=(6, 6), pady=(4, 4))
        entry.focus_set()

        ttk.Button(
            root,
            text=self.app.i18n.t("profiles.initial_setup.create_and_restart"),
            command=self.create_profile_and_restart,
        ).pack(anchor=tk.E)

    def create_profile_and_restart(self) -> None:
        name = self.name_var.get().strip()

        if not name:
            messagebox.showwarning(
                self.app.i18n.t("profiles.initial_setup.title"),
                self.app.i18n.t("profiles.initial_setup.name_required"),
                parent=self,
            )
            return

        try:
            profile = self.app.profile_controller.create_first_profile(name)
        except DuplicateProfileError:
            messagebox.showerror(
                self.app.i18n.t("profiles.initial_setup.title"),
                self.app.i18n.t("profiles.error.duplicate"),
                parent=self,
            )
            return
        except ProfileError as exc:
            messagebox.showerror(
                self.app.i18n.t("profiles.initial_setup.title"),
                str(exc),
                parent=self,
            )
            return

        messagebox.showinfo(
            self.app.i18n.t("profiles.initial_setup.title"),
            self.app.i18n.t(
                "profiles.initial_setup.created_restart",
                name=profile.name,
            ),
            parent=self,
        )

        self.app.app_lifecycle_controller.restart_application()

    def block_close(self) -> None:
        should_exit = messagebox.askyesno(
            self.app.i18n.t("profiles.initial_setup.exit_title"),
            self.app.i18n.t("profiles.initial_setup.exit_confirm"),
            parent=self,
        )

        if not should_exit:
            return

        try:
            self.grab_release()
        except tk.TclError:
            pass

        try:
            self.app.initial_profile_window = None
        except Exception:
            pass

        try:
            self.app.app_lifecycle_controller.on_close()
        except Exception:
            self.app.destroy()

    def _center_on_parent(self) -> None:
        self.update_idletasks()

        parent = self.app
        parent.update_idletasks()

        width = self.window_width
        height = self.window_height

        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")