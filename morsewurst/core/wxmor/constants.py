# ============================================================
# morsewurst/core/wxmor/constants.py
# ============================================================

from __future__ import annotations

from typing import Final


WX_MOR_DISPLAY_NAME: Final[str] = "WX-MOR"

ALLOWED_CHARS: Final[str] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
ALLOWED_CHARS_PATTERN: Final[str] = r"^[A-Z0-9 ]+$"


# ============================================================
# Weather vocabulary
# ============================================================

WEATHER_CODES: Final[tuple[str, ...]] = (
    "NIL",
    "RAIN",
    "DRIZZLE",
    "SNOW",
    "SLEET",
    "HAIL",
    "SHOWER",
    "THUNDER",
    "FOG",
    "MIST",
    "HAZE",
    "ICE",
    "SLIP",
    "BLIZZ",
    "FROST",
    "DRIFT",
    "FLOOD",
    "HEAT",
    "COLD",
    "STORM",
    "GALE",
    "UNKNOWN",
)

# WX-MOR standard recommended weather ordering.
WEATHER_ORDER: Final[tuple[str, ...]] = (
    "NIL",
    "THUNDER",
    "SHOWER",
    "DRIZZLE",
    "RAIN",
    "SLEET",
    "SNOW",
    "HAIL",
    "BLIZZ",
    "FOG",
    "MIST",
    "HAZE",
    "ICE",
    "SLIP",
    "FROST",
    "DRIFT",
    "GALE",
    "STORM",
    "FLOOD",
    "HEAT",
    "COLD",
    "UNKNOWN",
)

# Weather codes that may use L or H intensity prefix.
INTENSITY_ALLOWED_BASES: Final[tuple[str, ...]] = (
    "THUNDER",
    "SHOWER",
    "DRIZZLE",
    "RAIN",
    "SLEET",
    "SNOW",
    "HAIL",
    "BLIZZ",
    "FOG",
    "MIST",
    "HAZE",
    "GALE",
    "STORM",
)

# These groups are treated as mutually exclusive in generated messages.
EXCLUSIVE_WEATHER_GROUPS: Final[tuple[tuple[str, ...], ...]] = (
    ("NIL",),
    ("FOG", "MIST", "HAZE"),
    ("GALE", "STORM"),
    ("HEAT", "COLD"),
)

# Human readable weather to compact WX-MOR aliases.
COMPACT_WEATHER_ALIASES: Final[dict[str, str]] = {
    "RAIN": "RA",
    "DRIZZLE": "DZ",
    "SNOW": "SN",
    "SLEET": "SL",
    "HAIL": "GR",
    "SHOWER": "SH",
    "THUNDER": "TS",
    "FOG": "FG",
    "MIST": "BR",
    "HAZE": "HZ",
    "ICE": "ICE",
    "SLIP": "SLP",
    "BLIZZ": "BLZ",
    "FROST": "FRS",
    "DRIFT": "DRS",
    "GALE": "GAL",
    "STORM": "STM",
    "FLOOD": "FLD",
    "HEAT": "HOT",
    "COLD": "CLD",
    "UNKNOWN": "UNK",
    "NIL": "NIL",
}

COMPACT_TO_WEATHER: Final[dict[str, str]] = {
    compact: full for full, compact in COMPACT_WEATHER_ALIASES.items()
}

COMPACT_WEATHER_COMBINATIONS: Final[dict[str, tuple[str, ...]]] = {
    "TSRA": ("THUNDER", "RAIN"),
    "SHRA": ("SHOWER", "RAIN"),
    "SHSN": ("SHOWER", "SNOW"),
}


# ============================================================
# Wind, cloud and field constants
# ============================================================

WIND_DIRECTIONS: Final[tuple[str, ...]] = (
    "N",
    "NE",
    "E",
    "SE",
    "S",
    "SW",
    "W",
    "NW",
)

COLD_WIND_DIRECTIONS: Final[tuple[str, ...]] = (
    "N",
    "NE",
    "NW",
    "W",
)

WARM_WIND_DIRECTIONS: Final[tuple[str, ...]] = (
    "S",
    "SE",
    "SW",
    "W",
)

CLOUD_COVERS: Final[tuple[str, ...]] = (
    "SKC",
    "FEW",
    "SCT",
    "BKN",
    "OVC",
    "VV",
)

CLOUDY_COVERS: Final[tuple[str, ...]] = (
    "SCT",
    "BKN",
    "OVC",
)

LOW_CLOUD_COVERS: Final[tuple[str, ...]] = (
    "BKN",
    "OVC",
    "VV",
)

PRESSURE_TREND_CODES: Final[tuple[str, ...]] = (
    "QR",
    "QF",
    "QS",
)


# ============================================================
# Scenario names
# ============================================================

SCENARIO_CLEAR_SUMMER: Final[str] = "clear_summer"
SCENARIO_CLEAR_WINTER: Final[str] = "clear_winter"
SCENARIO_CLOUDY_DRY: Final[str] = "cloudy_dry"
SCENARIO_RAIN: Final[str] = "rain"
SCENARIO_HEAVY_RAIN: Final[str] = "heavy_rain"
SCENARIO_SNOW: Final[str] = "snow"
SCENARIO_BLIZZARD: Final[str] = "blizzard"
SCENARIO_FOG: Final[str] = "fog"
SCENARIO_ICE_SLIP: Final[str] = "ice_slip"
SCENARIO_WINDY: Final[str] = "windy"
SCENARIO_STORM: Final[str] = "storm"
SCENARIO_COLD: Final[str] = "cold"
SCENARIO_HEAT: Final[str] = "heat"

ALL_SCENARIOS: Final[tuple[str, ...]] = (
    SCENARIO_CLEAR_SUMMER,
    SCENARIO_CLEAR_WINTER,
    SCENARIO_CLOUDY_DRY,
    SCENARIO_RAIN,
    SCENARIO_HEAVY_RAIN,
    SCENARIO_SNOW,
    SCENARIO_BLIZZARD,
    SCENARIO_FOG,
    SCENARIO_ICE_SLIP,
    SCENARIO_WINDY,
    SCENARIO_STORM,
    SCENARIO_COLD,
    SCENARIO_HEAT,
)