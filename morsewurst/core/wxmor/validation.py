# ============================================================
# morsewurst/core/wxmor/validation.py
# ============================================================

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from morsewurst.core.wxmor.constants import (
    ALLOWED_CHARS_PATTERN,
    COMPACT_TO_WEATHER,
    COMPACT_WEATHER_COMBINATIONS,
    EXCLUSIVE_WEATHER_GROUPS,
    INTENSITY_ALLOWED_BASES,
    WEATHER_CODES,
)


_ALLOWED_RE = re.compile(ALLOWED_CHARS_PATTERN)
_TIME_RE = re.compile(r"^(?:\d{4}Z|\d{6}Z)$")
_TEMP_RE = re.compile(r"^[TD]M?\d{1,2}$")
_PRESSURE_RE = re.compile(r"^Q\d{4}$")
_PRESSURE_TREND_RE = re.compile(r"^Q[RFS]$")
_VISIBILITY_RE = re.compile(r"^(?:VOK|V\d{1,5})$")
_WIND_RE = re.compile(r"^(?:CALM|(?:(?:N|NE|E|SE|S|SW|W|NW|VRB)?\d{1,2})(?:G\d{1,2})?)$")
_CLOUD_RE = re.compile(r"^(?:SKC|FEW|SCT|BKN|OVC|VV)(?:\d{3})?$")
_UV_RE = re.compile(r"^UV\d{1,2}$")
_PERCENT_RE = re.compile(r"^RH\d{1,3}$")
_AMOUNT_RE = re.compile(r"^(?:RR|SD|NS)\d{1,3}$")
_LOCATION_RE = re.compile(r"^[A-Z0-9]{3,6}$")


@dataclass
class WxMorValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.ok = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


