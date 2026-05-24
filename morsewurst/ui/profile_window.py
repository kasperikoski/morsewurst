# ============================================================
# morsewurst/ui/profile_window.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import TYPE_CHECKING

from morsewurst.storage.profile_store import (
    DuplicateProfileError,
    LastProfileError,
    ProfileError,
)

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class ProfileWindow(tk.Toplevel):
    """Window for managing local user profiles."""

    def __init__(self, app: "MorsewurstApp") -> None:
        super().__init__(app)

        self.withdraw()

        self.app = app
        self.status_var = tk.StringVar(value="")
        self.tree: ttk.Treeview

        self.title(app.i18n.t("profiles.window.title"))
        self.geometry("620x430")
        self.minsize(580, 380)
        self.transient(app)

        self.protocol("WM_DELETE_WINDOW", self.close)

        self._build_ui()
        self.refresh_profiles()
        self._center_on_parent()

        self.deiconify()
        self.lift()
        self.focus_force()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            root,
            text=self.app.i18n.t("profiles.window.description"),
            wraplength=560,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 10))

        self.tree = ttk.Treeview(
            root,
            columns=("name", "status"),
            show="headings",
            selectmode="browse",
            height=9,
        )

        self.tree.heading("name", text=self.app.i18n.t("profiles.column.name"))
        self.tree.heading("status", text=self.app.i18n.t("profiles.column.status"))

        self.tree.column("name", width=360, anchor=tk.W)
        self.tree.column("status", width=150, anchor=tk.W)

        self.tree.pack(fill=tk.BOTH, expand=True)

        button_row = ttk.Frame(root)
        button_row.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(
            button_row,
            text=self.app.i18n.t("profiles.button.use"),
            command=self.use_selected_profile,
        ).pack(side=tk.LEFT)

        ttk.Button(
            button_row,
            text=self.app.i18n.t("profiles.button.add"),
            command=self.add_profile,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            button_row,
            text=self.app.i18n.t("profiles.button.rename"),
            command=self.rename_profile,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            button_row,
            text=self.app.i18n.t("profiles.button.delete"),
            command=self.delete_profile,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            button_row,
            text=self.app.i18n.t("profiles.button.close"),
            command=self.close,
        ).pack(side=tk.RIGHT)

        ttk.Label(
            root,
            textvariable=self.status_var,
            wraplength=560,
        ).pack(fill=tk.X, pady=(10, 0))

    def refresh_profiles(self) -> None:
        self.tree.delete(*self.tree.get_children())

        active_id = self.app.profile_controller.active_profile_id()

        for profile in self.app.profile_controller.list_profiles():
            status = (
                self.app.i18n.t("profiles.status.active")
                if profile.id == active_id
                else ""
            )

            self.tree.insert(
                "",
                tk.END,
                iid=profile.id,
                values=(profile.name, status),
            )

        if active_id:
            try:
                self.tree.selection_set(active_id)
                self.tree.focus(active_id)
            except Exception:
                pass

    def selected_profile_id(self) -> str:
        selected = self.tree.selection()

        if not selected:
            messagebox.showinfo(
                self.app.i18n.t("profiles.window.title"),
                self.app.i18n.t("profiles.message.select_first"),
                parent=self,
            )
            return ""

        return str(selected[0])

    def add_profile(self) -> None:
        name = simpledialog.askstring(
            self.app.i18n.t("profiles.add.title"),
            self.app.i18n.t("profiles.add.prompt"),
            parent=self,
        )

        if name is None:
            return

        try:
            profile = self.app.profile_controller.create_profile(name)
        except DuplicateProfileError:
            messagebox.showerror(
                self.app.i18n.t("profiles.window.title"),
                self.app.i18n.t("profiles.error.duplicate"),
                parent=self,
            )
            return
        except ProfileError as exc:
            messagebox.showerror(
                self.app.i18n.t("profiles.window.title"),
                str(exc),
                parent=self,
            )
            return

        self.refresh_profiles()
        self.tree.selection_set(profile.id)
        self.tree.focus(profile.id)
        self.status_var.set(
            self.app.i18n.t("profiles.status.created", name=profile.name)
        )

    def use_selected_profile(self) -> None:
        profile_id = self.selected_profile_id()

        if not profile_id:
            return

        if self.app.profile_controller.is_active_profile(profile_id):
            self.status_var.set(self.app.i18n.t("profiles.status.already_active"))
            return

        profile = self.app.profile_controller.activate_profile(profile_id)
        self.refresh_profiles()

        self._show_restart_now_dialog(profile.name)

        self.app.app_lifecycle_controller.restart_application()

    def rename_profile(self) -> None:
        profile_id = self.selected_profile_id()

        if not profile_id:
            return

        if self.app.profile_controller.is_active_profile(profile_id):
            messagebox.showwarning(
                self.app.i18n.t("profiles.window.title"),
                self.app.i18n.t("profiles.error.active_rename_blocked"),
                parent=self,
            )
            return

        current_name = self.tree.set(profile_id, "name")

        new_name = simpledialog.askstring(
            self.app.i18n.t("profiles.rename.title"),
            self.app.i18n.t("profiles.rename.prompt"),
            initialvalue=current_name,
            parent=self,
        )

        if new_name is None:
            return

        try:
            profile = self.app.profile_controller.rename_profile(profile_id, new_name)
        except DuplicateProfileError:
            messagebox.showerror(
                self.app.i18n.t("profiles.window.title"),
                self.app.i18n.t("profiles.error.duplicate"),
                parent=self,
            )
            return
        except ProfileError as exc:
            messagebox.showerror(
                self.app.i18n.t("profiles.window.title"),
                str(exc),
                parent=self,
            )
            return

        self.refresh_profiles()
        self.tree.selection_set(profile.id)
        self.tree.focus(profile.id)
        self.status_var.set(
            self.app.i18n.t("profiles.status.renamed", name=profile.name)
        )

    def delete_profile(self) -> None:
        profile_id = self.selected_profile_id()

        if not profile_id:
            return

        if self.app.profile_controller.is_active_profile(profile_id):
            messagebox.showwarning(
                self.app.i18n.t("profiles.window.title"),
                self.app.i18n.t("profiles.error.active_delete_blocked"),
                parent=self,
            )
            return

        profile_name = self.tree.set(profile_id, "name")

        confirmed = messagebox.askyesno(
            self.app.i18n.t("profiles.delete.title"),
            self.app.i18n.t("profiles.delete.confirm", name=profile_name),
            parent=self,
        )

        if not confirmed:
            return

        try:
            backup_path = self.app.profile_controller.delete_profile(profile_id)
        except LastProfileError:
            messagebox.showerror(
                self.app.i18n.t("profiles.window.title"),
                self.app.i18n.t("profiles.error.last_profile"),
                parent=self,
            )
            return
        except ProfileError as exc:
            messagebox.showerror(
                self.app.i18n.t("profiles.window.title"),
                str(exc),
                parent=self,
            )
            return

        self.refresh_profiles()

        messagebox.showinfo(
            self.app.i18n.t("profiles.window.title"),
            self.app.i18n.t(
                "profiles.delete.done",
                name=profile_name,
                path=str(backup_path),
            ),
            parent=self,
        )

        self.status_var.set(
            self.app.i18n.t("profiles.status.deleted", name=profile_name)
        )

    def _show_restart_now_dialog(self, profile_name: str) -> None:
        dialog = tk.Toplevel(self)
        dialog.withdraw()

        dialog.title(self.app.i18n.t("profiles.window.title"))
        self.app.window_controller.apply_window_icon(dialog)
        
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill=tk.BOTH, expand=True)

        message = self.app.i18n.t(
            "profiles.message.selected_restart_now",
            name=profile_name,
        )

        ttk.Label(
            frame,
            text=message,
            wraplength=360,
            justify=tk.CENTER,
        ).pack(fill=tk.X, pady=(0, 16))

        ok_button = ttk.Button(
            frame,
            text="OK",
            command=dialog.destroy,
        )
        ok_button.pack(anchor=tk.CENTER)

        dialog.update_idletasks()

        width = dialog.winfo_reqwidth()
        height = dialog.winfo_reqheight()

        self.update_idletasks()

        x = self.winfo_rootx() + max(0, (self.winfo_width() - width) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - height) // 2)

        dialog.geometry(f"{width}x{height}+{x}+{y}")

        dialog.deiconify()
        dialog.lift()
        dialog.focus_force()
        ok_button.focus_set()

        dialog.wait_window()

    def _center_on_parent(self) -> None:
        self.update_idletasks()

        parent = self.app
        width = max(1, self.winfo_reqwidth())
        height = max(1, self.winfo_reqheight())

        parent.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")

    def close(self) -> None:
        self.app.profile_window = None
        self.destroy()