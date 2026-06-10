# ============================================================
# morsewurst/ui/controllers/update_controller.py
# ============================================================

from __future__ import annotations

import json
import queue
import re
import threading
import urllib.request
import webbrowser
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import morsewurst.config as config
from morsewurst.core.app_logging import log_app_event, log_app_exception

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


@dataclass(frozen=True)
class UpdateManifest:
    """Validated update manifest data."""

    latest_version: str
    download_url: str
    release_url: str
    release_notes: list[str]


class UpdateController:
    """Checks whether a newer Morsewurst version is available.

    Version 1 only checks and notifies. It does not download, install or modify
    the local application.
    """

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app
        self._worker: threading.Thread | None = None
        self._result_queue: "queue.Queue[tuple[str, Any, bool]]" = queue.Queue()
        self._poll_after_id: str | None = None
        self._last_notified_version = ""

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------

    def check_for_updates_after_startup(self) -> None:
        """Schedule an automatic update check after the main UI has started."""
        if not bool(getattr(config, "UPDATE_CHECK_ON_STARTUP", True)):
            log_app_event(
                "app.update.check_skipped_disabled",
                message="Startup update check skipped because it is disabled.",
                context={"manual": False},
            )
            return

        delay_ms = _safe_int(
            getattr(config, "UPDATE_CHECK_STARTUP_DELAY_MS", 1500),
            default=1500,
            minimum=0,
            maximum=60_000,
        )

        try:
            self.app.after(delay_ms, lambda: self.check_for_updates(manual=False))
            log_app_event(
                "app.update.check_scheduled",
                message="Startup update check scheduled.",
                context={"delay_ms": delay_ms},
            )
        except Exception as exc:
            log_app_exception(
                "app.update.check_schedule_failed",
                exc,
                level="warning",
                message="Startup update check could not be scheduled.",
                context={"delay_ms": delay_ms},
            )

    def check_for_updates_manual(self) -> None:
        """Run a user-requested update check."""
        self.check_for_updates(manual=True)

    def check_for_updates(self, *, manual: bool = False) -> None:
        """Start an update check in a background thread."""
        log_app_event(
            "app.update.check_started",
            message="Update check requested.",
            context={"manual": bool(manual)},
        )

        if not bool(getattr(config, "UPDATE_CHECK_ENABLED", True)):
            log_app_event(
                "app.update.check_skipped_disabled",
                message="Update check skipped because it is disabled.",
                context={"manual": bool(manual)},
            )
            if manual:
                messagebox.showinfo(
                    config.APP_NAME,
                    self._t(
                        "update.check.disabled",
                        "Update checking is disabled.",
                    ),
                    parent=self.app,
                )
            return

        manifest_url = str(getattr(config, "UPDATE_MANIFEST_URL", "") or "").strip()
        if not manifest_url:
            log_app_event(
                "app.update.check_skipped_invalid_url",
                level="warning",
                message="Update check skipped because manifest URL is empty.",
                context={"manual": bool(manual)},
            )
            if manual:
                messagebox.showinfo(
                    config.APP_NAME,
                    self._t(
                        "update.check.manifest_url_missing",
                        (
                            "The update manifest URL has not been configured.\n\n"
                            "Set UPDATE_MANIFEST_URL in config.py."
                        ),
                    ),
                    parent=self.app,
                )
            return

        if not _is_safe_http_url(manifest_url):
            log_app_event(
                "app.update.check_skipped_invalid_url",
                level="warning",
                message="Update check skipped because manifest URL is invalid.",
                context={"manual": bool(manual), "manifest_url": manifest_url},
            )
            if manual:
                messagebox.showwarning(
                    config.APP_NAME,
                    self._t(
                        "update.check.manifest_url_invalid",
                        (
                            "The update manifest URL is invalid.\n\n"
                            "UPDATE_MANIFEST_URL must be an http:// or https:// URL."
                        ),
                    ),
                    parent=self.app,
                )
            return

        if self._worker is not None and self._worker.is_alive():
            log_app_event(
                "app.update.check_already_running",
                message="Update check skipped because a previous check is already running.",
                context={"manual": bool(manual)},
            )
            if manual:
                messagebox.showinfo(
                    config.APP_NAME,
                    self._t(
                        "update.check.already_running",
                        "An update check is already running.",
                    ),
                    parent=self.app,
                )
            return

        self._worker = threading.Thread(
            target=self._run_check_worker,
            args=(manifest_url, manual),
            daemon=True,
        )
        self._worker.start()
        log_app_event(
            "app.update.worker_started",
            message="Update check worker started.",
            context={"manual": bool(manual), "manifest_url": manifest_url},
        )
        self._schedule_result_poll()

    # ------------------------------------------------------------
    # Worker and result handling
    # ------------------------------------------------------------

    def _run_check_worker(self, manifest_url: str, manual: bool) -> None:
        try:
            manifest = self._fetch_manifest(manifest_url)
            log_app_event(
                "app.update.fetch_success",
                message="Update manifest fetched successfully.",
                context={
                    "manual": bool(manual),
                    "manifest_url": manifest_url,
                    "latest_version": manifest.latest_version,
                },
            )
            self._result_queue.put(("success", manifest, manual))
        except Exception as exc:
            log_app_exception(
                "app.update.fetch_failed",
                exc,
                level="warning",
                message="Update manifest fetch failed.",
                context={"manual": bool(manual), "manifest_url": manifest_url},
            )
            self._result_queue.put(("error", exc, manual))

    def _schedule_result_poll(self) -> None:
        if self._poll_after_id is not None:
            return

        try:
            self._poll_after_id = self.app.after(100, self._poll_result_queue)
        except Exception:
            self._poll_after_id = None

    def _poll_result_queue(self) -> None:
        self._poll_after_id = None

        while True:
            try:
                kind, payload, manual = self._result_queue.get_nowait()
            except queue.Empty:
                break

            if kind == "success":
                self._handle_manifest(payload, manual=manual)
            elif kind == "error":
                self._handle_error(payload, manual=manual)

        if self._worker is not None and self._worker.is_alive():
            self._schedule_result_poll()
            return

        if not self._result_queue.empty():
            self._schedule_result_poll()
            return

        self._worker = None

    def _handle_manifest(self, manifest: UpdateManifest, *, manual: bool) -> None:
        current_version = str(getattr(config, "APP_VERSION", "") or "").strip()
        latest_version = manifest.latest_version.strip()

        if _is_newer_version(latest_version, current_version):
            log_app_event(
                "app.update.available",
                message="New application version is available.",
                context={
                    "manual": bool(manual),
                    "current_version": current_version,
                    "latest_version": latest_version,
                    "has_release_url": bool(manifest.release_url),
                    "has_download_url": bool(manifest.download_url),
                },
            )
            self._show_update_available(manifest, manual=manual)
            return

        log_app_event(
            "app.update.not_available",
            message="No newer application version was found.",
            context={
                "manual": bool(manual),
                "current_version": current_version,
                "latest_version": latest_version,
            },
        )

        if manual:
            messagebox.showinfo(
                config.APP_NAME,
                self._t(
                    "update.check.up_to_date",
                    "You are using the latest version.\n\nInstalled version: {current_version}",
                    current_version=current_version,
                ),
                parent=self.app,
            )

    def _handle_error(self, exc: Any, *, manual: bool) -> None:
        log_app_exception(
            "app.update.check_failed",
            exc if isinstance(exc, BaseException) else RuntimeError(str(exc)),
            level="warning",
            message="Update check failed.",
            context={"manual": bool(manual)},
        )
        if not manual:
            return

        messagebox.showwarning(
            config.APP_NAME,
            self._t(
                "update.check.failed",
                "Update check failed.\n\n{error}",
                error=exc,
            ),
            parent=self.app,
        )

    # ------------------------------------------------------------
    # Manifest loading and validation
    # ------------------------------------------------------------

    def _fetch_manifest(self, manifest_url: str) -> UpdateManifest:
        timeout = float(getattr(config, "UPDATE_CHECK_TIMEOUT_SECONDS", 5.0) or 5.0)
        timeout = max(1.0, min(30.0, timeout))

        request = urllib.request.Request(
            manifest_url,
            headers={
                "Accept": "application/json",
                "User-Agent": f"{config.APP_NAME}/{getattr(config, 'APP_VERSION', '')}",
            },
        )

        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(512_000)

        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise ValueError(
                self._t(
                    "update.error.invalid_json",
                    "The update manifest is not valid JSON data.",
                )
            ) from exc

        if not isinstance(data, dict):
            raise ValueError(
                self._t(
                    "update.error.invalid_manifest_object",
                    "The update manifest must be a JSON object.",
                )
            )

        latest_version = _clean_text(
            data.get("latest_version") or data.get("version"),
            limit=80,
        )
        if not latest_version:
            raise ValueError(
                self._t(
                    "update.error.missing_latest_version",
                    "The update manifest is missing latest_version.",
                )
            )

        download_url = _clean_text(data.get("download_url"), limit=500)
        release_url = _clean_text(
            data.get("release_url") or data.get("url"),
            limit=500,
        )

        fallback_url = _clean_text(
            getattr(config, "UPDATE_DOWNLOAD_PAGE_URL", ""),
            limit=500,
        )

        if not download_url and fallback_url:
            download_url = fallback_url

        if download_url and not _is_safe_http_url(download_url):
            download_url = ""

        if release_url and not _is_safe_http_url(release_url):
            release_url = ""

        release_notes = _clean_release_notes(data.get("release_notes"))

        return UpdateManifest(
            latest_version=latest_version,
            download_url=download_url,
            release_url=release_url,
            release_notes=release_notes,
        )

    # ------------------------------------------------------------
    # UI
    # ------------------------------------------------------------

    def _t(self, key: str, default: str, **values: Any) -> str:
        """Return a translated UI string with a safe fallback."""

        i18n = getattr(self.app, "i18n", None)

        if i18n is not None:
            try:
                return str(i18n.t(key, default, **values))
            except Exception:
                pass

        if not values:
            return default

        try:
            return default.format(**values)
        except Exception:
            return default

    def _show_update_available(self, manifest: UpdateManifest, *, manual: bool) -> None:
        latest_version = manifest.latest_version.strip()

        if not manual and latest_version == self._last_notified_version:
            return

        self._last_notified_version = latest_version

        open_url = manifest.download_url or manifest.release_url
        should_open_url = self._show_update_dialog(
            manifest,
            manual=manual,
            open_url=open_url,
        )

        if not should_open_url or not open_url:
            return

        log_app_event(
            "app.update.open_download_url_requested",
            message="User requested opening the update download URL.",
            context={"latest_version": latest_version, "url": open_url},
        )

        try:
            webbrowser.open(open_url)
        except Exception as exc:
            log_app_exception(
                "app.update.open_download_url_failed",
                exc,
                message="Update download URL could not be opened.",
                context={"latest_version": latest_version, "url": open_url},
            )
            messagebox.showwarning(
                config.APP_NAME,
                self._t(
                    "update.dialog.open_failed",
                    "The download page could not be opened.\n\n{error}",
                    error=exc,
                ),
                parent=self.app,
            )

    def _show_update_dialog(
        self,
        manifest: UpdateManifest,
        *,
        manual: bool,
        open_url: str,
    ) -> bool:
        """Show a readable modal update dialog and return whether to open the URL."""

        del manual  # Reserved for future wording differences.

        result = {"open_url": False}

        window = tk.Toplevel(self.app)
        window.title(
            self._t(
                "update.dialog.window_title",
                "{app_name} update",
                app_name=config.APP_NAME,
            )
        )
        window.transient(self.app)
        window.resizable(True, True)
        window.minsize(620, 420)
        window.geometry("760x560")

        try:
            window.configure(padx=0, pady=0)
        except Exception:
            pass

        def close_dialog() -> None:
            window.destroy()

        def open_download_page() -> None:
            result["open_url"] = True
            window.destroy()

        outer = ttk.Frame(window, padding=(22, 20, 22, 18))
        outer.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            outer,
            text=self._t(
                "update.dialog.title",
                "A new Morsewurst version is available",
            ),
            font=("", 15, "bold"),
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=690,
        )
        title.pack(fill=tk.X, anchor=tk.W)

        intro = ttk.Label(
            outer,
            text=self._t(
                "update.dialog.message",
                "A newer version of {app_name} is available. Review the changes below before opening the download page.",
                app_name=config.APP_NAME,
            ),
            justify=tk.LEFT,
            wraplength=690,
        )
        intro.pack(fill=tk.X, anchor=tk.W, pady=(8, 16))

        version_frame = ttk.Frame(outer)
        version_frame.pack(fill=tk.X, pady=(0, 16))
        version_frame.columnconfigure(0, weight=1)
        version_frame.columnconfigure(1, weight=1)

        current_version = str(getattr(config, "APP_VERSION", "") or "").strip()
        latest_version = manifest.latest_version.strip()

        current_card = ttk.LabelFrame(
            version_frame,
            text=self._t(
                "update.dialog.installed_version",
                "Installed version",
            ),
            padding=(12, 8),
        )
        current_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        latest_card = ttk.LabelFrame(
            version_frame,
            text=self._t(
                "update.dialog.latest_version",
                "Latest version",
            ),
            padding=(12, 8),
        )
        latest_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        ttk.Label(
            current_card,
            text=current_version or "-",
            font=("", 12, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            latest_card,
            text=latest_version or "-",
            font=("", 12, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(
            outer,
            text=self._t(
                "update.dialog.release_notes",
                "Release notes",
            ),
            font=("", 11, "bold"),
        ).pack(fill=tk.X, anchor=tk.W)

        notes = ScrolledText(
            outer,
            height=12,
            wrap=tk.WORD,
            relief=tk.SOLID,
            borderwidth=1,
            padx=12,
            pady=10,
        )
        notes.pack(fill=tk.BOTH, expand=True, pady=(6, 16))

        try:
            notes.configure(font=("", 10))
            notes.tag_configure("bullet", lmargin1=12, lmargin2=12, spacing1=3, spacing3=7)
            notes.tag_configure("empty", foreground="#666666")
        except Exception:
            pass

        if manifest.release_notes:
            for note in manifest.release_notes[:500]:
                notes.insert(tk.END, f"\u2022 {note}\n", "bullet")
        else:
            notes.insert(
                tk.END,
                self._t(
                    "update.dialog.no_release_notes",
                    "No release notes were provided.",
                ),
                "empty",
            )

        notes.configure(state=tk.DISABLED)

        button_frame = ttk.Frame(outer)
        button_frame.pack(fill=tk.X)

        if open_url:
            open_button = ttk.Button(
                button_frame,
                text=self._t(
                    "update.dialog.open_download_page",
                    "Open download page",
                ),
                command=open_download_page,
            )
            open_button.pack(side=tk.RIGHT)

            later_button = ttk.Button(
                button_frame,
                text=self._t(
                    "update.dialog.later",
                    "Later",
                ),
                command=close_dialog,
            )
            later_button.pack(side=tk.RIGHT, padx=(0, 8))

            window.bind("<Return>", lambda _event: open_download_page())
            open_button.focus_set()
        else:
            close_button = ttk.Button(
                button_frame,
                text=self._t(
                    "update.dialog.close",
                    "Close",
                ),
                command=close_dialog,
            )
            close_button.pack(side=tk.RIGHT)
            close_button.focus_set()

        window.bind("<Escape>", lambda _event: close_dialog())
        window.protocol("WM_DELETE_WINDOW", close_dialog)

        self._center_update_dialog(window)

        try:
            window.grab_set()
        except Exception:
            pass

        window.wait_window()
        return bool(result["open_url"])

    def _center_update_dialog(self, window: tk.Toplevel) -> None:
        """Center a child dialog over the main application window."""

        try:
            window.update_idletasks()

            parent_x = self.app.winfo_rootx()
            parent_y = self.app.winfo_rooty()
            parent_width = self.app.winfo_width()
            parent_height = self.app.winfo_height()

            width = window.winfo_width()
            height = window.winfo_height()

            x = parent_x + max(0, (parent_width - width) // 2)
            y = parent_y + max(0, (parent_height - height) // 2)

            window.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            try:
                window.update_idletasks()

                width = window.winfo_width()
                height = window.winfo_height()
                screen_width = window.winfo_screenwidth()
                screen_height = window.winfo_screenheight()

                x = max(0, (screen_width - width) // 2)
                y = max(0, (screen_height - height) // 2)

                window.geometry(f"+{x}+{y}")
            except Exception:
                pass


# ============================================================
# Helper functions
# ============================================================

def _is_newer_version(latest: str, current: str) -> bool:
    return _version_key(latest) > _version_key(current)


def _version_key(version: str) -> tuple[int, ...]:
    """Return a numeric comparison key for long dotted versions.

    Examples:
    0.99       -> (0, 99)
    0.99.0     -> (0, 99)
    0.99.12345 -> (0, 99, 12345)

    Non-numeric separators are tolerated, but numeric parts decide ordering.
    """

    parts = re.findall(r"\d+", str(version or ""))

    if not parts:
        return (0,)

    numbers = tuple(int(part.lstrip("0") or "0") for part in parts)

    while len(numbers) > 1 and numbers[-1] == 0:
        numbers = numbers[:-1]

    return numbers


def _safe_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        number = int(value)
    except Exception:
        number = default

    return max(minimum, min(maximum, number))


def _clean_text(value: object, *, limit: int) -> str:
    text = str(value or "").strip()
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    text = "".join(ch for ch in text if ch.isprintable())
    return text[:limit].strip()


def _clean_release_notes(value: object) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        raw_items = value.splitlines()
    else:
        return []

    notes: list[str] = []

    for item in raw_items:
        text = _clean_text(item, limit=10_000)
        if text:
            notes.append(text)

    return notes[:500]


def _is_safe_http_url(value: str) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except Exception:
        return False

    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)