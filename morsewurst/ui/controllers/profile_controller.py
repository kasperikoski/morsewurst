# ============================================================
# morsewurst/ui/controllers/profile_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

from morsewurst.storage.profile_store import (
    DEFAULT_PROFILE_NAME,
    ProfileStore,
    UserProfile,
)

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class ProfileController:
    """Owns user profile selection and profile lifecycle actions."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app
        self.store = ProfileStore()
        self.active_profile: UserProfile | None = None

    def prepare_active_profile(self) -> UserProfile:
        self.active_profile = self.store.prepare_active_profile(
            default_name=DEFAULT_PROFILE_NAME,
        )
        return self.active_profile

    def active_profile_name(self) -> str:
        if self.active_profile is not None:
            return self.active_profile.name

        try:
            return self.store.active_profile().name
        except Exception:
            return DEFAULT_PROFILE_NAME

    def active_profile_id(self) -> str:
        if self.active_profile is not None:
            return self.active_profile.id

        try:
            return self.store.active_profile().id
        except Exception:
            return ""

    def list_profiles(self) -> list[UserProfile]:
        return self.store.list_profiles()

    def create_profile(self, name: str) -> UserProfile:
        return self.store.create_profile(name)

    def activate_profile(self, profile_id: str) -> UserProfile:
        return self.store.activate_profile(profile_id)

    def rename_profile(self, profile_id: str, new_name: str) -> UserProfile:
        return self.store.rename_profile(profile_id, new_name)

    def delete_profile(self, profile_id: str):
        return self.store.delete_profile(profile_id)

    def is_active_profile(self, profile_id: str) -> bool:
        return self.store.is_active_profile(profile_id)