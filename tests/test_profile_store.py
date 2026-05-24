from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

import morsewurst.config as config
from morsewurst.storage.profile_store import (
    DEBUG_DIRNAME,
    DuplicateProfileError,
    LastProfileError,
    ProfileError,
    ProfileNotFoundError,
    ProfileStore,
    clean_profile_name,
    normalize_profile_id,
)


DATABASE_FILENAME = "morsewurst.sqlite3"
UI_SETTINGS_FILENAME = "ui_settings.json"
NETWORK_SETTINGS_FILENAME = "network_settings.json"


@pytest.fixture(autouse=True)
def restore_config_data_dir():
    """Profile preparation changes global config paths, so restore them after each test."""

    original_data_dir = config.DATA_DIR
    yield
    config.set_active_data_dir(original_data_dir)


def make_store(tmp_path: Path) -> ProfileStore:
    base = tmp_path / "data"

    return ProfileStore(
        registry_path=base / "profiles.json",
        profiles_dir=base / "profiles",
        backup_dir=base / "Backups",
        base_data_dir=base,
    )


def read_registry(store: ProfileStore) -> dict:
    return json.loads(store.registry_path.read_text(encoding="utf-8"))


def create_kasperi_profile(store: ProfileStore):
    return store.create_first_profile("Kasperi")


def test_normalize_profile_id_handles_case_spaces_accents_and_symbols():
    assert normalize_profile_id("Kasperi") == "kasperi"
    assert normalize_profile_id("  Kasperi Koski  ") == "kasperi-koski"
    assert normalize_profile_id("Ääkkönen Örn") == "aakkonen-orn"
    assert normalize_profile_id("Hemmo!!! Testi") == "hemmo-testi"
    assert normalize_profile_id("...---___") == "user"
    assert normalize_profile_id("") == "user"
    assert normalize_profile_id(None) == "user"


def test_normalize_profile_id_limits_length():
    value = normalize_profile_id("A" * 200)

    assert len(value) == 48
    assert value == "a" * 48


def test_clean_profile_name_trims_collapses_and_limits_text():
    assert clean_profile_name("  Kasperi   Koski  ") == "Kasperi Koski"
    assert clean_profile_name("Hemmo\r\nTesti") == "Hemmo Testi"
    assert clean_profile_name("") == ""
    assert clean_profile_name(None) == ""

    long_name = clean_profile_name("A" * 200)
    assert len(long_name) == 80


def test_load_returns_empty_registry_when_registry_file_does_not_exist(tmp_path):
    store = make_store(tmp_path)

    registry = store.load()

    assert registry.version == 1
    assert registry.active_profile_id == ""
    assert registry.profiles == []


def test_has_profiles_returns_false_when_no_registry_exists(tmp_path):
    store = make_store(tmp_path)

    assert store.has_profiles() is False
    assert store.load_existing_registry().profiles == []


def test_load_existing_registry_does_not_create_default_profile(tmp_path):
    store = make_store(tmp_path)

    registry = store.load_existing_registry()

    assert registry.profiles == []
    assert registry.active_profile_id == ""
    assert not store.registry_path.exists()
    assert not store.profile_dir("default").exists()


def test_load_existing_registry_does_not_create_profile_from_invalid_json(tmp_path):
    store = make_store(tmp_path)

    store.registry_path.parent.mkdir(parents=True)
    store.registry_path.write_text("not json", encoding="utf-8")

    registry = store.load_existing_registry()

    assert registry.profiles == []
    assert registry.active_profile_id == ""
    assert not store.profile_dir("default").exists()


def test_load_existing_registry_recovers_invalid_active_profile_id(tmp_path):
    store = make_store(tmp_path)

    kasperi = create_kasperi_profile(store)
    hemmo = store.create_profile("Hemmo")

    registry = store.load()
    registry.active_profile_id = "missing-profile"
    store.save(registry)

    recovered = store.load_existing_registry()

    assert recovered.active_profile_id == kasperi.id
    assert {profile.id for profile in recovered.profiles} == {kasperi.id, hemmo.id}

    saved = read_registry(store)
    assert saved["active_profile_id"] == kasperi.id


def test_create_first_profile_creates_profile_registry_folder_and_debug_folder(tmp_path):
    store = make_store(tmp_path)

    active = store.create_first_profile("Kasperi")
    profile_dir = store.profile_dir("kasperi")

    assert active.id == "kasperi"
    assert active.name == "Kasperi"
    assert profile_dir.exists()
    assert (profile_dir / DEBUG_DIRNAME).exists()
    assert not store.profile_dir("default").exists()

    registry = read_registry(store)

    assert registry["version"] == 1
    assert registry["active_profile_id"] == "kasperi"
    assert len(registry["profiles"]) == 1
    assert registry["profiles"][0]["id"] == "kasperi"
    assert registry["profiles"][0]["name"] == "Kasperi"
    assert registry["profiles"][0]["created_at"].endswith("Z")
    assert registry["profiles"][0]["updated_at"].endswith("Z")