def normalize_message(message: str) -> str:
    value = str(message or "").upper()
    value = re.sub(r"[^A-Z0-9 ]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def validate_message_allowed(message: str) -> WxMorValidationResult:
    result = WxMorValidationResult(ok=True)
    normalized = normalize_message(message)

    if not normalized:
        result.add_error("message_empty")
        return result

    if normalized != str(message or "").strip().upper():
        result.add_error("message_contains_invalid_or_unexpected_characters")

    if not _ALLOWED_RE.fullmatch(normalized):
        result.add_error("message_contains_disallowed_characters")

    return result


def validate_wxmor_message(message: str) -> WxMorValidationResult:
    result = validate_message_allowed(message)

    normalized = normalize_message(message)
    tokens = normalized.split(" ") if normalized else []

    if not tokens:
        result.add_error("message_empty")
        return result

    if tokens[0] != "WX":
        result.add_error("message_must_start_with_WX")

    if len(tokens) < 5:
        result.add_warning("message_is_shorter_than_recommended_minimum")

    return result


def weather_base_tokens(token: str) -> list[str]:
    item = str(token or "").upper().strip()

    if not item:
        return []

    if item in COMPACT_WEATHER_COMBINATIONS:
        return list(COMPACT_WEATHER_COMBINATIONS[item])

    if len(item) >= 2 and item[0] in {"L", "H"}:
        rest = item[1:]

        if rest in COMPACT_WEATHER_COMBINATIONS:
            return list(COMPACT_WEATHER_COMBINATIONS[rest])

        return [COMPACT_TO_WEATHER.get(rest, rest)]

    return [COMPACT_TO_WEATHER.get(item, item)]


def weather_base_token(token: str) -> str:
    item = str(token or "").upper().strip()

    if item == "":
        return ""

    if len(item) >= 2 and item[0] in {"L", "H"}:
        rest = item[1:]
        return COMPACT_TO_WEATHER.get(rest, rest)

    return COMPACT_TO_WEATHER.get(item, item)


def weather_has_intensity(token: str) -> bool:
    item = str(token or "").upper().strip()
    return len(item) >= 2 and item[0] in {"L", "H"}


def sort_weather_tokens(tokens: list[str]) -> list[str]:
    from morsewurst.core.wxmor.constants import WEATHER_ORDER

    def key(token: str) -> tuple[int, str]:
        base = weather_base_token(token)
        try:
            index = WEATHER_ORDER.index(base)
        except ValueError:
            index = 999

        return index, token

    return sorted(tokens, key=key)


def validate_weather_tokens(tokens: list[str]) -> WxMorValidationResult:
    result = WxMorValidationResult(ok=True)

    cleaned = [
        str(token or "").upper().strip()
        for token in tokens
        if str(token or "").strip()
    ]

    if not cleaned:
        result.add_error("weather_missing")
        return result

    bases: list[str] = []

    for token in cleaned:
        token_bases = weather_base_tokens(token)

        if not token_bases:
            result.add_error(f"unknown_weather_token:{token}")
            continue

        for base in token_bases:
            bases.append(base)

            if base not in WEATHER_CODES:
                result.add_error(f"unknown_weather_token:{token}")
                continue

            if weather_has_intensity(token) and base not in INTENSITY_ALLOWED_BASES:
                result.add_error(f"weather_intensity_not_allowed:{token}")

    if "NIL" in bases and len(set(bases)) > 1:
        result.add_error("weather_nil_conflicts_with_other_weather")

    for group in EXCLUSIVE_WEATHER_GROUPS:
        group_hits = sorted(set(base for base in bases if base in group))

        if len(group_hits) > 1:
            result.add_error(
                "weather_exclusive_group_conflict:" + ",".join(group_hits)
            )

    return result


def validate_fields(fields: dict[str, Any]) -> WxMorValidationResult:
    result = WxMorValidationResult(ok=True)

    loc = _as_string(fields.get("loc"))
    time = _as_string(fields.get("time"))
    temperature = _as_string(fields.get("temperature"))
    dew_point = _as_string(fields.get("dew_point"))
    weather = _as_list(fields.get("weather"))
    wind = _as_string(fields.get("wind"))
    cloud = _as_list(fields.get("cloud"))
    visibility = _as_string(fields.get("visibility"))
    pressure = _as_string(fields.get("pressure"))
    uv_index = _as_string(fields.get("uv_index"))
    humidity = _as_string(fields.get("humidity"))
    rain_amount = _as_string(fields.get("rain_amount"))
    snow_depth = _as_string(fields.get("snow_depth"))
    new_snow = _as_string(fields.get("new_snow"))
    extra = _as_list(fields.get("extra"))

    if loc and not _LOCATION_RE.fullmatch(loc):
        result.add_error(f"invalid_location:{loc}")

    if time and not _TIME_RE.fullmatch(time):
        result.add_error(f"invalid_time:{time}")

    if temperature and not _TEMP_RE.fullmatch(temperature):
        result.add_error(f"invalid_temperature:{temperature}")

    if dew_point and not _TEMP_RE.fullmatch(dew_point):
        result.add_error(f"invalid_dew_point:{dew_point}")

    weather_result = validate_weather_tokens(weather)
    result.errors.extend(weather_result.errors)
    result.warnings.extend(weather_result.warnings)

    if not weather_result.ok:
        result.ok = False

    if wind and not _WIND_RE.fullmatch(wind):
        result.add_error(f"invalid_wind:{wind}")

    for cloud_item in cloud:
        if cloud_item and not _CLOUD_RE.fullmatch(cloud_item):
            result.add_error(f"invalid_cloud:{cloud_item}")

    if visibility and not _VISIBILITY_RE.fullmatch(visibility):
        result.add_error(f"invalid_visibility:{visibility}")

    if pressure and not (
        _PRESSURE_RE.fullmatch(pressure) or _PRESSURE_TREND_RE.fullmatch(pressure)
    ):
        result.add_error(f"invalid_pressure:{pressure}")

    if uv_index and not _UV_RE.fullmatch(uv_index):
        result.add_error(f"invalid_uv_index:{uv_index}")

    if humidity and not _PERCENT_RE.fullmatch(humidity):
        result.add_error(f"invalid_humidity:{humidity}")

    if rain_amount and not _AMOUNT_RE.fullmatch(rain_amount):
        result.add_error(f"invalid_rain_amount:{rain_amount}")

    if snow_depth and not _AMOUNT_RE.fullmatch(snow_depth):
        result.add_error(f"invalid_snow_depth:{snow_depth}")

    if new_snow and not _AMOUNT_RE.fullmatch(new_snow):
        result.add_error(f"invalid_new_snow:{new_snow}")

    for extra_item in extra:
        if extra_item and not re.fullmatch(r"^[A-Z0-9]{2,12}$", extra_item):
            result.add_error(f"invalid_extra:{extra_item}")

    _validate_temperature_weather_logic(
        result,
        temperature=temperature,
        weather=weather,
        snow_depth=snow_depth,
        new_snow=new_snow,
        rain_amount=rain_amount,
    )

    return result


def _validate_temperature_weather_logic(
    result: WxMorValidationResult,
    *,
    temperature: str,
    weather: list[str],
    snow_depth: str,
    new_snow: str,
    rain_amount: str,
) -> None:
    temp_value = _parse_temp(temperature)
    weather_bases = {
        base
        for token in weather
        for base in weather_base_tokens(token)
    }

    if temp_value is None:
        return

    if {"SNOW", "BLIZZ"} & weather_bases and temp_value > 3:
        result.add_error("snow_weather_too_warm")

    if "HEAT" in weather_bases and temp_value < 20:
        result.add_error("heat_weather_too_cold")

    if "COLD" in weather_bases and temp_value > -5:
        result.add_error("cold_weather_too_warm")

    if (snow_depth or new_snow) and temp_value > 5:
        result.add_warning("snow_amount_with_warm_temperature")

    if rain_amount and {"SNOW", "BLIZZ"} & weather_bases:
        result.add_warning("rain_amount_with_snow_weather")


def _parse_temp(value: str) -> int | None:
    value = str(value or "").upper().strip()

    if not value:
        return None

    if not value.startswith("T"):
        return None

    raw = value[1:]

    if raw.startswith("M"):
        try:
            return -int(raw[1:])
        except ValueError:
            return None

    try:
        return int(raw)
    except ValueError:
        return None


def _as_string(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        return " ".join(str(item) for item in value)

    return str(value).upper().strip()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [
            str(item).upper().strip()
            for item in value
            if str(item).strip()
        ]

    text = str(value).upper().strip()

    if not text:
        return []

    return [
        item.strip()
        for item in re.split(r"\s+", text)
        if item.strip()
    ]