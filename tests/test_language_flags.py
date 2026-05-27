from __future__ import annotations

import json
import struct
from pathlib import Path

from morsewurst import config
from morsewurst.i18n.service import SUPPORTED_LANGUAGES


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
EXPECTED_FLAG_HEIGHT_PX = 50
MAX_FLAG_WIDTH_PX = 100


def _read_png_size(path: Path) -> tuple[int, int]:
    """Read PNG width and height from the IHDR chunk without Pillow."""

    data = path.read_bytes()

    assert data.startswith(PNG_SIGNATURE), f"{path} is not a PNG file"
    assert len(data) >= 24, f"{path} is too small to contain a valid PNG IHDR chunk"
    assert data[12:16] == b"IHDR", f"{path} does not contain a PNG IHDR chunk"

    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def test_language_flag_directory_config_is_valid() -> None:
    assert hasattr(config, "LANGUAGE_FLAG_DIR")
    assert hasattr(config, "LANGUAGE_FLAG_ICON_SUBSAMPLE")
    assert hasattr(config, "LANGUAGE_FLAG_SPACING_PX")

    flag_dir = config.LANGUAGE_FLAG_DIR

    assert isinstance(flag_dir, Path)
    assert flag_dir.name == "flags"
    assert flag_dir.parent.name == "img"
    assert flag_dir.parent.parent.name == "assets"

    assert isinstance(config.LANGUAGE_FLAG_ICON_SUBSAMPLE, int)
    assert config.LANGUAGE_FLAG_ICON_SUBSAMPLE >= 1

    assert isinstance(config.LANGUAGE_FLAG_SPACING_PX, int)
    assert 0 <= config.LANGUAGE_FLAG_SPACING_PX <= 32


def test_every_supported_language_has_translation_catalog_and_flag_file() -> None:
    missing_catalogs: list[str] = []
    missing_flags: list[str] = []

    for language_code in SUPPORTED_LANGUAGES:
        catalog_path = config.resource_path(f"morsewurst/i18n/{language_code}.json")
        flag_path = config.LANGUAGE_FLAG_DIR / f"{language_code}.png"

        if not catalog_path.exists():
            missing_catalogs.append(str(catalog_path))

        if not flag_path.exists():
            missing_flags.append(str(flag_path))

    assert not missing_catalogs, "Missing translation catalogs:\n" + "\n".join(missing_catalogs)
    assert not missing_flags, "Missing language flag images:\n" + "\n".join(missing_flags)


def test_language_flag_files_match_supported_language_codes() -> None:
    flag_codes = {
        path.stem
        for path in config.LANGUAGE_FLAG_DIR.glob("*.png")
        if path.is_file()
    }
    supported_codes = set(SUPPORTED_LANGUAGES)

    missing = sorted(supported_codes - flag_codes)
    extra = sorted(flag_codes - supported_codes)

    assert not missing, (
        "These supported languages are missing flag PNG files: "
        + ", ".join(missing)
    )
    assert not extra, (
        "These flag PNG files do not have matching SUPPORTED_LANGUAGES entries: "
        + ", ".join(extra)
    )


def test_language_flags_are_valid_png_files_with_expected_dimensions() -> None:
    for language_code in SUPPORTED_LANGUAGES:
        flag_path = config.LANGUAGE_FLAG_DIR / f"{language_code}.png"

        width, height = _read_png_size(flag_path)

        assert height == EXPECTED_FLAG_HEIGHT_PX, (
            f"{flag_path} height should be {EXPECTED_FLAG_HEIGHT_PX}px, got {height}px"
        )
        assert 1 <= width <= MAX_FLAG_WIDTH_PX, (
            f"{flag_path} width should be 1-{MAX_FLAG_WIDTH_PX}px, got {width}px"
        )


def test_supported_language_catalogs_are_valid_json_objects() -> None:
    for language_code in SUPPORTED_LANGUAGES:
        catalog_path = config.resource_path(f"morsewurst/i18n/{language_code}.json")
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))

        assert isinstance(raw, dict), f"{catalog_path} must contain a JSON object"
        assert raw, f"{catalog_path} must not be empty"
