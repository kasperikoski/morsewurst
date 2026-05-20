from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType

import pytest


NETWORK_UI_PACKAGE = "morsewurst.ui.network"

EXPECTED_NETWORK_UI_MODULES = {
    "morsewurst.ui.network",
    "morsewurst.ui.network.lobby_window",
    "morsewurst.ui.network.lobby_state",
    "morsewurst.ui.network.lobby_actions",
    "morsewurst.ui.network.server_queries",
    "morsewurst.ui.network.widgets",
    "morsewurst.ui.network.views",
    "morsewurst.ui.network.views.callsign_view",
    "morsewurst.ui.network.views.lobby_view",
    "morsewurst.ui.network.views.room_view",
    "morsewurst.ui.network.views.settings_view",
    "morsewurst.ui.network.views.server_info_view",
}

EXPECTED_CORE_IMPORTS_USED_BY_NETWORK_UI = {
    "morsewurst.config",
    "morsewurst.network.defaults",
    "morsewurst.network.models",
    "morsewurst.network.public_rooms",
    "morsewurst.network.settings_store",
    "morsewurst.ui.network_matrix_theme",
}

EXPECTED_CLASSES = {
    "morsewurst.ui.network.lobby_window": {
        "NetworkLobbyWindow",
    },
    "morsewurst.ui.network.lobby_state": {
        "RoomSelectionState",
        "ServerQueryState",
    },
    "morsewurst.ui.network.lobby_actions": {
        "LobbyActionsMixin",
    },
    "morsewurst.ui.network.server_queries": {
        "NetworkServerQueriesMixin",
    },
    "morsewurst.ui.network.widgets": {
        "NetworkWidgetsMixin",
    },
    "morsewurst.ui.network.views.callsign_view": {
        "CallsignViewMixin",
    },
    "morsewurst.ui.network.views.lobby_view": {
        "LobbyViewMixin",
    },
    "morsewurst.ui.network.views.room_view": {
        "RoomViewMixin",
    },
    "morsewurst.ui.network.views.settings_view": {
        "SettingsViewMixin",
    },
    "morsewurst.ui.network.views.server_info_view": {
        "ServerInfoViewMixin",
    },
}

EXPECTED_PUBLIC_METHODS = {
    "show_callsign_view",
    "show_lobby_view",
    "show_room_view",
    "show_settings_view",
    "show_server_info_window",
    "join_public_room",
    "join_private_room",
    "disconnect",
    "close",
}

EXPECTED_INTERNAL_METHODS = {
    "_build_window_chrome",
    "_build_header",
    "_render_footer",
    "_clear_content",
    "_needs_first_callsign",
    "_save_first_callsign",
    "_ensure_lobby_presence",
    "_build_connection_panel",
    "_build_public_rooms_panel",
    "_build_remembered_private_rooms_panel",
    "_build_private_panel",
    "_render_public_rooms",
    "_render_remembered_private_rooms",
    "_refresh_public_rooms_async",
    "_poll_public_rooms_result_queue",
    "_request_server_info",
    "_request_server_ping",
    "_poll_server_query_result_queue",
    "_network_settings",
    "_save_current_settings",
    "_poll_status",
    "_append_log",
    "_center_on_parent",
    "bring_to_front",
    "_set_network_quality",
    "_network_quality_from_ping",
    "_update_network_quality_from_server_pong",
    "_is_buffer_quality_warning",
    "_refresh_network_quality_indicator",
}


def import_module(name: str) -> ModuleType:
    return importlib.import_module(name)


def test_network_ui_package_exports_network_lobby_window() -> None:
    from morsewurst.ui.network import NetworkLobbyWindow

    assert NetworkLobbyWindow.__name__ == "NetworkLobbyWindow"


@pytest.mark.parametrize("module_name", sorted(EXPECTED_NETWORK_UI_MODULES))
def test_all_expected_network_ui_modules_import(module_name: str) -> None:
    module = import_module(module_name)

    assert isinstance(module, ModuleType)


