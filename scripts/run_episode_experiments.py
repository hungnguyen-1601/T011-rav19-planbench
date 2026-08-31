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
from collections.abc import Mapping
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
from planbench_explanation.exemplars import (  # noqa: E402  # noqa: E402
    CardlessPairRefusal,
    ReportExemplarRefusal,
    cardless_pair,
    select_exemplars_from_report,
)
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION  # noqa: E402
from planbench_explanation.versioning import ExplanationArtifactHeader  # noqa: E402

#: o4-mini's list price per million tokens, applied to every token as
#: though none were discounted. **An upper bound on the bill, not the
#: bill** — and the gap is large enough to matter to whoever reads the
#: number this script prints.
#:
#: Measured on 2026-08-30: the `holdout-deployment` sweep printed $0.6805
#: against 273,458 in and 86,286 out; the provider charged $0.30, a
#: little under half. Repeated episodes share a long prefix — the system
#: prompt, the tool catalogue, the rubric — and a cached input token
#: bills at a fraction of a fresh one, which the token counts here do not
#: separate. Nothing in the response tells this script which tokens were
#: cached, so the honest arithmetic is the pessimistic one.
#:
#: **Do not "correct" these downward to match an observed bill.** They
#: gate spending: `--budget-usd` stops the sweep when the estimate
#: reaches the ceiling, so overestimating stops early and underestimating
#: overspends somebody's money. One measurement of a cache hit rate is
#: not a rate. What is worth fixing is how the figure is *reported* —
#: hence the wording where it is printed.
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
    # Differs from ep_b1 by one sentence in the system and nothing
    # else, so a difference in what survives rule 10 is that sentence.
    "ep_cite_two": RoundFeatures(episode_scope=True, contrast_citation_rule=True),
    # Differs from ep_b1 by one behaviour: a round whose every proposal
    # was removed over how it was written gets told what was removed and
    # asked once more. Its control is inside itself - the first turn is
    # the baseline for that round - so it needs no paired arm, which is
    # as well, because the packets changed under `outcome_margin` and
    # nothing run before today compares with anything run after it.
    "ep_reword": RoundFeatures(episode_scope=True, reword_once=True),
    # Differs from ep_b1 by one behaviour: the model may state a
    # magnitude as a ref in braces instead of writing the figure.
    # The floor fallback is deliberately NOT on here - it is
    # deterministic and already measured, and turning both on at
    # once would leave neither attributable.
    "ep_magnitudes": RoundFeatures(episode_scope=True, magnitude_placeholders=True),
    # **What a reader is actually served.** The three features the
    # episode route turns on, mirrored here so the configuration people
    # meet can be measured rather than inferred from three arms that
    # each carried one of them.
    #
    # It attributes nothing, and is not meant to: three behaviours are
    # on at once and two guard rules landed underneath it. The question
    # it answers is "how good is the thing we ship", which is not "what
    # did each flag buy" and is the one a demo decision rests on.
    # `ep_b1` stays the baseline every attribution is reported against.
    "ep_deployment": RoundFeatures(
        episode_scope=True,
        magnitude_placeholders=True,
        floor_when_silent=True,
        reword_once=True,
    ),
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


#: How many episodes a cardless run contributes, and how they are picked.
#:
#: Not the exemplar recipe. Three of its four roles are defined on ΔU
#: (``select_exemplars_from_report`` says so and refuses rather than
#: substituting travel time), and a run with no card has no per-episode
#: utility on at least one side — so a role called
#: ``strongest_for_winner`` would be a label saying these episodes were
#: chosen by a recipe that did not choose them.
#:
#: The rule instead: **every episode where the two sides disagree about
#: reaching the goal, plus a fixed sample of the rest.** The first group
#: is what the run is *for* — those are the episodes `build_verdict`
#: settles on ``outcome_only`` — and the second is the control, because
#: an arm that explains the decided ones and also invents explanations
#: for the undecided ones is worse than one that does neither, and with
#: only decided episodes in the set nothing would show that.
CARDLESS_UNDECIDED_SAMPLE = 4


def cardless_episodes(report: Mapping[str, Any], candidate_a: str, candidate_b: str) -> list[str]:
    """Which episodes of a cardless run are read, by the rule above."""
    outcomes: dict[str, dict[str, bool]] = {}
    for candidate in report.get("candidates", ()):
        candidate_id = str(candidate.get("candidate_id") or "")
        if candidate_id not in (candidate_a, candidate_b):
            continue
        for row in candidate.get("episodes", ()):
            episode = str(row.get("episode_context_id") or "")
            if episode:
                outcomes.setdefault(episode, {})[candidate_id] = bool(row.get("success"))

    order = [
        episode
        for episode in ((report.get("sample") or {}).get("episode_context_ids") or [])
        if episode in outcomes
    ]
    decided = [
        episode
        for episode in order
        if len(outcomes[episode]) == 2 and len(set(outcomes[episode].values())) == 2
    ]
    undecided = [episode for episode in order if episode not in set(decided)]
    return [*decided, *undecided[:CARDLESS_UNDECIDED_SAMPLE]]


