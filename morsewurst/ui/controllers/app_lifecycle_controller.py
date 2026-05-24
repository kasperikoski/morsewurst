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
            getattr(config, "UI_MIN_HEIGHT", 740),
        )
        app.protocol("WM_DELETE_WINDOW", self.on_close)
        app.window_controller.apply_window_icon(app)

    def init_services(self) -> None:
        """Initialise persistent services and hardware readers."""
        app = self.app

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

    def restart_application(self) -> None:
        """Restart the current Morsewurst process."""

        app = self.app

        app.audio_controller.stop_morse_speed_preview()

        try:
            app.settings_controller.save_ui_settings()
        except Exception:
            pass

        try:
            app.auto_connect_serial_var.set(False)
        except Exception:
            pass

        try:
            app.serial_reader.disconnect()
        except Exception:
            pass

        try:
            app.network_manager.stop()
        except Exception:
            pass

        if getattr(sys, "frozen", False):
            args = [sys.executable, *sys.argv[1:]]
        else:
            args = [sys.executable, *sys.argv]

        subprocess.Popen(args)
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

        app.audio_controller.stop_morse_speed_preview()
        app.settings_controller.save_ui_settings()

        try:
            app.auto_connect_serial_var.set(False)
        except Exception:
            pass

        try:
            app.serial_reader.disconnect()
        except Exception:
            pass

        try:
            app.network_manager.stop()
        except Exception:
            pass

        app.destroy()