def test_create_first_profile_rejects_empty_name(tmp_path):
    store = make_store(tmp_path)

    with pytest.raises(ProfileError):
        store.create_first_profile("   ")

    assert store.has_profiles() is False
    assert not store.registry_path.exists()


def test_create_first_profile_rejects_when_profile_already_exists(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)

    with pytest.raises(ProfileError):
        store.create_first_profile("Hemmo")

    registry = read_registry(store)
    assert {item["id"] for item in registry["profiles"]} == {"kasperi"}


def test_create_profile_requires_existing_first_profile(tmp_path):
    store = make_store(tmp_path)

    with pytest.raises(ProfileNotFoundError):
        store.create_profile("Hemmo")

    assert store.has_profiles() is False
    assert not store.registry_path.exists()


def test_prepare_active_profile_rejects_when_no_profiles_exist(tmp_path):
    store = make_store(tmp_path)

    with pytest.raises(ProfileNotFoundError):
        store.prepare_active_profile()


def test_prepare_active_profile_sets_config_paths_to_active_profile(tmp_path):
    store = make_store(tmp_path)

    created = create_kasperi_profile(store)
    active = store.prepare_active_profile()
    active_dir = store.profile_dir(created.id)

    assert active.id == "kasperi"
    assert config.DATA_DIR == active_dir
    assert config.DB_PATH == active_dir / DATABASE_FILENAME
    assert config.DEBUG_DIR == active_dir / DEBUG_DIRNAME
    assert config.DEBUG_LATEST_SNAPSHOT_PATH == active_dir / DEBUG_DIRNAME / "latest_round_debug.json"
    assert config.DEBUG_HISTORY_PATH == active_dir / DEBUG_DIRNAME / "debug_history.jsonl"


def test_prepare_active_profile_does_not_move_legacy_root_files(tmp_path):
    store = make_store(tmp_path)
    base = store.base_data_dir

    base.mkdir(parents=True)
    (base / DATABASE_FILENAME).write_text("db", encoding="utf-8")
    (base / f"{DATABASE_FILENAME}-wal").write_text("wal", encoding="utf-8")
    (base / f"{DATABASE_FILENAME}-shm").write_text("shm", encoding="utf-8")
    (base / UI_SETTINGS_FILENAME).write_text("ui", encoding="utf-8")
    (base / NETWORK_SETTINGS_FILENAME).write_text("net", encoding="utf-8")

    debug_dir = base / DEBUG_DIRNAME
    debug_dir.mkdir()
    (debug_dir / "latest_round_debug.json").write_text("debug", encoding="utf-8")

    create_kasperi_profile(store)
    active = store.prepare_active_profile()
    profile_dir = store.profile_dir(active.id)

    assert active.id == "kasperi"
    assert not (profile_dir / DATABASE_FILENAME).exists()
    assert not (profile_dir / f"{DATABASE_FILENAME}-wal").exists()
    assert not (profile_dir / f"{DATABASE_FILENAME}-shm").exists()
    assert not (profile_dir / UI_SETTINGS_FILENAME).exists()
    assert not (profile_dir / NETWORK_SETTINGS_FILENAME).exists()
    assert not (profile_dir / DEBUG_DIRNAME / "latest_round_debug.json").exists()

    assert (base / DATABASE_FILENAME).read_text(encoding="utf-8") == "db"
    assert (base / f"{DATABASE_FILENAME}-wal").read_text(encoding="utf-8") == "wal"
    assert (base / f"{DATABASE_FILENAME}-shm").read_text(encoding="utf-8") == "shm"
    assert (base / UI_SETTINGS_FILENAME).read_text(encoding="utf-8") == "ui"
    assert (base / NETWORK_SETTINGS_FILENAME).read_text(encoding="utf-8") == "net"
    assert (base / DEBUG_DIRNAME / "latest_round_debug.json").read_text(encoding="utf-8") == "debug"


