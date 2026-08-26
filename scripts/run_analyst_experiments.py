"""Run one or more arms of the analyst over the golden fixtures — B1 onward.

One script, one arm vector per run, every number written to disk beside
the checksums that say what produced it. The alternative — a notebook
somebody ran once — is how a result becomes a screenshot nobody can
reproduce.

    python scripts/run_analyst_experiments.py --arm b1 --provider openai \\
        --model o4-mini --repeats 3

What it refuses to do, and why each refusal exists:

**No cache.** Every repeat is an independent model call. A repeat served
from cache is the same answer counted twice, and reliability computed
over it is a number about the cache.

**No labels near the model.** The labels are loaded here, in the scorer,
after the round has finished. Nothing in ``planbench_analyst`` that the
round touches can see this module.

**Development partition only.** ``load_eval_spec`` refuses anything
else; the confirmatory set is opened once, by the official gate, after a
freeze.

**Every arm names itself.** The arm vector goes into the runtime config
checksum, so two runs of "the same" configuration that were not the same
configuration cannot be compared by accident.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for package in ("schemas", "planning", "metrics", "benchmark", "decision", "explanation"):
    sys.path.insert(0, str(ROOT / "packages" / package))
sys.path.insert(0, str(ROOT / "services" / "simulator"))
sys.path.insert(0, str(ROOT / "services" / "agent_service"))
sys.path.insert(0, str(ROOT / "services" / "analyst_service"))

from planbench_agent.factory import build_provider  # noqa: E402
from planbench_analyst.eval_spec import load_eval_spec  # noqa: E402
from planbench_analyst.features import RoundFeatures  # noqa: E402
from planbench_analyst.identity import (  # noqa: E402
    runtime_config_checksum,
    source_manifest_hash,
)
from planbench_analyst.packet_view import build_packet_view  # noqa: E402
from planbench_analyst.prompts import PROMPT_VERSION, prompt_checksum  # noqa: E402
from planbench_analyst.round_host import in_process_round  # noqa: E402
from planbench_analyst.runner import run_round  # noqa: E402
from planbench_analyst.scoring import score_case, score_repeat  # noqa: E402
from planbench_explanation.budget import PLATFORM_BUDGET_CAP  # noqa: E402
from planbench_explanation.bundle import AnalystBundle  # noqa: E402
from planbench_explanation.catalog import TOOL_CATALOG, TOOL_CATALOG_VERSION  # noqa: E402
from planbench_explanation.integration import reference_analyst  # noqa: E402
from planbench_explanation.packet_artifact import load_packet_artifact  # noqa: E402
from planbench_explanation.protocol import ANALYST_RUNNER_PROTOCOL_VERSION  # noqa: E402

FIXTURES = ROOT / "fixtures" / "golden" / "visible"
LABELS = ROOT / "fixtures" / "golden" / "labels" / "visible.json"
ARTIFACTS = ROOT / "artifacts" / "analyst-experiments"

#: The arms this plan named. Each one is a feature vector and nothing
#: else: an arm that also changed a prompt or a model would be two
#: variables wearing one label.
#:
#: ``b1`` is the baseline the plan measures everything against, and it
#: is **stated** rather than defaulted — the packet blocks are off, so
#: what E1 and E2 add is not already inside the thing they are compared
#: to.
ARMS: dict[str, RoundFeatures] = {
    "b1": RoundFeatures(measurements=False, timelines=False),
    "e1_measurements": RoundFeatures(measurements=True, timelines=False),
    "e2_timelines": RoundFeatures(measurements=True, timelines=True),
    "e3_knowledge": RoundFeatures(measurements=True, timelines=True, knowledge=True),
    "e4a_shortlist": RoundFeatures(
        measurements=True, timelines=True, candidate_shortlist=True
    ),
    "e4b_options": RoundFeatures(
        measurements=True,
        timelines=True,
        candidate_shortlist=True,
        verification_options=True,
    ),
    "e5a_filtered_menu": RoundFeatures(
        measurements=True, timelines=True, filter_tool_menu=True
    ),
    "e5b_auto_route": RoundFeatures(
        measurements=True, timelines=True, filter_tool_menu=True, auto_route_checker=True
    ),
}


def load_env(path: Path) -> None:
    """Read ``.env`` without printing anything from it.

    Last assignment wins, deliberately: a file with two lines for one
    key would otherwise be resolved by ``setdefault`` in favour of the
    first, which is how a dead key stayed in use for a week.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        os.environ[name.strip()] = value.strip().strip('"').strip("'")


def bundle_for(arm: str, model_id: str) -> AnalystBundle:
    """A dev bundle naming what this arm actually ran."""
    return AnalystBundle(
        bundle_id=f"dev-{arm}",
        agent_code_digest="git:" + "0" * 40,
        container_digest="sha256:" + "0" * 64,
        model_id=model_id or "mock",
        model_revision="dev",
        prompt_checksum=prompt_checksum(),
        rag_index_version="kb-v1.0.0",
        retrieval_config_checksum="0" * 64,
        tool_catalog_version=TOOL_CATALOG_VERSION,
        generation_parameters={},
        runner_protocol_version=ANALYST_RUNNER_PROTOCOL_VERSION,
        requested_budget=PLATFORM_BUDGET_CAP,
        created_at="2026-08-26T00:00:00Z",
    )