def cases_from(
    report_path: Path, traces_root: Path, *, every_episode: bool = False
) -> list[dict[str, Any]]:
    """The four exemplar episodes of one run, with their traces.

    The recipe is preregistered and deterministic, and the replay page
    already opens on these four — so the episodes an arm is read on are
    the ones a reader would have looked at anyway, rather than the ones
    that flattered an arm.
    """
    report = json.loads(report_path.read_text(encoding="utf-8"))
    pair = report.get("comparison_pair")
    if pair:
        candidate_a = pair["recommended_candidate_id"]
        candidate_b = pair["runner_up_candidate_id"]
        try:
            exemplars = select_exemplars_from_report(report)
        except ReportExemplarRefusal:
            return []
        chosen = [(item.episode_context_id, item.role) for item in exemplars.exemplars]
        if every_episode:
            roles = dict(chosen)
            chosen = [
                (episode, roles.get(episode, "holdout"))
                for episode in ((report.get("sample") or {}).get("episode_context_ids") or [])
            ]
    else:
        # **A run with no card is still a run somebody has to explain.**
        # The card is refused when fewer than two candidates clear the
        # gates, and that refusal is about a *deployment* claim. Whether
        # this stack reached the goal in this episode and that one did
        # not is a different claim, `build_verdict` settles it on
        # ``outcome_only`` without any utility, and it is the claim a
        # reader opening one episode is actually asking about.
        try:
            candidate_a, candidate_b = cardless_pair(report)
        except CardlessPairRefusal:
            return []
        chosen = [
            (episode, "cardless") for episode in cardless_episodes(report, candidate_a, candidate_b)
        ]

    built: list[dict[str, Any]] = []
    for episode, role in chosen:
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
            outcome_margin=EPISODE_PREREGISTRATION.outcome_margin,
        )
        built.append(
            {
                "cluster": report_path.parent.name,
                "episode": episode,
                "role": role,
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
        # **What the rule objected to, not only that it objected.**
        #
        # Only the rule name was kept, and it made the largest question
        # about this scope unanswerable after the fact: rule 2 refused a
        # hundred and nine proposals across ninety rounds and thirty-six
        # rounds were offered a rewrite, of which twenty-one still ended
        # in silence. Reading those twenty-one is the cheapest work
        # available — and it could not be done, because what the model
        # had written was gone and only the word
        # ``quantity_in_statement`` was left.
        #
        # ``detail`` is the guard's own account: for rule 2 it is the
        # tokens it read as figures, so a false positive is visible
        # without re-running anything. Kept beside `blocked` rather than
        # replacing it, so the counts above and every artifact already
        # written stay comparable.
        "blocked_detail": [
            {"rule": item.rule, "hypothesis_id": item.hypothesis_id, "detail": item.detail}
            for item in outcome.blocked
        ],
        # What the round did that is not visible in its proposals. The
        # rewording arm was measured by inferring a retry from a doubled
        # token count, which worked and should not have been necessary:
        # the runner already knows, and a figure reconstructed from cost
        # is a figure that stops being reconstructable the moment a turn
        # changes length.
        "flags": [list(item) for item in outcome.flags],
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
        "--every-episode",
        action="store_true",
        help=(
            "Read every episode of each run rather than the four exemplars. "
            "What the hold-out cluster is read with: four episodes from one "
            "run is too few to say anything generalises, and any subset of a "
            "cluster already on screen is a subset somebody chose."
        ),
    )
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
        # Deliberately not filtered on having a comparison pair. That
        # test was here because a report without one produced no cases,
        # and it silently kept excluding the cardless runs after
        # `cases_from` learned to read them — a filter that outlives its
        # reason looks exactly like a run with nothing in it.
        key = path.parent.name
        seen.setdefault(key, path)

    cases: list[dict[str, Any]] = []
    for path in seen.values():
        cases.extend(cases_from(path, traces_root, every_episode=args.every_episode))

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
        # An upper bound, kept under its old name so artifacts already
        # written stay comparable. The flag beside it says what it is,
        # for anything reading these later.
        "estimated_usd": round(estimate, 4),
        "usd_is_upper_bound": True,
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
    # Named as the bound it is. The earlier wording — a bare "~$" — was
    # read as the bill and reported onward as one; the sweep it was
    # printed for cost a little under half what it said.
    print(
        f"\nin={spent_in} out={spent_out} "
        f"at most ${estimate:.2f} (list price, no cache discount — "
        f"check the provider for what was billed)"
    )
    if stopped:
        print(f"STOPPED at {stopped} — the ceiling was reached, not the end of the plan")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
