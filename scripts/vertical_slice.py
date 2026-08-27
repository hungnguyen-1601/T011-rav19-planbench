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
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _package in (
    "packages/schemas",
    "packages/metrics",
    "packages/decision",
    "packages/explanation",
    "packages/plugin_sdk",
    "packages/benchmark",
    "packages/planning",
    "services/simulator",
    "services/tracking",
    "services/agent_service",
    "services/analyst_service",
    "ml",
    "apps/api",
    "apps/desktop",
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
    # Re-exported, not used here: the chain moved to
    # ``planbench_benchmark.pipeline`` but ``iter_run_plan`` is the rule
    # this script is judged on (HĐ-3.2's context-outer order), and
    # ``tests/test_vertical_slice.py`` reaches for it through this module.
    iter_run_plan,  # noqa: F401
)
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
    decide,
    score,
    simulate,
)
from planbench_benchmark.selection import assemble_card  # noqa: E402
from planbench_benchmark.task_map import load_task_map, validate_missions_on_map  # noqa: E402
from planbench_decision.candidate import (  # noqa: E402
    Candidate,
    TuningDeclaration,
    validate_experiment_scope,
)
from planbench_decision.card import (  # noqa: E402
    Provenance,
    resolve_git_sha,
)
from planbench_decision.objectives import DecisionSettings  # noqa: E402
from planbench_schemas.task_profile import TaskProfile  # noqa: E402

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


#: HĐ-15.1's name for the failure. The chain raises
#: :class:`~planbench_benchmark.pipeline.AcceptanceFailure`; this is the
#: same class under the name this script's criteria are numbered by, so
#: ``except SliceFailure`` keeps working and nobody has to catch two
#: types for one event.
SliceFailure = AcceptanceFailure


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
    affinity_source: str | None = None,
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
    host = detect_benchmark_host(affinity_source=affinity_source)  # type: ignore[arg-type]
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
    #
    # Assembled by the shared step rather than here: this script and
    # ``run_comparison`` used to build the card separately, and the one
    # that did it without these sweeps produced the project's first
    # Decision Card with both stability fields null.
    say("sweeping assumptions…")
    bundle = assemble_card(
        candidates=candidates,
        metrics_by_candidate=metrics_by_candidate,
        gate_reports=gate_reports,
        evidence=evidence,
        recommendation=recommendation,
        profile=profile,
        contexts=contexts,
        settings=settings,
        scope=EXPERIMENT_SCOPE,
        manifest_ref=f"runs/{created_at:%Y-%m-%d}/{git_sha[:12]}/manifest.json",
        provenance=Provenance(
            git_sha=git_sha,
            benchmark_host=host,
            created_at=created_at,
        ),
        bootstrap_seed=bootstrap_seed,
    )
    card, manifest = bundle.card, bundle.manifest
    weights_sweep, anchors_sweep, pareto = (
        bundle.weight_stability,
        bundle.anchor_stability,
        bundle.pareto,
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
    # On by default. HĐ-7.4 asks every candidate to run under the same
    # CPU allocation, and contract 3.0.0 records A* being eliminated at
    # G4 for the machine's behaviour rather than its own.
    parser.add_argument("--pin-cores", type=int, default=2, dest="pin_cores")
    parser.add_argument(
        "--no-pin",
        action="store_const",
        const=None,
        dest="pin_cores",
        help="run unpinned, or pin externally with taskset and say so here",
    )
    args = parser.parse_args(argv)

    affinity_source, pin_message = apply_pinning(args.pin_cores)
    if pin_message:
        print(pin_message, flush=True)

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
            affinity_source=affinity_source,
        )
    except SliceFailure as failure:
        print(f"\nHĐ-15.1 acceptance FAILED: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