def report_for(case_id: str) -> dict[str, object] | None:
    """The scoring report a fixture kept, if its run produced one.

    Only the latency family does today: an association between search
    size and tick latency lives per episode, and the packet carries per
    candidate aggregates. A case without one leaves that check honestly
    ``not_checkable``.
    """
    path = FIXTURES / case_id / "report.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def sidecars(case_id: str) -> dict[str, Path]:
    directory = FIXTURES / case_id / "sidecar"
    if not directory.exists():
        return {}
    return {folder.name: folder for folder in directory.iterdir() if folder.is_dir()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", action="append", required=True, choices=sorted(ARMS))
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--model", default="")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--cases", default="")
    parser.add_argument("--label", default="", help="what to call this run on disk")
    args = parser.parse_args()

    # The worktree shares a repository with the main checkout and not
    # its untracked files, so the keys live one directory up. Read there
    # too rather than making every run pass a flag it would forget.
    load_env(ROOT.parent / "P-011" / ".env")
    load_env(ROOT / ".env")
    spec = load_eval_spec(LABELS)
    case_ids = [item.strip() for item in args.cases.split(",") if item.strip()] or [
        item.case_id for item in spec.labels
    ]

    provider = build_provider(args.provider, model=args.model or None)
    started = time.time()
    runs: list[dict[str, object]] = []

    for arm in args.arm:
        features = ARMS[arm]
        bundle = bundle_for(arm, args.model)
        identity = runtime_config_checksum(
            prompt_checksum=prompt_checksum(),
            generation_config={},
            catalog_version=TOOL_CATALOG_VERSION,
            source_manifest_hash=source_manifest_hash(ROOT),
            features=features,
        )
        print(f"\n=== arm {arm}  ({args.provider}:{args.model or 'mock'})  {identity[:12]} ===")
        cases: list[dict[str, object]] = []
        for case_id in case_ids:
            label = spec.label_for(case_id)
            artifact = load_packet_artifact(FIXTURES, case_id)
            repeats = []
            floor_correct = None
            for index in range(max(1, args.repeats)):
                prepared = in_process_round(
                    artifact,
                    bundle,
                    catalog=TOOL_CATALOG,
                    analysis_run_id=f"{arm}-{case_id}-r{index + 1}",
                    sidecar_directories=sidecars(case_id),
                    report=report_for(case_id),
                )
                view = build_packet_view(
                    prepared.analysis.packet,
                    tool_catalog_version=TOOL_CATALOG_VERSION,
                    features=features,
                )
                outcome = run_round(prepared, provider, features=features)
                repeats.append(score_repeat(case_id, outcome, label, view))
                print(
                    f"  {case_id} r{index + 1}: {outcome.stopped_because}, "
                    f"{len(outcome.response.proposals)} proposal(s), "
                    f"{outcome.cost.input_tokens}+{outcome.cost.output_tokens} tokens"
                )
                if floor_correct is None:
                    floor = reference_analyst(prepared.analysis)
                    floor_correct = label is not None and any(
                        proposal.proposition_type == label.expected_mechanism
                        for proposal in floor.proposals
                    )
            scored = score_case(case_id, repeats)
            cases.append(
                {
                    "case_id": case_id,
                    "mechanism_correct": scored.mechanism_correct,
                    "subject_correct": scored.subject_correct,
                    "abstention_correct": scored.abstention_correct,
                    "stable": scored.stable,
                    "structural_violations": scored.structural_violations,
                    "median_tokens": scored.median_tokens,
                    "floor_mechanism_correct": bool(floor_correct),
                    "repeats": [asdict(item) for item in repeats],
                }
            )
        runs.append(
            {
                "arm": arm,
                "features": features.as_config,
                "runtime_config_checksum": identity,
                "prompt_version": PROMPT_VERSION,
                "eval_spec_checksum": spec.checksum,
                "provider": args.provider,
                "model": args.model,
                "repeats": args.repeats,
                "cases": cases,
            }
        )

    payload = {
        "started_at": started,
        "elapsed_s": round(time.time() - started, 1),
        "partition": spec.partition,
        "exploratory": True,
        "runs": runs,
    }
    name = args.label or f"{args.provider}-{args.model or 'mock'}"
    folder = ARTIFACTS / name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{'-'.join(args.arm)}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(f"\nwritten to {path.relative_to(ROOT).as_posix()}")
    for run in runs:
        rows = run["cases"]  # type: ignore[index]
        correct = sum(1 for row in rows if row["mechanism_correct"])  # type: ignore[index]
        floor = sum(1 for row in rows if row["floor_mechanism_correct"])  # type: ignore[index]
        print(
            f"  {run['arm']}: mechanism {correct}/{len(rows)} "  # type: ignore[index]
            f"(floor {floor}/{len(rows)}), "
            f"violations {sum(row['structural_violations'] for row in rows)}"  # type: ignore[index]
        )
    print("\nExploratory: three of six families, no holdout. Not a deployment result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
