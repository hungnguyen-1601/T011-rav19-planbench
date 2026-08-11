"""Measure **one** candidate on one deployment (plan F1).

This is not a smaller vertical slice. It produces a different artifact
for a different question, and the difference is the whole point.

``vertical_slice.py`` ends in a Decision Card, which is the artifact of a
**comparison**: ΔU, a paired confidence interval, CLEAR / NEAR_EQUIVALENT,
an ``alternative`` drawn from the Pareto frontier. Not one of those means
anything for a single candidate. Forcing a card out of one would fill
every field, look entirely normal, and state something the data cannot
support — which is exactly the failure the hundred-episode warehouse run
produced, and exactly what the platform exists to prevent.

So this script stops at the measurement and says so::

    profile + candidate -> episodes -> traces -> HĐ-6 metrics
                        -> G1..G6 -> four objectives -> measurement_report.json

The report carries ``decision_utility`` because it is a real property of
one candidate on one anchor scale, and because F4 should not have to
change the format to start comparing. It carries no recommendation, and
a test forbids the vocabulary of one.

**A failing gate is a result here, not an error.** The reference hall has
no moving traffic on purpose, so a deterministic stack replays one
episode per seed, G2 finds an effective sample size below ``N_min`` and
refuses to bound the collision probability. That is the system working.
Reading that red as something to fix by adding traffic until the numbers
look usable is the exact loop this plan was written to break.

Usage::

    python scripts/measure.py                          # hall, rrtstar+dwa, N_min episodes
    python scripts/measure.py --episodes 30            # smoke run; G2 will say it is one
    python scripts/measure.py --candidate astar+dwa
    python scripts/measure.py --local dwa_default      # the 20x40 sampling
    python scripts/measure.py --profile profiles/warehouse_a_v2.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _package in (
    "packages/schemas",
    "packages/benchmark",
    "packages/decision",
    "packages/metrics",
    "packages/planning",
    "services/simulator",
    "ml",
):
    sys.path.insert(0, str(REPO_ROOT / _package))

import yaml  # noqa: E402

from planbench_benchmark.candidates import (  # noqa: E402
    LOCAL_CONTROLLER_CONFIGS,
    candidate_from_stack,
    validate_control_rate,
)
from planbench_benchmark.contexts import build_evaluation_contexts  # noqa: E402
from planbench_benchmark.episode import run_contract_episode  # noqa: E402
from planbench_benchmark.hostinfo import (  # noqa: E402
    apply_pinning,
    detect_benchmark_host,
    unpinned_warning,
)
from planbench_benchmark.task_map import load_task_map, validate_missions_on_map  # noqa: E402
from planbench_decision.anchors import load_anchors  # noqa: E402
from planbench_decision.candidate import Candidate, TuningDeclaration  # noqa: E402
from planbench_decision.card import resolve_git_sha  # noqa: E402
from planbench_decision.gates import evaluate_gates  # noqa: E402
from planbench_decision.objectives import DecisionSettings  # noqa: E402
from planbench_decision.stats import build_evidence  # noqa: E402
from planbench_metrics.definitions import (  # noqa: E402
    EpisodeMetricSet,
    compute_metrics,
    pooled_p99_latency_ms,
)
from planbench_schemas.episode_context import EpisodeContext  # noqa: E402
from planbench_schemas.map import MapData  # noqa: E402
from planbench_schemas.task_profile import TaskProfile  # noqa: E402
from planbench_simulator.trace import read_trace, trace_path  # noqa: E402

#: ``v2``, not ``v1``. The quiet hall is a measuring instrument for the
#: fairness suite — deterministic on purpose, so those tests can compare
#: two runs step by step. Measuring a candidate there gives one episode
#: replayed once per seed, which is a real answer to the wrong question.
#: The deployment to measure on is the one that declares the vehicle's
#: noise (HĐ-2.5).
DEFAULT_PROFILE = REPO_ROOT / "profiles" / "open_hall_v2.yaml"
DEFAULT_CANDIDATE = "rrtstar+dwa"
DEFAULT_LOCAL = "dwa_coarse"

#: The sentence the report leads with, and the reason this artifact is
#: not a Decision Card. A single utility has no scale of its own: it is a
#: position on the anchor scale of one deployment, and nothing about it
#: says whether some other stack sits higher.
NOT_A_RECOMMENDATION = (
    "Đây là phép ĐO một candidate, không phải một phép SO. Một mình "
    "decision_utility không nói candidate này tốt hay nên dùng — nó là vị trí trên "
    "thang anchor của deployment này. Muốn có khuyến nghị thì cần ít nhất hai "
    "candidate và một Decision Card (HĐ-12)."
)

#: Declared engineering cost (HĐ-1.6). Library defaults, nobody tuned
#: anything, so the declaration is zero against evidence that says why.
UNTUNED = TuningDeclaration(
    tuning_trials_used=0,
    tuning_wall_clock_h=0.0,
    n_tunable_params=len(LOCAL_CONTROLLER_CONFIGS[DEFAULT_LOCAL]),
    evidence_log="scripts/measure.py (library defaults, no tuning run)",
)


class MeasurementFailure(AssertionError):
    """An F1 acceptance criterion did not hold."""


def load_profile(path: Path) -> TaskProfile:
    return TaskProfile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def build_candidate(profile: TaskProfile, stack: str, local: str) -> Candidate:
    """One candidate, checked against the deployment before it runs.

    ``validate_control_rate`` is not ceremony at N=1 either: a controller
    slower than the deployment's ``control_period`` passes G4 — which
    times one call and never counts them — while missing deadlines.
    """
    if local not in LOCAL_CONTROLLER_CONFIGS:
        raise SystemExit(
            f"unknown local controller {local!r}; known: {sorted(LOCAL_CONTROLLER_CONFIGS)}"
        )
    candidate = candidate_from_stack(
        stack, params=dict(LOCAL_CONTROLLER_CONFIGS[local])
    ).model_copy(update={"tuning": UNTUNED})
    validate_control_rate(profile, [candidate])
    return candidate


def simulate(
    candidate: Candidate,
    profile: TaskProfile,
    contexts: Sequence[EpisodeContext],
    map_data: MapData,
    trace_root: Path,
    *,
    reuse: bool,
    say,  # type: ignore[no-untyped-def]
) -> None:
    for index, context in enumerate(contexts, start=1):
        path = trace_path(candidate.candidate_id, context.episode_context_id, root=trace_root)
        if reuse and path.is_file():
            continue
        started = time.time()
        _, run = run_contract_episode(candidate, profile, context, map_data, root=trace_root)
        say(
            f"  {index:>4}/{len(contexts)}  seed {context.seed:<4} "
            f"{run.result.status.value:<16} {time.time() - started:5.1f}s"
        )


def score(
    candidate: Candidate,
    profile: TaskProfile,
    contexts: Sequence[EpisodeContext],
    map_data: MapData,
    trace_root: Path,
) -> tuple[list[EpisodeMetricSet], float]:
    """Recompute every HĐ-6 metric from the files, never from memory.

    Same shape as the slice's ``score``, and for the same reason: HĐ-5
    makes the trace the single source of truth, and the only way to know
    that holds is to throw away what the simulation had in hand.
    """
    traces = [
        read_trace(trace_path(candidate.candidate_id, context.episode_context_id, root=trace_root))
        for context in contexts
    ]
    metrics = [
        compute_metrics(
            trace, profile, context, map_data, resource_profile=candidate.resource_profile
        )
        for trace, context in zip(traces, contexts, strict=True)
    ]
    return metrics, pooled_p99_latency_ms(traces)


def check_l_ref(metrics: Sequence[EpisodeMetricSet], goal_tolerance_m: float) -> str:
    """``L_ref`` ≤ driven path + goal tolerance, on successful episodes.

    The slack is the tolerance ball's radius and nothing more: ``L_ref``
    measures to the goal *point*, an episode succeeds on entering the
    ball around it (HĐ-15.1(5), as tightened at contract 2.2.1).
    """
    checked = 0
    for row in metrics:
        if not row.success:
            continue
        checked += 1
        if row.l_ref_m > row.path_length_m + goal_tolerance_m + 1e-9:
            raise MeasurementFailure(
                f"episode {row.episode_context_id}: L_ref {row.l_ref_m:.3f} m exceeds the "
                f"driven path {row.path_length_m:.3f} m by more than the goal tolerance "
                f"{goal_tolerance_m:.3f} m"
            )
    return f"L_ref ≤ path_length + tolerance on all {checked} successful episodes"


def check_reproducible(first: float, second: float) -> str:
    """Scoring the same traces twice gives the same number to 6 places."""
    if round(first, 6) != round(second, 6):
        raise MeasurementFailure(f"re-scoring the same traces gave {second:.6f}, not {first:.6f}")
    return f"decision_utility reproducible to 6 dp ({first:.6f})"


def check_gate_table(report) -> str:  # type: ignore[no-untyped-def]
    """All six gates present with their run counts (HĐ-15.1(3))."""
    payload = report.to_card()
    missing = [gate for gate in ("G1", "G2", "G3", "G4", "G5", "G6") if gate not in payload]
    if missing:
        raise MeasurementFailure(f"gate report is missing {missing}")
    return "gate table carries all six gates"


def check_node_counts(metrics: Sequence[EpisodeMetricSet]) -> str:
    """``peak_search_nodes`` ≤ ``costmap_cells`` (HĐ-15.1(6))."""
    for row in metrics:
        if row.peak_search_nodes > row.costmap_cells:
            raise MeasurementFailure(
                f"episode {row.episode_context_id}: {row.peak_search_nodes} search nodes "
                f"on a {row.costmap_cells}-cell costmap"
            )
    return "peak_search_nodes ≤ costmap_cells on every episode"


def build_report(
    *,
    candidate: Candidate,
    local: str,
    profile: TaskProfile,
    contexts: Sequence[EpisodeContext],
    metrics: Sequence[EpisodeMetricSet],
    pooled_latency_ms: float,
    gate_report,  # type: ignore[no-untyped-def]
    evidence,  # type: ignore[no-untyped-def]
    host,  # type: ignore[no-untyped-def]
    git_sha: str,
    anchor_version: str,
    created_at: datetime,
) -> dict[str, object]:
    """The Measurement Report: what was measured, and how far it reaches."""
    successes = [m for m in metrics if m.success]
    return {
        "artifact": "measurement_report",
        "note": NOT_A_RECOMMENDATION,
        "identity": {
            "task_profile_id": profile.id,
            "candidate_id": candidate.candidate_id,
            "stack_label": candidate.stack_label,
            "local_controller_config": local,
            "git_sha": git_sha,
            "anchor_config_version": anchor_version,
            "created_at": created_at.isoformat(),
        },
        "sample": {
            "n_episodes": len(metrics),
            # Both counts, always. The bound's denominator alone hides a
            # replayed set; the row count alone is what printed a 3.0%
            # bound off one episode driven a hundred times.
            "n_distinct_episodes": gate_report.g2.n_distinct_episodes,
            "n_min_required": profile.constraints.n_min_evaluation_episodes,
            "episode_context_ids": [c.episode_context_id for c in contexts],
        },
        "outcomes": {
            "success_rate": len(successes) / len(metrics),
            "by_status": _status_counts(metrics),
        },
        "metrics": {
            "pooled_p99_latency_ms": pooled_latency_ms,
            "per_episode": [_metric_row(m) for m in metrics],
        },
        "gates": gate_report.to_card(),
        "objectives": {
            "set_level": evidence.set_objectives.model_dump(),
            "per_episode": {
                context_id: breakdown.model_dump()
                for context_id, breakdown in evidence.episode_objectives.items()
            },
        },
        "measurement_environment": {
            "benchmark_host": host.model_dump(),
            "warning": unpinned_warning(host),
        },
    }


def _status_counts(metrics: Sequence[EpisodeMetricSet]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in metrics:
        key = "success" if row.success else (row.failure_reason or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _metric_row(row: EpisodeMetricSet) -> dict[str, object]:
    """One episode, every HĐ-6 field the report promises."""
    return {
        "episode_context_id": row.episode_context_id,
        "success": row.success,
        "failure_reason": row.failure_reason,
        "collision_count": row.collision_count,
        "path_length_m": row.path_length_m,
        "l_ref_m": row.l_ref_m,
        "path_efficiency": row.path_efficiency,
        "travel_time_s": row.travel_time_s,
        "time_efficiency": row.time_efficiency,
        "min_clearance": row.min_clearance,
        "near_miss_rate": row.near_miss_rate,
        "p99_latency_ms": row.p99_latency_ms,
        "memory_estimate_mb": row.memory_estimate_mb,
        "cpu_time_per_mission_s": row.cpu_time_per_mission_s,
        "smoothness": row.smoothness,
        "stop_and_go_count": row.stop_and_go_count,
    }


def run_measurement(
    *,
    profile_path: Path,
    stack: str,
    local: str,
    episodes: int | None,
    trace_root: Path,
    run_root: Path,
    reuse: bool,
    quiet: bool = False,
    map_base_dir: Path | None = None,
    affinity_source: str | None = None,
) -> dict[str, object]:
    def say(message: str) -> None:
        if not quiet:
            print(message, flush=True)

    profile = load_profile(profile_path)
    map_data = load_task_map(profile, base_dir=map_base_dir or REPO_ROOT)
    validate_missions_on_map(profile, map_data)
    candidate = build_candidate(profile, stack, local)
    contexts = build_evaluation_contexts(profile, seed_count=episodes)
    settings = DecisionSettings()

    say(
        f"profile {profile.id}: {map_data.width}×{map_data.height} cells, "
        f"{len(contexts)} contexts "
        f"(N_min = {profile.constraints.n_min_evaluation_episodes} at "
        f"{profile.constraints.collision_probability_max:.0%} accepted collision risk)"
    )
    say(f"candidate: {candidate.stack_label} · {local} · {candidate.candidate_id}")

    host = detect_benchmark_host(affinity_source=affinity_source)  # type: ignore[arg-type]
    say(
        f"host: {host.cpu} · {host.cores_allocated}/{host.logical_cores} cores"
        + (f" (affinity {list(host.cpu_affinity)})" if host.cpu_affinity else "")
    )
    warning = unpinned_warning(host)
    if warning:
        say(f"⚠ {warning}")

    say("simulating…")
    simulate(candidate, profile, contexts, map_data, trace_root, reuse=reuse, say=say)

    say("scoring from traces…")
    metrics, pooled_latency_ms = score(candidate, profile, contexts, map_data, trace_root)
    anchors = load_anchors()
    resolved = anchors.resolve(profile)
    gate_report = evaluate_gates(
        candidate, profile, metrics, contexts, pooled_p99_latency_ms=pooled_latency_ms
    )
    evidence = build_evidence(candidate, metrics, contexts, resolved, settings)

    # Criterion 4 wants reproducibility of the *scoring*, so the second
    # pass re-reads the traces rather than reusing the objects above.
    again_metrics, _ = score(candidate, profile, contexts, map_data, trace_root)
    again = build_evidence(candidate, again_metrics, contexts, resolved, settings)

    checks = [
        check_l_ref(metrics, profile.constraints.goal_tolerance_m),
        check_reproducible(
            evidence.set_objectives.decision_utility, again.set_objectives.decision_utility
        ),
        check_gate_table(gate_report),
        check_node_counts(metrics),
    ]

    created_at = datetime.now(UTC)
    report = build_report(
        candidate=candidate,
        local=local,
        profile=profile,
        contexts=contexts,
        metrics=metrics,
        pooled_latency_ms=pooled_latency_ms,
        gate_report=gate_report,
        evidence=evidence,
        host=host,
        git_sha=resolve_git_sha(REPO_ROOT),
        anchor_version=anchors.version,
        created_at=created_at,
    )

    destination = (
        run_root / created_at.strftime("%Y-%m-%d") / f"{profile.id}_{candidate.candidate_id}"
    )
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "measurement_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    say("")
    for line in checks:
        say(f"  ✓ {line}")
    say("")
    say(f"episodes:       {len(metrics)} run, {gate_report.g2.n_distinct_episodes} distinct")
    say(f"success rate:   {report['outcomes']['success_rate']:.0%}")  # type: ignore[index]
    say(f"pooled p99:     {pooled_latency_ms:.2f} ms (G4 threshold {profile.robot.t_cycle_ms})")
    for gate in ("G1", "G2", "G3", "G4", "G5", "G6"):
        say(f"  {gate}: {_gate_line(gate_report.to_card()[gate])}")
    say(f"utility:        {evidence.set_objectives.decision_utility:.6f}")
    say(f"written to:     {path}")
    say("")
    say(NOT_A_RECOMMENDATION)
    return report


def _gate_line(entry: object) -> str:
    if isinstance(entry, dict):
        result = entry.get("result", "?")
        note = entry.get("note") or entry.get("statement") or ""
        return f"{result}" + (f" — {note}" if note else "")
    return str(entry)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE, help="registry stack id")
    parser.add_argument(
        "--local",
        default=DEFAULT_LOCAL,
        choices=sorted(LOCAL_CONTROLLER_CONFIGS),
        help="named local-controller configuration",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=None,
        help=(
            "episodes to run. Defaults to N_min = ceil(3 / collision_probability_max) "
            "from the profile (HĐ-7.1). Pass a smaller number for a smoke run and G2 "
            "will say so."
        ),
    )
    parser.add_argument("--trace-root", type=Path, default=REPO_ROOT / "artifacts" / "traces")
    parser.add_argument("--run-root", type=Path, default=REPO_ROOT / "artifacts" / "runs")
    parser.add_argument("--reuse-traces", action="store_true")
    # Pinning defaults to on: G4 reads wall-clock latency, and the same
    # stack measured 59.30 ms unpinned against 16.10 ms on two cores. A
    # protection that depends on remembering a flag protects the runs
    # where it was remembered.
    parser.add_argument("--pin-cores", type=int, default=2, dest="pin_cores")
    parser.add_argument(
        "--no-pin",
        action="store_const",
        const=None,
        dest="pin_cores",
        help="run unpinned, or pin externally with taskset and say so here",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    affinity_source, pin_message = apply_pinning(args.pin_cores)
    if pin_message and not args.quiet:
        print(pin_message, flush=True)

    try:
        run_measurement(
            profile_path=args.profile,
            stack=args.candidate,
            local=args.local,
            episodes=args.episodes,
            trace_root=args.trace_root,
            run_root=args.run_root,
            reuse=args.reuse_traces,
            quiet=args.quiet,
            affinity_source=affinity_source,
        )
    except MeasurementFailure as failure:
        print(f"\nF1 acceptance criterion failed: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
