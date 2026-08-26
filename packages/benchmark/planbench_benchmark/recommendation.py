"""Which algorithm should this deployment use — argued from stored runs.

Every verdict this platform produces already exists somewhere: the card
names a winner, the gate table names who was eliminated where, and the
report keeps every episode's utility. What no module answers is the
question a user actually asks: *"for my project, which one should I
pick — and in which situations does the answer differ?"* This module
answers it, and answers it only from what the database holds.

Three design rules, all inherited:

**The per-run verdict is never re-litigated.** A card is a card. The
rules here read ``recommended_candidate_id`` and ``status`` from the
stored run; nothing recomputes a winner the decision layer already
named, because a module that could disagree with a card would be a card
with no contract behind it.

**"In which cases" is answered inside a run, not across runs.** The
report stores one utility per episode, paired by ``episode_context_id``
across candidates — and a context is a (mission, seed) pair. Grouping
the paired differences by mission and bootstrapping each group answers
"who wins in mission M" with the same machinery (HĐ-11.2's
:func:`~planbench_decision.stats.paired_bootstrap_ci`) that answered
"who wins overall". Cross-run transfer is a different, weaker kind of
evidence, and it is deliberately not attempted here.

**Feasibility on *this* profile trumps history everywhere.** A stack
that won somewhere but cannot run on this deployment — its observation
is not available, its model was never chosen — must never be
recommended, so every candidate passes through the canonical
:mod:`~planbench_benchmark.preflight` rules before history is allowed a
word. Preflight is *called*, not re-implemented: a second copy of those
rules would drift from the first.

Same constitution as every advisory module: read-only, never raises,
every citation resolves against the source it ships with, and the LLM
layer above may rank and extend but never overrule.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from planbench_benchmark.preflight import build_draft, preflight
from planbench_benchmark.registry import list_algorithms
from planbench_decision.advice import Advice, keep_resolvable, order
from planbench_decision.stats import paired_bootstrap_ci
from planbench_schemas.episode_context import NOMINAL_VARIANT, EpisodeContext
from planbench_schemas.task_profile import TaskProfile

__all__ = [
    "MIN_PAIRS_PER_CASE",
    "RECOMMENDATION_CODES",
    "SEED_SEARCH_BOUND",
    "case_table",
    "map_contexts",
    "recommend_from_history",
    "recommendation_source",
]

#: Published for the same reason every sibling module publishes its
#: codes: "no advice" from a module that ran twelve rules is a
#: measurement, and from a module that ran none it is a malfunction —
#: the count is how a caller tells the two apart.
RECOMMENDATION_CODES: tuple[str, ...] = (
    "RC_CARD_ON_THIS_PROFILE",
    "RC_CASE_INSUFFICIENT",
    "RC_CASE_UNDECIDED",
    "RC_CASE_WINNER",
    "RC_CONFLICT_BETWEEN_RUNS",
    "RC_CONSENSUS_ACROSS_RUNS",
    "RC_FEASIBILITY_EXCLUDES",
    "RC_NEAR_EQUIVALENT_HONESTY",
    "RC_NO_COMPARABLE_HISTORY",
    "RC_NOT_PRODUCTION_ELIGIBLE",
    "RC_SINGLE_CASE_ONLY",
    "RC_UNMAPPED_EPISODES",
)

#: Fewest paired differences a per-mission bootstrap may run on.
#:
#: Below this the 2.5th and 97.5th percentiles of the bootstrap
#: distribution are order statistics of a handful of resampled means —
#: the "interval" is mostly the sample replayed at itself, and quoting
#: it as a CI would dress four numbers up as a measurement. A group this
#: small is *described* (its mean, its size) and never concluded from,
#: which is the same posture G2 takes toward an under-sampled run.
MIN_PAIRS_PER_CASE = 5

#: How many seeds :func:`map_contexts` will try per mission before
#: declaring an episode unmappable. Context ids are one-way hashes, so
#: the only way back from an id to its (mission, seed) is to regenerate
#: candidates and compare. Evaluation seeds start at 0 and count up
#: (``build_evaluation_contexts``), so any evaluation episode from a
#: sanely-sized run is found in the first few dozen; the bound exists so
#: a report full of foreign ids terminates instead of searching forever.
SEED_SEARCH_BOUND = 4096


def map_contexts(profile: TaskProfile, wanted: set[str]) -> dict[str, dict[str, Any]]:
    """``episode_context_id`` → ``{"mission_id", "seed"}`` for this profile.

    The id is ``sha256_short`` of the context payload (HĐ-3.1) — one-way
    by design, so this walks the id forward: regenerate every
    (mission, seed) context the evaluation generator could have built,
    hash it, and keep the ones the report actually used. Deterministic,
    needs no new storage, and works on every report already written.

    Ids that never match — neighborhood variants, a custom first seed,
    a different profile's episodes — are simply absent from the result.
    The caller reports them as unmapped rather than guessing: an episode
    that cannot be attributed to a mission must not be counted in one.
    """
    mapping: dict[str, dict[str, Any]] = {}
    if not wanted:
        return mapping
    for seed in range(SEED_SEARCH_BOUND):
        for mission in profile.missions:
            context = EpisodeContext(
                task_profile_id=profile.id,
                mission_id=mission.id,
                seed=seed,
                environment_variant=NOMINAL_VARIANT,
                sample_set="evaluation",
            )
            identifier = context.episode_context_id
            if identifier in wanted and identifier not in mapping:
                mapping[identifier] = {"mission_id": mission.id, "seed": seed}
        if len(mapping) == len(wanted):
            break
    return mapping


def case_table(
    profile: TaskProfile,
    report: Mapping[str, Any],
    *,
    seed: int = 0,
    min_pairs: int = MIN_PAIRS_PER_CASE,
) -> dict[str, Any]:
    """Per-mission ΔU between the run's recommended pair. Never raises.

    Reads the pair the card actually compared (``comparison_pair``) and
    the per-episode utilities the report stored, pairs them on context,
    groups by mission via :func:`map_contexts`, and bootstraps each
    group with the canonical :func:`paired_bootstrap_ci` — the same
    function, the same seed discipline, one aggregation level down.

    ``available: False`` with a reason is a result, not an error: a run
    imported from an old report may predate per-episode utilities, and
    an unranked run compared nobody. Both truths belong in the source a
    rule can cite.
    """
    pair = dict(report.get("comparison_pair") or {})
    a_id = pair.get("recommended_candidate_id")
    b_id = pair.get("runner_up_candidate_id")
    if not a_id or not b_id:
        return {"available": False, "reason": "the run compared no pair", "cases": []}

    by_id = {c.get("candidate_id"): c for c in report.get("candidates") or []}
    a, b = by_id.get(a_id), by_id.get(b_id)
    if a is None or b is None:
        return {"available": False, "reason": "the compared pair is not in the report", "cases": []}

    a_util = _utilities(a)
    b_util = _utilities(b)
    if not a_util or not b_util:
        return {
            "available": False,
            "reason": "the report predates per-episode utilities",
            "cases": [],
        }

    shared = sorted(set(a_util) & set(b_util))
    mapping = map_contexts(profile, set(shared))
    unmapped = sorted(identifier for identifier in shared if identifier not in mapping)

    grouped: dict[str, list[str]] = {}
    for identifier in shared:
        attributed = mapping.get(identifier)
        if attributed is not None:
            grouped.setdefault(attributed["mission_id"], []).append(identifier)

    cases: list[dict[str, Any]] = []
    for mission in profile.missions:  # profile order, so the table is stable
        contexts = grouped.get(mission.id)
        if not contexts:
            continue
        deltas = np.asarray([a_util[c] - b_util[c] for c in contexts], dtype=float)
        row: dict[str, Any] = {
            "mission_id": mission.id,
            "n_pairs": int(deltas.size),
            "delta_mean": float(deltas.mean()),
            "delta_median": float(np.median(deltas)),
            "ci95": None,
            "status": "INSUFFICIENT_EPISODES",
            "winner_stack": None,
            "winner_candidate_id": None,
        }
        if deltas.size >= min_pairs:
            low, high = paired_bootstrap_ci(deltas, seed=seed)
            row["ci95"] = [low, high]
            if low > 0.0:
                row["status"] = "CLEAR"
                row["winner_stack"] = a.get("stack_label")
                row["winner_candidate_id"] = a_id
            elif high < 0.0:
                row["status"] = "CLEAR"
                row["winner_stack"] = b.get("stack_label")
                row["winner_candidate_id"] = b_id
            else:
                row["status"] = "NEAR_EQUIVALENT"
        cases.append(row)

    return {
        "available": True,
        "pair": {
            "a": {"candidate_id": a_id, "stack": a.get("stack_label")},
            "b": {"candidate_id": b_id, "stack": b.get("stack_label")},
        },
        "cases": cases,
        "n_unmapped": len(unmapped),
        "unmapped_contexts": unmapped,
    }


def recommendation_source(
    profile: TaskProfile,
    runs: Sequence[Mapping[str, Any]],
    *,
    map_base_dir: Path | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Assemble the one dict the rules read. The only part that loads a map.

    ``runs`` are stored decision runs *for this profile*, as plain dicts
    (``run_id``, ``status``, ``card``, ``report``, ``created_at``,
    ``contracts_version``) — the caller queries, this function reads, so
    the rules stay pure and testable without a database.

    Feasibility comes from :func:`preflight` on a one-candidate draft
    per registered stack: the same rules that vet a launch vet a
    recommendation, and fixing one of them fixes both. Stacks the
    registry itself bars (``reference``, ``withdrawn``) are recorded
    with the registry's own words, because "why is dwa_predictive not
    on this list" deserves the answer that is already written down.
    """
    profile_dump = profile.model_dump(mode="json")

    feasibility: dict[str, dict[str, Any]] = {}
    for info in list_algorithms():
        record: dict[str, Any] = {
            "stack": info.id,
            "production_eligible": info.production_eligible,
            "reference": info.reference,
            "withdrawn": info.withdrawn,
            "blocking": [],
        }
        if info.production_eligible:
            draft = build_draft(profile_dump, [{"stack": info.id}], map_base_dir=map_base_dir)
            record["blocking"] = sorted(
                {item.code for item in preflight(draft) if item.severity == "blocking"}
            )
        feasibility[info.id] = record

    rows: list[dict[str, Any]] = []
    for stored in sorted(runs, key=lambda r: str(r.get("created_at") or "")):
        card = stored.get("card") or None
        report = stored.get("report") or {}
        ranked = card is not None
        recommended = (card or {}).get("recommended") or {}
        rows.append(
            {
                "run_id": str(stored.get("run_id") or ""),
                "status": stored.get("status"),
                "ranked": ranked,
                "recommended_stack": recommended.get("stack"),
                "recommended_candidate_id": recommended.get("candidate_id"),
                "created_at": stored.get("created_at"),
                "contracts_version": stored.get("contracts_version"),
                "evidence": (card or {}).get("evidence"),
                "case_table": case_table(profile, report, seed=seed) if ranked else None,
            }
        )

    winners = sorted({row["recommended_stack"] for row in rows if row["recommended_stack"]})
    n_ranked = sum(1 for row in rows if row["ranked"])

    return {
        "task_profile_id": profile.id,
        "n_runs": len(rows),
        "n_ranked": n_ranked,
        #: 1 = measured on this very profile; 3 = no comparable evidence.
        #: Tier 2 (transfer from a similar environment) is deliberately
        #: absent until it can be done honestly — a field that names its
        #: own gap is how the reader knows the gap exists.
        "evidence_tier": 1 if n_ranked else 3,
        "single_mission": len(profile.missions) == 1,
        "runs": rows,
        "winners": winners,
        "feasibility": feasibility,
    }


