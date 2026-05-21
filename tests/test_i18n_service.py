from __future__ import annotations

import ast
import json
import string
from pathlib import Path
from typing import Any

import morsewurst.i18n.service as i18n_service_module
from morsewurst.i18n import I18nService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
I18N_DIR = Path(i18n_service_module.__file__).resolve().parent

SOURCE_ROOTS = [
    PROJECT_ROOT / "morsewurst",
    PROJECT_ROOT / "main.py",
]

EXCLUDED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "venv",
}

def _load_catalog(language: str) -> dict[str, Any]:
    path = I18N_DIR / f"{language}.json"
    assert path.exists(), f"Missing translation catalog: {path}"

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), f"{path.name} must contain a JSON object"

    return raw


def _placeholder_names(text: str) -> list[str]:
    placeholders: list[str] = []

    for _literal_text, field_name, _format_spec, _conversion in string.Formatter().parse(text):
        if not field_name:
            continue

        # Support normal placeholders such as {error}, and also keep this safe
        # if a future string ever uses formatting like {value:.1f} or {item[name]}.
        name = str(field_name).split(".", 1)[0].split("[", 1)[0].strip()

        if name and name not in placeholders:
            placeholders.append(name)

    return placeholders


def _format_expectations_from_catalog(catalog: dict[str, Any]) -> dict[str, list[str]]:
    expectations: dict[str, list[str]] = {}

    for key, value in catalog.items():
        if not isinstance(value, str):
            continue

        placeholders = _placeholder_names(value)

        if placeholders:
            expectations[key] = placeholders

    return expectations


# en.json is the canonical key order.
# Keep fi.json in exactly the same order.
ENGLISH_CATALOG = _load_catalog("en")
REQUIRED_KEYS = list(ENGLISH_CATALOG.keys())
FORMAT_EXPECTATIONS = _format_expectations_from_catalog(ENGLISH_CATALOG)


def _format_values(placeholders: list[str]) -> dict[str, Any]:
    sample_values: dict[str, Any] = {
        "active": "raw data",
        "app_name": "Morsewurst",
        "bucket": "automatic",
        "callsign": "OH4GOY",
        "confidence": 85,
        "count": 3,
        "current": 2,
        "deleted": 2,
        "device": "Morsewurst",
        "elapsed": "12.3 s",
        "end": "21.05.2026 18:00",
        "error": "test error",
        "event_type": "tone",
        "keyboard_key": "Space",
        "label": "good",
        "level": 4,
        "max": 10,
        "message": "test message",
        "min_acc": 90,
        "min_chars": 12,
        "min_clean": 85,
        "min_req": 3,
        "optimized_wpm": 14,
        "percent": 85,
        "ping_ms": 42,
        "port": "COM3",
        "raw_wpm": 12.5,
        "reason": "completed",
        "recent": 100,
        "reference": "10.0 s",
        "required": 10,
        "room": "Makkara",
        "seconds": "42",
        "session_id": 123,
        "start": "21.05.2026 12:00",
        "suffix": " (preliminary)",
        "time": "12:34:56",
        "title": "Operator",
        "total": 5,
        "total_rounds": 5,
        "used": 3,
    }

    values: dict[str, Any] = {}

    for placeholder in placeholders:
        values[placeholder] = sample_values.get(placeholder, "test")

    return values


def _iter_project_python_files() -> list[Path]:
    files: list[Path] = []

    for root in SOURCE_ROOTS:
        if not root.exists():
            continue

        if root.is_file():
            if root.suffix == ".py":
                files.append(root)
            continue

        for path in root.rglob("*.py"):
            if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
                continue

            files.append(path)

    return sorted(files)


def _attribute_chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    current: ast.AST | None = node

    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value

    if isinstance(current, ast.Name):
        parts.append(current.id)

    parts.reverse()
    return parts


def _is_translation_call(node: ast.Call) -> bool:
    chain = _attribute_chain(node.func)

    if not chain:
        return False

    if chain[-1] == "t" and "i18n" in chain:
        return True

    if chain[-1] == "tr":
        return True

    return False


