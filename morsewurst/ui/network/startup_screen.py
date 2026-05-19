# ============================================================
# morsewurst/ui/network/startup_screen.py
# ============================================================

from __future__ import annotations

import tkinter as tk

import morsewurst.config as config


class NetworkStartupScreen:
    """Small splash screen shown while Morsewurst Network is starting."""

    def __init__(self, parent: tk.Misc) -> None:
        self.parent = parent
        self.window: tk.Toplevel | None = None
        self.canvas: tk.Canvas | None = None
        self.image: tk.PhotoImage | None = None
        self.status_text = "Starting Morsewurst Network."
        self.progress_percent = 0.0

    def show(self) -> None:
        if self.window is not None:
            return

        window = tk.Toplevel(self.parent)
        self.window = window

        window.overrideredirect(True)
        window.configure(background="#111111")
        window.attributes("-topmost", True)

        image_path = getattr(config, "NETWORK_STARTUP_SCREEN_IMAGE", None)

        image_loaded = False
        if image_path is not None:
            try:
                self.image = tk.PhotoImage(file=str(image_path))
                image_loaded = True
            except Exception:
                self.image = None

        if image_loaded and self.image is not None:
            width = self.image.width()
            height = self.image.height()
        else:
            width = 640
            height = 427

        self.canvas = tk.Canvas(
            window,
            width=width,
            height=height,
            highlightthickness=0,
            borderwidth=0,
            background="#111111",
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.draw()
        self.center()
        window.update()

    def status(self, text: str, progress_percent: float | None = None) -> None:
        self.status_text = str(text)

        if progress_percent is not None:
            self.progress_percent = max(0.0, min(100.0, float(progress_percent)))

        self.draw()

        try:
            if self.window is not None and self.window.winfo_exists():
                self.window.update()
        except Exception:
            pass

    def draw(self) -> None:
        canvas = self.canvas
        if canvas is None:
            return

        canvas.delete("all")

        width = max(1, int(canvas.winfo_width()))
        height = max(1, int(canvas.winfo_height()))

        if self.image is not None:
            width = self.image.width()
            height = self.image.height()
            canvas.configure(width=width, height=height)
            canvas.create_image(0, 0, image=self.image, anchor=tk.NW)
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
                height // 2 - 40,
                text="MORSEWURST NETWORK",
                fill="#00ff66",
                font=("Consolas", 28, "bold"),
            )
            canvas.create_text(
                width // 2,
                height // 2,
                text="Preparing network connection",
                fill="#99ffbb",
                font=("Consolas", 12, "bold"),
            )

        percent = max(0.0, min(100.0, float(self.progress_percent)))

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
            fill="#001a0a",
            outline="#00ff66",
            width=1,
        )

        if fill_width > 0:
            canvas.create_rectangle(
                bar_x1,
                bar_y1,
                bar_x1 + fill_width,
                bar_y2,
                fill="#00ff66",
                outline="",
            )

        canvas.create_text(
            width // 2,
            text_y,
            text=f"{self.status_text} {percent:.0f} %",
            fill="#00ff66",
            font=("Consolas", 11, "bold"),
        )

    def center(self) -> None:
        window = self.window
        if window is None:
            return

        window.update_idletasks()

        width = max(1, window.winfo_reqwidth())
        height = max(1, window.winfo_reqheight())

        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()

        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)

        window.geometry(f"{width}x{height}+{x}+{y}")

    def close(self) -> None:
        try:
            if self.window is not None and self.window.winfo_exists():
                self.window.destroy()
        except Exception:
            pass

        self.window = None
        self.canvas = None
        self.image = None
        self.status_text = ""
        self.progress_percent = 0.0