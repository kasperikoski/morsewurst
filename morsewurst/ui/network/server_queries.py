# ============================================================
# morsewurst/ui/network/server_queries.py
# ============================================================

from __future__ import annotations

import queue
import threading
import time

from morsewurst.network.defaults import PUBLIC_ROOMS_REFRESH_SECONDS
from morsewurst.network.public_rooms import (
    PublicRoom,
    fetch_public_rooms,
    fetch_server_info,
    ping_server,
)

class NetworkServerQueriesMixin:
    def _refresh_public_rooms_async(self, *, force: bool = False, silent: bool = False) -> None:
        if self._public_rooms_loading:
            if force and not silent:
                self.public_rooms_status_var.set(self.tr("network.public_rooms.refresh_already_running"))
            return

        self._public_rooms_loading = True
        self._public_rooms_request_seq += 1
        request_id = self._public_rooms_request_seq

        if not silent:
            self.public_rooms_status_var.set(self.tr("network.public_rooms.refreshing"))
            if not self.public_rooms:
                self._render_public_rooms()

        thread = threading.Thread(
            target=self._refresh_public_rooms_worker,
            args=(request_id,),
            daemon=True,
        )
        thread.start()

        self._start_public_rooms_queue_poll()

    def _refresh_public_rooms_worker(self, request_id: int) -> None:
        try:
            rooms = fetch_public_rooms(server_uri=self._server_uri())
            self._public_rooms_result_queue.put((request_id, True, rooms))
        except Exception as exc:
            self._public_rooms_result_queue.put((request_id, False, str(exc)))

    def _start_public_rooms_queue_poll(self) -> None:
        if self._public_rooms_queue_after_id is not None:
            return

        try:
            self._public_rooms_queue_after_id = self.after(100, self._poll_public_rooms_result_queue)
        except Exception:
            self._public_rooms_queue_after_id = None

    def _poll_public_rooms_result_queue(self) -> None:
        self._public_rooms_queue_after_id = None
        handled_current_request = False

        while True:
            try:
                request_id, ok, payload = self._public_rooms_result_queue.get_nowait()
            except queue.Empty:
                break

            if request_id != self._public_rooms_request_seq:
                continue

            handled_current_request = True

            if ok:
                self._apply_public_rooms(payload)  # type: ignore[arg-type]
            else:
                self._public_rooms_failed(str(payload))

        if self._public_rooms_loading and not handled_current_request:
            self._start_public_rooms_queue_poll()

    def _apply_public_rooms(self, rooms: list[PublicRoom]) -> None:
        old_signature = self._public_rooms_signature(self.public_rooms)
        new_rooms = tuple(rooms)
        new_signature = self._public_rooms_signature(new_rooms)

        self._public_rooms_loading = False
        self.public_rooms = new_rooms

        # A successful refresh clears the consecutive failure counter.
        self._public_rooms_failed_attempts = 0

        if self._public_rooms_error_visible:
            self._public_rooms_error_visible = False
            self._clear_notice()

        if old_signature != new_signature:
            self._render_public_rooms()
        else:
            count = len(self.public_rooms)
            self.public_rooms_status_var.set(
                self.tr(self._count_key("network.public_rooms.count", count), count=count)
            )

        if self._public_room_refresh_after_id is not None:
            try:
                self.after_cancel(self._public_room_refresh_after_id)
            except Exception:
                pass

        self._public_room_refresh_after_id = self.after(
            max(1, int(PUBLIC_ROOMS_REFRESH_SECONDS)) * 1000,
            lambda: self._refresh_public_rooms_async(silent=True),
        )

    def _public_rooms_failed(self, message: str) -> None:
        self._public_rooms_loading = False
        self._public_rooms_failed_attempts += 1

        if self.public_rooms:
            count = len(self.public_rooms)
            self.public_rooms_status_var.set(
                self.tr(
                    self._count_key("network.public_rooms.retrying_with_existing", count),
                    count=count,
                )
            )
        else:
            self.public_rooms_status_var.set(self.tr("network.public_rooms.retrying"))

        if not self.public_rooms:
            self._render_public_rooms()

        if self._public_rooms_failed_attempts >= self._public_rooms_error_threshold:
            self._public_rooms_error_visible = True
            self._show_notice(
                self.tr(
                    "network.public_rooms.load_failed",
                    count=self._public_rooms_failed_attempts,
                    message=message,
                ),
                "error",
            )

        if self._public_room_refresh_after_id is not None:
            try:
                self.after_cancel(self._public_room_refresh_after_id)
            except Exception:
                pass

        self._public_room_refresh_after_id = self.after(
            max(1, int(PUBLIC_ROOMS_REFRESH_SECONDS)) * 1000,
            lambda: self._refresh_public_rooms_async(silent=True),
        )

    def _request_initial_server_snapshot(self) -> None:
        self._request_server_info(silent=True)
        self.after(700, lambda: self._request_server_ping(silent=True))

    def _request_server_info(self, *, silent: bool = False) -> None:
        manager = getattr(self.app, "network_manager", None)

        if manager is not None and self._server_is_connected():
            try:
                manager.request_server_info()
                if not silent:
                    self._show_notice(
                        self.tr("network.server_query.info_requested"),
                        "info",
                    )
                return
            except Exception as exc:
                if not silent:
                    self._show_notice(
                        self.tr(
                            "network.server_query.info_request_failed",
                            error=str(exc),
                        ),
                        "warning",
                    )
                return

        if self._server_info_query_running:
            if not silent:
                self._show_notice(
                    self.tr("network.server_query.info_already_running"),
                    "info",
                )
            return

        self._server_info_query_running = True
        self.server_info_error_text = ""

        if not self._latest_server_info():
            self._update_server_info_views()

        if not silent:
            self._show_notice(
                self.tr("network.server_query.requesting_info"),
                "info",
            )

        thread = threading.Thread(
            target=self._server_info_query_worker,
            args=(silent,),
            daemon=True,
        )
        thread.start()

        self._start_server_query_queue_poll()

    def _request_server_ping(self, *, silent: bool = False) -> None:
        manager = getattr(self.app, "network_manager", None)

        if manager is not None and self._server_is_connected():
            try:
                manager.request_server_ping()
                if not silent:
                    self._show_notice(
                        self.tr("network.server_query.ping_requested"),
                        "info",
                    )
                return
            except Exception as exc:
                if not silent:
                    self._show_notice(
                        self.tr(
                            "network.server_query.ping_failed",
                            error=str(exc),
                        ),
                        "warning",
                    )
                return

        if self._server_ping_query_running:
            if not silent:
                self._show_notice(
                    self.tr("network.server_query.ping_already_running"),
                    "info",
                )
            return

        self._server_ping_query_running = True

        if not silent:
            self._show_notice(
                self.tr("network.server_query.testing_ping"),
                "info",
            )

        thread = threading.Thread(
            target=self._server_ping_query_worker,
            daemon=True,
        )
        thread.start()

        self._start_server_query_queue_poll()

    def _schedule_server_info_auto_refresh(self, *, delay_ms: int) -> None:
        try:
            if self._server_info_refresh_after_id is not None:
                self.after_cancel(self._server_info_refresh_after_id)
        except Exception:
            pass

        try:
            self._server_info_refresh_after_id = self.after(
                max(1000, int(delay_ms)),
                self._auto_refresh_server_info,
            )
        except Exception:
            self._server_info_refresh_after_id = None

    def _auto_refresh_server_info(self) -> None:
        self._server_info_refresh_after_id = None

        try:
            self._request_server_info(silent=True)
        except Exception:
            pass

        self._schedule_server_info_auto_refresh(
            delay_ms=max(5, int(self._server_info_refresh_seconds)) * 1000
        )

    def _server_info_query_worker(self, silent: bool = False) -> None:
        try:
            info = fetch_server_info(server_uri=self._server_uri())
            self._server_query_result_queue.put(("server_info", True, info, silent))
        except Exception as exc:
            self._server_query_result_queue.put(("server_info", False, str(exc), silent))

    def _server_ping_query_worker(self) -> None:
        try:
            pong = ping_server(server_uri=self._server_uri())
            self._server_query_result_queue.put(("server_pong", True, pong, False))
        except Exception as exc:
            self._server_query_result_queue.put(("server_pong", False, str(exc), False))

    def _start_server_query_queue_poll(self) -> None:
        if self._server_query_after_id is not None:
            return

        try:
            self._server_query_after_id = self.after(100, self._poll_server_query_result_queue)
        except Exception:
            self._server_query_after_id = None

    def _poll_server_query_result_queue(self) -> None:
        self._server_query_after_id = None

        handled_any = False

        while True:
            try:
                kind, ok, payload, silent = self._server_query_result_queue.get_nowait()
            except queue.Empty:
                break

            handled_any = True

            if kind == "server_info":
                self._server_info_query_running = False

            if kind == "server_pong":
                self._server_ping_query_running = False

            if not ok:
                message = str(payload)

                if kind == "server_info":
                    self.server_info_error_text = message
                    self._update_server_info_views()
                    failure_text = self.tr(
                        "network.server_query.query_failed",
                        message=message,
                    )
                    self._set_network_quality(
                        "server_not_responding",
                        failure_text,
                        force=True,
                    )

                    if not silent:
                        self._show_notice(failure_text, "warning")

                if kind == "server_pong":
                    failure_text = self.tr(
                        "network.server_query.ping_failed",
                        error=message,
                    )
                    self._set_network_quality(
                        "server_not_responding",
                        failure_text,
                        force=True,
                    )
                    if not silent:
                        self._show_notice(failure_text, "warning")

                continue

            if kind == "server_info" and isinstance(payload, dict):
                self.server_info_error_text = ""
                payload["client_received_time"] = time.time()
                payload["client_received_monotonic"] = time.monotonic()
                self.last_server_info = payload
                self._update_server_info_views()

                if not silent:
                    self._show_notice(
                        self.tr("network.server_query.info_updated"),
                        "success",
                    )
                continue

            if kind == "server_pong" and isinstance(payload, dict):
                payload["client_received_time"] = time.time()
                payload["client_received_monotonic"] = time.monotonic()
                self.last_server_pong = payload
                self._update_server_info_views()
                self._update_network_quality_from_server_pong()

                if not silent:
                    ping_ms = self._latest_server_ping_ms()
                    if ping_ms is not None:
                        self._append_log(
                            "success",
                            self.tr(
                                "network.server_query.ping_result",
                                ping_ms=ping_ms,
                            ),
                        )
                    else:
                        self._append_log(
                            "success",
                            self.tr("network.server_query.ping_received"),
                        )
                continue

        if (
            self._server_info_query_running
            or self._server_ping_query_running
            or not self._server_query_result_queue.empty()
        ):
            self._start_server_query_queue_poll()
            return

        if handled_any:
            self._update_server_info_views()

    def _refresh_server_summary(self) -> None:
        self._update_server_info_views()

        try:
            if self.winfo_exists():
                self._server_summary_after_id = self.after(1000, self._refresh_server_summary)
        except Exception:
            pass

    def _update_server_info_views(self) -> None:
        try:
            self.server_summary_var.set(self._format_server_summary())
            self.server_room_status_var.set(self._format_server_room_status())
            self._update_server_info_window_values()
        except Exception:
            pass