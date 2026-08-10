"""Feasibility gates G1–G6 (CONTRACTS HĐ-7).

> Gates run **before** any scoring. Thresholds come from
> ``task_profile.constraints`` and ``task_profile.hardware``, never
> hardcoded.

A gate is not a score. Scoring answers "which candidate is better"; a
gate answers "may this candidate be considered at all", and the two must
not be traded off against each other — a stack that collides is not
redeemed by being fast. That is why this module produces a verdict per
gate with the evidence attached, and why nothing here returns a number
that could be added to a utility.

Four properties carry more weight than the arithmetic.

**Every threshold is read from the profile.** There is not a single
numeric literal below that a deployment could disagree with: G1 reads
``no_path_rate_max``, G3 ``success_rate_min``, G4
``robot.control_period``, G5 ``hardware.available_ram_mb``, G6 the
declared observations, and G2's ``N_min`` derives from
``collision_probability_max`` by the rule of three. A constant here would
be a bar nobody set, which is the HĐ-15.3 violation the gates exist to
prevent.

**All six gates always run.** No short-circuit on the first failure:
HĐ-15.1 criterion 3 requires the card to print six gates with the number
of runs behind them, and "eliminated at G2" without knowing whether G4
also failed is a diagnosis nobody can act on.

**Zero collisions is a bound, not a certificate.** Observing no collision
in N runs bounds the probability by ~3/N at 95% — and only under the
scenario distribution actually simulated. G2 therefore refuses to pass on
zero collisions alone: it also demands ``N ≥ N_min``, and it emits the
sentence HĐ-7.1 mandates so the bound travels with the claim. The words
"an toàn" and "TCO" may never appear beside a number this system
produced (§17 ban 10); :func:`assert_no_banned_language` enforces that on
the rendered card, and a CI test runs it.

**Host screening only proves one direction.** The benchmark host is
faster than the target board and runs Python rather than C++/ROS2, so G4
and G5 are necessary conditions: failing here proves failure on the
target, passing proves nothing (HĐ-7.2, HĐ-7.3). The project has no
target board, so ``verified_on_target`` is not a value this module can
produce (§17 ban 12), and every G4 result carries
:data:`G4_HOST_ONLY_CAVEAT` verbatim.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from planbench_decision.candidate import ArtifactResourceProfile, Candidate
from planbench_decision.pairing import require_sample_set
from planbench_schemas.episode_context import EpisodeContext
from planbench_schemas.observations import ObservationToken
from planbench_schemas.task_profile import TaskProfile

if TYPE_CHECKING:  # pragma: no cover - import cycle, see below
    # ``planbench_metrics.definitions`` imports this package's candidate
    # module, so importing it at runtime would close a cycle whenever the
    # metrics module is the first one loaded. Only the type is needed
    # here — the gates read attributes off whatever the Metrics Engine
    # produced, and HĐ-6 keeps that shape in one place.
    from planbench_metrics.definitions import EpisodeMetricSet

__all__ = [
    "BANNED_PHRASES",
    "G4_HOST_ONLY_CAVEAT",
    "GATE_IDS",
    "BannedLanguageError",
    "G1Result",
    "G2Result",
    "G3Result",
    "G4Result",
    "G5Result",
    "G6Result",
    "GateInputError",
    "GateReport",
    "assert_no_banned_language",
    "evaluate_gates",
]

GateId = Literal["G1", "G2", "G3", "G4", "G5", "G6"]
GateVerdict = Literal["pass", "fail"]

#: Printed in this order on every card, whatever the outcome (HĐ-15.1).
GATE_IDS: tuple[GateId, ...] = ("G1", "G2", "G3", "G4", "G5", "G6")

#: HĐ-7.1: zero events in N trials bounds p by 3/N at ~95% confidence.
RULE_OF_THREE_NUMERATOR = 3.0

#: Sim-only reservation (HĐ-7.2): the project has no target board, so the
#: screening phase is the only phase, and the card says so in words.
RealtimeGateStatus = Literal["screened_on_host"]
G4_HOST_ONLY_CAVEAT = "G4 mới qua vòng sàng lọc — chưa xác nhận trên bo mạch đích"

#: HĐ-7.3. ``verified_on_target`` is absent on purpose: it would require a
#: measurement on hardware this project does not have (§17 ban 12).
MemoryGateStatus = Literal["estimated_from_structure", "declared_by_author"]

#: §17 ban 10. "an toàn" as a plain substring — "không an toàn" beside a
#: number is the same overclaim in the opposite direction, and both are
#: banned. "TCO" needs word boundaries so it cannot fire on a word that
#: merely contains those letters.
BANNED_PHRASES: tuple[str, ...] = ("an toàn", "TCO")
_BANNED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("an toàn", re.compile(r"an\s+toàn", re.IGNORECASE)),
    ("TCO", re.compile(r"\bTCO\b", re.IGNORECASE)),
)


class GateInputError(ValueError):
    """The episodes on hand cannot support a gate verdict.

    Raised rather than degraded into a failing gate: "this candidate was
    eliminated" and "we cannot tell whether it should be" are different
    statements, and a Decision Card that confuses them eliminates a
    candidate for a bookkeeping mistake.
    """


class BannedLanguageError(ValueError):
    """Text that would put a forbidden word beside a system number."""


def assert_no_banned_language(payload: object, *, where: str = "gate report") -> None:
    """Refuse "an toàn" / "TCO" anywhere in rendered output (§17 ban 10).

    Both words claim more than the evidence carries. Zero collisions in
    300 runs bounds the collision rate by 1% under *the distribution that
    was simulated*; calling the result "safe" turns a conditional bound
    into an unconditional property, and no reader recovers the condition
    afterwards. "TCO" does the same to a compute-cost proxy that never
    saw a price list.

    Walks strings, mappings and sequences so a card can be checked whole
    rather than field by field — the point is that no path through the
    renderer can leak the word.
    """
    if isinstance(payload, str):
        for phrase, pattern in _BANNED_PATTERNS:
            if pattern.search(payload):
                raise BannedLanguageError(
                    f"{where} contains the banned phrase {phrase!r} in {payload!r}. "
                    "§17 ban 10: this system's numbers are bounds under a simulated "
                    "distribution, and that word states an unconditional property "
                    "the evidence does not support"
                )
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert_no_banned_language(key, where=where)
            assert_no_banned_language(value, where=where)
        return
    if isinstance(payload, (list, tuple)):
        for item in payload:
            assert_no_banned_language(item, where=where)


class _GateResult(BaseModel):
    """Shared shape: a verdict plus the run count behind it."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    result: GateVerdict
    n_runs: int = Field(ge=1)

    @property
    def passed(self) -> bool:
        return self.result == "pass"


