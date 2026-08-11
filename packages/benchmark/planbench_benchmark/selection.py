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
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import yaml

from planbench_benchmark.candidates import (
    LOCAL_CONTROLLER_CONFIGS,
    candidate_from_stack,
    validate_control_rate,
)
from planbench_benchmark.contexts import build_evaluation_contexts
from planbench_benchmark.hostinfo import detect_benchmark_host, unpinned_warning
from planbench_benchmark.pipeline import (
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
from planbench_benchmark.pipeline import simulate as run_episodes
from planbench_benchmark.task_map import load_task_map, validate_missions_on_map
from planbench_decision.anchors import load_anchors
from planbench_decision.candidate import (
    Candidate,
    TuningDeclaration,
    validate_experiment_scope,
)
from planbench_decision.card import (
    Provenance,
    build_decision_card,
    build_manifest,
    resolve_git_sha,
)
from planbench_decision.objectives import DecisionSettings
from planbench_decision.stats import recommend
from planbench_schemas.task_profile import TaskProfile

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
    "build_candidates",
    "load_profile",
    "parse_candidates",
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

    destination = run_root / created_at.strftime("%Y-%m-%d") / run_dir_name(
        profile.id, scope, candidates
    )
    destination.mkdir(parents=True, exist_ok=True)

    if len(evidence) < 2:
        # Not an error. "Who was eliminated where, after how many runs"
        # is the gate table's own purpose (HĐ-12), and it is the honest
        # answer when the field does not support a ranking. The fix is a
        # new candidate, never a softer deployment.
        report["decision_card"] = None
        # Present and null, not absent. A caller checking `report["manifest"]`
        # should not have to know which branch produced the report.
        report["manifest"] = None
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
    # Returned, not merely written beside the card. HĐ-13's acceptance
    # criterion is that somebody else rebuilds the same card *from the
    # manifest*, so a caller that keeps only the card keeps a claim it
    # cannot reproduce. Writing it to disk served the CLI, which reads
    # the directory back; the API stores what this function returns, and
    # it was silently storing a card with no manifest — a latent hole,
    # because until now no run through the API had ever been ranked.
    report["manifest"] = manifest.to_json_dict()
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


def run_dir_name(profile_id: str, scope: str, candidates: Sequence[Candidate]) -> str:
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
    return f"{profile_id}_{scope}_{fingerprint}"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