def recommend_from_history(source: Mapping[str, Any]) -> tuple[Advice, ...]:
    """Advice about which algorithm to adopt. Never raises, never acts.

    Returns an empty tuple only for a source with nothing to say — which
    does not happen in practice, because "there is no comparable history"
    is itself the most important thing to say.
    """
    try:
        found = tuple(_rules(dict(source)))
    except Exception:  # noqa: BLE001 — advice must never take a caller down
        return ()
    return order(keep_resolvable(found, dict(source)))


# ---------------------------------------------------------------------------


def _utilities(candidate: Mapping[str, Any]) -> dict[str, float]:
    """``episode_context_id`` → stored utility; empty when not recorded."""
    utilities: dict[str, float] = {}
    for episode in candidate.get("episodes") or []:
        identifier = episode.get("episode_context_id")
        value = episode.get("episode_decision_utility")
        if isinstance(identifier, str) and isinstance(value, (int, float)):
            utilities[identifier] = float(value)
    return utilities


def _rules(source: dict[str, Any]) -> Any:
    yield from _feasibility_rules(source)
    yield from _history_rules(source)
    yield from _case_rules(source)


def _feasibility_rules(source: dict[str, Any]) -> Any:
    for stack, record in (source.get("feasibility") or {}).items():
        if not record.get("production_eligible"):
            withdrawn = str(record.get("withdrawn") or "")
            ground = (
                withdrawn
                if withdrawn
                else "a D12 reference adapter: it ignores sensing, and exists to exercise "
                "the pipeline, never to be a contender"
            )
            yield Advice(
                code="RC_NOT_PRODUCTION_ELIGIBLE",
                kind="recommendation",
                severity="disclosure",
                claim=f"{stack} is not on the menu for this deployment, by the registry's "
                "own record",
                ground=ground,
                field_path=f"feasibility.{stack}.withdrawn",
                do="Read the registry entry if the absence surprises you; the reason was "
                "written when the stack was barred, not invented for this answer.",
                do_not="Do not re-add it to a comparison to 'give it a chance' — reference "
                "adapters gamed the gates once already, and a withdrawal was measured.",
                subject=stack,
            )
        elif record.get("blocking"):
            codes = ", ".join(record["blocking"])
            yield Advice(
                code="RC_FEASIBILITY_EXCLUDES",
                kind="recommendation",
                severity="material",
                claim=f"{stack} cannot be recommended for this deployment as declared: "
                f"preflight blocks it ({codes})",
                ground="the same rules that would block launching it — a stack that cannot "
                "run here cannot be advised here, whatever it won elsewhere",
                field_path=f"feasibility.{stack}.blocking",
                do="Resolve the named blocker (choose a model, add the observation, fix the "
                "control period) and this stack re-enters the field.",
                do_not="Do not recommend it anyway on the strength of results from another "
                "deployment; those results ran on hardware this profile does not declare.",
                subject=stack,
            )