class G1Result(_GateResult):
    """``no_path_rate ≤ no_path_rate_max`` (constraints).

    Kept separate from G3 although both count failures: a planner that
    cannot find a route is failing at a different job than one whose
    route does not survive contact with traffic, and the fix for each
    lands on a different layer of the stack.
    """

    no_path_rate: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)


class G2Result(_GateResult):
    """Zero collisions on the whole evaluation set, **and** ``N ≥ N_min``.

    The second half is what makes the first half mean anything. Zero
    collisions in 10 runs is consistent with a 26% collision rate; the
    contract fixes the minimum N from the accepted risk rather than
    letting the run size decide what may be claimed (HĐ-7.1).

    ``upper_bound_95`` is ``None`` once a collision has been observed:
    the rule of three applies to zero-event data only, and quoting a
    bound anyway would be arithmetic dressed as evidence.
    """

    observed_collisions: int = Field(ge=0)
    n_min: int = Field(ge=1)
    upper_bound_95: float | None = None
    statement: str
    note: str | None = None


class G3Result(_GateResult):
    """``success_rate ≥ success_rate_min`` (constraints)."""

    success_rate: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)


class G4Result(_GateResult):
    """``p99_latency_ms ≤ control_period × 1000``, on the host only.

    ``p99_ms`` is the 99th percentile over **every control step of the
    evaluation set**, pooled — see
    :func:`~planbench_metrics.definitions.pooled_p99_latency_ms`, which
    is where it is computed and where the reasoning lives. It is
    deliberately neither the worst episode's p99 (which makes the gate a
    function of the unluckiest moment on the benchmark host) nor a mean
    of per-episode p99s (a percentile of percentiles is a statistic of
    nothing).

    No conversion factor to the target board exists here and none may be
    invented: A\\* is memory-bound and DWA is compute-bound, so they scale
    differently between x86 and ARM and a shared factor is a made-up
    number (HĐ-7.2, §17 ban 8).
    """

    status: RealtimeGateStatus = "screened_on_host"
    p99_ms: float = Field(ge=0.0)
    threshold_ms: float = Field(gt=0.0)
    caveat: str = G4_HOST_ONLY_CAVEAT


