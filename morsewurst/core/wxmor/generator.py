# ============================================================
# morsewurst/core/wxmor/generator.py
# ============================================================

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from random import Random
from typing import Any, Mapping, Sequence
from morsewurst.core.wxmor.locations import WXMOR_LOCATIONS

from morsewurst.core.wxmor.constants import (
    COLD_WIND_DIRECTIONS,
    CLOUDY_COVERS,
    COMPACT_WEATHER_ALIASES,
    LOW_CLOUD_COVERS,
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
    WARM_WIND_DIRECTIONS,
    WIND_DIRECTIONS,
)
from morsewurst.core.wxmor.profiles import (
    AUTO_PROFILE_WEIGHTS,
    PROFILE_AUTO,
    PROFILE_COMPACT,
    PROFILE_FIELD_ORDER,
    PROFILE_MINIMUM,
    SCENARIO_WEIGHTS_BY_PROFILE,
    WX_MOR_PROFILES,
)
from morsewurst.core.wxmor.validation import (
    normalize_message,
    sort_weather_tokens,
    validate_fields,
    validate_wxmor_message,
    weather_base_token,
)


@dataclass(frozen=True)
class WxMorGeneratorOptions:
    profile: str = PROFILE_AUTO
    seed: int | None = None
    locations: Sequence[str | Mapping[str, str]] | None = None
    scenario_weights: Mapping[str, float] | None = None
    max_attempts: int = 50


@dataclass(frozen=True)
class WxMorMessage:
    message: str
    profile: str
    scenario: str
    fields: dict[str, Any]


def generate_wxmor_message(
    profile: str = PROFILE_AUTO,
    *,
    seed: int | None = None,
    locations: Sequence[str | Mapping[str, str]] | None = None,
    scenario_weights: Mapping[str, float] | None = None,
    max_attempts: int = 50,
) -> WxMorMessage:
    rng = Random(seed) if seed is not None else random.SystemRandom()
    location_codes = _normalize_location_codes(locations)

    selected_profile = _resolve_profile(rng, profile)
    default_scenario_weights = SCENARIO_WEIGHTS_BY_PROFILE.get(selected_profile)

    if not default_scenario_weights:
        raise ValueError(f"Unknown WX-MOR profile: {profile}")

    effective_scenario_weights = _merge_scenario_weights(
        default_scenario_weights,
        scenario_weights,
    )

    for _attempt in range(max(1, max_attempts)):
        scenario = _weighted_choice(rng, effective_scenario_weights)

        fields = _build_scenario_fields(
            rng,
            scenario=scenario,
            location_codes=location_codes,
        )

        field_result = validate_fields(fields)

        if not field_result.ok:
            continue

        message = build_wxmor_message(fields, selected_profile)
        message = normalize_message(message)

        message_result = validate_wxmor_message(message)

        if message_result.ok:
            return WxMorMessage(
                message=message,
                profile=selected_profile,
                scenario=scenario,
                fields=fields,
            )

    raise RuntimeError("Failed to generate a valid WX-MOR message.")


def generate_from_options(options: WxMorGeneratorOptions) -> WxMorMessage:
    return generate_wxmor_message(
        profile=options.profile,
        seed=options.seed,
        locations=options.locations,
        scenario_weights=options.scenario_weights,
        max_attempts=options.max_attempts,
    )


def build_wxmor_message(fields: dict[str, Any], profile: str) -> str:
    if profile == PROFILE_AUTO:
        raise ValueError("PROFILE_AUTO must be resolved before building a message.")

    if profile not in PROFILE_FIELD_ORDER:
        raise ValueError(f"Unknown WX-MOR profile: {profile}")

    parts: list[str] = ["WX"]

    for key in PROFILE_FIELD_ORDER[profile]:
        value = fields.get(key)

        if key == "weather":
            weather_tokens = _as_list(value)

            if profile == PROFILE_MINIMUM:
                weather_tokens = minimum_weather_tokens(weather_tokens)

            if profile == PROFILE_COMPACT:
                weather_tokens = compact_weather_sequence(weather_tokens)
            else:
                weather_tokens = sort_weather_tokens(weather_tokens)

            for token in weather_tokens:
                _push(parts, token)

            continue

        _push(parts, value)

    return normalize_message(" ".join(parts))


def compact_weather_token(token: str) -> str:
    item = str(token or "").upper().strip()

    if not item:
        return ""

    if len(item) >= 2 and item[0] in {"L", "H"}:
        intensity = item[0]
        base = item[1:]
        compact = COMPACT_WEATHER_ALIASES.get(base, base)
        return intensity + compact

    return COMPACT_WEATHER_ALIASES.get(item, item)


def compact_weather_sequence(tokens: list[str]) -> list[str]:
    remaining = list(tokens)
    bases = [weather_base_token(token) for token in remaining]
    result: list[str] = []

    def has(base: str) -> bool:
        return base in bases

    def remove_first(base: str) -> None:
        for index, token in enumerate(list(remaining)):
            if weather_base_token(token) == base:
                remaining.pop(index)
                bases.pop(index)
                return

    if has("THUNDER") and has("RAIN"):
        result.append("TSRA")
        remove_first("THUNDER")
        remove_first("RAIN")

    if has("SHOWER") and has("RAIN"):
        result.append("SHRA")
        remove_first("SHOWER")
        remove_first("RAIN")

    if has("SHOWER") and has("SNOW"):
        result.append("SHSN")
        remove_first("SHOWER")
        remove_first("SNOW")

    result.extend(compact_weather_token(token) for token in remaining)

    return result


def minimum_weather_tokens(tokens: list[str]) -> list[str]:
    if not tokens:
        return []

    sorted_tokens = sort_weather_tokens(tokens)

    important_bases = {
        "THUNDER",
        "STORM",
        "BLIZZ",
        "SNOW",
        "SLEET",
        "RAIN",
        "DRIZZLE",
        "HAIL",
        "FOG",
        "MIST",
        "HAZE",
        "ICE",
        "SLIP",
        "FROST",
        "GALE",
        "HEAT",
        "COLD",
    }

    result = [
        token
        for token in sorted_tokens
        if weather_base_token(token) in important_bases
    ]

    return result[:2] if result else sorted_tokens[:1]


def _build_scenario_fields(
    rng: Random,
    *,
    scenario: str,
    location_codes: Sequence[str],
) -> dict[str, Any]:
    base = {
        "loc": rng.choice(list(location_codes)),
        "time": _random_time(rng),
        "temperature": None,
        "dew_point": None,
        "weather": ["NIL"],
        "wind": None,
        "cloud": None,
        "visibility": None,
        "pressure": _pressure(rng),
        "uv_index": None,
        "humidity": None,
        "rain_amount": None,
        "snow_depth": None,
        "new_snow": None,
        "extra": [],
    }

    if scenario == SCENARIO_CLEAR_SUMMER:
        return _scenario_clear_summer(rng, base)

    if scenario == SCENARIO_CLEAR_WINTER:
        return _scenario_clear_winter(rng, base)

    if scenario == SCENARIO_CLOUDY_DRY:
        return _scenario_cloudy_dry(rng, base)

    if scenario == SCENARIO_RAIN:
        return _scenario_rain(rng, base, heavy=False)

    if scenario == SCENARIO_HEAVY_RAIN:
        return _scenario_rain(rng, base, heavy=True)

    if scenario == SCENARIO_SNOW:
        return _scenario_snow(rng, base, blizzard=False)

    if scenario == SCENARIO_BLIZZARD:
        return _scenario_snow(rng, base, blizzard=True)

    if scenario == SCENARIO_FOG:
        return _scenario_fog(rng, base)

    if scenario == SCENARIO_ICE_SLIP:
        return _scenario_ice_slip(rng, base)

    if scenario == SCENARIO_WINDY:
        return _scenario_windy(rng, base)

    if scenario == SCENARIO_STORM:
        return _scenario_storm(rng, base)

    if scenario == SCENARIO_COLD:
        return _scenario_cold(rng, base)

    if scenario == SCENARIO_HEAT:
        return _scenario_heat(rng, base)

    raise ValueError(f"Unknown WX-MOR scenario: {scenario}")


def _scenario_clear_summer(rng: Random, fields: dict[str, Any]) -> dict[str, Any]:
    summer_type = _weighted_choice(
        rng,
        {
            "cool_clear_morning": 0.12,
            "fresh_sunny_morning": 0.10,
            "warm_sunny_day": 0.20,
            "dry_high_pressure": 0.14,
            "coastal_breeze": 0.12,
            "humid_warm_day": 0.10,
            "hot_clear_day": 0.08,
            "hazy_summer_day": 0.06,
            "calm_evening": 0.08,
        },
    )

    extra: list[str] = []

    if summer_type == "cool_clear_morning":
        temp = rng.randint(12, 18)
        dew_gap = rng.randint(3, 7)

        time = rng.choice(["0400Z", "0430Z", "0500Z", "0530Z", "0600Z", "0630Z", "0700Z"])
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=3,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud = rng.choice([
            ["SKC"],
            ["FEW030"],
            ["FEW040"],
            ["FEW050"],
            ["SCT050"],
        ])
        visibility = rng.choice(["VOK", "V9000"])
        pressure = _pressure(rng, low=1014, high=1029)
        uv_index = f"UV{rng.randint(1, 3)}"
        humidity = f"RH{rng.randint(60, 85)}"

    elif summer_type == "fresh_sunny_morning":
        temp = rng.randint(16, 22)
        dew_gap = rng.randint(5, 10)

        time = rng.choice(["0700Z", "0730Z", "0800Z", "0830Z", "0900Z", "0930Z"])
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=1,
            speed_max=4,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.05,
        )
        cloud = rng.choice([
            ["SKC"],
            ["FEW040"],
            ["FEW050"],
            ["FEW060"],
            ["SCT060"],
            ["FEW040", "SCT080"],
        ])
        visibility = "VOK"
        pressure = _pressure(rng, low=1015, high=1030)
        uv_index = f"UV{rng.randint(2, 5)}"
        humidity = f"RH{rng.randint(45, 75)}"

    elif summer_type == "warm_sunny_day":
        temp = rng.randint(20, 27)
        dew_gap = rng.randint(5, 12)

        time = rng.choice(["1000Z", "1030Z", "1100Z", "1130Z", "1200Z", "1230Z", "1300Z", "1330Z"])
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=1,
            speed_max=6,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.10,
        )
        cloud = rng.choice([
            ["SKC"],
            ["FEW050"],
            ["FEW060"],
            ["SCT050"],
            ["SCT060"],
            ["FEW050", "SCT090"],
        ])
        visibility = "VOK"
        pressure = _pressure(rng, low=1013, high=1027)
        uv_index = f"UV{rng.randint(5, 8)}"
        humidity = f"RH{rng.randint(35, 65)}"

    elif summer_type == "dry_high_pressure":
        temp = rng.randint(18, 26)
        dew_gap = rng.randint(8, 15)

        time = rng.choice(["0900Z", "1000Z", "1100Z", "1200Z", "1300Z", "1400Z"])
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=4,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud = rng.choice([
            ["SKC"],
            ["SKC"],
            ["FEW060"],
            ["FEW080"],
        ])
        visibility = "VOK"
        pressure = _pressure(rng, low=1020, high=1034)
        uv_index = f"UV{rng.randint(4, 8)}"
        humidity = f"RH{rng.randint(25, 50)}"
        extra = rng.choice([
            [],
            ["DRY"],
            ["SUNNY"],
        ])

    elif summer_type == "coastal_breeze":
        temp = rng.randint(17, 24)
        dew_gap = rng.randint(4, 9)

        time = rng.choice(["1000Z", "1100Z", "1200Z", "1300Z", "1400Z", "1500Z"])
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=3,
            speed_max=8,
            directions=("S", "SE", "SW", "W"),
            gust_chance=0.15,
        )
        cloud = rng.choice([
            ["SKC"],
            ["FEW040"],
            ["FEW050"],
            ["SCT050"],
            ["FEW040", "SCT070"],
        ])
        visibility = "VOK"
        pressure = _pressure(rng, low=1012, high=1025)
        uv_index = f"UV{rng.randint(4, 7)}"
        humidity = f"RH{rng.randint(45, 75)}"
        extra = rng.choice([
            [],
            ["SEA BREEZE"],
            ["COASTAL"],
        ])

    elif summer_type == "humid_warm_day":
        temp = rng.randint(21, 28)
        dew_gap = rng.randint(2, 6)

        time = rng.choice(["0900Z", "1000Z", "1100Z", "1200Z", "1300Z", "1400Z", "1500Z"])
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=1,
            speed_max=5,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.10,
        )
        cloud = rng.choice([
            ["FEW040"],
            ["SCT040"],
            ["SCT050"],
            ["FEW040", "SCT070"],
        ])
        visibility = rng.choice(["VOK", "V9000"])
        pressure = _pressure(rng, low=1009, high=1022)
        uv_index = f"UV{rng.randint(4, 7)}"
        humidity = f"RH{rng.randint(65, 88)}"
        extra = rng.choice([
            [],
            ["HUMID"],
        ])

    elif summer_type == "hot_clear_day":
        temp = rng.randint(28, 33)
        dew_gap = rng.randint(6, 14)

        time = rng.choice(["1000Z", "1100Z", "1200Z", "1300Z", "1400Z"])
        weather = ["HEAT"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=5,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.05,
        )
        cloud = rng.choice([
            ["SKC"],
            ["FEW060"],
            ["FEW080"],
            ["SCT080"],
        ])
        visibility = "VOK"
        pressure = _pressure(rng, low=1012, high=1028)
        uv_index = f"UV{rng.randint(6, 9)}"
        humidity = f"RH{rng.randint(25, 55)}"
        extra = rng.choice([
            [],
            ["HOT"],
            ["SUNNY"],
        ])

    elif summer_type == "hazy_summer_day":
        temp = rng.randint(22, 30)
        dew_gap = rng.randint(4, 10)

        time = rng.choice(["0900Z", "1000Z", "1100Z", "1200Z", "1300Z", "1400Z"])
        weather = [rng.choice(["HAZE", "LHAZE"])]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=4,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud = rng.choice([
            ["SKC"],
            ["FEW060"],
            ["SCT070"],
        ])
        visibility = rng.choice(["V7000", "V8000", "V9000"])
        pressure = _pressure(rng, low=1012, high=1026)
        uv_index = f"UV{rng.randint(4, 8)}"
        humidity = f"RH{rng.randint(40, 70)}"
        extra = rng.choice([
            [],
            ["HAZY"],
        ])

    else:  # calm_evening
        temp = rng.randint(16, 24)
        dew_gap = rng.randint(3, 8)

        time = rng.choice(["1600Z", "1700Z", "1800Z", "1900Z", "2000Z"])
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=3,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud = rng.choice([
            ["SKC"],
            ["FEW040"],
            ["FEW060"],
            ["SCT060"],
        ])
        visibility = "VOK"
        pressure = _pressure(rng, low=1013, high=1027)
        uv_index = f"UV{rng.randint(0, 3)}"
        humidity = f"RH{rng.randint(50, 80)}"
        extra = rng.choice([
            [],
            ["EVENING"],
            ["CALM"],
        ])

    fields.update(
        time=time,
        temperature=_signed("T", temp),
        dew_point=_signed("D", temp - dew_gap),
        weather=weather,
        wind=wind,
        cloud=cloud,
        visibility=visibility,
        pressure=pressure,
        uv_index=uv_index,
        humidity=humidity,
        rain_amount=None,
        snow_depth=None,
        new_snow=None,
        extra=extra,
    )

    return fields


