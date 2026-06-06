# ============================================================
# morsewurst/ui/backup_window.py
# ============================================================

from __future__ import annotations

import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tkinter as tk
from tkinter import messagebox, ttk

from morsewurst.core.app_logging import log_app_event, log_app_exception
from morsewurst.storage.backup_service import BackupRecord, BackupService

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class BackupWindow(tk.Toplevel):
    """Profile backup creation and restore window."""

    def __init__(self, app: "MorsewurstApp") -> None:
        super().__init__(app)
        self.withdraw()

        self.app = app
        self.service = self._service_or_raise()
        self.status_var = tk.StringVar(value="")
        self.records: list[BackupRecord] = []
        self.busy = False

        self.title(self.tr("backup.window.title"))
        self.geometry("760x520")
        self.minsize(700, 440)
        self.transient(app)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._build_ui()
        self.refresh_list()
        self._center_on_parent()

        self.deiconify()
        self.lift()
        self.focus_force()

        log_app_event(
            "app.backup.window_opened",
            message="Profile backup window opened.",
            context={"profile_id": self.service.profile_id},
        )

    def tr(self, key: str, default: str | None = None, **values: Any) -> str:
        return self.app.i18n.t(key, default, **values)

    def _service_or_raise(self) -> BackupService:
        service = self.app.backup_controller.service()
        if service is None:
            raise RuntimeError("No active profile is available for backups.")
        return service

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text=self.tr("backup.window.heading"),
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            outer,
            text=self.tr("backup.window.description"),
            wraplength=700,
        ).pack(anchor=tk.W, pady=(4, 10))

        table_frame = ttk.Frame(outer)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("created", "sending", "koch", "reason", "size")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=14,
        )
        self.tree.heading("created", text=self._heading_text(self.tr("backup.column.created")), anchor=tk.W)
        self.tree.heading("sending", text=self._heading_text(self.tr("backup.column.sending")), anchor=tk.W)
        self.tree.heading("koch", text=self._heading_text(self.tr("backup.column.koch")), anchor=tk.W)
        self.tree.heading("reason", text=self._heading_text(self.tr("backup.column.reason")), anchor=tk.W)
        self.tree.heading("size", text=self._heading_text(self.tr("backup.column.size")), anchor=tk.W)

        self.tree.column("created", width=185, stretch=False, anchor=tk.W)
        self.tree.column("sending", width=140, stretch=False, anchor=tk.W)
        self.tree.column("koch", width=130, stretch=False, anchor=tk.W)
        self.tree.column("reason", width=155, stretch=True, anchor=tk.W)
        self.tree.column("size", width=85, stretch=False, anchor=tk.W)

        yscroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_label = ttk.Label(outer, textvariable=self.status_var)
        self.status_label.pack(anchor=tk.W, pady=(8, 0))

        buttons = ttk.Frame(outer)
        buttons.pack(fill=tk.X, pady=(12, 0))

        self.create_button = ttk.Button(
            buttons,
            text=self.tr("backup.button.create"),
            command=self.create_manual_backup,
        )
        self.create_button.pack(side=tk.LEFT)

        self.restore_button = ttk.Button(
            buttons,
            text=self.tr("backup.button.restore"),
            command=self.restore_selected_backup,
        )
        self.restore_button.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            buttons,
            text=self.tr("backup.button.refresh"),
            command=self.refresh_list,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            buttons,
            text=self.tr("backup.button.open_folder"),
            command=self.open_backup_folder,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            buttons,
            text=self.tr("backup.button.close"),
            command=self.destroy,
        ).pack(side=tk.RIGHT)

    def refresh_list(self) -> None:
        self.records = self.service.list_backups()
        self.tree.delete(*self.tree.get_children())

        for index, record in enumerate(self.records):
            self.tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    self._cell_text(self._format_datetime(record.created_at)),
                    self._cell_text(str(record.sending_sessions)),
                    self._cell_text(str(record.koch_sessions)),
                    self._cell_text(self.tr(f"backup.reason.{record.reason}", record.reason)),
                    self._cell_text(self._format_size(record.size_bytes)),
                ),
            )

        if self.records:
            self.status_var.set(self.tr("backup.status.count", count=len(self.records)))
        else:
            self.status_var.set(self.tr("backup.status.empty"))

    def create_manual_backup(self) -> None:
        if self.busy:
            return
        self._set_busy(True, self.tr("backup.status.creating"))

        def worker() -> None:
            try:
                record = self.service.create_backup(reason="manual")
                self.app.after(0, lambda: self._manual_backup_completed(record))
            except Exception as exc:
                self.app.after(0, lambda: self._operation_failed("backup.status.create_failed", exc))

        threading.Thread(target=worker, name="morsewurst-manual-backup", daemon=True).start()

    def _manual_backup_completed(self, record: BackupRecord) -> None:
        self._set_busy(False, self.tr("backup.status.created", name=record.path.name))
        self.refresh_list()

    def restore_selected_backup(self) -> None:
        if self.busy:
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(
                self.tr("backup.message.no_selection.title"),
                self.tr("backup.message.no_selection.body"),
                parent=self,
            )
            return

        record = self.records[int(selection[0])]

        if bool(getattr(self.app, "practice_running", False)) or bool(getattr(self.app.round, "active", False)):
            messagebox.showwarning(
                self.tr("backup.message.practice_active.title"),
                self.tr("backup.message.practice_active.body"),
                parent=self,
            )
            return

        confirmed = messagebox.askyesno(
            self.tr("backup.message.restore_confirm.title"),
            self.tr(
                "backup.message.restore_confirm.body",
                created=self._format_datetime(record.created_at),
                sending=record.sending_sessions,
                koch=record.koch_sessions,
            ),
            parent=self,
        )
        if not confirmed:
            return

        self._set_busy(True, self.tr("backup.status.restoring"))
        self.update_idletasks()

        try:
            self._prepare_for_restore()
            safety = self.service.create_backup(reason="pre_restore", prune=False)
            self._close_database_for_restore()
            self.service.restore_backup(record.path)
            log_app_event(
                "app.backup.restore_restart_required",
                message="Backup restore completed and application restart will be requested.",
                context={
                    "restored_backup": str(record.path),
                    "pre_restore_backup": str(safety.path),
                },
            )
            messagebox.showinfo(
                self.tr("backup.message.restore_done.title"),
                self.tr(
                    "backup.message.restore_done.body",
                    restored=self._format_datetime(record.created_at),
                    safety=safety.path.name,
                ),
                parent=self,
            )
            self._restart_without_saving_settings()
        except Exception as exc:
            self._set_busy(False, self.tr("backup.status.restore_failed"))
            messagebox.showerror(
                self.tr("backup.message.restore_failed.title"),
                self.tr("backup.message.restore_failed.body", error=str(exc)),
                parent=self,
            )

    def _prepare_for_restore(self) -> None:
        try:
            self.app.practice_controller.shutdown_active_practice()
        except Exception as exc:
            log_app_exception(
                "app.backup.restore_shutdown_practice_failed",
                exc,
                level="warning",
                message="Active practice shutdown failed before backup restore.",
            )
        try:
            self.app.practice_controller.shutdown_background_worker(wait_seconds=5.0)
        except Exception as exc:
            log_app_exception(
                "app.backup.restore_background_shutdown_failed",
                exc,
                level="warning",
                message="Practice background worker shutdown failed before backup restore.",
            )
        try:
            self.app.serial_reader.disconnect()
        except Exception:
            pass
        try:
            self.app.network_manager.stop()
        except Exception:
            pass

    def _close_database_for_restore(self) -> None:
        try:
            self.app.db.close()
        except Exception as exc:
            log_app_exception(
                "app.backup.restore_db_close_failed",
                exc,
                level="warning",
                message="Database close failed before backup restore.",
            )

    def _restart_without_saving_settings(self) -> None:
        if getattr(sys, "frozen", False):
            args = [sys.executable, *sys.argv[1:]]
        else:
            args = [sys.executable, *sys.argv]

        subprocess.Popen(args)
        self.app.destroy()

    def _operation_failed(self, status_key: str, exc: Exception) -> None:
        log_app_exception(
            "app.backup.window_operation_failed",
            exc,
            message="Backup window operation failed.",
            context={"status_key": status_key},
        )
        self._set_busy(False, self.tr(status_key, error=str(exc)))
        messagebox.showerror(
            self.tr("backup.message.error.title"),
            self.tr("backup.message.error.body", error=str(exc)),
            parent=self,
        )

    def open_backup_folder(self) -> None:
        path = self.service.backups_dir
        path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            self._operation_failed("backup.status.open_folder_failed", exc)

    def _set_busy(self, busy: bool, status: str) -> None:
        self.busy = bool(busy)
        self.status_var.set(status)
        state = tk.DISABLED if busy else tk.NORMAL
        self.create_button.configure(state=state)
        self.restore_button.configure(state=state)

    def _heading_text(self, value: str) -> str:
        return f"  {value}"

    def _cell_text(self, value: str) -> str:
        return f"  {value}"

    def _format_datetime(self, value: str) -> str:
        text = str(value or "").strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
            return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return value or "-"

    def _format_size(self, size_bytes: int) -> str:
        value = float(max(0, int(size_bytes)))
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024.0 or unit == "GB":
                if unit == "B":
                    return f"{int(value)} {unit}"
                return f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{value:.1f} GB"

    def _center_on_parent(self) -> None:
        self.update_idletasks()
        parent = self.app
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
