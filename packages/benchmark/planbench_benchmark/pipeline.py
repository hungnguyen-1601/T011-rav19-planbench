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

import hashlib
import json
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from planbench_benchmark.contexts import episode_total, iter_run_plan
from planbench_benchmark.episode import run_contract_episode, scenario_for
from planbench_benchmark.fingerprint import execution_conditions_fingerprint
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
from planbench_simulator.trace import (
    PRODUCTION_USE,
    TraceUsePolicy,
    load_trace_for_use,
    metadata_for_use,
    trace_path,
)

__all__ = [
    "AcceptanceFailure",
    "SweepResult",
    "GateOnlyDeployment",
    "trace_checksum",
    "check_delta_u",
    "check_gate_table",
    "check_gates_reproducible",
    "check_l_ref",
    "check_node_counts",
    "check_reproducible",
    "check_shared_contexts",
    "decide",
    "gate_all",
    "paired_prefix",
    "score",
    "score_episode",
    "score_survivors",
    "simulate",
]

#: What a caller passes to receive progress lines. Printing lives with
#: the caller so this module stays usable from a test or a worker.
Say = Callable[[str], None]

#: The early-stop hook. Given a candidate and the episode it just
#: finished, return a verdict to retire it or ``None`` to keep going.
#: Typed loosely on purpose: the verdict type lives in
#: :mod:`planbench_decision.early_stop`, and the measuring chain should
#: not have to import the decision layer to run episodes.
Retire = Callable[[Candidate, EpisodeContext], object | None]

#: ``(done, total, what)`` — where a long sweep has got to.
#:
#: Structured rather than a second ``say`` the caller has to parse. The
#: numbers are already computed here for the journal, and a caller that
#: had to read them back out of a formatted line would break the first
#: time somebody widened a column.
#:
#: Called on reused traces as well as simulated ones: a run served
#: entirely from disk still moves from 0 to N, and a progress bar that
#: sat at zero through it would be reporting the wrong thing.
Progress = Callable[[int, int, str], None]


def _silent(_message: str) -> None:
    return None


@dataclass(frozen=True)
class SweepResult:
    """What a sweep did, as opposed to what it was asked to do.

    ``contexts_by_candidate`` is per-candidate because early stopping
    makes it so: a retired candidate genuinely covered fewer episodes
    than the ones still running. Everything downstream — scoring, gates,
    the checksum — has to be told which episodes belong to whom, and
    deriving that from the filesystem afterwards would get it wrong on a
    rerun where an older, longer set of traces is still lying around.
    """

    retired: dict[str, object]
    contexts_by_candidate: dict[str, tuple[EpisodeContext, ...]]


class AcceptanceFailure(AssertionError):
    """An acceptance criterion did not hold.

    One exception for all three entry points. The scripts alias it under
    their own names (``SliceFailure``, ``MeasurementFailure``) because the
    criteria they answer to are numbered differently — HĐ-15.1 for the
    slice, plan F1 for the measurement — but a failure is the same event
    and callers should not have to catch two types to survive it.
    """


class GateOnlyDeployment(Exception):
    """This deployment gates, it does not rank (HĐ-8.4).

    Raised before any objective is computed, not after — there is no
    partially-scored state to inspect and no half-built utility to
    mistake for a real one.

    Deliberately *not* an :class:`AcceptanceFailure`. Nothing failed: the
    deployment set a gate threshold at the ideal, which is a legal and
    meaningful thing for an acceptance site to do, and the measurement
    that follows is valid — it is the *ranking* that has no basis. A
    caller that catches this should write its gate table and say why
    there is no card, exactly as it does when fewer than two candidates
    survive. A caller that lets it propagate stops, which is also
    correct: better a named refusal than a ``decision_utility`` computed
    over a quietly smaller objective set.
    """


