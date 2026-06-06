from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path

from morsewurst.storage.backup_service import (
    BACKUP_DATABASE_NAME,
    BACKUP_MANIFEST_NAME,
    BACKUP_NETWORK_SETTINGS_NAME,
    BACKUP_UI_SETTINGS_NAME,
    BackupService,
)


def _make_profile(tmp_path: Path) -> Path:
    profile = tmp_path / "profiles" / "kasperi"
    profile.mkdir(parents=True)

    conn = sqlite3.connect(profile / BACKUP_DATABASE_NAME)
    try:
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE koch_sessions (id INTEGER PRIMARY KEY)")
        conn.executemany("INSERT INTO sessions DEFAULT VALUES", [() for _ in range(3)])
        conn.executemany("INSERT INTO koch_sessions DEFAULT VALUES", [() for _ in range(2)])
        conn.commit()
    finally:
        conn.close()

    (profile / BACKUP_UI_SETTINGS_NAME).write_text('{"language":"fi"}', encoding="utf-8")
    (profile / BACKUP_NETWORK_SETTINGS_NAME).write_text('{"callsign":"TEST"}', encoding="utf-8")
    return profile


def test_profile_backup_creates_zip_with_manifest_and_sqlite_snapshot(tmp_path: Path) -> None:
    profile = _make_profile(tmp_path)
    service = BackupService(
        profile_dir=profile,
        profile_id="kasperi",
        profile_name="Kasperi",
        db_path=profile / BACKUP_DATABASE_NAME,
    )

    record = service.create_backup(reason="manual")

    assert record.path.exists()
    assert record.sending_sessions == 3
    assert record.koch_sessions == 2

    with zipfile.ZipFile(record.path, "r") as archive:
        names = set(archive.namelist())
        assert BACKUP_DATABASE_NAME in names
        assert BACKUP_MANIFEST_NAME in names
        assert BACKUP_UI_SETTINGS_NAME in names
        assert BACKUP_NETWORK_SETTINGS_NAME in names

    records = service.list_backups()
    assert [item.path for item in records] == [record.path]
    assert records[0].reason == "manual"


def test_profile_backup_restore_replaces_database_and_settings(tmp_path: Path) -> None:
    profile = _make_profile(tmp_path)
    service = BackupService(
        profile_dir=profile,
        profile_id="kasperi",
        profile_name="Kasperi",
        db_path=profile / BACKUP_DATABASE_NAME,
    )
    record = service.create_backup(reason="manual")

    conn = sqlite3.connect(profile / BACKUP_DATABASE_NAME)
    try:
        conn.execute("DELETE FROM sessions")
        conn.commit()
    finally:
        conn.close()
    (profile / BACKUP_UI_SETTINGS_NAME).write_text('{"language":"en"}', encoding="utf-8")

    service.restore_backup(record.path)

    conn = sqlite3.connect(profile / BACKUP_DATABASE_NAME)
    try:
        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    finally:
        conn.close()

    assert count == 3
    assert '"language":"fi"' in (profile / BACKUP_UI_SETTINGS_NAME).read_text(encoding="utf-8")