def test_create_profile_creates_folder_and_debug_folder(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    profile = store.create_profile("Hemmo")

    profile_dir = store.profile_dir(profile.id)

    assert profile.id == "hemmo"
    assert profile.name == "Hemmo"
    assert profile_dir.exists()
    assert (profile_dir / DEBUG_DIRNAME).exists()

    registry = read_registry(store)

    assert registry["active_profile_id"] == "kasperi"
    assert {item["id"] for item in registry["profiles"]} == {"kasperi", "hemmo"}


def test_create_profile_rejects_empty_name(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)

    with pytest.raises(ProfileError):
        store.create_profile("   ")


def test_create_profile_rejects_duplicate_normalized_name(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    store.create_profile("Hemmo")

    with pytest.raises(DuplicateProfileError):
        store.create_profile("hemmo")


def test_create_profile_rejects_duplicate_after_accent_normalization(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    store.create_profile("Ääkkönen")

    with pytest.raises(DuplicateProfileError):
        store.create_profile("Aakkonen")


def test_activate_profile_updates_registry_but_does_not_change_config_until_prepare(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    store.prepare_active_profile()
    original_data_dir = config.DATA_DIR

    hemmo = store.create_profile("Hemmo")
    active = store.activate_profile(hemmo.id)

    registry = read_registry(store)

    assert active.id == "hemmo"
    assert registry["active_profile_id"] == "hemmo"
    assert config.DATA_DIR == original_data_dir

    prepared = store.prepare_active_profile()

    assert prepared.id == "hemmo"
    assert config.DATA_DIR == store.profile_dir("hemmo")


def test_activate_profile_rejects_missing_profile(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)

    with pytest.raises(ProfileNotFoundError):
        store.activate_profile("missing")


def test_list_profiles_returns_empty_list_when_no_profiles_exist(tmp_path):
    store = make_store(tmp_path)

    assert store.list_profiles() == []


def test_list_profiles_returns_all_profiles(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    store.create_profile("Hemmo")
    store.create_profile("Nyyti")

    profiles = store.list_profiles()

    assert [profile.id for profile in profiles] == ["kasperi", "hemmo", "nyyti"]


def test_active_profile_rejects_when_no_profiles_exist(tmp_path):
    store = make_store(tmp_path)

    with pytest.raises(ProfileNotFoundError):
        store.active_profile()


def test_active_profile_returns_current_active_profile(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    hemmo = store.create_profile("Hemmo")
    store.activate_profile(hemmo.id)

    active = store.active_profile()

    assert active.id == "hemmo"
    assert active.name == "Hemmo"


def test_is_active_profile_checks_current_registry_value(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    hemmo = store.create_profile("Hemmo")

    assert store.is_active_profile("kasperi") is True
    assert store.is_active_profile(hemmo.id) is False

    store.activate_profile(hemmo.id)

    assert store.is_active_profile("kasperi") is False
    assert store.is_active_profile(hemmo.id) is True


def test_is_active_profile_returns_false_when_no_profiles_exist(tmp_path):
    store = make_store(tmp_path)

    assert store.is_active_profile("kasperi") is False


def test_rename_profile_moves_folder_and_preserves_files(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    profile = store.create_profile("Hemmo")

    old_dir = store.profile_dir(profile.id)
    (old_dir / DATABASE_FILENAME).write_text("db", encoding="utf-8")

    renamed = store.rename_profile(profile.id, "Hemmo Uusi")
    new_dir = store.profile_dir("hemmo-uusi")

    assert renamed.id == "hemmo-uusi"
    assert renamed.name == "Hemmo Uusi"
    assert not old_dir.exists()
    assert new_dir.exists()
    assert (new_dir / DATABASE_FILENAME).read_text(encoding="utf-8") == "db"

    registry = read_registry(store)

    assert {item["id"] for item in registry["profiles"]} == {"kasperi", "hemmo-uusi"}


def test_rename_active_profile_updates_active_profile_id(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)

    renamed = store.rename_profile("kasperi", "Kasperi Uusi")
    registry = read_registry(store)

    assert renamed.id == "kasperi-uusi"
    assert registry["active_profile_id"] == "kasperi-uusi"
    assert store.profile_dir("kasperi-uusi").exists()
    assert not store.profile_dir("kasperi").exists()


def test_rename_profile_to_same_id_only_changes_display_name(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    profile = store.create_profile("Hemmo")

    renamed = store.rename_profile(profile.id, "HEMMO")

    assert renamed.id == "hemmo"
    assert renamed.name == "HEMMO"
    assert store.profile_dir("hemmo").exists()


def test_rename_profile_rejects_empty_name(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    profile = store.create_profile("Hemmo")

    with pytest.raises(ProfileError):
        store.rename_profile(profile.id, "   ")


def test_rename_profile_rejects_duplicate_name(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    hemmo = store.create_profile("Hemmo")
    store.create_profile("Nyyti")

    with pytest.raises(DuplicateProfileError):
        store.rename_profile(hemmo.id, "Nyyti")


def test_rename_profile_rejects_missing_profile(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)

    with pytest.raises(ProfileNotFoundError):
        store.rename_profile("missing", "New Name")


def test_rename_profile_rejects_when_target_folder_already_exists(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    hemmo = store.create_profile("Hemmo")

    target_dir = store.profile_dir("already-there")
    target_dir.mkdir(parents=True)

    with pytest.raises(DuplicateProfileError):
        store.rename_profile(hemmo.id, "Already There")


def test_delete_profile_moves_folder_to_backup(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    profile = store.create_profile("Hemmo")

    profile_dir = store.profile_dir(profile.id)
    (profile_dir / DATABASE_FILENAME).write_text("db", encoding="utf-8")
    (profile_dir / UI_SETTINGS_FILENAME).write_text("ui", encoding="utf-8")
    (profile_dir / NETWORK_SETTINGS_FILENAME).write_text("net", encoding="utf-8")

    backup_path = store.delete_profile(profile.id)

    assert backup_path.exists()
    assert backup_path.parent == store.backup_dir
    assert backup_path.name.startswith("profile_hemmo_")
    assert re.fullmatch(r"profile_hemmo_\d{8}_\d{6}(?:_\d+)?", backup_path.name)

    assert (backup_path / DATABASE_FILENAME).read_text(encoding="utf-8") == "db"
    assert (backup_path / UI_SETTINGS_FILENAME).read_text(encoding="utf-8") == "ui"
    assert (backup_path / NETWORK_SETTINGS_FILENAME).read_text(encoding="utf-8") == "net"
    assert not profile_dir.exists()

    registry = read_registry(store)

    assert {item["id"] for item in registry["profiles"]} == {"kasperi"}


def test_delete_active_profile_selects_next_available_profile(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    store.create_profile("Hemmo")

    backup_path = store.delete_profile("kasperi")
    registry = read_registry(store)

    assert backup_path.exists()
    assert registry["active_profile_id"] == "hemmo"
    assert {item["id"] for item in registry["profiles"]} == {"hemmo"}


def test_delete_profile_creates_backup_even_if_profile_folder_is_missing(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    profile = store.create_profile("Hemmo")

    profile_dir = store.profile_dir(profile.id)
    assert profile_dir.exists()

    shutil.rmtree(profile_dir)

    backup_path = store.delete_profile(profile.id)

    assert backup_path.exists()
    assert backup_path.is_dir()

    registry = read_registry(store)

    assert {item["id"] for item in registry["profiles"]} == {"kasperi"}


def test_delete_profile_rejects_missing_profile(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    store.create_profile("Hemmo")

    with pytest.raises(ProfileNotFoundError):
        store.delete_profile("missing")


def test_last_profile_cannot_be_deleted(tmp_path):
    store = make_store(tmp_path)

    active = create_kasperi_profile(store)

    with pytest.raises(LastProfileError):
        store.delete_profile(active.id)


def test_profile_dir_normalizes_given_id(tmp_path):
    store = make_store(tmp_path)

    assert store.profile_dir("Hemmo Testi") == store.profiles_dir / "hemmo-testi"


def test_save_writes_registry_atomically_without_tmp_file_left(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    registry = store.load_existing_registry()

    store.save(registry)

    assert store.registry_path.exists()
    assert not store.registry_path.with_suffix(store.registry_path.suffix + ".tmp").exists()


def test_prepare_active_profile_after_switch_uses_selected_profile_directory(tmp_path):
    store = make_store(tmp_path)

    create_kasperi_profile(store)
    hemmo = store.create_profile("Hemmo")
    store.activate_profile(hemmo.id)

    active = store.prepare_active_profile()

    assert active.id == "hemmo"
    assert config.DATA_DIR == store.profile_dir("hemmo")
    assert config.DB_PATH == store.profile_dir("hemmo") / DATABASE_FILENAME


def test_create_first_profile_adopts_existing_orphan_profile_folder(tmp_path):
    store = make_store(tmp_path)

    orphan_dir = store.profile_dir("kasperi")
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "existing.txt").write_text("keep me", encoding="utf-8")

    profile = store.create_first_profile("Kasperi")

    assert profile.id == "kasperi"
    assert profile.name == "Kasperi"
    assert orphan_dir.exists()
    assert (orphan_dir / "existing.txt").read_text(encoding="utf-8") == "keep me"
    assert (orphan_dir / DEBUG_DIRNAME).exists()

    registry = read_registry(store)

    assert registry["active_profile_id"] == "kasperi"
    assert len(registry["profiles"]) == 1
    assert registry["profiles"][0]["id"] == "kasperi"


def test_create_first_profile_rejects_existing_file_with_same_profile_id(tmp_path):
    store = make_store(tmp_path)

    store.profiles_dir.mkdir(parents=True)
    store.profile_dir("kasperi").write_text("not a directory", encoding="utf-8")

    with pytest.raises(DuplicateProfileError):
        store.create_first_profile("Kasperi")