def _scenario_clear_winter(rng: Random, fields: dict[str, Any]) -> dict[str, Any]:
    winter_type = _weighted_choice(
        rng,
        {
            "cold_clear_morning": 0.14,
            "dry_high_pressure_frost": 0.16,
            "arctic_cold": 0.10,
            "sunny_winter_day": 0.16,
            "calm_snowy_evening": 0.12,
            "clear_breezy_winter": 0.10,
            "late_winter_sun": 0.10,
            "frosty_mild_winter": 0.08,
            "very_dry_cold": 0.04,
        },
    )

    extra: list[str] = []

    if winter_type == "cold_clear_morning":
        temp = rng.randint(-18, -6)
        dew_gap = rng.randint(2, 6)

        time = rng.choice(["0400Z", "0430Z", "0500Z", "0530Z", "0600Z", "0630Z", "0700Z", "0730Z"])
        weather = rng.choice([
            ["NIL"],
            ["FROST"],
        ])
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=3,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud = rng.choice([
            ["SKC"],
            ["SKC"],
            ["FEW020"],
            ["FEW030"],
            ["SCT040"],
        ])
        visibility = rng.choice(["VOK", "V7000", "V9000"])
        pressure = _pressure(rng, low=1018, high=1036)
        humidity = f"RH{rng.randint(65, 92)}"
        snow_depth = f"SD{rng.randint(5, 65)}"
        extra = rng.choice([
            [],
            ["FROST"],
            ["CLEAR"],
        ])

    elif winter_type == "dry_high_pressure_frost":
        temp = rng.randint(-20, -7)
        dew_gap = rng.randint(5, 12)

        time = rng.choice(["0600Z", "0700Z", "0800Z", "0900Z", "1000Z", "1100Z", "1200Z"])
        weather = rng.choice([
            ["NIL"],
            ["FROST"],
        ])
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=3,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud = rng.choice([
            ["SKC"],
            ["SKC"],
            ["FEW030"],
            ["FEW050"],
        ])
        visibility = rng.choice(["VOK", "VOK", "V9000"])
        pressure = _pressure(rng, low=1025, high=1042)
        humidity = f"RH{rng.randint(45, 75)}"
        snow_depth = f"SD{rng.randint(5, 70)}"
        extra = rng.choice([
            [],
            ["DRY"],
            ["HIGH PRESSURE"],
            ["FROST"],
        ])

    elif winter_type == "arctic_cold":
        temp = rng.randint(-32, -18)
        dew_gap = rng.randint(3, 10)

        time = rng.choice(["0300Z", "0400Z", "0500Z", "0600Z", "0700Z", "0800Z"])
        weather = rng.choice([
            ["COLD"],
            ["FROST"],
        ])
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=4,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.05,
        )
        cloud = rng.choice([
            ["SKC"],
            ["SKC"],
            ["FEW020"],
            ["FEW040"],
        ])
        visibility = rng.choice(["VOK", "V7000", "V9000"])
        pressure = _pressure(rng, low=1018, high=1040)
        humidity = f"RH{rng.randint(55, 85)}"
        snow_depth = f"SD{rng.randint(15, 90)}"
        extra = rng.choice([
            [],
            ["ARCTIC"],
            ["KYLMA"],
            ["FROST"],
        ])

    elif winter_type == "sunny_winter_day":
        temp = rng.randint(-12, -1)
        dew_gap = rng.randint(2, 7)

        time = rng.choice(["0900Z", "1000Z", "1100Z", "1200Z", "1300Z", "1400Z"])
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=1,
            speed_max=5,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.05,
        )
        cloud = rng.choice([
            ["SKC"],
            ["FEW030"],
            ["FEW050"],
            ["SCT050"],
            ["FEW030", "SCT070"],
        ])
        visibility = "VOK"
        pressure = _pressure(rng, low=1015, high=1032)
        humidity = f"RH{rng.randint(50, 80)}"
        snow_depth = f"SD{rng.randint(3, 60)}"
        extra = rng.choice([
            [],
            ["SUNNY"],
            ["CLEAR"],
        ])

    elif winter_type == "calm_snowy_evening":
        temp = rng.randint(-16, -4)
        dew_gap = rng.randint(1, 5)

        time = rng.choice(["1500Z", "1600Z", "1700Z", "1800Z", "1900Z", "2000Z"])
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=2,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud = rng.choice([
            ["SKC"],
            ["FEW020"],
            ["FEW040"],
            ["SCT050"],
        ])
        visibility = rng.choice(["VOK", "V8000", "V9000"])
        pressure = _pressure(rng, low=1016, high=1034)
        humidity = f"RH{rng.randint(65, 90)}"
        snow_depth = f"SD{rng.randint(10, 80)}"
        extra = rng.choice([
            [],
            ["EVENING"],
            ["CALM"],
        ])

    elif winter_type == "clear_breezy_winter":
        temp = rng.randint(-15, -3)
        dew_gap = rng.randint(3, 8)

        time = rng.choice(["0800Z", "0900Z", "1000Z", "1100Z", "1200Z", "1300Z", "1400Z"])
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=4,
            speed_max=8,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.25,
        )
        cloud = rng.choice([
            ["SKC"],
            ["FEW030"],
            ["SCT040"],
            ["SCT060"],
        ])
        visibility = rng.choice(["VOK", "V9000"])
        pressure = _pressure(rng, low=1012, high=1028)
        humidity = f"RH{rng.randint(50, 82)}"
        snow_depth = f"SD{rng.randint(5, 65)}"
        extra = rng.choice([
            [],
            ["BREEZY"],
            ["CLEAR"],
        ])

    elif winter_type == "late_winter_sun":
        temp = rng.randint(-6, 3)
        dew_gap = rng.randint(2, 7)

        time = rng.choice(["0900Z", "1000Z", "1100Z", "1200Z", "1300Z", "1400Z", "1500Z"])
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=1,
            speed_max=5,
            directions=("S", "SE", "SW", "W"),
            gust_chance=0.05,
        )
        cloud = rng.choice([
            ["SKC"],
            ["FEW040"],
            ["FEW060"],
            ["SCT060"],
        ])
        visibility = "VOK"
        pressure = _pressure(rng, low=1012, high=1028)
        humidity = f"RH{rng.randint(45, 75)}"
        snow_depth = rng.choice([
            f"SD{rng.randint(1, 25)}",
            f"SD{rng.randint(10, 45)}",
            None,
        ])
        extra = rng.choice([
            [],
            ["SUNNY"],
            ["LATEWINTER"],
        ])

    elif winter_type == "frosty_mild_winter":
        temp = rng.randint(-5, 1)
        dew_gap = rng.randint(1, 4)

        time = rng.choice(["0500Z", "0600Z", "0700Z", "0800Z", "0900Z"])
        weather = rng.choice([
            ["NIL"],
            ["FROST"],
        ])
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=3,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud = rng.choice([
            ["SKC"],
            ["FEW020"],
            ["SCT030"],
            ["SCT050"],
        ])
        visibility = rng.choice(["VOK", "V7000", "V9000"])
        pressure = _pressure(rng, low=1014, high=1030)
        humidity = f"RH{rng.randint(70, 95)}"
        snow_depth = rng.choice([
            f"SD{rng.randint(1, 30)}",
            None,
        ])
        extra = rng.choice([
            [],
            ["FROST"],
            ["ICYGROUND"],
        ])

    else:  # very_dry_cold
        temp = rng.randint(-25, -10)
        dew_gap = rng.randint(8, 18)

        time = rng.choice(["0600Z", "0700Z", "0800Z", "0900Z", "1000Z", "1100Z"])
        weather = rng.choice([
            ["NIL"],
            ["COLD"],
        ])
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=4,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud = rng.choice([
            ["SKC"],
            ["SKC"],
            ["FEW050"],
        ])
        visibility = "VOK"
        pressure = _pressure(rng, low=1020, high=1042)
        humidity = f"RH{rng.randint(35, 65)}"
        snow_depth = f"SD{rng.randint(5, 70)}"
        extra = rng.choice([
            [],
            ["DRY"],
            ["COLD"],
        ])

    fields.update(
        time=time,
        temperature=_signed("T", temp),
        dew_point=_signed("D", temp - dew_gap),
        weather=weather,
        wind=wind,
        cloud=cloud,
        visibility=visibility,
        pressure=pressure,
        uv_index="UV0",
        humidity=humidity,
        rain_amount=None,
        snow_depth=snow_depth,
        new_snow=None,
        extra=extra,
    )

    return fields


def _scenario_cloudy_dry(rng: Random, fields: dict[str, Any]) -> dict[str, Any]:
    temp = rng.randint(-5, 14)

    fields.update(
        temperature=_signed("T", temp),
        dew_point=_signed("D", temp - rng.randint(2, 8)),
        weather=["NIL"],
        wind=_wind(rng, speed_min=1, speed_max=7, directions=WIND_DIRECTIONS),
        cloud=_clouds(rng, covers=CLOUDY_COVERS, height_chance=0.45),
        visibility=rng.choice(["VOK", "V8000", "V9000"]),
        pressure=_pressure(rng, low=1002, high=1024),
        uv_index=f"UV{rng.randint(0, 3)}",
        humidity=f"RH{rng.randint(55, 88)}",
    )

    return fields


