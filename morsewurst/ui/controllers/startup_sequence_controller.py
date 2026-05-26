# ============================================================
# morsewurst/ui/controllers/startup_sequence_controller.py
# ============================================================

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

import tkinter as tk

import morsewurst.config as config
from morsewurst.core.logging_service import setup_logging
from morsewurst.core.app_logging import log_app_event, log_app_exception

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class StartupSequenceController:
    """Owns the application startup sequence and startup error recovery."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def run_startup(self) -> None:
        """Run the full startup sequence from splash screen to ready UI."""
        app = self.app

        startup = app.startup_controller
        lifecycle = app.app_lifecycle_controller
        runtime = app.runtime_controller
        settings = app.settings_controller
        decoder = app.decoder_controller
        layout = app.layout_controller
        wxmor = app.wxmor_controller
        serial = app.serial_controller
        history = app.history_controller
        practice = app.practice_controller

        app.withdraw()
        self.init_startup_state()
        active_profile = app.profile_controller.prepare_active_profile()

        if active_profile is not None:
            setup_logging(config.DATA_DIR)
            log_app_event(
                "app.logging.ready",
                message="Application logging configured.",
                context={
                    "data_dir": str(config.DATA_DIR),
                    "profile_id": active_profile.id,
                    "profile_name": active_profile.name,
                },
            )

        self.preload_language_for_startup()
        startup.show_startup_screen()

        try:
            startup_started_at = time.perf_counter()

            log_app_event(
                "app.startup.started",
                message="Application startup sequence started.",
                context={
                    "app_version": getattr(config, "APP_VERSION", ""),
                    "data_dir": str(config.DATA_DIR),
                    "profile_id": getattr(active_profile, "id", ""),
                    "profile_name": getattr(active_profile, "name", ""),
                },
            )

            log_app_event("app.startup.step_started", context={"step": "configure_window", "progress": 5})
            startup.startup_status(app.i18n.t("app.startup.preparing_window"), 5)
            lifecycle.configure_window()
            startup.startup_delay(0.15)
            log_app_event("app.startup.step_completed", context={"step": "configure_window"})

            log_app_event("app.startup.step_started", context={"step": "init_services", "progress": 15})
            startup.startup_status(app.i18n.t("app.startup.opening_database"), 15)
            lifecycle.init_services()
            startup.startup_delay(0.20)
            log_app_event("app.startup.step_completed", context={"step": "init_services"})

            log_app_event("app.startup.step_started", context={"step": "init_runtime", "progress": 28})
            startup.startup_status(app.i18n.t("app.startup.initializing_app"), 28)
            runtime.init_runtime_state()
            runtime.init_variables()
            startup.startup_delay(0.20)
            log_app_event("app.startup.step_completed", context={"step": "init_runtime"})

            log_app_event("app.startup.step_started", context={"step": "load_ui_settings", "progress": 40})
            startup.startup_status(app.i18n.t("app.startup.loading_settings"), 40)
            settings.load_ui_settings()
            startup.startup_delay(0.20)
            log_app_event("app.startup.step_completed", context={"step": "load_ui_settings"})

            log_app_event("app.startup.step_started", context={"step": "refresh_timing_profiles", "progress": 52})
            startup.startup_status(app.i18n.t("app.startup.loading_timing_profiles"), 52)
            decoder.refresh_timing_profiles()
            startup.startup_delay(0.20)
            log_app_event("app.startup.step_completed", context={"step": "refresh_timing_profiles"})

            log_app_event("app.startup.step_started", context={"step": "build_ui", "progress": 66})
            startup.startup_status(app.i18n.t("app.startup.building_ui"), 66)
            layout.build_ui()
            wxmor.update_practice_state()
            runtime.bind_static_events()
            startup.startup_delay(0.35)
            log_app_event("app.startup.step_completed", context={"step": "build_ui"})

            log_app_event("app.startup.step_started", context={"step": "refresh_serial_ports", "progress": 78})
            startup.startup_status(app.i18n.t("app.startup.checking_serial_ports"), 78)
            serial.refresh_ports()
            startup.startup_delay(0.20)
            log_app_event("app.startup.step_completed", context={"step": "refresh_serial_ports"})

            log_app_event("app.startup.step_started", context={"step": "load_history_tables", "progress": 88})
            startup.startup_status(app.i18n.t("app.startup.loading_practice_data"), 88)
            history.load_tables()
            startup.startup_delay(0.15)
            log_app_event("app.startup.step_completed", context={"step": "load_history_tables"})

            log_app_event("app.startup.step_started", context={"step": "load_keying_event_summary", "progress": 93})
            startup.startup_status(app.i18n.t("app.startup.loading_keying_statistics"), 93)
            history.load_keying_event_summary_for_startup()
            startup.startup_delay(0.15)
            log_app_event("app.startup.step_completed", context={"step": "load_keying_event_summary"})

            log_app_event("app.startup.step_started", context={"step": "finish_startup", "progress": 97})
            startup.startup_status(app.i18n.t("app.startup.finishing"), 97)
            practice.update_practice_buttons()
            runtime.start_timers()
            log_app_event("app.startup.step_completed", context={"step": "finish_startup"})

            startup.startup_wait_until_minimum(
                startup_started_at,
                minimum_seconds=3.0,
            )

            startup.startup_status(app.i18n.t("app.startup.ready"), 100)
            startup.startup_delay(1.0)

            startup.finish_startup_screen()

            log_app_event(
                "app.startup.completed",
                message="Application startup sequence completed.",
                context={
                    "duration_seconds": round(time.perf_counter() - startup_started_at, 3),
                    "initial_profile_setup_required": bool(app.profile_controller.initial_profile_setup_required),
                },
            )

            if app.profile_controller.initial_profile_setup_required:
                app.after(300, app.profile_controller.open_initial_profile_window)
            else:
                app.update_controller.check_for_updates_after_startup()

        except Exception as exc:
            log_app_exception(
                "app.startup.failed",
                exc,
                message="Application startup sequence failed.",
            )
            self.recover_from_startup_error()
            raise

    def preload_language_for_startup(self) -> None:
        """Load the saved UI language before the first startup status is shown."""
        app = self.app
        settings = app.settings_controller

        try:
            data = settings.read_ui_settings_file()
            language = settings.language_from_data(data)
            app.i18n.set_language(language)
        except Exception as exc:
            log_app_exception(
                "app.i18n.language_file_failed",
                exc,
                level="warning",
                message="Startup language preload failed.",
            )

    def init_startup_state(self) -> None:
        """Initialise splash screen state before the startup screen is shown."""
        app = self.app

        app.startup_screen: Optional[tk.Toplevel] = None
        app.startup_canvas: Optional[tk.Canvas] = None
        app.startup_image: Optional[tk.PhotoImage] = None
        app.startup_status_text = "Käynnistetään..."
        app.startup_progress_percent = 0.0
        app.startup_started_at = time.monotonic()

    def recover_from_startup_error(self) -> None:
        """Destroy the startup screen and reveal the root window if startup fails."""
        app = self.app

        try:
            if app.startup_screen is not None and app.startup_screen.winfo_exists():
                app.startup_screen.destroy()
        except Exception as exc:
            log_app_exception(
                "app.startup.recovery_screen_destroy_failed",
                exc,
                level="warning",
                message="Startup recovery could not destroy the startup screen.",
            )

        app.deiconify()