def simulate(
    candidates: Sequence[Candidate],
    profile: TaskProfile,
    contexts: Sequence[EpisodeContext],
    map_data: MapData,
    trace_root: Path,
    *,
    evidence_class: str = "production",
    use: TraceUsePolicy = PRODUCTION_USE,
    reuse: bool,
    say: Say | None = None,
    journal: Path | None = None,
    retire: Retire | None = None,
    progress: Progress | None = None,
) -> SweepResult:
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

    ``journal`` turns the progress lines into an artifact. The ordering
    above already makes an interrupted sweep a valid smaller comparison,
    but that guarantee was only ever cashed in by a human reading stdout:
    the report is written after the last episode, so a run killed at 82%
    left three hours of episodes on disk and *no file saying what had
    been measured*. One JSON line per episode, flushed as it happens,
    means a run that never reaches its own ending is still readable —
    including by the process that finds it afterwards.

    ``retire`` is the early-stop hook. It is consulted after every
    episode a candidate completes — including episodes served from
    existing traces, so ``--reuse-traces`` reaches the same verdict as a
    fresh run rather than a different one. Once it returns a verdict for
    a candidate, that candidate's remaining pairs are skipped and the
    verdict is recorded.
    """
    emit = say or print
    locator = TraceLocator(trace_root, profile, map_data, evidence_class=evidence_class, use=use)
    total = episode_total(contexts, candidates)
    if journal is not None:
        journal.parent.mkdir(parents=True, exist_ok=True)
        # **Truncated, not appended to.** The run directory is named from
        # the profile id, the scope and the candidate set — none of which
        # change when the *world* does — so a second sweep of a changed
        # deployment lands in the same folder. Appending there produced a
        # journal holding sixty `stuck` episodes from one world followed
        # by sixty `success` ones from another, under identical context
        # ids, which reads as a flaky episode rather than as two runs.
        # Each sweep owns its journal; the traces are what persist.
        journal.write_text("", encoding="utf-8")
    retired: dict[str, object] = {}
    covered: dict[str, list[EpisodeContext]] = {c.candidate_id: [] for c in candidates}
    for index, (context, candidate) in enumerate(iter_run_plan(contexts, candidates), start=1):
        if candidate.candidate_id in retired:
            continue
        covered[candidate.candidate_id].append(context)
        if reuse and locator.usable(candidate, context):
            if progress is not None:
                progress(index, total, candidate.stack_label)
            _consult_retire(retire, retired, candidate, context, journal, emit)
            continue
        # monotonic, not time(): the wall clock steps when NTP corrects
        # it and can run backwards, which writes a negative duration
        # into the journal — a reader cannot tell that from a real
        # measurement, and the journal is what a stopped run is judged on.
        started = time.monotonic()
        _, run = run_contract_episode(
            candidate,
            profile,
            context,
            map_data,
            root=trace_root,
            evidence_class=locator.evidence_class,
        )
        elapsed = time.monotonic() - started
        emit(
            f"  {index:>4}/{total}  {candidate.stack_label:<14} "
            f"seed {context.seed:<4} {run.result.status.value:<16} "
            f"{elapsed:5.1f}s"
        )
        if progress is not None:
            progress(index, total, candidate.stack_label)
        if journal is not None:
            _append_journal(
                journal,
                {
                    "index": index,
                    "total": total,
                    "candidate_id": candidate.candidate_id,
                    "stack_label": candidate.stack_label,
                    "seed": context.seed,
                    "episode_context_id": context.episode_context_id,
                    "status": run.result.status.value,
                    "wall_clock_s": round(elapsed, 3),
                    "finished_at": datetime.now(UTC).isoformat(),
                },
            )
        _consult_retire(retire, retired, candidate, context, journal, emit)
    return SweepResult(
        retired=retired,
        contexts_by_candidate={cid: tuple(rows) for cid, rows in covered.items()},
    )


def _consult_retire(
    retire: Retire | None,
    retired: dict[str, object],
    candidate: Candidate,
    context: EpisodeContext,
    journal: Path | None,
    emit: Say,
) -> None:
    """Ask the early-stop rule, and make the answer loud if it fires.

    A candidate leaving the run mid-sweep is the kind of event that must
    never be inferred from a gap in the episode numbering. It goes on
    stdout and into the journal as its own record, with the gate named.
    """
    if retire is None:
        return
    verdict = retire(candidate, context)
    if verdict is None:
        return
    retired[candidate.candidate_id] = verdict
    gate = getattr(verdict, "gate", "?")
    rule = getattr(verdict, "rule", "")
    emit(f"  ⏹ DỪNG SỚM  {candidate.stack_label:<14} {gate} — {rule}")
    if journal is not None:
        _append_journal(
            journal,
            {
                "event": "stopped_early",
                "candidate_id": candidate.candidate_id,
                "stack_label": candidate.stack_label,
                "gate": gate,
                "rule": rule,
                "last_episode_context_id": context.episode_context_id,
                "at": datetime.now(UTC).isoformat(),
            },
        )


def _append_journal(path: Path, entry: dict[str, object]) -> None:
    """Append one line and flush it, because the reader may be a kill.

    Buffered writes would defeat the whole point: the entries that
    matter most are the ones written seconds before the process stopped.
    """
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        handle.flush()


class StaleTraceError(ValueError):
    """A trace on disk describes a world this run is not asking about."""


class TraceLocator:
    """Where this run's traces live, and which ones it may read.

    **Every address in this module comes from here.** Six call sites used
    to build ``trace_path(candidate_id, context_id, root)`` themselves;
    once the address grew an evidence class and a conditions hash, six
    places computing it independently is six places to get it subtly
    different — and a mismatch between where a trace is written and where
    it is looked for reads as "no trace", which is silent.

    The policy travels with the locator for the same reason: a run knows
    what it is (production sweep, research lane), and a reader that had
    to be told separately is a reader somebody will forget to tell.
    """

    def __init__(
        self,
        trace_root: Path,
        profile: TaskProfile,
        map_data: MapData,
        *,
        evidence_class: str = "production",
        use: TraceUsePolicy = PRODUCTION_USE,
    ) -> None:
        self.root = Path(trace_root)
        self.profile = profile
        self.map_data = map_data
        self.evidence_class = evidence_class
        self.use = use

    def fingerprint(self, context: EpisodeContext) -> str:
        return execution_conditions_fingerprint(
            self.map_data, scenario_for(self.profile, context), self.profile
        )

    def path(self, candidate: Candidate, context: EpisodeContext) -> Path:
        return trace_path(
            candidate.candidate_id,
            context.episode_context_id,
            root=self.root,
            evidence_class=self.evidence_class,
            execution_fingerprint=self.fingerprint(context),
        )

    def load(self, candidate: Candidate, context: EpisodeContext):
        """Rows, through the one boundary — class and address checked."""
        return load_trace_for_use(self.path(candidate, context), use=self.use)

    def usable(self, candidate: Candidate, context: EpisodeContext) -> bool:
        """Whether an existing trace may be reused for this run.

        Three refusals in one answer, and all three are already the
        platform's rules: the file must exist, its class must be one this
        use accepts, and its conditions must be the ones being asked
        about. The conditions check is now partly structural — a trace
        from another world is at another address — but the metadata check
        stays, because a file can be copied into a directory that lies.
        """
        path = self.path(candidate, context)
        if not path.is_file():
            return False
        try:
            recorded = metadata_for_use(path, use=self.use).execution_conditions_fingerprint
        except Exception:
            return False
        return bool(recorded) and recorded == self.fingerprint(context)


def paired_prefix(
    candidates: Sequence[Candidate],
    contexts: Sequence[EpisodeContext],
    trace_root: Path,
    profile: TaskProfile,
    map_data: MapData,
    *,
    evidence_class: str = "production",
    use: TraceUsePolicy = PRODUCTION_USE,
) -> list[EpisodeContext]:
    """The longest leading run of contexts every candidate has a trace for.

    The prefix, not the set. :func:`iter_run_plan` fills contexts in
    order, so an interrupted sweep leaves a prefix plus at most one
    half-finished context — and taking the prefix is what keeps "every
    candidate ran the same episodes" true (HĐ-7.3) instead of comparing
    one candidate's 245 episodes against another's 244.
    """
    locator = TraceLocator(trace_root, profile, map_data, evidence_class=evidence_class, use=use)
    kept: list[EpisodeContext] = []
    stale: list[str] = []
    for context in contexts:
        paths = [locator.path(candidate, context) for candidate in candidates]
        if not all(path.is_file() for path in paths):
            break
        mismatched = [
            locator.path(candidate, context)
            for candidate in candidates
            if not locator.usable(candidate, context)
        ]
        if mismatched:
            stale.extend(str(path) for path in mismatched)
            break
        kept.append(context)
    if stale:
        # **Refused, not truncated.** Scoring re-reads finished traces and
        # never re-simulates, so there is no way to replace a stale one:
        # quietly shortening the sample would hand back a report built
        # partly from a world nobody asked about, and the length is the
        # only clue it would leave.
        raise StaleTraceError(
            f"{len(stale)} trace(s) under {trace_root} were recorded under different "
            "execution conditions than this profile describes, and scoring cannot "
            "re-simulate them. Re-run the sweep instead of scoring. First: " + stale[0]
        )
    return kept


def score(
    candidate: Candidate,
    profile: TaskProfile,
    contexts: Sequence[EpisodeContext],
    map_data: MapData,
    trace_root: Path,
    *,
    evidence_class: str = "production",
    use: TraceUsePolicy = PRODUCTION_USE,
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
    locator = TraceLocator(trace_root, profile, map_data, evidence_class=evidence_class, use=use)
    traces = [locator.load(candidate, context) for context in contexts]
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


def score_episode(
    candidate: Candidate,
    profile: TaskProfile,
    context: EpisodeContext,
    map_data: MapData,
    trace_root: Path,
    *,
    evidence_class: str = "production",
    use: TraceUsePolicy = PRODUCTION_USE,
) -> EpisodeMetricSet:
    """One episode's metrics, read back from its trace.

    The single-episode form of :func:`score`, extracted so an early-stop
    watch can accumulate metrics one at a time instead of re-reading the
    whole run after every episode — which would be quadratic on a
    three-hour sweep.

    Deliberately still a **file** read. Taking the numbers the simulator
    already had in memory would be faster still and would break HĐ-5:
    a gate verdict that came from process memory cannot be re-derived
    later, and two runs could disagree with nothing on disk to explain
    which was right.
    """
    locator = TraceLocator(trace_root, profile, map_data, evidence_class=evidence_class, use=use)
    trace = locator.load(candidate, context)
    return compute_metrics(
        trace,
        profile,
        context,
        map_data,
        resource_profile=candidate.resource_profile,
    )


def trace_checksum(
    candidates: Sequence[Candidate],
    contexts: Sequence[EpisodeContext],
    trace_root: Path,
    profile: TaskProfile,
    map_data: MapData,
    *,
    evidence_class: str = "production",
    use: TraceUsePolicy = PRODUCTION_USE,
) -> str:
    """One hash over every trace this run was computed from (D15).

    A card and its manifest stay in the row; the Parquet traces behind
    them are megabytes per episode and stay in the artifact store,
    reachable through ``run_uri``. **The checksum is what makes that
    reference trustworthy rather than decorative** — a URI on its own
    cannot say the files it points at are the ones the card was computed
    from, and "the traces moved on" is exactly the failure a stored
    result cannot detect on its own.

    Hashed over *content*, not over size and mtime. A stale file with the
    right length is precisely the case worth catching, and mtime is a
    fact about the filesystem rather than about the episode.

    The path is included alongside each digest, so two episodes that
    happen to produce byte-identical traces still hash to different
    entries — otherwise a run that lost a file could match one that never
    had it.

    Missing files are hashed as absent rather than raising: this is a
    fingerprint of what the run actually had, and a run whose traces are
    incomplete should be *recognisable*, not unhashable.
    """
    locator = TraceLocator(trace_root, profile, map_data, evidence_class=evidence_class, use=use)
    digest = hashlib.sha256()
    entries: list[str] = []
    for candidate in candidates:
        for context in contexts:
            path = locator.path(candidate, context)
            key = f"{candidate.candidate_id}/{context.episode_context_id}"
            if not path.is_file():
                entries.append(f"{key}:absent")
                continue
            entries.append(f"{key}:{hashlib.sha256(path.read_bytes()).hexdigest()}")
    for entry in sorted(entries):
        digest.update(entry.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def gate_all(
    candidates: Sequence[Candidate],
    metrics_by_candidate: dict[str, list[EpisodeMetricSet]],
    pooled_latency_by_candidate: dict[str, float],
    profile: TaskProfile,
    contexts: Sequence[EpisodeContext],
    contexts_by_candidate: dict[str, Sequence[EpisodeContext]] | None = None,
) -> dict[str, GateReport]:
    """G1–G6 for every candidate, before anything is scored.

    ``contexts_by_candidate`` overrides ``contexts`` per candidate, and
    is needed only when early stopping has retired somebody: gates
    report *what was measured*, so a candidate retired at episode 30 has
    to be gated on its thirty episodes rather than on a set it never
    ran. Every gate threshold still comes from the deployment.
    """
    return {
        candidate.candidate_id: evaluate_gates(
            candidate,
            profile,
            metrics_by_candidate[candidate.candidate_id],
            (contexts_by_candidate or {}).get(candidate.candidate_id, contexts),
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
    gate_only = anchors.gate_only_reason
    if gate_only is not None:
        raise GateOnlyDeployment(
            f"task profile {profile.id!r} cannot be ranked, only gated — {gate_only}"
        )
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


def check_shared_contexts(
    metrics_by_candidate: dict[str, list[EpisodeMetricSet]],
    *,
    among: Sequence[str] | None = None,
) -> str:
    """Criterion 1: the same ``episode_context_id`` set, by assert.

    "By assert, not by eye" is in the contract because this is the
    failure that leaves no trace in the output: two candidates evaluated
    on overlapping-but-different conditions produce a perfectly
    well-formed ΔU that answers a question nobody asked.

    ``among`` narrows the claim to a subset of candidates, and exists for
    exactly one situation: early stopping retires a candidate mid-sweep,
    so it genuinely has fewer episodes than the rest. That is sound only
    because a retired candidate has **failed a gate**, and the two-tier
    architecture (N4) means a gate failure is never scored, never ranked
    and never enters ΔU — the pairing invariant is needed among
    *survivors*, not among everyone who was tried.

    The returned sentence says which set it is talking about, because a
    check that quietly changed what it guarantees would be worse than no
    check.
    """
    selected = (
        metrics_by_candidate
        if among is None
        else {cid: rows for cid, rows in metrics_by_candidate.items() if cid in set(among)}
    )
    if not selected:
        # Not "nobody ran anything" — everybody ran, and everybody was
        # retired. There is no surviving pair left to compare, so there
        # is nothing for the paired invariant to be about. Saying it the
        # other way round would report an empty run.
        return (
            f"every one of the {len(metrics_by_candidate)} candidates was retired early, "
            "so no ΔU is paired and there is no surviving context set to compare"
        )
    sets = {cid: {m.episode_context_id for m in rows} for cid, rows in selected.items()}
    reference = next(iter(sets.values()))
    for candidate_id, ids in sets.items():
        if ids != reference:
            raise AcceptanceFailure(
                f"candidate {candidate_id} ran a different context set: "
                f"{len(reference - ids)} missing, {len(ids - reference)} extra"
            )
    who = "all candidates" if among is None else f"all {len(selected)} candidates still in the run"
    return f"{who} ran the same {len(reference)} episode contexts"


def check_reproducible(first: float, second: float) -> str:
    """Criterion 2: the same inputs give the same utility to six places."""
    if round(first, 6) != round(second, 6):
        raise AcceptanceFailure(
            f"decision_utility is not reproducible: {first!r} then {second!r}. A card "
            "rebuilt from its manifest must come back identical (HĐ-13)"
        )
    return f"decision_utility reproduced to 6 dp: {first:.6f}"


def check_gates_reproducible(first: GateReport, second: GateReport) -> str:
    """Criterion 2 on a gate-only deployment (HĐ-8.4).

    There is no ``decision_utility`` to reproduce there, and dropping the
    criterion instead would leave the hall — the deployment whose entire
    job is to gate — as the one place the gate verdict is never checked
    twice. So the same demand is made of the artifact that deployment
    actually produces: score the traces again, get the same verdicts.
    """
    if first.to_card() != second.to_card():
        raise AcceptanceFailure(
            "the gate table is not reproducible: scoring the same traces twice gave "
            f"{first.to_card()} then {second.to_card()}"
        )
    blocking = list(first.blocking_gates) or ["none"]
    return f"gate table reproduced exactly; blocking: {blocking}"


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