def _scenario_rain(
    rng: Random,
    fields: dict[str, Any],
    *,
    heavy: bool,
) -> dict[str, Any]:
    extra: list[str] = []

    if heavy:
        rain_type = _weighted_choice(
            rng,
            {
                "steady_heavy_rain": 0.24,
                "heavy_showers": 0.18,
                "thunder_rain": 0.16,
                "windy_heavy_rain": 0.16,
                "cold_heavy_rain": 0.10,
                "coastal_heavy_rain": 0.08,
                "low_cloud_heavy_rain": 0.08,
            },
        )

        if rain_type == "steady_heavy_rain":
            temp = rng.randint(5, 16)
            dew_gap = rng.randint(0, 3)
            weather = [rng.choice(["HRAIN", "RAIN"])]
            wind = _wind(
                rng,
                speed_min=4,
                speed_max=10,
                directions=WARM_WIND_DIRECTIONS,
                gust_chance=0.45,
            )
            cloud_covers = ("BKN", "OVC")
            height_chance = 0.70
            visibility = rng.choice(["V1500", "V2000", "V3000", "V5000"])
            pressure = _pressure(rng, low=992, high=1010)
            uv_index = f"UV{rng.randint(0, 1)}"
            humidity = f"RH{rng.randint(88, 100)}"
            rain_amount = f"RR{rng.randint(6, 18)}"
            extra = rng.choice([
                [],
                ["WET"],
                ["SOAKED"],
            ])

        elif rain_type == "heavy_showers":
            temp = rng.randint(6, 18)
            dew_gap = rng.randint(1, 5)
            weather = [rng.choice(["HSHOWER", "SHOWER"]), rng.choice(["RAIN", "HRAIN"])]
            wind = _wind(
                rng,
                speed_min=3,
                speed_max=12,
                directions=WIND_DIRECTIONS,
                gust_chance=0.75,
            )
            cloud_covers = ("SCT", "BKN", "OVC")
            height_chance = 0.60
            visibility = rng.choice(["V2000", "V3000", "V5000", "V7000"])
            pressure = _pressure(rng, low=990, high=1012)
            uv_index = f"UV{rng.randint(0, 2)}"
            humidity = f"RH{rng.randint(78, 98)}"
            rain_amount = f"RR{rng.randint(4, 14)}"
            extra = rng.choice([
                [],
                ["SHOWERY"],
                ["BURSTS"],
            ])

        elif rain_type == "thunder_rain":
            temp = rng.randint(12, 23)
            dew_gap = rng.randint(0, 4)
            weather = ["THUNDER", rng.choice(["RAIN", "HRAIN", "SHOWER"])]
            wind = _wind(
                rng,
                speed_min=4,
                speed_max=14,
                directions=WIND_DIRECTIONS,
                gust_chance=0.90,
            )
            cloud_covers = ("BKN", "OVC")
            height_chance = 0.75
            visibility = rng.choice(["V1500", "V2000", "V3000", "V5000", "V8000"])
            pressure = _pressure(rng, low=988, high=1008)
            uv_index = f"UV{rng.randint(0, 3)}"
            humidity = f"RH{rng.randint(80, 99)}"
            rain_amount = f"RR{rng.randint(5, 22)}"
            extra = rng.choice([
                [],
                ["CB"],
                ["DISTANTTS"],
                ["FLASHES"],
            ])

        elif rain_type == "windy_heavy_rain":
            temp = rng.randint(4, 15)
            dew_gap = rng.randint(1, 5)
            weather = [rng.choice(["RAIN", "HRAIN"]), rng.choice(["GALE", "LGALE"])]
            wind = _wind(
                rng,
                speed_min=9,
                speed_max=17,
                directions=WIND_DIRECTIONS,
                gust_chance=0.95,
            )
            cloud_covers = ("BKN", "OVC")
            height_chance = 0.70
            visibility = rng.choice(["V2000", "V3000", "V5000", "V7000"])
            pressure = _pressure(rng, low=982, high=1004)
            uv_index = f"UV{rng.randint(0, 1)}"
            humidity = f"RH{rng.randint(80, 98)}"
            rain_amount = f"RR{rng.randint(4, 16)}"
            extra = rng.choice([
                [],
                ["WINDRAIN"],
                ["SQUALL"],
            ])

        elif rain_type == "cold_heavy_rain":
            temp = rng.randint(2, 7)
            dew_gap = rng.randint(0, 3)
            weather = [rng.choice(["RAIN", "HRAIN"])]
            wind = _wind(
                rng,
                speed_min=3,
                speed_max=10,
                directions=COLD_WIND_DIRECTIONS,
                gust_chance=0.50,
            )
            cloud_covers = ("BKN", "OVC", "VV")
            height_chance = 0.75
            visibility = rng.choice(["V1500", "V2000", "V3000", "V5000"])
            pressure = _pressure(rng, low=988, high=1010)
            uv_index = "UV0"
            humidity = f"RH{rng.randint(85, 100)}"
            rain_amount = f"RR{rng.randint(4, 14)}"
            extra = rng.choice([
                [],
                ["COLDRAIN"],
                ["RAW"],
            ])

        elif rain_type == "coastal_heavy_rain":
            temp = rng.randint(6, 15)
            dew_gap = rng.randint(0, 4)
            weather = [rng.choice(["RAIN", "HRAIN"])]
            wind = _wind(
                rng,
                speed_min=6,
                speed_max=13,
                directions=("S", "SE", "SW", "W"),
                gust_chance=0.70,
            )
            cloud_covers = ("BKN", "OVC")
            height_chance = 0.65
            visibility = rng.choice(["V2000", "V3000", "V5000", "V8000"])
            pressure = _pressure(rng, low=990, high=1010)
            uv_index = f"UV{rng.randint(0, 1)}"
            humidity = f"RH{rng.randint(82, 98)}"
            rain_amount = f"RR{rng.randint(4, 15)}"
            extra = rng.choice([
                [],
                ["COASTAL"],
                ["SEAWIND"],
            ])

        else:  # low_cloud_heavy_rain
            temp = rng.randint(4, 13)
            dew_gap = rng.randint(0, 2)
            weather = [rng.choice(["RAIN", "HRAIN"]), rng.choice(["MIST", "LHAZE"])]
            wind = _wind(
                rng,
                speed_min=2,
                speed_max=8,
                directions=WIND_DIRECTIONS,
                gust_chance=0.30,
            )
            cloud_covers = ("OVC", "VV")
            height_chance = 0.90
            visibility = rng.choice(["V800", "V1000", "V1500", "V2000", "V3000"])
            pressure = _pressure(rng, low=992, high=1012)
            uv_index = "UV0"
            humidity = f"RH{rng.randint(90, 100)}"
            rain_amount = f"RR{rng.randint(3, 12)}"
            extra = rng.choice([
                [],
                ["LOWCLOUD"],
                ["DAMP"],
            ])

    else:
        rain_type = _weighted_choice(
            rng,
            {
                "light_rain": 0.20,
                "drizzle": 0.18,
                "steady_rain": 0.20,
                "misty_rain": 0.12,
                "warm_rain": 0.10,
                "cool_autumn_rain": 0.10,
                "passing_shower": 0.07,
                "coastal_light_rain": 0.03,
            },
        )

        if rain_type == "light_rain":
            temp = rng.randint(5, 17)
            dew_gap = rng.randint(1, 5)
            weather = ["LRAIN"]
            wind = _wind(
                rng,
                speed_min=1,
                speed_max=6,
                directions=WARM_WIND_DIRECTIONS,
                gust_chance=0.10,
            )
            cloud_covers = ("SCT", "BKN", "OVC")
            height_chance = 0.55
            visibility = rng.choice(["V6000", "V8000", "V9000", "VOK"])
            pressure = _pressure(rng, low=1000, high=1018)
            uv_index = f"UV{rng.randint(0, 2)}"
            humidity = f"RH{rng.randint(70, 92)}"
            rain_amount = f"RR{rng.randint(1, 3)}"
            extra = rng.choice([
                [],
                ["LIGHT"],
            ])

        elif rain_type == "drizzle":
            temp = rng.randint(3, 14)
            dew_gap = rng.randint(0, 3)
            weather = [rng.choice(["DRIZZLE", "LDRIZZLE"])]
            wind = _wind(
                rng,
                speed_min=0,
                speed_max=4,
                directions=WIND_DIRECTIONS,
                gust_chance=0.05,
            )
            cloud_covers = ("BKN", "OVC", "VV")
            height_chance = 0.80
            visibility = rng.choice(["V3000", "V4000", "V5000", "V6000", "V8000"])
            pressure = _pressure(rng, low=1002, high=1020)
            uv_index = f"UV{rng.randint(0, 1)}"
            humidity = f"RH{rng.randint(82, 100)}"
            rain_amount = f"RR{rng.randint(1, 2)}"
            extra = rng.choice([
                [],
                ["DAMP"],
                ["GREY"],
            ])

        elif rain_type == "steady_rain":
            temp = rng.randint(4, 16)
            dew_gap = rng.randint(0, 4)
            weather = [rng.choice(["RAIN", "LRAIN"])]
            wind = _wind(
                rng,
                speed_min=2,
                speed_max=8,
                directions=WARM_WIND_DIRECTIONS,
                gust_chance=0.25,
            )
            cloud_covers = ("BKN", "OVC")
            height_chance = 0.65
            visibility = rng.choice(["V4000", "V5000", "V6000", "V8000"])
            pressure = _pressure(rng, low=996, high=1016)
            uv_index = f"UV{rng.randint(0, 2)}"
            humidity = f"RH{rng.randint(78, 98)}"
            rain_amount = f"RR{rng.randint(1, 5)}"
            extra = rng.choice([
                [],
                ["STEADY"],
            ])

        elif rain_type == "misty_rain":
            temp = rng.randint(3, 12)
            dew_gap = rng.randint(0, 2)
            weather = [rng.choice(["LRAIN", "DRIZZLE"]), "MIST"]
            wind = _wind(
                rng,
                speed_min=0,
                speed_max=4,
                directions=WIND_DIRECTIONS,
                gust_chance=0.05,
            )
            cloud_covers = ("BKN", "OVC", "VV")
            height_chance = 0.85
            visibility = rng.choice(["V1000", "V1500", "V2000", "V3000", "V5000"])
            pressure = _pressure(rng, low=998, high=1018)
            uv_index = "UV0"
            humidity = f"RH{rng.randint(90, 100)}"
            rain_amount = f"RR{rng.randint(1, 4)}"
            extra = rng.choice([
                [],
                ["DAMP"],
                ["MISTY"],
            ])

        elif rain_type == "warm_rain":
            temp = rng.randint(15, 23)
            dew_gap = rng.randint(1, 5)
            weather = [rng.choice(["RAIN", "LRAIN", "SHOWER"])]
            wind = _wind(
                rng,
                speed_min=1,
                speed_max=7,
                directions=WARM_WIND_DIRECTIONS,
                gust_chance=0.20,
            )
            cloud_covers = ("SCT", "BKN", "OVC")
            height_chance = 0.55
            visibility = rng.choice(["V5000", "V7000", "V8000", "V9000"])
            pressure = _pressure(rng, low=1000, high=1018)
            uv_index = f"UV{rng.randint(1, 4)}"
            humidity = f"RH{rng.randint(70, 95)}"
            rain_amount = f"RR{rng.randint(1, 6)}"
            extra = rng.choice([
                [],
                ["WARMRAIN"],
                ["HUMID"],
            ])

        elif rain_type == "cool_autumn_rain":
            temp = rng.randint(2, 9)
            dew_gap = rng.randint(0, 4)
            weather = [rng.choice(["RAIN", "LRAIN", "DRIZZLE"])]
            wind = _wind(
                rng,
                speed_min=2,
                speed_max=9,
                directions=WIND_DIRECTIONS,
                gust_chance=0.35,
            )
            cloud_covers = ("BKN", "OVC")
            height_chance = 0.70
            visibility = rng.choice(["V3000", "V5000", "V6000", "V8000"])
            pressure = _pressure(rng, low=992, high=1014)
            uv_index = "UV0"
            humidity = f"RH{rng.randint(80, 99)}"
            rain_amount = f"RR{rng.randint(1, 6)}"
            extra = rng.choice([
                [],
                ["RAW"],
                ["COLDRAIN"],
            ])

        elif rain_type == "passing_shower":
            temp = rng.randint(7, 18)
            dew_gap = rng.randint(2, 7)
            weather = [rng.choice(["SHOWER", "LSHOWER", "RAIN"])]
            wind = _wind(
                rng,
                speed_min=2,
                speed_max=9,
                directions=WIND_DIRECTIONS,
                gust_chance=0.45,
            )
            cloud_covers = ("FEW", "SCT", "BKN")
            height_chance = 0.45
            visibility = rng.choice(["V5000", "V7000", "V9000", "VOK"])
            pressure = _pressure(rng, low=998, high=1018)
            uv_index = f"UV{rng.randint(0, 3)}"
            humidity = f"RH{rng.randint(65, 90)}"
            rain_amount = f"RR{rng.randint(1, 4)}"
            extra = rng.choice([
                [],
                ["PASSING"],
                ["SHOWERY"],
            ])

        else:  # coastal_light_rain
            temp = rng.randint(5, 14)
            dew_gap = rng.randint(1, 5)
            weather = [rng.choice(["LRAIN", "DRIZZLE", "RAIN"])]
            wind = _wind(
                rng,
                speed_min=3,
                speed_max=9,
                directions=("S", "SE", "SW", "W"),
                gust_chance=0.30,
            )
            cloud_covers = ("BKN", "OVC")
            height_chance = 0.65
            visibility = rng.choice(["V4000", "V6000", "V8000", "V9000"])
            pressure = _pressure(rng, low=998, high=1016)
            uv_index = f"UV{rng.randint(0, 2)}"
            humidity = f"RH{rng.randint(78, 96)}"
            rain_amount = f"RR{rng.randint(1, 5)}"
            extra = rng.choice([
                [],
                ["COASTAL"],
                ["SEAWIND"],
            ])

    fields.update(
        temperature=_signed("T", temp),
        dew_point=_signed("D", temp - dew_gap),
        weather=weather,
        wind=wind,
        cloud=_clouds(rng, covers=cloud_covers, height_chance=height_chance),
        visibility=visibility,
        pressure=pressure,
        uv_index=uv_index,
        humidity=humidity,
        rain_amount=rain_amount,
        snow_depth=None,
        new_snow=None,
        extra=extra,
    )

    return fields


