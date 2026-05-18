# ============================================================
# morsewurst/ui/controllers/audio_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

from tkinter import messagebox

import morsewurst.config as config
from morsewurst.core.morse_preview_player import MorsePreviewPlayer

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp

try:
    import winsound
except ImportError:
    winsound = None


class AudioController:
    """Owns UI sound effects and Morse speed preview playback."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app
        self.morse_preview_player = MorsePreviewPlayer()

        # Compatibility for existing code that may still read this attribute.
        self.app.morse_preview_player = self.morse_preview_player

    def sound_event_enabled(self, event_name: str) -> bool:
        app = self.app

        try:
            if not app.sound_enabled_var.get():
                return False
        except Exception:
            return False

        event_var = app.sound_event_vars.get(event_name)
        if event_var is None:
            return True

        try:
            return bool(event_var.get())
        except Exception:
            return False

    def play_sound(self, event_name: str) -> None:
        if winsound is None or not self.sound_event_enabled(event_name):
            return

        sound_path = getattr(config, "SOUND_FILES", {}).get(event_name)
        if sound_path is None:
            return

        try:
            if sound_path.exists():
                winsound.PlaySound(
                    str(sound_path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC,
                )
        except Exception:
            return

    def stop_sound(self) -> None:
        if winsound is None:
            return

        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            try:
                winsound.PlaySound(None, 0)
            except Exception:
                pass

    def toggle_morse_speed_preview(self) -> None:
        if self.morse_preview_player.running:
            self.stop_morse_speed_preview()
        else:
            self.start_morse_speed_preview()

    def start_morse_speed_preview(self) -> None:
        app = self.app
        helpers = app.ui_helpers_controller

        wpm = helpers.safe_int_var(
            app.target_wpm_var,
            default=getattr(config, "DEFAULT_TARGET_WPM", 15),
            minimum=5,
            maximum=80,
        )

        try:
            self.morse_preview_player.start(wpm=wpm)
        except RuntimeError as exc:
            app.morse_preview_button_var.set("Äänitesti")
            messagebox.showerror(
                config.APP_NAME,
                "Äänitestiä ei voitu käynnistää.\n\n"
                f"{exc}\n\n"
                "Asenna tarvittaessa:\n"
                "python -m pip install numpy sounddevice",
            )
            return
        except Exception as exc:
            app.morse_preview_button_var.set("Äänitesti")
            messagebox.showerror(
                config.APP_NAME,
                f"Äänitesti epäonnistui:\n\n{exc}",
            )
            return

        app.morse_preview_button_var.set("Lopeta")
        app.status_var.set(
            f"Äänitesti: SOS CONNECTING PEOPLE, {wpm} WPM, 600 Hz."
        )

    def stop_morse_speed_preview(self) -> None:
        try:
            self.morse_preview_player.stop()
        except Exception:
            pass

        try:
            self.app.morse_preview_button_var.set("Äänitesti")
        except Exception:
            pass