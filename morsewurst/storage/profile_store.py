# ============================================================
# morsewurst/storage/profile_store.py
# ============================================================

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import morsewurst.config as config


PROFILE_REGISTRY_VERSION = 1
DEFAULT_PROFILE_NAME = "Default"

DATABASE_FILENAME = "morsewurst.sqlite3"
UI_SETTINGS_FILENAME = "ui_settings.json"
NETWORK_SETTINGS_FILENAME = "network_settings.json"
DEBUG_DIRNAME = "debug"


class ProfileError(RuntimeError):
    pass


class DuplicateProfileError(ProfileError):
    pass


class ProfileNotFoundError(ProfileError):
    pass


class LastProfileError(ProfileError):
    pass


@dataclass(slots=True)
class UserProfile:
    id: str
    name: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class ProfileRegistry:
    version: int
    active_profile_id: str
    profiles: list[UserProfile]


def normalize_profile_id(name: object) -> str:
    text = str(name or "").strip()
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-._")
    return text[:48] or "user"


def clean_profile_name(name: object) -> str:
    text = str(name or "").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    text = "".join(ch for ch in text if ch.isprintable())
    return text[:80].strip()


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ProfileStore:
    """Persistent storage for local Morsewurst user profiles."""

    def __init__(
        self,
        *,
        registry_path: Path | None = None,
        profiles_dir: Path | None = None,
        backup_dir: Path | None = None,
        base_data_dir: Path | None = None,
    ) -> None:
        self.registry_path = registry_path or config.PROFILE_REGISTRY_PATH
        self.profiles_dir = profiles_dir or config.PROFILES_DIR
        self.backup_dir = backup_dir or config.BACKUP_DIR
        self.base_data_dir = base_data_dir or config.BASE_DATA_DIR

    def prepare_active_profile(self, *, default_name: str = DEFAULT_PROFILE_NAME) -> UserProfile:
        """Ensure profiles exist, migrate legacy root data, and apply active paths."""

        registry = self.load_or_bootstrap(default_name=default_name)
        active = self.active_profile(registry)

        active_dir = self.profile_dir(active.id)
        active_dir.mkdir(parents=True, exist_ok=True)
        (active_dir / DEBUG_DIRNAME).mkdir(parents=True, exist_ok=True)

        config.set_active_data_dir(active_dir)

        return active

    def load_or_bootstrap(self, *, default_name: str = DEFAULT_PROFILE_NAME) -> ProfileRegistry:
        self.base_data_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        if not self.registry_path.exists():
            return self.bootstrap_legacy_profile(default_name=default_name)

        registry = self.load()

        if not registry.profiles:
            return self.bootstrap_legacy_profile(default_name=default_name)

        if registry.active_profile_id not in {profile.id for profile in registry.profiles}:
            registry.active_profile_id = registry.profiles[0].id
            self.save(registry)

        return registry

    def bootstrap_legacy_profile(self, *, default_name: str = DEFAULT_PROFILE_NAME) -> ProfileRegistry:
        """Create the first profile and move old root-level data into it."""

        name = clean_profile_name(default_name) or DEFAULT_PROFILE_NAME
        profile_id = normalize_profile_id(name)
        now = utc_now_iso()

        profile = UserProfile(
            id=profile_id,
            name=name,
            created_at=now,
            updated_at=now,
        )

        profile_dir = self.profile_dir(profile.id)
        profile_dir.mkdir(parents=True, exist_ok=True)

        self._move_legacy_file(DATABASE_FILENAME, profile_dir / DATABASE_FILENAME)
        self._move_legacy_file(f"{DATABASE_FILENAME}-wal", profile_dir / f"{DATABASE_FILENAME}-wal")
        self._move_legacy_file(f"{DATABASE_FILENAME}-shm", profile_dir / f"{DATABASE_FILENAME}-shm")
        self._move_legacy_file(UI_SETTINGS_FILENAME, profile_dir / UI_SETTINGS_FILENAME)
        self._move_legacy_file(NETWORK_SETTINGS_FILENAME, profile_dir / NETWORK_SETTINGS_FILENAME)
        self._move_legacy_dir(DEBUG_DIRNAME, profile_dir / DEBUG_DIRNAME)

        (profile_dir / DEBUG_DIRNAME).mkdir(parents=True, exist_ok=True)

        registry = ProfileRegistry(
            version=PROFILE_REGISTRY_VERSION,
            active_profile_id=profile.id,
            profiles=[profile],
        )

        self.save(registry)
        return registry

    def load(self) -> ProfileRegistry:
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except Exception:
            return ProfileRegistry(
                version=PROFILE_REGISTRY_VERSION,
                active_profile_id="",
                profiles=[],
            )

        if not isinstance(data, dict):
            return ProfileRegistry(
                version=PROFILE_REGISTRY_VERSION,
                active_profile_id="",
                profiles=[],
            )

        profiles: list[UserProfile] = []
        raw_profiles = data.get("profiles")

        if isinstance(raw_profiles, list):
            for item in raw_profiles:
                if not isinstance(item, dict):
                    continue

                profile_id = normalize_profile_id(item.get("id") or item.get("name"))
                name = clean_profile_name(item.get("name")) or profile_id

                profiles.append(
                    UserProfile(
                        id=profile_id,
                        name=name,
                        created_at=str(item.get("created_at") or utc_now_iso()),
                        updated_at=str(item.get("updated_at") or utc_now_iso()),
                    )
                )

        active_profile_id = normalize_profile_id(data.get("active_profile_id"))

        return ProfileRegistry(
            version=int(data.get("version") or PROFILE_REGISTRY_VERSION),
            active_profile_id=active_profile_id,
            profiles=profiles,
        )

    def save(self, registry: ProfileRegistry) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "version": int(registry.version),
            "active_profile_id": registry.active_profile_id,
            "profiles": [asdict(profile) for profile in registry.profiles],
        }

        tmp = self.registry_path.with_suffix(self.registry_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.registry_path)

    def active_profile(self, registry: ProfileRegistry | None = None) -> UserProfile:
        registry = registry or self.load_or_bootstrap()

        for profile in registry.profiles:
            if profile.id == registry.active_profile_id:
                return profile

        if registry.profiles:
            return registry.profiles[0]

        raise ProfileNotFoundError("No user profiles exist.")

    def list_profiles(self) -> list[UserProfile]:
        registry = self.load_or_bootstrap()
        return list(registry.profiles)

    def profile_dir(self, profile_id: str) -> Path:
        clean_id = normalize_profile_id(profile_id)
        return self.profiles_dir / clean_id

    def create_profile(self, name: object) -> UserProfile:
        registry = self.load_or_bootstrap()

        clean_name = clean_profile_name(name)
        if not clean_name:
            raise ProfileError("Profile name is empty.")

        profile_id = normalize_profile_id(clean_name)
        existing_ids = {profile.id for profile in registry.profiles}

        if profile_id in existing_ids:
            raise DuplicateProfileError("A profile with that name already exists.")

        now = utc_now_iso()
        profile = UserProfile(
            id=profile_id,
            name=clean_name,
            created_at=now,
            updated_at=now,
        )

        self.profile_dir(profile.id).mkdir(parents=True, exist_ok=False)
        (self.profile_dir(profile.id) / DEBUG_DIRNAME).mkdir(parents=True, exist_ok=True)

        registry.profiles.append(profile)
        self.save(registry)

        return profile

    def activate_profile(self, profile_id: str) -> UserProfile:
        registry = self.load_or_bootstrap()
        clean_id = normalize_profile_id(profile_id)

        for profile in registry.profiles:
            if profile.id == clean_id:
                registry.active_profile_id = profile.id
                self.save(registry)
                return profile

        raise ProfileNotFoundError("Profile was not found.")

    def rename_profile(self, profile_id: str, new_name: object) -> UserProfile:
        registry = self.load_or_bootstrap()
        old_id = normalize_profile_id(profile_id)

        clean_name = clean_profile_name(new_name)
        if not clean_name:
            raise ProfileError("Profile name is empty.")

        new_id = normalize_profile_id(clean_name)

        profile = self._find_profile(registry, old_id)

        if new_id != old_id and any(item.id == new_id for item in registry.profiles):
            raise DuplicateProfileError("A profile with that name already exists.")

        old_dir = self.profile_dir(old_id)
        new_dir = self.profile_dir(new_id)

        if new_id != old_id:
            if new_dir.exists():
                raise DuplicateProfileError("A profile folder with that name already exists.")

            if old_dir.exists():
                old_dir.rename(new_dir)
            else:
                new_dir.mkdir(parents=True, exist_ok=True)

            if registry.active_profile_id == old_id:
                registry.active_profile_id = new_id

        profile.id = new_id
        profile.name = clean_name
        profile.updated_at = utc_now_iso()

        self.save(registry)
        return profile

    def delete_profile(self, profile_id: str) -> Path:
        registry = self.load_or_bootstrap()
        clean_id = normalize_profile_id(profile_id)

        if len(registry.profiles) <= 1:
            raise LastProfileError("The last profile cannot be deleted.")

        profile = self._find_profile(registry, clean_id)

        profile_dir = self.profile_dir(profile.id)
        backup_path = self._unique_backup_path(profile.id)

        self.backup_dir.mkdir(parents=True, exist_ok=True)

        if profile_dir.exists():
            shutil.move(str(profile_dir), str(backup_path))
        else:
            backup_path.mkdir(parents=True, exist_ok=True)

        registry.profiles = [item for item in registry.profiles if item.id != profile.id]

        if registry.active_profile_id == profile.id:
            registry.active_profile_id = registry.profiles[0].id

        self.save(registry)
        return backup_path

    def is_active_profile(self, profile_id: str) -> bool:
        registry = self.load_or_bootstrap()
        return registry.active_profile_id == normalize_profile_id(profile_id)

    def _find_profile(self, registry: ProfileRegistry, profile_id: str) -> UserProfile:
        clean_id = normalize_profile_id(profile_id)

        for profile in registry.profiles:
            if profile.id == clean_id:
                return profile

        raise ProfileNotFoundError("Profile was not found.")

    def _move_legacy_file(self, filename: str, target: Path) -> None:
        source = self.base_data_dir / filename

        if not source.exists():
            return

        if target.exists():
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)

    def _move_legacy_dir(self, dirname: str, target: Path) -> None:
        source = self.base_data_dir / dirname

        if not source.exists() or not source.is_dir():
            return

        if target.exists():
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)

    def _unique_backup_path(self, profile_id: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = self.backup_dir / f"profile_{normalize_profile_id(profile_id)}_{timestamp}"

        candidate = base
        counter = 1

        while candidate.exists():
            candidate = self.backup_dir / f"{base.name}_{counter}"
            counter += 1

        return candidate