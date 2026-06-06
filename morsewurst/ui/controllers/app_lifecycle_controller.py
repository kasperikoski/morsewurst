# ============================================================
# morsewurst/ui/controllers/app_lifecycle_controller.py
# ============================================================

from __future__ import annotations

import queue
import subprocess
import sys
from typing import TYPE_CHECKING, Any, Dict

import tkinter as tk
from tkinter import messagebox

import morsewurst.config as config
from morsewurst.hardware.serial_reader import SerialReader
from morsewurst.storage.database import Database
from morsewurst.core.app_logging import log_app_event, log_app_exception

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class AppLifecycleController:
    """Owns root window setup, core service startup, focus handling and shutdown."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def configure_window(self) -> None:
        """Configure the root Tk window."""
        app = self.app

        profile_name = app.profile_controller.active_profile_name()
        app.title(f"{config.APP_NAME} {config.APP_VERSION} - {profile_name}")
        app.geometry(getattr(config, "UI_WINDOW_GEOMETRY", "1280x830"))
        app.minsize(
            getattr(config, "UI_MIN_WIDTH", 1280),
            getattr(config, "UI_MIN_HEIGHT", 830),
        )
        app.protocol("WM_DELETE_WINDOW", self.on_close)
        app.window_controller.apply_window_icon(app)
        log_app_event(
            "app.window.configured",
            message="Main window configured.",
            context={
                "geometry": getattr(config, "UI_WINDOW_GEOMETRY", ""),
                "min_width": getattr(config, "UI_MIN_WIDTH", None),
                "min_height": getattr(config, "UI_MIN_HEIGHT", None),
                "profile_name": profile_name,
            },
        )

    def init_services(self) -> None:
        """Initialise persistent services and hardware readers."""
        app = self.app

        log_app_event(
            "app.services.init_started",
            message="Application service initialization started.",
            context={"db_path": str(config.DB_PATH)},
        )

        app.db = Database(config.DB_PATH)

        replaced_path = getattr(app.db, "replaced_incompatible_database_path", None)
        if replaced_path is not None:
            messagebox.showwarning(
                config.APP_NAME,
                "Tietokanta ei ollut yhteensopiva tämän Morsewurst-version kanssa.\n\n"
                "Vanhaa tietokantaa ei poistettu, vaan se siirrettiin varmuuskopioksi:\n\n"
                f"{replaced_path}\n\n"
                "Ohjelma loi uuden tyhjän tietokannan.",
            )

        app.event_queue: queue.Queue[Dict[str, Any]] = queue.Queue()
        app.serial_reader = SerialReader(app.event_queue)
        log_app_event(
            "app.services.init_completed",
            message="Application services initialized.",
            context={
                "db_path": str(config.DB_PATH),
                "database_replaced": replaced_path is not None,
                "replaced_path": str(replaced_path) if replaced_path is not None else "",
            },
        )


    def _checkpoint_and_close_database(self, *, reason: str) -> None:
        """Best-effort WAL checkpoint and close for clean shutdown/restart."""

        app = self.app
        db = getattr(app, "db", None)
        if db is None:
            return

        try:
            result = db.checkpoint_wal(truncate=True)
            log_app_event(
                "app.shutdown.database_checkpoint_completed",
                message="Database WAL was checkpointed during clean application shutdown.",
                context={"reason": reason, **result},
            )
        except Exception as exc:
            log_app_exception(
                "app.shutdown.database_checkpoint_failed",
                exc,
                level="warning",
                message="Database WAL checkpoint failed during application shutdown.",
                context={"reason": reason},
            )

        try:
            db.close()
            log_app_event(
                "app.shutdown.database_closed",
                message="Database connection closed during application shutdown.",
                context={"reason": reason},
            )
        except Exception as exc:
            log_app_exception(
                "app.shutdown.database_close_failed",
                exc,
                level="warning",
                message="Database close failed during application shutdown.",
                context={"reason": reason},
            )

    def restart_application(self) -> None:
        """Restart the current Morsewurst process."""

        app = self.app

        log_app_event(
            "app.restart.requested",
            message="Application restart requested.",
            context={"frozen": bool(getattr(sys, "frozen", False))},
        )

        try:
            app.practice_controller.shutdown_active_practice()
        except Exception as exc:
            log_app_exception(
                "app.restart.shutdown_practice_failed",
                exc,
                level="warning",
                message="Active practice shutdown failed during restart.",
            )

        try:
            app.practice_controller.shutdown_background_worker(wait_seconds=5.0)
        except Exception as exc:
            log_app_exception(
                "app.restart.practice_background_shutdown_failed",
                exc,
                level="warning",
                message="Practice background worker shutdown failed during restart.",
            )

        app.audio_controller.stop_morse_speed_preview()

        try:
            app.settings_controller.save_ui_settings()
        except Exception as exc:
            log_app_exception(
                "app.restart.settings_save_failed",
                exc,
                level="warning",
                message="Saving settings during restart failed.",
            )

        try:
            app.auto_connect_serial_var.set(False)
        except Exception:
            pass

        try:
            app.serial_reader.disconnect()
        except Exception as exc:
            log_app_exception(
                "app.restart.serial_disconnect_failed",
                exc,
                level="warning",
                message="Serial disconnect during restart failed.",
            )

        try:
            app.network_manager.stop()
        except Exception as exc:
            log_app_exception(
                "app.restart.network_stop_failed",
                exc,
                level="warning",
                message="Network manager stop during restart failed.",
            )

        self._checkpoint_and_close_database(reason="restart")

        if getattr(sys, "frozen", False):
            args = [sys.executable, *sys.argv[1:]]
        else:
            args = [sys.executable, *sys.argv]

        try:
            subprocess.Popen(args)
            log_app_event(
                "app.restart.spawned",
                message="Replacement application process was spawned.",
                context={"args_count": len(args)},
            )
        except Exception as exc:
            log_app_exception(
                "app.restart.spawn_failed",
                exc,
                message="Application restart process could not be spawned.",
                context={"args_count": len(args)},
            )
            raise

        log_app_event(
            "app.restart.destroying_current_process",
            message="Current application window is closing after restart spawn.",
        )
        app.destroy()

    def focus_input(self, force: bool = False) -> None:
        """Keep the input field focused while a round is active, when enabled."""
        app = self.app

        if not app.keep_focus_var.get() and not force:
            return

        if app.round.active or force:
            try:
                if str(app.input_entry.cget("state")) != "disabled":
                    app.input_entry.focus_set()
            except Exception:
                pass

    def on_close(self) -> None:
        """Stop background activity, save settings and close the application."""
        app = self.app

        log_app_event(
            "app.shutdown.started",
            message="Application shutdown started.",
            context={
                "practice_running": bool(getattr(app, "practice_running", False)),
                "serial_connected": bool(getattr(app, "serial_connected", False)),
            },
        )

        try:
            app.practice_controller.shutdown_active_practice()
        except Exception as exc:
            log_app_exception(
                "app.shutdown.practice_shutdown_failed",
                exc,
                level="warning",
                message="Active practice shutdown failed during application close.",
            )

        try:
            app.practice_controller.shutdown_background_worker(wait_seconds=5.0)
        except Exception as exc:
            log_app_exception(
                "app.shutdown.practice_background_shutdown_failed",
                exc,
                level="warning",
                message="Practice background worker shutdown failed during application close.",
            )

        app.audio_controller.stop_morse_speed_preview()
        try:
            app.settings_controller.save_ui_settings()
        except Exception as exc:
            log_app_exception(
                "app.shutdown.settings_save_failed",
                exc,
                level="warning",
                message="Saving settings during shutdown failed.",
            )

        try:
            app.auto_connect_serial_var.set(False)
        except Exception:
            pass

        try:
            app.serial_reader.disconnect()
        except Exception as exc:
            log_app_exception(
                "app.shutdown.serial_disconnect_failed",
                exc,
                level="warning",
                message="Serial disconnect during shutdown failed.",
            )

        try:
            app.network_manager.stop()
        except Exception as exc:
            log_app_exception(
                "app.shutdown.network_stop_failed",
                exc,
                level="warning",
                message="Network manager stop during shutdown failed.",
            )

        self._checkpoint_and_close_database(reason="close")

        log_app_event(
            "app.shutdown.completed",
            message="Application shutdown completed.",
        )
        app.destroy()