"""When a candidate can no longer pass a gate, whatever it does next.

Every rule here is **arithmetic, not statistical**. A candidate is
retired only when the gate's own expression, evaluated at that
candidate's *best possible future*, still fails — never because it looks
like it is losing. Statistical elimination is N9 racing (successive
halving) and belongs to a later phase with its own safety condition; a
flag that quietly did both is how an unlucky candidate gets dropped and
nobody can trace why.

**The formulation, once.** Each rule assumes every remaining episode
goes as well as it possibly can — no collision, no failure, no growth in
memory — and then asks the gate. If it still fails, no sequence of
future episodes can save it.

That framing also makes the rules sound at a *shorter* run than the one
planned, which matters because a run can be interrupted after a
candidate was retired. Retiring on G3 needs
``failures > N(1 - threshold)``; at any ``n <= N`` the observed rate is
``(n - failures) / n``, and ``failures > N(1 - thr) >= n(1 - thr)``
gives ``(n - failures) / n < thr``. The verdict holds at every sample
size the run can end at, not only the one it aimed for.

**What is deliberately absent.**

*G4 (real-time)* has no sound rule and must not acquire one. The gate
compares a **pooled p99** over every control step, and that percentile
is not monotone: five thousand slow steps inside the first hundred
thousand can sink below p99 once the total reaches four hundred
thousand. "p99 is over budget right now" would retire a candidate for
starting slowly. :data:`GATES_WITHOUT_A_RULE` records the refusal so it
reads as a decision rather than an oversight.

*G6 (observation compatibility)* is decided before episode one, by
``build_candidates``. There is nothing left for a stopping rule to add.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from planbench_metrics.definitions import EpisodeMetricSet
from planbench_schemas.task_profile import TaskProfile

__all__ = [
    "GATES_WITHOUT_A_RULE",
    "StopVerdict",
    "check_early_stop",
]

#: Gates that must never retire a candidate, and why. Consulted by the
#: tests, so deleting an entry breaks a test rather than silently
#: widening the feature.
GATES_WITHOUT_A_RULE: dict[str, str] = {
    "G4": (
        "p99 gộp không đơn điệu — thêm control step có thể kéo phân vị xuống, "
        "nên 'đang vượt ngân sách' không chứng minh được 'sẽ vượt'"
    ),
    "G6": "quyết trước episode một, trong build_candidates — không còn gì để dừng sớm",
}


@dataclass(frozen=True)
class StopVerdict:
    """Why a candidate was retired, in terms a reader can re-check."""

    gate: str
    rule: str
    evidence: dict[str, object]

    def to_json_dict(self) -> dict[str, object]:
        return {"gate": self.gate, "rule": self.rule, "evidence": dict(self.evidence)}


def check_early_stop(
    metrics: Sequence[EpisodeMetricSet],
    profile: TaskProfile,
    *,
    planned_episodes: int,
    available_ram_mb: float | None = None,
) -> StopVerdict | None:
    """The first gate this candidate can no longer pass, or ``None``.

    ``metrics`` are the episodes measured so far, recomputed from traces
    like every other verdict (HĐ-5) — never counters carried in the
    simulating process, or a gate verdict could come from memory and two
    runs could disagree with no file to explain it.

    Gates are checked in contract order so the reported reason is the
    earliest one, which is also the one a reader looks for first.
    """
    if not metrics:
        return None
    checks = (
        _no_path_rate_already_lost,
        _collision_already_observed,
        _success_rate_already_lost,
        _memory_already_over_budget,
    )
    for check in checks:
        verdict = check(metrics, profile, planned_episodes, available_ram_mb)
        if verdict is not None:
            return verdict
    return None


def _collision_already_observed(
    metrics: Sequence[EpisodeMetricSet],
    profile: TaskProfile,
    _planned: int,
    _ram: float | None,
) -> StopVerdict | None:
    """G2 demands exactly zero. One observation is absorbing.

    The only rule here that needs no arithmetic at all: a collision
    cannot be un-observed, and G2 has no allowance to spend.
    """
    observed = sum(m.collision_count for m in metrics)
    if observed == 0:
        return None
    first = next(m for m in metrics if m.collision_count > 0)
    return StopVerdict(
        gate="G2",
        rule=(
            "đã quan sát va chạm trong khi G2 đòi đúng 0 — không episode nào sau đó "
            "đảo được điều đã quan sát"
        ),
        evidence={
            "observed_collisions": observed,
            "first_collision_episode_context_id": first.episode_context_id,
            "episodes_measured": len(metrics),
        },
    )


def _success_rate_already_lost(
    metrics: Sequence[EpisodeMetricSet],
    profile: TaskProfile,
    planned: int,
    _ram: float | None,
) -> StopVerdict | None:
    """G3, evaluated as if every remaining episode succeeded."""
    threshold = profile.constraints.success_rate_min
    failures = sum(1 for m in metrics if not m.success)
    # Exactly the gate's own expression (successes / n) at the best
    # future: all remaining episodes succeed, so successes = N - failures.
    best_possible = (planned - failures) / planned
    if best_possible >= threshold:
        return None
    return StopVerdict(
        gate="G3",
        rule=(
            f"{failures} thất bại trên {planned} episode dự kiến ⇒ success tốt nhất còn "
            f"đạt được là {best_possible:.4f}, dưới ngưỡng {threshold:.4f} kể cả khi mọi "
            "episode còn lại đều thành công"
        ),
        evidence={
            "failures": failures,
            "best_possible_success_rate": best_possible,
            "threshold": threshold,
            "max_failures_allowed": math.floor(planned * (1.0 - threshold)),
            "episodes_measured": len(metrics),
        },
    )


def _no_path_rate_already_lost(
    metrics: Sequence[EpisodeMetricSet],
    profile: TaskProfile,
    planned: int,
    _ram: float | None,
) -> StopVerdict | None:
    """G1, evaluated as if no remaining episode failed to find a path."""
    threshold = profile.constraints.no_path_rate_max
    no_path = sum(1 for m in metrics if m.failure_reason == "no_path")
    best_possible = no_path / planned
    if best_possible <= threshold:
        return None
    return StopVerdict(
        gate="G1",
        rule=(
            f"{no_path} episode không tìm được đường trên {planned} dự kiến ⇒ tỷ lệ thấp "
            f"nhất còn đạt được là {best_possible:.4f}, trên ngưỡng {threshold:.4f} kể cả "
            "khi mọi episode còn lại đều tìm được đường"
        ),
        evidence={
            "no_path_episodes": no_path,
            "best_possible_no_path_rate": best_possible,
            "threshold": threshold,
            "episodes_measured": len(metrics),
        },
    )


def _memory_already_over_budget(
    metrics: Sequence[EpisodeMetricSet],
    profile: TaskProfile,
    _planned: int,
    available_ram_mb: float | None,
) -> StopVerdict | None:
    """G5 takes the worst episode, so the maximum only ever grows.

    Skipped rather than raised when an estimate is missing: G5 itself
    refuses that input loudly at scoring time, and a stopping rule is
    the wrong place to discover it — it would turn a diagnosable error
    into an early exit.
    """
    budget = available_ram_mb if available_ram_mb is not None else profile.hardware.available_ram_mb
    estimates = [m.memory_estimate_mb for m in metrics if m.memory_estimate_mb is not None]
    if len(estimates) != len(metrics) or not estimates:
        return None
    worst = max(estimates)
    if worst <= budget:
        return None
    return StopVerdict(
        gate="G5",
        rule=(
            f"ước lượng bộ nhớ tệ nhất {worst:.2f} MB vượt ngân sách {budget:.2f} MB, và "
            "G5 lấy episode tệ nhất nên con số này chỉ có thể tăng"
        ),
        evidence={
            "memory_estimate_mb": worst,
            "available_ram_mb": budget,
            "episodes_measured": len(metrics),
        },
    )
