# ============================================================
# morsewurst/ui/help_window.py
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import morsewurst.config as config
from morsewurst.core.app_logging import log_app_event, log_app_exception

try:
    from morsewurst.ui import help_content as _help_content
except ModuleNotFoundError:
    _help_content = None

HELP_DOCUMENT = getattr(_help_content, "HELP_DOCUMENT", None)
build_help_document = getattr(_help_content, "build_help_document", None)


class HelpWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)

        self.app = parent

        self.title(self.app.i18n.t("help_window.title", app_name=config.APP_NAME))
        self.transient(parent)
        self.geometry("920x720")
        self.minsize(760, 520)

        self.protocol("WM_DELETE_WINDOW", self._close)

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
            text=self.app.i18n.t("help_window.header"),
            font=("Segoe UI", 16, "bold"),
        ).pack(side=tk.LEFT)

        ttk.Button(
            header,
            text=self.app.i18n.t("help_window.close_button"),
            command=self._close,
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

        blocks = self._load_help_blocks()

        for block in blocks:
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

    def _load_help_blocks(self) -> list[dict[str, str]]:
        if callable(build_help_document):
            try:
                return build_help_document(self.app.i18n)
            except Exception as exc:
                log_app_exception(
                    "app.help.content_load_failed",
                    exc,
                    level="warning",
                    message="Help document builder failed; fallback help content will be used if needed.",
                )

        if HELP_DOCUMENT is not None:
            return self._resolve_help_document(HELP_DOCUMENT)

        log_app_event(
            "app.help.fallback_used",
            level="warning",
            message="Fallback help content was used.",
        )
        return [
            {"type": "title", "text": self.app.i18n.t("help_window.fallback_title")},
            {"type": "paragraph", "text": self.app.i18n.t("help_window.fallback_paragraph")},
        ]

    def _close(self) -> None:
        log_app_event(
            "app.help.window_closed",
            message="Help window closed.",
        )
        self.destroy()

    def _resolve_help_document(self, document: object) -> list[dict[str, str]]:
        blocks: list[dict[str, str]] = []

        try:
            iterable = list(document)  # type: ignore[arg-type]
        except Exception:
            return blocks

        for raw_block in iterable:
            if not isinstance(raw_block, dict):
                continue

            block_type = str(raw_block.get("type", "paragraph"))
            key = str(raw_block.get("key", "")).strip()

            if key:
                text = self.app.i18n.t(key)
            else:
                text = str(raw_block.get("text", ""))

            text = text.strip()
            if text:
                blocks.append({"type": block_type, "text": text})

        return blocks

    def _center_on_parent(self, parent: tk.Misc) -> None:
        try:
            x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
            y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass
