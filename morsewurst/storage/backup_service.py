# ============================================================
# morsewurst/storage/backup_service.py
# ============================================================

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import morsewurst.config as config
from morsewurst.core.app_logging import log_app_event, log_app_exception


BACKUP_MANIFEST_NAME = "backup_manifest.json"
BACKUP_DATABASE_NAME = "morsewurst.sqlite3"
BACKUP_UI_SETTINGS_NAME = "ui_settings.json"
BACKUP_NETWORK_SETTINGS_NAME = "network_settings.json"
BACKUP_STATE_NAME = "backup_state.json"


@dataclass(frozen=True, slots=True)
class BackupRecord:
    path: Path
    profile_id: str
    profile_name: str
    created_at: str
    reason: str
    app_version: str
    sending_sessions: int
    koch_sessions: int
    size_bytes: int
    manifest: dict[str, Any]

    @property
    def created_datetime(self) -> datetime | None:
        return _parse_datetime(self.created_at)


class BackupError(RuntimeError):
    pass


class BackupService:
    """Create, list, prune and restore per-profile backup snapshots.

    Backups are stored inside the active profile directory. The database is
    copied with SQLite's backup API so WAL-mode data is captured as a consistent
    snapshot without copying -wal or -shm files directly.
    """

    def __init__(
        self,
        *,
        profile_dir: Path,
        profile_id: str,
        profile_name: str,
        db_path: Path | None = None,
    ) -> None:
        self.profile_dir = Path(profile_dir)
        self.profile_id = str(profile_id or "profile")
        self.profile_name = str(profile_name or self.profile_id)
        self.db_path = Path(db_path or (self.profile_dir / BACKUP_DATABASE_NAME))
        self.backups_dir = self.profile_dir / str(getattr(config, "PROFILE_BACKUP_DIRNAME", "backups"))
        self.state_path = self.backups_dir / BACKUP_STATE_NAME

    def should_create_automatic_backup(self, *, now: datetime | None = None) -> bool:
        if not bool(getattr(config, "PROFILE_BACKUP_AUTO_ENABLED", True)):
            return False

        if not self.db_path.exists():
            return False

        interval_hours = max(1.0, float(getattr(config, "PROFILE_BACKUP_INTERVAL_HOURS", 24)))
        now = _ensure_aware_utc(now or datetime.now(UTC))

        last_at = self._last_successful_backup_at()
        if last_at is None:
            return True

        return now - last_at >= timedelta(hours=interval_hours)

    def create_automatic_backup_if_due(self) -> BackupRecord | None:
        if not self.should_create_automatic_backup():
            log_app_event(
                "app.backup.skipped_recent",
                message="Automatic profile backup was skipped because a recent backup exists.",
                context={
                    "profile_id": self.profile_id,
                    "backups_dir": str(self.backups_dir),
                    "interval_hours": float(getattr(config, "PROFILE_BACKUP_INTERVAL_HOURS", 24)),
                },
            )
            return None

        return self.create_backup(reason="automatic_startup")

    def create_backup(self, *, reason: str = "manual", prune: bool = True) -> BackupRecord:
        started_at = datetime.now(UTC)
        reason = _safe_reason(reason)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        log_app_event(
            "app.backup.started",
            message="Profile backup creation started.",
            context={
                "profile_id": self.profile_id,
                "profile_name": self.profile_name,
                "reason": reason,
                "backups_dir": str(self.backups_dir),
                "db_path": str(self.db_path),
            },
        )

        try:
            if not self.db_path.exists():
                raise BackupError(f"Database file does not exist: {self.db_path}")

            timestamp = started_at.strftime("%Y-%m-%d_%H-%M-%S")
            backup_path = self._unique_backup_path(timestamp, reason)

            with tempfile.TemporaryDirectory(prefix="morsewurst_backup_") as temp_name:
                temp_dir = Path(temp_name)
                snapshot_path = temp_dir / BACKUP_DATABASE_NAME
                self._snapshot_database(snapshot_path)

                sending_sessions, koch_sessions = self._database_counts(snapshot_path)
                manifest = self._manifest(
                    created_at=started_at,
                    reason=reason,
                    sending_sessions=sending_sessions,
                    koch_sessions=koch_sessions,
                )

                self._write_zip(
                    backup_path=backup_path,
                    snapshot_path=snapshot_path,
                    manifest=manifest,
                )

            size_bytes = backup_path.stat().st_size if backup_path.exists() else 0
            record = self._record_from_manifest(backup_path, manifest, size_bytes=size_bytes)
            self._write_state(record)
            deleted = self.prune_old_backups() if prune else 0

            log_app_event(
                "app.backup.completed",
                message="Profile backup was created successfully.",
                context={
                    "profile_id": self.profile_id,
                    "reason": reason,
                    "backup_path": str(backup_path),
                    "size_bytes": size_bytes,
                    "sending_sessions": sending_sessions,
                    "koch_sessions": koch_sessions,
                    "deleted_old_backups": deleted,
                    "elapsed_ms": round((datetime.now(UTC) - started_at).total_seconds() * 1000.0, 2),
                },
            )
            return record
        except Exception as exc:
            log_app_exception(
                "app.backup.failed",
                exc,
                message="Profile backup creation failed.",
                context={
                    "profile_id": self.profile_id,
                    "reason": reason,
                    "backups_dir": str(self.backups_dir),
                    "db_path": str(self.db_path),
                },
            )
            raise

    def list_backups(self) -> list[BackupRecord]:
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        records: list[BackupRecord] = []

        for path in self.backups_dir.glob("*.zip"):
            record = self.read_backup_record(path)
            if record is not None:
                records.append(record)

        records.sort(
            key=lambda item: item.created_datetime or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return records

    def read_backup_record(self, path: Path) -> BackupRecord | None:
        path = Path(path)
        try:
            with zipfile.ZipFile(path, "r") as archive:
                with archive.open(BACKUP_MANIFEST_NAME, "r") as source:
                    manifest = json.loads(source.read().decode("utf-8"))
            return self._record_from_manifest(path, manifest)
        except Exception as exc:
            log_app_exception(
                "app.backup.manifest_read_failed",
                exc,
                level="warning",
                message="Backup manifest could not be read.",
                context={"path": str(path)},
            )
            return None

    def restore_backup(self, backup_path: Path) -> None:
        backup_path = Path(backup_path)

        log_app_event(
            "app.backup.restore_started",
            message="Profile backup restore started.",
            context={"profile_id": self.profile_id, "backup_path": str(backup_path)},
        )

        try:
            record = self.read_backup_record(backup_path)
            if record is None:
                raise BackupError("Backup manifest could not be read.")

            self._validate_backup_zip(backup_path)
            self.profile_dir.mkdir(parents=True, exist_ok=True)

            db_target = self.profile_dir / BACKUP_DATABASE_NAME
            ui_target = self.profile_dir / BACKUP_UI_SETTINGS_NAME
            network_target = self.profile_dir / BACKUP_NETWORK_SETTINGS_NAME

            with tempfile.TemporaryDirectory(prefix="morsewurst_restore_") as temp_name:
                temp_dir = Path(temp_name)
                with zipfile.ZipFile(backup_path, "r") as archive:
                    archive.extract(BACKUP_DATABASE_NAME, temp_dir)
                    if BACKUP_UI_SETTINGS_NAME in archive.namelist():
                        archive.extract(BACKUP_UI_SETTINGS_NAME, temp_dir)
                    if BACKUP_NETWORK_SETTINGS_NAME in archive.namelist():
                        archive.extract(BACKUP_NETWORK_SETTINGS_NAME, temp_dir)

                _replace_file(temp_dir / BACKUP_DATABASE_NAME, db_target)
                _remove_if_exists(self.profile_dir / f"{BACKUP_DATABASE_NAME}-wal")
                _remove_if_exists(self.profile_dir / f"{BACKUP_DATABASE_NAME}-shm")

                if (temp_dir / BACKUP_UI_SETTINGS_NAME).exists():
                    _replace_file(temp_dir / BACKUP_UI_SETTINGS_NAME, ui_target)
                else:
                    _remove_if_exists(ui_target)

                if (temp_dir / BACKUP_NETWORK_SETTINGS_NAME).exists():
                    _replace_file(temp_dir / BACKUP_NETWORK_SETTINGS_NAME, network_target)
                else:
                    _remove_if_exists(network_target)

            log_app_event(
                "app.backup.restore_completed",
                message="Profile backup was restored successfully.",
                context={
                    "profile_id": self.profile_id,
                    "backup_path": str(backup_path),
                    "created_at": record.created_at,
                    "reason": record.reason,
                    "sending_sessions": record.sending_sessions,
                    "koch_sessions": record.koch_sessions,
                },
            )
        except Exception as exc:
            log_app_exception(
                "app.backup.restore_failed",
                exc,
                message="Profile backup restore failed.",
                context={"profile_id": self.profile_id, "backup_path": str(backup_path)},
            )
            raise

    def prune_old_backups(self) -> int:
        records = self.list_backups()
        if not records:
            return 0

        max_total = max(1, int(getattr(config, "PROFILE_BACKUP_MAX_TOTAL", 200)))
        if len(records) <= max_total:
            return 0

        log_app_event(
            "app.backup.prune_started",
            message="Profile backup pruning started.",
            context={
                "profile_id": self.profile_id,
                "backup_count": len(records),
                "max_total": max_total,
            },
        )

        keep = self._smart_keep_set(records)
        ordered_oldest = sorted(
            records,
            key=lambda item: item.created_datetime or datetime.min.replace(tzinfo=UTC),
        )

        to_delete: list[BackupRecord] = []
        remaining = len(records)

        for record in ordered_oldest:
            if remaining <= max_total:
                break
            if record.path in keep:
                continue
            to_delete.append(record)
            remaining -= 1

        if remaining > max_total:
            for record in ordered_oldest:
                if remaining <= max_total:
                    break
                if record in to_delete:
                    continue
                to_delete.append(record)
                remaining -= 1

        deleted = 0
        for record in to_delete:
            try:
                record.path.unlink(missing_ok=True)
                deleted += 1
            except Exception as exc:
                log_app_exception(
                    "app.backup.prune_delete_failed",
                    exc,
                    level="warning",
                    message="Old profile backup could not be deleted.",
                    context={"profile_id": self.profile_id, "backup_path": str(record.path)},
                )

        log_app_event(
            "app.backup.prune_completed",
            message="Profile backup pruning completed.",
            context={
                "profile_id": self.profile_id,
                "backup_count_before": len(records),
                "deleted": deleted,
                "max_total": max_total,
            },
        )
        return deleted

    def _snapshot_database(self, destination: Path) -> None:
        source = sqlite3.connect(self.db_path)
        try:
            dest = sqlite3.connect(destination)
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()

    def _database_counts(self, db_path: Path) -> tuple[int, int]:
        conn = sqlite3.connect(db_path)
        try:
            return (
                _count_table_rows(conn, "sessions"),
                _count_table_rows(conn, "koch_sessions"),
            )
        finally:
            conn.close()

    def _manifest(
        self,
        *,
        created_at: datetime,
        reason: str,
        sending_sessions: int,
        koch_sessions: int,
    ) -> dict[str, Any]:
        included_files = [BACKUP_DATABASE_NAME, BACKUP_MANIFEST_NAME]

        if (self.profile_dir / BACKUP_UI_SETTINGS_NAME).exists():
            included_files.append(BACKUP_UI_SETTINGS_NAME)
        if (self.profile_dir / BACKUP_NETWORK_SETTINGS_NAME).exists():
            included_files.append(BACKUP_NETWORK_SETTINGS_NAME)

        return {
            "app": getattr(config, "APP_NAME", "Morsewurst"),
            "backup_version": 1,
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "created_at": _iso(created_at),
            "reason": reason,
            "app_version": getattr(config, "APP_VERSION", ""),
            "database_file": BACKUP_DATABASE_NAME,
            "included_files": included_files,
            "statistics": {
                "sending_sessions": int(sending_sessions),
                "koch_sessions": int(koch_sessions),
            },
        }

    def _write_zip(
        self,
        *,
        backup_path: Path,
        snapshot_path: Path,
        manifest: dict[str, Any],
    ) -> None:
        temp_zip = backup_path.with_suffix(backup_path.suffix + ".tmp")
        with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.write(snapshot_path, BACKUP_DATABASE_NAME)
            ui_path = self.profile_dir / BACKUP_UI_SETTINGS_NAME
            network_path = self.profile_dir / BACKUP_NETWORK_SETTINGS_NAME
            if ui_path.exists():
                archive.write(ui_path, BACKUP_UI_SETTINGS_NAME)
            if network_path.exists():
                archive.write(network_path, BACKUP_NETWORK_SETTINGS_NAME)
            archive.writestr(
                BACKUP_MANIFEST_NAME,
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
        temp_zip.replace(backup_path)

    def _validate_backup_zip(self, backup_path: Path) -> None:
        with zipfile.ZipFile(backup_path, "r") as archive:
            names = set(archive.namelist())
            if BACKUP_MANIFEST_NAME not in names:
                raise BackupError("Backup manifest is missing.")
            if BACKUP_DATABASE_NAME not in names:
                raise BackupError("Database snapshot is missing from backup.")
            bad = archive.testzip()
            if bad is not None:
                raise BackupError(f"Backup zip failed integrity check at: {bad}")

    def _record_from_manifest(
        self,
        path: Path,
        manifest: dict[str, Any],
        *,
        size_bytes: int | None = None,
    ) -> BackupRecord:
        stats = manifest.get("statistics") if isinstance(manifest.get("statistics"), dict) else {}
        return BackupRecord(
            path=Path(path),
            profile_id=str(manifest.get("profile_id") or self.profile_id),
            profile_name=str(manifest.get("profile_name") or self.profile_name),
            created_at=str(manifest.get("created_at") or ""),
            reason=str(manifest.get("reason") or "unknown"),
            app_version=str(manifest.get("app_version") or ""),
            sending_sessions=_safe_int(stats.get("sending_sessions"), 0),
            koch_sessions=_safe_int(stats.get("koch_sessions"), 0),
            size_bytes=int(size_bytes if size_bytes is not None else (path.stat().st_size if path.exists() else 0)),
            manifest=dict(manifest),
        )

    def _write_state(self, record: BackupRecord) -> None:
        payload = {
            "last_successful_backup_at": record.created_at,
            "last_backup_path": record.path.name,
            "last_backup_reason": record.reason,
        }
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _last_successful_backup_at(self) -> datetime | None:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            parsed = _parse_datetime(str(data.get("last_successful_backup_at") or ""))
            if parsed is not None:
                return parsed
        except Exception:
            pass

        records = self.list_backups()
        return records[0].created_datetime if records else None

    def _unique_backup_path(self, timestamp: str, reason: str) -> Path:
        profile_part = _safe_filename(self.profile_id)
        reason_part = _safe_filename(reason)
        base_name = f"{profile_part}_{timestamp}_{reason_part}.zip"
        candidate = self.backups_dir / base_name
        counter = 1
        while candidate.exists():
            candidate = self.backups_dir / f"{profile_part}_{timestamp}_{reason_part}_{counter}.zip"
            counter += 1
        return candidate

    def _smart_keep_set(self, records: Iterable[BackupRecord]) -> set[Path]:
        now = datetime.now(UTC)
        keep: set[Path] = set()
        dated = [record for record in records if record.created_datetime is not None]
        dated.sort(key=lambda item: item.created_datetime or datetime.min.replace(tzinfo=UTC), reverse=True)

        for record in dated[: max(0, int(getattr(config, "PROFILE_BACKUP_KEEP_ALWAYS_LAST", 10)))]:
            keep.add(record.path)

        daily_limit = max(0, int(getattr(config, "PROFILE_BACKUP_KEEP_DAILY_DAYS", 30)))
        weekly_limit = max(0, int(getattr(config, "PROFILE_BACKUP_KEEP_WEEKLY_WEEKS", 12)))
        monthly_limit = max(0, int(getattr(config, "PROFILE_BACKUP_KEEP_MONTHLY_MONTHS", 12)))

        daily_seen: set[str] = set()
        weekly_seen: set[tuple[int, int]] = set()
        monthly_seen: set[tuple[int, int]] = set()

        for record in dated:
            created = record.created_datetime
            if created is None:
                continue

            age_days = (now - created).days
            day_key = created.date().isoformat()
            if age_days <= daily_limit and day_key not in daily_seen:
                keep.add(record.path)
                daily_seen.add(day_key)

            iso_year, iso_week, _ = created.isocalendar()
            week_key = (int(iso_year), int(iso_week))
            if age_days <= weekly_limit * 7 and week_key not in weekly_seen:
                keep.add(record.path)
                weekly_seen.add(week_key)

            month_key = (created.year, created.month)
            month_age = (now.year - created.year) * 12 + (now.month - created.month)
            if month_age <= monthly_limit and month_key not in monthly_seen:
                keep.add(record.path)
                monthly_seen.add(month_key)

        return keep


def _count_table_rows(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if row is None:
        return 0
    count_row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(count_row[0] if count_row is not None else 0)


def _replace_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target.with_suffix(target.suffix + ".restore_tmp")
    if temp_target.exists():
        temp_target.unlink()
    shutil.copy2(source, temp_target)
    os.replace(temp_target, target)


def _remove_if_exists(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _ensure_aware_utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _ensure_aware_utc(datetime.fromisoformat(text))
    except Exception:
        return None


def _safe_reason(value: str) -> str:
    reason = str(value or "manual").strip().lower()
    return reason if reason in {"automatic_startup", "manual", "pre_restore", "profile_delete"} else "manual"


def _safe_filename(value: str) -> str:
    text = str(value or "backup").strip().lower()
    safe = []
    for ch in text:
        if ch.isalnum() or ch in {"-", "_", "."}:
            safe.append(ch)
        else:
            safe.append("-")
    result = "".join(safe).strip("-._")
    return result[:64] or "backup"