def _scenario_snow(
    rng: Random,
    fields: dict[str, Any],
    *,
    blizzard: bool,
) -> dict[str, Any]:
    extra: list[str] = []

    if blizzard:
        snow_type = _weighted_choice(
            rng,
            {
                "classic_blizzard": 0.24,
                "whiteout_blizzard": 0.16,
                "dry_powder_blizzard": 0.14,
                "coastal_blizzard": 0.12,
                "drifting_snow": 0.14,
                "wet_near_zero_blizzard": 0.08,
                "night_blizzard": 0.08,
                "arctic_blowing_snow": 0.04,
            },
        )

        if snow_type == "classic_blizzard":
            temp = rng.randint(-14, -3)
            dew_gap = rng.randint(1, 5)
            weather = ["HSNOW", "BLIZZ"]
            wind = _wind(
                rng,
                speed_min=8,
                speed_max=16,
                directions=COLD_WIND_DIRECTIONS,
                gust_chance=0.90,
            )
            cloud_covers = ("OVC",)
            height_chance = 0.80
            visibility = rng.choice(["V500", "V800", "V1000", "V1500"])
            pressure = _pressure(rng, low=985, high=1004)
            humidity = f"RH{rng.randint(80, 98)}"
            snow_depth = f"SD{rng.randint(10, 70)}"
            new_snow = f"NS{rng.randint(3, 18)}"
            extra = rng.choice([
                [],
                ["LOWVIS"],
                ["ROADSNOW"],
            ])

        elif snow_type == "whiteout_blizzard":
            temp = rng.randint(-12, -4)
            dew_gap = rng.randint(1, 4)
            weather = ["HSNOW", "BLIZZ", "DRIFT"]
            wind = _wind(
                rng,
                speed_min=10,
                speed_max=20,
                directions=COLD_WIND_DIRECTIONS,
                gust_chance=1.00,
            )
            cloud_covers = ("OVC", "VV")
            height_chance = 0.95
            visibility = rng.choice(["V200", "V300", "V500", "V800"])
            pressure = _pressure(rng, low=980, high=1000)
            humidity = f"RH{rng.randint(84, 100)}"
            snow_depth = f"SD{rng.randint(20, 90)}"
            new_snow = f"NS{rng.randint(8, 28)}"
            extra = rng.choice([
                ["WHITEOUT"],
                ["LOWVIS"],
                ["CLOSED"],
            ])

        elif snow_type == "dry_powder_blizzard":
            temp = rng.randint(-24, -10)
            dew_gap = rng.randint(4, 10)
            weather = ["SNOW", "BLIZZ", "DRIFT"]
            wind = _wind(
                rng,
                speed_min=7,
                speed_max=15,
                directions=COLD_WIND_DIRECTIONS,
                gust_chance=0.85,
            )
            cloud_covers = ("BKN", "OVC")
            height_chance = 0.70
            visibility = rng.choice(["V800", "V1000", "V1500", "V2000"])
            pressure = _pressure(rng, low=995, high=1018)
            humidity = f"RH{rng.randint(65, 88)}"
            snow_depth = f"SD{rng.randint(15, 85)}"
            new_snow = f"NS{rng.randint(2, 12)}"
            extra = rng.choice([
                [],
                ["POWDER"],
                ["DRY"],
            ])

        elif snow_type == "coastal_blizzard":
            temp = rng.randint(-8, -1)
            dew_gap = rng.randint(1, 4)
            weather = ["HSNOW", "BLIZZ"]
            wind = _wind(
                rng,
                speed_min=9,
                speed_max=18,
                directions=("N", "NE", "E", "SE", "NW"),
                gust_chance=0.95,
            )
            cloud_covers = ("OVC", "VV")
            height_chance = 0.85
            visibility = rng.choice(["V300", "V500", "V800", "V1000", "V1500"])
            pressure = _pressure(rng, low=982, high=1004)
            humidity = f"RH{rng.randint(85, 100)}"
            snow_depth = f"SD{rng.randint(10, 75)}"
            new_snow = f"NS{rng.randint(5, 22)}"
            extra = rng.choice([
                [],
                ["COASTAL"],
                ["SEASNOW"],
            ])

        elif snow_type == "drifting_snow":
            temp = rng.randint(-18, -5)
            dew_gap = rng.randint(2, 7)
            weather = [rng.choice(["SNOW", "LSNOW"]), "DRIFT"]
            wind = _wind(
                rng,
                speed_min=8,
                speed_max=17,
                directions=COLD_WIND_DIRECTIONS,
                gust_chance=0.90,
            )
            cloud_covers = ("SCT", "BKN", "OVC")
            height_chance = 0.55
            visibility = rng.choice(["V800", "V1000", "V1500", "V2000", "V3000"])
            pressure = _pressure(rng, low=990, high=1015)
            humidity = f"RH{rng.randint(70, 95)}"
            snow_depth = f"SD{rng.randint(15, 90)}"
            new_snow = f"NS{rng.randint(1, 8)}"
            extra = rng.choice([
                [],
                ["DRIFTING"],
                ["ROADSNOW"],
            ])

        elif snow_type == "wet_near_zero_blizzard":
            temp = rng.randint(-3, 1)
            dew_gap = rng.randint(0, 3)
            weather = ["HSNOW", "BLIZZ", rng.choice(["SLIP", "ICE"])]
            wind = _wind(
                rng,
                speed_min=7,
                speed_max=15,
                directions=WIND_DIRECTIONS,
                gust_chance=0.85,
            )
            cloud_covers = ("OVC", "VV")
            height_chance = 0.85
            visibility = rng.choice(["V500", "V800", "V1000", "V1500"])
            pressure = _pressure(rng, low=985, high=1006)
            humidity = f"RH{rng.randint(88, 100)}"
            snow_depth = f"SD{rng.randint(3, 45)}"
            new_snow = f"NS{rng.randint(3, 15)}"
            extra = rng.choice([
                [],
                ["WETSNOW"],
                ["SLUSH"],
            ])

        elif snow_type == "night_blizzard":
            temp = rng.randint(-18, -4)
            dew_gap = rng.randint(1, 5)
            weather = ["HSNOW", "BLIZZ"]
            wind = _wind(
                rng,
                speed_min=8,
                speed_max=16,
                directions=COLD_WIND_DIRECTIONS,
                gust_chance=0.95,
            )
            cloud_covers = ("OVC", "VV")
            height_chance = 0.90
            visibility = rng.choice(["V300", "V500", "V800", "V1000"])
            pressure = _pressure(rng, low=982, high=1005)
            humidity = f"RH{rng.randint(82, 99)}"
            snow_depth = f"SD{rng.randint(10, 80)}"
            new_snow = f"NS{rng.randint(4, 20)}"
            extra = rng.choice([
                ["NIGHT"],
                ["DARK"],
                ["LOWVIS"],
            ])

        else:  # arctic_blowing_snow
            temp = rng.randint(-30, -16)
            dew_gap = rng.randint(4, 12)
            weather = ["COLD", "BLIZZ", "DRIFT"]
            wind = _wind(
                rng,
                speed_min=7,
                speed_max=16,
                directions=COLD_WIND_DIRECTIONS,
                gust_chance=0.85,
            )
            cloud_covers = ("SCT", "BKN", "OVC")
            height_chance = 0.50
            visibility = rng.choice(["V500", "V800", "V1000", "V1500", "V2000"])
            pressure = _pressure(rng, low=998, high=1030)
            humidity = f"RH{rng.randint(55, 82)}"
            snow_depth = f"SD{rng.randint(20, 100)}"
            new_snow = rng.choice([
                f"NS{rng.randint(1, 6)}",
                None,
            ])
            extra = rng.choice([
                [],
                ["ARCTIC"],
                ["BLOWING"],
            ])

    else:
        snow_type = _weighted_choice(
            rng,
            {
                "light_snow": 0.16,
                "steady_snow": 0.20,
                "heavy_snow": 0.14,
                "snow_showers": 0.12,
                "wet_snow": 0.10,
                "cold_dry_snow": 0.10,
                "low_cloud_snow": 0.08,
                "snow_and_slip": 0.06,
                "sleet_mix": 0.04,
            },
        )

        if snow_type == "light_snow":
            temp = rng.randint(-10, 0)
            dew_gap = rng.randint(1, 5)
            weather = ["LSNOW"]
            wind = _wind(
                rng,
                speed_min=0,
                speed_max=5,
                directions=COLD_WIND_DIRECTIONS,
                gust_chance=0.10,
            )
            cloud_covers = ("BKN", "OVC")
            height_chance = 0.55
            visibility = rng.choice(["V3000", "V4000", "V6000", "V8000"])
            pressure = _pressure(rng, low=998, high=1018)
            humidity = f"RH{rng.randint(75, 96)}"
            snow_depth = f"SD{rng.randint(1, 45)}"
            new_snow = f"NS{rng.randint(1, 4)}"
            extra = rng.choice([
                [],
                ["LIGHT"],
            ])

        elif snow_type == "steady_snow":
            temp = rng.randint(-12, -1)
            dew_gap = rng.randint(1, 5)
            weather = ["SNOW"]
            wind = _wind(
                rng,
                speed_min=2,
                speed_max=8,
                directions=COLD_WIND_DIRECTIONS,
                gust_chance=0.30,
            )
            cloud_covers = ("BKN", "OVC")
            height_chance = 0.65
            visibility = rng.choice(["V2000", "V3000", "V4000", "V6000"])
            pressure = _pressure(rng, low=990, high=1012)
            humidity = f"RH{rng.randint(78, 96)}"
            snow_depth = f"SD{rng.randint(3, 55)}"
            new_snow = f"NS{rng.randint(1, 8)}"
            extra = rng.choice([
                [],
                ["STEADY"],
            ])

        elif snow_type == "heavy_snow":
            temp = rng.randint(-10, -1)
            dew_gap = rng.randint(0, 4)
            weather = ["HSNOW"]
            wind = _wind(
                rng,
                speed_min=3,
                speed_max=10,
                directions=COLD_WIND_DIRECTIONS,
                gust_chance=0.55,
            )
            cloud_covers = ("OVC", "VV")
            height_chance = 0.80
            visibility = rng.choice(["V800", "V1000", "V1500", "V2000", "V3000"])
            pressure = _pressure(rng, low=986, high=1008)
            humidity = f"RH{rng.randint(84, 100)}"
            snow_depth = f"SD{rng.randint(5, 70)}"
            new_snow = f"NS{rng.randint(4, 16)}"
            extra = rng.choice([
                [],
                ["HEAVYSNOW"],
                ["LOWVIS"],
            ])

        elif snow_type == "snow_showers":
            temp = rng.randint(-8, 2)
            dew_gap = rng.randint(1, 6)
            weather = rng.choice([
                ["SHOWER", "SNOW"],
                ["SHOWER", "LSNOW"],
                ["SNOW"],
                ["LSNOW"],
            ])
            wind = _wind(
                rng,
                speed_min=2,
                speed_max=9,
                directions=WIND_DIRECTIONS,
                gust_chance=0.45,
            )
            cloud_covers = ("FEW", "SCT", "BKN")
            height_chance = 0.45
            visibility = rng.choice(["V2000", "V3000", "V5000", "V7000", "V9000"])
            pressure = _pressure(rng, low=994, high=1016)
            humidity = f"RH{rng.randint(68, 92)}"
            snow_depth = f"SD{rng.randint(1, 45)}"
            new_snow = f"NS{rng.randint(1, 6)}"
            extra = rng.choice([
                [],
                ["SHOWERY"],
                ["PASSING"],
            ])

        elif snow_type == "wet_snow":
            temp = rng.randint(-1, 2)
            dew_gap = rng.randint(0, 3)
            weather = [rng.choice(["SNOW", "HSNOW"]), rng.choice(["SLIP", "ICE"])]
            wind = _wind(
                rng,
                speed_min=1,
                speed_max=7,
                directions=WIND_DIRECTIONS,
                gust_chance=0.25,
            )
            cloud_covers = ("BKN", "OVC", "VV")
            height_chance = 0.75
            visibility = rng.choice(["V1000", "V1500", "V2000", "V3000", "V5000"])
            pressure = _pressure(rng, low=990, high=1012)
            humidity = f"RH{rng.randint(88, 100)}"
            snow_depth = f"SD{rng.randint(1, 35)}"
            new_snow = f"NS{rng.randint(1, 10)}"
            extra = rng.choice([
                [],
                ["WETSNOW"],
                ["SLUSH"],
            ])

        elif snow_type == "cold_dry_snow":
            temp = rng.randint(-24, -10)
            dew_gap = rng.randint(4, 10)
            weather = [rng.choice(["LSNOW", "SNOW"])]
            wind = _wind(
                rng,
                speed_min=0,
                speed_max=6,
                directions=COLD_WIND_DIRECTIONS,
                gust_chance=0.15,
            )
            cloud_covers = ("SCT", "BKN", "OVC")
            height_chance = 0.50
            visibility = rng.choice(["V3000", "V5000", "V7000", "V9000"])
            pressure = _pressure(rng, low=1000, high=1024)
            humidity = f"RH{rng.randint(55, 82)}"
            snow_depth = f"SD{rng.randint(5, 80)}"
            new_snow = f"NS{rng.randint(1, 6)}"
            extra = rng.choice([
                [],
                ["DRY"],
                ["POWDER"],
            ])

        elif snow_type == "low_cloud_snow":
            temp = rng.randint(-8, 1)
            dew_gap = rng.randint(0, 3)
            weather = [rng.choice(["SNOW", "LSNOW"]), rng.choice(["MIST", "LFOG"])]
            wind = _wind(
                rng,
                speed_min=0,
                speed_max=5,
                directions=COLD_WIND_DIRECTIONS,
                gust_chance=0.10,
            )
            cloud_covers = ("OVC", "VV")
            height_chance = 0.90
            visibility = rng.choice(["V500", "V800", "V1000", "V1500", "V2000"])
            pressure = _pressure(rng, low=995, high=1016)
            humidity = f"RH{rng.randint(90, 100)}"
            snow_depth = f"SD{rng.randint(3, 50)}"
            new_snow = f"NS{rng.randint(1, 8)}"
            extra = rng.choice([
                [],
                ["LOWCLOUD"],
                ["DAMP"],
            ])

        elif snow_type == "snow_and_slip":
            temp = rng.randint(-4, 1)
            dew_gap = rng.randint(0, 3)
            weather = [rng.choice(["SNOW", "LSNOW"]), "SLIP"]
            wind = _wind(
                rng,
                speed_min=1,
                speed_max=7,
                directions=WIND_DIRECTIONS,
                gust_chance=0.20,
            )
            cloud_covers = ("BKN", "OVC")
            height_chance = 0.65
            visibility = rng.choice(["V1500", "V2000", "V3000", "V5000"])
            pressure = _pressure(rng, low=992, high=1014)
            humidity = f"RH{rng.randint(82, 100)}"
            snow_depth = f"SD{rng.randint(1, 40)}"
            new_snow = f"NS{rng.randint(1, 8)}"
            extra = rng.choice([
                [],
                ["ROADICE"],
                ["SLIPPERY"],
            ])

        else:  # sleet_mix
            temp = rng.randint(-1, 3)
            dew_gap = rng.randint(0, 3)
            weather = [rng.choice(["SLEET", "LSLEET"]), rng.choice(["SLIP", "ICE"])]
            wind = _wind(
                rng,
                speed_min=2,
                speed_max=8,
                directions=WIND_DIRECTIONS,
                gust_chance=0.25,
            )
            cloud_covers = ("BKN", "OVC", "VV")
            height_chance = 0.75
            visibility = rng.choice(["V1500", "V2000", "V3000", "V5000", "V7000"])
            pressure = _pressure(rng, low=990, high=1012)
            humidity = f"RH{rng.randint(85, 100)}"
            snow_depth = rng.choice([
                f"SD{rng.randint(1, 25)}",
                None,
            ])
            new_snow = rng.choice([
                f"NS{rng.randint(1, 4)}",
                None,
            ])
            extra = rng.choice([
                [],
                ["SLEETY"],
                ["SLUSH"],
            ])

    fields.update(
        temperature=_signed("T", temp),
        dew_point=_signed("D", temp - dew_gap),
        weather=weather,
        wind=wind,
        cloud=_clouds(rng, covers=cloud_covers, height_chance=height_chance),
        visibility=visibility,
        pressure=pressure,
        uv_index="UV0",
        humidity=humidity,
        rain_amount=None,
        snow_depth=snow_depth,
        new_snow=new_snow,
        extra=extra,
    )

    return fields


