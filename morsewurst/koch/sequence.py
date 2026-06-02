# ============================================================
# morsewurst/koch/sequence.py
# ============================================================

from __future__ import annotations

from dataclasses import dataclass

import morsewurst.config as config


@dataclass(frozen=True)
class KochSequence:
    key: str
    label: str
    characters: str
    description: str = ""


def _dedupe(text: str) -> str:
    result: list[str] = []

    for raw_char in str(text or "").upper():
        if raw_char.isspace():
            continue

        if raw_char not in result:
            result.append(raw_char)

    return "".join(result)


def _full_set() -> str:
    return _dedupe(
        str(getattr(config, "LETTERS", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        + str(getattr(config, "NUMBERS", "0123456789"))
        + str(getattr(config, "PUNCTUATION", ".,?!/()&:;=+-_\"@$'"))
    )


def _complete_sequence(prefix: str) -> str:
    """Return prefix plus every Morsewurst-supported character not already in it."""
    return _dedupe(prefix + _full_set())


CLASSIC_KOCH_SEQUENCE = _complete_sequence(
    "KMRSUAPTLOWI.NJEF0Y,VG5/Q9ZH38B?427C1D6X"
)

LCWO_STYLE_SEQUENCE = _complete_sequence(
    "KMURESNAPTLWI.JZ=FOY,VG5/Q9H38B?427C1D6X"
)



def all_koch_sequences() -> list[KochSequence]:
    return [
        KochSequence(
            key="classic",
            label="Classic Koch",
            characters=CLASSIC_KOCH_SEQUENCE,
            description="Classic K/M first order, completed with the full Morsewurst character set.",
        ),
        KochSequence(
            key="lcwo",
            label="LCWO-style",
            characters=LCWO_STYLE_SEQUENCE,
            description="LCWO-inspired order, completed with the full Morsewurst character set.",
        ),
    ]


def koch_sequence_by_key(key: str | None) -> KochSequence:
    normalized = str(key or "").strip().lower()

    for sequence in all_koch_sequences():
        if sequence.key == normalized:
            return sequence

    return all_koch_sequences()[0]


def active_chars_for_stage(sequence: KochSequence, stage_index: int) -> str:
    stage = max(1, int(stage_index))
    return sequence.characters[: min(stage, len(sequence.characters))]


def stage_for_all_characters(sequence: KochSequence) -> int:
    return len(sequence.characters)


def stage_label(sequence: KochSequence, stage_index: int) -> str:
    active = active_chars_for_stage(sequence, stage_index)
    return f"{sequence.label}: {len(active)}/{len(sequence.characters)}"
