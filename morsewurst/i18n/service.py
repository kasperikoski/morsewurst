# ============================================================
# morsewurst/i18n/service.py
# ============================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import morsewurst.config as config


DEFAULT_LANGUAGE = "en"
FALLBACK_LANGUAGE = "en"

SUPPORTED_LANGUAGES = {
    "en": "English",
    "fi": "Suomi",
    "sv": "Svenska",
    "de": "Deutsch",
    "ja": "日本語",
}


class I18nService:
    """Central translation lookup service."""

    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self._language = self.normalize_language(language)
        self._catalogs: dict[str, dict[str, str]] = {}

        self._load_language(FALLBACK_LANGUAGE)

        if self._language != FALLBACK_LANGUAGE:
            self._load_language(self._language)

    @property
    def language(self) -> str:
        return self._language

    def language_options(self) -> dict[str, str]:
        return dict(SUPPORTED_LANGUAGES)

    def normalize_language(self, value: object) -> str:
        code = str(value or "").strip().lower()

        if code in SUPPORTED_LANGUAGES:
            return code

        return DEFAULT_LANGUAGE

    def set_language(self, language: object) -> None:
        normalized = self.normalize_language(language)
        self._language = normalized

        self._load_language(FALLBACK_LANGUAGE)

        if normalized != FALLBACK_LANGUAGE:
            self._load_language(normalized)

    def t(self, key: str, default: str | None = None, **values: Any) -> str:
        text = self._lookup(key)

        if text is None:
            text = default if default is not None else key

        if not values:
            return text

        try:
            return text.format(**values)
        except Exception:
            return text

    def _lookup(self, key: str) -> str | None:
        current_catalog = self._catalogs.get(self._language, {})
        fallback_catalog = self._catalogs.get(FALLBACK_LANGUAGE, {})

        value = current_catalog.get(key)
        if isinstance(value, str):
            return value

        value = fallback_catalog.get(key)
        if isinstance(value, str):
            return value

        return None

    def _load_language(self, language: str) -> None:
        if language in self._catalogs:
            return

        path = self._language_file_path(language)

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}

        if not isinstance(raw, dict):
            raw = {}

        self._catalogs[language] = {
            str(key): str(value)
            for key, value in raw.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    def _language_file_path(self, language: str) -> Path:
        packaged_path = config.resource_path(f"morsewurst/i18n/{language}.json")

        if packaged_path.exists():
            return packaged_path

        return Path(__file__).resolve().parent / f"{language}.json"