def _scenario_fog(rng: Random, fields: dict[str, Any]) -> dict[str, Any]:
    fog_type = _weighted_choice(
        rng,
        {
            "light_mist": 0.16,
            "ordinary_fog": 0.20,
            "dense_fog": 0.14,
            "freezing_fog": 0.12,
            "sea_fog": 0.10,
            "valley_fog": 0.08,
            "low_stratus_fog": 0.10,
            "hazy_morning": 0.06,
            "calm_night_fog": 0.04,
        },
    )

    extra: list[str] = []

    if fog_type == "light_mist":
        temp = rng.randint(1, 10)
        dew_gap = rng.randint(0, 2)
        weather = [rng.choice(["MIST", "LMIST", "LFOG"])]
        wind = rng.choice(["CALM", "N1", "E1", "S1", "W1", "VRB1", "VRB2"])
        cloud_covers = ("BKN", "OVC")
        height_chance = 0.55
        visibility = rng.choice(["V1000", "V1500", "V2000", "V3000", "V5000"])
        pressure = _pressure(rng, low=1006, high=1024)
        humidity = f"RH{rng.randint(88, 100)}"
        uv_index = f"UV{rng.randint(0, 1)}"
        extra = rng.choice([
            [],
            ["MISTY"],
            ["DAMP"],
        ])

    elif fog_type == "ordinary_fog":
        temp = rng.randint(-2, 8)
        dew_gap = rng.randint(0, 1)
        weather = [rng.choice(["FOG", "LFOG"])]
        wind = rng.choice(["CALM", "N1", "E1", "S1", "W1", "VRB1"])
        cloud_covers = ("BKN", "OVC", "VV")
        height_chance = 0.70
        visibility = rng.choice(["V300", "V500", "V800", "V1000"])
        pressure = _pressure(rng, low=1002, high=1024)
        humidity = f"RH{rng.randint(92, 100)}"
        uv_index = "UV0"
        extra = rng.choice([
            [],
            ["LOWVIS"],
            ["DAMP"],
        ])

    elif fog_type == "dense_fog":
        temp = rng.randint(-2, 7)
        dew_gap = rng.randint(0, 1)
        weather = [rng.choice(["FOG", "HFOG"])]
        wind = rng.choice(["CALM", "CALM", "N1", "E1", "S1", "W1", "VRB1"])
        cloud_covers = ("OVC", "VV")
        height_chance = 0.85
        visibility = rng.choice(["V100", "V200", "V300", "V500"])
        pressure = _pressure(rng, low=1000, high=1022)
        humidity = f"RH{rng.randint(96, 100)}"
        uv_index = "UV0"
        extra = rng.choice([
            ["DENSEFOG"],
            ["LOWVIS"],
            ["SLOW"],
        ])

    elif fog_type == "freezing_fog":
        temp = rng.randint(-8, 0)
        dew_gap = rng.randint(0, 2)
        weather = [rng.choice(["FOG", "HFOG"]), rng.choice(["FROST", "ICE"])]
        wind = rng.choice(["CALM", "N1", "NE1", "E1", "VRB1", "VRB2"])
        cloud_covers = ("OVC", "VV")
        height_chance = 0.80
        visibility = rng.choice(["V100", "V200", "V300", "V500", "V800"])
        pressure = _pressure(rng, low=1004, high=1030)
        humidity = f"RH{rng.randint(92, 100)}"
        uv_index = "UV0"
        extra = rng.choice([
            ["FREEZFOG"],
            ["RIME"],
            ["ROADICE"],
            ["FROST"],
        ])

    elif fog_type == "sea_fog":
        temp = rng.randint(1, 9)
        dew_gap = rng.randint(0, 2)
        weather = [rng.choice(["FOG", "MIST", "LFOG"])]
        wind = rng.choice(["S1", "SE1", "SW1", "W1", "S2", "SW2", "VRB1", "VRB2"])
        cloud_covers = ("BKN", "OVC", "VV")
        height_chance = 0.75
        visibility = rng.choice(["V200", "V300", "V500", "V800", "V1000", "V1500"])
        pressure = _pressure(rng, low=1002, high=1022)
        humidity = f"RH{rng.randint(92, 100)}"
        uv_index = f"UV{rng.randint(0, 1)}"
        extra = rng.choice([
            ["SEAFOG"],
            ["COASTAL"],
            ["DAMP"],
        ])

    elif fog_type == "valley_fog":
        temp = rng.randint(-4, 7)
        dew_gap = rng.randint(0, 2)
        weather = [rng.choice(["FOG", "MIST", "LFOG"])]
        wind = rng.choice(["CALM", "CALM", "N1", "E1", "S1", "W1"])
        cloud_covers = ("SKC", "FEW", "BKN", "OVC")
        height_chance = 0.35
        visibility = rng.choice(["V300", "V500", "V800", "V1000", "V1500"])
        pressure = _pressure(rng, low=1008, high=1030)
        humidity = f"RH{rng.randint(90, 100)}"
        uv_index = "UV0"
        extra = rng.choice([
            ["VALLEYFOG"],
            ["LOWFOG"],
            ["MORNING"],
        ])

    elif fog_type == "low_stratus_fog":
        temp = rng.randint(-1, 9)
        dew_gap = rng.randint(0, 2)
        weather = [rng.choice(["MIST", "LFOG", "FOG"])]
        wind = rng.choice(["CALM", "N1", "E1", "S1", "W1", "VRB1", "VRB2", "VRB3"])
        cloud_covers = ("OVC", "VV")
        height_chance = 0.95
        visibility = rng.choice(["V500", "V800", "V1000", "V1500", "V2000"])
        pressure = _pressure(rng, low=1004, high=1024)
        humidity = f"RH{rng.randint(90, 100)}"
        uv_index = "UV0"
        extra = rng.choice([
            ["LOWCLOUD"],
            ["STRATUS"],
            ["GREY"],
        ])

    elif fog_type == "hazy_morning":
        temp = rng.randint(4, 13)
        dew_gap = rng.randint(2, 5)
        weather = [rng.choice(["HAZE", "LHAZE", "MIST"])]
        wind = rng.choice(["CALM", "N1", "E1", "S1", "W1", "VRB1", "VRB2"])
        cloud_covers = ("SKC", "FEW", "SCT", "BKN")
        height_chance = 0.35
        visibility = rng.choice(["V3000", "V5000", "V7000", "V8000", "V9000"])
        pressure = _pressure(rng, low=1008, high=1028)
        humidity = f"RH{rng.randint(70, 92)}"
        uv_index = f"UV{rng.randint(0, 2)}"
        extra = rng.choice([
            [],
            ["HAZY"],
            ["MORNING"],
        ])

    else:  # calm_night_fog
        temp = rng.randint(-3, 6)
        dew_gap = rng.randint(0, 1)
        weather = [rng.choice(["FOG", "LFOG", "MIST"])]
        wind = "CALM"
        cloud_covers = ("SKC", "FEW", "BKN", "OVC", "VV")
        height_chance = 0.55
        visibility = rng.choice(["V200", "V300", "V500", "V800", "V1000"])
        pressure = _pressure(rng, low=1008, high=1030)
        humidity = f"RH{rng.randint(94, 100)}"
        uv_index = "UV0"
        extra = rng.choice([
            ["NIGHT"],
            ["CALM"],
            ["LOWVIS"],
        ])

    fields.update(
        temperature=_signed("T", temp),
        dew_point=_signed("D", temp - dew_gap),
        weather=weather,
        wind=wind,
        cloud=_clouds(rng, covers=cloud_covers, height_chance=height_chance),
        visibility=visibility,
        pressure=pressure,
        uv_index=uv_index,
        humidity=humidity,
        rain_amount=None,
        snow_depth=None,
        new_snow=None,
        extra=extra,
    )

    return fields