def _history_rules(source: dict[str, Any]) -> Any:
    runs = list(source.get("runs") or [])
    ranked = [row for row in runs if row.get("ranked")]
    winners = list(source.get("winners") or [])

    if not ranked:
        eligible = sorted(
            stack
            for stack, record in (source.get("feasibility") or {}).items()
            if record.get("production_eligible") and not record.get("blocking")
        )
        offer = ", ".join(eligible) if eligible else "none — every stack is blocked"
        yield Advice(
            code="RC_NO_COMPARABLE_HISTORY",
            kind="recommendation",
            severity="material",
            claim="no stored comparison on this deployment has ranked a winner, so there "
            "is nothing measured to recommend from",
            ground="a recommendation without a run behind it would be folklore with this "
            "platform's name on it",
            field_path="n_ranked",
            do=f"Run a comparison on this profile. Feasible stacks today: {offer}.",
            do_not="Do not pick a stack from memory or from another project's result and "
            "call it recommended; run the comparison — it is the cheap step.",
        )
        return

    for index, row in enumerate(runs):
        if not row.get("ranked"):
            continue
        stack = row.get("recommended_stack") or row.get("recommended_candidate_id") or "?"
        status = str(row.get("status") or "")
        if status == "NEAR_EQUIVALENT":
            yield Advice(
                code="RC_NEAR_EQUIVALENT_HONESTY",
                kind="recommendation",
                severity="material",
                claim=f"run {row['run_id']} could not statistically separate the top pair; "
                f"{stack} was named by the declared tie-break ladder, not by a measured gap",
                ground="the CI of ΔU contains zero — the two candidates are "
                "indistinguishable on this evidence",
                field_path=f"runs[{index}].status",
                do="Adopt either candidate, or run more episodes if the distinction "
                "matters; the tie-break rung that decided is recorded on the card.",
                do_not=f"Do not describe {stack} as 'better' — the measurement's own "
                "verdict is that it could not tell.",
                subject=str(row.get("run_id") or ""),
            )
        else:
            yield Advice(
                code="RC_CARD_ON_THIS_PROFILE",
                kind="recommendation",
                severity="material",
                claim=f"run {row['run_id']} on this very deployment recommends {stack} ({status})",
                ground="first-tier evidence: measured on this profile's own map, missions "
                "and constraints, with the gate table and the interval on the card",
                field_path=f"runs[{index}].recommended_stack",
                do="Review the card and, with a second person's approval (HĐ-14), adopt "
                "this configuration.",
                do_not="Do not read this as a safety claim — the card bounds what was "
                "measured, in simulation, and says exactly that.",
                subject=str(row.get("run_id") or ""),
            )

    if len(ranked) >= 2 and len(winners) == 1:
        yield Advice(
            code="RC_CONSENSUS_ACROSS_RUNS",
            kind="recommendation",
            severity="material",
            claim=f"every ranked run on this deployment ({len(ranked)}) agrees on {winners[0]}",
            ground="independent runs reaching the same winner is the strongest signal "
            "this table can carry",
            field_path="winners",
            do="Adopt with the usual second-person approval; the agreement is the evidence.",
            do_not="Do not skip the approval because the answer looks settled — "
            "separation of duties is not a formality that consensus waives.",
        )
    elif len(winners) >= 2:
        yield Advice(
            code="RC_CONFLICT_BETWEEN_RUNS",
            kind="recommendation",
            severity="material",
            claim=f"ranked runs on this deployment disagree: {', '.join(winners)} have "
            "each been recommended",
            ground="the runs differ in something — episode count, contracts version, an "
            "edited profile — and that difference, not this module, holds the answer",
            field_path="winners",
            do="Compare the runs' manifests and sample sizes; prefer the larger, newer "
            "run, and re-run if the conflict survives that reading.",
            do_not="Do not average the runs or pick the majority — runs are not votes, "
            "and two small runs do not outweigh one adequate one.",
        )


