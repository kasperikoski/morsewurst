# ============================================================
# morsewurst/koch/alignment.py
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class KochAlignmentOp:
    """One visual/score alignment cell for a Koch receive-practice result."""

    action: str
    target_index: int | None
    entered_index: int | None
    timing_weight: float = 1.0
    timing_penalty: float = 0.0
    timing_status: str = ""


@dataclass(frozen=True)
class KochAlignmentSummary:
    """Combined text and time-aware alignment metrics."""

    ops: list[KochAlignmentOp]
    aligned_accuracy: float
    time_aligned_accuracy: float
    timing_fit: float


def _safe_percent(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0

    return max(0.0, min(100.0, (float(numerator) / float(denominator)) * 100.0))


def levenshtein_ops(target: str, entered: str) -> list[KochAlignmentOp]:
    """Return a plain text-only Levenshtein alignment.

    This remains useful as a generous "final copy" metric: it lets a user miss
    a few characters and then recover without making the entire rest of the
    line wrong.
    """

    n = len(target)
    m = len(entered)

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    back = [[""] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = i
        back[i][0] = "delete"

    for j in range(1, m + 1):
        dp[0][j] = j
        back[0][j] = "insert"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if target[i - 1] == entered[j - 1] else 1
            candidates = [
                (dp[i - 1][j - 1] + cost, "equal" if cost == 0 else "substitution"),
                (dp[i - 1][j] + 1, "delete"),
                (dp[i][j - 1] + 1, "insert"),
            ]
            best_cost, best_action = min(
                candidates,
                key=lambda item: (
                    item[0],
                    0 if item[1] in {"equal", "substitution"} else 1,
                    2 if item[1] == "insert" else 0,
                ),
            )
            dp[i][j] = best_cost
            back[i][j] = best_action

    raw_ops: list[KochAlignmentOp] = []
    i = n
    j = m

    while i > 0 or j > 0:
        action = back[i][j]

        if i > 0 and j > 0 and action in {"equal", "substitution"}:
            raw_ops.append(KochAlignmentOp(action, i - 1, j - 1))
            i -= 1
            j -= 1
            continue

        if i > 0 and (j == 0 or action == "delete"):
            raw_ops.append(KochAlignmentOp("delete", i - 1, None))
            i -= 1
            continue

        if j > 0:
            raw_ops.append(KochAlignmentOp("insert", None, j - 1))
            j -= 1
            continue

        break

    return list(reversed(raw_ops))


def _extract_target_times(target_schedule: list[dict[str, Any]], target_length: int) -> list[int | None]:
    times: list[int | None] = []

    for index in range(target_length):
        value: int | None = None
        if index < len(target_schedule):
            raw = target_schedule[index].get("end_ms")
            if isinstance(raw, (int, float)):
                value = int(raw)
            else:
                raw = target_schedule[index].get("start_ms")
                if isinstance(raw, (int, float)):
                    value = int(raw)
        times.append(value)

    return times


def _extract_typed_times(typed_events: list[dict[str, Any]], entered_length: int) -> list[int | None]:
    times: list[int | None] = []

    for index in range(entered_length):
        value: int | None = None
        if index < len(typed_events):
            raw = typed_events[index].get("typed_at_ms")
            if isinstance(raw, (int, float)):
                value = int(raw)
        times.append(value)

    return times


def _timing_penalty(target_time_ms: int | None, typed_time_ms: int | None) -> tuple[float, float, str]:
    """Return penalty, correctness weight and status for one possible pairing.

    This is deliberately not a strict reaction-time check. The user may copy
    almost immediately, trail behind by a second or two, or recover after a
    longer pause. Very implausible pairings still get penalized so repeated
    letters are not matched too generously to the wrong part of the drill.
    """

    if target_time_ms is None or typed_time_ms is None:
        return 0.0, 1.0, "unknown"

    delay = float(typed_time_ms - target_time_ms)

    if delay < -450.0:
        penalty = min(2.6, (abs(delay) - 450.0) / 700.0)
        return penalty, max(0.0, 1.0 - (penalty / 2.6)), "early"

    if delay <= 2500.0:
        return 0.0, 1.0, "in_time"

    if delay <= 7000.0:
        penalty = ((delay - 2500.0) / 4500.0) * 0.80
        return penalty, max(0.35, 1.0 - (penalty / 2.2)), "late"

    if delay <= 15000.0:
        penalty = 0.80 + (((delay - 7000.0) / 8000.0) * 1.10)
        return penalty, max(0.15, 1.0 - (penalty / 2.4)), "recovered_late"

    penalty = 2.7
    return penalty, 0.0, "too_late"


def time_aware_alignment(
    *,
    target: str,
    entered: str,
    typed_events: list[dict[str, Any]] | None,
    target_schedule: list[dict[str, Any]] | None,
) -> KochAlignmentSummary:
    """Align copy text using both sequence order and loose timing information.

    The algorithm still allows recovery after dropped characters, but it favors
    alignments whose typed characters were produced near the part of the drill
    where those characters were actually heard. This prevents short repeated
    alphabets such as K/M drills from receiving unrealistically high scores
    simply because the same letters appear many times elsewhere.
    """

    typed_events = typed_events or []
    target_schedule = target_schedule or []

    plain_ops = levenshtein_ops(target, entered)
    plain_correct = sum(
        1
        for op in plain_ops
        if op.action == "equal"
        and op.target_index is not None
        and op.entered_index is not None
    )
    aligned_accuracy = round(_safe_percent(plain_correct, len(target)), 2)

    target_times = _extract_target_times(target_schedule, len(target))
    typed_times = _extract_typed_times(typed_events, len(entered))

    if not target or not entered or not target_schedule or not typed_events:
        return KochAlignmentSummary(
            ops=plain_ops,
            aligned_accuracy=aligned_accuracy,
            time_aligned_accuracy=aligned_accuracy,
            timing_fit=100.0 if aligned_accuracy > 0 else 0.0,
        )

    n = len(target)
    m = len(entered)

    delete_cost = 1.00
    insert_cost = 1.15
    substitution_cost = 1.20

    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    back = [[""] * (m + 1) for _ in range(n + 1)]
    pair_meta: list[list[tuple[float, float, str] | None]] = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = float(i) * delete_cost
        back[i][0] = "delete"

    for j in range(1, m + 1):
        dp[0][j] = float(j) * insert_cost
        back[0][j] = "insert"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            timing_penalty, timing_weight, timing_status = _timing_penalty(
                target_times[i - 1],
                typed_times[j - 1],
            )

            if target[i - 1] == entered[j - 1]:
                pair_cost = timing_penalty
                action = "equal"
            else:
                pair_cost = substitution_cost + (timing_penalty * 0.45)
                action = "substitution"

            candidates = [
                (dp[i - 1][j - 1] + pair_cost, action, (timing_penalty, timing_weight, timing_status)),
                (dp[i - 1][j] + delete_cost, "delete", None),
                (dp[i][j - 1] + insert_cost, "insert", None),
            ]
            best_cost, best_action, best_meta = min(
                candidates,
                key=lambda item: (
                    item[0],
                    0 if item[1] in {"equal", "substitution"} else 1,
                    2 if item[1] == "insert" else 0,
                ),
            )
            dp[i][j] = best_cost
            back[i][j] = best_action
            pair_meta[i][j] = best_meta

    ops: list[KochAlignmentOp] = []
    i = n
    j = m

    while i > 0 or j > 0:
        action = back[i][j]

        if i > 0 and j > 0 and action in {"equal", "substitution"}:
            meta = pair_meta[i][j] or (0.0, 1.0, "unknown")
            ops.append(
                KochAlignmentOp(
                    action=action,
                    target_index=i - 1,
                    entered_index=j - 1,
                    timing_penalty=float(meta[0]),
                    timing_weight=float(meta[1]),
                    timing_status=str(meta[2]),
                )
            )
            i -= 1
            j -= 1
            continue

        if i > 0 and (j == 0 or action == "delete"):
            ops.append(KochAlignmentOp("delete", i - 1, None, 0.0, 0.0, "missing"))
            i -= 1
            continue

        if j > 0:
            ops.append(KochAlignmentOp("insert", None, j - 1, 0.0, 0.0, "extra"))
            j -= 1
            continue

        break

    ops.reverse()

    timed_correct_weight = 0.0
    timing_weights: list[float] = []
    for op in ops:
        if op.target_index is not None and op.entered_index is not None:
            timing_weights.append(op.timing_weight)
            if op.action == "equal":
                timed_correct_weight += op.timing_weight

    time_aligned_accuracy = round(_safe_percent(timed_correct_weight, len(target)), 2)
    timing_fit = round((sum(timing_weights) / len(timing_weights)) * 100.0, 2) if timing_weights else 0.0

    return KochAlignmentSummary(
        ops=ops,
        aligned_accuracy=aligned_accuracy,
        time_aligned_accuracy=time_aligned_accuracy,
        timing_fit=timing_fit,
    )
