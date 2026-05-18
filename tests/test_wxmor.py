from __future__ import annotations

import random

from morsewurst.core.challenge import generate_wxmor_challenge
from morsewurst.core.wxmor.generator import WxMorGeneratorOptions, generate_from_options, generate_wxmor_message
from morsewurst.core.wxmor.validation import (
    normalize_message,
    sort_weather_tokens,
    validate_message_allowed,
    validate_wxmor_message,
    weather_base_token,
)


def test_wxmor_normalize_message_removes_disallowed_characters() -> None:
    assert normalize_message("wx efhk! t05\nRAIN") == "WX EFHK T05 RAIN"


def test_wxmor_generated_minimum_message_is_allowed_and_starts_with_wx() -> None:
    random.seed(1)

    message = generate_wxmor_message(profile="minimum", locations=["EFHK"]).message
    validation = validate_wxmor_message(message)

    assert message.startswith("WX EFHK ")
    assert validation.ok is True
    assert validate_message_allowed(message).ok is True


def test_generate_from_options_uses_profile_and_location() -> None:
    random.seed(2)
    result = generate_from_options(WxMorGeneratorOptions(profile="basic", locations=["EFOU"]))

    assert result.message.startswith("WX EFOU ")
    assert result.profile in {"basic", "minimum", "compact", "extended"}
    assert result.scenario
    assert result.fields["loc"] == "EFOU"


def test_challenge_adapter_returns_plain_wxmor_message() -> None:
    random.seed(3)

    challenge = generate_wxmor_challenge(profile="minimum", locations=["EFHK"])

    assert isinstance(challenge, str)
    assert challenge.startswith("WX EFHK ")
    assert validate_wxmor_message(challenge).ok is True


def test_weather_token_helpers_understand_compact_aliases() -> None:
    assert weather_base_token("LRA") == "RAIN"
    assert sort_weather_tokens(["SNOW", "RAIN", "THUNDER"])[0] == "THUNDER"
