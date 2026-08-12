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

**There is a second way to get no card, and it is not the same one.** A
deployment that sets a gated metric's threshold at the ideal collapses
that anchor's scale onto ``good`` and cannot rank at all — it measures,
it gates, and no candidate would ever change that (HĐ-8.4). The report
says which situation it is in ``gate_only_deployment``, separately from
``why_no_card``, because the two ask for opposite responses: "nobody
survived" invites a better candidate, "this deployment cannot rank" says
no candidate ever will. No shipped profile is in that state today — both
halls declare ``success_rate_min: 0.95`` — but the hall was there for a
day, and ``docs/KNOWN_LIMITATIONS.md`` L6 says why it may be again.

Usage::

    python scripts/compare.py                                   # the hall, two stacks
    python scripts/compare.py --candidates astar+dwa,rrtstar+dwa
    python scripts/compare.py --candidates astar+dwa:dwa_default,astar+dwa:dwa_coarse \\
                              --scope local_controller_selection
    python scripts/compare.py --profile profiles/warehouse_a_v2.yaml --episodes 300
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
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


from planbench_benchmark.hostinfo import (  # noqa: E402
    apply_pinning,
)
from planbench_benchmark.pipeline import AcceptanceFailure  # noqa: E402
from planbench_benchmark.selection import (  # noqa: E402
    DEFAULT_SCOPE,
    parse_candidates,
    run_comparison,
)

DEFAULT_PROFILE = REPO_ROOT / "profiles" / "open_hall_v2.yaml"
DEFAULT_CANDIDATES = "astar+dwa,rrtstar+dwa"
DEFAULT_LOCAL = "dwa_coarse"
DEFAULT_RUN_ROOT = REPO_ROOT / "artifacts" / "runs"

CompareFailure = AcceptanceFailure


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
    parser.add_argument(
        "--score-only",
        action="store_true",
        help=(
            "do not simulate: score whatever paired episodes are already on disk. This is "
            "how a run killed mid-sweep gets its gate table — the report says how many of "
            "the requested episodes it actually covers"
        ),
    )
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--pin-cores", type=int, default=2, dest="pin_cores")
    parser.add_argument(
        "--no-pin",
        action="store_const",
        const=None,
        dest="pin_cores",
        help="run unpinned, or pin externally with taskset and say so here",
    )
    parser.add_argument(
        "--stop-early",
        action="store_true",
        help=(
            "retire a candidate as soon as arithmetic proves it cannot pass a gate. OFF by "
            "default: a saving has to be asked for. Turning it on trades distribution for "
            "hours — on the first warehouse run both stacks were doomed by episode 12 of "
            "600, and stopping there would have cost the findings that mattered. Refused "
            "on an acceptance deployment"
        ),
    )
    parser.add_argument(
        "--min-episodes-before-stop",
        type=int,
        default=None,
        help=(
            "episodes every candidate runs before --stop-early may retire it. Flag beats "
            "profile beats the default of 30; the value used is written to the report"
        ),
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
            score_only=args.score_only,
            stop_early=args.stop_early,
            min_episodes_before_stop=args.min_episodes_before_stop,
        )
    except CompareFailure as failure:
        print(f"\nacceptance criterion failed: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