def _case_rules(source: dict[str, Any]) -> Any:
    if source.get("single_mission") and source.get("n_ranked"):
        yield Advice(
            code="RC_SINGLE_CASE_ONLY",
            kind="recommendation",
            severity="disclosure",
            claim="this deployment declares exactly one mission, so 'which algorithm in "
            "which situations' cannot be answered from its runs — there is only one "
            "situation",
            ground="the per-mission split needs missions to split by; "
            "effective_claim_level caps a one-mission profile at a mission-level claim "
            "for the same reason",
            field_path="single_mission",
            do="Declare the deployment's real mission distribution and re-run; the same "
            "episodes then answer the per-case question at no extra machinery.",
            do_not="Do not read this run's winner as the winner for missions that were "
            "never simulated.",
        )

    for index, row in enumerate(source.get("runs") or []):
        table = row.get("case_table")
        if not table or not table.get("available"):
            continue
        pair = table.get("pair") or {}
        a = (pair.get("a") or {}).get("stack")
        b = (pair.get("b") or {}).get("stack")
        for case_index, case in enumerate(table.get("cases") or []):
            mission = case.get("mission_id")
            path = f"runs[{index}].case_table.cases[{case_index}]"
            if case.get("status") == "CLEAR":
                winner = case.get("winner_stack")
                loser = b if winner == a else a
                low, high = case.get("ci95") or (None, None)
                yield Advice(
                    code="RC_CASE_WINNER",
                    kind="recommendation",
                    severity="material",
                    claim=f"in mission {mission}, {winner} beat {loser}: ΔU CI95 "
                    f"[{low:.4f}, {high:.4f}] over {case.get('n_pairs')} paired episodes",
                    ground="the same paired bootstrap that decides the card, run on this "
                    "mission's episodes alone",
                    field_path=f"{path}.ci95",
                    do="Weight this result by the mission's share of real traffic when "
                    "reading the overall recommendation.",
                    do_not="Do not promote one mission's winner to the whole deployment; "
                    "the overall card already aggregates the missions it declared.",
                    subject=str(mission),
                )
            elif case.get("status") == "NEAR_EQUIVALENT":
                yield Advice(
                    code="RC_CASE_UNDECIDED",
                    kind="recommendation",
                    severity="disclosure",
                    claim=f"in mission {mission} the pair {a} vs {b} is statistically "
                    "indistinguishable — the CI of ΔU contains zero",
                    ground="an interval containing zero licenses no per-case winner, "
                    "exactly as it licenses none overall",
                    field_path=f"{path}.ci95",
                    do="Treat this mission as tied; more seeds per mission would narrow "
                    "the interval if the distinction matters.",
                    do_not="Do not break the tie by eye from the mean — the interval is "
                    "the measurement.",
                    subject=str(mission),
                )
            elif case.get("status") == "INSUFFICIENT_EPISODES":
                yield Advice(
                    code="RC_CASE_INSUFFICIENT",
                    kind="recommendation",
                    severity="disclosure",
                    claim=f"mission {mission} has only {case.get('n_pairs')} paired "
                    f"episodes — below the {MIN_PAIRS_PER_CASE} this module requires "
                    "before quoting an interval",
                    ground="a bootstrap over a handful of pairs replays the sample at "
                    "itself; the numbers are described, not concluded from",
                    field_path=f"{path}.n_pairs",
                    do="Increase seeds per mission (the seed count divides across "
                    "missions) if a per-case verdict for this mission matters.",
                    do_not="Do not read the group's mean as a winner; it has no interval "
                    "around it.",
                    subject=str(mission),
                )
        if table.get("n_unmapped"):
            yield Advice(
                code="RC_UNMAPPED_EPISODES",
                kind="recommendation",
                severity="disclosure",
                claim=f"{table['n_unmapped']} episode(s) of run {row['run_id']} could not "
                "be attributed to a mission and are excluded from the per-case table",
                ground="context ids are one-way hashes; an id the evaluation generator "
                "cannot reproduce (a variant, a custom seed base) has no honest mission "
                "label",
                field_path=f"runs[{index}].case_table.n_unmapped",
                do="Nothing, usually — the overall card still counts these episodes; "
                "only the per-mission split omits them.",
                do_not="Do not assign them to the most plausible mission to make the "
                "table complete.",
                subject=str(row.get("run_id") or ""),
            )
