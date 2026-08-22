"""Running a candidate selection, once — for the CLI and for the API.

``scripts/compare.py`` used to own this. The API cannot import a script,
so leaving it there would have meant a second orchestration living in
``planbench_api`` — and then two ways to run a selection, free to
disagree about what a gate verdict means. That is the failure M3 removed
between the slice, the measurement and the comparison, one layer up:
**the chain is shared, and callers differ only in what they do with the
result.** The CLI writes JSON under ``artifacts/runs/`` and prints a
summary; the API stores the same objects in ``decision_runs`` and serves
them. Neither decides anything the other does not.

Named ``selection`` rather than ``comparison`` because
:mod:`planbench_benchmark.comparison` already exists and means something
else — P04's seed-paired statistics between two stacks. This module is
the *run* that a Planner Selector performs.

**A selection that cannot be ranked still returns.** Fewer than two
candidates through the gates means no ΔU and no card, and that is a
result: the gate table answers "who was eliminated where, after how many
runs", which is the question HĐ-12 puts on a card. So this returns a
report either way, with ``decision_card`` set to ``None``. Raising
instead would push every caller to treat an ordinary outcome as an error
— and that pressure is what produced a card bounding a collision
probability off a single episode.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

import yaml

from planbench_benchmark.candidates import (
    LOCAL_CONTROLLER_CONFIGS,
    candidate_from_stack,
    validate_config_names,
    validate_control_rate,
)
from planbench_benchmark.contexts import build_evaluation_contexts
from planbench_benchmark.hostinfo import detect_benchmark_host, unpinned_warning
from planbench_benchmark.pipeline import (
    AcceptanceFailure,
    GateOnlyDeployment,
    Progress,
    SweepResult,
    TraceLocator,
    check_delta_u,
    check_gate_table,
    check_l_ref,
    check_node_counts,
    check_reproducible,
    check_shared_contexts,
    gate_all,
    paired_prefix,
    score,
    score_episode,
    score_survivors,
    trace_checksum,
)
from planbench_benchmark.pipeline import simulate as run_episodes
from planbench_benchmark.task_map import load_task_map, validate_missions_on_map
from planbench_decision.anchors import load_anchors
from planbench_decision.candidate import (
    Candidate,
    TuningDeclaration,
    validate_experiment_scope,
)
from planbench_decision.card import (
    DecisionCard,
    Manifest,
    Provenance,
    build_decision_card,
    build_manifest,
    resolve_git_sha,
)
from planbench_decision.early_stop import (
    GATES_WITHOUT_A_RULE,
    StopVerdict,
    check_early_stop,
)
from planbench_decision.gates import GateReport
from planbench_decision.objectives import DecisionSettings
from planbench_decision.pareto import ParetoReport, label_field
from planbench_decision.sensitivity import (
    AnchorStability,
    ScoredField,
    WeightStability,
    anchor_stability,
    weight_stability,
)
from planbench_decision.stats import CandidateEvidence, Recommendation, recommend
from planbench_explanation.catalog import TOOL_CATALOG_VERSION
from planbench_explanation.detectors import DETECTOR_VERSION
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION
from planbench_explanation.packet_builder import (
    EpisodeTrace,
    build_scoring_packet,
    packet_block,
)
from planbench_explanation.versioning import file_checksum
from planbench_explanation.waterfall import Waterfall, build_waterfall
from planbench_metrics.definitions import EpisodeMetricSet
from planbench_schemas.episode_context import EpisodeContext
from planbench_schemas.feasibility import SafetyEnvelope, hard_clearance
from planbench_schemas.map import MapData
from planbench_schemas.task_profile import DEFAULT_MIN_EPISODES_BEFORE_STOP, TaskProfile

REPO_ROOT = Path(__file__).resolve().parents[3]

#: HĐ-1.4's default claim. Declared by the caller, never inferred from
#: the candidate set — inferring it would turn
#: ``validate_experiment_scope``'s refusal into a rename.
DEFAULT_SCOPE = "global_planner_selection"

#: Nobody tuned anything, and both halves matter for U_C: zero hours, and
#: an evidence log saying where to check.
UNTUNED_EVIDENCE = "planbench_benchmark.selection (library defaults, no tuning run)"

__all__ = [
    "DEFAULT_SCOPE",
    "CardBundle",
    "assemble_card",
    "build_candidates",
    "load_profile",
    "parse_candidates",
    "refuse_early_stop",
    "resolve_stop_floor",
    "run_comparison",
    "run_dir_name",
]


def load_profile(path: Path) -> TaskProfile:
    return TaskProfile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def parse_candidates(spec: str, default_local: str) -> tuple[tuple[str, str], ...]:
    """``"astar+dwa,rrtstar+dwa:dwa_default"`` → ``((stack, local), ...)``.

    The optional ``:local`` suffix is what makes a local-controller
    comparison expressible at all. Without it the sampling density would
    have to be a flag applying to every candidate, and "same stack, two
    controllers" — the question left open by the convex-corner stall —
    could not be asked.
    """
    parsed: list[tuple[str, str]] = []
    for item in spec.split(","):
        entry = item.strip()
        if not entry:
            continue
        stack, _, local = entry.partition(":")
        local = local or default_local
        if local not in LOCAL_CONTROLLER_CONFIGS:
            raise SystemExit(
                f"unknown local controller {local!r} in {entry!r}; "
                f"known: {sorted(LOCAL_CONTROLLER_CONFIGS)}"
            )
        parsed.append((stack.strip(), local))
    if len(parsed) < 2:
        raise SystemExit(
            f"a comparison needs at least two candidates, got {len(parsed)}. "
            "To measure one, use scripts/measure.py — it produces a Measurement "
            "Report instead of a Decision Card, because ΔU, its interval and its "
            "label do not exist for a single candidate"
        )
    return tuple(parsed)


def build_candidates(
    profile: TaskProfile, specs: Sequence[tuple[str, str]], scope: str
) -> tuple[Candidate, ...]:
    """Every candidate, checked against the deployment before episode one.

    Three refusals happen here rather than after hours of simulation:
    ``validate_config_names`` on whether each configuration belongs to
    the controller it was paired with, ``validate_experiment_scope`` on
    whether the set can support the declared claim (HĐ-1.4), and
    ``validate_control_rate`` on whether each controller keeps up with
    the deployment's T_cycle — which G4 cannot see, since it times one
    call and never counts them.

    The first is checked **before** the candidates are built: a mismatched
    pair constructs perfectly well and only becomes visible in the report
    it goes on to mislabel.
    """
    validate_config_names(specs)
    candidates = tuple(
        candidate_from_stack(stack, params=dict(LOCAL_CONTROLLER_CONFIGS[local])).model_copy(
            update={
                "tuning": TuningDeclaration(
                    tuning_trials_used=0,
                    tuning_wall_clock_h=0.0,
                    n_tunable_params=len(LOCAL_CONTROLLER_CONFIGS[local]),
                    evidence_log=UNTUNED_EVIDENCE,
                )
            }
        )
        for stack, local in specs
    )
    validate_experiment_scope(scope, candidates)  # type: ignore[arg-type]
    validate_control_rate(profile, candidates)
    return candidates


@dataclass(frozen=True)
class CardBundle:
    """A Decision Card and everything that had to be computed to earn it."""

    card: DecisionCard
    manifest: Manifest
    weight_stability: WeightStability
    anchor_stability: AnchorStability
    pareto: ParetoReport


def assemble_card(
    *,
    candidates: Sequence[Candidate],
    metrics_by_candidate: dict[str, list],
    gate_reports: dict[str, GateReport],
    evidence: Sequence[CandidateEvidence],
    recommendation: Recommendation,
    profile: TaskProfile,
    contexts: Sequence[object],
    settings: DecisionSettings,
    scope: str,
    manifest_ref: str,
    provenance: Provenance,
    bootstrap_seed: int,
) -> CardBundle:
    """Turn a finished comparison into a card, with every caveat measured.

    **Why this is shared rather than written twice.** The slice built a
    card with sensitivity and Pareto; ``run_comparison`` built one
    without, so the project's first Decision Card carried
    ``weight_stability_margin: null`` and ``anchor_stability: null``.
    HĐ-12 reads null as *"not measured"*, so that card was honest and
    incomplete — and HĐ-11.5 calls the sensitivity sweep the single most
    useful thing on a card, because a ``CLEAR_RECOMMENDATION`` nobody
    knows the flipping point of is half an answer.

    Two producers of one artifact is the same failure M3 removed between
    the slice, the measurement and the comparison — caught one layer
    later, at the step that assembles the card rather than the step that
    measures.

    **The sweeps are cheap and that is the point.** Both re-score metrics
    already in memory and never touch the simulator, so they cost seconds
    on a run that cost hours. There was never a budget reason to leave
    them out.

    **Pareto runs after the recommendation, not before.** It does not
    choose the winner; it decides which of the others may be offered
    beside it, and whether the winner is only winning on the weights
    (HĐ-10.1: label, never delete).
    """
    anchors = load_anchors().resolve(profile)
    field = ScoredField.from_survivors(
        candidates,
        metrics_by_candidate,
        contexts,
        {cid: report.passed for cid, report in gate_reports.items()},
    )
    weights_sweep = weight_stability(field, anchors, settings, seed=bootstrap_seed)
    anchors_sweep = anchor_stability(field, anchors, settings, seed=bootstrap_seed)
    pareto = label_field(evidence, seed=bootstrap_seed)

    card = build_decision_card(
        recommendation,
        evidence,
        gate_reports,
        profile,
        settings,
        scope,  # type: ignore[arg-type]
        manifest_ref,
        weight_stability=weights_sweep,
        anchor_stability=anchors_sweep,
        pareto=pareto,
    )
    manifest = build_manifest(
        recommendation,
        evidence,
        gate_reports,
        profile,
        settings,
        anchors,
        provenance,
        contexts,
    )
    return CardBundle(
        card=card,
        manifest=manifest,
        weight_stability=weights_sweep,
        anchor_stability=anchors_sweep,
        pareto=pareto,
    )


def resolve_stop_floor(profile: TaskProfile, override: int | None) -> int:
    """Flag › profile › default 30, and the winner is put on the report.

    Three sources rather than a constant because the floor buys a
    *distribution*, and how much distribution is worth buying is a
    property of the question being asked, not of the code. It is written
    into the report for the same reason ``constraints`` had to go into
    the manifest (A4): two runs of one profile under two floors are two
    different measurements, and nothing else would tell them apart.
    """
    if override is not None:
        return override
    if profile.min_episodes_before_stop is not None:
        return profile.min_episodes_before_stop
    return DEFAULT_MIN_EPISODES_BEFORE_STOP


def refuse_early_stop(profile: TaskProfile) -> str | None:
    """Why this deployment may not stop early, or ``None``.

    An acceptance deployment is refused (Q3 of the 12-08 plan) because
    the trade is bad at both ends: every failure there is a *diagnostic
    symptom* rather than a statistic — HĐ's reason for
    ``success_rate_min = 1.00`` on the hall — so the episodes are the
    product, and the hall is also the cheap deployment, so the hours
    saved are small.

    Refused rather than silently ignored. A flag that gets swallowed
    leaves the user believing they are saving time when they are not,
    which is worse than either honest outcome.
    """
    if profile.deployment_role != "acceptance":
        return None
    return (
        f"profile {profile.id!r} khai deployment_role='acceptance', nên không được dừng "
        "sớm: ở đó mọi failure là một tín hiệu chẩn đoán chứ không phải một thống kê, và "
        "chính các episode là sản phẩm. Bỏ cờ --stop-early, hoặc đổi vai trò của "
        "deployment nếu nó thật sự không còn là acceptance"
    )


def _refuse_a_retired_survivor(
    retired: dict[str, object], gate_reports: dict[str, GateReport]
) -> None:
    """The premise the whole feature rests on, checked instead of assumed.

    Early stopping is only sound because a retired candidate has failed
    a gate, and therefore never reaches ΔU — which is what lets the
    paired-context invariant be narrowed to survivors. If a candidate
    were ever retired *and* passed its gates, that reasoning would be
    gone and a truncated candidate could be ranked against a full one.

    It cannot happen: every rule in :mod:`planbench_decision.early_stop`
    holds at any sample size the run can end at. So this raises rather
    than warns — a violation means a rule is wrong, not that a run is
    unusual.
    """
    contradictions = sorted(cid for cid in retired if gate_reports[cid].passed)
    if contradictions:
        raise AcceptanceFailure(
            f"candidate(s) {contradictions} bị dừng sớm nhưng vẫn qua đủ cổng — luật dừng "
            "đã tuyên bố một điều không đúng. Một candidate bị dừng phải là một candidate "
            "trượt cổng, nếu không phép so ghép cặp đang so một tập episode với một tập khác"
        )


class _EarlyStopWatch:
    """Accumulates one candidate's metrics from traces and asks the rule.

    Metrics are read back **from the trace files** one episode at a time
    (HĐ-5), not taken from the simulator's memory: a gate verdict that
    came from process memory could not be re-derived later. Accumulating
    rather than re-reading the whole run each time keeps that honest and
    linear instead of quadratic — the difference between seconds and
    hours on a 300-episode sweep.
    """

    def __init__(
        self,
        profile: TaskProfile,
        map_data: object,
        trace_root: Path,
        *,
        planned: int,
        floor: int,
        evidence_class: str = "production",
    ) -> None:
        self._profile = profile
        self._map_data = map_data
        self._trace_root = trace_root
        self._evidence_class = evidence_class
        self._planned = planned
        self._floor = floor
        self._metrics: dict[str, list] = {}
        #: Where the rule *first* fired, even if the floor held the
        #: candidate in the run for longer. The report carries it so
        #: "it knew at episode 7, why did it run to 30?" has an answer.
        self._would_have_stopped_at: dict[str, int] = {}

    def retire(self, candidate: Candidate, context: object) -> StopVerdict | None:
        rows = self._metrics.setdefault(candidate.candidate_id, [])
        rows.append(
            score_episode(
                candidate,
                self._profile,
                context,  # type: ignore[arg-type]
                self._map_data,  # type: ignore[arg-type]
                self._trace_root,
                evidence_class=self._evidence_class,
            )
        )
        verdict = check_early_stop(rows, self._profile, planned_episodes=self._planned)
        if verdict is None:
            return None
        self._would_have_stopped_at.setdefault(candidate.candidate_id, len(rows))
        if len(rows) < self._floor:
            return None
        return verdict

    def floor_report(self, candidate_id: str) -> dict[str, object]:
        return {
            "min_episodes_before_stop": self._floor,
            "would_have_stopped_at": self._would_have_stopped_at.get(candidate_id),
        }


def run_comparison(
    *,
    profile_path: Path,
    candidate_specs: Sequence[tuple[str, str]],
    scope: str,
    episodes: int | None,
    trace_root: Path,
    run_root: Path,
    reuse: bool,
    bootstrap_seed: int = 0,
    git_sha: str | None = None,
    created_at: datetime | None = None,
    quiet: bool = False,
    map_base_dir: Path | None = None,
    affinity_source: str | None = None,
    score_only: bool = False,
    stop_early: bool = False,
    #: What this whole sweep's evidence is worth (§5.10). It reaches the
    #: recorder, the trace addresses, the reuse check, the scoring reads
    #: **and** the run directory — a knob that stopped at any one of
    #: those would separate namespaces without routing anything into
    #: them, which is how H9A first shipped.
    evidence_class: str = "production",
    min_episodes_before_stop: int | None = None,
    progress: Progress | None = None,
) -> dict[str, object]:
    def say(message: str) -> None:
        if not quiet:
            print(message, flush=True)

    created_at = created_at or datetime.now(UTC)
    profile = load_profile(profile_path)
    map_data = load_task_map(profile, base_dir=map_base_dir or REPO_ROOT)
    validate_missions_on_map(profile, map_data)
    candidates = build_candidates(profile, candidate_specs, scope)
    contexts = build_evaluation_contexts(profile, seed_count=episodes)
    settings = DecisionSettings()
    host = detect_benchmark_host(affinity_source=affinity_source)  # type: ignore[arg-type]

    say(
        f"profile {profile.id}: {map_data.width}×{map_data.height} cells, "
        f"{len(contexts)} contexts "
        f"(N_min = {profile.constraints.n_min_evaluation_episodes} at "
        f"{profile.constraints.collision_probability_max:.0%} accepted collision risk)"
    )
    for candidate, (_stack, local) in zip(candidates, candidate_specs, strict=True):
        say(f"  {candidate.stack_label:<14} {local:<12} {candidate.candidate_id}")
    warning = unpinned_warning(host)
    if warning:
        say(f"⚠ {warning}")

    # The destination is known before the first episode — its name is
    # built from the profile, the scope and the candidate set, none of
    # which the run can change. Creating it here rather than at the end
    # is what lets the journal exist while the run is still going, and a
    # run that dies in its first minute now leaves a directory saying it
    # was attempted instead of nothing at all.
    destination = (
        run_root
        / created_at.strftime("%Y-%m-%d")
        / run_dir_name(profile.id, scope, candidates, evidence_class)
    )
    destination.mkdir(parents=True, exist_ok=True)

    requested = len(contexts)
    interrupted = False
    floor = resolve_stop_floor(profile, min_episodes_before_stop)
    if stop_early:
        refusal = refuse_early_stop(profile)
        if refusal:
            raise AcceptanceFailure(refusal)
        say(
            f"dừng sớm: BẬT, sàn {floor} episode "
            f"(cổng không có luật dừng: {', '.join(sorted(GATES_WITHOUT_A_RULE))})"
        )
    watch = (
        _EarlyStopWatch(
            profile,
            map_data,
            trace_root,
            planned=requested,
            floor=floor,
            evidence_class=evidence_class,
        )
        if stop_early and not score_only
        else None
    )
    sweep: SweepResult | None = None
    if score_only:
        # Recovering a run whose process is already gone. A hard kill
        # never reaches the KeyboardInterrupt path below, so the episodes
        # it left on disk need a way back into a report that does not
        # involve re-simulating them or hand-editing JSON. Same prefix
        # rule, same honesty about the sample it ended up with.
        contexts = paired_prefix(
            candidates, contexts, trace_root, profile, map_data, evidence_class=evidence_class
        )
        interrupted = len(contexts) < requested
        if not contexts:
            raise AcceptanceFailure(
                "score-only: không có episode nào ghép cặp đủ cả hai candidate dưới "
                f"{trace_root} — không có gì để chấm"
            )
        say(
            f"chỉ chấm, không mô phỏng: {len(contexts)}/{requested} episode có trace đủ cả "
            f"{len(candidates)} candidate"
        )
        contexts_by_candidate = {c.candidate_id: tuple(contexts) for c in candidates}
    else:
        say("simulating…")
        contexts_by_candidate = {c.candidate_id: tuple(contexts) for c in candidates}
        try:
            sweep = run_episodes(
                candidates,
                profile,
                contexts,
                map_data,
                trace_root,
                evidence_class=evidence_class,
                reuse=reuse,
                say=say,
                journal=destination / "run_journal.jsonl",
                retire=watch.retire if watch is not None else None,
                progress=progress,
            )
            contexts_by_candidate = sweep.contexts_by_candidate
        except KeyboardInterrupt:
            # An interrupted sweep is a smaller run, not a failed one —
            # the context-outer ordering in `simulate` exists to make
            # that true. Re-raising would throw away every episode
            # already on disk, which is exactly the outcome that made a
            # three-hour run unreadable once.
            interrupted = True
            contexts = paired_prefix(
                candidates, contexts, trace_root, profile, map_data, evidence_class=evidence_class
            )
            contexts_by_candidate = {c.candidate_id: tuple(contexts) for c in candidates}
            say(
                f"\n⚠ NGẮT GIỮA CHỪNG — chấm trên {len(contexts)}/{requested} episode đã ghép "
                "cặp đủ cả hai bên; phần dở dang bị bỏ để mọi candidate vẫn chạy cùng một tập"
            )
            if not contexts:
                report = _interrupted_before_any_episode(
                    profile, scope, requested, created_at, git_sha, host, warning
                )
                _write_json(destination / "comparison_report.json", report)
                say(f"written to:     {destination}")
                return report

    say("scoring from traces…")
    scored = {
        candidate.candidate_id: score(
            candidate,
            profile,
            contexts_by_candidate[candidate.candidate_id],
            map_data,
            trace_root,
            evidence_class=evidence_class,
        )
        for candidate in candidates
    }
    metrics_by_candidate = {cid: rows for cid, (rows, _) in scored.items()}
    latency_by_candidate = {cid: latency for cid, (_, latency) in scored.items()}

    gate_reports = gate_all(
        candidates,
        metrics_by_candidate,
        latency_by_candidate,
        profile,
        contexts,
        contexts_by_candidate,
    )
    retired: dict[str, object] = dict(sweep.retired) if sweep is not None else {}
    _refuse_a_retired_survivor(retired, gate_reports)
    # A gate-only deployment (HĐ-8.4) reaches exactly the same place as a
    # field where nobody survived: a gate table and no card. Caught here
    # rather than checked before simulating, because the measurement is
    # still worth having — the hall's whole job is to say who fails on an
    # easy symmetric mission, and that answer needs the episodes run.
    gate_only: str | None = None
    try:
        evidence = score_survivors(
            candidates, gate_reports, metrics_by_candidate, profile, contexts, settings
        )
    except GateOnlyDeployment as refusal:
        gate_only = str(refusal)
        evidence = []

    # **Episode-level utility, kept per episode.** The card's number is
    # the *set* level and cannot be taken apart afterwards; the paired
    # statistics run on this one, and until now it existed only inside
    # this function. Anything downstream that needs "which episode did
    # the winner win hardest" — the E2 exemplar recipe, the E4 case
    # packet — had to either recompute the whole metric set from the
    # traces or invent a proxy. A candidate eliminated at a gate has no
    # entry, which is the honest answer: it was never scored.
    utility_by_candidate = {item.candidate_id: item.episode_utilities for item in evidence}

    # Checks that hold whether or not a card comes out. They are the
    # ones about the *measurement*; the ΔU check needs a comparison and
    # only runs when there is one.
    checks = [
        # Narrowed to the candidates still in the run: early stopping
        # gives a retired candidate genuinely fewer episodes, and that is
        # sound only because a retired candidate has failed a gate and so
        # never enters ΔU. `_refuse_a_retired_survivor` above is what
        # keeps that premise true rather than assumed.
        check_shared_contexts(
            metrics_by_candidate,
            among=[cid for cid in metrics_by_candidate if cid not in retired],
        ),
        check_gate_table(gate_reports),
        check_l_ref(metrics_by_candidate, profile.constraints.goal_tolerance_m),
        check_node_counts(metrics_by_candidate),
    ]

    report: dict[str, object] = {
        "artifact": "comparison_report",
        "identity": {
            "task_profile_id": profile.id,
            "experiment_scope": scope,
            # Carried here as well as on the manifest, because a run that
            # produces no card produces no manifest either — and that is
            # precisely the run where the question "which world was this
            # measured in?" has nowhere else to be answered.
            # `episode_context_id` does not hash the amplitudes (HĐ-3.1),
            # so two reports at the same seeds under different sigma
            # would otherwise be indistinguishable down to the context
            # ids while being two different experiments.
            "sensor_noise": profile.environment.sensor_noise.model_dump(),
            "git_sha": git_sha or resolve_git_sha(REPO_ROOT),
            "anchor_config_version": load_anchors().version,
            "created_at": created_at.isoformat(),
        },
        "sample": {
            "n_episodes": len(contexts),
            # What was asked for, beside what was measured. Without it an
            # interrupted run reads as a deliberate 245-episode run, and
            # "we chose to stop at 245" is a different claim from "the
            # machine was taken back at 245".
            "n_episodes_requested": requested,
            "interrupted": interrupted,
            "n_min_required": profile.constraints.n_min_evaluation_episodes,
            "episode_context_ids": [c.episode_context_id for c in contexts],
        },
        "early_stop": {
            "enabled": stop_early,
            "min_episodes_before_stop": floor,
            "deployment_role": profile.deployment_role,
            "gates_without_a_rule": dict(GATES_WITHOUT_A_RULE),
            "stopped": [
                {
                    "candidate_id": cid,
                    "episodes_run": len(contexts_by_candidate[cid]),
                    "episodes_planned": requested,
                    **verdict.to_json_dict(),  # type: ignore[union-attr]
                }
                for cid, verdict in retired.items()
            ],
            # The saving, stated rather than assumed. A feature that
            # trades data for hours has to make both sides visible or it
            # will be judged only on the half that is easy to see.
            "episodes_saved": sum(requested - len(contexts_by_candidate[cid]) for cid in retired),
        },
        "candidates": [
            {
                "candidate_id": candidate.candidate_id,
                "stack_label": candidate.stack_label,
                "local_controller_config": local,
                # **The stack, as fields rather than as a label.** The
                # lattice reading of E3 asks which pairs differ in
                # exactly one component, and ``stack_label`` answers
                # that only by being split on a plus sign — which works
                # until a stack name contains one, at which point the
                # comparison quietly changes meaning. Typed here, where
                # the candidate object is in scope and nothing has to
                # be inferred.
                "components": _components(candidate, local),
                # What this candidate was allowed to see. Recorded per
                # candidate because a comparison between stacks shown
                # different things is not a comparison between the
                # stacks: a controller reading the static map and one
                # reading only its LiDAR are answering different
                # questions, and the difference in their numbers is
                # mostly the difference in their inputs. Every registry
                # entry is `full_static_map` + `lidar_only` today, so
                # nothing here mixes — which is exactly why it has to be
                # written down now, before the first entry that does not
                # match makes it a silent problem.
                "global_observation_class": _observation_classes(_stack)[0],
                "local_observation_class": _observation_classes(_stack)[1],
                # Per candidate, because early stopping makes the counts
                # differ. Two success rates over different denominators
                # are not a ranking, and a reader needs the denominator
                # beside the rate to see that.
                "n_episodes": len(contexts_by_candidate[candidate.candidate_id]),
                "stopped_early": (
                    {
                        "episodes_run": len(contexts_by_candidate[candidate.candidate_id]),
                        "episodes_planned": requested,
                        **retired[candidate.candidate_id].to_json_dict(),  # type: ignore[union-attr]
                        "floor_applied": watch.floor_report(candidate.candidate_id)
                        if watch is not None
                        else None,
                    }
                    if candidate.candidate_id in retired
                    else None
                ),
                "gates": gate_reports[candidate.candidate_id].to_card(),
                "cleared_gates": gate_reports[candidate.candidate_id].passed,
                "blocking_gates": list(gate_reports[candidate.candidate_id].blocking_gates),
                "n_distinct_episodes": gate_reports[candidate.candidate_id].g2.n_distinct_episodes,
                "success_rate": sum(
                    1 for m in metrics_by_candidate[candidate.candidate_id] if m.success
                )
                / len(metrics_by_candidate[candidate.candidate_id]),
                "pooled_p99_latency_ms": latency_by_candidate[candidate.candidate_id],
                # Evidence, never a score. There is no replan budget any
                # more: the cost of replanning is time and latency, and
                # both are already charged — every replan records a
                # control-step row carrying the global planner's latency,
                # so G4 pools it. A separate penalty would price the same
                # thing twice with a weight somebody chose.
                #
                # Reported because a reader needs to tell "recovered on
                # the first try" from "replanned forty times and timed
                # out", and a bare `timeout` cannot say which.
                "replan_count": sum(
                    m.replan_count for m in metrics_by_candidate[candidate.candidate_id]
                ),
                "episodes": _episode_outcomes(
                    metrics_by_candidate[candidate.candidate_id],
                    utilities=utility_by_candidate.get(candidate.candidate_id, {}),
                ),
            }
            for candidate, (_stack, local) in zip(candidates, candidate_specs, strict=True)
        ],
        "measurement_environment": {
            "benchmark_host": host.model_dump(),
            "warning": warning,
        },
    }

    # D15: the row keeps the card and the manifest; the Parquet traces
    # stay in the artifact store behind a URI. The checksum is what makes
    # that reference trustworthy rather than decorative — a URI alone
    # cannot say the files it points at are the ones this run was
    # computed from. Carried in the report because the API stores what
    # this function returns, not what it writes to disk.
    report["run_uri"] = f"file://{destination}"
    report["run_checksum"] = trace_checksum(
        candidates, contexts, trace_root, profile, map_data, evidence_class=evidence_class
    )

    if len(evidence) < 2:
        # Not an error. "Who was eliminated where, after how many runs"
        # is the gate table's own purpose (HĐ-12), and it is the honest
        # answer when the field does not support a ranking. The fix is a
        # new candidate, never a softer deployment.
        report["decision_card"] = None
        # Present and null, not absent. A caller checking `report["manifest"]`
        # should not have to know which branch produced the report.
        report["manifest"] = None
        # Two ways to arrive here, and they call for different actions —
        # so they must not share a sentence. "Nobody survived" is fixed
        # by registering a better candidate. "This deployment cannot
        # rank" is not a thing about the candidates at all, and no new
        # candidate will ever change it.
        report["gate_only_deployment"] = gate_only
        report["why_no_card"] = (
            (
                f"{gate_only}. Deployment này là DỤNG CỤ CỔNG (HĐ-8.4): nó trả lời được ai "
                "qua/không qua, nhưng không có thang để xếp hạng, nên vĩnh viễn không có "
                "Decision Card ở đây. Bảng cổng bên dưới là toàn bộ kết quả. Muốn xếp hạng "
                "thì chạy trên deployment có ngưỡng chừa khoảng trống phía trên nó"
            )
            if gate_only is not None
            else (
                f"chỉ {len(evidence)}/{len(candidates)} candidate qua đủ sáu cổng, nên không có "
                "ΔU để tính và không có Decision Card để viết. Đây là một KẾT QUẢ, không phải "
                "lỗi: bảng cổng đã trả lời ai bị loại ở đâu sau bao nhiêu lần chạy. Lối ra hợp "
                "lệ là ĐĂNG KÝ MỘT CANDIDATE MỚI, không phải nới deployment"
            )
        )
        report["checks"] = checks
        # **A run that ranked nobody still gets a packet (E4.2).** It has
        # no pair, so no waterfall and no exemplars — but the sightings,
        # the geometry and the gate table are facts about this run, and
        # "why did it fail" is asked of exactly these runs. Building only
        # in the ranked branch meant the detectors never ran here and the
        # explanation endpoint answered 409 to the one question the run
        # provoked.
        report["case_packet"] = _explanation_packet(
            destination=destination,
            run_id=destination.name,
            profile=profile,
            map_data=map_data,
            candidates=candidates,
            contexts_by_candidate=contexts_by_candidate,
            waterfall=None,
            decision_status="NO_DECISION_CARD",
            gate_reports=gate_reports,
            trace_root=trace_root,
            evidence_class=evidence_class,
            report=report,
            say=say,
            manifest_written=False,
        )
        _write_json(destination / "comparison_report.json", report)
        _say_summary(say, report, destination)
        return report

    recommendation = recommend(evidence, seed=bootstrap_seed)
    checks.append(check_delta_u(recommendation))
    again = recommend(
        score_survivors(
            candidates, gate_reports, metrics_by_candidate, profile, contexts, settings
        ),
        seed=bootstrap_seed,
    )
    winner = next(e for e in evidence if e.candidate_id == recommendation.recommended_id)
    checks.append(
        check_reproducible(
            winner.set_objectives.decision_utility,
            next(
                e.set_objectives.decision_utility
                for e in evidence
                if e.candidate_id == again.recommended_id
            ),
        )
    )

    bundle = assemble_card(
        candidates=candidates,
        metrics_by_candidate=metrics_by_candidate,
        gate_reports=gate_reports,
        evidence=evidence,
        recommendation=recommendation,
        profile=profile,
        contexts=contexts,
        settings=settings,
        scope=scope,
        manifest_ref="manifest.json",
        provenance=Provenance(
            git_sha=git_sha or resolve_git_sha(REPO_ROOT),
            benchmark_host=host,
            created_at=created_at,
        ),
        bootstrap_seed=bootstrap_seed,
    )
    card, manifest = bundle.card, bundle.manifest
    report["decision_card"] = card.to_json_dict()
    # **Which two candidates the paired comparison was about.**
    #
    # Not derivable from the card. ``recommended`` is on it, but the
    # other half is not: ``alternative`` may only ever name a
    # PARETO_FRONTIER candidate (HĐ-12), so it is ``None`` on every run
    # that did not do a Pareto analysis — and when it is set it can be a
    # *different* candidate from the one ΔU was computed against.
    # Second-on-the-ranking and not-dominated are two claims, and the
    # card is deliberately careful not to conflate them.
    #
    # Everything downstream that shows the two runs side by side — the
    # comparison canvases, the exemplar roles, the replay alignment — is
    # about the pair the statistics used, so that pair is recorded here
    # rather than guessed at by each reader.
    report["comparison_pair"] = {
        "recommended_candidate_id": recommendation.recommended_id,
        "runner_up_candidate_id": recommendation.runner_up_id,
    }
    # Returned, not merely written beside the card. HĐ-13's acceptance
    # criterion is that somebody else rebuilds the same card *from the
    # manifest*, so a caller that keeps only the card keeps a claim it
    # cannot reproduce. Writing it to disk served the CLI, which reads
    # the directory back; the API stores what this function returns, and
    # it was silently storing a card with no manifest — a latent hole,
    # because until now no run through the API had ever been ranked.
    report["manifest"] = manifest.to_json_dict()
    report["gate_only_deployment"] = None
    report["checks"] = checks

    # **The manifest is written before the packet is built**, because the
    # packet's header names it by checksum and a checksum of bytes needs
    # the bytes. Writing the report last then keeps the ordinary
    # invariant: every file the report refers to is already on disk when
    # the report lands.
    _write_json(destination / "decision_card.json", card.to_json_dict())
    _write_json(destination / "manifest.json", manifest.to_json_dict())

    report["case_packet"] = _explanation_packet(
        destination=destination,
        run_id=destination.name,
        profile=profile,
        map_data=map_data,
        candidates=candidates,
        contexts_by_candidate=contexts_by_candidate,
        waterfall=_decomposition(evidence, recommendation, settings, bootstrap_seed, say),
        decision_status="CLEAR_RECOMMENDATION",
        gate_reports=gate_reports,
        trace_root=trace_root,
        evidence_class=evidence_class,
        report=report,
        say=say,
        manifest_written=True,
    )
    _write_json(destination / "comparison_report.json", report)
    _say_summary(say, report, destination)
    return report


def _decomposition(
    evidence: Sequence[CandidateEvidence],
    recommendation: Recommendation,
    settings: DecisionSettings,
    bootstrap_seed: int,
    say,  # type: ignore[no-untyped-def]
) -> Waterfall | None:
    """The paired ΔU decomposition, or ``None`` with the reason said out loud.

    Separated from packet assembly because the packet is now built on
    both paths and only one of them has a pair. A caller that could not
    tell "this run has no comparison" from "the decomposition failed"
    would file the second as the first.
    """
    try:
        winner = next(
            item for item in evidence if item.candidate_id == recommendation.recommended_id
        )
        runner_up = next(
            item for item in evidence if item.candidate_id == recommendation.runner_up_id
        )
        return build_waterfall(winner, runner_up, settings=settings, seed=bootstrap_seed)
    except Exception as error:  # noqa: BLE001 - a thin packet beats a lost sweep
        say(f"⚠ không dựng được waterfall cho tầng giải thích: {error!r}")
        return None


def _explanation_packet(
    *,
    destination: Path,
    run_id: str,
    profile: TaskProfile,
    map_data: MapData,
    candidates: Sequence[Candidate],
    contexts_by_candidate: Mapping[str, Sequence[EpisodeContext]],
    waterfall: Waterfall | None,
    decision_status: str,
    gate_reports: Mapping[str, object],
    trace_root: Path,
    evidence_class: str,
    report: Mapping[str, object],
    say,  # type: ignore[no-untyped-def]
    manifest_written: bool,
) -> dict[str, object]:
    """Build the analyst's case packet while the scoring pass holds its parts.

    **Here rather than behind an endpoint, and that was the decision.**
    The waterfall needs two ``CandidateEvidence`` objects and they exist
    only in this function; rebuilding them from the report later would
    put a second piece of code in the repository computing the same ΔU,
    which is the parallel source HĐ-5 forbids everywhere else. The price
    is paid in the open: the report grows a block, and a run scored
    before this has no packet and cannot be given one.

    **Called on both paths (E4.2).** ``waterfall`` is ``None`` for a run
    that ranked nobody, and the packet then carries sightings, geometry
    and a gate table with no comparison — which is what those runs have
    to say, and what somebody asking "why did it fail" opens.

    **The traces are read a second time.** Scoring already read them to
    recompute the metrics, and holding every candidate's traces in
    memory until now would cost more than re-reading a file the OS still
    has cached. Said out loud because "reads the traces twice" is the
    kind of thing that looks like an oversight in a profile.

    A failure here does not fail the run. A comparison report with no
    packet is a run somebody can still act on; a sweep that died after
    the last episode because a detector refused is hours thrown away.
    """
    try:
        locator = TraceLocator(trace_root, profile, map_data, evidence_class=evidence_class)
        traces: list[EpisodeTrace] = []
        for candidate in candidates:
            for context in contexts_by_candidate.get(candidate.candidate_id, ()):
                loaded = locator.load(candidate, context)
                events = [
                    {"index": index, "event": name}
                    for index, name in enumerate(loaded.column("event"))
                    if name
                ]
                traces.append(
                    EpisodeTrace(
                        candidate_id=candidate.candidate_id,
                        episode_context_id=context.episode_context_id,
                        columns={
                            "t": loaded.column("t"),
                            "x": loaded.column("x"),
                            "y": loaded.column("y"),
                            "clearance_m": loaded.column("clearance_m"),
                            "planner_latency_ms": loaded.column("planner_latency_ms"),
                            "events": events,
                        },
                    )
                )

        # The margin the planner's grid was inflated by, from the
        # deployment's own numbers. ``hard_clearance`` is the one figure
        # both layers are required to agree on, so the packet quotes it
        # rather than re-deriving a margin of its own — and the envelope
        # comes from the environment's declared sensor noise, the same
        # way ``nav_stack`` derives it for the grid the planner is given.
        # A profile is not the carrier of an envelope; the noise is.
        margin = (
            hard_clearance(
                profile.robot, SafetyEnvelope.for_noise(profile.environment.sensor_noise)
            )
            - profile.robot.radius
        )

        # A run with no card writes no manifest, and a header cannot name
        # a file that will not exist. Its own report is the artifact of
        # record on that path, so that is what the packet points at.
        manifest_name = "manifest.json" if manifest_written else "comparison_report.json"
        manifest_bytes = (
            (destination / "manifest.json").read_bytes()
            if manifest_written
            else json.dumps(dict(report), sort_keys=True, default=str).encode("utf-8")
        )

        built = build_scoring_packet(
            run_id=run_id,
            source_manifest_ref=manifest_name,
            source_manifest_checksum=file_checksum(manifest_bytes),
            detector_version=DETECTOR_VERSION,
            knowledge_base_version=KNOWLEDGE_BASE_VERSION,
            tool_catalog_version=TOOL_CATALOG_VERSION,
            task_profile_id=profile.id,
            robot_radius_m=profile.robot.radius,
            inflation_margin_m=max(margin, 0.0),
            decision_status=decision_status,
            waterfall=waterfall,
            report=report,
            traces=traces,
            episodes_total=max((len(rows) for rows in contexts_by_candidate.values()), default=0),
            evidence_class=evidence_class,
            gates={
                name: {"passed": bool(getattr(row, "passed", False))}
                for name, row in gate_reports.items()
            },
        )
    except Exception as error:  # noqa: BLE001 - a thin packet beats a lost sweep
        say(f"⚠ không dựng được case packet cho tầng giải thích: {error!r}")
        return {"packet": None, "skipped_episodes": [], "omissions": [repr(error)]}

    if built.omissions:
        say(f"  case packet: {len(built.omissions)} phần thiếu, ghi trong report")
    return packet_block(built)


def _interrupted_before_any_episode(
    profile: TaskProfile,
    scope: str,
    requested: int,
    created_at: datetime,
    git_sha: str | None,
    host: object,
    warning: str | None,
) -> dict[str, object]:
    """The report of a run that was stopped before one paired episode.

    There is nothing to gate and nothing to score, and it is still an
    artifact: it names the deployment, the scope and the machine, and it
    says the run was interrupted at zero. The alternative — writing
    nothing — is the behaviour that made three hours of episodes
    unreadable, applied to the case where the loss is smallest but the
    silence is exactly as total.
    """
    return {
        "artifact": "comparison_report",
        "identity": {
            "task_profile_id": profile.id,
            "experiment_scope": scope,
            "sensor_noise": profile.environment.sensor_noise.model_dump(),
            "git_sha": git_sha or resolve_git_sha(REPO_ROOT),
            "anchor_config_version": load_anchors().version,
            "created_at": created_at.isoformat(),
        },
        "sample": {
            "n_episodes": 0,
            "n_episodes_requested": requested,
            "interrupted": True,
            "n_min_required": profile.constraints.n_min_evaluation_episodes,
            "episode_context_ids": [],
        },
        "candidates": [],
        "measurement_environment": {
            "benchmark_host": host.model_dump(),  # type: ignore[attr-defined]
            "warning": warning,
        },
        "run_uri": None,
        "run_checksum": None,
        "decision_card": None,
        "manifest": None,
        "gate_only_deployment": None,
        "why_no_card": (
            f"run bị ngắt trước khi có episode nào ghép cặp đủ hai bên (xin {requested}); "
            "không có gì để chấm cổng. Bản ghi này tồn tại để lần chạy đó không biến mất"
        ),
        "checks": [],
    }


def _say_summary(say, report: dict[str, object], destination: Path) -> None:  # type: ignore[no-untyped-def]
    say("")
    for line in report["checks"]:  # type: ignore[index]
        say(f"  ✓ {line}")
    say("")
    for entry in report["candidates"]:  # type: ignore[index]
        verdict = "pass" if entry["cleared_gates"] else f"fail {entry['blocking_gates']}"
        say(
            f"  {entry['stack_label']:<14} {entry['local_controller_config']:<12} "
            f"{entry['n_distinct_episodes']:>3} distinct  "
            f"success {entry['success_rate']:>4.0%}  "
            f"p99 {entry['pooled_p99_latency_ms']:>6.2f} ms  {verdict}"
        )
    say("")
    stopped = report.get("early_stop", {}).get("stopped", [])  # type: ignore[union-attr]
    for entry in stopped:
        say(
            f"⏹ DỪNG SỚM  {entry['candidate_id']}  {entry['gate']} sau "
            f"{entry['episodes_run']}/{entry['episodes_planned']} episode — {entry['rule']}"
        )
    if stopped:
        say(f"   episode tiết kiệm: {report['early_stop']['episodes_saved']}")  # type: ignore[index]
        say("")
    sample = report["sample"]  # type: ignore[index]
    if sample.get("interrupted"):  # type: ignore[union-attr]
        say(
            f"⚠ RUN BỊ NGẮT — chấm trên {sample['n_episodes']}/"  # type: ignore[index]
            f"{sample['n_episodes_requested']} episode đã xin. "  # type: ignore[index]
            "Đây là một phép đo nhỏ hơn, không phải một lựa chọn về cỡ mẫu"
        )
        say("")
    if report["decision_card"] is None:
        say(f"KHÔNG CÓ DECISION CARD — {report['why_no_card']}")
    else:
        card = report["decision_card"]
        say(f"recommended:    {card['recommended']['candidate_id']} ({card['status']})")
    say(f"written to:     {destination}")


def run_dir_name(
    profile_id: str,
    scope: str,
    candidates: Sequence[Candidate],
    evidence_class: str = "production",
) -> str:
    """One directory per (deployment, scope, candidate set).

    The first draft used ``{profile}_compare`` for every run, and the
    second comparison of the day silently overwrote the first — two
    different questions, one directory, and the earlier answer simply
    gone. Nothing warned, because from the filesystem's point of view a
    run had merely been repeated.

    The hash is over the *candidate ids*, which already cover the stack
    and every parameter (HĐ-1.3). So re-running the same comparison
    overwrites itself, which is right, and changing any candidate lands
    somewhere else, which is also right.
    """
    fingerprint = hashlib.sha256(
        "|".join(sorted(c.candidate_id for c in candidates)).encode("utf-8")
    ).hexdigest()[:8]
    # **The evidence class is part of the directory too.** The trace
    # address grew one in H9A, but the run directory — and therefore
    # ``run_journal.jsonl`` — was still named from (profile, scope,
    # candidates) alone. A research sweep and a production sweep of the
    # same three things shared a folder and truncated each other's
    # journal: the 16-08 defect one level above the traces it was fixed
    # in. ``production`` keeps its bare name so existing run directories
    # stay where they are.
    suffix = "" if evidence_class == "production" else f"_{evidence_class}"
    return f"{profile_id}_{scope}_{fingerprint}{suffix}"


def _components(candidate: Candidate, local_config: str) -> dict[str, str] | None:
    """A modular candidate's layers, named one field each.

    ``None`` for a monolithic policy, which has no layers to swap: the
    lattice reading compares candidates that differ in exactly one
    component, and a policy is not one component of anything. Saying so
    keeps it out of those comparisons instead of giving it placeholder
    names that look swappable.
    """
    if candidate.global_planner is None or candidate.local_controller is None:
        return None
    return {
        "global_planner": candidate.global_planner.name,
        "local_controller": candidate.local_controller.name,
        "local_controller_config": local_config,
    }


def _observation_classes(stack_id: str) -> tuple[str | None, str | None]:
    """What a registry stack is shown, or ``(None, None)`` if unknown.

    Unknown rather than an assumed default: a stack the registry has
    never heard of is one whose inputs nobody has declared, and printing
    a plausible class for it would be the report inventing the one fact
    the reader is checking. The UI renders ``None`` as "not declared".
    """
    from planbench_benchmark.registry import list_algorithms

    for info in list_algorithms():
        if info.id == stack_id:
            return info.global_observation_class, info.local_observation_class
    return None, None


def _episode_outcomes(
    metrics: Sequence[EpisodeMetricSet],
    *,
    utilities: Mapping[str, float] = MappingProxyType({}),
) -> list[dict[str, object]]:
    """Which episodes this candidate passed, and how the rest failed.

    **The aggregate was never the whole answer.** ``success_rate: 0.70``
    says seventy per cent of something happened; it does not say *which*
    thirty per cent did not, nor whether they were thirty collisions or
    thirty timeouts — and those two call for different work. The numbers
    existed all along: every ``EpisodeMetricSet`` carries ``success`` and
    ``failure_reason``, and until now the report pooled them and dropped
    the rows.

    Per candidate rather than one shared table, because early stopping
    retires candidates at different episodes (HĐ-7.3 keeps the *prefix*
    paired, not the length). A shared table would have to invent blanks
    for the difference, and a blank in a results table reads as a
    measurement that came back empty rather than one never taken.

    Deliberately narrow. This is the row a reader scans to find the
    episode worth opening, not a second copy of the metric set — the
    trace endpoint serves the episode itself, and duplicating twenty
    fields per episode here would put a megabyte of restatement in front
    of them.
    """
    return [
        {
            "episode_context_id": m.episode_context_id,
            "success": m.success,
            # Null when it succeeded — not "none of the four reasons",
            # which is what an empty string here would come to mean.
            "failure_reason": m.failure_reason,
            "collision_count": m.collision_count,
            "min_clearance": m.min_clearance,
            "travel_time_s": m.travel_time_s,
            "p99_latency_ms": m.p99_latency_ms,
            # The global search's size, kept in the two columns HĐ-6
            # already separates it into. A grid search's expanded nodes
            # and a sampling planner's tree size count different things,
            # so they stay apart here and whoever reads them picks one —
            # summing them would produce a number about the units.
            #
            # Written per episode because that is the only level an
            # association between search size and search cost can be
            # made at: HĐ-5's trace carries planner latency per row and
            # no expanded-node column, and that schema is frozen.
            "peak_search_nodes": m.peak_search_nodes,
            "peak_tree_nodes": m.peak_tree_nodes,
            # Per episode as well as per candidate: a total of forty
            # replans reads very differently when it is one runaway
            # episode than when it is one replan in each of forty.
            "replan_count": m.replan_count,
            # **Episode level, not the card's number** (HĐ-9.1). The two
            # differ at U_R, where every episode is clipped, so a reader
            # averaging this column will not land on the card — which is
            # correct and is why the name says which level it is.
            #
            # Absent for a candidate that never reached scoring: a gate
            # eliminated it, and 0.0 would read as "scored, and terrible".
            "episode_decision_utility": utilities.get(m.episode_context_id),
        }
        for m in metrics
    ]


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
