# ============================================================
# morsewurst/ui/help_window.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import morsewurst.config as config
try:
    from morsewurst.ui.help_content import HELP_DOCUMENT
except ModuleNotFoundError:
    HELP_DOCUMENT = [
        {"type": "title", "text": "Morsewurst ohje"},
        {"type": "paragraph", "text": "Ohjesisältöä ei löytynyt tästä paketista."},
    ]


class HelpWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)

        self.title(f"{config.APP_NAME} ohje")
        self.transient(parent)
        self.geometry("920x720")
        self.minsize(760, 520)

        self._build_ui()
        self._insert_help_content()

        self.update_idletasks()
        self._center_on_parent(parent)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            header,
            text="Ohje",
            font=("Segoe UI", 16, "bold"),
        ).pack(side=tk.LEFT)

        ttk.Button(
            header,
            text="Sulje",
            command=self.destroy,
        ).pack(side=tk.RIGHT)

        content_frame = ttk.Frame(outer)
        content_frame.pack(fill=tk.BOTH, expand=True)

        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            content_frame,
            wrap=tk.WORD,
            padx=18,
            pady=16,
            font=("Segoe UI", 10),
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#dddddd",
            relief=tk.FLAT,
        )

        scrollbar = ttk.Scrollbar(
            content_frame,
            orient=tk.VERTICAL,
            command=self.text.yview,
        )

        self.text.configure(yscrollcommand=scrollbar.set)

        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.text.tag_configure(
            "title",
            font=("Segoe UI", 18, "bold"),
            spacing1=0,
            spacing3=16,
        )

        self.text.tag_configure(
            "heading",
            font=("Segoe UI", 13, "bold"),
            spacing1=14,
            spacing3=6,
        )

        self.text.tag_configure(
            "subheading",
            font=("Segoe UI", 11, "bold"),
            spacing1=10,
            spacing3=4,
        )

        self.text.tag_configure(
            "paragraph",
            font=("Segoe UI", 10),
            spacing1=2,
            spacing3=8,
            lmargin1=0,
            lmargin2=0,
        )

        self.text.tag_configure(
            "bullet",
            font=("Segoe UI", 10),
            spacing1=2,
            spacing3=4,
            lmargin1=20,
            lmargin2=38,
        )

        self.text.tag_configure(
            "note",
            font=("Segoe UI", 10, "italic"),
            foreground="#555555",
            spacing1=6,
            spacing3=8,
            lmargin1=12,
            lmargin2=12,
        )

        self.text.tag_configure(
            "code",
            font=("Consolas", 10),
            background="#f4f4f4",
            spacing1=4,
            spacing3=8,
            lmargin1=12,
            lmargin2=12,
        )

        self.text.configure(state=tk.DISABLED)

    def _insert_help_content(self) -> None:
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        for block in HELP_DOCUMENT:
            block_type = str(block.get("type", "paragraph"))
            text = str(block.get("text", ""))

            if not text:
                continue

            if block_type == "title":
                self.text.insert(tk.END, text + "\n", "title")

            elif block_type == "heading":
                self.text.insert(tk.END, text + "\n", "heading")

            elif block_type == "subheading":
                self.text.insert(tk.END, text + "\n", "subheading")

            elif block_type == "bullet":
                self.text.insert(tk.END, f"• {text}\n", "bullet")

            elif block_type == "note":
                self.text.insert(tk.END, text + "\n", "note")

            elif block_type == "code":
                self.text.insert(tk.END, text + "\n", "code")

            else:
                self.text.insert(tk.END, text + "\n", "paragraph")

        self.text.configure(state=tk.DISABLED)

    def _center_on_parent(self, parent: tk.Misc) -> None:
        try:
            x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
            y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass