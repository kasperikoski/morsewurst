# ============================================================
# morsewurst/ui/help_content.py
# ============================================================

from __future__ import annotations

from typing import Any


# This file defines the help document structure only.
# The visible text is loaded through the normal Morsewurst i18n service.
# Add matching translations for these keys to all supported morsewurst/i18n/*.json files.

HELP_DOCUMENT_SPEC: list[dict[str, str]] = [
    {"type": "title", "key": "help.content.title"},
    {"type": "paragraph", "key": "help.content.intro"},
    {"type": "note", "key": "help.content.prototype_note"},

    {"type": "heading", "key": "help.content.getting_started.heading"},
    {"type": "paragraph", "key": "help.content.getting_started.intro"},
    {"type": "paragraph", "key": "help.content.getting_started.profile"},
    {"type": "paragraph", "key": "help.content.getting_started.device"},
    {"type": "paragraph", "key": "help.content.getting_started.settings"},
    {"type": "paragraph", "key": "help.content.getting_started.start"},
    {"type": "paragraph", "key": "help.content.getting_started.results"},

    {"type": "heading", "key": "help.content.input.heading"},
    {"type": "paragraph", "key": "help.content.input.intro"},
    {"type": "paragraph", "key": "help.content.input.telemetry"},
    {"type": "paragraph", "key": "help.content.input.hid"},
    {"type": "paragraph", "key": "help.content.input.keyboard"},
    {"type": "paragraph", "key": "help.content.input.autoconnect"},
    {"type": "note", "key": "help.content.input.note"},

    {"type": "heading", "key": "help.content.practice_settings.heading"},
    {"type": "paragraph", "key": "help.content.practice_settings.intro"},
    {"type": "paragraph", "key": "help.content.practice_settings.characters"},
    {"type": "paragraph", "key": "help.content.practice_settings.character_mix"},
    {"type": "note", "key": "help.content.practice_settings.character_mix_note"},
    {"type": "paragraph", "key": "help.content.practice_settings.groups"},
    {"type": "paragraph", "key": "help.content.practice_settings.wpm"},
    {"type": "paragraph", "key": "help.content.practice_settings.rounds"},
    {"type": "paragraph", "key": "help.content.practice_settings.wxmor"},
    {"type": "paragraph", "key": "help.content.practice_settings.problem_chars"},
    {"type": "paragraph", "key": "help.content.practice_settings.problem_chars_mix"},
    {"type": "paragraph", "key": "help.content.practice_settings.suggest_speed"},

    {"type": "heading", "key": "help.content.koch.heading"},
    {"type": "paragraph", "key": "help.content.koch.intro"},
    {"type": "paragraph", "key": "help.content.koch.modes"},
    {"type": "paragraph", "key": "help.content.koch.sequence_stage"},
    {"type": "paragraph", "key": "help.content.koch.speed_audio"},
    {"type": "paragraph", "key": "help.content.koch.target_length"},
    {"type": "paragraph", "key": "help.content.koch.scoring"},
    {"type": "paragraph", "key": "help.content.koch.guided_progress"},
    {"type": "paragraph", "key": "help.content.koch.skill"},
    {"type": "paragraph", "key": "help.content.koch.radio_noise"},
    {"type": "note", "key": "help.content.koch.note"},

    {"type": "heading", "key": "help.content.round.heading"},
    {"type": "paragraph", "key": "help.content.round.intro"},
    {"type": "paragraph", "key": "help.content.round.target"},
    {"type": "paragraph", "key": "help.content.round.raw"},
    {"type": "paragraph", "key": "help.content.round.decoded"},
    {"type": "paragraph", "key": "help.content.round.clock"},
    {"type": "paragraph", "key": "help.content.round.finish"},
    {"type": "paragraph", "key": "help.content.round.stop"},
    {"type": "note", "key": "help.content.round.auto_finish_note"},

    {"type": "heading", "key": "help.content.scoring.heading"},
    {"type": "paragraph", "key": "help.content.scoring.intro"},
    {"type": "paragraph", "key": "help.content.scoring.accuracy"},
    {"type": "paragraph", "key": "help.content.scoring.cleanliness"},
    {"type": "paragraph", "key": "help.content.scoring.overall"},
    {"type": "paragraph", "key": "help.content.scoring.timing"},
    {"type": "paragraph", "key": "help.content.scoring.paris"},
    {"type": "paragraph", "key": "help.content.scoring.net"},
    {"type": "paragraph", "key": "help.content.scoring.device"},
    {"type": "paragraph", "key": "help.content.scoring.ratio"},
    {"type": "code", "key": "help.content.scoring.formula"},
    {"type": "note", "key": "help.content.scoring.spaces_note"},

    {"type": "heading", "key": "help.content.decoder.heading"},
    {"type": "paragraph", "key": "help.content.decoder.intro"},
    {"type": "paragraph", "key": "help.content.decoder.target_seed"},
    {"type": "paragraph", "key": "help.content.decoder.profile"},
    {"type": "paragraph", "key": "help.content.decoder.sources"},
    {"type": "paragraph", "key": "help.content.decoder.confidence"},
    {"type": "paragraph", "key": "help.content.decoder.profile_quality"},
    {"type": "paragraph", "key": "help.content.decoder.raw_truth"},
    {"type": "code", "key": "help.content.decoder.units"},
    {"type": "note", "key": "help.content.decoder.note"},

    {"type": "heading", "key": "help.content.skill.heading"},
    {"type": "paragraph", "key": "help.content.skill.intro"},
    {"type": "paragraph", "key": "help.content.skill.overall"},
    {"type": "paragraph", "key": "help.content.skill.both_keys"},
    {"type": "paragraph", "key": "help.content.skill.level"},
    {"type": "paragraph", "key": "help.content.skill.confidence"},
    {"type": "paragraph", "key": "help.content.skill.mastery"},
    {"type": "paragraph", "key": "help.content.skill.not_enough"},

    {"type": "heading", "key": "help.content.history.heading"},
    {"type": "paragraph", "key": "help.content.history.intro"},
    {"type": "paragraph", "key": "help.content.history.recent"},
    {"type": "paragraph", "key": "help.content.history.general"},
    {"type": "paragraph", "key": "help.content.history.stats"},
    {"type": "paragraph", "key": "help.content.history.delete"},

    {"type": "heading", "key": "help.content.advanced.heading"},
    {"type": "paragraph", "key": "help.content.advanced.intro"},
    {"type": "paragraph", "key": "help.content.advanced.speed"},
    {"type": "paragraph", "key": "help.content.advanced.input"},
    {"type": "paragraph", "key": "help.content.advanced.decoder"},
    {"type": "paragraph", "key": "help.content.advanced.problem_chars"},
    {"type": "paragraph", "key": "help.content.advanced.sound"},
    {"type": "paragraph", "key": "help.content.advanced.koch"},
    {"type": "paragraph", "key": "help.content.advanced.effective"},
    {"type": "paragraph", "key": "help.content.advanced.skill"},
    {"type": "paragraph", "key": "help.content.advanced.stats"},
    {"type": "paragraph", "key": "help.content.advanced.debug"},
    {"type": "paragraph", "key": "help.content.advanced.logging"},

    {"type": "heading", "key": "help.content.network.heading"},
    {"type": "paragraph", "key": "help.content.network.intro"},
    {"type": "paragraph", "key": "help.content.network.callsign"},
    {"type": "paragraph", "key": "help.content.network.public_rooms"},
    {"type": "paragraph", "key": "help.content.network.private_rooms"},
    {"type": "paragraph", "key": "help.content.network.remembered"},
    {"type": "paragraph", "key": "help.content.network.server_info"},
    {"type": "paragraph", "key": "help.content.network.quality"},
    {"type": "paragraph", "key": "help.content.network.settings"},
    {"type": "paragraph", "key": "help.content.network.audio"},
    {"type": "paragraph", "key": "help.content.network.radio_noise"},
    {"type": "paragraph", "key": "help.content.network.noise_ducking"},
    {"type": "paragraph", "key": "help.content.network.transmit"},
    {"type": "note", "key": "help.content.network.note"},

    {"type": "heading", "key": "help.content.profiles.heading"},
    {"type": "paragraph", "key": "help.content.profiles.intro"},
    {"type": "paragraph", "key": "help.content.profiles.create"},
    {"type": "paragraph", "key": "help.content.profiles.switch"},
    {"type": "paragraph", "key": "help.content.profiles.delete"},
    {"type": "paragraph", "key": "help.content.profiles.language"},
    {"type": "paragraph", "key": "help.content.profiles.storage"},

    {"type": "heading", "key": "help.content.troubleshooting.heading"},
    {"type": "paragraph", "key": "help.content.troubleshooting.intro"},
    {"type": "paragraph", "key": "help.content.troubleshooting.serial"},
    {"type": "paragraph", "key": "help.content.troubleshooting.keyboard"},
    {"type": "paragraph", "key": "help.content.troubleshooting.network"},
    {"type": "paragraph", "key": "help.content.troubleshooting.audio"},
    {"type": "paragraph", "key": "help.content.troubleshooting.debug"},
    {"type": "paragraph", "key": "help.content.troubleshooting.logs"},
    {"type": "paragraph", "key": "help.content.troubleshooting.updates"},

    {"type": "heading", "key": "help.content.tips.heading"},
    {"type": "paragraph", "key": "help.content.tips.telemetry"},
    {"type": "paragraph", "key": "help.content.tips.clean_rounds"},
    {"type": "paragraph", "key": "help.content.tips.wpm"},
    {"type": "paragraph", "key": "help.content.tips.problem_chars"},
    {"type": "paragraph", "key": "help.content.tips.character_mix"},
    {"type": "paragraph", "key": "help.content.tips.network"},

    {"type": "paragraph", "key": "help.content.closing"},
]

HELP_DOCUMENT = HELP_DOCUMENT_SPEC


def build_help_document(i18n: Any) -> list[dict[str, str]]:
    """Build translated help blocks for HelpWindow."""

    translated: list[dict[str, str]] = []

    for block in HELP_DOCUMENT_SPEC:
        block_type = str(block.get("type") or "paragraph")
        key = str(block.get("key") or "").strip()

        if not key:
            continue

        try:
            text = str(i18n.t(key))
        except Exception:
            text = key

        text = text.strip()
        if not text:
            continue

        translated.append({"type": block_type, "text": text})

    return translated
