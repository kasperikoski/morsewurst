# ============================================================
# morsewurst/ui/controllers/profile_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

from morsewurst.storage.profile_store import (
    ProfileStore,
    UserProfile,
)
from morsewurst.core.app_logging import log_app_event, log_app_exception

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
            log_app_event(
                "app.profile.initial_setup_required",
                message="No user profiles exist; initial profile setup is required.",
            )
            self.initial_profile_setup_required = True
            self.active_profile = None
            return None

        self.initial_profile_setup_required = False
        self.active_profile = self.store.prepare_active_profile()
        log_app_event(
            "app.profile.active_prepared",
            message="Active user profile prepared.",
            context={
                "profile_id": self.active_profile.id,
                "profile_name": self.active_profile.name,
            },
        )
        return self.active_profile
    
    def create_first_profile(self, name: str) -> UserProfile:
        try:
            profile = self.store.create_first_profile(name)
            log_app_event(
                "app.profile.first_created",
                message="First user profile created.",
                context={"profile_id": profile.id, "profile_name": profile.name},
            )
            return profile
        except Exception as exc:
            log_app_exception(
                "app.profile.create_failed",
                exc,
                message="First user profile creation failed.",
            )
            raise

    def open_initial_profile_window(self) -> None:
        from morsewurst.ui.initial_profile_window import InitialProfileWindow

        if getattr(self.app, "initial_profile_window", None) is not None:
            try:
                if self.app.initial_profile_window.winfo_exists():
                    self.app.initial_profile_window.lift()
                    return
            except Exception:
                pass

        log_app_event(
            "app.window.opened",
            message="Initial profile window opened.",
            context={"window": "initial_profile_window"},
        )
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
        profiles = self.store.list_profiles()
        log_app_event(
            "app.profile.listed",
            message="User profiles listed.",
            context={"profile_count": len(profiles)},
        )
        return profiles

    def create_profile(self, name: str) -> UserProfile:
        try:
            profile = self.store.create_profile(name)
            log_app_event(
                "app.profile.created",
                message="User profile created.",
                context={"profile_id": profile.id, "profile_name": profile.name},
            )
            return profile
        except Exception as exc:
            log_app_exception(
                "app.profile.create_failed",
                exc,
                message="User profile creation failed.",
            )
            raise

    def activate_profile(self, profile_id: str) -> UserProfile:
        try:
            profile = self.store.activate_profile(profile_id)
            log_app_event(
                "app.profile.activated",
                message="User profile activated for next restart.",
                context={"profile_id": profile.id, "profile_name": profile.name},
            )
            return profile
        except Exception as exc:
            log_app_exception(
                "app.profile.activate_failed",
                exc,
                message="User profile activation failed.",
                context={"profile_id": profile_id},
            )
            raise

    def rename_profile(self, profile_id: str, new_name: str) -> UserProfile:
        try:
            profile = self.store.rename_profile(profile_id, new_name)
            log_app_event(
                "app.profile.renamed",
                message="User profile renamed.",
                context={"profile_id": profile.id, "profile_name": profile.name},
            )
            return profile
        except Exception as exc:
            log_app_exception(
                "app.profile.rename_failed",
                exc,
                message="User profile rename failed.",
                context={"profile_id": profile_id},
            )
            raise

    def delete_profile(self, profile_id: str):
        try:
            backup_path = self.store.delete_profile(profile_id)
            log_app_event(
                "app.profile.deleted",
                message="User profile deleted and backed up.",
                context={
                    "profile_id": profile_id,
                    "backup_path": str(backup_path),
                },
            )
            return backup_path
        except Exception as exc:
            log_app_exception(
                "app.profile.delete_failed",
                exc,
                message="User profile deletion failed.",
                context={"profile_id": profile_id},
            )
            raise

    def is_active_profile(self, profile_id: str) -> bool:
        return self.store.is_active_profile(profile_id)