"""The vertical slice: one deployment, two candidates, one decision.

CONTRACTS HĐ-15.1. One map, one mission, one robot, two candidate stacks,
30–100 paired episodes:

    trace → metrics → gates → objectives → decision_utility → CI of ΔU
          → Decision Card (JSON) + manifest

**This script is a gate, not a demo.** Everything before it was unit
tested against fabricated traces, which proves the modules agree with
their own assumptions. Only running the whole chain on real episodes can
show that the assumptions are true of the simulator — metrics that come
out all zero, two candidates that turn out identical, an ``L_ref`` that
does not match the distance actually driven. HĐ-15.2 says the methodology
stops changing after this passes, so the six acceptance checks below are
the last chance to find out it was wrong.

The checks are assertions, not printed advice: a slice that quietly
reports a broken invariant is worse than no slice, because the number it
produced looks exactly like a valid one.

Usage::

    python scripts/vertical_slice.py                 # N_min episodes, from the profile
    python scripts/vertical_slice.py --episodes 30   # smoke run; G2 will say it is one
    python scripts/vertical_slice.py --reuse-traces  # re-decide, do not re-simulate
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _package in (
    "packages/schemas",
    "packages/metrics",
    "packages/decision",
    "packages/benchmark",
    "packages/planning",
    "services/simulator",
):
    sys.path.insert(0, str(REPO_ROOT / _package))

import yaml  # noqa: E402

from planbench_benchmark.candidates import (  # noqa: E402
    LOCAL_CONTROLLER_CONFIGS,
    candidate_from_stack,
    validate_control_rate,
)
from planbench_benchmark.contexts import (  # noqa: E402
    build_evaluation_contexts,
    episode_total,
    iter_run_plan,
)
from planbench_benchmark.episode import run_contract_episode  # noqa: E402
from planbench_benchmark.hostinfo import detect_benchmark_host, unpinned_warning  # noqa: E402
from planbench_benchmark.task_map import load_task_map, validate_missions_on_map  # noqa: E402
from planbench_decision.anchors import load_anchors  # noqa: E402
from planbench_decision.candidate import (  # noqa: E402
    Candidate,
    TuningDeclaration,
    validate_experiment_scope,
)
from planbench_decision.card import (  # noqa: E402
    Provenance,
    build_decision_card,
    build_manifest,
    resolve_git_sha,
)
from planbench_decision.gates import GateReport, evaluate_gates  # noqa: E402
from planbench_decision.objectives import DecisionSettings  # noqa: E402
from planbench_decision.pareto import label_field  # noqa: E402
from planbench_decision.sensitivity import (  # noqa: E402
    ScoredField,
    anchor_stability,
    weight_stability,
)
from planbench_decision.stats import Recommendation, build_evidence, recommend  # noqa: E402
from planbench_metrics.definitions import (  # noqa: E402
    EpisodeMetricSet,
    compute_metrics,
    pooled_p99_latency_ms,
)
from planbench_schemas.episode_context import EpisodeContext  # noqa: E402
from planbench_schemas.map import MapData  # noqa: E402
from planbench_schemas.task_profile import TaskProfile  # noqa: E402
from planbench_simulator.trace import read_trace, trace_path  # noqa: E402

PROFILE_PATH = REPO_ROOT / "profiles" / "warehouse_a_v2.yaml"
DEFAULT_RUN_ROOT = REPO_ROOT / "artifacts" / "runs"

#: The one thing the slice is allowed to conclude (HĐ-1.4). Both
#: candidates run the *same* local controller with the *same* parameters,
#: so the only thing that differs is the global planner — which is what
#: makes "A* suits this deployment better than RRT*" a sentence the data
#: supports. ``validate_experiment_scope`` refuses the run if that ever
#: stops being true.
EXPERIMENT_SCOPE = "global_planner_selection"

#: Which named local controller this slice runs (see
#: :data:`~planbench_benchmark.candidates.LOCAL_CONTROLLER_CONFIGS`). It
#: is identical for both candidates, so it cannot favour either — and it
#: is a *named* configuration rather than a constant typed here, because
#: the coarse sampling was chosen for the wall clock and that makes it a
#: declared property of the candidates rather than of the script.
LOCAL_CONTROLLER = "dwa_coarse"
LOCAL_CONTROLLER_PARAMS: dict[str, object] = dict(LOCAL_CONTROLLER_CONFIGS[LOCAL_CONTROLLER])

#: Declared engineering cost (HĐ-1.6). Both stacks ship with the library
#: defaults and nobody tuned either, so both declare zero hours against
#: the same evidence — the honest statement, and one that makes the U_C
#: comparison turn on compute cost rather than on paperwork.
UNTUNED = TuningDeclaration(
    tuning_trials_used=0,
    tuning_wall_clock_h=0.0,
    n_tunable_params=len(LOCAL_CONTROLLER_PARAMS),
    evidence_log="scripts/vertical_slice.py (library defaults, no tuning run)",
)


class SliceFailure(AssertionError):
    """An HĐ-15.1 acceptance criterion did not hold."""


def load_profile(path: Path = PROFILE_PATH) -> TaskProfile:
    return TaskProfile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def build_candidates(profile: TaskProfile | None = None) -> tuple[Candidate, ...]:
    """The two stacks under comparison, differing only in their planner.

    ``profile`` is optional only so the tests that care about candidate
    identity alone need not load one; when it is given, the controller is
    checked against the deployment's T_cycle before a single episode runs.
    """
    candidates = tuple(
        candidate_from_stack(stack, params=dict(LOCAL_CONTROLLER_PARAMS)).model_copy(
            update={"tuning": UNTUNED}
        )
        for stack in ("astar+dwa", "rrtstar+dwa")
    )
    validate_experiment_scope(EXPERIMENT_SCOPE, candidates)
    if profile is not None:
        validate_control_rate(profile, candidates)
    return candidates


def simulate(
    candidates: Sequence[Candidate],
    profile: TaskProfile,
    contexts: Sequence[EpisodeContext],
    map_data: MapData,
    trace_root: Path,
    *,
    reuse: bool,
) -> None:
    """Run every (candidate, context) pair that has no trace yet.

    **Context outermost, candidate innermost** — HĐ-3.2's order, via
    :func:`iter_run_plan`, which exists to provide exactly this. Two
    reasons, and the second only became visible at 300 episodes:

    Interruption. Stop a candidate-outer sweep halfway and the first
    candidate has every episode while the last has none: nothing is
    comparable and the partial data is worthless. Stop a context-outer
    sweep halfway and both candidates have the same episodes, so the
    comparison is still valid, just smaller. Over a three-hour run that
    stops being a hypothetical.

    Machine drift. Candidate-outer puts one candidate in the first half
    of the wall clock and the other in the second, so any thermal
    throttling, background process or change of machine state lands
    entirely on one of them. HĐ-7.4 requires every candidate to run under
    the same conditions, and over ten minutes the difference was
    invisible; over three hours it is the mechanism that already
    eliminated A\\* at G4 once (contract 3.0.0). Interleaving makes both
    candidates share whatever the machine was doing, minute by minute.

    Reuse is keyed on the file existing, which is safe because the path
    is derived from the candidate id and the context id — both hashes of
    everything that could change the episode. A stale file is therefore
    a file for a configuration that no longer exists, and it simply never
    gets looked up.
    """
    total = episode_total(contexts, candidates)
    for index, (context, candidate) in enumerate(iter_run_plan(contexts, candidates), start=1):
        path = trace_path(candidate.candidate_id, context.episode_context_id, root=trace_root)
        if reuse and path.is_file():
            continue
        started = time.time()
        _, run = run_contract_episode(candidate, profile, context, map_data, root=trace_root)
        print(
            f"  {index:>4}/{total}  {candidate.stack_label:<14} "
            f"seed {context.seed:<4} {run.result.status.value:<16} "
            f"{time.time() - started:5.1f}s",
            flush=True,
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


def decide(
    candidates: Sequence[Candidate],
    metrics_by_candidate: dict[str, list[EpisodeMetricSet]],
    pooled_latency_by_candidate: dict[str, float],
    profile: TaskProfile,
    contexts: Sequence[EpisodeContext],
    settings: DecisionSettings,
    seed: int,
) -> tuple[dict[str, GateReport], list, Recommendation]:
    """Gates, then objectives, then the paired comparison — in that order.

    The order is the contract's (HĐ-7: gates run before any scoring) and
    it is load-bearing here: a candidate that fails a gate is never
    scored, so it can never appear in the ranking, so the fastest
    candidate on the board cannot win by being fast.
    """
    anchors = load_anchors().resolve(profile)
    gate_reports = {
        candidate.candidate_id: evaluate_gates(
            candidate,
            profile,
            metrics_by_candidate[candidate.candidate_id],
            contexts,
            pooled_p99_latency_ms=pooled_latency_by_candidate[candidate.candidate_id],
        )
        for candidate in candidates
    }
    evidence = [
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
    if len(evidence) < 2:
        raise SliceFailure(
            "fewer than two candidates cleared the gates, so there is no comparison to "
            "make. Gate verdicts: "
            + ", ".join(
                f"{cid}: {list(report.blocking_gates) or 'pass'}"
                for cid, report in gate_reports.items()
            )
        )
    return gate_reports, evidence, recommend(evidence, seed=seed)


# --- HĐ-15.1 acceptance ------------------------------------------------


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
            raise SliceFailure(
                f"candidate {candidate_id} ran a different context set: "
                f"{len(reference - ids)} missing, {len(ids - reference)} extra"
            )
    return f"both candidates ran the same {len(reference)} episode contexts"


def check_reproducible(first: float, second: float) -> str:
    """Criterion 2: the same inputs give the same utility to six places."""
    if round(first, 6) != round(second, 6):
        raise SliceFailure(
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
            raise SliceFailure(f"candidate {candidate_id} card is missing {missing}")
        if card["G2"]["n_runs"] < 1:
            raise SliceFailure(f"candidate {candidate_id} reports no runs behind its gates")
    return f"all six gates reported for {len(gate_reports)} candidates, with N"


def check_delta_u(recommendation: Recommendation) -> str:
    """Criterion 4: ΔU and its paired CI exist and are not NaN."""
    comparison = recommendation.comparison
    values = (comparison.delta_median, comparison.delta_mean, *comparison.ci95)
    if not all(math.isfinite(value) for value in values):
        raise SliceFailure(f"ΔU or its CI is not finite: {values}")
    low, high = comparison.ci95
    if low > high:
        raise SliceFailure(f"CI is inverted: [{low}, {high}]")
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
    (HĐ-15.1(5), tightened to this form at 2.2.1 by the first run of this
    script). ``L_ref`` is measured to the goal *point*; an episode
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
                raise SliceFailure(
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
                raise SliceFailure(
                    f"candidate {candidate_id}, episode {row.episode_context_id}: "
                    f"{row.peak_search_nodes} search nodes over {row.costmap_cells} cells"
                )
    return "peak_search_nodes ≤ costmap_cells on every episode"


def run_slice(
    *,
    episodes: int | None,
    trace_root: Path,
    run_root: Path,
    reuse: bool,
    bootstrap_seed: int,
    git_sha: str,
    created_at: datetime,
    profile_path: Path = PROFILE_PATH,
    map_base_dir: Path | None = None,
    quiet: bool = False,
) -> dict[str, object]:
    """The whole chain, plus the six checks. Returns the card as a dict."""

    def say(message: str) -> None:
        if not quiet:
            print(message, flush=True)

    profile = load_profile(profile_path)
    # Map paths in a profile are relative to the repository root, the
    # same convention the rest of the codebase uses. A caller running a
    # profile from somewhere else — a test fixture, a deployment bundle —
    # says where its files are rather than having the root guessed.
    map_data = load_task_map(profile, base_dir=map_base_dir or REPO_ROOT)
    validate_missions_on_map(profile, map_data)
    candidates = build_candidates(profile)
    contexts = build_evaluation_contexts(profile, seed_count=episodes)
    settings = DecisionSettings()

    say(
        f"profile {profile.id}: {map_data.width}×{map_data.height} cells, "
        f"{len(contexts)} contexts "
        f"(N_min = {profile.constraints.n_min_evaluation_episodes} at "
        f"{profile.constraints.collision_probability_max:.0%} accepted collision risk)"
    )
    say(f"candidates: {', '.join(c.stack_label + ' ' + c.candidate_id for c in candidates)}")

    # Measured before the run, not asserted after it: what the manifest
    # records has to be what the episodes actually got (HĐ-7.4).
    host = detect_benchmark_host()
    say(
        f"host: {host.cpu} · {host.cores_allocated}/{host.logical_cores} cores"
        + (f" (affinity {list(host.cpu_affinity)})" if host.cpu_affinity else "")
    )
    warning = unpinned_warning(host)
    if warning:
        say(f"⚠ {warning}")

    say("simulating…")
    simulate(candidates, profile, contexts, map_data, trace_root, reuse=reuse)

    say("scoring from traces…")
    scored = {
        candidate.candidate_id: score(candidate, profile, contexts, map_data, trace_root)
        for candidate in candidates
    }
    metrics_by_candidate = {cid: rows for cid, (rows, _) in scored.items()}
    pooled_latency = {cid: latency for cid, (_, latency) in scored.items()}

    gate_reports, evidence, recommendation = decide(
        candidates,
        metrics_by_candidate,
        pooled_latency,
        profile,
        contexts,
        settings,
        bootstrap_seed,
    )
    # Criterion 2 wants the same inputs to give the same number, so the
    # decision runs twice over the identical traces. Re-simulating would
    # test the simulator's determinism instead, which is a different
    # claim and is already fixed by the episode seed.
    _, _, again = decide(
        candidates,
        metrics_by_candidate,
        pooled_latency,
        profile,
        contexts,
        settings,
        bootstrap_seed,
    )

    # HĐ-11.5. Both sweeps re-score from metrics already in memory and
    # never touch the simulator, so this costs seconds on a run that cost
    # minutes — which is the whole reason the two most useful caveats on
    # the card are affordable at all.
    say("sweeping assumptions…")
    field = ScoredField.from_survivors(
        candidates,
        metrics_by_candidate,
        contexts,
        {cid: report.passed for cid, report in gate_reports.items()},
    )
    anchors_resolved = load_anchors().resolve(profile)
    weights_sweep = weight_stability(field, anchors_resolved, settings, seed=bootstrap_seed)
    anchors_sweep = anchor_stability(field, anchors_resolved, settings, seed=bootstrap_seed)
    # HĐ-10: labels, never deletions. Runs after the recommendation
    # because it does not choose the winner — it decides which of the
    # others may be offered beside it, and whether the winner itself is
    # only winning on the weights.
    pareto = label_field(evidence, seed=bootstrap_seed)

    manifest_ref = f"runs/{created_at:%Y-%m-%d}/{git_sha[:12]}/manifest.json"
    card = build_decision_card(
        recommendation,
        evidence,
        gate_reports,
        profile,
        settings,
        EXPERIMENT_SCOPE,
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
        load_anchors().resolve(profile),
        Provenance(
            git_sha=git_sha,
            benchmark_host=host,
            created_at=created_at,
        ),
        contexts,
    )

    winner = next(e for e in evidence if e.candidate_id == recommendation.recommended_id)
    checks = [
        check_shared_contexts(metrics_by_candidate),
        check_reproducible(
            winner.set_objectives.decision_utility,
            next(
                e for e in evidence if e.candidate_id == again.recommended_id
            ).set_objectives.decision_utility,
        ),
        check_gate_table(gate_reports),
        check_delta_u(recommendation),
        check_l_ref(metrics_by_candidate, profile.constraints.goal_tolerance_m),
        check_node_counts(metrics_by_candidate),
    ]

    destination = run_root / f"{created_at:%Y-%m-%d}" / git_sha[:12]
    destination.mkdir(parents=True, exist_ok=True)
    card_json = card.to_json_dict()
    _write_json(destination / "decision_card.json", card_json)
    _write_json(destination / "manifest.json", manifest.to_json_dict())

    say("")
    for index, line in enumerate(checks, start=1):
        say(f"  HĐ-15.1({index}) ✓ {line}")
    say("")
    say(f"status:         {card.status}")
    say(f"recommended:    {card.recommended.stack} ({card.recommended.candidate_id})")
    say(f"decision_utility: {card.decision_utility:.6f}")
    say(f"weight margin:  {weights_sweep.margin:.4f}{_sensitivity_note(weights_sweep)}")
    if weights_sweep.nearest_flip is not None:
        say(f"  {weights_sweep.nearest_flip.sentence}")
    say(f"anchor ±10%:    {anchors_sweep.verdict}")
    say(f"pareto:         {card.pareto_label}")
    for candidate_id, label in sorted(pareto.labels.items()):
        if candidate_id != card.recommended.candidate_id:
            say(f"  {candidate_id}: {label}")
    if card.alternative is not None:
        say(f"alternative:    {card.alternative.candidate_id}")
    say(f"written to:     {destination}")
    return card_json


def _sensitivity_note(sweep) -> str:  # type: ignore[no-untyped-def]
    """HĐ-11.5's label, printed only when it applies."""
    return f"  [{sweep.label}]" if sweep.label else ""


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--episodes",
        type=int,
        default=None,
        help=(
            "paired episodes per candidate. Defaults to N_min = ceil(3 / "
            "collision_probability_max) from the profile (HĐ-7.1) — the count is a "
            "consequence of the declared risk, not a taste setting. Pass a smaller "
            "number for a smoke run and G2 will say so."
        ),
    )
    parser.add_argument("--trace-root", type=Path, default=REPO_ROOT / "artifacts" / "traces")
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument(
        "--reuse-traces",
        action="store_true",
        help="skip episodes whose trace already exists (re-decide without re-simulating)",
    )
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--profile", type=Path, default=PROFILE_PATH)
    args = parser.parse_args(argv)

    try:
        run_slice(
            episodes=args.episodes,
            trace_root=args.trace_root,
            run_root=args.run_root,
            reuse=args.reuse_traces,
            bootstrap_seed=args.bootstrap_seed,
            git_sha=resolve_git_sha(REPO_ROOT),
            created_at=datetime.now(UTC),
            profile_path=args.profile,
        )
    except SliceFailure as failure:
        print(f"\nHĐ-15.1 acceptance FAILED: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
