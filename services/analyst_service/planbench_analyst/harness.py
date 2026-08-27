"""What a round cost, what it got wrong, and whether it beat the floor.

The order of this module is the order of the work, and it is deliberately
not the order somebody reaching for a metric would choose.

**Failures are counted before metrics are read.** :func:`failure_table`
takes the rounds and returns a frequency table — which guard rule fired,
which host code refused a request, how each round ended. A bar chosen
before anybody has looked at what actually goes wrong measures the thing
that was easy to measure. The six preregistered targets are still the
bar; this is what says which of them is worth working on.

**A round run once measures nothing about reliability.**
:func:`pass_hat_k` runs the same case k times and asks whether it held
every time. ``pass@k`` — did it work at least once — is the number that
goes in a demo; ``pass^k`` is the number a deployment lives with, and an
analyst that is right 90% of the time is right 73% of the time three
times running.

**The floor is a paired comparison, not two averages.** The model-free
:func:`~planbench_explanation.integration.reference_analyst` runs on the
*same* packets, and :func:`mcnemar_exact` reads only the cases where the
two disagreed. Two means over one set hide which cases moved; and below
about six discordant cases no p-value can reach 0.05, so the honest
answer there is "not enough data" rather than a number.

**Cost is an axis, not a footnote.** Tokens and tool calls per case sit
beside the quality numbers, because "better and four times the price" is
a different answer from "better", and only one of them is a deployment.

**What this module will not do on real packets.** The thirteen packets
production has produced carry no planted answer, so precision and recall
are not computable from them and are not reported. What is: did it
crash, did it abstain where there was nothing to find, what did it ask
for, what did the host refuse, and did it beat the floor.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from math import comb

from planbench_agent.provider import LLMProvider
from planbench_analyst.cache import ResponseCache
from planbench_analyst.eval_spec import EvalSpec
from planbench_analyst.guard import guard
from planbench_analyst.packet_view import build_packet_view
from planbench_analyst.round_host import PreparedRound
from planbench_analyst.runner import RoundOutcome, run_round
from planbench_explanation.integration import reference_analyst
from planbench_explanation.protocol import AnalysisResponse

__all__ = [
    "branch_matrix",
    "cost_by_class",
    "CaseResult",
    "FloorComparison",
    "HarnessReport",
    "compare_with_floor",
    "failure_table",
    "mcnemar_exact",
    "pass_hat_k",
    "quality_pass_hat_k",
    "routing_failures",
    "wilson_interval",
]

#: Host rejection codes read as the tool-routing mistake they are. The
#: platform already counts refusals by code; this names what each one
#: means about the analyst rather than about the platform, so a table of
#: twenty-two codes becomes four things somebody can act on.
ROUTING_FAILURE: dict[str, str] = {
    "unknown_tool": "wrong_tool",
    "tool_mismatch": "wrong_tool",
    "arguments_rejected": "wrong_arg_value",
    "measurements_rejected": "wrong_arg_value",
    "missing_required_evidence": "unnecessary_tool",
    "execution_not_authorized": "unnecessary_tool",
    "proposition_not_supported": "wrong_tool",
    "unknown_hypothesis": "wrong_boundary",
    "sequence_out_of_order": "wrong_boundary",
    "duplicate_request_id": "wrong_boundary",
    "request_budget_exhausted": "unnecessary_tool",
}


@dataclass(frozen=True)
class CaseResult:
    """One case, run once. The unit everything below aggregates."""

    case_id: str
    outcome: RoundOutcome
    #: What the model-free floor said about the same packet. Kept beside
    #: the model's answer rather than in a second table: the comparison
    #: is paired, and a pairing carried by list position is a pairing one
    #: sort away from being wrong.
    floor: AnalysisResponse

    @property
    def abstained(self) -> bool:
        return self.outcome.response.abstained

    @property
    def floor_abstained(self) -> bool:
        return self.floor.abstained

    @property
    def crashed(self) -> bool:
        return self.outcome.stopped_because == "model_failed"

    @property
    def proposals(self) -> int:
        return len(self.outcome.response.proposals)


def failure_table(results: Sequence[CaseResult]) -> dict[str, int]:
    """What went wrong, by kind, before anybody reads a target.

    Guard rules, host refusals and endings in one table because they are
    one question — *what is this analyst doing wrong* — and three tables
    would be three things nobody cross-references.
    """
    counts: dict[str, int] = {}
    for result in results:
        counts[f"ended:{result.outcome.stopped_because}"] = (
            counts.get(f"ended:{result.outcome.stopped_because}", 0) + 1
        )
        for blocked in result.outcome.guard.blocked:
            key = f"guard:{blocked.rule}"
            counts[key] = counts.get(key, 0) + 1
        for code in result.outcome.rejections:
            counts[f"host:{code}"] = counts.get(f"host:{code}", 0) + 1
    return dict(sorted(counts.items()))


def routing_failures(results: Sequence[CaseResult]) -> dict[str, int]:
    """Host refusals, read as tool-routing mistakes.

    ``checker_selection`` is one number for a skill with four distinct
    ways of going wrong; asking for a tool that cannot answer the
    question and asking the right tool with the wrong argument need
    different fixes.
    """
    counts: dict[str, int] = {}
    for result in results:
        for code in result.outcome.rejections:
            kind = ROUTING_FAILURE.get(code, "other")
            counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))


def pass_hat_k(runs: Sequence[Sequence[bool]]) -> float:
    """Share of cases that held on **every** repeat.

    ``runs[i]`` is one case's k outcomes. Not ``pass@k``: "it worked
    once out of eight" is a demo, and the number a deployment lives with
    is the one that goes down as k rises.
    """
    if not runs:
        return 0.0
    return sum(1 for case in runs if case and all(case)) / len(runs)


def wilson_interval(successes: int, trials: int, *, z: float = 1.96) -> tuple[float, float]:
    """A confidence interval that behaves near 0 and 1 on small n.

    Reported beside every ``pass^k`` because three to five repeats on a
    handful of cases is a coarse estimate, and a bare rate reads as more
    precise than it is. Wilson rather than Wald: Wald collapses to a
    zero-width interval at 0/n and n/n, which is exactly where small
    evaluations land.
    """
    if trials <= 0:
        return (0.0, 0.0)
    rate = successes / trials
    denominator = 1 + z * z / trials
    centre = (rate + z * z / (2 * trials)) / denominator
    half = z * ((rate * (1 - rate) / trials + z * z / (4 * trials * trials)) ** 0.5)
    half /= denominator
    return (max(0.0, centre - half), min(1.0, centre + half))


def quality_pass_hat_k(
    runs: Sequence[Sequence[bool]], *, min_cases: int
) -> tuple[float | None, tuple[int, int], tuple[float, float]]:
    """``pass^k`` where pass means *met the quality bar*, not *did not crash*.

    Returns ``(rate, (held, cases), wilson_ci)``. The rate is ``None``
    below ``min_cases``: on three cases one flip is thirty-three points,
    and a number that coarse should not travel as a number — the counts
    do, and the reader sees them.
    """
    held = sum(1 for case in runs if case and all(case))
    cases = len(runs)
    interval = wilson_interval(held, cases)
    if cases < min_cases:
        return (None, (held, cases), interval)
    return (held / cases, (held, cases), interval)


def mcnemar_exact(only_first: int, only_second: int) -> float:
    """Two-sided exact p over the discordant pairs. No dependencies.

    Concordant cases carry no information about which system is better —
    both got it right, or both got it wrong — so only the disagreements
    are counted. Below about six discordant pairs the smallest reachable
    p is above 0.05, which is worth knowing *before* running the
    comparison rather than after reading a number from it.
    """
    total = only_first + only_second
    if total == 0:
        return 1.0
    smaller = min(only_first, only_second)
    tail = sum(comb(total, index) for index in range(smaller + 1)) / (2**total)
    return min(1.0, 2 * tail)


@dataclass(frozen=True)
class FloorComparison:
    """The model against the model-free floor, case by case."""

    cases: tuple[CaseResult, ...]
    #: Cases where the model proposed something and the floor abstained.
    model_only: int = 0
    #: Cases where the floor proposed something and the model abstained.
    floor_only: int = 0

    @property
    def p_value(self) -> float:
        return mcnemar_exact(self.model_only, self.floor_only)

    @property
    def discordant(self) -> int:
        return self.model_only + self.floor_only

    @property
    def underpowered(self) -> bool:
        """Whether the comparison could reach significance at all.

        Reported rather than left implicit: a p of 0.25 on three
        discordant cases is not weak evidence of no difference, it is no
        evidence either way.
        """
        return mcnemar_exact(self.discordant, 0) > 0.05


@dataclass
class HarnessReport:
    """Everything one harness run measured, and what it may not claim."""

    cases: tuple[CaseResult, ...] = ()
    repeats: int = 1
    reliability: float = 1.0
    comparison: FloorComparison | None = None
    #: Stated on the report itself rather than in a docstring somebody
    #: reads once: these packets carry no planted answer, so precision
    #: and recall are not computable and are not here.
    caveats: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)
    #: Reads served from a response cache during this run. A measured
    #: run must report zero: reading the same answer twice says nothing
    #: about whether the model would say it twice.
    cache_hits: int = 0

    @property
    def measured_independently(self) -> bool:
        return self.cache_hits == 0

    @property
    def crashes(self) -> int:
        return sum(1 for case in self.cases if case.crashed)

    @property
    def total_input_tokens(self) -> int:
        return sum(case.outcome.cost.input_tokens for case in self.cases)

    @property
    def total_output_tokens(self) -> int:
        return sum(case.outcome.cost.output_tokens for case in self.cases)

    @property
    def tool_requests(self) -> int:
        return sum(case.outcome.cost.tool_requests for case in self.cases)

    @property
    def median_cost(self) -> tuple[int, int]:
        """Median input and output tokens per case. Median, not mean: one
        runaway case should not set the number somebody budgets against."""
        if not self.cases:
            return (0, 0)
        ins = sorted(case.outcome.cost.input_tokens for case in self.cases)
        outs = sorted(case.outcome.cost.output_tokens for case in self.cases)
        middle = len(ins) // 2
        return (ins[middle], outs[middle])

    def summary(self) -> dict[str, object]:
        """The table a report prints. Every caveat travels with it."""
        return {
            "cases": len(self.cases),
            "repeats": self.repeats,
            "crashes": self.crashes,
            "abstentions": sum(1 for case in self.cases if case.abstained),
            "floor_abstentions": sum(1 for case in self.cases if case.floor_abstained),
            "reliability_pass_hat_k": round(self.reliability, 3),
            "median_input_tokens": self.median_cost[0],
            "median_output_tokens": self.median_cost[1],
            "tool_requests": self.tool_requests,
            "failures": failure_table(self.cases),
            "routing_failures": routing_failures(self.cases),
            "floor_discordant": self.comparison.discordant if self.comparison else 0,
            "floor_p_value": round(self.comparison.p_value, 4) if self.comparison else None,
            "floor_underpowered": self.comparison.underpowered if self.comparison else None,
            "cache_hits": self.cache_hits,
            "measured_independently": self.measured_independently,
            "caveats": list(self.caveats),
        }


#: What a caller is told about a run over production packets. Written
#: here so it cannot be left out of a report by forgetting to write it.
REAL_PACKET_CAVEATS: tuple[str, ...] = (
    "these packets carry no planted answer: precision, recall@3 and "
    "component-attribution are not computable from them and are not reported",
    "an abstention is only checkable where the packet holds no detection at all",
)

PreparedFor = Callable[[str], PreparedRound]


def compare_with_floor(
    case_ids: Sequence[str],
    prepared_for: PreparedFor,
    provider: LLMProvider,
    *,
    repeats: int = 1,
    caveats: Sequence[str] = REAL_PACKET_CAVEATS,
    cache: ResponseCache | None = None,
) -> HarnessReport:
    """Run the model and the floor over the same packets, and report both.

    ``prepared_for`` builds a fresh :class:`PreparedRound` per call —
    fresh because a host carries the session, and reusing one across
    repeats would let the second run inherit the first's declarations.
    """
    results: list[CaseResult] = []
    holds: list[list[bool]] = []
    model_only = 0
    floor_only = 0

    for case_id in case_ids:
        repeats_held: list[bool] = []
        first: CaseResult | None = None
        for _ in range(max(1, repeats)):
            prepared = prepared_for(case_id)
            outcome = run_round(prepared, provider)
            view = build_packet_view(
                prepared.analysis.packet,
                tool_catalog_version=prepared.analysis.catalog.catalog_version,
            )
            # The floor is guarded too. Comparing a guarded model against
            # an unguarded floor would credit the model for drops the
            # floor never had to survive.
            floor = guard(
                reference_analyst(prepared.analysis),
                view,
                catalog=prepared.analysis.catalog,
            ).response
            result = CaseResult(case_id=case_id, outcome=outcome, floor=floor)
            repeats_held.append(not result.crashed)
            if first is None:
                first = result
        assert first is not None
        results.append(first)
        holds.append(repeats_held)
        if not first.abstained and first.floor_abstained:
            model_only += 1
        elif first.abstained and not first.floor_abstained:
            floor_only += 1

    comparison = FloorComparison(cases=tuple(results), model_only=model_only, floor_only=floor_only)
    hits = cache.stats.hits if cache is not None else 0
    if hits:
        # Not a caveat — a refusal. A report with cache hits in it is
        # not a measurement of the model, and it must not be able to
        # leave this function looking like one.
        raise RuntimeError(
            f"{hits} response(s) were served from cache during a measured run; every "
            "repeat has to be an independent model call"
        )
    return HarnessReport(
        cases=tuple(results),
        repeats=max(1, repeats),
        reliability=pass_hat_k(holds),
        comparison=comparison,
        caveats=tuple(caveats),
        cache_hits=hits,
    )


def cost_by_class(
    results: Sequence[CaseResult], spec: EvalSpec
) -> dict[str, dict[str, float | int]]:
    """Median tokens and model calls per **fixture class** — W4.6.

    The class is ``expected_check_required``, which the label file fixed
    before anything ran. Reporting cost by the branch the *model* chose
    instead would be post-treatment: the branch is an outcome, and
    comparing the check-plan cases against a baseline subset picked
    after seeing which cases the model sent down that branch compares
    two different populations and calls the difference a cost.

    The branch is still reported, in :func:`branch_matrix`, and only as
    a diagnostic.
    """
    by_class: dict[str, list[CaseResult]] = {"check_required": [], "no_check_required": []}
    for name, case_ids in spec.strata.items():
        for result in results:
            if result.case_id in case_ids:
                by_class.setdefault(name, []).append(result)
    summary: dict[str, dict[str, float | int]] = {}
    for name, rows in by_class.items():
        tokens = sorted(
            row.outcome.cost.input_tokens + row.outcome.cost.output_tokens for row in rows
        )
        calls = sorted(row.outcome.cost.model_calls for row in rows)
        summary[name] = {
            "cases": len(rows),
            "median_tokens": _median(tokens),
            "median_model_calls": _median(calls),
        }
    return summary


def branch_matrix(results: Sequence[CaseResult], spec: EvalSpec) -> dict[str, dict[str, int]]:
    """Fixture class against the branch the model actually took.

    Diagnostic only. What it answers is "does the model send the cases
    that need a checker down the check branch" — which is worth seeing
    and is not a cost comparison, because the branch is the model's
    decision and the class is not.
    """
    matrix: dict[str, dict[str, int]] = {
        name: {"check": 0, "no_check": 0} for name in ("check_required", "no_check_required")
    }
    for name, case_ids in spec.strata.items():
        for result in results:
            if result.case_id not in case_ids:
                continue
            asked = any(proposal.requested_checks for proposal in result.outcome.response.proposals)
            matrix.setdefault(name, {"check": 0, "no_check": 0})[
                "check" if asked else "no_check"
            ] += 1
    return matrix


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (float(ordered[middle - 1]) + float(ordered[middle])) / 2.0