def _literal_i18n_key_usages() -> list[tuple[str, int, str]]:
    usages: set[tuple[str, int, str]] = set()

    for path in _iter_project_python_files():
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            source = path.read_text(encoding="utf-8", errors="replace")

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            if not node.args:
                continue

            first_arg = node.args[0]

            if not isinstance(first_arg, ast.Constant):
                continue

            if not isinstance(first_arg.value, str):
                continue

            if not _is_translation_call(node):
                continue

            key = first_arg.value.strip()

            if not key:
                continue

            relative_path = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            usages.add((relative_path, int(getattr(node, "lineno", 0)), key))

    return sorted(usages)


def test_default_language_is_english() -> None:
    service = I18nService()
    assert service.language == "en"


def test_unknown_language_falls_back_to_english() -> None:
    service = I18nService("unknown")
    assert service.language == "en"


def test_language_normalization_accepts_case_and_whitespace() -> None:
    service = I18nService()
    assert service.normalize_language(" FI ") == "fi"
    assert service.normalize_language(" EN ") == "en"


def test_set_language_changes_current_language() -> None:
    service = I18nService()

    service.set_language("fi")
    assert service.language == "fi"

    service.set_language("en")
    assert service.language == "en"


def test_set_language_rejects_unknown_language_by_using_default() -> None:
    service = I18nService("fi")

    service.set_language("not-real")

    assert service.language == "en"


def test_language_options_contains_supported_languages() -> None:
    service = I18nService()

    assert service.language_options()["en"] == "English"
    assert service.language_options()["fi"] == "Suomi"


def test_known_finnish_translation_is_loaded() -> None:
    service = I18nService("fi")

    assert service.t("settings.language.tab") == "Kieli"


def test_missing_key_returns_key_when_no_default_exists() -> None:
    service = I18nService("fi")

    assert service.t("missing.key") == "missing.key"


def test_missing_key_can_use_default() -> None:
    service = I18nService("fi")

    assert service.t("missing.key", default="Fallback text") == "Fallback text"


def test_translation_supports_format_values() -> None:
    service = I18nService("en")

    assert service.t("network.public_rooms.count_many", count=3) == "3 rooms."


def test_translation_format_failure_returns_unformatted_text() -> None:
    service = I18nService("en")

    assert service.t("network.public_rooms.count_many") == "{count} rooms."


def test_finnish_missing_key_falls_back_to_english_catalog() -> None:
    service = I18nService("fi")
    service._catalogs["fi"].pop("app.ready", None)

    assert service.t("app.ready") == "Ready"


def test_catalog_files_are_valid_json_objects() -> None:
    _load_catalog("en")
    _load_catalog("fi")


def test_catalogs_only_contain_string_keys_and_values() -> None:
    for language in ("en", "fi"):
        catalog = _load_catalog(language)

        bad_keys = [key for key in catalog if not isinstance(key, str)]
        bad_values = [
            key
            for key, value in catalog.items()
            if not isinstance(value, str)
        ]

        assert bad_keys == [], f"{language}.json has non-string keys: {bad_keys}"
        assert bad_values == [], f"{language}.json has non-string values at keys: {bad_values}"


def test_english_catalog_contains_required_keys() -> None:
    catalog = _load_catalog("en")

    missing = [key for key in REQUIRED_KEYS if key not in catalog]

    assert missing == [], f"Missing keys in en.json: {missing}"


def test_finnish_catalog_contains_required_keys() -> None:
    catalog = _load_catalog("fi")

    missing = [key for key in REQUIRED_KEYS if key not in catalog]

    assert missing == [], f"Missing keys in fi.json: {missing}"


def test_finnish_catalog_does_not_contain_keys_missing_from_english() -> None:
    english = _load_catalog("en")
    finnish = _load_catalog("fi")

    extra = sorted(set(finnish) - set(english))

    assert extra == [], f"Extra keys in fi.json not in en.json: {extra}"


