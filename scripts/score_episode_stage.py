"""Read one sweep artifact and print what the preregistration asks of it.

Separate from the runner because the runner spends money and this does
not: a scoring bug should be fixable without paying to re-run, and a
re-read of an artifact already on disk is the cheapest way to check a
selection rule before applying it.

No judgement of correctness here either. Whether a hypothesis holds up
is read by a person against the rubric; what this prints is the vetoes,
the arm-level counts the selection rule names, and the per-cluster
breakdown the preregistration requires because twelve episodes from
three runs are not twelve trials.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _package in (
    "packages/schemas",
    "packages/benchmark",
    "packages/decision",
    "packages/explanation",
    "packages/plugin_sdk",
    "packages/metrics",
    "packages/planning",
    "services/simulator",
    "ml",
    "services/tracking",
    "services/agent_service",
    "services/analyst_service",
    "apps/api",
    "apps/desktop",
):
    sys.path.insert(0, str(REPO_ROOT / _package))

from planbench_analyst.preregistration_episode import (  # noqa: E402
    EPISODE_PREREGISTRATION,
    episode_preregistration_checksum,
)

PRICE_IN_PER_M = 1.10
PRICE_OUT_PER_M = 4.40


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact")
    args = parser.parse_args()

    payload = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = payload["results"]

    written = payload.get("preregistration_checksum", "")
    now = episode_preregistration_checksum()
    if written != now:
        # Not fatal: the constraint definitions were corrected after this
        # sweep was recorded, and saying so is the point of printing it.
        print(f"preregistration differs from the one recorded: {written[:12]} -> {now[:12]}\n")

    vetoes = [name for name, _ in EPISODE_PREREGISTRATION.hard_constraints]
    arms: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        arms[row["arm"]].append(row)

    print(
        f"{'arm':24} {'ok':>3} {'fail':>4} {'abst':>4} {'prop':>4} {'ctr':>4} "
        f"{'blk':>4} {'drop':>5} {'$':>6}  vetoes"
    )
    summary: dict[str, dict[str, Any]] = {}
    for arm, entries in arms.items():
        failed = [row for row in entries if "model_failed" in row]
        done = [row for row in entries if "model_failed" not in row]
        breaches = {name: sum(row.get(name, 0) for row in done) for name in vetoes}
        spend = sum(
            row.get("input_tokens", 0) / 1e6 * PRICE_IN_PER_M
            + row.get("output_tokens", 0) / 1e6 * PRICE_OUT_PER_M
            for row in entries
        )
        summary[arm] = {
            "rounds": len(done),
            "model_failed": len(failed),
            "abstained": sum(1 for row in done if row["abstained"]),
            "proposals": sum(len(row["proposals"]) for row in done),
            "contrasts": sum(row["contrast_count"] for row in done),
            "blocked": sum(len(row["blocked"]) for row in done),
            "usd": round(spend, 3),
            **breaches,
        }
        offered = summary[arm]["proposals"] + summary[arm]["blocked"]
        summary[arm]["drop_rate"] = round(summary[arm]["blocked"] / offered, 3) if offered else 0.0
        breached = ", ".join(f"{name}={count}" for name, count in breaches.items() if count)
        print(
            f"{arm:24} {len(done):3} {len(failed):4} {summary[arm]['abstained']:4} "
            f"{summary[arm]['proposals']:4} {summary[arm]['contrasts']:4} "
            f"{summary[arm]['blocked']:4} {summary[arm]['drop_rate']:5.2f} "
            f"{spend:6.2f}  {breached or '-'}"
        )

    if len(summary) <= EPISODE_PREREGISTRATION.stage_two_arms:
        # The selection rule belongs to the stage that has arms to
        # choose between. Printing "stage two: ep_b1" underneath a
        # stage-two artifact reads as a conclusion and is none.
        print(
            f"\nno selection printed: {len(summary)} arms is what stage two "
            "runs, so there is nothing here to select from"
        )
        _per_cluster(arms)
        return 0

    baseline = summary.get("ep_b1", {}).get("blocked", 0)
    print(f"\nselection rule: {EPISODE_PREREGISTRATION.stage_two_rule}")
    print(f"  baseline (ep_b1) guard drops: {baseline}")
    eligible = [
        arm
        for arm, figures in summary.items()
        if not any(figures[name] for name in vetoes) and figures["blocked"] <= baseline
    ]
    print(f"  eligible: {', '.join(eligible) or 'none'}")
    print(f"  tiebreak: {EPISODE_PREREGISTRATION.stage_two_tiebreak}")
    contenders = sorted(
        (arm for arm in eligible if arm != "ep_b1"),
        key=lambda arm: (summary[arm]["blocked"], arm),
    )
    chosen = ["ep_b1", *contenders][: EPISODE_PREREGISTRATION.stage_two_arms]
    print(f"  stage two: {', '.join(chosen)}")

    _per_cluster(arms)
    return 0


def _per_cluster(arms: dict[str, list[dict[str, Any]]]) -> None:
    print("\nper cluster, because a run is a cluster:")
    for arm, entries in arms.items():
        by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in entries:
            by_cluster[row["cluster"]].append(row)
        parts = [
            f"{cluster.rsplit('_', 1)[0][:22]}: "
            f"{sum(len(r.get('proposals', ())) for r in rs)}p/"
            f"{sum(1 for r in rs if r.get('abstained'))}a"
            for cluster, rs in sorted(by_cluster.items())
        ]
        print(f"  {arm:24} " + "  ".join(parts))


if __name__ == "__main__":
    raise SystemExit(main())