class G5Result(_GateResult):
    """``memory_estimate_mb ≤ available_ram_mb`` (HĐ-7.3).

    The estimate comes from data-structure counts times the *target*
    implementation's byte sizes, never from ``peak_rss_mb`` — the RSS of
    a Python process is wrong by an order of magnitude against a C++
    board budget, and in a direction that cannot be predicted (HĐ-6, §17
    ban 13). ``peak_rss_mb_diagnostic`` is carried alongside for leak
    hunting and relative comparison, deliberately named so it cannot be
    mistaken for the gate's own number.

    Passing is an elimination test that came out negative, not a
    certificate of fit: both statuses are screening phases, and with
    ``declared_by_author`` the figure was never measured at all
    (HĐ-7.3 law 2).
    """

    status: MemoryGateStatus
    memory_estimate_mb: float = Field(ge=0.0)
    available_ram_mb: float = Field(gt=0.0)
    peak_rss_mb_diagnostic: float = Field(ge=0.0)
    target_implementation: str | None = None
    bytes_per_search_node: int | None = None
    peak_search_nodes: int | None = None
    note: str


class G6Result(_GateResult):
    """``observation_requirements ⊆ available_observations``.

    A literal set comparison, which only works because the vocabulary is
    closed on both sides (HĐ-7.0): an unknown token fails at parse time,
    so a spelling difference can never reach this gate and be reported as
    a hardware incompatibility that does not exist.

    ``n_runs`` is carried for the card's uniform shape even though this
    gate needs no episode: a candidate can be excluded before a single
    run, and the number tells a reader which of the two happened.
    """

    required: tuple[ObservationToken, ...]
    available: tuple[ObservationToken, ...]
    missing: tuple[ObservationToken, ...]


