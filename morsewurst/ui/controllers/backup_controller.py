# ============================================================
# morsewurst/ui/controllers/backup_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

import morsewurst.config as config
from morsewurst.core.app_logging import log_app_event, log_app_exception
from morsewurst.storage.backup_service import BackupRecord, BackupService

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class BackupController:
    """Owns active-profile backup service access and startup backup checks."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def service(self) -> BackupService | None:
        profile = getattr(self.app.profile_controller, "active_profile", None)
        if profile is None:
            return None

        return BackupService(
            profile_dir=config.DATA_DIR,
            profile_id=profile.id,
            profile_name=profile.name,
            db_path=config.DB_PATH,
        )

    def create_startup_backup_if_due(self) -> BackupRecord | None:
        service = self.service()
        if service is None:
            log_app_event(
                "app.backup.startup_skipped_no_profile",
                message="Startup backup check was skipped because no active profile exists.",
            )
            return None

        try:
            log_app_event(
                "app.backup.auto_check_started",
                message="Startup profile backup check started.",
                context={
                    "profile_id": service.profile_id,
                    "backups_dir": str(service.backups_dir),
                },
            )
            return service.create_automatic_backup_if_due()
        except Exception as exc:
            log_app_exception(
                "app.backup.auto_check_failed",
                exc,
                level="warning",
                message="Startup profile backup check failed.",
                context={"profile_id": service.profile_id},
            )
            return None
