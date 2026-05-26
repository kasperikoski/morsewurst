# ============================================================
# morsewurst/ui/debug_window.py
# ============================================================

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

import morsewurst.config as config
from morsewurst.core.app_logging import log_app_event, log_app_exception
from morsewurst.core.debug_snapshot import (
    clear_debug_files,
    debug_dir_path,
    read_history_debug_text,
    read_latest_debug_text,
)


class DebugWindow(tk.Toplevel):
    def __init__(self, app: tk.Misc) -> None:
        super().__init__(app)

        self.app = app
        self.mode_var = tk.StringVar(value="latest")
        self.status_var = tk.StringVar(value="")

        self.title(self.app.i18n.t("debug_window.title"))
        self.transient(app)
        self.geometry("1100x760")
        self.minsize(850, 560)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.load_latest()
        self._center_on_parent()
        log_app_event(
            "app.debug.window_opened",
            message="Debug window opened.",
        )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text=self.app.i18n.t("debug_window.header"),
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            outer,
            text=self.app.i18n.t("debug_window.description"),
            wraplength=980,
        ).pack(anchor=tk.W, pady=(4, 10))

        button_row = ttk.Frame(outer)
        button_row.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            button_row,
            text=self.app.i18n.t("debug_window.button.show_latest"),
            command=self.load_latest,
        ).pack(side=tk.LEFT)

        ttk.Button(
            button_row,
            text=self.app.i18n.t("debug_window.button.show_history_pretty"),
            command=self.load_history_pretty,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            button_row,
            text=self.app.i18n.t("debug_window.button.show_history_raw"),
            command=self.load_history_raw,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            button_row,
            text=self.app.i18n.t("debug_window.button.copy_visible"),
            command=self.copy_visible_text,
        ).pack(side=tk.LEFT, padx=(18, 0))

        ttk.Button(
            button_row,
            text=self.app.i18n.t("debug_window.button.copy_latest"),
            command=self.copy_latest,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            button_row,
            text=self.app.i18n.t("debug_window.button.open_folder"),
            command=self.open_debug_folder,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            button_row,
            text=self.app.i18n.t("debug_window.button.clear_data"),
            command=self.clear_debug_data,
        ).pack(side=tk.LEFT, padx=(18, 0))

        ttk.Button(
            button_row,
            text=self.app.i18n.t("debug_window.button.close"),
            command=self.close,
        ).pack(side=tk.RIGHT)

        text_frame = ttk.Frame(outer)
        text_frame.pack(fill=tk.BOTH, expand=True)

        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame,
            wrap=tk.NONE,
            undo=False,
            font=("Consolas", 10),
        )

        scrollbar_y = ttk.Scrollbar(
            text_frame,
            orient=tk.VERTICAL,
            command=self.text.yview,
        )

        scrollbar_x = ttk.Scrollbar(
            text_frame,
            orient=tk.HORIZONTAL,
            command=self.text.xview,
        )

        self.text.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
        )

        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        status_row = ttk.Frame(outer)
        status_row.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(
            status_row,
            textvariable=self.status_var,
            foreground="#666666",
        ).pack(side=tk.LEFT)

    def _center_on_parent(self) -> None:
        try:
            self.update_idletasks()

            x = self.app.winfo_rootx() + max(
                0,
                (self.app.winfo_width() - self.winfo_width()) // 2,
            )
            y = self.app.winfo_rooty() + max(
                0,
                (self.app.winfo_height() - self.winfo_height()) // 2,
            )

            self.geometry(f"+{x}+{y}")

        except Exception:
            pass

    def _set_text(self, content: str) -> None:
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        if content:
            self.text.insert("1.0", content)
        else:
            self.text.insert("1.0", self.app.i18n.t("debug_window.no_data"))

        self.text.configure(state=tk.NORMAL)
        self.text.mark_set(tk.INSERT, "1.0")
        self.text.see("1.0")

    def load_latest(self) -> None:
        self.mode_var.set("latest")
        content = read_latest_debug_text()

        self._set_text(content)
        self.status_var.set(self.app.i18n.t("debug_window.status.showing_latest"))

    def load_history_pretty(self) -> None:
        self.mode_var.set("history_pretty")
        content = read_history_debug_text(pretty=True)

        self._set_text(content)
        self.status_var.set(self.app.i18n.t("debug_window.status.showing_history_pretty"))

    def load_history_raw(self) -> None:
        self.mode_var.set("history_raw")
        content = read_history_debug_text(pretty=False)

        self._set_text(content)
        self.status_var.set(self.app.i18n.t("debug_window.status.showing_history_raw"))

    def copy_visible_text(self) -> None:
        content = self.text.get("1.0", tk.END).rstrip()

        if not content:
            self.status_var.set(self.app.i18n.t("debug_window.status.nothing_to_copy"))
            return

        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_var.set(self.app.i18n.t("debug_window.status.copied_visible"))
        log_app_event(
            "app.debug.visible_copied",
            message="Visible debug window text copied to clipboard.",
            context={"character_count": len(content), "mode": self.mode_var.get()},
        )

    def copy_latest(self) -> None:
        content = read_latest_debug_text().rstrip()

        if not content:
            self.status_var.set(self.app.i18n.t("debug_window.status.no_latest"))
            return

        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_var.set(self.app.i18n.t("debug_window.status.copied_latest"))
        log_app_event(
            "app.debug.latest_copied",
            message="Latest debug snapshot copied from debug window.",
            context={"character_count": len(content)},
        )

    def clear_debug_data(self) -> None:
        log_app_event(
            "app.debug.clear_requested",
            message="Debug data clear requested from debug window.",
        )
        ok = messagebox.askyesno(
            config.APP_NAME,
            self.app.i18n.t("debug_window.confirm_clear"),
            parent=self,
        )

        if not ok:
            log_app_event(
                "app.debug.clear_cancelled",
                message="Debug data clear was cancelled from debug window.",
            )
            return

        deleted = clear_debug_files()
        log_app_event(
            "app.debug.clear_completed",
            message="Debug data cleared from debug window.",
            context={"deleted_count": deleted},
        )

        self._set_text("")
        self.status_var.set(
            self.app.i18n.t("debug_window.status.cleared", deleted=deleted)
        )

    def open_debug_folder(self) -> None:
        path = debug_dir_path()
        path.mkdir(parents=True, exist_ok=True)

        log_app_event(
            "app.debug.folder_open_requested",
            message="Debug folder open requested.",
            context={"path": str(path)},
        )

        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])

        except Exception as exc:
            log_app_exception(
                "app.debug.folder_open_failed",
                exc,
                message="Debug folder could not be opened.",
                context={"path": str(path)},
            )
            messagebox.showerror(
                config.APP_NAME,
                self.app.i18n.t("debug_window.error_open_folder", error=exc),
                parent=self,
            )

    def close(self) -> None:
        try:
            if getattr(self.app, "debug_window", None) is self:
                self.app.debug_window = None
        except Exception:
            pass

        log_app_event(
            "app.debug.window_closed",
            message="Debug window closed.",
        )
        self.destroy()