class GateReport(BaseModel):
    """All six gate verdicts for one candidate, with their evidence.

    A candidate is feasible only if every gate passes. The report keeps
    the failing ones enumerable (:attr:`blocking_gates`) because "who was
    eliminated where, after how many runs" is the question the gate table
    exists to answer.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate_id: str
    task_profile_id: str
    n_runs: int = Field(ge=1)
    g1: G1Result
    g2: G2Result
    g3: G3Result
    g4: G4Result
    g5: G5Result
    g6: G6Result

    @property
    def results(self) -> dict[GateId, _GateResult]:
        return {
            "G1": self.g1,
            "G2": self.g2,
            "G3": self.g3,
            "G4": self.g4,
            "G5": self.g5,
            "G6": self.g6,
        }

    @property
    def passed(self) -> bool:
        """Feasible: every gate passed. No gate trades against another."""
        return all(result.passed for result in self.results.values())

    @property
    def blocking_gates(self) -> tuple[GateId, ...]:
        """Which gates eliminated this candidate, in contract order."""
        return tuple(gate for gate in GATE_IDS if not self.results[gate].passed)

    def to_card(self) -> dict[str, Any]:
        """The ``gates`` entry of a Decision Card, in HĐ-12's shape.

        G1, G3 and G6 render as bare verdict strings and the other three
        as blocks, exactly as the contract writes them — a card is a
        summary that has to be diffable against the contract by eye. The
        full evidence stays on this object, which is what the gate table
        in the UI reads.

        Checked for banned language on the way out rather than trusting
        every future caller to remember (§17 ban 10).
        """
        card: dict[str, Any] = {
            "candidate_id": self.candidate_id,
            "G1": self.g1.result,
            "G2": {
                "result": self.g2.result,
                "observed": self.g2.observed_collisions,
                "n_runs": self.g2.n_runs,
                "upper_bound_95": self.g2.upper_bound_95,
                "n_min": self.g2.n_min,
                "statement": self.g2.statement,
                "note": self.g2.note,
            },
            "G3": self.g3.result,
            "G4": {
                "result": self.g4.result,
                "status": self.g4.status,
                "p99_ms": self.g4.p99_ms,
                "threshold_ms": self.g4.threshold_ms,
                "caveat": self.g4.caveat,
            },
            "G5": {
                "result": self.g5.result,
                "status": self.g5.status,
                "memory_estimate_mb": self.g5.memory_estimate_mb,
                "available_ram_mb": self.g5.available_ram_mb,
                "peak_rss_mb_diagnostic": self.g5.peak_rss_mb_diagnostic,
                "note": self.g5.note,
            },
            "G6": self.g6.result,
        }
        if self.g5.target_implementation is not None:
            card["G5"]["target_implementation"] = self.g5.target_implementation
            card["G5"]["bytes_per_search_node"] = self.g5.bytes_per_search_node
            card["G5"]["peak_search_nodes"] = self.g5.peak_search_nodes
        assert_no_banned_language(card, where=f"gate card for {self.candidate_id}")
        return card


def evaluate_gates(
    candidate: Candidate,
    profile: TaskProfile,
    metrics: Sequence[EpisodeMetricSet],
    contexts: Sequence[EpisodeContext],
    *,
    pooled_p99_latency_ms: float,
) -> GateReport:
    """Run G1–G6 for one candidate over its evaluation episodes.

    ``pooled_p99_latency_ms`` is G4's measurement and arrives already
    computed, from
    :func:`~planbench_metrics.definitions.pooled_p99_latency_ms`. Gates
    compare against thresholds; defining a metric is the Metrics Engine's
    job and HĐ-15.3 keeps it to one module. The pooled percentile also
    cannot be reconstructed from :class:`EpisodeMetricSet`, which carries
    one p99 per episode — pooling those would be a percentile of
    percentiles.

    ``contexts`` is required, and required to be the ``evaluation`` set,
    because G2's bound assumes independent draws. Neighborhood episodes
    are clustered by variant, so pooling them would inflate N without
    adding independent evidence and make ``3/N`` look better than the
    data supports — the one direction of error a collision claim must
    never take (HĐ-3.3, HĐ-11.4). The check is here rather than left to
    the caller because by the time the bound is on a card, the mistake is
    invisible.

    Raises :class:`GateInputError` when the episodes cannot answer the
    question at all; a failing gate is reserved for candidates that were
    actually measured and fell short.
    """
    _require_consistent_inputs(candidate, profile, metrics, contexts)
    require_sample_set(contexts, "evaluation")

    n_runs = len(metrics)
    return GateReport(
        candidate_id=candidate.candidate_id,
        task_profile_id=profile.id,
        n_runs=n_runs,
        g1=_gate_1(profile, metrics),
        g2=_gate_2(profile, metrics),
        g3=_gate_3(profile, metrics),
        g4=_gate_4(profile, metrics, pooled_p99_latency_ms),
        g5=_gate_5(candidate, profile, metrics),
        g6=_gate_6(candidate, profile, n_runs),
    )


def _require_consistent_inputs(
    candidate: Candidate,
    profile: TaskProfile,
    metrics: Sequence[EpisodeMetricSet],
    contexts: Sequence[EpisodeContext],
) -> None:
    """The rows must describe this candidate on this profile, once each.

    Every check below is a way of quietly scoring the wrong thing: rows
    from two candidates pooled into one verdict, one episode counted
    twice inflating N behind the collision bound, or a context set that
    belongs to a different deployment than the thresholds being applied.
    """
    if not metrics:
        raise GateInputError(
            f"candidate {candidate.candidate_id} has no episodes; gates report what was "
            "measured, and nothing was"
        )

    foreign = sorted({m.candidate_id for m in metrics if m.candidate_id != candidate.candidate_id})
    if foreign:
        raise GateInputError(
            f"metrics for candidate(s) {foreign} were passed alongside "
            f"{candidate.candidate_id}; a gate verdict pooled across candidates belongs to "
            "neither of them"
        )

    metric_ids = [m.episode_context_id for m in metrics]
    duplicates = sorted({i for i in metric_ids if metric_ids.count(i) > 1})
    if duplicates:
        raise GateInputError(
            f"episode context(s) {duplicates} appear more than once for candidate "
            f"{candidate.candidate_id}; repeated conditions would inflate N behind G2's "
            "collision bound without adding independent evidence"
        )

    context_ids = {context.episode_context_id for context in contexts}
    if context_ids != set(metric_ids):
        missing = sorted(context_ids - set(metric_ids))
        extra = sorted(set(metric_ids) - context_ids)
        raise GateInputError(
            f"episode metrics and contexts do not describe the same run: {len(missing)} "
            f"context(s) have no metrics (e.g. {missing[:3]}), {len(extra)} metric(s) have "
            f"no context (e.g. {extra[:3]})"
        )
    if len(contexts) != len(metrics):
        raise GateInputError(
            f"got {len(contexts)} contexts for {len(metrics)} episodes; N is the number "
            "of independent runs, and the two lists disagree about what it is"
        )

    wrong_profile = sorted({c.task_profile_id for c in contexts if c.task_profile_id != profile.id})
    if wrong_profile:
        raise GateInputError(
            f"episodes ran under task profile(s) {wrong_profile} but are being gated against "
            f"{profile.id!r}; every threshold below comes from the profile, so the verdict "
            "would apply one deployment's limits to another's runs"
        )


def _gate_1(profile: TaskProfile, metrics: Sequence[EpisodeMetricSet]) -> G1Result:
    threshold = profile.constraints.no_path_rate_max
    no_path = sum(1 for m in metrics if m.failure_reason == "no_path")
    rate = no_path / len(metrics)
    return G1Result(
        result="pass" if rate <= threshold else "fail",
        n_runs=len(metrics),
        no_path_rate=rate,
        threshold=threshold,
    )


def _gate_2(profile: TaskProfile, metrics: Sequence[EpisodeMetricSet]) -> G2Result:
    """Zero collisions and enough runs, with the mandated sentence.

    The sentence is a contract artefact, not a log line: it is what stops
    "0 collisions" from being read as "no collisions happen". It names
    the run count and the bound, and it names the distribution the bound
    is conditional on.
    """
    n_runs = len(metrics)
    n_min = profile.constraints.n_min_evaluation_episodes
    observed = sum(m.collision_count for m in metrics)
    enough_runs = n_runs >= n_min
    clean = observed == 0

    if clean:
        bound = RULE_OF_THREE_NUMERATOR / n_runs
        statement = (
            f"0 va chạm quan sát trong {n_runs} lần chạy; cận trên 95% dưới phân phối "
            f"kịch bản đã mô phỏng: {bound:.1%}"
        )
    else:
        bound = None
        statement = (
            f"{observed} va chạm quan sát trong {n_runs} lần chạy; quy tắc số ba chỉ áp "
            "dụng cho dữ liệu không có sự kiện, nên không có cận trên nào được nêu ở đây"
        )

    note: str | None = "dưới phân phối kịch bản đã mô phỏng" if clean else None
    if clean and not enough_runs:
        note = (
            f"chỉ {n_runs} lần chạy, dưới N_min = {n_min} = ceil(3 / "
            f"{profile.constraints.collision_probability_max}); cận trên "
            f"{RULE_OF_THREE_NUMERATOR / n_runs:.1%} còn lỏng hơn mức rủi ro đã khai"
        )

    return G2Result(
        result="pass" if clean and enough_runs else "fail",
        n_runs=n_runs,
        observed_collisions=observed,
        n_min=n_min,
        upper_bound_95=bound,
        statement=statement,
        note=note,
    )


def _gate_3(profile: TaskProfile, metrics: Sequence[EpisodeMetricSet]) -> G3Result:
    threshold = profile.constraints.success_rate_min
    rate = sum(1 for m in metrics if m.success) / len(metrics)
    return G3Result(
        result="pass" if rate >= threshold else "fail",
        n_runs=len(metrics),
        success_rate=rate,
        threshold=threshold,
    )


def _gate_4(
    profile: TaskProfile, metrics: Sequence[EpisodeMetricSet], pooled_p99_ms: float
) -> G4Result:
    threshold_ms = profile.robot.t_cycle_ms
    return G4Result(
        result="pass" if pooled_p99_ms <= threshold_ms else "fail",
        n_runs=len(metrics),
        p99_ms=pooled_p99_ms,
        threshold_ms=threshold_ms,
    )


#: What a G5 pass may and may not be read as, per status (HĐ-7.3).
_G5_NOTES: dict[str, str] = {
    "estimated_from_structure": (
        "ước lượng từ bộ đếm cấu trúc dữ liệu nhân kích thước byte của hiện thực đích; "
        "pha sàng lọc là điều kiện cần — vượt ngân sách thì chắc chắn không vừa, "
        "không vượt thì chưa kết luận được điều ngược lại"
    ),
    "declared_by_author": (
        "số do tác giả candidate khai lúc đăng ký, không phải một phép đo; theo HĐ-7.3 "
        "luật 2, kết quả G5 ở đây chỉ có giá trị loại bỏ, không bao giờ chứng nhận vừa "
        "bộ nhớ"
    ),
}


def _gate_5(
    candidate: Candidate, profile: TaskProfile, metrics: Sequence[EpisodeMetricSet]
) -> G5Result:
    """Worst-case memory estimate against the board's navigation budget.

    The worst episode decides here, unlike G4, and the difference is not
    an inconsistency. ``memory_estimate_mb`` is counted, not timed: it is
    data-structure counts multiplied by declared byte sizes, so it has no
    measurement noise for an outlier to come from, and an episode that
    genuinely needed more memory than the board has is a real
    disqualification. G4's input is a wall-clock measurement on a shared
    host, where the largest value in the set is frequently the operating
    system rather than the candidate.
    """
    resource_profile = candidate.resource_profile
    artifact = resource_profile if isinstance(resource_profile, ArtifactResourceProfile) else None
    if artifact is not None and artifact.source == "measured_on_target":
        raise GateInputError(
            f"candidate {candidate.candidate_id} declares resource_profile.source="
            "'measured_on_target', but this project has no target board (HĐ-7.2/7.3 "
            "reservation), so no such measurement exists to report. Lift the reservation "
            "and bump contracts_version MINOR before using it"
        )

    missing = [m.episode_context_id for m in metrics if m.memory_estimate_mb is None]
    if missing:
        raise GateInputError(
            f"{len(missing)} episode(s) of candidate {candidate.candidate_id} carry no "
            f"memory_estimate_mb (e.g. {missing[:3]}); recompute the metrics with the "
            "candidate's resource_profile. G5 will not fall back to peak_rss_mb, which "
            "measures a Python process rather than the target implementation (§17 ban 13)"
        )

    estimate = max(m.memory_estimate_mb for m in metrics if m.memory_estimate_mb is not None)
    budget = profile.hardware.available_ram_mb
    # The structural provenance fields (which byte sizes, which counts)
    # only exist for a counted estimate. A declared artifact figure has
    # no such trail, and inventing one would let the card imply a
    # measurement that never happened.
    if isinstance(resource_profile, ArtifactResourceProfile):
        status: MemoryGateStatus = "declared_by_author"
        target_implementation: str | None = None
        bytes_per_search_node: int | None = None
        peak_search_nodes: int | None = None
    else:
        status = "estimated_from_structure"
        target_implementation = resource_profile.target_implementation
        bytes_per_search_node = resource_profile.bytes_per_search_node
        peak_search_nodes = max(m.peak_search_nodes for m in metrics)

    return G5Result(
        result="pass" if estimate <= budget else "fail",
        n_runs=len(metrics),
        status=status,
        memory_estimate_mb=estimate,
        available_ram_mb=budget,
        peak_rss_mb_diagnostic=max(m.peak_rss_mb for m in metrics),
        target_implementation=target_implementation,
        bytes_per_search_node=bytes_per_search_node,
        peak_search_nodes=peak_search_nodes,
        note=_G5_NOTES[status],
    )


def _gate_6(candidate: Candidate, profile: TaskProfile, n_runs: int) -> G6Result:
    required = tuple(candidate.observation_requirements)
    available = tuple(profile.available_observations)
    missing = tuple(token for token in required if token not in set(available))
    return G6Result(
        result="pass" if not missing else "fail",
        n_runs=n_runs,
        required=required,
        available=available,
        missing=missing,
    )
