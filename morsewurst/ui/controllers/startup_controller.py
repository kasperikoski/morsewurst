# ============================================================
# morsewurst/ui/controllers/startup_controller.py
# ============================================================

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

import tkinter as tk

import morsewurst.config as config

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class StartupController:
    """Owns startup splash screen drawing, progress updates and startup delays."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def startup_delay(self, seconds: float) -> None:
        app = self.app
        end_time = time.perf_counter() + max(0.0, float(seconds))

        while time.perf_counter() < end_time:
            try:
                app.update_idletasks()
                app.update()
            except tk.TclError:
                return

            time.sleep(0.02)

    def startup_wait_until_minimum(
        self,
        started_at: float,
        minimum_seconds: float = 3.0,
    ) -> None:
        elapsed = time.perf_counter() - started_at
        remaining = max(0.0, float(minimum_seconds) - elapsed)

        if remaining > 0:
            self.startup_delay(remaining)

    def show_startup_screen(self) -> None:
        app = self.app

        app.startup_screen = tk.Toplevel(app)
        app.startup_screen.overrideredirect(True)
        app.startup_screen.configure(background="#111111")
        app.startup_screen.attributes("-topmost", True)

        image_path = getattr(config, "STARTUP_SCREEN_IMAGE", None)

        image_loaded = False
        if image_path is not None:
            try:
                app.startup_image = tk.PhotoImage(file=str(image_path))
                image_loaded = True
            except Exception:
                app.startup_image = None

        if image_loaded and app.startup_image is not None:
            width = app.startup_image.width()
            height = app.startup_image.height()
        else:
            width = 720
            height = 576

        app.startup_canvas = tk.Canvas(
            app.startup_screen,
            width=width,
            height=height,
            highlightthickness=0,
            borderwidth=0,
            background="#111111",
        )
        app.startup_canvas.pack(fill=tk.BOTH, expand=True)

        self.draw_startup_screen()
        self.center_startup_screen()
        app.startup_screen.update()

    def draw_startup_screen(self) -> None:
        app = self.app

        if app.startup_canvas is None:
            return

        canvas = app.startup_canvas
        canvas.delete("all")

        width = max(1, int(canvas.winfo_width()))
        height = max(1, int(canvas.winfo_height()))

        if app.startup_image is not None:
            width = app.startup_image.width()
            height = app.startup_image.height()
            canvas.configure(width=width, height=height)
            canvas.create_image(0, 0, image=app.startup_image, anchor=tk.NW)
        else:
            canvas.configure(width=width, height=height)
            canvas.create_rectangle(
                0,
                0,
                width,
                height,
                fill="#111111",
                outline="",
            )
            canvas.create_text(
                width // 2,
                height // 2 - 30,
                text=config.APP_NAME,
                fill="#ffffff",
                font=("Segoe UI", 28, "bold"),
            )

        percent = max(0.0, min(100.0, float(app.startup_progress_percent)))

        bar_margin_x = int(width * 0.10)
        bar_width = width - (bar_margin_x * 2)
        bar_height = 14

        text_y = height - 46
        bar_y = text_y - 30

        bar_x1 = bar_margin_x
        bar_y1 = bar_y
        bar_x2 = bar_x1 + bar_width
        bar_y2 = bar_y1 + bar_height

        fill_width = int(bar_width * (percent / 100.0))

        overlay_x1 = bar_x1 - 14
        overlay_y1 = bar_y1 - 12
        overlay_x2 = bar_x2 + 14
        overlay_y2 = text_y + 22

        canvas.create_rectangle(
            overlay_x1,
            overlay_y1,
            overlay_x2,
            overlay_y2,
            fill="#000000",
            outline="",
            stipple="gray50",
        )

        canvas.create_rectangle(
            bar_x1,
            bar_y1,
            bar_x2,
            bar_y2,
            fill="#2b2b2b",
            outline="#ffffff",
            width=1,
        )

        if fill_width > 0:
            canvas.create_rectangle(
                bar_x1,
                bar_y1,
                bar_x1 + fill_width,
                bar_y2,
                fill="#ffffff",
                outline="",
            )

        canvas.create_text(
            width // 2,
            text_y,
            text=f"{app.startup_status_text} {percent:.0f} %",
            fill="#ffffff",
            font=("Segoe UI", 11, "bold"),
        )

    def center_startup_screen(self) -> None:
        app = self.app

        if app.startup_screen is None:
            return

        app.startup_screen.update_idletasks()

        width = max(1, app.startup_screen.winfo_reqwidth())
        height = max(1, app.startup_screen.winfo_reqheight())

        screen_width = app.startup_screen.winfo_screenwidth()
        screen_height = app.startup_screen.winfo_screenheight()

        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)

        app.startup_screen.geometry(f"{width}x{height}+{x}+{y}")

    def startup_status(
        self,
        text: str,
        progress_percent: Optional[float] = None,
    ) -> None:
        app = self.app

        try:
            app.startup_status_text = text

            if progress_percent is not None:
                app.startup_progress_percent = max(
                    0.0,
                    min(100.0, float(progress_percent)),
                )

            self.draw_startup_screen()

            if app.startup_screen is not None and app.startup_screen.winfo_exists():
                app.startup_screen.update()

        except Exception:
            pass

    def finish_startup_screen(self) -> None:
        app = self.app

        min_ms = int(getattr(config, "STARTUP_SCREEN_MIN_MS", 3000))
        elapsed_ms = int((time.monotonic() - app.startup_started_at) * 1000)
        delay_ms = max(0, min_ms - elapsed_ms)

        self.startup_status("Valmis", 100)

        if delay_ms > 0:
            app.after(delay_ms, self.close_startup_screen)
        else:
            self.close_startup_screen()

    def close_startup_screen(self) -> None:
        app = self.app

        try:
            if app.startup_screen is not None and app.startup_screen.winfo_exists():
                app.startup_screen.destroy()
        except Exception:
            pass

        app.startup_screen = None
        app.startup_canvas = None
        app.startup_image = None
        app.startup_status_text = ""
        app.startup_progress_percent = 0.0

        app.deiconify()
        app.lift()

        try:
            app.attributes("-topmost", True)
            app.after(100, lambda: app.attributes("-topmost", False))
        except Exception:
            pass

        app.app_lifecycle_controller.focus_input(force=True)