def test_catalogs_have_the_same_key_order() -> None:
    english_keys = list(_load_catalog("en").keys())
    finnish_keys = list(_load_catalog("fi").keys())

    if finnish_keys == english_keys:
        return

    max_len = max(len(english_keys), len(finnish_keys))

    for index in range(max_len):
        english_key = english_keys[index] if index < len(english_keys) else "<missing>"
        finnish_key = finnish_keys[index] if index < len(finnish_keys) else "<missing>"

        if english_key != finnish_key:
            raise AssertionError(
                "Translation catalog key order differs.\n"
                f"First difference at index {index}:\n"
                f"  en.json: {english_key!r}\n"
                f"  fi.json: {finnish_key!r}\n\n"
                "Move the key blocks so that fi.json follows exactly the same key order as en.json."
            )

    raise AssertionError("Translation catalog key order differs.")


def test_required_format_placeholders_exist_in_both_languages() -> None:
    for language in ("en", "fi"):
        catalog = _load_catalog(language)
        failures: list[str] = []

        for key, placeholders in FORMAT_EXPECTATIONS.items():
            text = catalog.get(key, "")

            for placeholder in placeholders:
                marker = "{" + placeholder + "}"

                if marker not in text:
                    failures.append(f"{language}:{key} missing {marker}")

        assert failures == []


def test_format_placeholders_match_english_catalog() -> None:
    english = _load_catalog("en")

    for language in ("fi",):
        catalog = _load_catalog(language)
        failures: list[str] = []

        for key in REQUIRED_KEYS:
            english_placeholders = _placeholder_names(str(english.get(key, "")))
            translated_placeholders = _placeholder_names(str(catalog.get(key, "")))

            if translated_placeholders != english_placeholders:
                failures.append(
                    f"{language}:{key} placeholders {translated_placeholders!r} "
                    f"do not match English {english_placeholders!r}"
                )

        assert failures == []


def test_required_format_strings_render_in_both_languages() -> None:
    for language in ("en", "fi"):
        service = I18nService(language)
        failures: list[str] = []

        for key, placeholders in FORMAT_EXPECTATIONS.items():
            values = _format_values(placeholders)
            rendered = service.t(key, **values)

            if "{" in rendered or "}" in rendered:
                failures.append(f"{language}:{key} rendered as {rendered!r}")

        assert failures == []


def test_no_required_translation_resolves_to_raw_key() -> None:
    for language in ("en", "fi"):
        service = I18nService(language)

        unresolved = [key for key in REQUIRED_KEYS if service.t(key) == key]

        assert unresolved == []


def test_core_catalogs_do_not_contain_empty_values() -> None:
    for language in ("en", "fi"):
        catalog = _load_catalog(language)

        empty_values = [
            key
            for key, value in catalog.items()
            if value.strip() == ""
        ]

        assert empty_values == []


def test_literal_i18n_keys_used_in_python_exist_in_both_catalogs() -> None:
    usages = _literal_i18n_key_usages()

    assert usages, "No literal i18n translation keys were found in project source files."

    for language in ("en", "fi"):
        catalog = _load_catalog(language)

        missing = [
            f"{path}:{line} uses missing key {key!r}"
            for path, line, key in usages
            if key not in catalog
        ]

        assert missing == [], "Missing i18n keys:\n" + "\n".join(missing)


def test_literal_i18n_keys_used_in_python_have_matching_placeholders() -> None:
    usages = _literal_i18n_key_usages()
    english = _load_catalog("en")
    finnish = _load_catalog("fi")

    failures: list[str] = []

    for path, line, key in usages:
        if key not in english or key not in finnish:
            continue

        english_placeholders = _placeholder_names(str(english[key]))
        finnish_placeholders = _placeholder_names(str(finnish[key]))

        if finnish_placeholders != english_placeholders:
            failures.append(
                f"{path}:{line} key {key!r} has Finnish placeholders "
                f"{finnish_placeholders!r}, expected {english_placeholders!r}"
            )

    assert failures == []