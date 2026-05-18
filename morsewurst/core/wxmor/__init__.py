# ============================================================
# morsewurst/core/wxmor/__init__.py
# ============================================================

from __future__ import annotations

from morsewurst.core.wxmor.generator import (
    WxMorGeneratorOptions,
    WxMorMessage,
    generate_wxmor_message,
)
from morsewurst.core.wxmor.profiles import (
    PROFILE_AUTO,
    PROFILE_BASIC,
    PROFILE_COMPACT,
    PROFILE_EXTENDED,
    PROFILE_MINIMUM,
    WX_MOR_PROFILE_LABELS,
)
from morsewurst.core.wxmor.validation import (
    WxMorValidationResult,
    validate_fields,
    validate_message_allowed,
    validate_wxmor_message,
)

__all__ = [
    "WxMorGeneratorOptions",
    "WxMorMessage",
    "generate_wxmor_message",
    "PROFILE_AUTO",
    "PROFILE_BASIC",
    "PROFILE_COMPACT",
    "PROFILE_EXTENDED",
    "PROFILE_MINIMUM",
    "WX_MOR_PROFILE_LABELS",
    "WxMorValidationResult",
    "validate_fields",
    "validate_message_allowed",
    "validate_wxmor_message",
]