@pytest.mark.parametrize("module_name", sorted(EXPECTED_CORE_IMPORTS_USED_BY_NETWORK_UI))
def test_network_ui_dependencies_import(module_name: str) -> None:
    module = import_module(module_name)

    assert isinstance(module, ModuleType)


def test_network_ui_package_contains_expected_submodules() -> None:
    package = import_module(NETWORK_UI_PACKAGE)

    discovered = {
        module_info.name
        for module_info in pkgutil.walk_packages(
            package.__path__,
            prefix=f"{NETWORK_UI_PACKAGE}.",
        )
    }

    expected_without_root = EXPECTED_NETWORK_UI_MODULES - {NETWORK_UI_PACKAGE}

    assert expected_without_root <= discovered


@pytest.mark.parametrize("module_name, class_names", sorted(EXPECTED_CLASSES.items()))
def test_expected_network_ui_classes_exist(module_name: str, class_names: set[str]) -> None:
    module = import_module(module_name)

    for class_name in class_names:
        value = getattr(module, class_name, None)

        assert inspect.isclass(value), f"{module_name}.{class_name} is missing or is not a class"


def test_network_lobby_window_inherits_all_required_mixins() -> None:
    from morsewurst.ui.network import NetworkLobbyWindow
    from morsewurst.ui.network.lobby_actions import LobbyActionsMixin
    from morsewurst.ui.network.server_queries import NetworkServerQueriesMixin
    from morsewurst.ui.network.widgets import NetworkWidgetsMixin
    from morsewurst.ui.network.views.callsign_view import CallsignViewMixin
    from morsewurst.ui.network.views.lobby_view import LobbyViewMixin
    from morsewurst.ui.network.views.room_view import RoomViewMixin
    from morsewurst.ui.network.views.server_info_view import ServerInfoViewMixin
    from morsewurst.ui.network.views.settings_view import SettingsViewMixin

    expected_mixins = {
        NetworkWidgetsMixin,
        CallsignViewMixin,
        LobbyViewMixin,
        RoomViewMixin,
        SettingsViewMixin,
        ServerInfoViewMixin,
        NetworkServerQueriesMixin,
        LobbyActionsMixin,
    }

    actual_mro = set(NetworkLobbyWindow.__mro__)

    assert expected_mixins <= actual_mro


def test_network_lobby_window_has_expected_public_methods() -> None:
    from morsewurst.ui.network import NetworkLobbyWindow

    for method_name in EXPECTED_PUBLIC_METHODS:
        method = getattr(NetworkLobbyWindow, method_name, None)

        assert callable(method), f"Missing public method: {method_name}"


def test_network_lobby_window_has_expected_internal_methods() -> None:
    from morsewurst.ui.network import NetworkLobbyWindow

    for method_name in EXPECTED_INTERNAL_METHODS:
        method = getattr(NetworkLobbyWindow, method_name, None)

        assert callable(method), f"Missing internal method: {method_name}"


def test_network_lobby_window_constructor_accepts_app_argument() -> None:
    from morsewurst.ui.network import NetworkLobbyWindow

    signature = inspect.signature(NetworkLobbyWindow)

    assert "app" in signature.parameters


def test_network_ui_init_exports_expected_public_api() -> None:
    import morsewurst.ui.network as network_ui

    assert hasattr(network_ui, "NetworkLobbyWindow")

    exported = set(getattr(network_ui, "__all__", []))

    assert exported == {"NetworkLobbyWindow"}


def test_network_lobby_window_uses_split_package_structure() -> None:
    from morsewurst.ui.network import NetworkLobbyWindow

    expected_mixin_modules = {
        "morsewurst.ui.network.widgets",
        "morsewurst.ui.network.views.callsign_view",
        "morsewurst.ui.network.views.lobby_view",
        "morsewurst.ui.network.views.room_view",
        "morsewurst.ui.network.views.settings_view",
        "morsewurst.ui.network.views.server_info_view",
        "morsewurst.ui.network.server_queries",
        "morsewurst.ui.network.lobby_actions",
    }

    actual_mixin_modules = {
        cls.__module__
        for cls in NetworkLobbyWindow.__mro__
    }

    assert expected_mixin_modules <= actual_mixin_modules