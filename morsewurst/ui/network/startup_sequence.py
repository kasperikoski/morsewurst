# ============================================================
# morsewurst/ui/network/startup_sequence.py
# ============================================================

from __future__ import annotations

import time
import tkinter as tk

import morsewurst.config as config
from morsewurst.core.logging_service import log_event, log_exception
from morsewurst.ui.network.startup_screen import NetworkStartupScreen


class NetworkStartupSequenceMixin:
    """Owns the lobby startup splash and network readiness gate."""

    def _init_network_startup_state(self) -> None:
        self._network_startup_screen: NetworkStartupScreen | None = None
        self._network_startup_started_at = 0.0
        self._network_startup_deadline_monotonic = 0.0
        self._network_startup_complete = False
        self._network_initial_queries_started = False
        self._network_startup_after_id: str | None = None
        self._network_ready_poll_after_id: str | None = None

    def _show_network_window(self) -> None:
        try:
            self.update_idletasks()
            self._center_on_parent()
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _start_network_startup_sequence(self) -> None:
        if self._network_startup_screen is not None:
            return

        self._network_startup_complete = False
        self._network_initial_queries_started = False
        self._network_startup_started_at = time.monotonic()
        log_event(
            "network",
            "network.startup.started",
            message="Network startup sequence started.",
            context={"server_uri": self._server_uri()},
        )

        timeout_seconds = max(
            1.0,
            float(getattr(config, "NETWORK_STARTUP_READY_TIMEOUT_SECONDS", 8.0)),
        )
        self._network_startup_deadline_monotonic = (
            self._network_startup_started_at + timeout_seconds
        )

        self.status_var.set(
            self.app.i18n.t("network.startup.state.starting", "STARTING")
        )
        self.room_status_var.set(
            self.app.i18n.t(
                "network.startup.message.starting",
                "Starting Morsewurst Network.",
            )
        )

        self._network_startup_screen = NetworkStartupScreen(self.app)
        self._network_startup_screen.show()
        self._network_startup_status(
            self.app.i18n.t(
                "network.startup.status.engine",
                "Starting network engine.",
            ),
            8,
        )

        try:
            self._network_startup_after_id = self.after(
                120,
                self._connect_network_lobby_presence,
            )
        except Exception:
            self._connect_network_lobby_presence()

    def _connect_network_lobby_presence(self) -> None:
        self._network_startup_after_id = None
        self._network_startup_status(
            self.app.i18n.t(
                "network.startup.status.connecting_relay",
                "Connecting to relay.",
            ),
            32,
        )

        try:
            self._ensure_lobby_presence()
        except Exception as exc:
            log_exception(
                "network",
                "network.startup.lobby_presence_failed",
                exc,
                level="warning",
                message="Lobby presence startup failed.",
                context={"server_uri": self._server_uri()},
            )
            self._append_log(
                "warning",
                self.app.i18n.t(
                    "network.startup.log.lobby_presence_failed",
                    "Lobby presence startup failed: {error}",
                    error=str(exc),
                ),
            )

        self._schedule_network_ready_poll(delay_ms=150)

    def _schedule_network_ready_poll(self, *, delay_ms: int) -> None:
        try:
            if self._network_ready_poll_after_id is not None:
                self.after_cancel(self._network_ready_poll_after_id)
        except Exception:
            pass

        try:
            self._network_ready_poll_after_id = self.after(
                max(50, int(delay_ms)),
                self._poll_network_startup_ready,
            )
        except Exception:
            self._network_ready_poll_after_id = None

    def _poll_network_startup_ready(self) -> None:
        self._network_ready_poll_after_id = None

        manager = getattr(self.app, "network_manager", None)
        ready = False

        if manager is not None:
            try:
                ready = bool(getattr(manager, "control_channel_ready", False))
            except Exception:
                ready = False

        if ready:
            log_event(
                "network",
                "network.startup.ready_detected",
                message="Network startup detected a ready control channel.",
                context={"server_uri": self._server_uri()},
            )
            self._network_startup_status(
                self.app.i18n.t(
                    "network.startup.status.loading_public_rooms",
                    "Loading public rooms.",
                ),
                72,
            )
            self._start_initial_network_queries()
            self._finish_network_startup(
                final_status=self.app.i18n.t("network.status.standby", "STANDBY"),
                final_message=self.app.i18n.t("network.startup.message.ready", "Ready."),
            )
            return

        now = time.monotonic()
        if now >= self._network_startup_deadline_monotonic:
            log_event(
                "network",
                "network.startup.timeout",
                level="warning",
                message="Network startup timed out; connection will continue retrying in background.",
                context={
                    "server_uri": self._server_uri(),
                    "timeout_seconds": round(self._network_startup_deadline_monotonic - self._network_startup_started_at, 3),
                },
            )
            self._network_startup_status(
                self.app.i18n.t(
                    "network.startup.status.retrying_background",
                    "Connection is retrying in background.",
                ),
                88,
            )
            self._start_initial_network_queries()
            self._finish_network_startup(
                final_status=self.app.i18n.t("network.status.retrying", "RETRYING"),
                final_message=self.app.i18n.t(
                    "network.startup.message.retrying_background",
                    "Network is still connecting. Retrying in background.",
                ),
            )
            return

        total = max(
            1.0,
            self._network_startup_deadline_monotonic - self._network_startup_started_at,
        )
        elapsed = max(0.0, now - self._network_startup_started_at)
        progress = min(68.0, 32.0 + (elapsed / total) * 36.0)

        self._network_startup_status(
            self.app.i18n.t(
                "network.startup.status.connecting_relay",
                "Connecting to relay.",
            ),
            progress,
        )
        self._schedule_network_ready_poll(delay_ms=150)

    def _start_initial_network_queries(self) -> None:
        if self._network_initial_queries_started:
            return

        self._network_initial_queries_started = True

        try:
            self._request_initial_server_snapshot()
        except Exception as exc:
            log_exception(
                "network",
                "network.startup.initial_server_snapshot_failed",
                exc,
                level="warning",
                message="Initial server snapshot failed.",
                context={"server_uri": self._server_uri()},
            )
            self._append_log(
                "warning",
                self.app.i18n.t(
                    "network.startup.log.initial_server_snapshot_failed",
                    "Initial server snapshot failed: {error}",
                    error=str(exc),
                ),
            )

        try:
            if not self.public_rooms:
                self._refresh_public_rooms_async(silent=True)
        except Exception as exc:
            log_exception(
                "network",
                "network.startup.initial_public_rooms_failed",
                exc,
                level="warning",
                message="Initial public room refresh failed.",
                context={"server_uri": self._server_uri()},
            )
            self._append_log(
                "warning",
                self.app.i18n.t(
                    "network.startup.log.initial_public_room_refresh_failed",
                    "Initial public room refresh failed: {error}",
                    error=str(exc),
                ),
            )

        try:
            self._schedule_server_info_auto_refresh(
                delay_ms=max(5, int(self._server_info_refresh_seconds)) * 1000
            )
        except Exception:
            pass

    def _finish_network_startup(
        self,
        *,
        final_status: str,
        final_message: str,
    ) -> None:
        self._network_startup_complete = True
        log_event(
            "network",
            "network.startup.success" if final_status != self.app.i18n.t("network.status.retrying", "RETRYING") else "network.startup.background_retry",
            message="Network startup sequence finished.",
            context={
                "server_uri": self._server_uri(),
                "final_status": final_status,
                "final_message": final_message,
                "elapsed_ms": int((time.monotonic() - self._network_startup_started_at) * 1000),
            },
        )
        self.status_var.set(final_status)
        self.room_status_var.set(final_message)
        self._network_startup_status(
            self.app.i18n.t("network.startup.status.ready", "Ready."),
            100,
        )

        min_ms = int(getattr(config, "NETWORK_STARTUP_SCREEN_MIN_MS", 1800))
        elapsed_ms = int((time.monotonic() - self._network_startup_started_at) * 1000)
        delay_ms = max(0, min_ms - elapsed_ms)

        try:
            self._network_startup_after_id = self.after(
                delay_ms,
                self._close_network_startup_and_show_window,
            )
        except Exception:
            self._close_network_startup_and_show_window()

    def _close_network_startup_and_show_window(self) -> None:
        self._network_startup_after_id = None

        try:
            if self._network_startup_screen is not None:
                self._network_startup_screen.close()
        except Exception:
            pass

        self._network_startup_screen = None
        self._show_network_window()

    def _network_startup_status(self, text: str, progress_percent: float) -> None:
        try:
            if self._network_startup_screen is not None:
                self._network_startup_screen.status(text, progress_percent)
        except Exception:
            pass

    def _cancel_network_startup_sequence(self) -> None:
        complete = bool(self._network_startup_complete)
        log_event(
            "network",
            "network.startup.cleanup" if complete else "network.startup.cancelled",
            message=(
                "Network startup sequence cleanup started."
                if complete
                else "Network startup sequence was cancelled."
            ),
            context={"server_uri": self._server_uri(), "complete": complete},
        )
        for attr_name in (
            "_network_startup_after_id",
            "_network_ready_poll_after_id",
        ):
            after_id = getattr(self, attr_name, None)
            if after_id is None:
                continue

            try:
                self.after_cancel(after_id)
            except Exception:
                pass

            try:
                setattr(self, attr_name, None)
            except Exception:
                pass

        try:
            if self._network_startup_screen is not None:
                self._network_startup_screen.close()
        except Exception:
            pass

        self._network_startup_screen = None