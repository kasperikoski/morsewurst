# ============================================================
# morsewurst/ui/controllers/profile_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

from morsewurst.storage.profile_store import (
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
        self.initial_profile_setup_required = False

    def prepare_active_profile(self) -> UserProfile | None:
        if not self.store.has_profiles():
            self.initial_profile_setup_required = True
            self.active_profile = None
            return None

        self.initial_profile_setup_required = False
        self.active_profile = self.store.prepare_active_profile()
        return self.active_profile
    
    def create_first_profile(self, name: str) -> UserProfile:
        return self.store.create_first_profile(name)

    def open_initial_profile_window(self) -> None:
        from morsewurst.ui.initial_profile_window import InitialProfileWindow

        if getattr(self.app, "initial_profile_window", None) is not None:
            try:
                if self.app.initial_profile_window.winfo_exists():
                    self.app.initial_profile_window.lift()
                    return
            except Exception:
                pass

        self.app.initial_profile_window = InitialProfileWindow(self.app)
        self.app.window_controller.apply_window_icon(self.app.initial_profile_window)

    def active_profile_name(self) -> str:
        if self.active_profile is not None:
            return self.active_profile.name

        if self.initial_profile_setup_required:
            return "Setup"

        try:
            return self.store.active_profile().name
        except Exception:
            return "No profile"

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