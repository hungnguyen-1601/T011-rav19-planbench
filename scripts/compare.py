"""Compare any candidate set on one deployment (plan M3/M4).

``vertical_slice.py`` is an acceptance record fixed at two hardcoded
stacks; ``measure.py`` deliberately refuses to compare. This is the
general comparison, and it exists because the first real question the
platform has to answer needs three candidates rather than two:
``astar+dwa`` fails G3 on the reference hall, and the legal response is
to register another candidate — not to edit the map.

    profile + candidates -> episodes -> traces -> HĐ-6 metrics
                         -> gates -> objectives -> ΔU -> Decision Card

**A gate table is a deliverable, not a failure path.** When fewer than
two candidates clear the gates there is no ΔU to compute and no card to
write, and that is a *result*: "these stacks were eliminated here, after
this many runs" answers the deployment question. So this script writes a
``comparison_report.json`` either way and marks whether a card was
produced. A tool that only succeeded when it could rank things would put
pressure on every run to be rankable, which is the pressure that
produced a card claiming a collision bound off a single episode.

Usage::

    python scripts/compare.py                                   # the hall, two stacks
    python scripts/compare.py --candidates astar+dwa,rrtstar+dwa
    python scripts/compare.py --candidates astar+dwa:dwa_default,astar+dwa:dwa_coarse \\
                              --scope local_controller_selection
    python scripts/compare.py --profile profiles/warehouse_a_v2.yaml --episodes 300
"""

from __future__ import annotations

import argparse
import json
import sys
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
from planbench_benchmark.hostinfo import (  # noqa: E402
    apply_pinning,
    detect_benchmark_host,
    unpinned_warning,
)
from planbench_benchmark.pipeline import (  # noqa: E402
    AcceptanceFailure,
    check_delta_u,
    check_gate_table,
    check_l_ref,
    check_node_counts,
    check_reproducible,
    check_shared_contexts,
    gate_all,
    score,
    score_survivors,
)
from planbench_benchmark.pipeline import simulate as run_episodes  # noqa: E402
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
from planbench_decision.objectives import DecisionSettings  # noqa: E402
from planbench_decision.stats import recommend  # noqa: E402
from planbench_schemas.task_profile import TaskProfile  # noqa: E402

DEFAULT_PROFILE = REPO_ROOT / "profiles" / "open_hall_v2.yaml"
DEFAULT_CANDIDATES = "astar+dwa,rrtstar+dwa"
DEFAULT_LOCAL = "dwa_coarse"
DEFAULT_RUN_ROOT = REPO_ROOT / "artifacts" / "runs"

#: What the run is allowed to conclude (HĐ-1.4). Declared rather than
#: inferred: ``validate_experiment_scope`` refuses a candidate set that
#: cannot support the claim, and inferring the scope from the set would
#: turn that refusal into a rename.
DEFAULT_SCOPE = "global_planner_selection"

#: Nobody tuned anything, and both halves of that matter for U_C: the
#: declaration is zero hours, and the evidence log says where to check.
UNTUNED_EVIDENCE = "scripts/compare.py (library defaults, no tuning run)"