def _scenario_ice_slip(rng: Random, fields: dict[str, Any]) -> dict[str, Any]:
    ice_type = _weighted_choice(
        rng,
        {
            "black_ice": 0.18,
            "freezing_drizzle": 0.16,
            "refreeze_evening": 0.14,
            "zero_degree_slip": 0.14,
            "frost_slip": 0.12,
            "freezing_fog_ice": 0.10,
            "sleet_slip": 0.10,
            "coastal_ice": 0.06,
        },
    )

    extra: list[str] = []

    if ice_type == "black_ice":
        temp = rng.randint(-5, 0)
        dew_gap = rng.randint(0, 4)
        weather = ["ICE", "SLIP"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=4,
            directions=WIND_DIRECTIONS,
            gust_chance=0.05,
        )
        cloud_covers = ("SKC", "FEW", "SCT", "BKN")
        height_chance = 0.25
        visibility = rng.choice(["VOK", "V7000", "V8000", "V9000"])
        pressure = _pressure(rng, low=1004, high=1028)
        humidity = f"RH{rng.randint(70, 95)}"
        rain_amount = None
        snow_depth = rng.choice([
            None,
            f"SD{rng.randint(1, 20)}",
        ])
        extra = rng.choice([
            ["BLACKICE"],
            ["ROADICE"],
            ["GLAZE"],
        ])

    elif ice_type == "freezing_drizzle":
        temp = rng.randint(-4, 0)
        dew_gap = rng.randint(0, 2)
        weather = [rng.choice(["DRIZZLE", "LDRIZZLE"]), "ICE", "SLIP"]
        wind = _wind(
            rng,
            speed_min=1,
            speed_max=6,
            directions=WIND_DIRECTIONS,
            gust_chance=0.10,
        )
        cloud_covers = ("BKN", "OVC", "VV")
        height_chance = 0.80
        visibility = rng.choice(["V1500", "V2000", "V3000", "V5000", "V6000"])
        pressure = _pressure(rng, low=994, high=1014)
        humidity = f"RH{rng.randint(88, 100)}"
        rain_amount = f"RR{rng.randint(1, 3)}"
        snow_depth = rng.choice([
            None,
            f"SD{rng.randint(1, 15)}",
        ])
        extra = rng.choice([
            ["FREEZDRZ"],
            ["ROADICE"],
            ["DAMP"],
        ])

    elif ice_type == "refreeze_evening":
        temp = rng.randint(-6, -1)
        dew_gap = rng.randint(1, 5)
        weather = ["ICE", "SLIP"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=5,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.05,
        )
        cloud_covers = ("FEW", "SCT", "BKN")
        height_chance = 0.35
        visibility = rng.choice(["VOK", "V6000", "V8000", "V9000"])
        pressure = _pressure(rng, low=1000, high=1024)
        humidity = f"RH{rng.randint(70, 96)}"
        rain_amount = None
        snow_depth = rng.choice([
            None,
            f"SD{rng.randint(1, 25)}",
        ])
        extra = rng.choice([
            ["REFREEZE"],
            ["EVENING"],
            ["ROADICE"],
        ])

    elif ice_type == "zero_degree_slip":
        temp = rng.randint(-1, 1)
        dew_gap = rng.randint(0, 3)
        weather = ["ICE", "SLIP"]
        wind = _wind(
            rng,
            speed_min=1,
            speed_max=6,
            directions=WIND_DIRECTIONS,
            gust_chance=0.15,
        )
        cloud_covers = ("BKN", "OVC")
        height_chance = 0.55
        visibility = rng.choice(["V4000", "V5000", "V6000", "V8000"])
        pressure = _pressure(rng, low=995, high=1016)
        humidity = f"RH{rng.randint(78, 98)}"
        rain_amount = None
        snow_depth = rng.choice([
            None,
            f"SD{rng.randint(1, 20)}",
        ])
        extra = rng.choice([
            [],
            ["ZEROC"],
            ["SLIPPERY"],
        ])

    elif ice_type == "frost_slip":
        temp = rng.randint(-8, -1)
        dew_gap = rng.randint(0, 4)
        weather = ["FROST", "ICE", "SLIP"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=3,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud_covers = ("SKC", "FEW", "SCT")
        height_chance = 0.20
        visibility = rng.choice(["VOK", "V7000", "V9000"])
        pressure = _pressure(rng, low=1010, high=1034)
        humidity = f"RH{rng.randint(65, 95)}"
        rain_amount = None
        snow_depth = rng.choice([
            None,
            f"SD{rng.randint(1, 30)}",
        ])
        extra = rng.choice([
            ["FROST"],
            ["MORNING"],
            ["ROADICE"],
        ])

    elif ice_type == "freezing_fog_ice":
        temp = rng.randint(-7, 0)
        dew_gap = rng.randint(0, 2)
        weather = [rng.choice(["FOG", "LFOG", "MIST"]), "ICE", "SLIP"]
        wind = rng.choice(["CALM", "N1", "NE1", "E1", "VRB1", "VRB2"])
        cloud_covers = ("OVC", "VV")
        height_chance = 0.85
        visibility = rng.choice(["V200", "V300", "V500", "V800", "V1000"])
        pressure = _pressure(rng, low=1002, high=1026)
        humidity = f"RH{rng.randint(92, 100)}"
        rain_amount = None
        snow_depth = rng.choice([
            None,
            f"SD{rng.randint(1, 35)}",
        ])
        extra = rng.choice([
            ["FREEZFOG"],
            ["RIME"],
            ["LOWVIS"],
        ])

    elif ice_type == "sleet_slip":
        temp = rng.randint(-2, 2)
        dew_gap = rng.randint(0, 3)
        weather = [rng.choice(["SLEET", "LSLEET"]), "ICE", "SLIP"]
        wind = _wind(
            rng,
            speed_min=2,
            speed_max=8,
            directions=WIND_DIRECTIONS,
            gust_chance=0.25,
        )
        cloud_covers = ("BKN", "OVC", "VV")
        height_chance = 0.70
        visibility = rng.choice(["V1500", "V2000", "V3000", "V5000", "V7000"])
        pressure = _pressure(rng, low=990, high=1012)
        humidity = f"RH{rng.randint(85, 100)}"
        rain_amount = f"RR{rng.randint(1, 4)}"
        snow_depth = rng.choice([
            None,
            f"SD{rng.randint(1, 25)}",
        ])
        extra = rng.choice([
            ["SLEETY"],
            ["SLUSH"],
            ["ROADICE"],
        ])

    else:  # coastal_ice
        temp = rng.randint(-3, 1)
        dew_gap = rng.randint(0, 3)
        weather = ["ICE", "SLIP"]
        wind = _wind(
            rng,
            speed_min=3,
            speed_max=9,
            directions=("N", "NE", "E", "SE", "W", "NW"),
            gust_chance=0.25,
        )
        cloud_covers = ("BKN", "OVC")
        height_chance = 0.55
        visibility = rng.choice(["V3000", "V5000", "V7000", "V9000"])
        pressure = _pressure(rng, low=994, high=1018)
        humidity = f"RH{rng.randint(78, 98)}"
        rain_amount = None
        snow_depth = rng.choice([
            None,
            f"SD{rng.randint(1, 25)}",
        ])
        extra = rng.choice([
            ["COASTAL"],
            ["SEAICE"],
            ["ROADICE"],
        ])

    fields.update(
        temperature=_signed("T", temp),
        dew_point=_signed("D", temp - dew_gap),
        weather=weather,
        wind=wind,
        cloud=_clouds(rng, covers=cloud_covers, height_chance=height_chance),
        visibility=visibility,
        pressure=pressure,
        uv_index="UV0",
        humidity=humidity,
        rain_amount=rain_amount,
        snow_depth=snow_depth,
        new_snow=None,
        extra=extra,
    )

    return fields


def _scenario_windy(rng: Random, fields: dict[str, Any]) -> dict[str, Any]:
    windy_type = _weighted_choice(
        rng,
        {
            "breezy_clear": 0.14,
            "gusty_partly_cloudy": 0.18,
            "coastal_windy": 0.14,
            "cold_north_wind": 0.12,
            "dry_windy": 0.10,
            "grey_windy": 0.12,
            "light_gale": 0.10,
            "lake_wind": 0.06,
            "evening_wind": 0.04,
        },
    )

    extra: list[str] = []

    if windy_type == "breezy_clear":
        temp = rng.randint(6, 16)
        dew_gap = rng.randint(4, 9)
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=6,
            speed_max=10,
            directions=WIND_DIRECTIONS,
            gust_chance=0.45,
        )
        cloud_covers = ("SKC", "FEW", "SCT")
        height_chance = 0.30
        visibility = rng.choice(["VOK", "V9000"])
        pressure = _pressure(rng, low=1004, high=1022)
        uv_index = f"UV{rng.randint(1, 4)}"
        humidity = f"RH{rng.randint(45, 72)}"
        extra = rng.choice([
            [],
            ["BREEZY"],
            ["CLEARWIND"],
        ])

    elif windy_type == "gusty_partly_cloudy":
        temp = rng.randint(4, 15)
        dew_gap = rng.randint(3, 8)
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=7,
            speed_max=13,
            directions=WIND_DIRECTIONS,
            gust_chance=0.85,
        )
        cloud_covers = ("FEW", "SCT", "BKN")
        height_chance = 0.45
        visibility = rng.choice(["VOK", "V8000", "V9000"])
        pressure = _pressure(rng, low=996, high=1018)
        uv_index = f"UV{rng.randint(0, 3)}"
        humidity = f"RH{rng.randint(50, 82)}"
        extra = rng.choice([
            [],
            ["GUSTY"],
            ["OPENAREA"],
        ])

    elif windy_type == "coastal_windy":
        temp = rng.randint(5, 14)
        dew_gap = rng.randint(2, 7)
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=7,
            speed_max=14,
            directions=("S", "SE", "SW", "W", "NW"),
            gust_chance=0.80,
        )
        cloud_covers = ("SCT", "BKN", "OVC")
        height_chance = 0.50
        visibility = rng.choice(["VOK", "V8000", "V9000"])
        pressure = _pressure(rng, low=996, high=1016)
        uv_index = f"UV{rng.randint(0, 3)}"
        humidity = f"RH{rng.randint(60, 88)}"
        extra = rng.choice([
            ["COASTAL"],
            ["SEAWIND"],
            ["SHOREWIND"],
        ])

    elif windy_type == "cold_north_wind":
        temp = rng.randint(-4, 7)
        dew_gap = rng.randint(3, 9)
        weather = rng.choice([
            ["NIL"],
            ["COLD"],
        ])
        wind = _wind(
            rng,
            speed_min=6,
            speed_max=13,
            directions=("N", "NE", "NW", "W"),
            gust_chance=0.75,
        )
        cloud_covers = ("FEW", "SCT", "BKN")
        height_chance = 0.40
        visibility = rng.choice(["VOK", "V7000", "V9000"])
        pressure = _pressure(rng, low=1000, high=1024)
        uv_index = f"UV{rng.randint(0, 2)}"
        humidity = f"RH{rng.randint(45, 78)}"
        extra = rng.choice([
            [],
            ["COLDWIND"],
            ["NORTHWIND"],
        ])

    elif windy_type == "dry_windy":
        temp = rng.randint(7, 18)
        dew_gap = rng.randint(7, 14)
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=6,
            speed_max=12,
            directions=WIND_DIRECTIONS,
            gust_chance=0.65,
        )
        cloud_covers = ("SKC", "FEW", "SCT")
        height_chance = 0.25
        visibility = "VOK"
        pressure = _pressure(rng, low=1006, high=1026)
        uv_index = f"UV{rng.randint(1, 5)}"
        humidity = f"RH{rng.randint(25, 55)}"
        extra = rng.choice([
            [],
            ["DRY"],
            ["DUSTY"],
            ["OPENAREA"],
        ])

    elif windy_type == "grey_windy":
        temp = rng.randint(3, 13)
        dew_gap = rng.randint(2, 7)
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=7,
            speed_max=13,
            directions=WIND_DIRECTIONS,
            gust_chance=0.70,
        )
        cloud_covers = ("BKN", "OVC")
        height_chance = 0.60
        visibility = rng.choice(["V7000", "V8000", "V9000", "VOK"])
        pressure = _pressure(rng, low=992, high=1012)
        uv_index = f"UV{rng.randint(0, 2)}"
        humidity = f"RH{rng.randint(65, 88)}"
        extra = rng.choice([
            [],
            ["GREY"],
            ["LOWCLOUD"],
        ])

    elif windy_type == "light_gale":
        temp = rng.randint(2, 14)
        dew_gap = rng.randint(3, 8)
        weather = ["LGALE"]
        wind = _wind(
            rng,
            speed_min=10,
            speed_max=15,
            directions=WIND_DIRECTIONS,
            gust_chance=0.90,
        )
        cloud_covers = ("SCT", "BKN", "OVC")
        height_chance = 0.55
        visibility = rng.choice(["VOK", "V8000", "V9000"])
        pressure = _pressure(rng, low=990, high=1010)
        uv_index = f"UV{rng.randint(0, 2)}"
        humidity = f"RH{rng.randint(58, 86)}"
        extra = rng.choice([
            [],
            ["GUSTY"],
            ["WINDY"],
        ])

    elif windy_type == "lake_wind":
        temp = rng.randint(4, 15)
        dew_gap = rng.randint(3, 8)
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=6,
            speed_max=12,
            directions=("N", "NE", "E", "SE", "S", "SW", "W", "NW"),
            gust_chance=0.65,
        )
        cloud_covers = ("FEW", "SCT", "BKN")
        height_chance = 0.40
        visibility = rng.choice(["VOK", "V8000", "V9000"])
        pressure = _pressure(rng, low=998, high=1018)
        uv_index = f"UV{rng.randint(0, 3)}"
        humidity = f"RH{rng.randint(50, 82)}"
        extra = rng.choice([
            ["LAKEWIND"],
            ["OPENWATER"],
            ["SHORE"],
        ])

    else:  # evening_wind
        temp = rng.randint(2, 12)
        dew_gap = rng.randint(3, 8)
        weather = ["NIL"]
        wind = _wind(
            rng,
            speed_min=5,
            speed_max=10,
            directions=WIND_DIRECTIONS,
            gust_chance=0.45,
        )
        cloud_covers = ("FEW", "SCT", "BKN")
        height_chance = 0.35
        visibility = rng.choice(["VOK", "V8000", "V9000"])
        pressure = _pressure(rng, low=1000, high=1020)
        uv_index = f"UV{rng.randint(0, 1)}"
        humidity = f"RH{rng.randint(55, 85)}"
        extra = rng.choice([
            [],
            ["EVENING"],
            ["BREEZY"],
        ])

    fields.update(
        temperature=_signed("T", temp),
        dew_point=_signed("D", temp - dew_gap),
        weather=weather,
        wind=wind,
        cloud=_clouds(rng, covers=cloud_covers, height_chance=height_chance),
        visibility=visibility,
        pressure=pressure,
        uv_index=uv_index,
        humidity=humidity,
        rain_amount=None,
        snow_depth=None,
        new_snow=None,
        extra=extra,
    )

    return fields


