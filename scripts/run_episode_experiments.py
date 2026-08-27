"""Read the arms of the episode scope on episodes somebody actually ran.

**Recorded runs, not planted worlds.** The golden fixtures carry no
per-episode utility — they were built for the run scope, where the
verdict is a decision card — so every one of their episodes comes back
``undecidable`` and the correct answer on all fourteen is silence. An
experiment on that set measures how well a model stays quiet.

A recorded run has the opposite property and none of the convenience: a
verdict for every episode, a real winner, real detections from the
traces beside it — and no planted answer, so correctness is read by a
person against the rubric fixed on 26-08 rather than computed here.

Two things this script will not do. It will not pick which episodes to
read after seeing how an arm did on them: the twelve come from the
exemplar recipe, which is preregistered and deterministic. And it will
not spend past the ceiling in the preregistration — it stops, writes
what it has, and says which arms never ran.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
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


from planbench_agent.factory import build_provider  # noqa: E402
from planbench_analyst.analyst import AnalystRefusal  # noqa: E402
from planbench_analyst.episode_prompts import episode_prompt_checksum  # noqa: E402
from planbench_analyst.episode_runner import (  # noqa: E402
    EpisodeRound,
    episode_runtime_config,
    run_episode_round,
)
from planbench_analyst.episode_view import build_episode_view  # noqa: E402
from planbench_analyst.features import RoundFeatures  # noqa: E402
from planbench_analyst.preregistration_episode import (  # noqa: E402
    EPISODE_PREREGISTRATION,
    episode_preregistration_checksum,
)
from planbench_explanation.catalog import TOOL_CATALOG, TOOL_CATALOG_VERSION  # noqa: E402
from planbench_explanation.episode_builder import build_episode_packet  # noqa: E402
from planbench_explanation.episode_floor import episode_floor  # noqa: E402
from planbench_explanation.exemplars import (  # noqa: E402
    ReportExemplarRefusal,
    select_exemplars_from_report,
)
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION  # noqa: E402
from planbench_explanation.versioning import ExplanationArtifactHeader  # noqa: E402

#: What o4-mini bills, per million tokens. Used to stop, not to invoice:
#: the run halts on the preregistered ceiling, and the number it prints
#: is an estimate a reader should check against the provider's own.
PRICE_IN_PER_M = 1.10
PRICE_OUT_PER_M = 4.40

#: Six arms. Each is a feature vector and nothing else, so a difference
#: between two of them is one change rather than a package of them.
ARMS: dict[str, RoundFeatures] = {
    "ep_b1": RoundFeatures(episode_scope=True),
    "ep_shortlist": RoundFeatures(episode_scope=True, candidate_shortlist=True),
    "ep_knowledge": RoundFeatures(episode_scope=True, knowledge=True),
    "ep_shortlist_knowledge": RoundFeatures(
        episode_scope=True, candidate_shortlist=True, knowledge=True
    ),
    "ep_no_union": RoundFeatures(episode_scope=True, discriminated_union=False),
    "ep_run_context": RoundFeatures(episode_scope=True, run_context=True),
}


def header_for(run_id: str) -> ExplanationArtifactHeader:
    return ExplanationArtifactHeader.for_current_code(
        source_manifest_ref=f"artifacts/runs/{run_id}/manifest.json",
        source_manifest_checksum="0" * 64,
        detector_version="0.1.0",
        knowledge_base_version=KNOWLEDGE_BASE_VERSION,
        tool_catalog_version=TOOL_CATALOG_VERSION,
    )


def trace_for(traces_root: Path, candidate_id: str, episode: str) -> dict[str, Any] | None:
    """One episode's trace, in the shape the platform serves it.

    Read straight off the parquet rather than through the API: this is a
    script reading its own repository, and standing up a service to
    fetch a file it can open would be a second answer to where traces
    live.
    """
    import pyarrow.parquet as pq

    hits = sorted(traces_root.glob(f"*/*/{candidate_id}/{episode}.parquet"))
    if not hits:
        return None
    table = pq.read_table(hits[0]).to_pydict()
    events = [
        {"index": index, "event": value}
        for index, value in enumerate(table.get("event") or [])
        if value
    ]
    return {
        "candidate_id": candidate_id,
        "episode_context_id": episode,
        "t": table["t"],
        "x": table["x"],
        "y": table["y"],
        "clearance_m": table.get("clearance_m"),
        "planner_latency_ms": table.get("planner_latency_ms"),
        "events": events,
    }


def cases_from(report_path: Path, traces_root: Path) -> list[dict[str, Any]]:
    """The four exemplar episodes of one run, with their traces.

    The recipe is preregistered and deterministic, and the replay page
    already opens on these four — so the episodes an arm is read on are
    the ones a reader would have looked at anyway, rather than the ones
    that flattered an arm.
    """
    report = json.loads(report_path.read_text(encoding="utf-8"))
    pair = report.get("comparison_pair")
    if not pair:
        return []
    candidate_a = pair["recommended_candidate_id"]
    candidate_b = pair["runner_up_candidate_id"]
    try:
        exemplars = select_exemplars_from_report(report)
    except ReportExemplarRefusal:
        return []

    built: list[dict[str, Any]] = []
    for exemplar in exemplars.exemplars:
        episode = exemplar.episode_context_id
        packet = build_episode_packet(
            header=header_for(report_path.parent.name),
            run_id=report_path.parent.name,
            episode_context_id=episode,
            candidate_a=candidate_a,
            candidate_b=candidate_b,
            report=report,
            trace_a=trace_for(traces_root, candidate_a, episode),
            trace_b=trace_for(traces_root, candidate_b, episode),
            tie_epsilon=EPISODE_PREREGISTRATION.tie_epsilon,
        )
        built.append(
            {
                "cluster": report_path.parent.name,
                "episode": episode,
                "role": exemplar.role,
                "packet": packet,
            }
        )
    return built


def _names_an_id(statement: str, real_ids: tuple[str, ...]) -> bool:
    """Whether a surviving sentence writes out a candidate's own id.

    On word boundaries rather than as a substring: a real id is twelve
    hex characters, but a fixture's is one letter, and a substring test
    over that would read every sentence mentioning a stack as a leak.
    """
    return any(
        re.search(rf"(?<![\w-]){re.escape(candidate_id)}(?![\w-])", statement)
        for candidate_id in real_ids
        if candidate_id
    )


def score_round(outcome: Any, view: Any) -> dict[str, Any]:
    """What a round produced, in the terms the preregistration names.

    No judgement here: correctness on a recorded run is read by a person
    against the rubric, and a number this script invented would be the
    number a reader took instead.
    """
    from planbench_analyst.episode_guard import (
        CONTRACT_TERMS,
        CONTRAST,
        DIAGNOSIS,
        contradicts_verdict,
    )
    from planbench_analyst.guard import quantities_in

    # **A rule firing is the guard working, not the arm failing.** The
    # first version of this block counted `outcome.blocked`, and the
    # first real sweep read 55 quantity firings as 55 violations of a
    # constraint whose ceiling is zero — every one of them a sentence
    # the guard had already removed. What a hard constraint is about is
    # what survived into the answer a person is handed, so each count
    # below re-applies the rule to the *kept* proposals. Corrected after
    # seeing data, and only because the definition was wrong on its own
    # terms: it would have read the same way had the numbers flattered.
    blocked = [item.rule for item in outcome.blocked]
    kept = outcome.response.proposals
    identifiers = view.identifiers
    real_ids = tuple(stack.candidate_id for stack in view.packet.candidates)

    def _unmet(item: Any) -> bool:
        annotation = outcome.annotations.get(item.hypothesis_id)
        if annotation is None or annotation.bearing != CONTRAST:
            return False
        return any(term not in annotation.contract for term in CONTRACT_TERMS)

    return {
        "abstained": outcome.response.abstained,
        "abstention_reason": outcome.response.abstention_reason,
        "proposals": [
            {
                "hypothesis_id": item.hypothesis_id,
                "statement": item.hypothesis_statement,
                "proposition_type": item.proposition_type,
                "subject": item.proposed_subject,
                "supports": [ref.ref for ref in item.supports],
                "bearing": outcome.annotations.get(item.hypothesis_id).bearing
                if outcome.annotations.get(item.hypothesis_id)
                else DIAGNOSIS,
                "contract": list(
                    outcome.annotations.get(item.hypothesis_id).contract
                    if outcome.annotations.get(item.hypothesis_id)
                    else ()
                ),
            }
            for item in outcome.response.proposals
        ],
        "contrast_count": sum(1 for item in outcome.of(CONTRAST)),
        "diagnosis_count": sum(1 for item in outcome.of(DIAGNOSIS)),
        "blocked": blocked,
        # What the guard removed. Read as effort, never as a violation.
        "verdict_contradictions_blocked": blocked.count("contradicts_verdict"),
        "contrast_contract_unmet_blocked": blocked.count("contrast_contract_unmet"),
        "quantities_in_statements_blocked": blocked.count("quantity_in_statement"),
        # What reached the reader. These are the preregistered vetoes.
        "verdict_contradictions_in_final": sum(
            1 for item in kept if contradicts_verdict(item, view)
        ),
        "contrast_contract_unmet_in_final": sum(1 for item in kept if _unmet(item)),
        "quantities_in_statements_in_final": sum(
            1 for item in kept if quantities_in(item.hypothesis_statement, identifiers)
        ),
        # The failure the first sweep actually produced: a statement
        # naming the twelve-character hash of a candidate the model was
        # never shown. Counted here because it happened, not because it
        # was foreseen.
        "candidate_ids_in_final": sum(
            1 for item in kept if _names_an_id(item.hypothesis_statement, real_ids)
        ),
        "input_tokens": outcome.cost.input_tokens,
        "output_tokens": outcome.cost.output_tokens,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", action="append", required=True, choices=sorted(ARMS))
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--model", default="")
    parser.add_argument("--label", default="episode")
    parser.add_argument(
        "--runs",
        default="artifacts/runs",
        help="Where the recorded comparison reports are.",
    )
    parser.add_argument("--traces", default="artifacts/traces")
    parser.add_argument(
        "--budget-usd",
        type=float,
        default=EPISODE_PREREGISTRATION.max_usd,
        help="Stop before spending past this. The preregistered ceiling by default.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Build the cases and stop.")
    parser.add_argument(
        "--env-file",
        default="",
        help=(
            "Read provider keys from this file. The value is never printed and "
            "never written to an artifact; only the variable name is."
        ),
    )
    args = parser.parse_args()

    if args.env_file:
        # Same rule as the API's own loader: copy only the variables a
        # provider is known to read, let a shell value win over a file,
        # and treat an empty line as absent rather than as a key.
        import os

        wanted = {
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
            "OPENROUTER_API_KEY",
        }
        filled = []
        text = Path(args.env_file).read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            name, _, value = line.partition("=")
            name, value = name.strip(), value.strip()
            if name in wanted and value and not os.environ.get(name):
                os.environ[name] = value
                filled.append(name)
        print(f"provider keys read from file: {', '.join(filled) or 'none'}")

    runs_root = REPO_ROOT / args.runs if not Path(args.runs).is_absolute() else Path(args.runs)
    traces_root = (
        REPO_ROOT / args.traces if not Path(args.traces).is_absolute() else Path(args.traces)
    )

    # One report per cluster: two directories holding the same episodes
    # under the same profile are one experiment run twice, and counting
    # them as two clusters would double an observation.
    seen: dict[str, Path] = {}
    for path in sorted(runs_root.glob("*/*/comparison_report.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        if "comparison_pair" not in report:
            continue
        key = path.parent.name
        seen.setdefault(key, path)

    cases: list[dict[str, Any]] = []
    for path in seen.values():
        cases.extend(cases_from(path, traces_root))

    clusters = sorted({case["cluster"] for case in cases})
    print(f"{len(cases)} cases across {len(clusters)} clusters")
    for cluster in clusters:
        mine = [case for case in cases if case["cluster"] == cluster]
        traced = sum(
            1 for case in mine if any(item.detections for item in case["packet"].diagnoses)
        )
        print(f"  {cluster[:52]:52} cases={len(mine)} with_detections={traced}")
    if args.dry_run or not cases:
        return 0

    floor_rows = [
        {
            "cluster": case["cluster"],
            "episode": case["episode"],
            "role": case["role"],
            "abstained": episode_floor(case["packet"]).abstained,
            "proposals": len(episode_floor(case["packet"]).proposals),
            "contrast": len(episode_floor(case["packet"]).of("contrast")),
        }
        for case in cases
    ]

    provider = build_provider(args.provider, model=args.model or None)
    print(f"provider {provider.name} | model {provider.model}")

    spent_in = spent_out = 0
    results: list[dict[str, Any]] = []
    stopped = ""
    for arm in args.arm:
        features = ARMS[arm]
        for case in cases:
            for repeat in range(args.repeats):
                estimate = spent_in / 1e6 * PRICE_IN_PER_M + spent_out / 1e6 * PRICE_OUT_PER_M
                if estimate >= args.budget_usd:
                    stopped = f"{arm}/{case['episode']}/r{repeat}"
                    break
                # The view carries the facts; the feature vector
                # decides what the round *shows* and is passed to the
                # runner. Knowledge is an offer the view indexes, so
                # an arm that turns it off simply makes no offer.
                view = build_episode_view(case["packet"])
                started = time.perf_counter()
                try:
                    outcome = run_episode_round(
                        EpisodeRound(
                            analysis_run_id=f"{case['cluster']}:{case['episode']}:{arm}:{repeat}",
                            analyst_bundle_id=f"episode:{episode_prompt_checksum()[:16]}",
                            catalog=TOOL_CATALOG,
                        ),
                        view,
                        provider,
                        features=features,
                        catalog=TOOL_CATALOG,
                    )
                except AnalystRefusal as refused:
                    # A round the model could not complete is a result,
                    # not the end of the experiment. Losing the rest of
                    # the sweep to one malformed answer would also lose
                    # every case after it, and the sweep costs money.
                    elapsed = time.perf_counter() - started
                    results.append(
                        {
                            "arm": arm,
                            "cluster": case["cluster"],
                            "episode": case["episode"],
                            "role": case["role"],
                            "repeat": repeat,
                            "elapsed_s": round(elapsed, 2),
                            "model_failed": str(refused),
                        }
                    )
                    print(f"  {arm:24} {case['role']:22} {case['episode'][:12]} r{repeat} FAILED")
                    continue
                elapsed = time.perf_counter() - started
                scored = score_round(outcome, view)
                spent_in += scored["input_tokens"]
                spent_out += scored["output_tokens"]
                results.append(
                    {
                        "arm": arm,
                        "cluster": case["cluster"],
                        "episode": case["episode"],
                        "role": case["role"],
                        "repeat": repeat,
                        "elapsed_s": round(elapsed, 2),
                        **scored,
                    }
                )
                said = "abstain" if scored["abstained"] else f"{len(scored['proposals'])} props"
                print(
                    f"  {arm:24} {case['role']:22} {case['episode'][:12]} "
                    f"r{repeat} {said} blocked={len(scored['blocked'])} "
                    f"out={scored['output_tokens']}"
                )
            if stopped:
                break
        if stopped:
            break

    estimate = spent_in / 1e6 * PRICE_IN_PER_M + spent_out / 1e6 * PRICE_OUT_PER_M
    artifact = {
        "label": args.label,
        "arms": args.arm,
        "repeats": args.repeats,
        "provider": provider.name,
        "model": provider.model,
        "preregistration_checksum": episode_preregistration_checksum(),
        "prompt_checksum": episode_prompt_checksum(),
        "runtime_config": episode_runtime_config(
            ARMS[args.arm[0]],
            source_manifest_hash="0" * 64,
            catalog_version=TOOL_CATALOG_VERSION,
        ),
        "clusters": clusters,
        "cases": len(cases),
        "input_tokens": spent_in,
        "output_tokens": spent_out,
        "estimated_usd": round(estimate, 4),
        # Written whether or not the ceiling stopped it. A run that
        # halted and did not say so would read as a run that covered
        # everything asked of it.
        "stopped_at": stopped,
        "conclusion_class": EPISODE_PREREGISTRATION.conclusion_class,
        "floor": floor_rows,
        "results": results,
    }
    out = REPO_ROOT / "artifacts" / "analyst-episode-experiments" / f"{args.label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nin={spent_in} out={spent_out} ~${estimate:.2f}")
    if stopped:
        print(f"STOPPED at {stopped} — the ceiling was reached, not the end of the plan")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
