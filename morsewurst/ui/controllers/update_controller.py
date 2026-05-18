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

from tkinter import messagebox

import morsewurst.config as config

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
            return

        delay_ms = _safe_int(
            getattr(config, "UPDATE_CHECK_STARTUP_DELAY_MS", 1500),
            default=1500,
            minimum=0,
            maximum=60_000,
        )

        try:
            self.app.after(delay_ms, lambda: self.check_for_updates(manual=False))
        except Exception:
            pass

    def check_for_updates_manual(self) -> None:
        """Run a user-requested update check."""
        self.check_for_updates(manual=True)

    def check_for_updates(self, *, manual: bool = False) -> None:
        """Start an update check in a background thread."""
        if not bool(getattr(config, "UPDATE_CHECK_ENABLED", True)):
            if manual:
                messagebox.showinfo(
                    config.APP_NAME,
                    "Päivitystarkistus ei ole käytössä.",
                    parent=self.app,
                )
            return

        manifest_url = str(getattr(config, "UPDATE_MANIFEST_URL", "") or "").strip()
        if not manifest_url:
            if manual:
                messagebox.showinfo(
                    config.APP_NAME,
                    (
                        "Päivitystarkistuksen osoitetta ei ole asetettu.\n\n"
                        "Aseta config.py-tiedostoon UPDATE_MANIFEST_URL."
                    ),
                    parent=self.app,
                )
            return

        if not _is_safe_http_url(manifest_url):
            if manual:
                messagebox.showwarning(
                    config.APP_NAME,
                    (
                        "Päivitystarkistuksen osoite ei kelpaa.\n\n"
                        "UPDATE_MANIFEST_URL-arvon pitää olla http:// tai https:// osoite."
                    ),
                    parent=self.app,
                )
            return

        if self._worker is not None and self._worker.is_alive():
            if manual:
                messagebox.showinfo(
                    config.APP_NAME,
                    "Päivitystarkistus on jo käynnissä.",
                    parent=self.app,
                )
            return

        self._worker = threading.Thread(
            target=self._run_check_worker,
            args=(manifest_url, manual),
            daemon=True,
        )
        self._worker.start()
        self._schedule_result_poll()

    # ------------------------------------------------------------
    # Worker and result handling
    # ------------------------------------------------------------

    def _run_check_worker(self, manifest_url: str, manual: bool) -> None:
        try:
            manifest = self._fetch_manifest(manifest_url)
            self._result_queue.put(("success", manifest, manual))
        except Exception as exc:
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
            self._show_update_available(manifest, manual=manual)
            return

        if manual:
            messagebox.showinfo(
                config.APP_NAME,
                (
                    "Käytössä on uusin versio.\n\n"
                    f"Nykyinen versio: {current_version}"
                ),
                parent=self.app,
            )

    def _handle_error(self, exc: Any, *, manual: bool) -> None:
        if not manual:
            return

        messagebox.showwarning(
            config.APP_NAME,
            (
                "Päivitystarkistus epäonnistui.\n\n"
                f"{exc}"
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
            raise ValueError("Päivitysmanifesti ei ole kelvollista JSON-dataa.") from exc

        if not isinstance(data, dict):
            raise ValueError("Päivitysmanifestin pitää olla JSON-objekti.")

        latest_version = _clean_text(
            data.get("latest_version") or data.get("version"),
            limit=80,
        )
        if not latest_version:
            raise ValueError("Päivitysmanifestista puuttuu latest_version.")

        download_url = _clean_text(data.get("download_url"), limit=500)
        release_url = _clean_text(
            data.get("release_url") or data.get("url"),
            limit=500,
        )

        fallback_url = _clean_text(
            getattr(config, "UPDATE_DOWNLOAD_PAGE_URL", ""),
            limit=500,
        )

        if not release_url and fallback_url:
            release_url = fallback_url

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

    def _show_update_available(self, manifest: UpdateManifest, *, manual: bool) -> None:
        latest_version = manifest.latest_version.strip()

        if not manual and latest_version == self._last_notified_version:
            return

        self._last_notified_version = latest_version

        current_version = str(getattr(config, "APP_VERSION", "") or "").strip()
        open_url = manifest.release_url or manifest.download_url

        text_parts = [
            f"Uusi {config.APP_NAME}-versio on saatavilla.",
            "",
            f"Nykyinen versio: {current_version}",
            f"Uusi versio: {latest_version}",
        ]

        if manifest.release_notes:
            text_parts.extend(["", "Muutokset:"])
            text_parts.extend(f"- {note}" for note in manifest.release_notes[:8])

        if open_url:
            text_parts.extend(["", "Haluatko avata lataussivun selaimeen?"])
            answer = messagebox.askyesno(
                config.APP_NAME,
                "\n".join(text_parts),
                parent=self.app,
            )

            if answer:
                try:
                    webbrowser.open(open_url)
                except Exception as exc:
                    messagebox.showwarning(
                        config.APP_NAME,
                        (
                            "Lataussivua ei voitu avata.\n\n"
                            f"{exc}"
                        ),
                        parent=self.app,
                    )
            return

        messagebox.showinfo(
            config.APP_NAME,
            "\n".join(text_parts),
            parent=self.app,
        )


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
        text = _clean_text(item, limit=180)
        if text:
            notes.append(text)

    return notes[:20]


def _is_safe_http_url(value: str) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except Exception:
        return False

    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)