def _scenario_storm(rng: Random, fields: dict[str, Any]) -> dict[str, Any]:
    storm_type = _weighted_choice(
        rng,
        {
            "classic_low_pressure_storm": 0.18,
            "heavy_rain_storm": 0.16,
            "thunderstorm": 0.16,
            "hail_thunderstorm": 0.08,
            "coastal_storm": 0.14,
            "dry_windstorm": 0.08,
            "cold_autumn_storm": 0.10,
            "severe_storm": 0.06,
            "squall_line": 0.04,
        },
    )

    extra: list[str] = []

    if storm_type == "classic_low_pressure_storm":
        temp = rng.randint(4, 14)
        dew_gap = rng.randint(1, 5)
        weather = [rng.choice(["STORM", "STORM", "HSTORM"])]
        wind = _wind(
            rng,
            speed_min=14,
            speed_max=24,
            directions=WIND_DIRECTIONS,
            gust_chance=1.00,
        )
        cloud_covers = ("BKN", "OVC")
        height_chance = 0.75
        visibility = rng.choice(["V3000", "V5000", "V7000", "V8000"])
        pressure = _pressure(rng, low=975, high=1000)
        uv_index = f"UV{rng.randint(0, 1)}"
        humidity = f"RH{rng.randint(70, 95)}"
        rain_amount = f"RR{rng.randint(1, 12)}"
        extra = rng.choice([
            [],
            ["LOWPRESS"],
            ["WINDDAMAGE"],
        ])

    elif storm_type == "heavy_rain_storm":
        temp = rng.randint(5, 16)
        dew_gap = rng.randint(0, 4)
        weather = [rng.choice(["STORM", "HSTORM"]), rng.choice(["RAIN", "HRAIN"])]
        wind = _wind(
            rng,
            speed_min=14,
            speed_max=25,
            directions=WIND_DIRECTIONS,
            gust_chance=1.00,
        )
        cloud_covers = ("OVC", "VV")
        height_chance = 0.85
        visibility = rng.choice(["V1000", "V1500", "V2000", "V3000", "V5000"])
        pressure = _pressure(rng, low=970, high=995)
        uv_index = "UV0"
        humidity = f"RH{rng.randint(85, 100)}"
        rain_amount = f"RR{rng.randint(8, 30)}"
        extra = rng.choice([
            ["HEAVYRAIN"],
            ["FLOODRISK"],
            ["LOWVIS"],
        ])

    elif storm_type == "thunderstorm":
        temp = rng.randint(12, 26)
        dew_gap = rng.randint(0, 5)
        weather = ["THUNDER", rng.choice(["STORM", "HSTORM"]), rng.choice(["RAIN", "HRAIN", "SHOWER"])]
        wind = _wind(
            rng,
            speed_min=10,
            speed_max=22,
            directions=WIND_DIRECTIONS,
            gust_chance=1.00,
        )
        cloud_covers = ("BKN", "OVC")
        height_chance = 0.70
        visibility = rng.choice(["V1500", "V2000", "V3000", "V5000", "V8000"])
        pressure = _pressure(rng, low=980, high=1006)
        uv_index = f"UV{rng.randint(0, 3)}"
        humidity = f"RH{rng.randint(75, 98)}"
        rain_amount = f"RR{rng.randint(5, 25)}"
        extra = rng.choice([
            ["THUNDERSTORM"],
            ["LIGHTNING"],
            ["CB"],
            ["FLASHES"],
        ])

    elif storm_type == "hail_thunderstorm":
        temp = rng.randint(10, 24)
        dew_gap = rng.randint(1, 6)
        weather = ["THUNDER", rng.choice(["STORM", "HSTORM"]), rng.choice(["HAIL", "HHAIL"])]
        wind = _wind(
            rng,
            speed_min=11,
            speed_max=23,
            directions=WIND_DIRECTIONS,
            gust_chance=1.00,
        )
        cloud_covers = ("BKN", "OVC")
        height_chance = 0.70
        visibility = rng.choice(["V1000", "V1500", "V2000", "V3000", "V5000"])
        pressure = _pressure(rng, low=978, high=1004)
        uv_index = f"UV{rng.randint(0, 2)}"
        humidity = f"RH{rng.randint(70, 96)}"
        rain_amount = f"RR{rng.randint(3, 20)}"
        extra = rng.choice([
            ["HAILCORE"],
            ["CB"],
            ["DAMAGE"],
        ])

    elif storm_type == "coastal_storm":
        temp = rng.randint(3, 13)
        dew_gap = rng.randint(1, 5)
        weather = [rng.choice(["STORM", "HSTORM"]), rng.choice(["RAIN", "HRAIN"])]
        wind = _wind(
            rng,
            speed_min=16,
            speed_max=28,
            directions=("S", "SE", "SW", "W", "NW"),
            gust_chance=1.00,
        )
        cloud_covers = ("BKN", "OVC", "VV")
        height_chance = 0.80
        visibility = rng.choice(["V1500", "V2000", "V3000", "V5000", "V7000"])
        pressure = _pressure(rng, low=965, high=995)
        uv_index = "UV0"
        humidity = f"RH{rng.randint(78, 98)}"
        rain_amount = f"RR{rng.randint(3, 18)}"
        extra = rng.choice([
            ["COASTAL"],
            ["SEASTORM"],
            ["HIGHSEA"],
            ["WAVES"],
        ])

    elif storm_type == "dry_windstorm":
        temp = rng.randint(8, 22)
        dew_gap = rng.randint(6, 14)
        weather = [rng.choice(["STORM", "HSTORM"])]
        wind = _wind(
            rng,
            speed_min=14,
            speed_max=25,
            directions=WIND_DIRECTIONS,
            gust_chance=1.00,
        )
        cloud_covers = ("FEW", "SCT", "BKN")
        height_chance = 0.45
        visibility = rng.choice(["VOK", "V7000", "V8000", "V9000"])
        pressure = _pressure(rng, low=985, high=1010)
        uv_index = f"UV{rng.randint(1, 4)}"
        humidity = f"RH{rng.randint(30, 65)}"
        rain_amount = None
        extra = rng.choice([
            ["DRYSTORM"],
            ["DUST"],
            ["TREEFALL"],
        ])

    elif storm_type == "cold_autumn_storm":
        temp = rng.randint(0, 8)
        dew_gap = rng.randint(1, 5)
        weather = [rng.choice(["STORM", "HSTORM"]), rng.choice(["RAIN", "SLEET", "SHOWER"])]
        wind = _wind(
            rng,
            speed_min=13,
            speed_max=24,
            directions=("N", "NE", "NW", "W", "SW"),
            gust_chance=1.00,
        )
        cloud_covers = ("BKN", "OVC", "VV")
        height_chance = 0.80
        visibility = rng.choice(["V1500", "V2000", "V3000", "V5000", "V7000"])
        pressure = _pressure(rng, low=970, high=1000)
        uv_index = "UV0"
        humidity = f"RH{rng.randint(78, 98)}"
        rain_amount = f"RR{rng.randint(2, 14)}"
        extra = rng.choice([
            ["RAW"],
            ["COLDSTORM"],
            ["AUTUMN"],
        ])

    elif storm_type == "severe_storm":
        temp = rng.randint(4, 18)
        dew_gap = rng.randint(0, 5)
        weather = ["HSTORM"]
        wind = _wind(
            rng,
            speed_min=20,
            speed_max=32,
            directions=WIND_DIRECTIONS,
            gust_chance=1.00,
        )
        cloud_covers = ("OVC", "VV")
        height_chance = 0.90
        visibility = rng.choice(["V800", "V1000", "V1500", "V2000", "V3000"])
        pressure = _pressure(rng, low=955, high=985)
        uv_index = "UV0"
        humidity = f"RH{rng.randint(80, 100)}"
        rain_amount = rng.choice([
            f"RR{rng.randint(5, 25)}",
            None,
        ])
        extra = rng.choice([
            ["SEVERE"],
            ["DAMAGE"],
            ["POWEROUT"],
            ["TREEFALL"],
        ])

    else:  # squall_line
        temp = rng.randint(8, 22)
        dew_gap = rng.randint(1, 6)
        weather = [rng.choice(["STORM", "HSTORM"]), rng.choice(["SHOWER", "HSHOWER", "RAIN"])]
        wind = _wind(
            rng,
            speed_min=13,
            speed_max=26,
            directions=WIND_DIRECTIONS,
            gust_chance=1.00,
        )
        cloud_covers = ("SCT", "BKN", "OVC")
        height_chance = 0.65
        visibility = rng.choice(["V1000", "V1500", "V2000", "V3000", "V5000"])
        pressure = _pressure(rng, low=975, high=1005)
        uv_index = f"UV{rng.randint(0, 2)}"
        humidity = f"RH{rng.randint(70, 96)}"
        rain_amount = f"RR{rng.randint(3, 18)}"
        extra = rng.choice([
            ["SQUALL"],
            ["GUSTFRONT"],
            ["FASTMOVE"],
        ])

    fields.update(
        temperature=_signed("T", temp),
        dew_point=_signed("D", temp - dew_gap),
        weather=weather,
        wind=wind,
        cloud=_clouds(rng, covers=cloud_covers, height_chance=height_chance),
        visibility=visibility,
        pressure=pressure,
        uv_index=uv_index,
        humidity=humidity,
        rain_amount=rain_amount,
        snow_depth=None,
        new_snow=None,
        extra=extra,
    )

    return fields


