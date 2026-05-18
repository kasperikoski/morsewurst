# ============================================================
# morsewurst/ui/controllers/debug_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

import tkinter as tk
from tkinter import messagebox

import morsewurst.config as config
from morsewurst.core.debug_snapshot import (
    build_round_debug_snapshot,
    clear_debug_files,
    read_latest_debug_text,
    write_debug_snapshot,
)

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class DebugController:
    """Owns debug snapshot writing, copying and clearing."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def write_round_snapshot_if_enabled(self) -> None:
        """Write the latest completed round debug snapshot when debug capture is enabled."""
        if not self._snapshot_enabled():
            return

        app = self.app
        decoder = app.decoder_controller

        try:
            current_time_us = decoder.adaptive_current_device_time_us()

            decoded = decoder.decode_tone_events(
                app.round.events,
                current_time_us=current_time_us,
                flush_final=True,
                seed_unit_us=decoder.adaptive_seed_unit_us(),
            )

            snapshot = build_round_debug_snapshot(
                app=app,
                round_state=app.round,
                decoded=decoded,
                summary=app.last_summary,
                char_results=app.last_char_results,
                current_time_us=current_time_us,
            )

            write_debug_snapshot(
                snapshot,
                save_latest=True,
                save_history=self._save_history_enabled(),
            )

        except Exception as exc:
            app.status_controller.set_main_status(
                f"Debug-datan tallennus epäonnistui: {exc}",
                state="warning",
            )

    def copy_latest_snapshot(self) -> None:
        """Copy the latest debug snapshot JSON text to the clipboard."""
        content = read_latest_debug_text().rstrip()

        if not content:
            messagebox.showinfo(
                config.APP_NAME,
                "Viimeisintä debug-snapshotia ei löytynyt.",
                parent=self.app,
            )
            return

        self.app.clipboard_clear()
        self.app.clipboard_append(content)
        self.app.status_var.set("Viimeisin debug-snapshot kopioitu leikepöydälle.")

    def clear_snapshots(self) -> None:
        """Delete latest debug snapshot and debug history after confirmation."""
        ok = messagebox.askyesno(
            config.APP_NAME,
            "Haluatko varmasti tyhjentää debug-datan?\n\n"
            "Tämä poistaa latest_round_debug.json- ja debug_history.jsonl-tiedostot.",
            parent=self.app,
        )

        if not ok:
            return

        deleted = clear_debug_files()
        self.app.status_var.set(f"Debug-data tyhjennetty. Poistettuja tiedostoja: {deleted}.")

        self.refresh_debug_window_if_open()

    def refresh_debug_window_if_open(self) -> None:
        """Reload the visible debug window when it is currently open."""
        window = self.app.window_controller.existing_window_or_none("debug_window")

        if window is None:
            return

        try:
            window.load_latest()
        except Exception:
            pass

    def _snapshot_enabled(self) -> bool:
        """Return True when round debug snapshot writing is enabled."""
        try:
            return bool(self.app.debug_snapshot_enabled_var.get())
        except Exception:
            return bool(getattr(config, "DEBUG_SNAPSHOT_ENABLED_DEFAULT", False))

    def _save_history_enabled(self) -> bool:
        """Return True when debug snapshots should also be appended to history."""
        try:
            return bool(self.app.debug_snapshot_save_history_var.get())
        except Exception:
            return bool(getattr(config, "DEBUG_SNAPSHOT_SAVE_HISTORY_DEFAULT", True))