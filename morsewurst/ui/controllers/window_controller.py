# ============================================================
# morsewurst/ui/controllers/window_controller.py
# ============================================================

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tkinter as tk
from tkinter import messagebox, ttk

import morsewurst.config as config

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class WindowController:
    """Owns opening, focusing and basic lifecycle handling for secondary windows."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def existing_window_or_none(self, attribute: str) -> Any:
        """Return an existing Tk window stored on app, or clear the stale reference."""
        window = getattr(self.app, attribute, None)

        if window is None:
            return None

        try:
            if window.winfo_exists():
                return window
        except Exception:
            pass

        setattr(self.app, attribute, None)
        return None

    def raise_existing_window(self, attribute: str) -> bool:
        """Bring an already-open window to front when it exists."""
        window = self.existing_window_or_none(attribute)

        if window is None:
            return False

        try:
            window.lift()
            window.focus_force()
        except Exception:
            pass

        return True

    def apply_window_icon(self, window: tk.Misc) -> None:
        """Apply the Morsewurst .ico icon to a Tk or Toplevel window when available."""
        icon_path = self._window_icon_path()

        if icon_path is None:
            return

        try:
            if icon_path.exists():
                window.iconbitmap(str(icon_path))
        except Exception:
            pass

    def _window_icon_path(self) -> Path | None:
        """Return the configured runtime window icon path."""
        configured_icon = getattr(config, "APP_WINDOW_ICON", None)

        if configured_icon is not None:
            try:
                return Path(configured_icon)
            except Exception:
                pass

        try:
            return config.resource_path("Assets/morse.ico")
        except Exception:
            return None

    def open_debug_window(self) -> None:
        """Open the debug-data window, or focus it if it is already open."""
        if self.raise_existing_window("debug_window"):
            return

        from morsewurst.ui.debug_window import DebugWindow

        self.app.debug_window = DebugWindow(self.app)
        self.apply_window_icon(self.app.debug_window)

    def open_delete_sessions_window(self) -> None:
        """Open the database cleanup window for deleting saved practice sessions."""
        window = DeleteSessionsWindow(self.app)
        self.apply_window_icon(window)

    def open_advanced_settings(self) -> None:
        """Open the advanced settings window."""
        from morsewurst.ui.advanced_settings_window import AdvancedSettingsWindow

        window = AdvancedSettingsWindow(self.app)
        self.apply_window_icon(window)

    def open_profile_window(self) -> None:
        """Open the local user profile window, or focus it if it is already open."""
        if self.raise_existing_window("profile_window"):
            return

        from morsewurst.ui.profile_window import ProfileWindow

        self.app.profile_window = ProfileWindow(self.app)
        self.apply_window_icon(self.app.profile_window)

    def open_help(self) -> None:
        """Open the help window."""
        from morsewurst.ui.help_window import HelpWindow

        window = HelpWindow(self.app)
        self.apply_window_icon(window)

    def open_stats_window(self) -> None:
        """Open the statistics window, or focus it if it is already open."""
        if self.raise_existing_window("stats_window"):
            return

        from morsewurst.ui.stats_window import StatsWindow

        self.app.stats_window = StatsWindow(self.app)
        self.apply_window_icon(self.app.stats_window)

    def open_network_window(self) -> None:
        """Open the network lobby window, or focus it if it is already open."""
        if self.raise_existing_window("network_window"):
            return

        from morsewurst.ui.network import NetworkLobbyWindow

        self.app.network_window = NetworkLobbyWindow(self.app)
        self.apply_window_icon(self.app.network_window)

    def close_known_windows(self) -> None:
        """Best-effort close for known secondary windows."""
        for attribute in (
            "debug_window",
            "stats_window",
            "network_window",
            "profile_window",
        ):
            window = self.existing_window_or_none(attribute)

            if window is None:
                continue

            try:
                window.destroy()
            except Exception:
                pass

            setattr(self.app, attribute, None)


class DeleteSessionsWindow(tk.Toplevel):
    """Window for deleting saved practice sessions from the local database."""

    def __init__(self, app: "MorsewurstApp") -> None:
        super().__init__(app)

        self.withdraw()

        self.app = app
        self.status_var = tk.StringVar(value="")
        self.start_date_var: tk.StringVar
        self.start_time_var: tk.StringVar
        self.end_date_var: tk.StringVar
        self.end_time_var: tk.StringVar
        self.tree: ttk.Treeview

        self._configure_window()
        self._build_ui()
        self.refresh_list()
        self._center_on_parent()

        self.deiconify()
        self.lift()
        self.focus_force()

        try:
            self.grab_set()
        except tk.TclError:
            pass

    def tr(self, translation_key: str, default: str | None = None, **values: Any) -> str:
        return self.app.i18n.t(translation_key, default, **values)

    def _configure_window(self) -> None:
        """Configure the delete-sessions window shell."""
        self.title(self.tr("delete_sessions.window.title", "Delete practice sessions"))

        try:
            self.app.window_controller.apply_window_icon(self)
        except Exception:
            pass

        self.transient(self.app)
        self.geometry("900x620")

    def _build_ui(self) -> None:
        """Build all visible controls for the delete-sessions window."""
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text=self.tr("delete_sessions.window.title", "Delete practice sessions"),
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            outer,
            text=self.tr(
                "delete_sessions.description",
                "You can delete all saved practice sessions or choose a time range. Deletion affects the database directly and also removes telemetry and character results related to the sessions.",
            ),
            wraplength=840,
        ).pack(anchor=tk.W, pady=(4, 12))

        self._build_session_list(outer)
        self._build_range_controls(outer)

        ttk.Label(
            outer,
            textvariable=self.status_var,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(8, 0))

        self._build_buttons(outer)

    def _build_session_list(self, parent: tk.Misc) -> None:
        """Build the table containing recent saved practice sessions."""
        list_frame = ttk.LabelFrame(
            parent,
            text=self.tr("delete_sessions.saved_sessions", "Saved practice sessions"),
        )
        list_frame.pack(fill=tk.BOTH, expand=True)

        inner = ttk.Frame(list_frame)
        inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        inner.columnconfigure(0, weight=1)
        inner.rowconfigure(0, weight=1)

        columns = (
            "id",
            "finished",
            "accuracy",
            "cleanliness",
            "score",
            "errors",
            "time",
            "entered",
            "target",
        )

        self.tree = ttk.Treeview(
            inner,
            columns=columns,
            show="headings",
            height=getattr(config, "DELETE_SESSIONS_VISIBLE_ROWS", 14),
        )

        for col, title, width in [
            ("id", self.tr("delete_sessions.column.id", "ID"), 55),
            ("finished", self.tr("delete_sessions.column.finished", "Time"), 150),
            ("accuracy", self.tr("delete_sessions.column.accuracy", "Accuracy"), 85),
            ("cleanliness", self.tr("delete_sessions.column.cleanliness", "Cleanliness"), 85),
            ("score", self.tr("delete_sessions.column.score", "Score"), 75),
            ("errors", self.tr("delete_sessions.column.errors", "Errors"), 70),
            ("time", self.tr("delete_sessions.column.duration", "Duration"), 75),
            ("entered", self.tr("delete_sessions.column.entered", "Input"), 170),
            ("target", self.tr("delete_sessions.column.target", "Target"), 170),
        ]:
            self.tree.heading(col, text=title, anchor=tk.W)
            self.tree.column(col, width=width, anchor=tk.W, stretch=False)

        scroll_y = ttk.Scrollbar(inner, orient=tk.VERTICAL, command=self.tree.yview)
        scroll_x = ttk.Scrollbar(inner, orient=tk.HORIZONTAL, command=self.tree.xview)

        self.tree.configure(
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<Delete>", lambda _event: self.delete_selected())

    def _build_range_controls(self, parent: tk.Misc) -> None:
        """Build date and time fields for range deletion."""
        frame = ttk.LabelFrame(
            parent,
            text=self.tr("delete_sessions.range.title", "Delete by time range"),
        )
        frame.pack(fill=tk.X, pady=(12, 0))

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        self.start_date_var = tk.StringVar(value=today_start.strftime("%d.%m.%Y"))
        self.start_time_var = tk.StringVar(value=today_start.strftime("%H:%M"))
        self.end_date_var = tk.StringVar(value=now.strftime("%d.%m.%Y"))
        self.end_time_var = tk.StringVar(value=now.strftime("%H:%M"))

        grid = ttk.Frame(frame)
        grid.pack(fill=tk.X, padx=8, pady=8)

        fields = [
            (self.tr("delete_sessions.range.start_date", "Start date"), self.start_date_var, 12),
            (self.tr("delete_sessions.range.time", "Time"), self.start_time_var, 8),
            (self.tr("delete_sessions.range.end_date", "End date"), self.end_date_var, 12),
            (self.tr("delete_sessions.range.time", "Time"), self.end_time_var, 8),
        ]

        column = 0
        for label, variable, width in fields:
            ttk.Label(grid, text=label).grid(row=0, column=column, sticky=tk.W)
            ttk.Entry(
                grid,
                textvariable=variable,
                width=width,
            ).grid(row=0, column=column + 1, padx=(6, 14 if column < 6 else 0))
            column += 2

    def _build_buttons(self, parent: tk.Misc) -> None:
        """Build action buttons for refresh, counting and deletion."""
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(12, 0))

        ttk.Button(
            row,
            text=self.tr("delete_sessions.button.refresh", "Refresh list"),
            command=self.refresh_list,
        ).pack(side=tk.LEFT)

        ttk.Button(
            row,
            text=self.tr("delete_sessions.button.count_range", "Count range"),
            command=self.update_range_count,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            row,
            text=self.tr("delete_sessions.button.delete_selected", "Delete selected"),
            command=self.delete_selected,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            row,
            text=self.tr("delete_sessions.button.delete_range", "Delete range"),
            command=self.delete_range,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            row,
            text=self.tr("delete_sessions.button.delete_all", "Delete all"),
            command=self.delete_all,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            row,
            text=self.tr("delete_sessions.button.close", "Close"),
            command=self.destroy,
        ).pack(side=tk.RIGHT)

    def refresh_list(self) -> None:
        """Reload the newest saved practice sessions into the table."""
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        try:
            rows = self.app.db.sessions_for_management(1000)
        except Exception as exc:
            self.status_var.set(
                self.tr(
                    "delete_sessions.status.load_failed",
                    "Loading the list failed: {error}",
                    error=str(exc),
                )
            )
            return

        for row in rows:
            self.tree.insert("", tk.END, values=self._row_values(row))

        total = self.app.db.count_sessions_for_delete()
        self.status_var.set(
            self.tr(
                "delete_sessions.status.total",
                "The database contains {total} practice sessions. The list shows at most the 1000 newest sessions.",
                total=total,
            )
        )

    def _row_values(self, row: Any) -> tuple[Any, ...]:
        """Convert one database row into visible table values."""
        elapsed_us = self.app.history_controller.row_get(row, "elapsed_us")
        elapsed = "-" if elapsed_us is None else f"{float(elapsed_us) / 1_000_000:.1f}s"

        accuracy = self.app.history_controller.row_get(row, "accuracy")
        cleanliness = self.app.history_controller.row_get(row, "cleanliness")
        score = self.app.history_controller.row_get(row, "overall_score")

        return (
            self.app.history_controller.row_get(row, "id", "-"),
            self.app.history_controller.format_datetime(str(self.app.history_controller.row_get(row, "finished_at", ""))),
            "-" if accuracy is None else f"{float(accuracy):.1f} %",
            "-" if cleanliness is None else f"{float(cleanliness):.1f} %",
            "-" if score is None else f"{float(score):.1f}",
            self.app.history_controller.row_get(row, "error_count", "-"),
            elapsed,
            self.app.history_controller.row_get(row, "entered", ""),
            self.app.history_controller.row_get(row, "target", ""),
        )

    def selected_session_id(self) -> int | None:
        """Return the selected session id from the table."""
        selected_items = self.tree.selection()

        if not selected_items:
            return None

        values = self.tree.item(selected_items[0], "values")

        if not values:
            return None

        try:
            return int(values[0])
        except Exception:
            return None

    def delete_selected(self) -> None:
        """Delete the currently selected practice session."""
        session_id = self.selected_session_id()

        if session_id is None:
            messagebox.showinfo(
                config.APP_NAME,
                self.tr(
                    "delete_sessions.message.select_session_first",
                    "Select a practice session from the list first.",
                ),
                parent=self,
            )
            return

        ok = messagebox.askyesno(
            config.APP_NAME,
            self.tr(
                "delete_sessions.message.confirm_delete_selected",
                "Do you really want to delete the selected practice session?\n\nPractice session ID {session_id}\n\nThis also removes the related telemetry events, character-specific results and skill rating snapshots.\n\nThis action cannot be undone.",
                session_id=session_id,
            ),
            parent=self,
        )

        if not ok:
            return

        try:
            deleted = self.app.db.delete_session_by_id(session_id)
        except Exception as exc:
            messagebox.showerror(
                config.APP_NAME,
                self.tr(
                    "delete_sessions.error.delete_selected_failed",
                    "Deleting the selected practice session failed:\n{error}",
                    error=str(exc),
                ),
                parent=self,
            )
            return

        self.refresh_list()
        self.app.decoder_controller.refresh_timing_profiles()
        self.app.history_controller.load_tables()

        self.status_var.set(
            self.tr(
                "delete_sessions.status.deleted_selected",
                "Deleted practice session ID {session_id}.",
                session_id=session_id,
            )
            if deleted > 0
            else self.tr(
                "delete_sessions.status.selected_not_found",
                "Practice session ID {session_id} was not found.",
                session_id=session_id,
            )
        )

    def parse_range(self) -> tuple[datetime, datetime] | None:
        """Parse the date and time range entered by the user."""
        start_text = f"{self.start_date_var.get().strip()} {self.start_time_var.get().strip()}"
        end_text = f"{self.end_date_var.get().strip()} {self.end_time_var.get().strip()}"

        try:
            start_dt = datetime.strptime(start_text, "%d.%m.%Y %H:%M")
            end_dt = datetime.strptime(end_text, "%d.%m.%Y %H:%M")
        except ValueError:
            messagebox.showerror(
                config.APP_NAME,
                self.tr(
                    "delete_sessions.error.invalid_range",
                    "The time range is not valid.\n\nUse this format:\nDate: dd.mm.yyyy\nTime: HH:MM",
                ),
                parent=self,
            )
            return None

        if end_dt < start_dt:
            messagebox.showerror(
                config.APP_NAME,
                self.tr(
                    "delete_sessions.error.end_before_start",
                    "The end time cannot be before the start time.",
                ),
                parent=self,
            )
            return None

        return start_dt, end_dt

    def delete_all(self) -> None:
        """Delete all saved practice sessions after confirmation."""
        try:
            count = self.app.db.count_sessions_for_delete()
        except Exception as exc:
            messagebox.showerror(
                config.APP_NAME,
                self.tr(
                    "delete_sessions.error.count_failed",
                    "Counting practice sessions failed:\n{error}",
                    error=str(exc),
                ),
                parent=self,
            )
            return

        if count <= 0:
            messagebox.showinfo(
                config.APP_NAME,
                self.tr(
                    "delete_sessions.message.no_sessions_to_delete",
                    "There are no practice sessions to delete in the database.",
                ),
                parent=self,
            )
            return

        ok = messagebox.askyesno(
            config.APP_NAME,
            self.tr(
                "delete_sessions.message.confirm_delete_all",
                "Do you really want to delete all practice sessions?\n\nThis removes {count} practice sessions and their related telemetry and character results.\n\nThis action cannot be undone.",
                count=count,
            ),
            parent=self,
        )

        if not ok:
            return

        try:
            deleted = self.app.db.delete_sessions()
        except Exception as exc:
            messagebox.showerror(
                config.APP_NAME,
                self.tr(
                    "delete_sessions.error.delete_failed",
                    "Deletion failed:\n{error}",
                    error=str(exc),
                ),
                parent=self,
            )
            return

        self.refresh_list()
        self.app.decoder_controller.refresh_timing_profiles()
        self.app.history_controller.load_tables()
        self.status_var.set(
            self.tr(
                "delete_sessions.status.deleted_all",
                "Deleted {count} practice sessions.",
                count=deleted,
            )
        )

    def delete_range(self) -> None:
        """Delete saved practice sessions inside the selected date and time range."""
        parsed = self.parse_range()

        if parsed is None:
            return

        start_dt, end_dt = parsed
        start_iso = start_dt.isoformat(timespec="seconds")
        end_iso = end_dt.isoformat(timespec="seconds")

        try:
            count = self.app.db.count_sessions_for_delete(
                start_at=start_iso,
                end_at=end_iso,
            )
        except Exception as exc:
            messagebox.showerror(
                config.APP_NAME,
                self.tr(
                    "delete_sessions.error.count_failed",
                    "Counting practice sessions failed:\n{error}",
                    error=str(exc),
                ),
                parent=self,
            )
            return

        if count <= 0:
            messagebox.showinfo(
                config.APP_NAME,
                self.tr(
                    "delete_sessions.message.no_sessions_in_range",
                    "No practice sessions to delete were found in the selected time range.",
                ),
                parent=self,
            )
            return

        start_label = start_dt.strftime("%d.%m.%Y %H:%M")
        end_label = end_dt.strftime("%d.%m.%Y %H:%M")

        ok = messagebox.askyesno(
            config.APP_NAME,
            self.tr(
                "delete_sessions.message.confirm_delete_range",
                "Do you really want to delete the practice sessions in the selected time range?\n\nFrom {start}\nTo {end}\n\nThis removes {count} practice sessions and their related telemetry and character results.\n\nThis action cannot be undone.",
                start=start_label,
                end=end_label,
                count=count,
            ),
            parent=self,
        )

        if not ok:
            return

        try:
            deleted = self.app.db.delete_sessions(
                start_at=start_iso,
                end_at=end_iso,
            )
        except Exception as exc:
            messagebox.showerror(
                config.APP_NAME,
                self.tr(
                    "delete_sessions.error.delete_failed",
                    "Deletion failed:\n{error}",
                    error=str(exc),
                ),
                parent=self,
            )
            return

        self.refresh_list()
        self.app.decoder_controller.refresh_timing_profiles()
        self.app.history_controller.load_tables()
        self.status_var.set(
            self.tr(
                "delete_sessions.status.deleted_range",
                "Deleted {count} practice sessions from the selected time range.",
                count=deleted,
            )
        )

    def update_range_count(self) -> None:
        """Show how many sessions match the selected date and time range."""
        parsed = self.parse_range()

        if parsed is None:
            return

        start_dt, end_dt = parsed

        try:
            count = self.app.db.count_sessions_for_delete(
                start_at=start_dt.isoformat(timespec="seconds"),
                end_at=end_dt.isoformat(timespec="seconds"),
            )
        except Exception as exc:
            messagebox.showerror(
                config.APP_NAME,
                self.tr(
                    "delete_sessions.error.count_failed",
                    "Counting practice sessions failed:\n{error}",
                    error=str(exc),
                ),
                parent=self,
            )
            return

        self.status_var.set(
            self.tr(
                "delete_sessions.status.range_count",
                "The time range {start} - {end} contains {count} practice sessions.",
                start=start_dt.strftime("%d.%m.%Y %H:%M"),
                end=end_dt.strftime("%d.%m.%Y %H:%M"),
                count=count,
            )
        )

    def _center_on_parent(self) -> None:
        """Center the window over the main application window."""
        try:
            self.app.update_idletasks()
        except Exception:
            pass

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