def _scenario_cold(rng: Random, fields: dict[str, Any]) -> dict[str, Any]:
    cold_type = _weighted_choice(
        rng,
        {
            "dry_high_pressure_cold": 0.18,
            "calm_radiation_frost": 0.16,
            "arctic_air": 0.14,
            "wind_chill_cold": 0.14,
            "frosty_cold": 0.12,
            "ice_fog_cold": 0.10,
            "cloudy_cold": 0.10,
            "extreme_cold": 0.06,
        },
    )

    extra: list[str] = []

    if cold_type == "dry_high_pressure_cold":
        temp = rng.randint(-28, -14)
        dew_gap = rng.randint(7, 16)
        weather = ["COLD"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=4,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud_covers = ("SKC", "FEW", "SCT")
        height_chance = 0.18
        visibility = rng.choice(["VOK", "V9000"])
        pressure = _pressure(rng, low=1024, high=1044)
        humidity = f"RH{rng.randint(35, 65)}"
        snow_depth = f"SD{rng.randint(10, 85)}"
        extra = rng.choice([
            [],
            ["DRYCOLD"],
            ["HIGHPRESSURE"],
            ["ARCTIC"],
        ])

    elif cold_type == "calm_radiation_frost":
        temp = rng.randint(-30, -16)
        dew_gap = rng.randint(3, 10)
        weather = ["COLD", "FROST"]
        wind = rng.choice(["CALM", "CALM", "N1", "NE1", "VRB1"])
        cloud_covers = ("SKC", "SKC", "FEW")
        height_chance = 0.12
        visibility = rng.choice(["VOK", "V7000", "V9000"])
        pressure = _pressure(rng, low=1020, high=1042)
        humidity = f"RH{rng.randint(55, 85)}"
        snow_depth = f"SD{rng.randint(10, 90)}"
        extra = rng.choice([
            ["RADIATION"],
            ["FROST"],
            ["STILL"],
            ["NIGHTCOLD"],
        ])

    elif cold_type == "arctic_air":
        temp = rng.randint(-34, -18)
        dew_gap = rng.randint(5, 14)
        weather = ["COLD"]
        wind = _wind(
            rng,
            speed_min=1,
            speed_max=6,
            directions=("N", "NE", "NW"),
            gust_chance=0.10,
        )
        cloud_covers = ("SKC", "FEW", "SCT", "BKN")
        height_chance = 0.25
        visibility = rng.choice(["VOK", "V7000", "V9000"])
        pressure = _pressure(rng, low=1018, high=1040)
        humidity = f"RH{rng.randint(45, 78)}"
        snow_depth = f"SD{rng.randint(15, 100)}"
        extra = rng.choice([
            ["ARCTIC"],
            ["LOWTEMP"],
            ["DRY"],
        ])

    elif cold_type == "wind_chill_cold":
        temp = rng.randint(-24, -10)
        dew_gap = rng.randint(4, 12)
        weather = ["COLD"]
        wind = _wind(
            rng,
            speed_min=5,
            speed_max=12,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.55,
        )
        cloud_covers = ("FEW", "SCT", "BKN")
        height_chance = 0.35
        visibility = rng.choice(["VOK", "V7000", "V9000"])
        pressure = _pressure(rng, low=1008, high=1032)
        humidity = f"RH{rng.randint(45, 78)}"
        snow_depth = f"SD{rng.randint(10, 90)}"
        extra = rng.choice([
            ["WINDCHILL"],
            ["COLDWIND"],
            ["BITING"],
        ])

    elif cold_type == "frosty_cold":
        temp = rng.randint(-22, -8)
        dew_gap = rng.randint(1, 6)
        weather = ["COLD", "FROST"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=4,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud_covers = ("SKC", "FEW", "SCT", "BKN")
        height_chance = 0.25
        visibility = rng.choice(["VOK", "V7000", "V9000"])
        pressure = _pressure(rng, low=1014, high=1036)
        humidity = f"RH{rng.randint(65, 92)}"
        snow_depth = f"SD{rng.randint(5, 80)}"
        extra = rng.choice([
            [],
            ["RIME"],
            ["FROST"],
            ["DRYFROST"],
        ])

    elif cold_type == "ice_fog_cold":
        temp = rng.randint(-28, -12)
        dew_gap = rng.randint(0, 4)
        weather = ["COLD", rng.choice(["FOG", "LFOG", "MIST"])]
        wind = rng.choice(["CALM", "CALM", "N1", "NE1", "E1", "VRB1"])
        cloud_covers = ("OVC", "VV", "BKN")
        height_chance = 0.85
        visibility = rng.choice(["V200", "V300", "V500", "V800", "V1000", "V1500"])
        pressure = _pressure(rng, low=1010, high=1038)
        humidity = f"RH{rng.randint(88, 100)}"
        snow_depth = f"SD{rng.randint(10, 90)}"
        extra = rng.choice([
            ["ICEFOG"],
            ["LOWVIS"],
            ["RIME"],
            ["ICECRYSTAL"],
        ])

    elif cold_type == "cloudy_cold":
        temp = rng.randint(-20, -8)
        dew_gap = rng.randint(2, 8)
        weather = ["COLD"]
        wind = _wind(
            rng,
            speed_min=1,
            speed_max=7,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.20,
        )
        cloud_covers = ("SCT", "BKN", "OVC")
        height_chance = 0.50
        visibility = rng.choice(["V6000", "V7000", "V9000", "VOK"])
        pressure = _pressure(rng, low=1006, high=1028)
        humidity = f"RH{rng.randint(60, 88)}"
        snow_depth = f"SD{rng.randint(5, 75)}"
        extra = rng.choice([
            [],
            ["GREYCOLD"],
            ["LOWCLOUD"],
        ])

    else:  # extreme_cold
        temp = rng.randint(-40, -28)
        dew_gap = rng.randint(5, 18)
        weather = ["COLD"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=6,
            directions=COLD_WIND_DIRECTIONS,
            gust_chance=0.10,
        )
        cloud_covers = ("SKC", "FEW", "SCT")
        height_chance = 0.20
        visibility = rng.choice(["VOK", "V7000", "V9000"])
        pressure = _pressure(rng, low=1020, high=1048)
        humidity = f"RH{rng.randint(35, 75)}"
        snow_depth = f"SD{rng.randint(20, 110)}"
        extra = rng.choice([
            ["EXTCOLD"],
            ["FROSTBITE"],
            ["ARCTIC"],
            ["LOWTEMP"],
        ])

    fields.update(
        temperature=_signed("T", temp),
        dew_point=_signed("D", temp - dew_gap),
        weather=weather,
        wind=wind,
        cloud=_clouds(rng, covers=cloud_covers, height_chance=height_chance),
        visibility=visibility,
        pressure=pressure,
        uv_index="UV0",
        humidity=humidity,
        rain_amount=None,
        snow_depth=snow_depth,
        new_snow=None,
        extra=extra,
    )

    return fields


def _scenario_heat(rng: Random, fields: dict[str, Any]) -> dict[str, Any]:
    heat_type = _weighted_choice(
        rng,
        {
            "dry_clear_heat": 0.18,
            "humid_heat": 0.16,
            "high_pressure_heat": 0.16,
            "urban_heat": 0.12,
            "heatwave": 0.12,
            "hazy_heat": 0.10,
            "calm_hot_afternoon": 0.08,
            "warm_evening": 0.05,
            "hot_breeze": 0.03,
        },
    )

    extra: list[str] = []

    if heat_type == "dry_clear_heat":
        temp = rng.randint(27, 34)
        dew_gap = rng.randint(10, 18)
        weather = ["HEAT"]
        wind = _wind(
            rng,
            speed_min=1,
            speed_max=5,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.05,
        )
        cloud_covers = ("SKC", "FEW")
        height_chance = 0.10
        visibility = "VOK"
        pressure = _pressure(rng, low=1012, high=1028)
        uv_index = f"UV{rng.randint(6, 9)}"
        humidity = f"RH{rng.randint(22, 45)}"
        extra = rng.choice([
            [],
            ["DRYHEAT"],
            ["SUNNY"],
            ["DRYAIR"],
        ])

    elif heat_type == "humid_heat":
        temp = rng.randint(26, 32)
        dew_gap = rng.randint(2, 6)
        weather = ["HEAT"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=4,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.05,
        )
        cloud_covers = ("FEW", "SCT", "BKN")
        height_chance = 0.25
        visibility = rng.choice(["VOK", "V8000", "V9000"])
        pressure = _pressure(rng, low=1008, high=1022)
        uv_index = f"UV{rng.randint(5, 8)}"
        humidity = f"RH{rng.randint(60, 88)}"
        extra = rng.choice([
            [],
            ["HUMID"],
            ["MUGGY"],
            ["HEATINDEX"],
        ])

    elif heat_type == "high_pressure_heat":
        temp = rng.randint(28, 35)
        dew_gap = rng.randint(8, 16)
        weather = ["HEAT"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=4,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud_covers = ("SKC", "SKC", "FEW")
        height_chance = 0.08
        visibility = "VOK"
        pressure = _pressure(rng, low=1020, high=1034)
        uv_index = f"UV{rng.randint(7, 10)}"
        humidity = f"RH{rng.randint(25, 55)}"
        extra = rng.choice([
            ["HIGHPRESSURE"],
            ["HOT"],
            ["SUNNY"],
        ])

    elif heat_type == "urban_heat":
        temp = rng.randint(29, 36)
        dew_gap = rng.randint(5, 12)
        weather = ["HEAT"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=3,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud_covers = ("SKC", "FEW", "SCT")
        height_chance = 0.12
        visibility = rng.choice(["VOK", "V8000", "V9000"])
        pressure = _pressure(rng, low=1010, high=1026)
        uv_index = f"UV{rng.randint(6, 9)}"
        humidity = f"RH{rng.randint(35, 70)}"
        extra = rng.choice([
            ["URBANHEAT"],
            ["CITYHEAT"],
            ["ASPHALT"],
        ])

    elif heat_type == "heatwave":
        temp = rng.randint(31, 38)
        dew_gap = rng.randint(6, 16)
        weather = ["HEAT"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=5,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.05,
        )
        cloud_covers = ("SKC", "FEW", "SCT")
        height_chance = 0.15
        visibility = "VOK"
        pressure = _pressure(rng, low=1012, high=1030)
        uv_index = f"UV{rng.randint(7, 10)}"
        humidity = f"RH{rng.randint(28, 65)}"
        extra = rng.choice([
            ["HEATWAVE"],
            ["HOTDAY"],
            ["SUNGLARE"],
        ])

    elif heat_type == "hazy_heat":
        temp = rng.randint(27, 35)
        dew_gap = rng.randint(5, 12)
        weather = ["HEAT", rng.choice(["HAZE", "LHAZE"])]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=4,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud_covers = ("SKC", "FEW", "SCT")
        height_chance = 0.12
        visibility = rng.choice(["V5000", "V7000", "V8000", "V9000"])
        pressure = _pressure(rng, low=1010, high=1028)
        uv_index = f"UV{rng.randint(5, 9)}"
        humidity = f"RH{rng.randint(35, 70)}"
        extra = rng.choice([
            ["HAZY"],
            ["DUSTHAZE"],
            ["SUNHAZE"],
        ])

    elif heat_type == "calm_hot_afternoon":
        temp = rng.randint(28, 36)
        dew_gap = rng.randint(7, 15)
        weather = ["HEAT"]
        wind = rng.choice(["CALM", "CALM", "S1", "SE1", "SW1", "VRB1"])
        cloud_covers = ("SKC", "FEW")
        height_chance = 0.08
        visibility = "VOK"
        pressure = _pressure(rng, low=1012, high=1028)
        uv_index = f"UV{rng.randint(7, 10)}"
        humidity = f"RH{rng.randint(25, 55)}"
        extra = rng.choice([
            ["AFTERNOON"],
            ["CALM"],
            ["HOT"],
        ])

    elif heat_type == "warm_evening":
        temp = rng.randint(24, 31)
        dew_gap = rng.randint(4, 10)
        weather = ["HEAT"]
        wind = _wind(
            rng,
            speed_min=0,
            speed_max=4,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.0,
        )
        cloud_covers = ("SKC", "FEW", "SCT")
        height_chance = 0.12
        visibility = rng.choice(["VOK", "V9000"])
        pressure = _pressure(rng, low=1010, high=1026)
        uv_index = f"UV{rng.randint(0, 3)}"
        humidity = f"RH{rng.randint(45, 75)}"
        extra = rng.choice([
            ["EVENING"],
            ["WARMNIGHT"],
            ["NIGHTHEAT"],
        ])

    else:  # hot_breeze
        temp = rng.randint(26, 34)
        dew_gap = rng.randint(6, 14)
        weather = ["HEAT"]
        wind = _wind(
            rng,
            speed_min=4,
            speed_max=8,
            directions=WARM_WIND_DIRECTIONS,
            gust_chance=0.20,
        )
        cloud_covers = ("SKC", "FEW", "SCT")
        height_chance = 0.15
        visibility = "VOK"
        pressure = _pressure(rng, low=1008, high=1024)
        uv_index = f"UV{rng.randint(5, 9)}"
        humidity = f"RH{rng.randint(30, 65)}"
        extra = rng.choice([
            ["HOTWIND"],
            ["BREEZY"],
            ["DRYHEAT"],
        ])

    fields.update(
        temperature=_signed("T", temp),
        dew_point=_signed("D", temp - dew_gap),
        weather=weather,
        wind=wind,
        cloud=_clouds(rng, covers=cloud_covers, height_chance=height_chance),
        visibility=visibility,
        pressure=pressure,
        uv_index=uv_index,
        humidity=humidity,
        rain_amount=None,
        snow_depth=None,
        new_snow=None,
        extra=extra,
    )

    return fields


def _random_time(rng: Random) -> str:
    hour = rng.randint(0, 23)
    minute = rng.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])
    return f"{hour:02d}{minute:02d}Z"


def _signed(prefix: str, value: int) -> str:
    if value < 0:
        return f"{prefix}M{abs(value)}"

    return f"{prefix}{value}"


def _pressure(rng: Random, *, low: int = 990, high: int = 1030) -> str:
    return f"Q{rng.randint(low, high):04d}"


def _wind(
    rng: Random,
    *,
    speed_min: int,
    speed_max: int,
    directions: Sequence[str],
    gust_chance: float = 0.0,
) -> str:
    speed = rng.randint(speed_min, speed_max)

    if speed <= 0:
        return "CALM"

    direction = rng.choice(list(directions))

    if rng.random() < 0.08:
        direction = "VRB"

    wind = f"{direction}{speed}"

    if rng.random() < gust_chance:
        gust = min(99, speed + rng.randint(3, 10))
        wind += f"G{gust}"

    return wind


def _clouds(
    rng: Random,
    *,
    covers: Sequence[str],
    height_chance: float,
) -> list[str]:
    cover = rng.choice(list(covers))

    if cover == "SKC":
        return ["SKC"]

    layers = [_cloud_layer(rng, cover, height_chance=height_chance)]

    if rng.random() < 0.18 and cover not in {"OVC", "VV"}:
        second_cover = rng.choice(list(LOW_CLOUD_COVERS))
        layers.append(_cloud_layer(rng, second_cover, height_chance=height_chance))

    return sorted(layers, key=_cloud_sort_key)


def _cloud_sort_key(layer: str) -> tuple[int, int, str]:
    text = str(layer or "").upper().strip()

    if text == "SKC":
        return (0, 0, text)

    match = re.search(r"(\d{3})$", text)

    if match:
        return (1, int(match.group(1)), text)

    return (2, 999, text)


def _cloud_layer(rng: Random, cover: str, *, height_chance: float) -> str:
    if cover == "SKC":
        return "SKC"

    if rng.random() > height_chance:
        return cover

    height = rng.randint(3, 90)
    return f"{cover}{height:03d}"


def _resolve_profile(rng: Random, profile: str) -> str:
    profile = str(profile or PROFILE_AUTO).lower().strip()

    if profile not in WX_MOR_PROFILES:
        raise ValueError(f"Unknown WX-MOR profile: {profile}")

    if profile == PROFILE_AUTO:
        return _weighted_choice(rng, AUTO_PROFILE_WEIGHTS)

    return profile


def _merge_scenario_weights(
    default_weights: Mapping[str, float],
    override_weights: Mapping[str, float] | None,
) -> dict[str, float]:
    result = {
        str(key): max(0.0, float(value))
        for key, value in default_weights.items()
    }

    if override_weights is None:
        return result

    for key, value in override_weights.items():
        key = str(key)

        if key not in result:
            continue

        result[key] = max(0.0, float(value))

    return result


def _weighted_choice(rng: Random, weights: Mapping[str, float]) -> str:
    cleaned = [
        (key, max(0.0, float(weight)))
        for key, weight in weights.items()
        if float(weight) > 0
    ]

    if not cleaned:
        raise ValueError("Weighted choice received no positive weights.")

    total = sum(weight for _key, weight in cleaned)
    pick = rng.random() * total
    cumulative = 0.0

    for key, weight in cleaned:
        cumulative += weight

        if pick <= cumulative:
            return key

    return cleaned[-1][0]


def _normalize_location_codes(
    locations: Sequence[str | Mapping[str, str]] | None,
) -> list[str]:
    source = locations if locations else WXMOR_LOCATIONS
    result: list[str] = []

    for item in source:
        if isinstance(item, Mapping):
            raw_code = str(item.get("code", ""))
        else:
            raw_code = str(item)

        code = re.sub(r"[^A-Z0-9]", "", raw_code.upper().strip())

        if 3 <= len(code) <= 6:
            result.append(code)

    if not result:
        raise ValueError("WX-MOR location list is empty.")

    return sorted(set(result))


def _push(parts: list[str], value: Any) -> None:
    if value is None:
        return

    if isinstance(value, (list, tuple)):
        for item in value:
            _push(parts, item)

        return

    text = normalize_message(str(value))

    if text:
        parts.extend(text.split(" "))


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