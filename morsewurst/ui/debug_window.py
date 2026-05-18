# ============================================================
# morsewurst/ui/debug_window.py
# ============================================================

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

import morsewurst.config as config
from morsewurst.core.debug_snapshot import (
    clear_debug_files,
    debug_dir_path,
    read_history_debug_text,
    read_latest_debug_text,
)


class DebugWindow(tk.Toplevel):
    def __init__(self, app: tk.Misc) -> None:
        super().__init__(app)

        self.app = app
        self.mode_var = tk.StringVar(value="latest")
        self.status_var = tk.StringVar(value="")

        self.title("Debug-data")
        self.transient(app)
        self.geometry("1100x760")
        self.minsize(850, 560)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.load_latest()
        self._center_on_parent()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text="Debug-data",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            outer,
            text=(
                "Tässä näkyy kierroksen jälkeen tallennettu debug-snapshot. "
                "Se sisältää Python-ohjelman vastaanottamat tone-tapahtumat, "
                "lasketut tauot, dekooderin timing-arvot, rescue-päätökset "
                "ja lopullisen tulkinnan."
            ),
            wraplength=980,
        ).pack(anchor=tk.W, pady=(4, 10))

        button_row = ttk.Frame(outer)
        button_row.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            button_row,
            text="Näytä viimeisin kierros",
            command=self.load_latest,
        ).pack(side=tk.LEFT)

        ttk.Button(
            button_row,
            text="Näytä historia siistinä",
            command=self.load_history_pretty,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            button_row,
            text="Näytä raaka JSONL",
            command=self.load_history_raw,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            button_row,
            text="Kopioi näkyvä teksti",
            command=self.copy_visible_text,
        ).pack(side=tk.LEFT, padx=(18, 0))

        ttk.Button(
            button_row,
            text="Kopioi viimeisin kierros",
            command=self.copy_latest,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            button_row,
            text="Avaa kansio",
            command=self.open_debug_folder,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(
            button_row,
            text="Tyhjennä debug-data",
            command=self.clear_debug_data,
        ).pack(side=tk.LEFT, padx=(18, 0))

        ttk.Button(
            button_row,
            text="Sulje",
            command=self.close,
        ).pack(side=tk.RIGHT)

        text_frame = ttk.Frame(outer)
        text_frame.pack(fill=tk.BOTH, expand=True)

        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame,
            wrap=tk.NONE,
            undo=False,
            font=("Consolas", 10),
        )

        scrollbar_y = ttk.Scrollbar(
            text_frame,
            orient=tk.VERTICAL,
            command=self.text.yview,
        )

        scrollbar_x = ttk.Scrollbar(
            text_frame,
            orient=tk.HORIZONTAL,
            command=self.text.xview,
        )

        self.text.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
        )

        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        status_row = ttk.Frame(outer)
        status_row.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(
            status_row,
            textvariable=self.status_var,
            foreground="#666666",
        ).pack(side=tk.LEFT)

    def _center_on_parent(self) -> None:
        try:
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

        except Exception:
            pass

    def _set_text(self, content: str) -> None:
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        if content:
            self.text.insert("1.0", content)
        else:
            self.text.insert("1.0", "Debug-dataa ei ole vielä tallennettu.\n")

        self.text.configure(state=tk.NORMAL)
        self.text.mark_set(tk.INSERT, "1.0")
        self.text.see("1.0")

    def load_latest(self) -> None:
        self.mode_var.set("latest")
        content = read_latest_debug_text()

        self._set_text(content)
        self.status_var.set("Näytetään viimeisin debug-snapshot.")

    def load_history_pretty(self) -> None:
        self.mode_var.set("history_pretty")
        content = read_history_debug_text(pretty=True)

        self._set_text(content)
        self.status_var.set("Näytetään koko debug-historia siistissä muodossa.")

    def load_history_raw(self) -> None:
        self.mode_var.set("history_raw")
        content = read_history_debug_text(pretty=False)

        self._set_text(content)
        self.status_var.set("Näytetään raaka JSONL-historiatiedosto.")

    def copy_visible_text(self) -> None:
        content = self.text.get("1.0", tk.END).rstrip()

        if not content:
            self.status_var.set("Ei kopioitavaa.")
            return

        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_var.set("Näkyvä debug-data kopioitu leikepöydälle.")

    def copy_latest(self) -> None:
        content = read_latest_debug_text().rstrip()

        if not content:
            self.status_var.set("Viimeisintä debug-snapshotia ei löytynyt.")
            return

        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_var.set("Viimeisin debug-snapshot kopioitu leikepöydälle.")

    def clear_debug_data(self) -> None:
        ok = messagebox.askyesno(
            config.APP_NAME,
            "Haluatko varmasti tyhjentää debug-datan?\n\n"
            "Tämä poistaa latest_round_debug.json- ja debug_history.jsonl-tiedostot.",
            parent=self,
        )

        if not ok:
            return

        deleted = clear_debug_files()

        self._set_text("")
        self.status_var.set(
            f"Debug-data tyhjennetty. Poistettuja tiedostoja: {deleted}."
        )

    def open_debug_folder(self) -> None:
        path = debug_dir_path()
        path.mkdir(parents=True, exist_ok=True)

        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])

        except Exception as exc:
            messagebox.showerror(
                config.APP_NAME,
                f"Debug-kansion avaaminen epäonnistui:\n{exc}",
                parent=self,
            )

    def close(self) -> None:
        try:
            if getattr(self.app, "debug_window", None) is self:
                self.app.debug_window = None
        except Exception:
            pass

        self.destroy()