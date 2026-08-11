"""The measuring chain, once (plan M3).

    contexts + candidates -> episodes -> traces -> HĐ-6 metrics
                          -> gates -> objectives -> paired comparison

Three entry points now drive this: ``scripts/vertical_slice.py`` (the
HĐ-15 acceptance record), ``scripts/measure.py`` (one candidate, no
comparison) and ``scripts/compare.py`` (any candidate set). They differ
only in what they *do with* the result — which artifact they write, and
what they refuse to say. The chain itself must be the same code, or the
three will drift and nobody will be able to say whether a difference
between two runs came from the candidates or from which script was used.

**Why the slice was not simply made general.** ``vertical_slice.py`` is
an acceptance record: HĐ-15.1 gives it six criteria and HĐ-15.2 freezes
the methodology behind it. A script that grows options as needs arrive
stops being a record of anything. So the chain moved here and the slice
became a thin caller of it, with its behaviour unchanged — the test that
proves that is ``tests/test_vertical_slice.py``, which passes without a
line edited.

**Gates before scoring, and it is not a style choice.** HĐ-7 puts the
gates first so a candidate that fails one is never scored, never ranked,
and therefore cannot win by being fast. :func:`gate_all` and
:func:`score_survivors` are separate functions for the same reason: the
second physically cannot see a candidate the first rejected.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from planbench_benchmark.contexts import episode_total, iter_run_plan
from planbench_benchmark.episode import run_contract_episode
from planbench_decision.anchors import load_anchors
from planbench_decision.candidate import Candidate
from planbench_decision.gates import GateReport, evaluate_gates
from planbench_decision.objectives import DecisionSettings
from planbench_decision.stats import (
    CandidateEvidence,
    Recommendation,
    build_evidence,
    recommend,
)
from planbench_metrics.definitions import (
    EpisodeMetricSet,
    compute_metrics,
    pooled_p99_latency_ms,
)
from planbench_schemas.episode_context import EpisodeContext
from planbench_schemas.map import MapData
from planbench_schemas.task_profile import TaskProfile
from planbench_simulator.trace import read_trace, trace_path

__all__ = [
    "AcceptanceFailure",
    "check_delta_u",
    "check_gate_table",
    "check_l_ref",
    "check_node_counts",
    "check_reproducible",
    "check_shared_contexts",
    "decide",
    "gate_all",
    "score",
    "score_survivors",
    "simulate",
]

#: What a caller passes to receive progress lines. Printing lives with
#: the caller so this module stays usable from a test or a worker.
Say = Callable[[str], None]


def _silent(_message: str) -> None:
    return None


class AcceptanceFailure(AssertionError):
    """An acceptance criterion did not hold.

    One exception for all three entry points. The scripts alias it under
    their own names (``SliceFailure``, ``MeasurementFailure``) because the
    criteria they answer to are numbered differently — HĐ-15.1 for the
    slice, plan F1 for the measurement — but a failure is the same event
    and callers should not have to catch two types to survive it.
    """


def simulate(
    candidates: Sequence[Candidate],
    profile: TaskProfile,
    contexts: Sequence[EpisodeContext],
    map_data: MapData,
    trace_root: Path,
    *,
    reuse: bool,
    say: Say | None = None,
) -> None:
    """Run every (candidate, context) pair that has no trace yet.

    **Context outermost, candidate innermost** — HĐ-3.2's order, via
    :func:`iter_run_plan`, which exists to provide exactly this. Two
    reasons, and the second only became visible at 300 episodes:

    Interruption. Stop a candidate-outer sweep halfway and the first
    candidate has every episode while the last has none: nothing is
    comparable and the partial data is worthless. Stop a context-outer
    sweep halfway and every candidate has the same episodes, so the
    comparison is still valid, just smaller. Over a three-hour run that
    stops being a hypothetical.

    Machine drift. Candidate-outer puts one candidate in the first half
    of the wall clock and the other in the second, so any thermal
    throttling, background process or change of machine state lands
    entirely on one of them. HĐ-7.4 requires every candidate to run under
    the same conditions, and over ten minutes the difference was
    invisible; over three hours it is the mechanism that already
    eliminated A\\* at G4 once (contract 3.0.0). Interleaving makes every
    candidate share whatever the machine was doing, minute by minute.

    Reuse is keyed on the file existing, which is safe because the path
    is derived from the candidate id and the context id — both hashes of
    everything that could change the episode. A stale file is therefore
    a file for a configuration that no longer exists, and it simply never
    gets looked up.
    """
    emit = say or print
    total = episode_total(contexts, candidates)
    for index, (context, candidate) in enumerate(iter_run_plan(contexts, candidates), start=1):
        path = trace_path(candidate.candidate_id, context.episode_context_id, root=trace_root)
        if reuse and path.is_file():
            continue
        started = time.time()
        _, run = run_contract_episode(candidate, profile, context, map_data, root=trace_root)
        emit(
            f"  {index:>4}/{total}  {candidate.stack_label:<14} "
            f"seed {context.seed:<4} {run.result.status.value:<16} "
            f"{time.time() - started:5.1f}s"
        )


def score(
    candidate: Candidate,
    profile: TaskProfile,
    contexts: Sequence[EpisodeContext],
    map_data: MapData,
    trace_root: Path,
) -> tuple[list[EpisodeMetricSet], float]:
    """Recompute every HĐ-6 metric for one candidate, from the files only.

    Reading the traces back rather than keeping what the simulation had
    in memory is the point of HĐ-5, not ceremony: it is what proves a
    stored run can still be re-analysed after the process that produced
    it is gone.

    Returns the per-episode metrics and G4's pooled latency percentile.
    The second value cannot be recovered from the first — pooling needs
    every control step, and an ``EpisodeMetricSet`` carries one
    percentile per episode — so it is computed here, where the traces are
    open, rather than by re-reading them later.
    """
    traces = [
        read_trace(trace_path(candidate.candidate_id, context.episode_context_id, root=trace_root))
        for context in contexts
    ]
    metrics = [
        compute_metrics(
            trace,
            profile,
            context,
            map_data,
            resource_profile=candidate.resource_profile,
        )
        for trace, context in zip(traces, contexts, strict=True)
    ]
    return metrics, pooled_p99_latency_ms(traces)


def gate_all(
    candidates: Sequence[Candidate],
    metrics_by_candidate: dict[str, list[EpisodeMetricSet]],
    pooled_latency_by_candidate: dict[str, float],
    profile: TaskProfile,
    contexts: Sequence[EpisodeContext],
) -> dict[str, GateReport]:
    """G1–G6 for every candidate, before anything is scored."""
    return {
        candidate.candidate_id: evaluate_gates(
            candidate,
            profile,
            metrics_by_candidate[candidate.candidate_id],
            contexts,
            pooled_p99_latency_ms=pooled_latency_by_candidate[candidate.candidate_id],
        )
        for candidate in candidates
    }


def score_survivors(
    candidates: Sequence[Candidate],
    gate_reports: dict[str, GateReport],
    metrics_by_candidate: dict[str, list[EpisodeMetricSet]],
    profile: TaskProfile,
    contexts: Sequence[EpisodeContext],
    settings: DecisionSettings,
) -> list[CandidateEvidence]:
    """Objectives for the candidates that cleared every gate.

    A candidate that failed a gate is not a worse choice, it is not a
    choice — so it is not scored at all rather than scored and ranked
    last. That is what stops "fastest" from ever competing with "did not
    collide" (HĐ-7).
    """
    anchors = load_anchors().resolve(profile)
    return [
        build_evidence(
            candidate,
            metrics_by_candidate[candidate.candidate_id],
            contexts,
            anchors,
            settings,
        )
        for candidate in candidates
        if gate_reports[candidate.candidate_id].passed
    ]


def decide(
    candidates: Sequence[Candidate],
    metrics_by_candidate: dict[str, list[EpisodeMetricSet]],
    pooled_latency_by_candidate: dict[str, float],
    profile: TaskProfile,
    contexts: Sequence[EpisodeContext],
    settings: DecisionSettings,
    seed: int,
) -> tuple[dict[str, GateReport], list[CandidateEvidence], Recommendation]:
    """Gates, then objectives, then the paired comparison — in that order.

    Raises when fewer than two candidates survive: a recommendation needs
    something to recommend *over*. Callers that must survive that case —
    ``compare.py``, which reports the gate table instead — use
    :func:`gate_all` and :func:`score_survivors` and decide for
    themselves, rather than catching an exception to steer control flow.
    """
    gate_reports = gate_all(
        candidates, metrics_by_candidate, pooled_latency_by_candidate, profile, contexts
    )
    evidence = score_survivors(
        candidates, gate_reports, metrics_by_candidate, profile, contexts, settings
    )
    if len(evidence) < 2:
        raise AcceptanceFailure(
            "fewer than two candidates cleared the gates, so there is no comparison to "
            "make. Gate verdicts: "
            + ", ".join(
                f"{cid}: {list(report.blocking_gates) or 'pass'}"
                for cid, report in gate_reports.items()
            )
        )
    return gate_reports, evidence, recommend(evidence, seed=seed)


# --- acceptance criteria (HĐ-15.1) -------------------------------------


def check_shared_contexts(metrics_by_candidate: dict[str, list[EpisodeMetricSet]]) -> str:
    """Criterion 1: the same ``episode_context_id`` set, by assert.

    "By assert, not by eye" is in the contract because this is the
    failure that leaves no trace in the output: two candidates evaluated
    on overlapping-but-different conditions produce a perfectly
    well-formed ΔU that answers a question nobody asked.
    """
    sets = {cid: {m.episode_context_id for m in rows} for cid, rows in metrics_by_candidate.items()}
    reference = next(iter(sets.values()))
    for candidate_id, ids in sets.items():
        if ids != reference:
            raise AcceptanceFailure(
                f"candidate {candidate_id} ran a different context set: "
                f"{len(reference - ids)} missing, {len(ids - reference)} extra"
            )
    return f"all candidates ran the same {len(reference)} episode contexts"


def check_reproducible(first: float, second: float) -> str:
    """Criterion 2: the same inputs give the same utility to six places."""
    if round(first, 6) != round(second, 6):
        raise AcceptanceFailure(
            f"decision_utility is not reproducible: {first!r} then {second!r}. A card "
            "rebuilt from its manifest must come back identical (HĐ-13)"
        )
    return f"decision_utility reproduced to 6 dp: {first:.6f}"


def check_gate_table(gate_reports: dict[str, GateReport]) -> str:
    """Criterion 3: six gates, with the run count, for every candidate."""
    for candidate_id, report in gate_reports.items():
        card = report.to_card()
        missing = [gate for gate in ("G1", "G2", "G3", "G4", "G5", "G6") if gate not in card]
        if missing:
            raise AcceptanceFailure(f"candidate {candidate_id} card is missing {missing}")
        if card["G2"]["n_runs"] < 1:
            raise AcceptanceFailure(f"candidate {candidate_id} reports no runs behind its gates")
    return f"all six gates reported for {len(gate_reports)} candidates, with N"


def check_delta_u(recommendation: Recommendation) -> str:
    """Criterion 4: ΔU and its paired CI exist and are not NaN."""
    comparison = recommendation.comparison
    values = (comparison.delta_median, comparison.delta_mean, *comparison.ci95)
    if not all(math.isfinite(value) for value in values):
        raise AcceptanceFailure(f"ΔU or its CI is not finite: {values}")
    low, high = comparison.ci95
    if low > high:
        raise AcceptanceFailure(f"CI is inverted: [{low}, {high}]")
    return (
        f"ΔU median {comparison.delta_median:+.6f}, "
        f"CI95 [{low:+.6f}, {high:+.6f}] over {comparison.n_episodes} paired episodes"
    )


def check_l_ref(
    metrics_by_candidate: dict[str, list[EpisodeMetricSet]], goal_tolerance_m: float
) -> str:
    """Criterion 5: ``L_ref`` ≤ ``path_length_m + goal_tolerance_m``.

    A shortest path longer than the route actually driven means one of
    the two is wrong, and both feed ``path_efficiency``.

    The slack is exactly the goal tolerance, and it is not a fudge factor
    (HĐ-15.1(5), tightened to this form at 2.2.1 by the first run of the
    slice). ``L_ref`` is measured to the goal *point*; an episode
    succeeds on entering the tolerance *ball* around it and stops there.
    So a legitimate drive is shorter than the reference by up to the
    ball's radius — the first slice reported 4.205 m against 4.024 m with
    a 0.20 m tolerance, which is that effect and nothing else. Anything
    past the tolerance is still a genuine error, which is what this
    check is for.

    Successes only: a failed episode stopped wherever it failed, and its
    path is legitimately shorter than any route to the goal.
    """
    checked = 0
    for candidate_id, rows in metrics_by_candidate.items():
        for row in rows:
            if not row.success:
                continue
            checked += 1
            if row.l_ref_m > row.path_length_m + goal_tolerance_m + 1e-9:
                raise AcceptanceFailure(
                    f"candidate {candidate_id}, episode {row.episode_context_id}: "
                    f"L_ref {row.l_ref_m:.3f} m exceeds the driven path "
                    f"{row.path_length_m:.3f} m by more than the goal tolerance "
                    f"{goal_tolerance_m:.3f} m"
                )
    return f"L_ref ≤ path_length + goal tolerance on all {checked} successful episodes"


def check_node_counts(metrics_by_candidate: dict[str, list[EpisodeMetricSet]]) -> str:
    """Criterion 6: ``peak_search_nodes`` ≤ ``costmap_cells``.

    A graph search cannot hold more nodes than the grid has cells unless
    it is counting the same cell twice — and ``memory_estimate_mb``, and
    therefore gate G5, is that count multiplied by a byte size.
    """
    for candidate_id, rows in metrics_by_candidate.items():
        for row in rows:
            if row.peak_search_nodes > row.costmap_cells:
                raise AcceptanceFailure(
                    f"candidate {candidate_id}, episode {row.episode_context_id}: "
                    f"{row.peak_search_nodes} search nodes over {row.costmap_cells} cells"
                )
    return "peak_search_nodes ≤ costmap_cells on every episode"
