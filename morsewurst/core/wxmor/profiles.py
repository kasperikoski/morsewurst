# ============================================================
# morsewurst/core/wxmor/profiles.py
# ============================================================

from __future__ import annotations

from typing import Final

from morsewurst.core.wxmor.constants import (
    SCENARIO_BLIZZARD,
    SCENARIO_CLEAR_SUMMER,
    SCENARIO_CLEAR_WINTER,
    SCENARIO_CLOUDY_DRY,
    SCENARIO_COLD,
    SCENARIO_FOG,
    SCENARIO_HEAT,
    SCENARIO_HEAVY_RAIN,
    SCENARIO_ICE_SLIP,
    SCENARIO_RAIN,
    SCENARIO_SNOW,
    SCENARIO_STORM,
    SCENARIO_WINDY,
)


PROFILE_AUTO: Final[str] = "auto"
PROFILE_MINIMUM: Final[str] = "minimum"
PROFILE_BASIC: Final[str] = "basic"
PROFILE_COMPACT: Final[str] = "compact"
PROFILE_EXTENDED: Final[str] = "extended"

WX_MOR_PROFILES: Final[tuple[str, ...]] = (
    PROFILE_AUTO,
    PROFILE_MINIMUM,
    PROFILE_BASIC,
    PROFILE_COMPACT,
    PROFILE_EXTENDED,
)

WX_MOR_PROFILE_LABELS: Final[dict[str, str]] = {
    PROFILE_AUTO: "Auto",
    PROFILE_MINIMUM: "Minimi",
    PROFILE_BASIC: "Perus",
    PROFILE_COMPACT: "Kompakti",
    PROFILE_EXTENDED: "Laaja",
}

# Used when profile is "auto".
# These values are normalized automatically.
AUTO_PROFILE_WEIGHTS: Final[dict[str, float]] = {
    PROFILE_MINIMUM: 0.35,
    PROFILE_BASIC: 0.35,
    PROFILE_COMPACT: 0.20,
    PROFILE_EXTENDED: 0.10,
}

# Fields included by each profile.
# "WX" prefix is always added automatically.
PROFILE_FIELD_ORDER: Final[dict[str, tuple[str, ...]]] = {
    PROFILE_MINIMUM: (
        "loc",
        "time",
        "temperature",
        "weather",
    ),
    PROFILE_BASIC: (
        "loc",
        "time",
        "temperature",
        "dew_point",
        "weather",
        "wind",
        "cloud",
        "pressure",
    ),
    PROFILE_COMPACT: (
        "loc",
        "time",
        "temperature",
        "weather",
        "wind",
        "cloud",
        "visibility",
        "pressure",
        "uv_index",
        "extra",
    ),
    PROFILE_EXTENDED: (
        "loc",
        "time",
        "temperature",
        "dew_point",
        "weather",
        "wind",
        "cloud",
        "visibility",
        "pressure",
        "uv_index",
        "humidity",
        "rain_amount",
        "snow_depth",
        "new_snow",
        "extra",
    ),
}

# Default scenario weights.
# These are used unless a profile overrides them below.
DEFAULT_SCENARIO_WEIGHTS: Final[dict[str, float]] = {
    SCENARIO_CLEAR_SUMMER: 0.11,
    SCENARIO_CLEAR_WINTER: 0.08,
    SCENARIO_CLOUDY_DRY: 0.14,
    SCENARIO_RAIN: 0.15,
    SCENARIO_HEAVY_RAIN: 0.07,
    SCENARIO_SNOW: 0.12,
    SCENARIO_BLIZZARD: 0.04,
    SCENARIO_FOG: 0.08,
    SCENARIO_ICE_SLIP: 0.06,
    SCENARIO_WINDY: 0.07,
    SCENARIO_STORM: 0.03,
    SCENARIO_COLD: 0.03,
    SCENARIO_HEAT: 0.02,
}

# Profile-specific scenario weights.
# Minimum profile should not produce too many long or complex cases.
# Extended profile may include heavier or richer weather more often.
SCENARIO_WEIGHTS_BY_PROFILE: Final[dict[str, dict[str, float]]] = {
    PROFILE_MINIMUM: {
        SCENARIO_CLEAR_SUMMER: 0.14,
        SCENARIO_CLEAR_WINTER: 0.10,
        SCENARIO_CLOUDY_DRY: 0.16,
        SCENARIO_RAIN: 0.17,
        SCENARIO_HEAVY_RAIN: 0.05,
        SCENARIO_SNOW: 0.12,
        SCENARIO_BLIZZARD: 0.02,
        SCENARIO_FOG: 0.09,
        SCENARIO_ICE_SLIP: 0.05,
        SCENARIO_WINDY: 0.05,
        SCENARIO_STORM: 0.02,
        SCENARIO_COLD: 0.02,
        SCENARIO_HEAT: 0.01,
    },
    PROFILE_BASIC: DEFAULT_SCENARIO_WEIGHTS,
    PROFILE_COMPACT: DEFAULT_SCENARIO_WEIGHTS,
    PROFILE_EXTENDED: {
        SCENARIO_CLEAR_SUMMER: 0.08,
        SCENARIO_CLEAR_WINTER: 0.07,
        SCENARIO_CLOUDY_DRY: 0.11,
        SCENARIO_RAIN: 0.15,
        SCENARIO_HEAVY_RAIN: 0.09,
        SCENARIO_SNOW: 0.13,
        SCENARIO_BLIZZARD: 0.07,
        SCENARIO_FOG: 0.08,
        SCENARIO_ICE_SLIP: 0.07,
        SCENARIO_WINDY: 0.07,
        SCENARIO_STORM: 0.04,
        SCENARIO_COLD: 0.02,
        SCENARIO_HEAT: 0.02,
    },
}