CompareFailure = AcceptanceFailure


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

    Two refusals happen here rather than after hours of simulation:
    ``validate_experiment_scope`` on whether the set can support the
    declared claim (HĐ-1.4), and ``validate_control_rate`` on whether
    each controller keeps up with the deployment's T_cycle — which G4
    cannot see, since it times one call and never counts them.
    """
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

    say("simulating…")
    run_episodes(candidates, profile, contexts, map_data, trace_root, reuse=reuse, say=say)

    say("scoring from traces…")
    scored = {
        candidate.candidate_id: score(candidate, profile, contexts, map_data, trace_root)
        for candidate in candidates
    }
    metrics_by_candidate = {cid: rows for cid, (rows, _) in scored.items()}
    latency_by_candidate = {cid: latency for cid, (_, latency) in scored.items()}

    gate_reports = gate_all(
        candidates, metrics_by_candidate, latency_by_candidate, profile, contexts
    )
    evidence = score_survivors(
        candidates, gate_reports, metrics_by_candidate, profile, contexts, settings
    )

    # Checks that hold whether or not a card comes out. They are the
    # ones about the *measurement*; the ΔU check needs a comparison and
    # only runs when there is one.
    checks = [
        check_shared_contexts(metrics_by_candidate),
        check_gate_table(gate_reports),
        check_l_ref(metrics_by_candidate, profile.constraints.goal_tolerance_m),
        check_node_counts(metrics_by_candidate),
    ]

    report: dict[str, object] = {
        "artifact": "comparison_report",
        "identity": {
            "task_profile_id": profile.id,
            "experiment_scope": scope,
            "git_sha": git_sha or resolve_git_sha(REPO_ROOT),
            "anchor_config_version": load_anchors().version,
            "created_at": created_at.isoformat(),
        },
        "sample": {
            "n_episodes": len(contexts),
            "n_min_required": profile.constraints.n_min_evaluation_episodes,
            "episode_context_ids": [c.episode_context_id for c in contexts],
        },
        "candidates": [
            {
                "candidate_id": candidate.candidate_id,
                "stack_label": candidate.stack_label,
                "local_controller_config": local,
                "gates": gate_reports[candidate.candidate_id].to_card(),
                "cleared_gates": gate_reports[candidate.candidate_id].passed,
                "blocking_gates": list(gate_reports[candidate.candidate_id].blocking_gates),
                "n_distinct_episodes": gate_reports[candidate.candidate_id].g2.n_distinct_episodes,
                "success_rate": sum(
                    1 for m in metrics_by_candidate[candidate.candidate_id] if m.success
                )
                / len(metrics_by_candidate[candidate.candidate_id]),
                "pooled_p99_latency_ms": latency_by_candidate[candidate.candidate_id],
            }
            for candidate, (_stack, local) in zip(candidates, candidate_specs, strict=True)
        ],
        "measurement_environment": {
            "benchmark_host": host.model_dump(),
            "warning": warning,
        },
    }

    destination = run_root / created_at.strftime("%Y-%m-%d") / f"{profile.id}_compare"
    destination.mkdir(parents=True, exist_ok=True)

    if len(evidence) < 2:
        # Not an error. "Who was eliminated where, after how many runs"
        # is the gate table's own purpose (HĐ-12), and it is the honest
        # answer when the field does not support a ranking. The fix is a
        # new candidate, never a softer deployment.
        report["decision_card"] = None
        report["why_no_card"] = (
            f"chỉ {len(evidence)}/{len(candidates)} candidate qua đủ sáu cổng, nên không có "
            "ΔU để tính và không có Decision Card để viết. Đây là một KẾT QUẢ, không phải "
            "lỗi: bảng cổng đã trả lời ai bị loại ở đâu sau bao nhiêu lần chạy. Lối ra hợp "
            "lệ là ĐĂNG KÝ MỘT CANDIDATE MỚI, không phải nới deployment"
        )
        report["checks"] = checks
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

    manifest = build_manifest(
        recommendation,
        evidence,
        gate_reports,
        profile,
        settings,
        load_anchors().resolve(profile),
        Provenance(
            git_sha=git_sha or resolve_git_sha(REPO_ROOT),
            benchmark_host=host,
            created_at=created_at,
        ),
        contexts,
    )
    card = build_decision_card(
        recommendation,
        evidence,
        gate_reports,
        profile,
        settings,
        scope,  # type: ignore[arg-type]
        manifest_ref="manifest.json",
    )
    report["decision_card"] = card.to_json_dict()
    report["checks"] = checks
    _write_json(destination / "comparison_report.json", report)
    _write_json(destination / "decision_card.json", card.to_json_dict())
    _write_json(destination / "manifest.json", manifest.to_json_dict())
    _say_summary(say, report, destination)
    return report


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
    if report["decision_card"] is None:
        say(f"KHÔNG CÓ DECISION CARD — {report['why_no_card']}")
    else:
        card = report["decision_card"]
        say(f"recommended:    {card['recommended']['candidate_id']} ({card['status']})")
    say(f"written to:     {destination}")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument(
        "--candidates",
        default=DEFAULT_CANDIDATES,
        help="comma-separated 'stack[:local_config]', e.g. 'astar+dwa,astar+dwa:dwa_default'",
    )
    parser.add_argument(
        "--local", default=DEFAULT_LOCAL, help="local config for entries without one"
    )
    parser.add_argument("--scope", default=DEFAULT_SCOPE)
    parser.add_argument(
        "--episodes",
        type=int,
        default=None,
        help=(
            "paired episodes per candidate. Defaults to N_min from the profile (HĐ-7.1) — "
            "the count is a consequence of the declared risk, not a taste setting."
        ),
    )
    parser.add_argument("--trace-root", type=Path, default=REPO_ROOT / "artifacts" / "traces")
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--reuse-traces", action="store_true")
    parser.add_argument("--bootstrap-seed", type=int, default=0)
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

    specs = parse_candidates(args.candidates, args.local)
    affinity_source, pin_message = apply_pinning(args.pin_cores)
    if pin_message and not args.quiet:
        print(pin_message, flush=True)

    try:
        run_comparison(
            profile_path=args.profile,
            candidate_specs=specs,
            scope=args.scope,
            episodes=args.episodes,
            trace_root=args.trace_root,
            run_root=args.run_root,
            reuse=args.reuse_traces,
            bootstrap_seed=args.bootstrap_seed,
            quiet=args.quiet,
            affinity_source=affinity_source,
        )
    except CompareFailure as failure:
        print(f"\nacceptance criterion failed: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
