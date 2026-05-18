# ============================================================
# morsewurst/ui/controllers/startup_sequence_controller.py
# ============================================================

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

import tkinter as tk

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
        startup.show_startup_screen()

        try:
            startup_started_at = time.perf_counter()

            startup.startup_status("Valmistellaan ikkunaa...", 5)
            lifecycle.configure_window()
            startup.startup_delay(0.15)

            startup.startup_status("Avataan tietokantaa...", 15)
            lifecycle.init_services()
            startup.startup_delay(0.20)

            startup.startup_status("Alustetaan sovellusta...", 28)
            runtime.init_runtime_state()
            runtime.init_variables()
            startup.startup_delay(0.20)

            startup.startup_status("Ladataan asetuksia...", 40)
            settings.load_ui_settings()
            startup.startup_delay(0.20)

            startup.startup_status("Ladataan ajoitusprofiileja...", 52)
            decoder.refresh_timing_profiles()
            startup.startup_delay(0.20)

            startup.startup_status("Rakennetaan käyttöliittymää...", 66)
            layout.build_ui()
            wxmor.update_practice_state()
            runtime.bind_static_events()
            startup.startup_delay(0.35)

            startup.startup_status("Tarkistetaan sarjaportit...", 78)
            serial.refresh_ports()
            startup.startup_delay(0.20)

            startup.startup_status("Ladataan harjoitusdataa...", 90)
            history.load_tables()
            startup.startup_delay(0.25)

            startup.startup_status("Viimeistellään...", 97)
            practice.update_practice_buttons()
            runtime.start_timers()

            startup.startup_wait_until_minimum(
                startup_started_at,
                minimum_seconds=3.0,
            )

            startup.startup_status("Valmis", 100)
            startup.startup_delay(1.0)

            startup.finish_startup_screen()
            app.update_controller.check_for_updates_after_startup()

        except Exception:
            self.recover_from_startup_error()
            raise

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
        except Exception:
            pass

        app.deiconify()